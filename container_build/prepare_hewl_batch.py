#!/usr/bin/env python3
"""Freeze source-only inputs for the native generated-SLURM wrapper tests.

Run locally before SCP. Reuse the reviewed cycle source allowlist, append only
the batch fixture and actual scheduler generator, record index/working-tree
provenance and per-file hashes, and archive outside Git. Simulation inputs and
the SIF are already on Deucalion; no binary, credential or Git directory is sent.
This command prepares inputs and never submits a job.
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
    """Create a new immutable context after the repository credential/artifact guard."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    output = args.output_dir.resolve()
    if output == repo or repo in output.parents:
        raise SystemExit("Keep native validation payloads outside the Git checkout")
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).decode()
    if status and not args.allow_dirty:
        raise SystemExit("Commit reviewed changes first, or explicitly supply --allow-dirty")
    subprocess.run([sys.executable, str(repo / "tests/check_repository_safety.py")], cwd=repo, check=True)
    selected = set(source_files(repo))
    for name in ["tests/arm64/hewl_batch.py", "container_build/slurm/hewl-batch-prepare.slurm",
                 "container_build/slurm/hewl-batch-audit.slurm",
                 "container_build/slurm/hewl-batch-dispatch-audit.slurm",
                 "template/slurm/generate_CpHMD_slurm.sh", "template/slurm/CpHMD-slurm.settings"]:
        path = repo / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit("Expected regular source file: " + name)
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
        if data[:4] == b"\x7fELF":
            raise SystemExit("Compiled payload excluded: " + str(name))
        hashes[str(name)] = hashlib.sha256(data).hexdigest()
    metadata = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip(),
                "working_tree_dirty": bool(status), "git_status": status.splitlines(),
                "file_sha256": hashes, "preparer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "purpose": "Generated native SLURM wrapper: guard transport, synchronization, continuation and failures"}
    (frozen / "source-snapshot.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (frozen / "source.sha256").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + str(path.relative_to(frozen)) + "\n"
        for path in sorted(frozen.rglob("*")) if path.is_file()))
    archive = output / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(frozen, arcname="source")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "source.tar.gz.sha256").write_text(checksum + "  source.tar.gz\n")
    print(json.dumps({"archive": str(archive), "sha256": checksum,
                      "status": "Batch source context prepared; no scheduler submission by this command."}, indent=2))


if __name__ == "__main__":
    main()
