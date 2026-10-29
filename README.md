## Hi there 👋

<!--
**NadimGhaznavi/NadimGhaznavi** is a ✨ _special_ ✨ repository because its `README.md` (this file) appears on your GitHub profile.

Here are some ideas to get you started:

- 🔭 I’m currently working on ...
- 🌱 I’m currently learning ...
- 👯 I’m looking to collaborate on ...
- 🤔 I’m looking for help with ...
- 💬 Ask me about ...
- 📫 How to reach me: ...
- 😄 Pronouns: ...
- ⚡ Fun fact: ...
-->

<details>
<summary>Project maintenance and CMDB tracking</summary>

This profile uses the BMForge workflow. Its application payload is this README
and [the CMDB constants file](nadimghaznavi/constants/DNadimGhaznavi.py).

The canonical CMDB name is `NadimGhaznavi`, its subtype is `GitHub Profile`,
and its installation directory is `/opt/prod/nadimghaznavi`.

From a separate checkout of the intended release, using Bash and Python 3.10+:

```sh
scripts/install.sh --check
sudo scripts/install.sh
```

For subsequent releases, use `scripts/upgrade.sh --check` followed by
`sudo scripts/upgrade.sh`. To remove managed files, use
`scripts/uninstall.sh --check` followed by `sudo scripts/uninstall.sh`.
Each script supports `--help`. Unowned files are retained.

Installation verifies the copied payload before writing `.deployment-version`.
The `.installation-manifest.json` file records ownership. Individual files are
replaced atomically; an interrupted upgrade can leave mixed files and requires
inspection or a retry. The successful-version marker remains at the prior
version until verification completes.

After installation, register `NadimGhaznavi` in CMDB and verify discovery on the
workstation. Run **Re-Scan Applications** after upgrades.

For local validation:

```sh
python3 .agents/bmforge/manage.py check --project .
python3 -B scripts/check-cmdb.py --name NadimGhaznavi nadimghaznavi/constants/DNadimGhaznavi.py
python3 -B -m unittest discover -s tests -v
```

Record changes in `CHANGELOG.md`. `scripts/new-release.sh --help` describes
the standard release workflow; release publication and workstation deployment
are separate operations.

</details>
