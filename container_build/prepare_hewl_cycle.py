#!/usr/bin/env python3
"""Freeze source-only HEWL cycle validation inputs outside the Git checkout.

Called on the workstation before SCP/SLURM submission. Check repository safety,
require a clean revision unless --allow-dirty is explicit, copy only the native
gate's text scripts/data, record per-file hashes, and make a new tar archive.
No credentials, Git metadata, ELF files, simulation outputs or SIF are packaged;
the native job reads its already-verified scientific snapshot and image locally.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def source_files(repo: Path) -> list:
    """Select runtime scripts and scientific tables; reject compiled host payloads."""
    selected = set()
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=repo).decode().split("\0"))
    for parent in ["CpHMD/scripts", "DelphiTools", "STs/St-Amber14SBpH", "Databases"]:
        for path in (repo / parent).rglob("*"):
            # Git-ignored/untracked files can contain local authentication or
            # debug material. Never sweep them into a broad directory archive.
            if (str(path.relative_to(repo)) in tracked and path.is_file()
                    and not path.is_symlink() and "__pycache__" not in path.parts):
                if path.read_bytes()[:4] != b"\x7fELF":
                    selected.add(path)
    for name in ["template/CpHMD-basic-Amber14SBpH.settings", "tests/arm64/hewl_cycle.py",
                 "tests/arm64/run_hewl_cycle.sh", "tests/arm64/compare_hewl_pbmc.py",
                 "container_build/slurm/hewl-cycle.slurm"]:
        path = repo / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit("Expected a regular gate source file: " + name)
        selected.add(path)
    return sorted(selected)


def main() -> None:
    """Publish a new context only; never overwrite an existing validation snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    output = args.output_dir.resolve()
    if output == repo or repo in output.parents:
        raise SystemExit("Keep validation payloads outside the Git checkout")
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repo))
    if dirty and not args.allow_dirty:
        raise SystemExit("Commit/review changes first, or explicitly use --allow-dirty for hashed development inputs")
    subprocess.run([sys.executable, str(repo / "tests/check_repository_safety.py")], cwd=repo, check=True)
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "source"
    frozen.mkdir()
    hashes = {}
    for path in source_files(repo):
        relative = path.relative_to(repo)
        target = frozen / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        hashes[str(relative)] = hashlib.sha256(target.read_bytes()).hexdigest()
    metadata = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip(),
                "working_tree_dirty": dirty, "file_sha256": hashes,
                "preparer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "purpose": "Native HEWL cycle/RT validation; source only"}
    (frozen / "source-snapshot.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (frozen / "source.sha256").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + str(path.relative_to(frozen)) + "\n"
        for path in sorted(frozen.rglob("*")) if path.is_file()))
    archive = output / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(frozen, arcname="source")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "source.tar.gz.sha256").write_text(checksum + "  source.tar.gz\n")
    print(json.dumps({"archive": str(archive), "sha256": checksum, "source_files": len(hashes),
                      "status": "Source context prepared; this command does not submit jobs."}, indent=2))


if __name__ == "__main__":
    main()
