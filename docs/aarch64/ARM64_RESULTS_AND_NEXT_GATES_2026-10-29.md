# Overnight results and portable-image follow-up — 29 October 2026

## What the completed jobs establish

Every overnight Deucalion allocation completed with `0:0`, and every expected
scientific/timing audit exists and passes. The detached mini05 launcher also
finished with status zero. There is no failed job to resubmit.

| Work | Job | Result |
|---|---|---|
| A64FX reference, seven RT cycles with `-reprod` and forced finalized stop/resume | 2160556 | Passed, 9:19 |
| Reference, separate-allocation reduced cycle 7 → 8 | 2160557 | Passed, 2:15 |
| Reference, longer fixed-TPR MD | 2160558_0–5 | All six cases passed; 24 observations |
| Generic ARM baseline rebuild and tight PB/MC comparison | 2160578 | Passed, 28:43 |
| mini05 x86 2026.3 experimental rc3, longer MD | Detached launcher | Passed; eight observations |

The portable candidate is:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/portable.20261028.MZWHAj/candidate/CpHMD-arm64.sif
SHA256 dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479
```

It uses NEON/ASIMD GROMACS and the generic `-tp=px` DelPhi compilation.
Five GROMACS unit suites, native dependency/helper/PETIT checks, water
MD/PLUMED and the separate ordinary-user smoke check passed. The tight PB/MC
comparison against the frozen x86 reference passed with unchanged tolerances:

- 21 sites, 69 pseudostates and 4761 matrix elements;
- maximum intrinsic-pK difference 0.000686, versus the frozen 0.005 limit;
- maximum raw interaction difference 0.0002425682 kBT;
- largest site-mean MC occupancy difference across three seeds 0.000129998.

These are fixed-coordinate regression results. They do not establish complete
PB convergence, physical pKa accuracy or execution on every ARM CPU. In
particular, the unchanged focus/model iteration cap remains part of the
previously documented convergence limitation. The build marker deliberately
retains `NON_SVE_EXECUTION_PENDING` until a separate gate is recorded.

## What longer MD changes in the interpretation

The table gives two-repeat medians for **200 ps**, using the identical frozen
HEWL TPR, 1-fs step and output schedule. Command time includes process startup;
GROMACS time is its own reported timing interval. These ARM results belong to
the **SVE512/A64FX reference**, not the portable candidate.

| Machine / threads | Profile | Command seconds | GROMACS seconds | Reported ns/day |
|---|---|---:|---:|---:|
| mini05 x86 / 4 physical cores | default | 1030.4 | 1028.1 | 16.81 |
| mini05 x86 / 4 physical cores | `-reprod` | 1032.9 | 1031.0 | 16.76 |
| Deucalion ARM / 4 | default | 4402.7 | 4357.7 | 3.97 |
| Deucalion ARM / 4 | `-reprod` | 4377.3 | 4361.0 | 3.96 |
| Deucalion ARM / 16 | default | 1293.6 | 1248.5 | 13.84 |
| Deucalion ARM / 16 | `-reprod` | 1258.3 | 1242.0 | 13.91 |
| Deucalion ARM / 48 | default | 639.3 | 577.8 | 29.91 |
| Deucalion ARM / 48 | `-reprod` | 604.1 | 587.8 | 29.40 |

At equal four-core counts, ARM's reported integration time is about 4.2 times
the x86 time. At 48 cores, ARM finishes this MD-only case sooner than mini05 at
four cores, using twelve times as many cores. Different processors, clocks,
memory and storage prevent an ISA-only or compiler-only interpretation.
Every ARM timing task reserved an exclusive 48-core node even when running
fewer threads; the thread count is not the billed reservation.

`-reprod` reduces the ARM time outside the reported GROMACS interval from about
45 seconds (4/16 threads) or 61 seconds (48 threads) to about 16 seconds. The
200-ps command-time improvement is only 0.6%, 2.7% and 5.5% at 4/16/48 threads.
At 50 ps it is 2.4%, 8.6% and 21.4%. Sustained integration rates change much
less, and the 48-thread reproducible case is slightly slower inside GROMACS.
Thus this is principally a startup benefit for short, repeatedly launched
segments. The earlier short-cycle tests remain relevant to CpHMD. These longer
fixed-protonation trajectories do not justify changing the titration interval.

All 32 observations passed frame-count, finite-energy/temperature, atom-order,
disulfide-geometry and completion checks. Two repeats provide an engineering
screen rather than a statistical performance study or equilibrium sampling.
Raw compact observations and both durations are in
`evidence/2026-10-29/overnight-results/`.

## Portable-image checks already dispatched

The new root is independent of the completed overnight root:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/portable-validation.20261029.gj2COz
```

