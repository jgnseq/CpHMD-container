#!/usr/bin/env python3
"""Freeze only reviewed scientific text inputs for the native performance stage.

Run locally before SCP; this never submits jobs. Reuse the cycle allowlist,
append this stage's two runtime files and preparer, record the exact dirty-tree
provenance, and keep the resulting archive outside Git. No SIF, trajectory,
credential or repository metadata is included.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from prepare_hewl_cycle import source_files


def main():
    """Create a new, checksummed source context after the repository safety guard."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--overnight", action="store_true",
                        help="Include the bounded RT/continuation and longer-MD launchers")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    output = args.output_dir.resolve()
    assert output != repo and repo not in output.parents, "Keep payloads outside Git"
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).decode()
    if status and not args.allow_dirty:
        raise SystemExit("Commit reviewed changes first, or explicitly use --allow-dirty")
    subprocess.run([sys.executable, str(repo / "tests/check_repository_safety.py")], cwd=repo, check=True)
    selected = set(source_files(repo))
    for name in ["tests/arm64/hewl_performance.py", "tests/arm64/hewl_solver_performance.py",
                 "tests/arm64/run_hewl_solver_performance.sh",
                 "tests/arm64/hewl_startup_probe.py", "tests/arm64/compare_hewl_performance.py",
                 "container_build/run_hewl_x86_performance.sh", "container_build/slurm/hewl-startup-probe.slurm",
                 "container_build/slurm/hewl-performance.slurm", "container_build/slurm/hewl-solver-performance.slurm",
                 "container_build/prepare_hewl_performance.py"]:
        path = repo / name
        assert path.is_file() and not path.is_symlink()
        selected.add(path)
    if args.overnight:
        for name in ["tests/arm64/hewl_overnight.py", "container_build/slurm/hewl-overnight-rt.slurm",
                     "container_build/slurm/hewl-overnight-md.slurm", "container_build/run_hewl_overnight_x86.sh",
                     "container_build/slurm/hewl-portable-validation.slurm"]:
            path = repo / name
            assert path.is_file() and not path.is_symlink()
            selected.add(path)
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "source"
    frozen.mkdir()
    hashes = {}
    for path in sorted(selected):
        name = path.relative_to(repo)
        target = frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        data = target.read_bytes()
        assert not data.startswith(b"\x7fELF")
        hashes[str(name)] = hashlib.sha256(data).hexdigest()
    metadata = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip(),
                "working_tree_dirty": bool(status), "git_status": status.splitlines(),
                "file_sha256": hashes, "overnight": args.overnight,
                "purpose": "Bounded image-pinned performance/integration gates; launcher selects reference or portable candidate"}
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
                      "status": "Prepared source only; no jobs submitted."}, indent=2))


if __name__ == "__main__":
    main()
