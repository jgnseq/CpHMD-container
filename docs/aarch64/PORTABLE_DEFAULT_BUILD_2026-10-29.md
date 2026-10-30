# Portable default: packaging and fresh-candidate verification

## Behavior implemented

`submit_deucalion_arm64.sh` and `prepare_arm64_build.py` now default to the
**portable** profile: ARMv8-A/ASIMD, generic DelPhi and no SVE requirement.
The explicit `a64fx` profile retains the separately validated specialized
bootstrap. `--simd ARM_SVE` without `--profile a64fx` fails before transport.
Selecting NEON with the A64FX profile remains a hardware-specific comparison;
it is never labeled portable.

For committed, reviewed source on the workstation:

```bash
# Prepare for inspection; does not submit anything.
bash container_build/submit_deucalion_arm64.sh

# Portable build plus the separate bounded HEWL scientific acceptance job.
bash container_build/submit_deucalion_arm64.sh --submit --verify-hewl --jobs 8

# Explicit optimized reference; separate output directory and metadata.
bash container_build/submit_deucalion_arm64.sh --profile a64fx --submit --jobs 8
```

Do not run these commands to duplicate the already submitted development
candidate below. The normal launcher exports **committed objects only**,
checks tracked changes and required new build files, scans repository safety
before upload, and independently verifies the source bundle's connectivity.
Unrelated untracked notes stay local and are never added automatically. The
current branch name is validated before insertion into the remote command.
The agent has not staged, committed or pushed any user changes.

## Runtime inheritance and fresh build

The shared profile policy pins the portable bootstrap to:

```text
portable.20261028.MZWHAj/candidate/CpHMD-arm64.sif
SHA256 dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479
```

This bootstrap already passed native scientific gates, non-SVE emulation and
portable timing/wrapper checks. It supplies the generic DelPhi runtime compiled
with NVFORTRAN 25.1 `-O2 -tp=px -Kieee`. This packaging step **retains that
verified runtime**; it does not recompile or change DelPhi mathematics.

Before removing inherited payloads, the rootfs staging helper checks the
bootstrap pin, generic target, absence of mixed CPU/unsafe math flags, all
recorded installed hashes, the fixed solver hash and AArch64 ELF headers.
Only the declared solver/libraries are staged and reinstalled. The whole
native-library/PLUMED/PETIT/GROMACS trees are rebuilt or replaced, preventing
obsolete optimized variants surviving under alternate names.

GROMACS/PETIT/helpers/PLUMED keep the tested explicit ARMv8-A flags. Inherited
build evidence **and installed smoke-test files** are removed in the disposable
rootfs before new evidence/tests are installed. Original base images and their
evidence remain unchanged. All persistent source, cache, images and output stay
in the project. Only the previously authorized rootfs/build staging uses `/tmp`.

Parent validation is not acceptance of a new SIF. New images retain pending
validation metadata until separate candidate-specific receipts establish their
outcomes. Physical other-ARM coverage and absolute PB convergence remain outside
these engineering gates. The default guard-forwarding issue is still deferred;
no canonical controller, force-field or scheduler-generator code was changed.

## Submitted development snapshot

The user committed the previous stage as `e53734f`. This candidate was frozen
earlier from `d6607de` plus the exact staged/working-tree bytes and records
`source_dirty=true`. It is a **fresh native rootfs build**, not a claim that its
source was already a clean published Git revision. After review/commit, the
normal launcher uses the committed export path above. Preserve the recorded
source snapshot and manifest when associating it with the reviewed commit.

