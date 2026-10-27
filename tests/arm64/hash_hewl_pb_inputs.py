#!/usr/bin/env python3
"""Fingerprint actual PB inputs, excluding solver outputs and temporary paths.

Run on retained run_hewl_pbmc.sh output before attributing numerical differences
to the solver. Equal final GROs alone do not prove equal derived PQRs/centers.
The normalized JSON can be compared byte-for-byte across hosts/architectures.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    """Stream coordinates, parameters and TPR data in bounded memory."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def fingerprints(root: Path) -> dict:
    """Hash actual controller/preparation/solver inputs under stable logical keys."""
    folders = list(root.glob("delphiT*/tmp"))
    if len(folders) != 1:
        raise ValueError("Expected exactly one retained DelPhi calculation directory")
    solver = folders[0]
    files = {}
    for name in ("TMP_effective.gro", "TMP_CpHMD.top", "TMP_CpHMD_charge.top", "TMP_CpHMD.ndx",
                 "TMP_CpHMD.tpr", "HEWL-all.sites", "DELPHI.pbp", "USER.pbp",
                 "DataBaseT.crg", "DataBaseT.siz", "CRG_FILE", "TMP_delphi.crg"):
        files["controller/" + name] = digest(root / name)
    for path in root.glob("*.st"):
        files["templates/" + path.name] = digest(path)
    for pattern in ("*.gro", "*.pqr", "*.sites", "cent"):
        for path in solver.parent.glob(pattern):
            files["prepared/" + path.name] = digest(path)
    for pattern in ("*.prm", "*.pdb", "*.crg", "*.siz"):
        for path in solver.glob(pattern):
            files["solver/" + path.name] = digest(path)
    if not any(name.endswith(".prm") for name in files):
        raise ValueError("No generated PB parameter files found")
    return dict(sorted(files.items()))


def main() -> None:
    """Save the normalized manifest beside results; print only its size/hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    files = fingerprints(args.directory)
    destination = args.directory / "pb-input-sha256.json"
    destination.write_text(json.dumps(files, sort_keys=True, indent=2) + "\n")
    print(len(files), "PB input files; manifest SHA256", digest(destination))


if __name__ == "__main__":
    main()
