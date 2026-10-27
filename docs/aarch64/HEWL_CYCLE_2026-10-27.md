# Native HEWL CpHMD cycles and reduced-titration continuation

## Current outcome

All-site job **2151193** completed `0:0` in **6:05** on `cna0003`.
The actual controller completed two cycles of PB/MC, state application, solvent
relaxation, effective MD and finalized output. The independent auditor checked
**354 dictionary-selected atom charge/type assignments per cycle**; 19 and 16
atoms respectively changed type or charge. Both cycles retained the 21-site
definition, all 27,989 atoms and the four disulfides. The final checkpoint
reports two completed cycles and `CPHMD_SEGMENT_FINALIZED=1`.

The added energy audit of those saved outputs passed: each effective stage
covers 1 ps with 11 finite energy records; mean temperatures are **311.043 K**
and **310.035 K**. Each relaxation covers 0.1 ps with two finite records and
mean temperatures **313.094 K** / **310.656 K**. The earlier run and original
audit remain intact; this supplemental analysis runs on a copy in job 2151577.

Seven-cycle RT/continuation job **2151577** completed `0:0` in **17:09** on
`cna0001`, including the independent audit. Its first invocation returned the
expected clean-boundary code **10** after cycle 1; the second continued cycles
2--7 from that finalized restart. PB site counts were **21, 7, 7, 7, 7, 21, 5**.
Independent selection/merge checks passed at every cycle. Effective-stage mean
temperatures span **307.980--311.043 K**. The final checkpoint records cycle 7,
last full refresh 6, five active sites and `CPHMD_SEGMENT_FINALIZED=1`.

Separate-allocation job **2151670** completed `0:0` in **3:38** on `cna0001`,
continuing finalized **reduced cycle 7** through cycle 8. It passed the full
eight-cycle audit, including restored five-site templates, dictionary application,
energies and state propagation. Segment clocks/frame counts are **0--1 ps / 11**,
**1--7 ps / 61**, **7--8 ps / 11**. The final checkpoint is cycle 8, finalized,
last full refresh 6 and five active sites. This complements the already-passed
restart after full cycle 1. The prior result was copied into a new directory
and inherited pass markers removed before execution; the original stays read-only.

