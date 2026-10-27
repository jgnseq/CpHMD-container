#!/usr/bin/env python3
"""Exercise the cycle auditor against real native outputs and corruptions.

Run manually after extracting the 2151193 and 2151577 archives outside Git.
No simulator runs here. These checks show that incorrect topology charges,
types, masses, state/site ordering and coordinate inventories cannot pass the
independent audit merely because the controller exited successfully.
"""
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests/arm64"))
from hewl_cycle import gro, topology_mapping, reduced_mapping


def rejects(label, action):
    """Require a meaningful corrupted scientific input to be rejected."""
    try:
        action()
    except (AssertionError, ValueError, IndexError):
        print("PASS: rejected " + label)
    else:
        raise AssertionError("Auditor accepted " + label)


def check_reduced_evidence(base):
    """Check real RT selection/merging, then corrupt a fixed state and mean."""
    captures = base / "rt-2151577/coupled/captures"
    for cycle in range(1,8):
        reduced_mapping(captures / f"cycle-{cycle}", cycle in (1,6),
                        captures / f"cycle-{cycle-1}" if cycle>1 else None)
    print("PASS: actual seven-cycle RT selection and merging")
    with tempfile.TemporaryDirectory(prefix="cphmd-rt-audit-tests.") as tmp:
        capture = Path(tmp)
        original = captures / "cycle-2"
        names = ["all.sites","HEWL-RT-active.sites","TMP_RT_template.occ","TMP_RT_template.mocc",
                 "TMP_RT_current.occ","TMP_RT_current.mocc","states.dat","PBMC.sites","PBMC.dat","petit.out"]
        for name in names:
            shutil.copyfile(original / name, capture / name)
        template = (capture / "TMP_RT_template.occ").read_text().split()
        fixed = next(i for i,value in enumerate(template) if value!="-")
        current = (capture / "TMP_RT_current.occ").read_text().split()
        states = (capture / "states.dat").read_text().splitlines()
        replacement = "0" if current[fixed]!="0" else "1"
        current[fixed] = replacement
        fields = states[fixed].split();fields[0] = replacement;states[fixed] = " ".join(fields)
        (capture / "TMP_RT_current.occ").write_text(" ".join(current)+"\n")
        (capture / "states.dat").write_text("\n".join(states)+"\n")
        rejects("fixed RT state changed between refreshes", lambda: reduced_mapping(capture,False,captures/'cycle-1'))
        for name in ["TMP_RT_current.occ","states.dat"]:
            shutil.copyfile(original / name, capture / name)
        active = next(i for i,value in enumerate(template) if value=="-")
        means = (capture / "TMP_RT_current.mocc").read_text().split();means[active] = "0.123456789"
        (capture / "TMP_RT_current.mocc").write_text(" ".join(means)+"\n")
        rejects("incorrect active-site mean merge", lambda: reduced_mapping(capture,False,captures/'cycle-1'))


def main():
    """Use copied native evidence; never mutate its archived originals."""
    base = ROOT.parent / "artifacts/hewl-4lzt"
    original = base / "coupled-2151193/coupled/captures/cycle-1"
    dictionary = base / "snapshot-2149846/snapshot/Amber14SBpH.ff/protstates.dic"
    assert topology_mapping(original, dictionary)["dictionary_atom_parameters_checked"] == 354
    assert len(gro(original / "effective.gro")[0]) == 27989
    print("PASS: actual native topology and coordinate evidence")
    with tempfile.TemporaryDirectory(prefix="cphmd-cycle-audit-tests.") as tmp:
        capture = Path(tmp)
        for name in ["states.dat", "all.sites", "before.top", "after.top", "effective.gro"]:
            shutil.copyfile(original / name, capture / name)
        topology = (capture / "after.top").read_text()
        lines = topology.splitlines()
        atom = next(i for i,line in enumerate(lines) if "changed by update-top" in line and len(line.split()) >= 8)
        for label, column, value in [("wrong atom charge",6,"123.0"), ("wrong atom type",1,"BOGUS"), ("changed atom mass",7,"999.0")]:
            changed = lines.copy()
            fields = changed[atom].split()
            fields[column] = value
            changed[atom] = " ".join(fields)
            (capture / "after.top").write_text("\n".join(changed) + "\n")
            rejects(label, lambda: topology_mapping(capture, dictionary))
        (capture / "after.top").write_text(topology)
        states = (capture / "states.dat").read_text().splitlines()
        states[0], states[1] = states[1], states[0]
        (capture / "states.dat").write_text("\n".join(states) + "\n")
        rejects("swapped terminal/side-chain state rows", lambda: topology_mapping(capture, dictionary))
        rows = (capture / "effective.gro").read_text().splitlines()
        corrupted = rows.copy()
        corrupted[2] = corrupted[2][:20] + "     nan" + corrupted[2][28:]
        (capture / "effective.gro").write_text("\n".join(corrupted) + "\n")
        rejects("nonfinite coordinates", lambda: gro(capture / "effective.gro"))
        corrupted = rows.copy()
        corrupted[1] = "27988"
        (capture / "effective.gro").write_text("\n".join(corrupted) + "\n")
        rejects("changed atom count", lambda: gro(capture / "effective.gro"))
    check_reduced_evidence(base)


if __name__ == "__main__":
    main()
