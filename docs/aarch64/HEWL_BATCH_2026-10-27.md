# Native generated-SLURM wrapper validation

## Outcome and acceptance boundary

This stage exercises the **unmodified** scheduler generator and the embedded
ARM controller, with copied fixture settings/diagnostic wrappers. It tests real
`sbatch` jobs rather than substituting a scheduler mock. Setup job **2151803**
completed `0:0` in **8 seconds**, verified the candidate/source/snapshot and
generated five scripts without submitting simulations. The scripts were then
hash-checked and submitted separately.

| Case | Native jobs | Expected/observed behavior |
|---|---|---|
| Default guard transport | 2151814 | `COMPLETED 0:0`, 5:27. Host requests a 1-second cycle guard; controller records **0** and completes both cycles. Default guard contract fails; execution/sync assessed separately. |
| Explicit guard | 2151815, successor 2151826 | Both `COMPLETED 0:0`, 3:22 and 3:02. Supported `CPHMD_CONTAINER_ENV` passes guard **1**. Controller code 10 submits one real successor; it restores cycle 1, completes cycle 2, synchronizes and writes DONE. |
| Controlled MD command failure | 2151816 | `FAILED 42:0`; no successor, no DONE or partial scientific publication, private scratch retained. |
| Controlled PB driver failure | 2151817 | `FAILED 43:0`; no successor, no DONE or partial scientific publication, private scratch retained. |
| Incomplete persistent checkpoint | 2151818 | `FAILED 42:0` before container execution; only a copied prior package has one XTC removed. |

Independent native audit **2151860** completed `0:0` in **15 seconds**, checking
synchronized scientific files and transaction invariants after all jobs finished.
The acceptance marker deliberately distinguishes
the supported explicit configuration from the broken default guard transport:
`EXPLICIT_ENV_BATCH_GATE_PASSED_DEFAULT_GUARD_REVIEW_REQUIRED`.
Do not interpret Slurm success or a scientific execution/synchronization pass
as acceptance of the default guard contract. In the detailed report, the default
case's execution checks and `default_guard_contract_passed` are separate;
the latter and the root `default_guard_transport_passed` remain false.

Native root:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/batch.wrapper.1ETCjX
```

## What changed in this stage

Only new validation tooling and documentation are introduced. The canonical
`template/slurm/generate_CpHMD_slurm.sh`, `CpHMD/`, `DelphiTools/` and `FFs/`
are unchanged. Existing staged cycle work is not reset or restaged by the agent.
General defects are recorded with issue-ready text in `DEFERRED_ISSUES.md`,
following the user's instruction to prioritize ARM evidence before 31 October.

The pipeline under test is:

1. Generate a CPU job from explicit scheduler and CpHMD settings.
2. Validate persistent restart completeness before scientific execution.
3. Copy settings/restart/RT state to project-backed scratch and run the SIF.
4. Synchronize only finalized segments, restart files and selected logs/state.
5. On controller code 10, increment the bounded counter and submit a successor.
6. On code 0, write DONE and clean successful scratch; on 42/43, write FAILED,
   retain failure scratch and avoid resubmission or partial publication.

The actual image is the checksum-pinned candidate
`1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d`.
No host controller is mounted over `/CpHMD`; its embedded bytes already match
the tested source (see the cycle-stage identity evidence). Read-only source,
snapshot, copied helper/configuration and force-field mounts are explicit.
Validation captures use a separate writable project mount, so wrapper cleanup
does not remove the independent evidence.

## Protocol and deliberate faults

Both positive cases use the same pH-6 Amber14SBpH/TIP3P snapshot, 310 K, 1 fs,
100 relaxation and 1,000 effective steps per cycle as the preceding cycle gate.
They target two RT cycles, interval 5: full-site cycle 1 and reduced cycle 2.
PB retains the tested tighter copied profile and its known focus/model cap.
The previous caveats about sampling, physical convergence and charged-system
PME warnings remain; these runs validate workflow behavior, not physical pKas.

All scripts request eight CPU threads, 8 GiB and one hour on `dev-arm`, account
`f202500250cpcaa2a`. The explicit guard forces a boundary after cycle 1. Its
maximum resubmission count is **one**. The default-guard characterization allows
**zero** successors, preventing an unexpected environment result from creating
an unbounded test. Failure cases also cap successors at one, and must submit none.

For `md-failure`, a fixture launcher returns 73 only for effective MD after the
real native zero-step preflight, PB/MC, topology application and relaxation.
The controller must translate that command failure to 42. For `pb-failure`, a
fixture driver returns 73 after the real zero-step preflight but before Delphi;
the controller must translate it to 43. Fault markers retain the injected cause.
The invalid-checkpoint case removes one XTC only from a fresh copy of the passed
cycle-7 package. Its original package remains read-only and intact.

## Default guard defect and tested configuration

The generator exports `CPHMD_MAX_SECONDS` and `CPHMD_WALL_START_EPOCH` on the
host, but its `exec --cleanenv` invocation does not explicitly pass them. Native
instrumentation confirms guard 0 in the default case despite the host log's 1.
This matches [SingularityCE's environment rules](https://docs.sylabs.io/guides/4.3/user-guide/environment_and_metadata.html):
`--cleanenv` excludes ordinary host variables, while `--env` carries explicit
container settings. The controller then selects its internal disabled-guard
default. A successful short completion cannot certify walltime-stop safety.

The tested public configuration uses:

```bash
# Validation test only: deliberately stop after the first complete cycle.
CPHMD_MAX_SECONDS_OVERRIDE="1"
CPHMD_CONTAINER_ENV+=("CPHMD_MAX_SECONDS=1")
```

It does not change the generator or disable `--cleanenv`. The first value alone
is insufficient with the current code. A production guard must be chosen for
the actual allocation, worst complete-cycle time and synchronization buffer;
do not copy the artificial 1-second test value blindly. Proper forwarding of
the dynamically computed guard/start time remains a general release follow-up.

## Independent checks and file map

| File | Purpose, caller and place in the workflow |
|---|---|
| `container_build/prepare_hewl_batch.py` | Workstation entry point; reuse the reviewed source allowlist, add only batch/generator files, check repository safety and freeze source hashes outside Git. Never submits. |
| `container_build/slurm/hewl-batch-prepare.slurm` | Small native setup allocation; verify hashes, prepare isolated cases using container Python, then invoke the actual generator in generation-only mode and save generated-script hashes. Login-node Python 3.6 cannot import the modern auditor, so preparation deliberately runs inside the native image. |
| `tests/arm64/hewl_batch.py` | `settings_for_batch` separates immutable inputs from scratch; `instrument` records actual guards and named faults; `scheduler_config` uses public generator settings; `prepare` isolates five cases; `successful_case` checks synchronized science/RT/restart/cleanup; `failed_case` checks containment and untouched copied inputs; `check` preserves the default-guard review independently of explicit-configuration success. |
| `container_build/slurm/hewl-batch-audit.slurm` | After all generated jobs finish, verify source/image and run the independent scientific/status audit on native ARM. |

Scientific checks reuse the independently tested dictionary, geometry, PB/MC,
RT selection/merge and finite energy readers. Persistent GRO/TOP/TPR must match
the actual last effective cycle; full-site state records and segment clocks must
match captures; real XTC/EDR readers must pass. The explicit case must contain
one actual submitted successor, two valid finalized segments and counter 1.
Successful scratch must be gone. Failures must retain diagnostic scratch and
FAILED, with no DONE, successor, counter advance or partial scientific sync.
Both positive cases and all three deliberate failure cases have finished;
accounting preserves their actual statuses. The native audit is a separate job.
The first/second scientific stages, synchronization, independent RT/dictionary
checks and negative-case containment all passed under the explicit configuration.

## Inspect these jobs without resubmission

From a Deucalion SSH terminal:

```bash
cphmd_batch=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/batch.wrapper.1ETCjX
sacct -j 2151803,2151814,2151815,2151816,2151817,2151818,2151826,2151860 \
  -o JobID,JobName,State,ExitCode,Elapsed
