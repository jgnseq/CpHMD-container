# Portable ARM64: completed benchmarks and night handover — 29 October 2026

## Completed and independently checked

All twelve planned portable MD observations completed with passed health
screens: two repeats of 50 and 200 ps at 4, 16 and 48 threads. The four-thread
case combines all four single-observation jobs; no partial canceled run enters
the comparison. The accepted `(steps, repeat)` set is exactly
`(50000,1/2)` and `(200000,1/2)` at every thread count.

| Allocation | Result |
|---|---|
| 2160989_3, sixteen threads | Completed `0:0`, 1:30:02 |
| 2160989_5, forty-eight threads | Completed `0:0`, 38:08 |
| 2161053_0/1, four-thread 200-ps repeats | Completed `0:0`, 2:09:52 / 2:09:42 |
| 2161053_2/3, four-thread 50-ps repeats | Completed `0:0`, 32:45 / 32:44 |
| 2160989_1, superseded four-thread grouping | Deliberately canceled; no accepted timing |

The independent receipt audit required the fixed TPR SHA256
`7276106632db360dadc02f3cc0075006ee9de10d029e143a590c2a1e02113e48`,
portable image scope, CPU/profile/command identity, both repeats, finite positive
timings, and passed trajectory/energy/atom-order/disulfide health checks.
For split jobs it also required the four distinct observation indices and their
one-observation summaries. Data and the normalized comparison are in
`evidence/2026-10-29/portable-performance/`.

Native build/unit/smoke/ordinary-user, fixed-coordinate tight PB/MC, two all-site
cycles, seven RT cycles with finalized stop/resume, separate-allocation reduced
cycle 7 → 8, and non-SVE QEMU executed-path gates had already passed. Those
results are retained in the earlier 29 October report. They do not establish
physical pKa accuracy, complete PB convergence or every ARM hardware path.

## What performance means for the portable target

These are two-repeat medians for **200 ps of fixed-protonation MD**, all using
`-reprod`, the same TPR and output schedule. Command time includes startup;
ns/day is GROMACS's reported integration rate, not complete CpHMD throughput.

| Image / machine | Threads | Command minutes | Reported ns/day |
|---|---:|---:|---:|
| x86 experimental 2026.3 rc3 / mini05 | 4 physical cores | 17.2 | 16.76 |
| Portable NEON / Deucalion | 4 | 129.5 | 2.23 |
| A64FX SVE512 reference / Deucalion | 4 | 73.0 | 3.96 |
| Portable NEON / Deucalion | 16 | 35.6 | 8.15 |
| A64FX SVE512 reference / Deucalion | 16 | 21.0 | 13.91 |
| Portable NEON / Deucalion | 48 | 14.9 | 19.71 |
| A64FX SVE512 reference / Deucalion | 48 | 10.1 | 29.40 |

On the same Deucalion hardware, portable command time is 1.78/1.70/1.48 times
the optimized reference time at 4/16/48 threads. The corresponding integration
time ratios are about 1.78/1.71/1.49. Most of this difference is sustained MD
work, rather than a new startup delay: portable startup remains about sixteen
seconds with the tested profile. Preserve both images and their identities.
The measured cost does not justify silently introducing SVE into the portable
baseline. Performance on other ARM processors remains unmeasured.

At equal four-core counts, portable ARM command time is about 7.52 times the
mini05 x86 time. Using 48 ARM threads finishes this MD-only case in about 86.5%
of the four-core x86 command time, with twelve times as many cores. Hardware,
clock and memory differences prevent attributing the cross-machine ratio to
instruction set or compiler alone. Each ARM measurement reserved an exclusive
48-core node even when fewer threads were used. Two repeats are an engineering
screen, not a statistical performance study. The generic solver's previously
measured cost and PB/MC stage costs remain separate from this MD table.

## Portable generated-wrapper gate launched tonight

Preparation job **2165793** passed in eight seconds. It generated the actual
unmodified scheduler scripts against the portable image SHA256
`dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479`.
All script/source/image pins and shell syntax were checked before submission.

| Case | Initial job | Required behavior |
|---|---|---|
| Default guard characterization | 2165802 | Run/synchronize; preserve the known default guard defect as REVIEW |
| Explicit guard | 2165803 → 2165821 | Both completed `0:0`; finalized cycle 1 and continued through cycle 2 |
| Controlled MD command failure | 2165804 | Expected Slurm `FAILED 42:0`; no false DONE/successor |
| Controlled PB driver failure | 2165805 | Expected Slurm `FAILED 43:0`; no false DONE/successor |
| Damaged checkpoint copy | 2165806 | Expected `FAILED 42:0` before simulation; original checkpoint untouched |
| Audit dispatcher | 2165807 | Completed `0:0`; submitted the successor-dependent auditor |
| Independent audit | 2165834 | Completed `0:0`, 18 seconds; explicit configuration/successor/containment passed |

