#!/usr/bin/env python3
"""Check Git-bound files without printing potentially secret contents.

Run before staging, then with --staged before committing. The default checks
tracked working files and non-ignored untracked files; --staged reads actual
index blobs. Existing binary/archive payloads are allowed only when identical
to the audited 5e20356 baseline. This is a credential/artifact guard, not a
malware scanner, history audit, or guarantee that arbitrary scripts are safe.
"""
import argparse
import json
import os
import posixpath
from pathlib import Path
import re
import subprocess

BASELINE = "5e20356faf6fadec41938795d06229f9daad8157"
PATTERNS = {
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "GitHub token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b",
    "AWS access key": rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    # Also catch a password accidentally entered as the HTTP username, even
    # when the URL contains no colon/password field (the earlier Git prompt).
    "HTTP URL with user information": rb"https?://[^\s/\x00@]+@",
}


def git(*args: str) -> bytes:
    """Use argv rather than shell interpolation for file names and Git refs."""
    return subprocess.check_output(["git", *args])


def inspect(name: str, data: bytes, legacy: bytes | None, symlink: bool) -> list:
    """Return redacted reasons; never return matching credential values."""
    reasons = [kind for kind, pattern in PATTERNS.items() if re.search(pattern, data)]
    if re.search(r"(^|/)(?:\.env(?:\..*)?|id_(?:rsa|ed25519|ecdsa)|credentials|\.netrc|\.git-credentials)$", name):
        if not name.endswith(".env.example"):
            reasons.append("authentication filename")
    artifact = (data.startswith((b"\x7fELF", b"MZ", b"PK\x03\x04", b"\x1f\x8b"))
                or Path(name).suffix.lower() in {".sif", ".simg", ".zip", ".tar", ".gz", ".xz", ".bz2", ".7z", ".xtc", ".trr", ".tpr", ".edr", ".cpt"}
                or len(data) > 10 * 1024 * 1024)
    if artifact and data != legacy:
        reasons.append("new or modified binary/archive/generated payload")
    if symlink:
        target = data.decode("utf-8", errors="replace")
        destination = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        if target.startswith("/") or destination == ".." or destination.startswith("../"):
            reasons.append("symlink escapes the repository")
    return reasons


def main() -> None:
    """Audit the selected Git surface and report only paths, hashes and counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report_path = args.report.resolve() if args.report else None
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    os.chdir(root)
    # Require a local immutable baseline; never fetch or contact GitHub here.
    baseline = git("rev-parse", BASELINE + "^{commit}").decode().strip()
    entries = {}
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if record:
            meta, name = record.split(b"\t", 1)
            mode, oid, stage = meta.decode().split()
            if stage != "0":
                raise SystemExit("Resolve the Git index conflict before auditing")
            entries[name.decode()] = (mode, oid)
    if not args.staged:
        for name in git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"):
            if name:
                entries.setdefault(name, ("", ""))
    findings = []
    checked = 0
    for name, (mode, oid) in sorted(entries.items()):
        path = root / name
        if args.staged:
            if mode == "160000":
                findings.append({"file": name, "reasons": ["submodule requires separate audit"]})
                continue
            data = git("cat-file", "blob", oid)
            symlink = mode == "120000"
        else:
            if not path.exists() and not path.is_symlink():
                continue
            symlink = path.is_symlink()
            data = str(path.readlink()).encode() if symlink else path.read_bytes()
        # Query legacy blobs only for artifact candidates; no secrets are
        # exempted by this baseline. Git errors are deliberately not echoed.
        legacy = None
        artifact = data.startswith((b"\x7fELF", b"MZ", b"PK\x03\x04", b"\x1f\x8b")) or len(data) > 10 * 1024 * 1024
        artifact |= Path(name).suffix.lower() in {".sif", ".simg", ".zip", ".tar", ".gz", ".xz", ".bz2", ".7z", ".xtc", ".trr", ".tpr", ".edr", ".cpt"}
        if artifact:
            result = subprocess.run(["git", "show", baseline + ":" + name], capture_output=True)
            if result.returncode == 0:
                legacy = result.stdout
        reasons = inspect(name, data, legacy, symlink)
        if reasons:
            findings.append({"file": name, "reasons": reasons})
        checked += 1
    remotes = subprocess.run(["git", "config", "--get-regexp", r"^remote\..*\.url$"], capture_output=True)
    for line in remotes.stdout.decode().splitlines():
        key, _, value = line.partition(" ")
        if re.search(r"https?://[^/]*@", value):
            findings.append({"setting": key, "reasons": ["HTTP remote contains user information"]})
    report = {"passed": not findings, "scope": "index" if args.staged else "working files",
              "baseline_commit": baseline, "checked_files": checked, "findings": findings,
              "limits": "Pattern/artifact guard only; no malware or complete-history certification."}
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
