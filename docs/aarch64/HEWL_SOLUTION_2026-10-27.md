# Native HEWL solution preparation

## Purpose and frozen protocol

**Completed:** job **2149846**, `COMPLETED 0:0`, elapsed **00:07:54**. The
solution health gate and snapshot manifest passed. Both the portable snapshot
and full preparation archive have checksum-verified off-cluster copies.

Prepare one solvated coordinate snapshot for matched x86/ARM PB/MC and subsequent
CpHMD/RT/restart checks, using the topology verified by job 2148669 and the
ordinary-user ARM SIF from job 2148618. This stage uses fixed starting
protonation; pH 6 sampling is a later PB/MC operation. General preparation and
force-field fixes remain deferred.

The submitted source snapshot records Git commit `ada4739`, dirty status and
per-file hashes of the new validation tools. Native job **2149846** runs in:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M
```

All temporary and persistent simulation files stay under the project. Existing
topology/production inputs are mounted read-only. The job never resubmits itself.

| Stage | Explicit choices | Purpose / pass criterion |
| --- | --- | --- |
| Box/solvent | Dodecahedron, 1.2 nm padding; TIP3P force field/SETTLE; standard three-site water coordinates | Preserve first 2,004 protein atoms and explicit solvent topology. Coordinate source `spc216.gro` does not change the chosen TIP3P interaction model. |
| Ions | Na+/Cl−, placement seed 1729; target total mobile-ion I=0.1 M, including counterions | Choose closest neutral integer counts; verify actual coordinate/topology counts and zero starting net charge. |
| Minimization | Restrained protein heavy atoms, 1000 kJ/mol/nm²; steepest descent, 0.005 nm step, at most 20,000 steps | Maximum force below 1,000 kJ/mol/nm before integration. |
| NVT | 10 ps, 1 fs, 310 K, v-rescale with 0.5 ps coupling; Protein and SOL baths | Complete finite output and acceptable tail temperature. SOL includes water and ions. Velocity seed 314159; thermostat seed 271828. |
| NPT | 20 ps, 1 fs, 310 K / 1 bar; C-rescale barostat, 5 ps coupling, COM reference-coordinate scaling | Continue the NVT checkpoint without regenerating velocities. Complete finite output, plausible density/volume and preserved topology. Thermostat/barostat stochastic seed 161803. |

MD uses PME, 1.0 nm Coulomb/LJ cutoffs, potential-shift LJ and `EnerPres`, matching
the Amber profile's nonbonded choices. Equilibration uses H-bond constraints,
LINCS order 8 / 2 iterations. All grompp commands have `-maxwarn 0`. The genion
input TPR uses cutoff electrostatics solely for coordinate/inventory bookkeeping;
no dynamics runs from it. No warnings are waived for production preparation.

The short restrained runs are bounded preparation checks, **not** evidence of
thermodynamic equilibration, converged pKa values or production performance.
GROMACS documents C-rescale for equilibration/production and the chosen seed
options in its [2026.3 MDP reference](https://manual.gromacs.org/2026.3/user-guide/mdp-options.html).

## Ionic-strength convention

For monovalent ions, `I = (N_NA + N_CL)/(2 * 0.602214076 * V_nm³)`.
The starting protein has +9 e, so `N_CL - N_NA = 9`. Choose the closest neutral
integer pair to the target. Adding 0.1 M salt and *then* nine counterions would
instead exceed the requested total mobile-ion strength.

The actual prepared box volume is **287.386680 nm³**. Counts are **13 NA and
22 CL**, giving **0.101116 M** initially. It contains **8,650 waters** and
**27,989 atoms**. NPT changes volume slightly, so report the final concentration
separately. Fixed ions neutralize the starting topology only; later protonation
sampling can change the system charge and needs the method's usual treatment.

Minimization reached **Fmax 874.259 kJ/mol/nm in 594 steps**. Equilibration and
snapshot acceptance passed with the following actual last-half means:

| Result | Value |
| --- | ---: |
| NVT temperature | 306.283 K |
| NPT temperature | 309.438 K |
| NPT density | 1005.730 kg/m³ |
| NPT pressure | −47.914 bar |
| Final box volume | 282.887231 nm³ |
| Final mobile-ion ionic strength | 0.102724 M |

Pressure fluctuations and the short duration preclude an equilibrium-pressure
claim. All selected energy records were finite, all four S–S distances stayed
0.198–0.212 nm, and atom order/inventory remained consistent. An independent
off-cluster check confirmed that protein topology data and the 21-site list
remain identical to the verified starting topology.

Native snapshot:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution/snapshot
```

