"""Scan publishable files and Git history. Never print matched credential values."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"Bearer [A-Za-z0-9_.-]{20,}"),
]


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def scan():
    paths = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    failures = []
    for raw in set(paths):
        if not raw:
            continue
        name = raw.decode()
        p = ROOT / name
        if p.is_file() and any(regex.search(p.read_bytes()) for regex in PATTERNS):
            failures.append(name)
    try:
        history = git("rev-list", "--objects", "--all").decode().splitlines()
    except subprocess.CalledProcessError:
        history = []
    checked = set()
    for entry in history:
        oid = entry.split(" ", 1)[0]
        if oid in checked or git("cat-file", "-t", oid).strip() != b"blob":
            continue
        checked.add(oid)
        if any(regex.search(git("cat-file", "blob", oid)) for regex in PATTERNS):
            failures.append("history blob " + oid[:12])
    if failures:
        print("Potential credential patterns in: " + ", ".join(failures))
        raise SystemExit(1)
    print(
        f"PASS: {len(set(paths)) - 1} publishable files and {len(checked)} historical blobs scanned; no known credential patterns. Manual privacy review still required."
    )


if __name__ == "__main__":
    scan()