Native roots:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.all.wtFLwM
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.rt.XNDQa2
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.continue.qEgYU2
```

## What this stage tests

The previous fixed-coordinate PB/MC gate established a working native solver
and reasonable architecture agreement. This stage tests the connections:

1. Read the verified solution snapshot and regenerate the same 21 sites.
2. Run actual DelPhi and PETIT, with legal state vectors and complete finite
   PB matrices; retain their raw outputs before normal controller cleanup.
3. Apply each site's sampled/fixed state using the real `update-top` helper.
4. Independently compare every selected atom charge/type with `protstates.dic`,
   including the separate N-terminal and Lys side-chain sites on residue 1.
5. Run solvent relaxation and effective MD using the updated topology.
6. Validate coordinates, energies, trajectories and finalized segment/restart
   files. Only then write the gate's pass marker.

RT uses `RTInterval=5`, so cycles **1 and 6** are full-site refreshes. Between
refreshes the auditor independently reconstructs the 0.01-threshold selection,
always-active termini, fixed templates and active-to-full 21-site vector merge.
The first invocation intentionally hits the cycle-boundary walltime guard after
cycle 1 and returns 10. The saved boundary is copied before the second invocation
continues cycles 2--7. No synthetic checkpoint is supplied. This is a fresh
controller process in the same allocated job; scheduler resubmission/synchronization
is a separate next gate. The additional `continue` mode advances the real
cycle-7 boundary through cycle 8 in another allocation and checks segment clock
ranges, frame counts and full-site OCC/MOCC records across all segments.

## Explicit protocol and limits

Use the unchanged HEWL snapshot from **2149846**, Amber14SBpH/TIP3P, pH 6,
310 K, 0.1 M continuum PB salt, free titratable termini and four disulfides.
Effective MD is unrestrained NVT, 1 fs, 1,000 steps per cycle (1 ps), preceded
by 100 relaxation steps (0.1 ps). The historical solvent-relaxation helper
freezes the protein, then restores its starting protein coordinates/velocities.
Hydrogen-bond constraints use LINCS order 8 / two iterations. Thermostat groups
are Protein/SOL with v-rescale, tau 0.5 ps, explicit seed 314159. The previous
NPT velocities are retained; no new velocities are generated. PME and 1.0 nm
Coulomb/LJ cutoffs retain the Amber nonbonded profile. PLUMED is disabled here;
its native integration already passed the separate smoke gate.

PB uses the separately tested tighter fixture profile: maxc 0.0001, coarse
linit 1,000; focus/model retain the existing 500-iteration cap. Actual generated
parameters are checked. These settings do not establish full PB convergence;
see the preceding PB/MC report. PETIT uses the actual controller's 1,000/100,000
equilibration/production steps and explicit seed 1729. Reusing that seed is a
reproducible integration test, not a claim of independent equilibrium samples.

Health checks require finite EDR quantities, completed requested durations,
mean stage temperatures 290--330 K, finite coordinates/velocities, original atom
order and S--S distances 0.18--0.23 nm. These broad short-run checks do not prove
equilibration, pKa accuracy or long-time stability. The controller's `-maxwarn
1000` policy remains unchanged and is documented in the deferred issues.

An observed methodological caveat is retained explicitly: sampled protein charges
over cycles 1--8 were **+9, +10, +7, +8, +8, +8, +8, +8 e**. Fixed Na+/Cl-
contribute -9 e, giving total MD charges **0, +1, -2, -1, -1, -1, -1, -1 e**.
GROMACS prints charged-system Ewald/PME warnings in the affected preprocessing
stages. They were permitted by the existing controller warning allowance, not
silently removed. This integration pass is not an approval of physical artifacts
from changing net charge. A separate expert review must define/document the
CpHMD electrostatic/finite-size treatment before physical pKa claims; the warning
excerpt and a ready-to-paste issue draft are retained without changing the method.

The restart contract tested here is finalized **GRO/TOP plus RT state**.
The controller does not restore a GROMACS CPT containing the complete integrator
and thermostat state. Do not describe this as bitwise/exact MD continuation.
The general checkpoint-policy follow-up is recorded, not repaired in this sprint.

The five embedded controller/settings/site/topology files were extracted from
the saved SIF without executing it and found byte-identical to the tested source.
The fixture adds transparent retention wrappers and a copied PB template; it
does not change the canonical controller, force-field parameters or solver.

## Source, artifacts and security

The image remains the repaired candidate SHA-256
`1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d`.
All source snapshots identify commit `5e20356` plus dirty development fixtures,
with all staged file hashes. The first source-only archive SHA-256 is
`ae4c45becb3b859346b1f192757f12383d2cc713611cadcf7732379c4ced718c`;
the RT/energy-audit snapshot is
`e4aad48b9c2c855eebb316d1a0a86b619b24b0ef6a1fa0e97addd01e47123faf`.
The final continuation snapshot, made by the maintained source-only preparer,
is `ead4b96f3db7ba32303a64a922ad930a3d071c8d5c709b1e5f392b6ef085e617`.

The checksum-verified all-site result archive is saved outside Git:

```text
../artifacts/hewl-4lzt/HEWL-coupled-2151193.tar.gz
SHA256 8e992de7496fdfaee078d9c27b3c6193046f37e672ddbd745e07fb68544839d6
../artifacts/hewl-4lzt/HEWL-RT-2151577.tar.gz
SHA256 69bae3a9da3a787b6a58d3e55ab9e64b8ca0cf59b493862fa35c8013060f80fc
../artifacts/hewl-4lzt/HEWL-RT-continue-2151670.tar.gz
SHA256 5c58da57771efb16109f21e8b2bcf21f8d401633aec0d1a2c6cd521f1bf6da0b
```

Full results (including TPR/XTC/EDR), images and archives stay outside Git.
Versioned evidence is limited to compact text reports, checkpoints as data,
checksums, actual execution scripts and source provenance. The repository guard
rejects newly introduced binary/archive/generated payloads and credential
patterns. See [REPOSITORY_SECURITY_2026-10-27.md](REPOSITORY_SECURITY_2026-10-27.md)
for its scope and the inherited binary baseline.

## Maintainer map

| File | Responsibility and integration |
|---|---|
| `container_build/prepare_hewl_cycle.py` | `source_files` selects text runtime/data; `main` checks safety/dirty status, freezes per-file hashes and archives a new source-only context outside Git. Never submits jobs. |
| `container_build/slurm/hewl-cycle.slurm` | Pin image/source hashes, preserve true exit status, optionally re-audit a copied previous all-site run, invoke the fixture as ordinary user with project-backed temporary storage. |
| `tests/arm64/run_hewl_cycle.sh` | Verify snapshot, stage explicit settings, call actual controller; RT mode preserves a real cycle-1 boundary and continues in a second process; continue mode clones a finalized cycle-7 result into a new tree and advances to 8; require the independent audit before pass. |
| `tests/arm64/hewl_cycle.py` | `prepare` creates copied configuration/retention wrappers; `atoms`/`gro` validate inventories; `topology_mapping` checks dictionary application; `energy` reads finite labeled EDR data; `reduced_mapping` independently checks selection/merging; `state_file` parses checkpoints as data; `check` combines cycle/restart invariants. |
| `tests/check_hewl_cycle_helpers.py` | Real native positive evidence plus eight corruptions: wrong charge/type/mass, swapped terminal/site rows, nonfinite coordinates, wrong atom count, changed fixed RT state and incorrect active-mean merge. Manual; requires both off-cluster archives. |
| `tests/check_repository_safety.py` | Credential/artifact guard for working files or actual index blobs. Existing payloads must match the immutable baseline; reports never print secret matches. |

## Inspect completed/running jobs

Run in an SSH terminal on Deucalion:

```bash
sacct -j 2151193,2151577,2151670 -o JobID,State,ExitCode,Elapsed
cphmd_all=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.all.wtFLwM
cphmd_rt=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.rt.XNDQa2
cphmd_continue=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.continue.qEgYU2
cat "$cphmd_all/coupled/cycle-audit.json"
cat "$cphmd_rt/all-site-recheck/cycle-audit.json"
tail -n 30 "$cphmd_rt/slurm-2151577.log"
cat "$cphmd_continue/coupled/cycle-audit.json"
```

## Prepare a future source context

Do not rerun completed scientific jobs just to record their evidence in Git.
After committing/reviewing the desired source, prepare a **new** context locally:

```bash
cd '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/CpHMD-container'
python3 container_build/prepare_hewl_cycle.py \
  --output-dir '../artifacts/hewl-4lzt/next-cycle-context'
