# Installation and customization

## Requirements

Use a conventional Fedora 44 KDE Plasma 6 installation with Python 3.11+.
Kinoite and other immutable variants are outside the installer's supported
scope. The installer uses standard `~/.config`, `~/.local/share` and
`~/.local/state` locations; custom XDG base directories are rejected on live
installation. Symlinked destinations are also rejected so an existing dotfiles
manager is not overwritten indirectly.

## Install

From the repository directory:

```bash
./setup.sh
./setup.sh --apply --packages
```

The first command previews file changes. The second installs the selected
modules and their Fedora dependencies. DNF asks before installing packages;
there is no automatic system upgrade or package removal. To use dependencies
already installed, omit `--packages`.

Reopen applications and sign out/back in after installation. GTK and
libadwaita applications vary in how they honor color overrides. Flameshot also
depends on the desktop screenshot portal; verify capture after signing in.
This installer prepares configuration without controlling the running session.

## Choose modules

```bash
./setup.sh --modules theme,terminal --apply
./setup.sh --modules shortcuts --apply --packages
./setup.sh --modules editors --apply --packages
```

`terminal` replaces the selected Alacritty, tmux, bat and fastfetch files after
backing them up. It uses normal Ctrl+C behavior in terminals; clipboard copy
and paste use Ctrl+Shift+C/V.

`shortcuts` installs its own launchers and KWin workspace helper. It assigns the
documented keys and removes those same active key combinations from conflicting
actions, preserving other shortcuts. It keeps existing workspace IDs and names,
adds missing workspaces and never reduces an existing workspace count.
Zoom shortcuts are disabled by default; set
`disable_desktop_zoom_shortcuts = false` to leave them as they were.
Automatic tiling is separate from this setup; the supplied workflow uses KDE's
manual tile editor and quick tiling.

`editors` is optional because it installs selected Neovim starter files. The
starter downloads LazyVim and plugins on first launch; its lockfile records
plugin revisions. Existing plugin files outside the starter remain in place,
so use a clean Neovim config for a predictable starter installation.
To load your own plugin specs, create `lua/plugins/` and enable its import in
`lua/config/lazy.lua`.
To start Neovim without user configuration, use `nvim -u NONE`.

The VS Code theme is installed locally. Reload VS Code, select **Lumon** using
**Preferences: Color Theme**, and optionally merge
`~/.config/Code/User/lumon-settings.json` into your settings. The installer
leaves your `settings.json` and its comments intact. VS Code itself is not
installed through an external repository by this setup.

## Personal profile

```bash
cp profiles/default.toml setup.local.toml
```

Edit the local copy. Write each command as an array of arguments:

```toml
font = "JetBrains Mono"
font_size = 11
workspaces = 10

[apps]
browser = ["firefox", "--new-window"]
editor = ["kate"]
```

Missing values inherit the default profile. For an alternative profile:

```bash
./setup.sh --config path/to/profile.toml
```

Install any custom application commands separately. For example, selecting a
different browser does not configure a third-party package repository.
The tmux launcher expects the configured terminal to support `-e`, as Alacritty
does. The default font does not need Nerd Font glyphs or a font download.

## Preview in a separate directory

```bash
mkdir -p /tmp/kde-setup-preview
./setup.sh --target-home /tmp/kde-setup-preview --apply
```

This stages configuration and backups under the chosen directory, without
installing packages or contacting the desktop session. Do not use a staging
directory inside this repository. Generated paths target that staging home;
run the installer against the real home when ready, instead of copying a
staging directory blindly.

## Restore

Backups stay on the installation machine under
`~/.local/state/fedora-kde-setup/backups/`. Each run stores original files,
permissions and checksums. The installer prints its backup ID.

```bash
./setup.sh --restore BACKUP_ID
./setup.sh --restore BACKUP_ID --apply
```

The first command previews restoration. The second restores the saved files
and removes files created by that installation. It stops before changing files
if any installed file was subsequently edited or a backup checksum differs.
Resolve those cases manually from the backup directory. Empty directories and
packages installed by DNF are not removed. Sign out/back in after restoring
KDE settings. Use the same `--target-home` when restoring a staged installation.

## Check the desktop

After installing on Fedora KDE:

1. Sign out and back in; open a KDE app and the terminal to check colors.
2. Launch apps with the configured keys, switch workspaces and quick tile a window.
3. Capture a region with Flameshot; check the PNG and clipboard.
4. Open tmux and check splits, navigation and copy mode.
5. If using the optional editors, let Neovim install plugins and select Lumon in VS Code.

The automated tests use temporary homes and simulated KWin workspaces. Live
desktop behavior, package installation and Neovim plugin downloads need to be
checked on the destination machine.

Drivers, codecs, debloating, automatic tiling, bootloader customization and VM
provisioning are outside this installer's scope.
