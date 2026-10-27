#!/usr/bin/env python3
"""Manual corruption checks for the HEWL scientific-output comparator.

Use actual saved x86 results, not implementation-shaped synthetic matrices.
Positive control must pass; each corrupted copy must fail. Original evidence
is read-only. This provisional fixture gate is not wired into general CI.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile


def main() -> None:
    """Exercise incomplete, nonfinite, misidentified and numerically wrong data."""
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("pbcheck", root / "tests/arm64/compare_hewl_pbmc.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    reference = root / "docs/aarch64/evidence/2026-10-27/hewl-pbmc/x86"
    contract = json.loads((root / "tests/arm64/hewl-pbmc-contract.json").read_text())
    assert check.compare(reference, reference, contract)["passed"]
    changes = {
        "missing matrix entry": ("PBMC.g", lambda s: "\n".join(s.splitlines()[1:]) + "\n"),
        "NaN energy": ("PBMC.g", lambda s: s.replace("0.000000e+00", "NaN", 1)),
        "wrong site identity": ("PBMC.pkcrg", lambda s: s.replace("LYS1-1", "LYS1-999", 1)),
        "illegal final state": ("petit-1729.out", lambda s: "\n".join(
            "f 999 " + " ".join(line.split()[2:]) if line.startswith("f ") else line
            for line in s.splitlines()) + "\n"),
        "missing sampled site": ("petit-1729.out", lambda s: "\n".join(
            line for line in s.splitlines() if not (
                line.startswith(".") and len(line.split()) > 3 and line.split()[3] == "0")) + "\n"),
        "inconsistent population": ("petit-1729.out", lambda s: s.replace("9.92519975e-01", "1.92519975e-01", 1)),
        "pK threshold exceeded": ("PBMC.pkcrg", lambda s: s.replace("8.416363e+00", "8.436363e+00", 1)),
    }
    for name, (filename, transform) in changes.items():
        with tempfile.TemporaryDirectory(prefix="hewl-pbmc-negative-") as temp:
            candidate = Path(temp)
            # Copy just the scientific inputs, without optional native binaries.
            for pattern in ("PBMC.*", "petit-*.out"):
                for source in reference.glob(pattern):
                    shutil.copy2(source, candidate / source.name)
            path = candidate / filename
            original = path.read_text()
            changed = transform(original)
            assert changed != original, f"Negative fixture did not mutate: {name}"
            path.write_text(changed)
            try:
                rejected = not check.compare(reference, candidate, contract)["passed"]
            except (ValueError, IndexError, KeyError, StopIteration):
                rejected = True
            assert rejected, f"Corrupt scientific output accepted: {name}"
        print("PASS: rejected", name)


if __name__ == "__main__":
    main()
