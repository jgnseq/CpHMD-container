# HEWL topology verification: native ARM and x86

## Result and scope

Native ARM job **2148669** completed `0:0` in **9 seconds** using the readable
SIF derived by job 2148618. The corresponding x86 reference preparation passed.
Both passed `grompp -maxwarn 0` for a zero-step, unsolvated topology diagnostic.
No molecular dynamics, DelPhi/PETIT comparison or CpHMD production cycle ran.

The parsed MD topologies and controller-generated PB charge-label topologies
are identical across architectures. Site files are byte-identical. All **153
compared force-field parameter/ST/support files** match, and generated GRO
coordinates match at GRO precision (maximum difference 0.000 nm).

The image-owned controller function files have different provenance; unused
legacy force-field scripts and native fixgro binaries also differ in hash.
Those differences are recorded in `comparison-summary.json`. Topology output
identity does not establish PB/MC equivalence: match the science-driving scripts
explicitly before the fixed-coordinate PB/MC comparison.

## Verified nomenclature and sites

| Conventional residue | Prepared PDB/GRO/MD topology name | Site family | Residue numbers |
| --- | --- | --- | --- |
| ASP | AS4 | ASP | 18, 48, 52, 66, 87, 101, 119 |
| GLU | GL4 | GLU | 7, 35 |
| HIS | HI2 | HIS | 15 |
| LYS | LY3 | LYS | 1, 13, 33, 96, 97, 116 |
| TYR | TY0 | TYR | 20, 23, 53 |
| Oxidized CYS | CYS, using CYX RTP | none | 6, 30, 64, 76, 80, 94, 115, 127 |
| N-terminal backbone | LY3 in MD input; NTR atom labels in PB charge view | NTR | 1 |
| C-terminal backbone | LEU using CLEU RTP; CTR atom labels in PB charge view | CTR | 129 |

There are **21 independent titration sites**, including both the Lys side chain
and N terminus at residue 1. Their state-table atom sets are disjoint. All
tautomer atom sets are present, state charge differences are +1 e, and the
initial topology matches an intended ST charge state at every site.

The starting system has **2,004 atoms** including CpHMD dummy hydrogens and
charge **+9 e**. This is the chosen starting protonation configuration, not a
prediction of the equilibrium charge at pH 6. Oxidized cysteines are not titrated.
All 128 peptide bonds, four S–S bonds (6–127, 30–115, 64–80, 76–94), absence of
thiol S–H bonds and exact terminal bond graphs were checked. GRO/TOP/PB-view
atom indices and physical atom properties remain consistent.

## Deferred terminal finding and fixture-only construction supplement

The supplied CLEU RTP already defines the CpHMD terminal carboxyl group, but its
HDB omits four dummy-H construction rules. Applying `CpH0-` on top of CLEU
creates invalid bonds and 16 missing angle/dihedral parameter errors. Selecting
`None` without completing construction leaves four missing atoms.

Before the user's scope correction, the isolated x86 prototype completed only
the copied CLEU HDB using four construction lines from the existing CpH0- TDB.
The ARM test reused that frozen fixture supplement; RTP, charges, bonded and
nonbonded parameter files were unchanged. Terminal selection was by live name:
N-terminal `CpH_NH3+`, C-terminal `None` with existing charged CLEU.

The canonical preparation helper and force-field files have **not** been fixed
or changed. Generalizing this behavior and adopting regressions in CI are
deferred per user instruction. Full reproduction details and paste-ready GitHub
issue text are in [DEFERRED_ISSUES.md](DEFERRED_ISSUES.md). Provisional helper
scripts are validation tooling only, not a general terminal-preparation API.

## Evidence and reproduction

ARM directory:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/topology.zfP6K8
```

Local evidence:

```text
docs/aarch64/evidence/2026-10-27/hewl-topology/
```

Each source snapshot records the pre-existing Git commit, dirty status and
per-file hashes of the uncommitted validation scripts. The actual native
scripts were frozen before submission; failed attempts remain preserved.

`tests/arm64/prepare_hewl_topology.sh` orchestrates the image-owned naming helper,
named terminal selection, actual controller `make_sites` preparation, pure
identity/charge audit and zero-step grompp diagnostic. `pdb2gmx_termini.py` reads
live menu names with a timeout; `complete_amber_cleu_hdb.py` records the local
construction-only supplement; `check_hewl_topology.py` validates both topology
views, ST coverage/charges and connectivity. `tests/check_hewl_topology.py` uses
copied real evidence to reject broken bonds, missing sites, wrong names and ST
charge mismatch. Its six manual regression cases passed.

To reproduce inside either matching image, mount a frozen source snapshot as
`/source` and a new writable validation directory as `/out`, then run:

```bash
bash /source/tests/arm64/prepare_hewl_topology.sh /source /out/topology
```

For a fresh native allocation, the provided topology SLURM script takes the
new project run directory, image path and expected image SHA-256 as arguments.
It never submits another job. Do not reuse a completed output directory.

## Next ARM gate

Prepare a self-contained solvated/ionized snapshot, minimize and equilibrate it,
then freeze identical coordinates and numerical inputs for x86/ARM PB/MC.
After that pass the all-site, RT and batch/restart cases. Keep the topology
diagnostic MDP out of production settings: plain cutoff electrostatics here
tests parameter completeness only, and grompp emits informational notes about
the unsolvated charge and zero-step setup. No warnings were waived.