| Stage | Job | Purpose / dependency |
|---|---|---|
| All-site integration | 2160986 | Two real PB/MC/topology/relaxation/effective-MD cycles; passed `0:0`, 4:26 |
| RT and forced stop/resume | 2160987 | Seven cycles, full refreshes 1/6 and reduced reconstruction; passed `0:0`, 11:18 |
| Separate allocation continuation | 2160988 | Finalized reduced cycle 7 → 8; passed `0:0`, 2:26 |
| Portable longer MD, 16/48 threads | 2160989_3,5 | Two repeats of 50/200 ps, `-reprod`; running after continuation |
| Portable longer MD, four threads | 2161053_0–3 | One unchanged observation/task, at most two exclusive nodes simultaneously; all four indices required |
| Generic DelPhi/PETIT component screen | 2160991 | Three serial repeats of the previously frozen six PB decks and MC table; passed `0:0`, 26 seconds |

All jobs pin the new image SHA256, source manifest and starting snapshot. The
new helper labels its image scope explicitly; an audit from the reference
cannot silently count as portable-image acceptance. No canonical controller,
force-field, solver mathematics, titration interval or scientific threshold was
changed. RT continuation remains a GRO/TOP/RT controller checkpoint, not
bitwise continuation of GROMACS integrator/thermostat state from a CPT file.

The newly frozen source archive has SHA256
`b247bc525d9ee8240d5a173d6d4f19f9fdc43596f05efad401ad6a56ffb1cd25`.
The separate component launcher has SHA256
`6fb79af5f09a4db4d917097ca5fc2c648d698bf7aa5f108ad3cae7c689c76867`.
Both are retained with the actual executed script; the running source archive
is immutable even if this development checkout is subsequently committed.

