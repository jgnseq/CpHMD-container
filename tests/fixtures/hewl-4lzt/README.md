# HEWL validation input: 4LZT

`source/4LZT.pdb` is the unmodified official coordinate file downloaded from
https://files.rcsb.org/download/4LZT.pdb on 27 October 2026. The associated entry
is https://www.rcsb.org/structure/4LZT (revision 1.4, 16 October 2024).

SHA-256:

```text
eec47d81860d9da162f3f8151126af361aba4d4c8055f686dd4cae9d29991941
```

Preserve the original fixed-column bytes, including trailing spaces. A narrow
`.gitattributes` rule exempts only these raw PDB inputs from whitespace checks.

The standard-library script `tests/arm64/prepare_hewl_structure.py` produces a
new protein-only PDB and audit JSON, retaining chain A residue numbering 1–129
and the four deposited disulfide declarations. It resolves alternates per
residue by mean occupancy, preferring A on a tie, and requires complete canonical
heavy atoms. It removes deposited crystal waters/nitrate, hydrogens if present
and ANISOU records. Alternate locations and anisotropic displacement records
are different concepts; the latter are not duplicate atomic positions.

Run from the repository root, selecting a new output directory:

```bash
python3 tests/arm64/prepare_hewl_structure.py \
  --source tests/fixtures/hewl-4lzt/source/4LZT.pdb \
  --output-dir /tmp/hewl-4lzt-prepared
bash tests/check_hewl_structure.sh
```

This is the structural preparation stage only. Force-field/CpHMD naming,
topology generation, disulfide bonds in the topology, solvation/ions and
minimization/equilibration must pass before PB/MC or MD validation. Follow
`docs/aarch64/HEWL_4LZT_VALIDATION.md` for the agreed protocol and test matrix.
