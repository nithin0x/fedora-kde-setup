#!/usr/bin/env python3
"""Install portable user configuration, preview by default, with backups."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"theme", "terminal", "shortcuts", "editors"}
STATE = ".local/state/fedora-kde-setup"


def safe_path(home, relative):
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("Invalid relative destination")
    current = home
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Destination is a symlink; manage it manually: {relative}")
    return current


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_kconfig(text):
    groups = {}
    group = ""
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            group = line
        elif "=" in line and not line.lstrip().startswith(("#", ";")):
            key, value = line.split("=", 1)
            groups.setdefault(group, {})[key] = value
    return groups


def merge_kconfig(text, changes):
    """Edit selected keys, preserving unrelated keys, comments and groups."""
    lines = text.splitlines()
    for group, updates in changes.items():
        if group + "[$i]" in lines:
            raise ValueError(f"KDE policy locks group {group}")
        starts = [i for i, line in enumerate(lines) if line == group]
        if len(starts) > 1:
            raise ValueError(f"Duplicate KDE configuration group {group}")
        if not starts:
            if lines and lines[-1]:
                lines.append("")
            lines.append(group)
            starts = [len(lines) - 1]
        start = starts[0] + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
        for key, value in updates.items():
            matches = [i for i in range(start, end)
                       if "=" in lines[i] and lines[i].split("=", 1)[0].split("[", 1)[0] == key]
            if any("[$i]" in lines[i].split("=", 1)[0] for i in matches):
                raise ValueError(f"KDE policy locks {group}/{key}")
            if len(matches) > 1:
                raise ValueError(f"Duplicate KDE configuration key {group}/{key}")
            new = f"{key}={value}"
            if matches:
                lines[matches[0]] = new
            else:
                lines.insert(end, new)
                end += 1
    return "\n".join(lines) + "\n"


def load_profile(path):
    profile = tomllib.loads(path.read_text())
    defaults = tomllib.loads((ROOT / "profiles/default.toml").read_text())
    if not isinstance(profile.get("apps", {}), dict):
        raise ValueError("apps must be a TOML table of command arrays")
    apps = {**defaults["apps"], **profile.get("apps", {})}
    profile = {**defaults, **profile, "apps": apps}
    modules = profile["modules"]
    if (not isinstance(modules, list) or not modules or
            any(not isinstance(m, str) or m not in MODULES for m in modules)):
        raise ValueError("Select one or more valid modules")
    font = profile.get("font", "monospace")
    if (not isinstance(font, str) or not font.strip()
            or any(ord(c) < 32 or ord(c) == 127 or c in ',\\"' for c in font)):
        raise ValueError("Use a font family without quotes, commas, backslashes or control characters")
    size = profile.get("font_size", 11)
    if not isinstance(size, (float, int)) or isinstance(size, bool) or not 6 <= size <= 32:
        raise ValueError("font_size must be between 6 and 32")
    count = profile.get("workspaces", 10)
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError("workspaces must be between 1 and 20")
    if type(profile.get("disable_desktop_zoom_shortcuts", True)) is not bool:
        raise ValueError("disable_desktop_zoom_shortcuts must be true or false")
    for name in ("terminal", "browser", "files", "editor", "monitor"):
        args = profile.get("apps", {}).get(name)
        if (not isinstance(args, list) or not args or
                any(not isinstance(a, str) or not a or any(c in a for c in "\x00\n\r") for a in args)):
            raise ValueError(f"apps.{name} must be a nonempty array of command arguments")
    return profile


class Plan:
    def __init__(self, home):
        self.home = home
        self.files = {}

    def text(self, path):
        if path in self.files:
            return self.files[path][0].decode()
        source = safe_path(self.home, path)
        return source.read_text() if source.exists() else ""

    def put(self, path, data, mode=0o644):
        target = safe_path(self.home, path)
        if target.exists():
            mode = target.stat().st_mode & 0o777
        self.files[path] = (data.encode() if isinstance(data, str) else data, mode)

    def kconfig(self, path, changes):
        self.put(path, merge_kconfig(self.text(path), changes))

    def copy(self, source, destination):
        source = ROOT / "assets" / source
        if source.is_dir():
            for file in sorted(source.rglob("*")):
                if file.is_file():
                    self.put(str(Path(destination) / file.relative_to(source)), file.read_bytes())
        else:
            self.put(destination, source.read_bytes())

    def changed(self):
        return {path: (data, mode) for path, (data, mode) in self.files.items()
                if not safe_path(self.home, path).exists()
                or safe_path(self.home, path).read_bytes() != data}


def theme(plan, cfg):
    plan.copy("theme/color-schemes", ".local/share/color-schemes")
    plan.copy("theme/konsole", ".local/share/konsole")
    colors = read_kconfig((ROOT / "assets/theme/color-schemes/Lumon.colors").read_text())
    changes = {group: values for group, values in colors.items()
               if group.startswith(("[Colors:", "[ColorEffects:", "[WM]"))}
    changes.update({"[General]": {"ColorScheme": "Lumon", "font": f'{cfg["font"]},10,-1,5,400,0,0,0,0,0',
                                   "fixed": f'{cfg["font"]},10,-1,5,400,0,0,0,0,0'},
                    "[Icons]": {"Theme": "breeze-dark"}})
    plan.kconfig(".config/kdeglobals", changes)
    plan.put(".local/share/konsole/Lumon.profile", merge_kconfig("", {
        "[General]": {"Name": "Lumon", "Parent": "FALLBACK/"},
        "[Appearance]": {"ColorScheme": "Lumon", "Font": f'{cfg["font"]},11,-1,5,400,0,0,0,0,0'}}))
    plan.kconfig(".config/konsolerc", {"[Desktop Entry]": {"DefaultProfile": "Lumon.profile"}})
    for version in (3, 4):
        base = f".config/gtk-{version}.0"
        plan.copy("theme/lumon.css", f"{base}/lumon.css")
        css = plan.text(f"{base}/gtk.css")
        marker = "/* BEGIN FEDORA KDE SETUP */\n@import url(\"lumon.css\");\n/* END FEDORA KDE SETUP */"
        css = re.sub(r"/\* BEGIN FEDORA KDE SETUP \*/.*?/\* END FEDORA KDE SETUP \*/\n?", "", css, flags=re.S)
        plan.put(f"{base}/gtk.css", marker + "\n" + css)
        plan.kconfig(f"{base}/settings.ini", {"[Settings]": {
            "gtk-application-prefer-dark-theme": "true", "gtk-font-name": f'{cfg["font"]} 10',
            "gtk-theme-name": "Breeze", "gtk-icon-theme-name": "breeze-dark"}})


def terminal(plan, cfg):
    for name in ("active-theme.toml", "keybinds.toml"):
        plan.copy(f"terminal/alacritty/{name}", f".config/alacritty/{name}")
    template = (ROOT / "assets/terminal/alacritty/alacritty.toml.in").read_text()
    plan.put(".config/alacritty/alacritty.toml",
             template.replace("@FONT@", json.dumps(cfg["font"]))
             .replace("@FONT_SIZE@", str(cfg["font_size"])))
    plan.copy("terminal/tmux", ".config/tmux")
    plan.copy("terminal/bat/Lumon.tmTheme", ".config/bat/themes/Lumon.tmTheme")
    plan.put(".config/bat/config", '--theme="Lumon"\n')
    plan.copy("terminal/fastfetch.jsonc", ".config/fastfetch/config.jsonc")


def desktop_quote(value):
    # Desktop Exec fields have their own escaping rules, separate from a shell.
    escaped = value.replace("%", "%%").replace("\\", "\\\\\\\\")
    for c in ('"', '`', '$'):
        escaped = escaped.replace(c, "\\\\" + c)
    return '"' + escaped + '"'


def key_identity(value):
    parts = value.split("+")
    return "+".join(sorted(parts[:-1]) + parts[-1:]).casefold()


def shortcuts(plan, cfg):
    base = ".local/share/omarchy-kde-shortcuts"
    plan.copy("shortcuts/launch.py", f"{base}/launch.py")
    plan.copy("shortcuts/CHEATSHEET.txt", f"{base}/CHEATSHEET.txt")
    plan.copy("shortcuts/kwin", ".local/share/kwin/scripts/omarchy-kde")
    apps = dict(cfg["apps"])
    apps.update({"tmux": apps["terminal"] + ["-e", "tmux", "new-session", "-A", "-s", "main"],
                 "launcher": ["krunner"], "settings": ["systemsettings", "kcm_keys"],
                 "shortcuts": ["kdialog"], "screenshot": ["flameshot"]})
    plan.put(f"{base}/apps.json", json.dumps(apps, indent=2) + "\n")
    runner = f'/usr/bin/python3 {desktop_quote(str(plan.home / base / "launch.py"))}'
    bindings = {"terminal": "Meta+Return", "tmux": "Meta+Alt+Return", "browser": "Meta+Shift+B",
                "files": "Meta+Shift+F", "editor": "Meta+Shift+N", "monitor": "Meta+Shift+T",
                "launcher": "Meta+Space", "shortcuts": "Meta+K", "settings": "Meta+Ctrl+K"}
    changes = {}
    for name, keys in bindings.items():
        service = f"omarchy-kde-{name}.desktop"
        plan.put(f".local/share/kglobalaccel/{service}",
                 "[Desktop Entry]\nType=Application\n" + f"Name=KDE setup: {name}\nExec={runner} {name}\n" +
                 "Icon=preferences-desktop-keyboard-shortcuts\nX-KDE-GlobalAccel-CommandShortcut=true\n" +
                 f"X-KDE-Shortcuts={keys}\nStartupNotify=false\n")
        changes[f"[{service}]"] = {"_launch": f"{keys},none,{name}"}
    kwin = {"Edit Tiles": "Meta+T", "Window Fullscreen": "Meta+F", "Window Maximize": "Meta+Alt+F",
            "Window Close": "Meta+W\\tMeta+Q\\tAlt+F4", "Switch to Next Desktop": "Meta+Tab",
            "Switch to Previous Desktop": "Meta+Shift+Tab", "OmarchyFormerDesktop": "Meta+Ctrl+Tab"}
    for direction, tile in (("Left", "Left"), ("Right", "Right"), ("Up", "Top"), ("Down", "Bottom")):
        kwin[f"Switch Window {direction}"] = f"Meta+{direction}"
        kwin[f"Window Quick Tile {tile}"] = f"Meta+Shift+{direction}"
    kwinconfig = read_kconfig(plan.text(".config/kwinrc")).get("[Desktops]", {})
    try:
        count = max(cfg["workspaces"], int(kwinconfig.get("Number", "1")))
    except ValueError:
        raise ValueError("Existing workspace count is invalid") from None
    if not 1 <= count <= 20:
        raise ValueError("Existing workspace count is outside KDE's supported range")
    desktops = {"Number": str(count), "Rows": str(2 if count > 5 else 1)}
    for index in range(1, count + 1):
        if not kwinconfig.get(f"Id_{index}"):
            desktops[f"Id_{index}"] = str(uuid.uuid4())
        if not kwinconfig.get(f"Name_{index}"):
            desktops[f"Name_{index}"] = str(index)
    for index in range(1, min(count, 10) + 1):
        key = str(index % 10)
        kwin[f"Switch to Desktop {index}"] = f"Meta+{key}"
        kwin[f"OmarchyMoveFollow{index}"] = f"Meta+Shift+{key}"
    if cfg.get("disable_desktop_zoom_shortcuts", True):
        kwin.update({name: "none" for name in ("view_zoom_in", "view_zoom_out", "view_actual_size")})
        plan.kconfig(".config/kwinrc", {"[Effect-zoom]": {"InitialZoom": "1"}})
    plan.kconfig(".config/kwinrc", {"[Desktops]": desktops, "[Plugins]": {"omarchy-kdeEnabled": "true"}})
    changes["[kwin]"] = {action: f"{keys},none,{action}" for action, keys in kwin.items()}
    changes["[services][org.flameshot.Flameshot.desktop]"] = {
        "Capture": "Print\\tMeta+Ctrl+Alt+C,none,Capture screenshot"}
    plan.put(".local/share/applications/org.flameshot.Flameshot.desktop",
             "[Desktop Entry]\nType=Application\nName=Flameshot\nExec=flameshot\n" +
             "Icon=org.flameshot.Flameshot\nActions=Capture;Configure;\n" +
             "X-KDE-DBUS-Restricted-Interfaces=org.kde.kwin.Screenshot,org.kde.KWin.ScreenShot2\n" +
             f"\n[Desktop Action Capture]\nName=Take screenshot\nExec={runner} screenshot\n" +
             "\n[Desktop Action Configure]\nName=Configure\nExec=flameshot config\n")
    path = ".config/kglobalshortcutsrc"
    claimed = {key_identity(k) for entries in changes.values() for value in entries.values()
               for k in value.split(",", 1)[0].split("\\t") if k != "none"}
    for group, entries in read_kconfig(plan.text(path)).items():
        for action, value in entries.items():
            if action.startswith("_") or action in changes.get(group, {}):
                continue
            fields = value.split(",", 2)
            active = fields[0].split("\\t")
            keep = [k for k in active if key_identity(k) not in claimed]
            if active != keep:
                fields[0] = "\\t".join(keep) or "none"
                changes.setdefault(group, {})[action] = ",".join(fields)
    plan.kconfig(path, changes)


def editors(plan, cfg):
    # A separate optional module: users with existing editor setups can omit it.
    plan.copy("editors/nvim", ".config/nvim")
    plan.copy("editors/vscode", ".vscode/extensions/local.lumon-1.0.0")
    # Keep the user's JSONC settings file intact and provide a separate snippet.
    plan.put(".config/Code/User/lumon-settings.json", json.dumps({
        "workbench.colorTheme": "Lumon", "editor.fontFamily": cfg["font"],
        "terminal.integrated.fontFamily": cfg["font"], "window.autoDetectColorScheme": False,
    }, indent=2) + "\n")


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".kde-setup-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install(plan, changes):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    backup = safe_path(plan.home, f"{STATE}/backups/{run_id}")
    backup.mkdir(parents=True, mode=0o700)
    backup.chmod(0o700)
    manifest = {"version": 1, "files": []}
    for relative, (data, _) in changes.items():
        target = safe_path(plan.home, relative)
        exists = target.exists()
        item = {"path": relative, "existed": exists, "installed_sha256": digest(data)}
        if exists:
            original = target.read_bytes()
            item.update({"mode": target.stat().st_mode & 0o777, "original_sha256": digest(original)})
            saved = safe_path(backup, f"files/{relative}")
            atomic_write(saved, original, 0o600)
        manifest["files"].append(item)
    atomic_write(backup / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), 0o600)
    completed = []
    try:
        for item in manifest["files"]:
            relative = item["path"]
            data, mode = changes[relative]
            atomic_write(safe_path(plan.home, relative), data, mode)
            completed.append(item)
    except BaseException:
        for item in reversed(completed):
            restore_item(plan.home, backup, item)
        raise
    command = ["./setup.sh", "--restore", run_id, "--apply"]
    if plan.home != Path.home().resolve():
        command.extend(["--target-home", str(plan.home)])
    print(f"Backup ID: {run_id}\nRestore: {shlex.join(command)}")


def restore_item(home, backup, item):
    target = safe_path(home, item["path"])
    if item["existed"]:
        original = safe_path(backup, "files/" + item["path"]).read_bytes()
        if digest(original) != item["original_sha256"]:
            raise ValueError("Backup checksum mismatch")
        atomic_write(target, original, item["mode"])
    else:
        target.unlink(missing_ok=True)


def restore(home, run_id, apply):
    if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", run_id):
        raise ValueError("Invalid backup ID")
    backup = safe_path(home, f"{STATE}/backups/{run_id}")
    manifest = json.loads(safe_path(backup, "manifest.json").read_text())
    for item in manifest["files"]:
        target = safe_path(home, item["path"])
        if not target.is_file() or digest(target.read_bytes()) != item["installed_sha256"]:
            raise ValueError(f'Changed since installation; restore it manually: {item["path"]}')
        if item["existed"]:
            saved = safe_path(backup, "files/" + item["path"])
            if digest(saved.read_bytes()) != item["original_sha256"]:
                raise ValueError("Backup checksum mismatch")
    print(f'{"Restoring" if apply else "Would restore"} {len(manifest["files"])} files')
    if apply:
        for item in reversed(manifest["files"]):
            restore_item(home, backup, item)


def install_packages(cfg):
    packages = set()
    modules = set(cfg["modules"])
    if "theme" in modules:
        packages.add("breeze-gtk")
    if "terminal" in modules:
        packages.update(("alacritty", "tmux", "bat", "fastfetch"))
    if "shortcuts" in modules:
        packages.update(("flameshot", "kdialog", "tmux"))
        for args in cfg["apps"].values():
            if args[0] in {"alacritty", "firefox", "kate", "dolphin", "plasma-systemmonitor"}:
                packages.add(args[0])
    if "editors" in modules:
        packages.update(("neovim", "git", "ripgrep", "fd-find", "gcc", "make", "unzip"))
    if packages:
        subprocess.run(["sudo", "dnf", "install", *sorted(packages)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the previewed changes")
    parser.add_argument("--config", type=Path, help="TOML profile (default: setup.local.toml, if present)")
    parser.add_argument("--modules", help="Comma-separated module selection")
    parser.add_argument("--packages", action="store_true", help="Also install Fedora packages via sudo dnf")
    parser.add_argument("--target-home", type=Path, help="Stage files in another home directory; no system operations")
    parser.add_argument("--restore", metavar="BACKUP_ID", help="Preview or apply an earlier backup")
    args = parser.parse_args()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        parser.error("Run as your desktop user, without sudo")
    home = (args.target_home or Path.home()).expanduser().resolve()
    if not home.is_dir():
        parser.error("Home directory must already exist")
    if home == Path("/") or home == ROOT or home.is_relative_to(ROOT):
        parser.error("Choose a staging directory outside the repository")
    if args.packages and (not args.apply or args.target_home or args.restore):
        parser.error("--packages requires --apply on the current user's home")
    if not args.target_home:
        for var, expected in (("XDG_CONFIG_HOME", home / ".config"),
                              ("XDG_DATA_HOME", home / ".local/share"),
                              ("XDG_STATE_HOME", home / ".local/state")):
            if os.environ.get(var) and Path(os.environ[var]) != expected:
                parser.error(f"Custom {var} is not supported; use --target-home for staging")
    if args.restore:
        restore(home, args.restore, args.apply)
        return
    config_path = args.config or (ROOT / "setup.local.toml" if (ROOT / "setup.local.toml").exists()
                                  else ROOT / "profiles/default.toml")
    cfg = load_profile(config_path)
    if args.modules:
        cfg["modules"] = args.modules.split(",")
        if not set(cfg["modules"]) <= MODULES:
            parser.error("Unknown module")
    if args.apply and not args.target_home:
        system = Path("/etc/os-release").read_text()
        if not re.search(r'^ID=["\x27]?fedora["\x27]?$', system, re.M) or Path("/run/ostree-booted").exists():
            parser.error("Supported target: conventional Fedora KDE; stage files elsewhere with --target-home")
        if not shutil.which("kwin_wayland") and not shutil.which("kwin_x11"):
            parser.error("KDE Plasma 6 is required")
    plan = Plan(home)
    for name in dict.fromkeys(cfg["modules"]):
        {"theme": theme, "terminal": terminal, "shortcuts": shortcuts, "editors": editors}[name](plan, cfg)
    changes = plan.changed()
    print("Modules: " + ", ".join(cfg["modules"]))
    for path in changes:
        print("  " + path)
    print(f'{"Installing" if args.apply else "Preview:"} {len(changes)} changed files')
    if not args.apply:
        print("No changes made. Add --apply to install; --packages optionally installs dependencies.")
        return
    if args.packages:
        install_packages(cfg)
    if changes:
        install(plan, changes)
    if "terminal" in cfg["modules"] and shutil.which("bat") and not args.target_home:
        result = subprocess.run(["bat", "cache", "--build"], check=False)
        if result.returncode:
            print("Configs installed. Run 'bat cache --build' again to finish the bat theme cache.")
    print("Configuration ready. Sign out and back in to load KDE shortcuts and colors.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Setup stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