The original four-thread task `2160989_1` was deliberately canceled after its
partial trajectory rate showed that all four observations would exceed the
four-hour allocation. Its partial log is preserved; it supplies no accepted
timing. This is a scheduling adjustment, not a scientific-output failure.
The replacement uses the same TPR, profile, two 50-ps/two 200-ps observations
and replicate IDs, split across four bounded allocations. It has a new frozen
source SHA256 `be0af039036420b410734ebdcea5180d429d0aa70f493d5c2b40b8d9bd19524d`
and a separate root:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/portable-validation.20261029.split4.haW4Gw
```

Each split summary explicitly says `complete_case: false`. Require all four
indices, the complete `(50000/200000 steps, repeat 1/2)` set and passed health
audits before aggregating this case. Never substitute partial progress estimates
for completed benchmark observations. The two arrays together can reserve up to
four exclusive nodes; individual reservations remain 48 cores for isolation.

The generic solver's serial component times are 1.19–2.17 times the A64FX
solver's times on these six decks. Against the original x86 solver they are
2.80–3.84 times as long. PETIT's generic/reference difference is about 0.5% in
this small sample. Both the matched input hashes and actual iteration/residual
records accompany these ratios in
`evidence/2026-10-29/portable-followup/`. Portability has a measured cost here;
retain the separately named optimized reference. Performance of the whole
portable container still requires its pending MD observations.

## Non-SVE gate and recovery

`tests/arm64/check_non_sve_runtime.py` **passed locally** under QEMU 10.2.1 on the
x86 workstation, using an
extraction of the exact verified SIF. A tiny GNU-assembled SVE control must
execute on QEMU's `max` model and fail with SIGILL on `cortex-a53`. The real
generic DelPhi model/coarse/focus decks, complete-table MC, analytic PETIT,
periodic fixgro and water MD/PLUMED then run on that Cortex-A53 model.
[QEMU documents named CPU feature restrictions](https://www.qemu.org/docs/master/system/arm/emulation.html).
No root, binfmt registration or system package installation is needed. Package
downloads/extractions and generated instruction-probe binaries stay outside Git.
This is an executed-path gate; physical non-SVE ARM testing remains desirable.
It must not supply performance numbers.

The control exited zero on `max` and was terminated by SIGILL (`-4`) on
`cortex-a53`. All real workloads passed. The six printed PB scalar energies and
their last reported iteration counts matched native generic-ARM execution;
the frozen-table MC means/final states also matched. This is not an emulated
comparison of every element in the complete PB energy matrix. Compact audit,
actual binary hashes, package hashes and comparison are in
`evidence/2026-10-29/non-sve/`. Full logs, package extractions, rootfs and generated
control binaries remain outside Git in `../artifacts/arm64/non-sve-20261029/`.
The original build marker remains unchanged as a record of what that build
itself proved; this later acceptance is a separate receipt.

Off-cluster recovery copies are being collected under `../artifacts/`, outside
Git. These essential candidate copies have completed:

| Local artifact | Verified identity |
|---|---|
| `../artifacts/arm64/portable-2160578/CpHMD-arm64.sif` | Exact image SHA256 `dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479` |
| `../artifacts/arm64/portable-2160578/recovery-runtime-and-recipe.tar.gz` | SHA256 `8e2ebed1e9137d88d6864b85e528574abb56d1ebad8daef69e28d93c6ecb1637`; all 40 regular members matched independently collected remote hashes; all solver runtime bytes also matched pre-build provenance |
| `../artifacts/arm64/CpHMD-portable-seed-20261028.tar.gz` | Frozen source seed; SHA256 `ec7148f2ee65db667f31bf8204b4ef20c7e8386491ec55ee01744db7cf9405ff` |
| `../artifacts/arm64/cphmd-delphi5-matched-source.tar.gz` | Matched solver source; SHA256 `e42194bac9255b658c5637da32a8f7a7203dccc78ac087d3f15c118fc8a97026` |

GNU tar reported metadata-change warnings for two runtime files during the
focused recovery transfer. Its exit status 1 is retained in the recovery audit;
the complete archive was accepted only after gzip/archive validation and
comparison of every regular member against independent remote SHA256 values.
No byte mismatch was found. The current seed manifest was also rechecked
remotely. This evidence is distinct from a clean exit-status claim.

Larger full-build and raw overnight ARM/x86 archives are still transferring.
The full-build archive deliberately excludes the SIF, which has the separate
verified copy above. A `.part` archive is not a finished backup. Keep the
workstation on during these transfers. Submitted Slurm jobs themselves need
neither the workstation nor a live SSH session. Read actual SHA sidecars and
transfer status before calling the full recovery campaign done. Interrupted
initial streams remain explicitly named `.abandoned-uncompressed-stream` and
are not accepted backups. Archives can contain container-specific symlinks;
do not blindly restore them into a live checkout or host root.

`quotaprojects` reported project usage **18.39G / 2.93T** and 82568 files
without a file-count limit at this check. Persistent cluster data remains under
`/projects/F202500250CPCAA2/`.

## Inspect without resubmitting

Run on a Deucalion terminal:

```bash
cphmd_portable_run=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/portable-validation.20261029.gj2COz
squeue -j 2160986,2160987,2160988,2160989,2160991,2161053 -o '%.20i %.28j %.10T %.10M %R'
sacct -j 2160986,2160987,2160988,2160989,2160991,2161053 -o JobID,State,ExitCode,Elapsed
cat "$cphmd_portable_run/submissions.tsv"
find "$cphmd_portable_run" -maxdepth 2 -name overnight-audit.json -print
find "$cphmd_portable_run" -maxdepth 2 -name summary.json -print
```

Before 31 October, finish portable performance and checksum-verified recovery
of the image, compiler runtime,
source/recipe and all acceptance evidence. Then freeze the release candidate
and document remaining hardware coverage and deferred preparation/scheduler
issues. Confirm the generated production wrapper with the portable image and
the already supported explicit guard configuration: these direct Slurm
integration gates do not themselves repeat the generated-wrapper test. The
known default guard-transport issue remains deferred. Additional compiler
tuning is bounded by those delivery requirements.

## Code map for this stage

| File / functions | Role in the cycle and validation |
|---|---|
| `hewl_overnight.py`: `all_sites`, `rt`, `continuation` | Configure disposable explicit fixtures, run the actual controller, call the independent cycle auditor and record image scope. |
| `hewl_overnight.py`: `long_md` | Keep the exact TPR and output cadence while measuring repeated longer fixed-protonation MD; optional `--observation` selects one unchanged replicate/duration for a bounded allocation. |
| `hewl-portable-validation.slurm` | Image/source/snapshot pins, project-backed temp/output, bounded allocations and actual exit receipts for integration or MD. |
| `hewl-portable-components.slurm` | Same Bash engine timer and frozen decks as the earlier x86/reference screen, followed by independent PB/MC output audit. |
| `check_non_sve_runtime.py`: `logged`, `digest`, `main` | Retain true command outcomes, pin inputs/binaries and exercise real delivered executables behind a verified non-SVE instruction control. |
| `prepare_hewl_performance.py --overnight` | Freeze allowlisted source and per-file hashes before upload; no credentials, Git metadata, ELF or runtime results. |

Only reviewed source, documentation and compact text evidence belong in Git.
The repository guard checks credential patterns and new runtime artifacts;
it does not certify malware absence or all historical Git objects.
