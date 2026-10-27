# Viewing the native ARM HEWL preparation

The actual NVT/NPT trajectories from job **2149846** were converted using
GROMACS **2026.3** in the x86 reference image; no dynamics were rerun. GROMACS
reads the native ARM TPR/XTC files directly. The original input/output files
remain unchanged. Conversion logs and input hashes accompany the exports.

Local export folder, outside the Git checkout:

```text
/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/artifacts/hewl-4lzt/pymol-2149846
```

From a terminal:

```bash
pymol -r '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/artifacts/hewl-4lzt/pymol-2149846/view_hewl.py'
```

Alternatively, in the PyMOL command line:

```text
run /home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/artifacts/hewl-4lzt/pymol-2149846/view_hewl.py
```

The launcher opens the NPT movie. Press Play. For NVT, enter:

```text
disable hewl_npt
enable hewl_nvt
frame 1
```

| File | What it shows |
|---|---|
| `npt-protein.pdb` | 21 states, phase time 0–20 ps, 1 ps between frames. |
| `nvt-protein.pdb` | 11 states, phase time 0–10 ps, 1 ps between frames. |
| `minimized.pdb` | Final contact-minimization structure. |
| `*-native.pdb` | Original CpHMD residue names and every simulated protein atom, including dummy hydrogens. |
| `final-system.pdb` | Final water/ion/protein view in a compact periodic cell; load separately. |
| `*-geometry.csv` | CA displacement and four sulfur distances, in angstrom. |

The protein movies first make molecules whole and center the protein, then
remove translation/rotation by fitting the backbone in a separate conversion.
Each display model has **1,001 heavy atoms / 129 residues**. Standard display
names replace AS4/GL4/HI2/LY3/TY0 with ASP/GLU/HIS/LYS/TYR. No input topology,
trajectory or PB coordinate is renamed. Never restart MD or run PB from the
display copies. NVT and NPT clocks reset independently; the movies stay separate.

Look for chain continuity, detached fragments, severe overlaps or abnormal
stretches. Yellow sulfur sticks identify the disulfides. Solvent is intentionally
absent from protein-only movies; inspect `final-system.pdb` for the water/ions.

Across saved frames, the largest CA RMSD from each phase's first fitted frame is
**0.249 Å (NVT)** and **0.307 Å (NPT)**. The four sulfur separations span
**1.959–2.119 Å (NVT)** and **1.897–2.114 Å (NPT)**. These describe the exported
coordinates, not physical stability acceptance thresholds. Heavy-atom restraints
and the short preparation duration limit what can be concluded. PyMOL is not
installed in the local execution environment, so the files were structurally
audited, but the PyMOL rendering itself has not been visually inspected here.

## Reproducing the export

`tests/arm64/export_hewl_pymol.sh` runs inside either GROMACS 2026.3 image with
the original solution mounted read-only and a new output path. It performs the
two conversion passes and writes native PDBs plus a final solvent view.
`tests/arm64/finish_hewl_pymol.py` then runs on the host: `display_copy` filters
hydrogens and maps display names; `geometry` writes descriptive per-frame CSVs;
`main` validates frame counts and creates the portable PyMOL launcher.

Example with the solution folder and repository mounted inside a container:

```bash
bash /source/tests/arm64/export_hewl_pymol.sh /input/solution /output/pymol
python3 /source/tests/arm64/finish_hewl_pymol.py /output/pymol
```

Reference behavior: [GROMACS trjconv](https://manual.gromacs.org/2026.3/onlinehelp/gmx-trjconv.html)
documents separate PBC/fit passes; [PyMOL load](https://www.pymolwiki.org/Load)
documents loading multi-model PDBs as states with `multiplex=0`.
