#!/usr/bin/env python3
"""Gate the coordinate helper used before non-membrane PB/MC preparation.

Run one/two-stage periodic assembly fixtures and optionally compare an x86
reference. Called by host support checks and the candidate image's %test;
this verifies geometry handling, not DelPhi/PETIT scientific equivalence.
"""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def coordinates(binary, gro, definitions):
    """Run one assembly case and return validated, centered GRO coordinates.

    Require unchanged atom indices and a compact minimum-image cluster; these
    protect the ordering and geometry consumed by downstream PB preparation.
    """
    env = os.environ.copy()
    # Legacy fixgro does not free all allocations; check invalid accesses here.
    env.setdefault("ASAN_OPTIONS", "detect_leaks=0")
    result = subprocess.run(
        [str(binary), str(gro), str(definitions)],
        check=True, text=True, capture_output=True, timeout=15, env=env,
    )
    lines = result.stdout.splitlines()
    if len(lines) != 7 or int(lines[1]) != 4:
        raise AssertionError("wrong GRO frame or atom count")
    xyz = [tuple(float(line[i:i + 8]) for i in (20, 28, 36))
           for line in lines[2:6]]
    if max(row[0] for row in xyz) - min(row[0] for row in xyz) > 0.301:
        raise AssertionError("molecules remain separated across the boundary")
    if any(abs(sum(row[k] for row in xyz) / 4 - 0.5) > 0.001
           for k in range(3)):
        raise AssertionError("assembled group is not centered")
    if [int(line[15:20]) for line in lines[2:6]] != [1, 2, 3, 4]:
        raise AssertionError("atom indices changed")
    return xyz


def main():
    """Create a four-atom periodic fixture and exercise flat/nested assembly."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    reference = args.reference.resolve() if args.reference else None
    with tempfile.TemporaryDirectory(prefix="cphmd-fixgro-") as tmp:
        root = Path(tmp)
        rows = ["PBC assembly fixture", "    4"]
        for i, x in enumerate((0.05, 0.15, 0.85, 0.95), 1):
            residue = 1 if i <= 2 else 2
            rows.append(f'{residue:5d}{"MOL":<5}{"C" + str(i):>5}{i:5d}'
                        f'{x:8.3f}{0.5:8.3f}{0.5:8.3f}')
        rows.append("   1.00000   1.00000   1.00000")
        gro = root / "fixture.gro"
        gro.write_text("\n".join(rows) + "\n")
        cases = (
            "G All\na 1 2\na 3 4\nA All\n",
            "G First\na 1 2\nG Second\na 3 4\n"
            "G All\ng First\ng Second\nA First\nA All\n",
        )
        for stages, groups in enumerate(cases, 1):
            definitions = root / "fixture.moldef"
            definitions.write_text(groups + "C All All All\nP 1 1 1\n")
            actual = coordinates(binary, gro, definitions)
            if reference and actual != coordinates(reference, gro, definitions):
                raise AssertionError("coordinates differ at GRO precision")
            print(f"PASS: {stages} assembly stage(s), compact centered PBC group")


if __name__ == "__main__":
    main()
