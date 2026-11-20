# Fedora KDE Setup

A portable Lumon desktop palette, terminal configs, and Omarchy-inspired
keyboard workflow for Fedora 44 KDE Plasma 6. Python 3.11 or newer is required.

Download or clone this repository, open its directory, then run:

```bash
# Preview the exact files that would change.
./setup.sh

# Install dependencies and apply the default configuration.
./setup.sh --apply --packages
```

Run as your normal desktop user. The package step uses `sudo dnf install` and
shows DNF's confirmation prompt. Sign out and back in afterward to load KDE
shortcuts and colors.

| Module | What it installs |
| --- | --- |
| `theme` | Lumon KDE and Konsole colors, GTK color overlay, configurable fonts |
| `terminal` | Alacritty, tmux, bat and fastfetch configuration |
| `shortcuts` | App launchers, workspace controls, manual tiling, Flameshot capture |
| `editors` (optional) | LazyVim starter, local VS Code theme and settings snippet |

The first three modules are the default. The installer backs up existing files
before replacing them and merges selected KDE and GTK keys into existing settings.
It preserves workspace identities and unrelated settings. Panels, wallpaper,
display scaling, drivers and virtual machines stay as they are.

Customize the font, apps or workspace count in a local profile:

```bash
cp profiles/default.toml setup.local.toml
# Edit setup.local.toml, then preview again.
./setup.sh
```

`setup.local.toml` is ignored by Git. The default `monospace` font works without
downloading fonts. Set `font = "JetBrains Mono"` if that family is installed.

Use only the modules you want:

```bash
./setup.sh --modules theme,terminal --apply --packages
./setup.sh --modules editors --apply --packages
```

Every installation prints a backup ID and restore command. Restore uses
checksums to protect files edited after installation.

- [Installation, customization and restore](docs/setup.md)
- [Keyboard shortcuts](docs/shortcuts.md)
- [Contributing and publication checks](CONTRIBUTING.md)

Reusable assets live under `assets/`; configuration defaults under `profiles/`;
installation code under `scripts/`. No personal snapshot, package inventory,
credentials, user paths, machine IDs or private backup state is bundled.

The [contribution guide](CONTRIBUTING.md) covers bug reports and checks to run
before submitting changes. GitHub Actions runs disposable-home tests, workspace
shortcut checks and the public-file check on pushes and pull requests.

Original files use the [MIT license](LICENSE). The bundled LazyVim starter keeps
its Apache 2.0 license; see [third-party notices](THIRD_PARTY_NOTICES.md).
# fedora-kde-setup
