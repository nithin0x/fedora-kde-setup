// KWin 6 scripting API. Virtual desktop identities are preserved by the installer.
var formerDesktop = null;
workspace.currentDesktopChanged.connect(function (previous) {
    formerDesktop = previous;
});

registerShortcut("OmarchyFormerDesktop", "Omarchy: former workspace", "Meta+Ctrl+Tab", function () {
    if (formerDesktop && workspace.desktops.indexOf(formerDesktop) !== -1) {
        workspace.currentDesktop = formerDesktop;
    }
});

function registerMoveFollow(index) {
    var key = index === 9 ? "0" : String(index + 1);
    registerShortcut("OmarchyMoveFollow" + (index + 1),
        "Omarchy: move window to workspace " + (index + 1) + " and follow",
        "Meta+Shift+" + key, function () {
            var window = workspace.activeWindow;
            var target = workspace.desktops[index];
            if (!window || window.specialWindow || !target) return;
            window.desktops = [target];
            workspace.currentDesktop = target;
        });
}

for (var i = 0; i < Math.min(10, workspace.desktops.length); i++) registerMoveFollow(i);