Off-cluster copies are outside the Git checkout:

```text
../artifacts/hewl-4lzt/HEWL-snapshot.tar.gz
SHA-256 bd322b839e71c9bc8f7df3c22596b341e66c5b94dc6579f052bba69c3a1683b9
../artifacts/hewl-4lzt/HEWL-preparation-2149846.tar.gz
SHA-256 8a25d4b613b7f8458fc76ed865e0ca9d4ae2b72779a2f06aca0f4532d1e76241
```

The portable snapshot is extracted locally at
`../artifacts/hewl-4lzt/snapshot-2149846/snapshot`. Its internal manifest was
verified after export. Logs, energy tables, source/protocol metadata and the
validation summary are versioned under `evidence/2026-10-27/hewl-solution/`.

## Output health gates

- Minimized coordinates exist and the maximum force satisfies the stated gate.
- No fatal/constraint/LINCS diagnostics; complete 10 ps and 20 ps energy records.
- All selected energies/coordinates are finite; times increase strictly.
- Last-half mean temperature is 290–330 K; NPT density is 800–1200 kg/m³ and
  final/initial volume ratio is 0.8–1.2. These deliberately broad health checks
  do not certify equilibrium or statistically converged pressure.
- Protein atom order and full solvent/ion inventory remain unchanged; final
  four S–S distances remain 0.18–0.23 nm.
- Trajectory and energy readers pass. Energy analysis uses recorded XVG legend
  names rather than assuming GROMACS preserves requested column order.

Only after these checks does the tool write `solution-audit.json`, create a
self-contained `snapshot/` and its SHA-256 manifest, and emit
`SOLUTION_PREPARATION_AND_SNAPSHOT_PASSED`. The snapshot contains coordinates,
topology/include tree, index, site definition and audit. Unused legacy FF scripts
and architecture-specific helper binaries are omitted from the portable input.

## Maintainer map

`container_build/slurm/hewl-solution.slurm` reserves native ARM resources,
verifies image/source/topology/FF hashes and invokes the container normally.
Its EXIT handler preserves the actual status and all failed outputs.

`tests/arm64/prepare_hewl_solution.sh` runs each stage in a new directory.
`run_logged` records exact argv and separate stdout/stderr. The four MDP files
under `tests/arm64/hewl-solution/` define ions/EM/NVT/NPT explicitly.

`plan_hewl_ions.py`: `read_gro` validates atom counts and triclinic volume;
`ion_counts` enforces neutrality and nearest target strength; `write_index`
checks actual placement and writes the Protein/SOL/Water/Ions/Solute groups;
`main` selects pre-genion planning or post-genion verification.

`check_hewl_solution.py`: `xvg` validates finite, labeled energy columns and time;
`check_minimization` gates integration on the force threshold; `check_final`
checks short-run health/invariants and freezes the portable snapshot; `main`
selects the stage. `tests/check_hewl_solution_helpers.py` has seven portable
bookkeeping/parser regressions, all passed before interpreting MD results.

## Inspect this job from an SSH terminal

```bash
squeue -j 2149846
sacct -j 2149846 -o JobID,State,ExitCode,Elapsed
cphmd_solution=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M
tail -n 40 "$cphmd_solution/slurm-2149846.log"
cat "$cphmd_solution/exit-2149846.txt"
cat "$cphmd_solution/solution/result.txt"
cat "$cphmd_solution/solution/solution-audit.json"
```

A valid completion requires SLURM `COMPLETED 0:0`, exit marker 0 and the
successful snapshot marker. Preserve failed work rather than overwriting it.

## Next stage

Use this exact snapshot for fixed-coordinate PB/MC comparisons, with identical
science-driving scripts, ST/database data, parameters and seeds in both images.
Agree/record units and numerical tolerances before inspecting differences. The
prepared geometry is suitable for a bounded pipeline comparison; it is not a
converged pH-6 ensemble. Then run the all-site, RT and batch/restart cases.

Do not resubmit solution preparation merely to record this completed milestone.