```

Use `--allow-dirty` only deliberately during fixture development; all copied
bytes remain hashed. The printed status refers to context preparation only.
For a future intentional repeat, transfer/verify/submit with these commands.
Set the final mode argument to `rt` for the seven-cycle continuation gate;
`all` is the two-cycle test. Existing results are never overwritten.

```bash
cphmd_context='../artifacts/hewl-4lzt/next-cycle-context'
cphmd_sha=$(sha256sum "$cphmd_context/source.tar.gz" | awk '{print $1}')
cphmd_project=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
scp -o BatchMode=yes -o ForwardAgent=no -o ForwardX11=no \
  -o ControlMaster=no -o StrictHostKeyChecking=yes \
  "$cphmd_context/source.tar.gz" \
  "deucalion:$cphmd_project/inputs/hewl-cycle-$cphmd_sha.tar.gz"
ssh -o BatchMode=yes -o ForwardAgent=no -o ForwardX11=no \
  -o ControlMaster=no -o StrictHostKeyChecking=yes \
  deucalion bash -s -- "$cphmd_sha" all <<'REMOTE'
set -eu
cphmd_sha=$1
cphmd_mode=$2
case "$cphmd_mode" in all|rt) ;; *) exit 2 ;; esac
cphmd_project=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
cphmd_archive="$cphmd_project/inputs/hewl-cycle-$cphmd_sha.tar.gz"
echo "$cphmd_sha  $cphmd_archive" | sha256sum -c -
cphmd_run=$(mktemp -d "$cphmd_project/validation/hewl-4lzt/cycle.$cphmd_mode.XXXXXX")
tar -xzf "$cphmd_archive" -C "$cphmd_run"
(cd "$cphmd_run/source" && sha256sum -c source.sha256 > "$cphmd_run/source-verification.log")
printf 'New run: %s\n' "$cphmd_run"
sbatch --parsable --output="$cphmd_run/slurm-%j.log" \
  "$cphmd_run/source/container_build/slurm/hewl-cycle.slurm" \
  "$cphmd_run" "$cphmd_mode"
REMOTE
```

For reduced-cycle continuation, use mode `continue`, create a fresh
`cycle.continue.*` root, and supply the passed seven-cycle result as the third
SLURM-script argument, for example from Deucalion after freezing/extracting the
new source in that root:

```bash
sbatch --parsable --output="$cphmd_run/slurm-%j.log" \
  "$cphmd_run/source/container_build/slurm/hewl-cycle.slurm" \
  "$cphmd_run" continue \
  /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.rt.XNDQa2/coupled
```

Only run this intentionally; the completed continuation above already supplies
the acceptance evidence. It clones inputs into a new run and never mutates the
passed parent.

## Following gate

After these coupled/RT/restart gates: exercise the generated scheduler wrapper with project
scratch, finalized-output synchronization and real batch continuation, then
controlled MD/output failure 42 and PB/MC failure 43. Failures must not trigger
automatic resubmission or publish partial output as DONE. Broader physical
convergence, other pH values, membrane/multiple-solute cases and performance
remain distinct later stages.