Root:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/batch.portable.20261029.uS0Q9t
```

The dispatcher uses `afterany` so deliberate failures do not block inspection.
It reads the one real successor ID from the completed initial explicit-case
log and assigns that dependency to the scientific auditor. It does not poll,
retry or certify science itself. Missing successor evidence goes to the auditor
for rejection; more than one successor stops dispatch. Acceptance requires the
final `batch-audit.json` and its Slurm/exit receipts, not initial job colors.
Those receipts have now been copied locally and independently checked. The
accepted marker is
`EXPLICIT_ENV_BATCH_GATE_PASSED_DEFAULT_GUARD_REVIEW_REQUIRED`.
Explicit guard 1 reached the actual controller; the default case still observed
guard 0 and remains REVIEW. Evidence is in
`evidence/2026-10-29/portable-batch-night/`.

The known default transport problem remains deferred. Do not turn its review
into a pass or use the artificial one-second test guard for production. The
supported explicit container guard is tested separately. No canonical CpHMD,
force-field, PB/MC numerical or scheduler-generator source was edited tonight.

Frozen source SHA256:
`bef4d3dd1fd6e9ffab10ba46238315ec1d340f49fd821d2fae69e0c884e62d82`.
The separately uploaded dispatcher SHA256 is
`24ccdd8602add014bd9813c6158e2a80a883183b3fc902cabda4462e244ba249`.
Changing or committing this working checkout does not change submitted inputs.

## Recovery and shutdown boundary

Recovery job **2161141** completed `0:0`, verifying the full build/reference
archives on the cluster. The x86 archive on mini05 was also content-verified.
Job **2165795** completed `0:0`, archiving the newly finished portable
validation and split-MD roots under:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/recovery.portable-final.20261029.WZ0lBZ
```

The workstation connection was slow for multi-gigabyte data. Read-only discovery
confirmed existing mini05 → Deucalion SSH access. A direct, detached, eight-hour
bounded recovery pull completed on mini05, with `pull.exit=0` and the final
`OFF_CLUSTER_RECOVERY_ON_MINI05_PASSED` marker (timeout PID was **189077**):

```text
/home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.20261029.rT3rfu
```

It used the existing SSH authentication and strict known-host checks, with agent
forwarding disabled. No private keys or authentication configuration were copied.
Each folder requires the archive creator's zero exit, then copies final archives,
manifests and checksums using resumable rsync and verifies SHA256 after receipt.
Project ownership is not imposed on mini05. A lock prevents duplicate pulls.
The final `pull.exit` must be `0`; a live PID or an existing archive alone is not
acceptance. All four archives passed the copied SHA256 checks. A separate
direct copy of the portable SIF also passed its expected SHA256 on mini05, giving
the image independent copies there and on the workstation. Source/content
manifests, not metadata-warning suppression, establish
the server-side archive checks.

The redundant local rsync was interrupted deliberately with status 20; its
partial data remain resumable. The local verified SIF, runtime/recipe, source
seed, solver source and compact evidence are already safe. Full archives are
now off-cluster verified on mini05. Latest production-wrapper raw output is a
separate recovery: archive job **2165845** and a bounded mini05 pull with timeout
PID **189137**, both now completed with zero status and SHA256-verified copy, under:

```text
Cluster: /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/recovery.portable-batch.20261029.RMt8j8
mini05: /home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.20261029.batch.pxF5Co
```

That separate run reached `pack.exit=0`, `pull.exit=0` and a copied archive
SHA256 pass. Its full raw recovery is accepted; the compact audit is also safe
locally. Summary receipts are in `evidence/2026-10-29/recovery-night/`.
The helper's optional `ROOT REMOTE_RECOVERY_ROOT LABEL`
mode validates the remote path/label before use in SSH and allows this one-folder
pull without repeating the earlier archives.

The workstation may shut down. Every job launched in this stage and both direct
pulls have finished; no local transfer remains active. The local recovery-fetch
script has been updated to read the verified mini05 mirrors, so later raw-data
downloads do not require Deucalion access. mini05 must be reachable for those
later downloads. When the user asks to stop development, save the
latest IDs/status/handover and start no further work. Existing authorized remote
jobs can continue unless the user asks to cancel them. No Git commit is required
to keep submitted work running; the agent does not stage, commit or push.

## Remaining work before access ends

Treat **30 October** as the working deadline:

1. Finalize the normal ARM build/release path around the validated portable
   profile. Keep the A64FX profile separately named and explicitly selected.
2. After those packaging changes, perform one clean native build and appropriate
   final checks; pin the selected image, source/runtime/recipe and exact settings.
3. Repeat recovery for that final image/evidence and commit/push reviewed code,
   documentation and compact evidence. Publish a clear handover with hardware/convergence/guard
   limits and commands that still work after Deucalion access ends.

Further compiler tuning, the finalized x86 release, physical non-SVE hardware
coverage and the deferred preparation/termini fixes can follow later. Avoid
starting a broad optimization experiment tonight. The useful stop point is the
completed wrapper/audit chain and verified recovery, with final packaging reserved
for tomorrow.

## Changed file/function map

| File / function | Role |
|---|---|
| `hewl-batch-prepare.slurm` | Select/pin portable or historical A64FX image and its passed prior checkpoint; generate disposable fixtures/scripts without submitting simulations. |
| `hewl-batch-audit.slurm` | Require the same profile/pin used in preparation, then run the independent existing science/status auditor. |
| `hewl-batch-dispatch-audit.slurm` | Submit one auditor after initial cases and their real bounded successor, independently of the workstation. |
| `prepare_hewl_batch.py` | Include the owned dispatcher in future allowlisted contexts; retain source hashes and dirty-tree provenance. |
| `pull_arm_recovery_on_mini05.sh`: `wait_and_copy` | Wait for bounded archive preparation, pull only final payloads, retain rsync partials and verify SHA256 on mini05. |

Use explicit Git paths when committing. The pre-existing untracked local file
was left untouched and was not included in the allowlisted upload.
