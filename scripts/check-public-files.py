#!/usr/bin/env python3
"""Check this repository for common secrets and accidental private exports."""
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "personal home path": re.compile(rb"/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+"),
    "email address": re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "GitHub credential": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "API credential": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|sk_live_[A-Za-z0-9]{16,}"),
    "private key": re.compile(b"-----BEGIN " + rb"(?:OPENSSH |RSA |EC )?PRIVATE KEY-----"),
    "machine UUID": re.compile(rb"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b"),
    "credential assignment": re.compile(
        rb"(?im)^\s*(?:export\s+)?(?:[A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|SECRET_KEY)|PASSWORD)\s*=\s*[\"']?[A-Za-z0-9_+/=-]{12,}"),
}
PRIVATE_NAMES = {".env", ".git-credentials", ".bash_history", "auth.json", "credentials", "credentials.json"}
PRIVATE_TOP = {"snapshots", "backups", "inventory", ".aws", ".ssh", ".codex", ".agents", ".config", ".local"}


def check(root):
    issues = []
    for file in sorted(root.rglob("*")):
        rel = file.relative_to(root)
        if any(p in {".git", "__pycache__"} for p in rel.parts):
            continue
        if file.is_symlink():
            issues.append((str(rel), "symlink"))
            continue
        if not file.is_file():
            continue
        if rel.parts[0] in PRIVATE_TOP or file.name in PRIVATE_NAMES or file.name.startswith(".env."):
            issues.append((str(rel), "private export"))
        if file.name == "setup.local.toml":
            # Personal overrides are allowed locally, but must remain ignored/untracked.
            if shutil.which("git"):
                tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", str(rel)],
                                         capture_output=True, timeout=10, check=False)
                if tracked.returncode == 0:
                    issues.append((str(rel), "tracked personal override"))
            continue
        data = file.read_bytes()
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                issues.append((str(rel), label))
    return issues


if __name__ == "__main__":
    issues = check(ROOT)
    for path, label in issues:
        print(f"{path}: {label}")  # Report categories, never matching secret values.
    print(f"Public-file check: {'FAIL' if issues else 'PASS'}")
    sys.exit(bool(issues))
