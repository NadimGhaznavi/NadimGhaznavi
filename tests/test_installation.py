"""Exercise the profile's installation lifecycle in disposable directories."""

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = "nadimghaznavi/constants/DNadimGhaznavi.py"
PAYLOAD = ("README.md", VERSION_FILE)
spec = importlib.util.spec_from_file_location("profile_installation", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="profile-installation-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / "checkout"
        self.destination = self.root / "installed"
        for name in (*PAYLOAD, "scripts/check-cmdb.py"):
            source = ROOT / name
            target = self.checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def installation(self):
        return installer.Installation(self.checkout, destination=self.destination)

    def apply(self, action, *, check=False):
        with redirect_stdout(StringIO()):
            self.installation().apply(action, check=check)

    def snapshot(self):
        return {
            path.relative_to(self.destination).as_posix(): path.read_bytes()
            for path in self.destination.rglob("*") if path.is_file()
        }

    def prepare_upgrade(self):
        path = self.checkout / VERSION_FILE
        source = path.read_text()
        version_line = next(line for line in source.splitlines() if line.strip().startswith("VERSION:"))
        self.old_version = version_line.split('"')[1]
        self.new_version = "9.8.7" if self.old_version != "9.8.7" else "9.8.8"
        path.write_text(source.replace(version_line, version_line.replace(self.old_version, self.new_version)))
        with (self.checkout / "README.md").open("a") as stream:
            stream.write("\nUpdated profile fixture.\n")

    def test_install_has_only_profile_payload_and_bookkeeping(self):
        self.apply("install")
        self.assertEqual(
            set(self.snapshot()),
            {*PAYLOAD, ".deployment-version", ".installation-manifest.json"},
        )
        for name in PAYLOAD:
            self.assertEqual((self.destination / name).read_bytes(), (self.checkout / name).read_bytes())
            self.assertEqual((self.destination / name).stat().st_mode & 0o777, 0o644)
        metadata = self.installation().metadata
        self.assertEqual((self.destination / ".deployment-version").read_text(), metadata["VERSION"] + "\n")
        self.assertEqual(metadata["BASE_DIR"], "/opt/prod/nadimghaznavi")
        self.assertEqual(metadata["CMDB_SUBTYPE"], "GitHub Profile")
        manifest = json.loads((self.destination / ".installation-manifest.json").read_text())
        self.assertEqual(manifest["project"], "NadimGhaznavi")
        self.assertEqual(set(manifest["files"]), set(PAYLOAD))

    def test_check_is_read_only_for_each_operation(self):
        self.apply("install", check=True)
        self.assertFalse(self.destination.exists())
        self.apply("install")
        previous = self.snapshot()
        for action in ("install", "upgrade", "uninstall"):
            with self.subTest(action=action):
                self.apply(action, check=True)
                self.assertEqual(self.snapshot(), previous)

    def test_reinstall_is_idempotent(self):
        self.apply("install")
        previous = self.snapshot()
        self.apply("install")
        self.assertEqual(self.snapshot(), previous)

    def test_upgrade_updates_payload_and_retains_unowned_configuration(self):
        self.apply("install")
        retained = self.destination / "conf/preferences.json"
        retained.parent.mkdir()
        retained.write_text('{"theme": "dark"}\n')
        self.prepare_upgrade()
        self.apply("upgrade")
        for name in PAYLOAD:
            self.assertEqual((self.destination / name).read_bytes(), (self.checkout / name).read_bytes())
        self.assertEqual((self.destination / ".deployment-version").read_text(), self.new_version + "\n")
        self.assertEqual(retained.read_text(), '{"theme": "dark"}\n')

    def test_uninstall_repeats_and_reinstall_preserves_unowned_files(self):
        self.apply("install")
        retained = self.destination / "notes.txt"
        retained.write_text("Keep this personal file.\n")
        for _ in range(2):
            self.apply("uninstall")
            self.assertEqual(retained.read_text(), "Keep this personal file.\n")
            self.assertFalse((self.destination / ".deployment-version").exists())
            for name in PAYLOAD:
                self.assertFalse((self.destination / name).exists())
        self.apply("install")
        self.assertTrue((self.destination / VERSION_FILE).is_file())
        self.assertEqual(retained.read_text(), "Keep this personal file.\n")

    def test_uninstall_removes_empty_installation_and_can_repeat(self):
        self.apply("install")
        self.apply("uninstall")
        self.assertFalse(self.destination.exists())
        self.apply("uninstall")
        self.assertFalse(self.destination.exists())

    def test_upgrade_without_installation_fails_before_mutation(self):
        for check in (True, False):
            with self.subTest(check=check), self.assertRaisesRegex(ValueError, "No installation found"):
                self.apply("upgrade", check=check)
        self.assertFalse(self.destination.exists())

    def test_install_refuses_an_unowned_destination(self):
        self.destination.mkdir()
        (self.destination / "README.md").write_text("Personal notes.\n")
        previous = self.snapshot()
        with self.assertRaisesRegex(ValueError, "without an ownership manifest"):
            self.apply("install")
        self.assertEqual(self.snapshot(), previous)

    def test_upgrade_does_not_claim_an_unowned_file(self):
        self.apply("install")
        path = self.destination / ".installation-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files"].remove("README.md")
        path.write_text(json.dumps(manifest))
        previous = self.snapshot()
        with self.assertRaisesRegex(ValueError, "overwrite an unowned file"):
            self.apply("upgrade")
        self.assertEqual(self.snapshot(), previous)

    def test_upgrade_removes_obsolete_owned_files(self):
        self.apply("install")
        obsolete = self.destination / "old-profile.md"
        obsolete.write_text("Earlier release payload.\n")
        path = self.destination / ".installation-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files"].append("old-profile.md")
        path.write_text(json.dumps(manifest))
        self.apply("upgrade")
        self.assertFalse(obsolete.exists())
        self.assertTrue((self.destination / "README.md").is_file())

    def test_failed_copy_retains_last_successful_version_and_retry_works(self):
        self.apply("install")
        self.prepare_upgrade()
        deployment = self.installation()
        write = deployment.atomic_write

        def fail_readme(path, content, mode=0o644):
            if path == self.destination / "README.md":
                raise OSError("Simulated disk write failure")
            write(path, content, mode)

        with patch.object(deployment, "atomic_write", side_effect=fail_readme):
            with self.assertRaisesRegex(OSError, "Simulated disk write failure"):
                deployment.apply("upgrade")
        self.assertEqual((self.destination / ".deployment-version").read_text(), self.old_version + "\n")
        self.apply("upgrade")
        self.assertEqual((self.destination / ".deployment-version").read_text(), self.new_version + "\n")

    def test_failed_verification_does_not_advance_successful_version(self):
        self.apply("install")
        self.prepare_upgrade()
        deployment = self.installation()
        write = deployment.atomic_write

        def corrupt_readme(path, content, mode=0o644):
            write(path, b"corrupted" if path == self.destination / "README.md" else content, mode)

        with patch.object(deployment, "atomic_write", side_effect=corrupt_readme):
            with self.assertRaisesRegex(ValueError, "Installed file failed verification"):
                deployment.apply("upgrade")
        self.assertEqual((self.destination / ".deployment-version").read_text(), self.old_version + "\n")

    def test_uninstall_refuses_symlink_and_retains_external_file(self):
        self.apply("install")
        external = self.root / "external.md"
        external.write_text("External content.\n")
        readme = self.destination / "README.md"
        readme.unlink()
        readme.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.apply("uninstall")
        self.assertEqual(external.read_text(), "External content.\n")
        self.assertTrue((self.destination / ".deployment-version").is_file())

    def test_invalid_metadata_fails_before_mutation(self):
        path = self.checkout / VERSION_FILE
        source = path.read_text()
        version_line = next(line for line in source.splitlines() if line.strip().startswith("VERSION:"))
        path.write_text(source.replace(version_line, '    VERSION = "invalid"'))
        with self.assertRaisesRegex(ValueError, "semantic version"):
            self.apply("install")
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
