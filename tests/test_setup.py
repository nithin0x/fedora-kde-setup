"""Exercise installation against disposable homes, never the desktop session."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup", ROOT / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
privacy_spec = importlib.util.spec_from_file_location("privacy", ROOT / "scripts/check-public-files.py")
privacy = importlib.util.module_from_spec(privacy_spec)
privacy_spec.loader.exec_module(privacy)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kde-setup-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.cfg = setup.load_profile(ROOT / "profiles/default.toml")

    def build(self, modules=None):
        plan = setup.Plan(self.home)
        for name in modules or self.cfg["modules"]:
            getattr(setup, name)(plan, self.cfg)
        return plan

    def apply(self, plan):
        with contextlib.redirect_stdout(io.StringIO()):
            setup.install(plan, plan.changed())
        return next((self.home / setup.STATE / "backups").iterdir()).name

    def test_preview_does_not_write(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/setup.py"),
                                 "--target-home", str(self.home)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No changes made", result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_install_is_idempotent_and_restore_recovers_original(self):
        config = self.home / ".config/kdeglobals"
        config.parent.mkdir()
        original = b"# Keep this comment\n[General]\nUnrelated=keep\n"
        config.write_bytes(original)
        config.chmod(0o600)
        css = self.home / ".config/gtk-3.0/gtk.css"
        css.parent.mkdir()
        css.write_text("\n/* Existing user CSS */\nbutton { padding: 2px; }\n")
        original_css = css.read_bytes()
        backup_id = self.apply(self.build())
        self.assertIn("Unrelated=keep", config.read_text())
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertIn("Existing user CSS", css.read_text())
        self.assertEqual(self.build().changed(), {})
        with contextlib.redirect_stdout(io.StringIO()):
            setup.restore(self.home, backup_id, False)
            setup.restore(self.home, backup_id, True)
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(css.read_bytes(), original_css)
        self.assertFalse((self.home / ".config/tmux/tmux.conf").exists())

    def test_preserves_desktop_ids_and_unrelated_shortcuts(self):
        config = self.home / ".config/kwinrc"
        config.parent.mkdir()
        desktop_id = str(uuid.uuid4())
        config.write_text(f"[Desktops]\nNumber=12\nId_1={desktop_id}\nName_1=Work\n")
        shortcuts = self.home / ".config/kglobalshortcutsrc"
        shortcuts.write_text("[other]\ncustom=Meta+Return\\tCtrl+Alt+X,none,Custom\nkeep=Alt+F2,none,Keep\n")
        plan = self.build(["shortcuts"])
        groups = setup.read_kconfig(plan.text(".config/kwinrc"))
        self.assertEqual(groups["[Desktops]"]["Id_1"], desktop_id)
        self.assertEqual(groups["[Desktops]"]["Number"], "12")
        self.assertEqual(groups["[Desktops]"]["Name_1"], "Work")
        keys = setup.read_kconfig(plan.text(".config/kglobalshortcutsrc"))
        self.assertEqual(keys["[other]"]["custom"], "Ctrl+Alt+X,none,Custom")
        self.assertEqual(keys["[other]"]["keep"], "Alt+F2,none,Keep")
        self.assertIn("Print", keys["[services][org.flameshot.Flameshot.desktop]"]["Capture"])
        self.assertTrue(keys["[kwin]"]["view_zoom_in"].startswith("none,"))

    @unittest.skipUnless(shutil.which("kreadconfig6"), "requires KDE's kreadconfig6")
    def test_kconfig_can_be_read_by_kde(self):
        plan = self.build(["shortcuts"])
        self.apply(plan)
        result = subprocess.run(["kreadconfig6", "--file", str(self.home / ".config/kwinrc"),
                                 "--group", "Desktops", "--key", "Number"], capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "10")
        result = subprocess.run(["kreadconfig6", "--file", str(self.home / ".config/kglobalshortcutsrc"),
                                 "--group", "services", "--group", "org.flameshot.Flameshot.desktop",
                                 "--key", "Capture"], capture_output=True, text=True)
        self.assertIn("Print", result.stdout)

    def test_refuses_symlinks_and_path_traversal(self):
        (self.home / ".config").symlink_to("/tmp")
        with self.assertRaises(ValueError):
            self.build()
        with self.assertRaises(ValueError):
            setup.safe_path(self.home, "../escape")
        with self.assertRaises(ValueError):
            setup.safe_path(self.home, "/tmp/escape")

    def test_restore_does_not_overwrite_later_edits(self):
        backup_id = self.apply(self.build(["terminal"]))
        target = self.home / ".config/tmux/tmux.conf"
        target.write_text("# User changed this\n")
        with self.assertRaisesRegex(ValueError, "Changed since installation"):
            setup.restore(self.home, backup_id, True)
        self.assertEqual(target.read_text(), "# User changed this\n")

    def test_corrupted_backup_stops_restore_before_any_file_changes(self):
        first = self.home / "first"
        second = self.home / "second"
        first.write_text("first original")
        second.write_text("second original")
        plan = setup.Plan(self.home)
        plan.put("first", "first installed")
        plan.put("second", "second installed")
        backup_id = self.apply(plan)
        saved = self.home / setup.STATE / "backups" / backup_id / "files/first"
        saved.write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "Backup checksum mismatch"):
            setup.restore(self.home, backup_id, True)
        self.assertEqual(first.read_text(), "first installed")
        self.assertEqual(second.read_text(), "second installed")

    def test_failed_install_rolls_back_completed_writes(self):
        plan = setup.Plan(self.home)
        (self.home / "original").write_text("before")
        plan.put("original", "after")
        plan.put("second", "new")
        real_write = setup.atomic_write

        def fail_second(path, data, mode):
            if path == self.home / "second":
                raise OSError("Simulated disk failure")
            return real_write(path, data, mode)

        with patch.object(setup, "atomic_write", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.apply(plan)
        self.assertEqual((self.home / "original").read_text(), "before")
        self.assertFalse((self.home / "second").exists())

    def test_partial_profile_and_invalid_input(self):
        profile = self.home / "custom.toml"
        profile.write_text('font = "JetBrains Mono"\n[apps]\nbrowser = ["custom-browser", "--new-window"]\n')
        cfg = setup.load_profile(profile)
        self.assertEqual(cfg["apps"]["browser"][0], "custom-browser")
        self.assertEqual(cfg["apps"]["terminal"], ["alacritty"])
        profile.write_text('workspaces = 0\n')
        with self.assertRaises(ValueError):
            setup.load_profile(profile)

    def test_font_rejects_control_characters_before_writing(self):
        profile = self.home / "custom.toml"
        for font in ('"font\\u0000name"', '"font\\tname"', '"font\\u007fname"', '"   "'):
            with self.subTest(font=font):
                profile.write_text(f"font = {font}\n")
                with self.assertRaisesRegex(ValueError, "font family"):
                    setup.load_profile(profile)

    def test_staged_restore_command_returns_files_to_original_state(self):
        staged = self.home / "staged home 'quoted'"
        staged.mkdir()
        plan = setup.Plan(staged)
        target = staged / "original"
        target.write_text("before")
        plan.put("original", "after")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            setup.install(plan, plan.changed())
        command = next(line.removeprefix("Restore: ") for line in output.getvalue().splitlines()
                       if line.startswith("Restore: "))
        result = subprocess.run(shlex.split(command), cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(), "before")

    def test_shortcuts_package_selection_includes_tmux(self):
        self.cfg["modules"] = ["shortcuts"]
        with patch.object(setup.subprocess, "run") as run:
            setup.install_packages(self.cfg)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["sudo", "dnf", "install"])
        self.assertIn("tmux", command)

    def test_immutable_kde_settings_are_respected(self):
        with self.assertRaises(ValueError):
            setup.merge_kconfig("[General]\nColorScheme[$i]=Locked\n", {"[General]": {"ColorScheme": "Lumon"}})
        with self.assertRaises(ValueError):
            setup.merge_kconfig("[General][$i]\nColorScheme=Locked\n", {"[General]": {"ColorScheme": "Lumon"}})

    def test_cli_apply_stages_all_modules_without_system_changes(self):
        result = subprocess.run([str(ROOT / "setup.sh"), "--apply", "--target-home", str(self.home),
                                 "--modules", "theme,terminal,shortcuts,editors"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".config/nvim/init.lua").exists())
        self.assertTrue((self.home / ".vscode/extensions/local.lumon-1.0.0/package.json").exists())
        self.assertFalse((self.home / ".config/Code/User/settings.json").exists())
        tomllib.loads((self.home / ".config/alacritty/alacritty.toml").read_text())
        for file in self.home.rglob("*.json"):
            json.loads(file.read_text())

    def test_privacy_check_reports_categories_without_values(self):
        token = "ghp_" + "A" * 30
        (self.home / "leak.txt").write_text(token)
        issues = privacy.check(self.home)
        self.assertIn(("leak.txt", "GitHub credential"), issues)
        self.assertNotIn(token, str(issues))
        (self.home / "leak.txt").unlink()
        (self.home / "snapshots").mkdir()
        (self.home / "snapshots/export.txt").write_text("raw export")
        self.assertIn(("snapshots/export.txt", "private export"), privacy.check(self.home))

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "requires desktop-file-utils")
    def test_generated_desktop_files_validate_with_special_home_path(self):
        special = self.home / 'user space $dollar %percent "quote"'
        special.mkdir()
        plan = setup.Plan(special)
        setup.shortcuts(plan, self.cfg)
        with contextlib.redirect_stdout(io.StringIO()):
            setup.install(plan, plan.changed())
        for desktop in special.rglob("*.desktop"):
            result = subprocess.run(["desktop-file-validate", str(desktop)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_personal_override_cannot_be_tracked_unnoticed(self):
        subprocess.run(["git", "init", "-q", str(self.home)], check=True)
        (self.home / "setup.local.toml").write_text('font = "monospace"\n')
        subprocess.run(["git", "-C", str(self.home), "add", "setup.local.toml"], check=True)
        self.assertIn(("setup.local.toml", "tracked personal override"), privacy.check(self.home))


if __name__ == "__main__":
    unittest.main()
