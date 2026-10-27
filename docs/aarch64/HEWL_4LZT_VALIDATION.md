# HEWL 4LZT: preparation and staged scientific validation

## Agreed protocol and source

The user selected HEWL from PDB **4LZT** and approved **Amber14SBpH/TIP3P,
pH 6.0, 310 K, 0.1 M ionic strength, free titratable termini and four intact
disulfides**. Reduced titration and SLURM batch/restart testing belong in this
validation campaign. Prepare the cases together; execute them in dependency
order so failures have a clear origin. Short checks establish pipeline behavior,
not converged pKa values or production-quality sampling.

Available mini05 references were found at:

```text
/home/jsequeira/Projects/04_ASICs/FF/tests/Test_systems/MD/HEWL
/home/jsequeira/Projects/04_ASICs/FF/tests/Test_systems/CpHMD/HEWL
```

The existing setup scripts specify Amber14SBpH/TIP3P and their equilibration MDPs
use 310 K. There are pH-specific preparation/settings directories; their presence
does not establish completed CpHMD simulations. Existing files are read-only
references. Force fields linked to another user's historical installation are
not copied into the new test: use the image's recorded force field/ST/database.

The existing `MD/HEWL/Structures/HEWL.pdb` has the same 1,020 protein atom records
(identity, alternate labels and coordinates) as the official 4LZT file. It lacks
the source header/disulfide declarations, so use the separately pinned official
file in `tests/fixtures/hewl-4lzt/source/4LZT.pdb` as the reproducible starting point.
The repository's older zipped tutorial refers to 3LZT and is not the source for
this new test.

## 1. Structure audit and cleaning — completed locally

`tests/arm64/prepare_hewl_structure.py` selects a coherent alternate per residue,
removes crystal heteroatoms and displacement records, and requires all canonical
protein heavy atoms. It produces **1,001 heavy atoms, 129 residues, chain A**.
S–S pairs are **6–127, 30–115, 64–80 and 76–94**. These cysteines remain oxidized
and must not enter the titratable cysteine set.

Blank alternate labels are shared atoms. Pick the highest mean-occupancy labeled
conformer for a residue, with A as the tie-break. This selects B for residues
85, 86 and 109, and A for the other labeled residues. Do not silently keep all
A alternates or mix atom-specific alternate choices. The original 139 crystal
waters and six nitrate ions are omitted; bulk solvent/ions will be generated
from the agreed solution protocol.

The full audit and regression log are in `evidence/2026-10-27/hewl-4lzt/`.
No topology, minimization, PB/MC or scientific MD has run in this stage.

## 2. CpHMD topology verified; solution preparation next

Native job 2148669 and the x86 reference passed the topology/site/charge gates
below. See [HEWL_TOPOLOGY_2026-10-27.md](HEWL_TOPOLOGY_2026-10-27.md) for the
actual names, construction supplement, limitations and evidence. Canonical
terminal/preparation fixes are deferred at the user's request. Solvation/ions
and minimization/equilibration remain the next execution stage.

1. Freeze the cleaned structure, preparation scripts, image hashes and protocol
   choices in a new test directory. On Deucalion keep persistent and temporary
   simulation data in `/projects/F202500250CPCAA2/`; the earlier node-local
   exception covered container assembly. The existing candidate image from job
   2147983 supplies the ARM runtime; do not rebuild it for this test.
2. Use the image's `pdb2cphmd` interface to map ASP, GLU, HIS, LYS and TYR to
   CpHMD-compatible residues. Leave the eight disulfide cysteines out of cysteine
   conversion. Preserve the ordinary fixed ARG treatment for this initial case.
3. Generate an Amber14SBpH/TIP3P topology and record terminal selections by their
   actual names. Verify four S–S bonds in the resulting topology and expected
   terminal atom names/charges. Do not reuse old numeric menu answers blindly.
   `CYS2` maps to Amber `CYX` through the supplied `aminoacids.r2b` table.
4. Validate the site list: expected candidate side chains are 7 ASP, 2 GLU,
   1 HIS, 6 LYS and 3 TYR, plus both termini (**21 sites** when all are enabled).
   Initial controller intent is `sites="all 1N 129C"`. Require one entry per
   intended site, correct atom ordering and no oxidized cysteine titration.
5. Build the box, solvate, add the agreed salt/charge treatment, minimize and
   equilibrate. Record box geometry/padding, ion counts/placement seed, starting
   state charges, MDPs and warnings explicitly before execution. Do not treat
   neutralizing the initial topology as proof of neutrality across all CpHMD
   states. Use one frozen resulting GRO/TOP/NDX snapshot for comparisons.

The output contract is a complete self-contained topology/include tree,
coordinates, index with required groups, explicit CpHMD settings and provenance.
`grompp` must succeed without hiding warnings behind an unrestricted maxwarn.

## 3. Cases to prepare now and run in order

| Case | Purpose | Required evidence before advancing |
| --- | --- | --- |
| Fixed-coordinate x86/ARM PB/MC | Isolate electrostatics/helpers from chaotic MD divergence. Use identical inputs, scripts, parameters and seeds; record exact x86 and ARM solver/runtime identities. | Match site/atom order, dimensions and units; compare centers, intrinsic pK and interaction matrices using tolerances fixed before inspecting results; then compare sampled quantities with stochastic uncertainty. |
| Short all-site CpHMD | Exercise coordinate preparation → PB/MC → topology update → relaxation → effective MD. Set `ReduceTitration=0`. | Valid GRO/TOP/TPR/XTC/EDR and full site-state records through the requested cycles; no stale outputs accepted. |
| Seven-cycle RT | Exercise full/reduced transitions with `ReduceTitration=1`, `RTInterval=5`, initially `RTThreshold=0.01`. | Full refreshes at cycles 1 and 6, immutable all-site definitions, consistent full templates, active/fixed reconstruction and topology state. Report the observed active-set size; adjust the documented test conditions if no meaningful reduction occurs. |
| Batch restart/continuation | Run the same RT case through the repository's generated SLURM wrapper and force short clean segments using its test guard. | Resume at the next unfinished cycle, restore active/template state after a reduced cycle, preserve the 1/6 refresh schedule and output time continuity, and synchronize finalized state. |
| Controlled failure behavior | Exercise wrapper failure handling on separate disposable copied runs after the happy path passes. | PB/MC exit 43 and output exit 42 retain diagnostics and do not trigger automatic resubmission. |

Use `template/slurm/generate_CpHMD_slurm.sh` and its settings template for the
batch case. Test the actual maintained wrapper instead of introducing a parallel
HEWL-specific resubmission implementation. Use the selected account
`f202500250cpcaa2a`, CPU partition, explicit image/run paths and a low bounded
resubmission limit. Scratch stays in the project with `allow-network` policy for
this first test. Generated scripts and scheduler settings must be reviewable
before submission; preparation is not submission.

Keep the all-site and RT runs in separate output directories, starting from the
same prepared snapshot. Their MD trajectories need not coincide after different
protonation updates. Cross-architecture PB/MC tolerances also must not be inferred
from the small stochastic PETIT smoke fixture's 0.02 sampling allowance.

## Git checkpoints

The initial structural preparation checkpoint is committed as `5c2c4c7`.
Current review/commit commands for ARM runtime access, topology evidence and
deferred issues are in section 1 of [BUILD_AND_VALIDATE.md](BUILD_AND_VALIDATE.md).