Candidate control root:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/portable-default.20261029.Q6nWxw
```

| Stage | ID | Acceptance / bound |
|---|---|---|
| Fresh build | 2165989 | Eight CPUs, 28 GiB, four hours; five GROMACS suites, dependency/helper/MD/PLUMED and ordinary-user smoke |
| Native candidate acceptance | 2165990 | `afterok` build, eight CPUs, two hours; embedded-source identity, tight PB/MC, all-site/RT/continuation and serial-component checks |
| Verified recovery | 2166011 | `afterany` acceptance, one CPU, one hour; preserves diagnostics even if native acceptance fails |
| mini05 recovery and non-SVE gate | timeout PID 189313 | Detached eight-hour bound; copied archive SHA256, native-pass requirement and exact-image Cortex-A53/QEMU workloads |

At 00:12 UTC on 30 October, build **2165989 completed 0:0 in 25m10s**.
The generic bootstrap byte/target preflight, five GROMACS suites and
ordinary-user dependency/helper/PETIT/MD/PLUMED smoke checks passed. Native
scientific acceptance **2165990 was running**; recovery and the candidate's
non-SVE gate remained pending. The detached mini05 process was still alive
after disconnection. See `pipeline-status.json` in the adjacent evidence folder.
These are distinct stages: build success alone does not accept the candidate.

Fresh candidate SIF SHA256:

```text
d4d4278861eb1e9917db8b0ca74b32304fca69674a109f9813574807b85fb5f4
```

Snapshot identities:

```text
Context manifest: 0e40c2cb38ae22cbda5437dd250d19168c975b31ff1a48e5dfb8da0bb4eadfac
Source packet:   32f029602b532fbd5b8a24dc212f13eda74ce65e0d997779d4449eb99074cf74
Full local source archive: 802d4fde885117593f5e4b50b581cc58938f9b1dcdcf93aa640d774a93f909aa
```

Only seven changed source files needed upload. The reconstruction helper copied
**only current manifest-listed files** from the packet or immutable source
cache, checked each digest before copying, and rechecked the complete resulting
manifest. The materialized context has 3360 regular files and zero inherited
ELF payloads. A full source archive is saved outside Git at
`../artifacts/arm64/portable-default-20261029/inputs/frozen-context.tar.gz`.
This cache is a transport optimization, not an alternative source of CPU policy
or validation. The normal committed-source entry point continues to use its
verified Git bundle. No private key, credential configuration or Git directory
was put in the development packet.

## What the queued gates do

Native acceptance first proves that the mounted controller/data bytes match
the embedded image; expected newly compiled helper binaries are checked by
their executable gates instead of text identity. Fixed PB/MC uses the original
tighter x86 reference and unchanged acceptance tolerances. It then runs two
all-site cycles, seven RT cycles including a forced finalized stop/resume, and
reduced cycle 7 → 8 continuation. This is controller GRO/TOP/RT continuation,
not bitwise GROMACS CPT continuation. The serial micro screen retains actual
energies/iterations and checks deterministic within-platform repeats.

Recovery is separate from scientific acceptance: an archive can correctly
preserve a failed candidate. The mini05 verifier refuses to execute it unless
the archived native acceptance is passed and the extracted SIF matches its
recorded SHA256. It derives the ARM64 SIF partition from the installed SIF tool,
extracts it without root, and runs the same non-SVE executed-path gate as before:
SVE positive/negative control, real DelPhi decks/MC/helper fixtures and water
MD/PLUMED. Sources are a small exact subset from the verified candidate archive;
the micro inputs are copied from that candidate's native gate. No performance
numbers are taken under emulation.

Recovery root:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/recovery.default-portable.20261029.NkWg6R
```

mini05 root:

```text
/home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.default-portable.20261029.Hl8Yxh
```

## Inspection and shutdown

On Deucalion, inspect existing jobs rather than submitting duplicates:

```bash
cphmd_run=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/portable-default.20261029.Q6nWxw
sacct -j 2165989,2165990,2166011 -o JobID,State,ExitCode,Elapsed
tail -n 40 "$cphmd_run/candidate/slurm-2165989.log"
cat "$cphmd_run/candidate/acceptance-result.txt"
cat "$cphmd_run/candidate/acceptance/acceptance.json"
```

The last two files exist only when those stages have reached their results.
On mini05:

```bash
cphmd_verify=/home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.default-portable.20261029.Hl8Yxh
cat "$cphmd_verify/verification.exit"
tail -n 40 "$cphmd_verify/pipeline.log"
cat "$cphmd_verify/verification.json"
```

Require `verification.exit=0`, `verification.json` passed and matching image
hashes before calling the new candidate accepted. Pending/failed stages retain
their diagnostics and do not resubmit themselves. The workstation may shut
down after confirmed dispatch; mini05 must remain on for its detached follow-up.
All uploads/submissions are complete and no laptop mount or SSH tunnel is used.

## Code map and local validation

| File / function | Role in this stage |
|---|---|
| `arm64/profiles.py`: `select_profile`, `validate_generic_solver` | Shared default/opt-in policy, pinned bootstraps and generic-runtime target checks. |
| `arm64/stage-bootstrap-delphi.py`: `stage_bootstrap` | Verify and stage the pinned generic runtime before clearing inherited payloads. |
| `arm64/install-portable-delphi.py` | Reinstall declared verified runtime, record origin and current hashes. |
| `arm64/build-inside.sh` | Fresh source rebuild and fresh evidence/test installation in the disposable rootfs. |
| `prepare_arm64_build.py` / definition template | Select policy, freeze allowed source, record provenance and render accurate profile labels. |
| `submit_deucalion_arm64.sh` | Committed-source validation/export, profile selection, optional build and dependent native acceptance. |
| `reconstruct_arm64_context.py`: `reconstruct` | Optional development-snapshot transport; reject changed/traversing input and omit all unlisted cached payloads. |
| `slurm/verify-arm64-candidate.slurm` | Candidate-specific native scientific and source-identity gate. |
| `verify_arm64_candidate_on_mini05.sh` | Candidate-specific recovery, native-pass requirement and non-SVE execution. |
| `pull_arm_recovery_on_mini05.sh`: `wait_and_copy` | SHA-checked, resumable server-to-server recovery; default one-hour wait, explicitly bounded up to seven hours for a build pipeline. |

Twenty local policy/CLI/context tests passed, including rejected SVE defaults,
wrong/mixed/corrupt runtimes, dirty tracked source, ignored local notes and
cache traversal/stale-payload controls. Source-bundle history/connectivity,
native helper compilation and analytic PETIT fixtures passed as well. The new
unit gates are wired into `check_arm64_build_support.sh` for future CI runs.
Temporary unit repositories/ELF-header fixtures never execute payloads, use the
network or change the user's index. Runtime binaries/archives remain outside Git.
