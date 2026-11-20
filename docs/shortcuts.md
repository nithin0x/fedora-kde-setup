# Keyboard workflow

Super means the Windows / Meta key. Application commands are configurable in
the profile. These keys apply after installing `shortcuts` and signing in again.

| Keys | Action |
| --- | --- |
| Super+Enter | Terminal |
| Super+Alt+Enter | Terminal with tmux session `main` |
| Super+Shift+B | Browser |
| Super+Shift+F | Files |
| Super+Shift+N | Editor |
| Super+Shift+T | System Monitor |
| Super+Space | KRunner |
| Super+K | Shortcut reference |
| Super+Ctrl+K | KDE shortcut settings |
| Super+Arrow | Focus a window in that direction |
| Super+Shift+Arrow | Quick tile the window |
| Super+T | KDE manual tile editor |
| Super+F | Fullscreen |
| Super+Alt+F | Maximize |
| Super+W / Super+Q / Alt+F4 | Close window |
| Super+1…9, 0 | Workspaces 1…10, when available |
| Super+Shift+1…9, 0 | Move to workspace and follow |
| Super+Tab / Super+Shift+Tab | Next / previous workspace |
| Super+Ctrl+Tab | Former workspace |
| Print / Super+Ctrl+Alt+C | Flameshot region capture, save and clipboard |

Screenshots use your XDG Pictures folder, falling back to `~/Pictures`, with a
`Screenshots` subfolder. Escape cancels selection. Zoom shortcuts are disabled
by the default profile.

Tmux accepts Ctrl+Space or Ctrl+B as its prefix:

| Keys | Action |
| --- | --- |
| Prefix, h / v | Split above/below / side-by-side |
| Prefix, c / r / d | New window / rename / detach |
| Prefix, q / ? | Reload config / list bindings |
| Alt+1…9 | Select tmux window |
| Ctrl+Alt+Arrow | Focus pane |
| Ctrl+Alt+Shift+Arrow | Resize pane |
| Prefix, [ | Copy mode: v selects, y copies, q exits |

The workspace helper uses the [KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/).
The keyboard workflow is inspired by [Omarchy](https://omarchy.org/manual/hotkeys/).
