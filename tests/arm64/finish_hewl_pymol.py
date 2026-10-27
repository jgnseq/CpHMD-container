#!/usr/bin/env python3
"""Make clean heavy-atom display copies; never rewrite scientific inputs.

Called after export_hewl_pymol.sh. Native PDBs retain every simulated atom,
including CpHMD dummy hydrogens. Display copies use ordinary residue names so
PyMOL recognizes the protein; this mapping must never be used for restarting MD.
"""
import argparse
import json
import math
from pathlib import Path

NAMES = {"AS4": "ASP", "GL4": "GLU", "HI2": "HIS", "LY3": "LYS", "TY0": "TYR"}


def display_copy(source: Path, target: Path) -> dict:
    """Filter hydrogens, preserve fixed-column coordinates and audit each model."""
    lines, models, atoms = [], [], []
    for line in source.read_text().splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            element = line[76:78].strip() or line[12:16].strip().lstrip("0123456789")[0]
            if element in ("H", "D"):
                continue
            line = line[:17] + NAMES.get(line[17:20], line[17:20]) + line[20:]
            atoms.append((line[22:27], line[12:16], line[17:20]))
        # CONECT serials may refer to removed atoms; PyMOL infers heavy bonds.
        if not line.startswith("CONECT"):
            lines.append(line)
        if line.startswith("ENDMDL"):
            models.append(atoms)
            atoms = []
    if atoms:
        models.append(atoms)
    if not models or not all(model == models[0] for model in models):
        raise ValueError(f"Changing atom identities or empty PDB: {source}")
    if len({identity[0] for identity in models[0]}) != 129:
        raise ValueError("Expected all 129 protein residues")
    target.write_text("\n".join(lines) + "\n")
    return {"models": len(models), "heavy_atoms_per_model": len(models[0]), "residues": 129}


def geometry(directory: Path, phase: str) -> dict:
    """Describe each fitted frame in angstrom; these are not acceptance limits."""
    frames, current = [], {}
    for line in (directory / f"{phase}-protein.pdb").read_text().splitlines():
        if line.startswith("ATOM"):
            current[(int(line[22:26]), line[12:16].strip())] = tuple(
                float(line[i:i + 8]) for i in (30, 38, 46))
        if line.startswith("ENDMDL"):
            frames.append(current)
            current = {}
    reference = frames[0]
    ca = [key for key in reference if key[1] == "CA"]
    rows = []
    for time, frame in enumerate(frames):
        rmsd = math.sqrt(sum(math.dist(frame[key], reference[key]) ** 2 for key in ca) / len(ca))
        sulfur = [math.dist(frame[(a, "SG")], frame[(b, "SG")])
                  for a, b in ((6, 127), (30, 115), (64, 80), (76, 94))]
        rows.append([time, rmsd, *sulfur])
    (directory / f"{phase}-geometry.csv").write_text(
        "phase_time_ps,CA_RMSD_from_phase_first_frame_A,SS_6_127_A,SS_30_115_A,SS_64_80_A,SS_76_94_A\n"
        + "".join(",".join(f"{value:.6f}" for value in row) + "\n" for row in rows))
    return {"frames": len(frames), "max_CA_RMSD_from_phase_first_frame_A": max(row[1] for row in rows),
            "SS_distance_range_A": [min(min(row[2:]) for row in rows), max(max(row[2:]) for row in rows)]}


def main() -> None:
    """Generate display files and a portable PyMOL launcher in the export folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    audit = {}
    for phase in ("nvt", "npt", "minimized"):
        stem = phase + ("-protein" if phase != "minimized" else "")
        audit[phase] = display_copy(directory / f"{stem}-native.pdb", directory / f"{stem}.pdb")
    if (audit["nvt"]["models"], audit["npt"]["models"]) != (11, 21):
        raise ValueError("Expected 11 NVT and 21 NPT saved frames")
    (directory / "display-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    summary = {phase: geometry(directory, phase) for phase in ("nvt", "npt")}
    (directory / "geometry-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    # PyMOL's Python API resolves paths relative to this script, independent of
    # the user's working directory. No reinitialize: preserve existing sessions.
    (directory / "view_hewl.py").write_text('''"""Run in PyMOL with: run /absolute/path/to/view_hewl.py"""
from pathlib import Path
from pymol import cmd
# PyMOL's default global run sets __script__; __file__ may name pymol itself.
script_path = globals().get("__script__") or globals().get("__file__")
root = Path(script_path).resolve().parent
for name, filename in [("hewl_nvt", "nvt-protein.pdb"), ("hewl_npt", "npt-protein.pdb")]:
    cmd.load(str(root / filename), name, multiplex=0)
    cmd.hide("everything", name)
    cmd.show("cartoon", name)
    cmd.color("marine", name)
    cmd.show("sticks", name + " and resn CYS and name CB+SG")
    cmd.color("yellow", name + " and elem S")
cmd.disable("hewl_nvt")
cmd.enable("hewl_npt")
cmd.bg_color("white")
cmd.set("movie_fps", 5)
cmd.orient("hewl_npt")
cmd.frame(1)
print("NPT: 21 states, 0–20 ps at 1 ps/frame. NVT: 11 states, 0–10 ps.")
print("Use the play button. To inspect NVT: disable hewl_npt; enable hewl_nvt")
''')
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
