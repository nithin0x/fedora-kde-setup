// Exercise the script with a fake workspace; no desktop session is contacted.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../assets/shortcuts/kwin/contents/code/main.js"), "utf8");
for (const count of [1, 3, 10, 12]) {
  const shortcuts = new Map();
  let desktopChanged;
  const desktops = Array.from({ length: count }, (_, index) => ({ name: String(index + 1) }));
  const workspace = {
    desktops,
    currentDesktop: desktops[0],
    currentDesktopChanged: { connect(callback) { desktopChanged = callback; } },
    activeWindow: { desktops: [desktops[0]], specialWindow: false },
  };
  vm.runInNewContext(source, {
    workspace,
    registerShortcut(name, description, key, callback) {
      assert(!shortcuts.has(name), `Duplicate shortcut: ${name}`);
      shortcuts.set(name, { key, callback });
    },
  });
  assert.equal(shortcuts.size, Math.min(10, count) + 1);
  const index = Math.min(10, count) - 1;
  const move = shortcuts.get(`OmarchyMoveFollow${index + 1}`);
  assert.equal(move.key, `Meta+Shift+${(index + 1) % 10}`);
  move.callback();
  assert.equal(workspace.activeWindow.desktops[0], desktops[index]);
  assert.equal(workspace.currentDesktop, desktops[index]);
  desktopChanged(desktops[0]);
  const former = shortcuts.get("OmarchyFormerDesktop").callback;
  former();
  assert.equal(workspace.currentDesktop, desktops[0]);
  desktopChanged({ name: "removed" });
  former();
  assert.equal(workspace.currentDesktop, desktops[0]);
  workspace.activeWindow = null;
  move.callback();
  workspace.activeWindow = { specialWindow: true };
  move.callback();
  assert.equal(workspace.currentDesktop, desktops[0]);
}
console.log("KWin shortcut checks: PASS (1, 3, 10 and 12 workspaces)");