cat "$cphmd_batch/initial-submissions.tsv"
cat "$cphmd_batch/result.txt"
cat "$cphmd_batch/batch-audit.json"
cat "$cphmd_batch/runs/explicit-guard/resub_maint/DONE"
cat "$cphmd_batch/runs/md-failure/resub_maint/FAILED"
cat "$cphmd_batch/runs/pb-failure/resub_maint/FAILED"
```

Expected 42/43 failures are evidence of containment, not successful simulations.
Do not resubmit them to make accounting green. Failed scratch is intentionally
preserved under the same project root for inspection and off-cluster archiving.

## Reproducibility and security

Frozen source identifies commit `5e20356` plus the recorded staged/working files;
the source-only archive SHA-256 is
`262f81e43a69841621a4a3c655eb0b99fd1394ce95a36740e4ee980c7800006a`.
It contains 159 regular source/provenance files, no ELF/Git directory and no
credential-pattern matches. Its off-cluster copy is
`../artifacts/hewl-4lzt/HEWL-batch-source-262f81e43a69.tar.gz`.
All scientific scratch, captures, logs and persistent results stay under the
authorized project. Scheduler exports also pin host/container temporary paths
to the project. Large archives, TPR/EDR/XTC and SIF files remain outside Git;
only compact text evidence/provenance is selected for version control.

The full completed result archive, including retained failure scratch, has a
checksum-verified off-cluster copy outside Git:

```text
../artifacts/hewl-4lzt/HEWL-batch-2151860.tar.gz
SHA256 2ad5c38f906535924de8117a87f1125102fdc09635de7c16ce79912f40037b48
```

Compact raw reports, generated scripts/configuration, actual job logs, markers,
source hashes and failure diagnostics are under
`evidence/2026-10-27/hewl-batch/`. `verdict-summary.json` explicitly sets
`default_scheduler_release_ready=false`; the unmodified raw audit remains beside
it. A supplementary check verified every synchronized MOCC row against its
capture and exact XTC frame counts (21 for the two-cycle segment, or 11/11 for
the split run). Full archives are extracted locally as regular files only,
without restoring their container-target symlinks. Locale warnings are retained
and recorded separately in the deferred issues.

To prepare a future reviewed context locally (no job is submitted):

```bash
cd '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/CpHMD-container'
python3 container_build/prepare_hewl_batch.py \
  --output-dir '../artifacts/hewl-4lzt/next-batch-context'
```

`--allow-dirty` is an explicit development option; copied bytes remain hashed.
Transfer the new archive, verify its hash and extract into a new `batch.*`
project directory. Submit that context's preparation script first, inspect its
generated scripts and only then submit individual cases. The completed runs
above should not be repeated just to commit their evidence.
