# Contributing

| Directory | Contents |
| --- | --- |
| `assets/theme/` | Reusable Lumon palette and GTK overlay |
| `assets/terminal/` | Terminal configuration and syntax colors |
| `assets/shortcuts/` | Launcher, shortcut reference and KWin workspace helper |
| `assets/editors/` | Optional editor starter and theme |
| `profiles/` | Portable defaults |
| `scripts/` | Installer and publication check |
| `tests/` | Disposable-home installation and rollback checks |
| `docs/` | User documentation |

Keep personal overrides in the ignored `setup.local.toml`. Backups, raw
snapshots, package inventories, credentials, browser data, shell history,
machine IDs and local operational notes do not belong in the repository.
The installer generates account-specific paths and workspace IDs on the
destination machine. Backups are written outside the repository.

Before committing:

```bash
python3 scripts/check-public-files.py
python3 -m unittest discover -s tests -v
node tests/test_kwin.js
bash -n setup.sh
git diff --check
git diff --cached
```

The publication check reports file names and categories without printing secret
values. It checks common credential formats, home paths, email addresses,
machine UUIDs and accidental private exports. It is a focused check, not a
guarantee against every possible secret format. Keep it alongside a review of
the staged diff.

Do not add a general home-directory exporter. Add individual, reviewed defaults
or templates when supporting another application. Avoid screenshots containing
account names, private terminals, notifications or browser sessions.

Tests use temporary home directories and do not install packages or contact
the desktop session. Install `git` to run the suite. The KDE file format checks
also need `kreadconfig6` and `desktop-file-validate`; tests skip those checks
when the tools are absent. On Fedora, install `kf6-kconfig` and
`desktop-file-utils` for full coverage. The JavaScript check needs Node.js 18+.

GitHub Actions runs the Python suite on Python 3.11 and 3.14. A separate
Fedora 44 container job installs both KDE validators and runs the suite as an
unprivileged user. Workflow definitions use the official
[checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) actions.

Original files use the [MIT license](LICENSE). The LazyVim starter retains
its upstream Apache 2.0 license under `assets/editors/nvim/LICENSE`.
Preserve the [third-party notices](THIRD_PARTY_NOTICES.md) when redistributing
the repository or adding assets.

For bug reports, include the Fedora and Plasma versions, selected modules,
whether you used a custom profile, and steps to reproduce the problem. Remove
personal paths and account details from logs before posting them.

Tests use disposable homes and mocked KWin workspaces. They do not validate a
running desktop. Follow the [desktop checks](docs/setup.md#check-the-desktop)
after installation.
