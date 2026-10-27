# Native ARM candidate: build and validation commands

This branch now combines the reviewed August explicit-settings work with the ARM build support. The legacy source worktree is unchanged. `settings-import.json` identifies the imported files and their original hashes. The released x86 0.7.0 image remains the scientific comparison baseline.

The [developer guide](DEVELOPER_GUIDE.md) maps each build/validation file and
function to its caller, outputs and place in the scientific cycle. Follow its
commenting convention for future project-owned changes.

## Current ARM image: ordinary-user acceptance after permission repair

Native preparation job 2148556 showed that the original SIF's `/analysis` and
other copied source trees retained project-only access modes. Embedded `%test`
had run as fakeroot, so build success did not prove ordinary-user usability.

Job **2148618** derived a permission-normalized SIF without recompiling. It
verified **1,764 runtime files byte-identical** before/after and passed native
ordinary-user dependency/PETIT/fixgro/MD/PLUMED checks as UID 30597 (not root).
The original SIF remains preserved. The current usable candidate is:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/runtime-permissions/repair.G02c6n/CpHMD-arm64-readable.sif
SHA-256: d153f31722e76f167080485942074633ce9e3d7abc51dfa97827f790947880ba
```

A matching off-cluster copy is saved outside the Git checkout at
`../artifacts/arm64/CpHMD-arm64-readable-2148618.sif`. Its checksum was verified.
Runtime permission normalization and a mandatory ordinary-user post-build check
are now in the full-build path as well. Logs are in
`evidence/2026-10-27/arm-runtime-permissions/`.

HEWL topology/site verification subsequently passed on native ARM in job
**2148669**, with matching parsed x86/ARM topology data and 21 sites; see
[HEWL_TOPOLOGY_2026-10-27.md](HEWL_TOPOLOGY_2026-10-27.md). Scientific PB/MC,
complete CpHMD/RT and restart validation remain pending.

ARM access ends **31 October 2026**. General terminal/preparation issues are
documented in [DEFERRED_ISSUES.md](DEFERRED_ISSUES.md) and deferred at the user's
request. The immediate priorities are ARM scientific gates and verified exports.

Native solution job **2149846** passed `COMPLETED 0:0` in 7 minutes 54 seconds:
solvation/ions, restrained contact minimization, 10 ps NVT and 20 ps NPT. Its
frozen protocol, health checks and checksum-verified off-cluster snapshot are in
[HEWL_SOLUTION_2026-10-27.md](HEWL_SOLUTION_2026-10-27.md). Fixed-coordinate
matched-source PB/MC is now the next scientific gate. Do not rerun preparation
just to record the milestone.

## Original native compilation and embedded tests: job 2147983

The native build and embedded smoke gates passed on 27 October 2026. Job
`2147983` finished `COMPLETED`, exit `0:0`, in `00:41:35`, from source commit
`31ca50688bc0158e44263a78c2b6d9c4ae438d0d`. All five selected GROMACS suites
executed and passed: CommandLine, Hardware, Math, Mdtypes and FileIO. The
runtime reports GROMACS 2026.3, mixed precision, ARM_SVE with 512-bit compiler
flags, thread-MPI/OpenMP, CPU-only and PLUMED enabled.

Embedded checks passed for the 21 ELF payload files inspected as AArch64,
runtime dependencies, both fixgro assembly fixtures, PETIT analytic occupancy
at pH -1/0/1, and a 20-step water MD/PLUMED run with readable XTC/EDR and finite
COLVAR output. This fixture is not a throughput benchmark or a complete CpHMD
validation.

The candidate image is:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/31ca50688bc0158e44263a78c2b6d9c4ae438d0d-ARM_SVE-20261027T004036Z/CpHMD-arm64.sif
```

Its SHA-256 was independently checked against the saved checksum file:

```text
7393d585ad790e1d53089d9199cf11bdbb6b9cbea1016d16b979b3999fb24343
```

Logs, test output, recipe, manifest and provenance are copied into
`evidence/2026-10-27/build-2147983/`; the image remains in project storage.
Retain the original for provenance; use the permission-normalized derivative
above for ordinary-user scientific execution.

The next step is to freeze a small input system and compare fixed-coordinate
PB/MC results with the x86 reference, with units/tolerances established before
examining differences. Then exercise complete CpHMD cycles, RT refreshes and
checkpoint continuation. Those tests remain pending; section 4 defines them.
No additional build job is needed to record or use this successful candidate.

## Previous build: compiled-test gate failure in job 2147644

The first complete build attempt reached the end of the native PLUMED/GROMACS
compilation on A64FX with SVE-512. SLURM job `2147644` ran for `00:36:18` and
finished `FAILED`, with accounting exit `127:0`. Its CTest phase reported
`commandline-test`, `hardware-test` and `math-test` as missing executables;
all three selected suites were **Not Run**. No completed SIF or build-success
marker was produced, and image smoke/scientific tests have not run.

The build script enabled/registers tests through CMake, but normal GROMACS
release builds exclude test executables from the default build target. The
script did not explicitly build them before CTest. Its approximate test-name
filter also omitted two intended suites, whose exact names are `FileIOTests`
and `MdtypesUnitTest`. This is a build orchestration error; these results do not
show a numerical test failure or a PETIT architecture problem.

The corrected gate, `container_build/arm64/check-gromacs-build.sh`, explicitly
builds all five selected test executables, verifies that all five CTest names
are registered and then executes them. Failure remains fatal and the test-build
log, selected-test inventory and CTest output are preserved. The EXIT handler
now also preserves `LastTest.log` after a failing test run.

The isolated regression `tests/check_gromacs_test_gate.sh` passed on mini05:
the default build leaves its fixture test binaries unbuilt; the gate builds/runs
all five, rejects a deliberately failing test and rejects a missing registration.
This regression checks orchestration, not the actual ARM engine's tests. CI runs
it with CMake installed. The desktop lacks CMake, so its existing support checks
parse this regression while the executable regression was run on mini05.

Original Deucalion evidence is retained under:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/c1bb78bc515136573002bd0dacea0ee97944ec72-ARM_SVE-20261026T233843Z/
```

Copies of the build log and compiler/test artifacts, plus the repair regression
record, are under `evidence/2026-10-27/`. Keep the failed candidate unchanged.
The correction was committed in `31ca506` and those gates subsequently passed
in job `2147983`, as recorded above. Keep this failure evidence to explain the
orchestration correction without confusing it with a numerical test failure.

## Recovery from the incomplete-bundle clone error

The initial transfer of commit `ee74839392d385c21958c35e193e2f21965a78ed`
failed because the workstation clone was shallow. Commit `3c63a518...` was a
shallow boundary whose parent `6db15cc8...` was absent from the exported pack.
The original bundle's local `git bundle verify` passed, but an independent clone
reproduced the recipient's missing-parent failure. Verifying inside the donor
repository was insufficient. This is a source-transfer failure before compilation
or job submission, not evidence about PETIT or the ARM image.

The repair fetches complete history without changing the current branch or
working files. Run this in another checkout if it is still shallow (already
completed in this desktop checkout):

```bash
git rev-parse --is-shallow-repository
if [ "$(git rev-parse --is-shallow-repository)" = true ]; then
    git fetch --unshallow upstream
fi
git fsck --connectivity-only --no-dangling
```

The submission helper now rejects shallow history before transfer and uses
`create_source_bundle.sh` to validate the actual pack from an empty repository,
clone it independently, check history connectivity and check out the exact tip.
Remote clones are staged under a unique `.incoming-TIMESTAMP` name and validated
before being published at `sources/COMMIT`. Existing source checkouts must pass
connectivity, identity and clean-tree checks before reuse. Failed inputs and any
remaining staging directories are retained. The failed `ee748393...` checkout was absent when inspected;
no manual deletion is needed. Retry the normal helper after committing the repair.

After the history repair, the same committed branch successfully cloned and
passed connectivity, exact-HEAD and clean-tree checks on Deucalion at
`validation/git-transfer.9wY0Xv/checkout` under the sprint project directory.
This was an isolated transfer check; it submitted no build job. The regression
and all six repository/support checks passed. Evidence is recorded in
`evidence/2026-10-26/bundle-repair-checks.json` and
`evidence/2026-10-26/bundle-repair-transfer.json`.

## What is ready, and what has passed

- The five settings/runtime repository checks pass after import.
- `check_arm64_build_support.sh` checks shell parsing, compiles fixgro, PETIT and the two PB helpers, and runs fixgro and analytic PETIT fixtures on the local host.
- Native A64FX job `2147469` passed PETIT architecture/version inspection, native fixgro compilation and both PBC fixtures, fakeroot execution and a minimal SIF build. Its exit was `0:0`; elapsed 27 seconds. The probe image and full log are preserved in the project.
- The 20-step water MD smoke fixture passed on the existing x86 GROMACS 2026.3 CPU image, including PLUMED distance output and XTC/EDR readability. The PETIT fixture passed at pH -1, 0 and 1 against analytic two-state probabilities.
- The source-context preparation tool was exercised locally: manifest verification passed, explicit settings/profiles were preserved, and all host ELF products were excluded (53 omitted host products in the tested snapshot).
- Job `2147983` passed native compilation, all five selected unit suites and embedded image smoke checks, and produced the checksum-verified SIF. Fixed-coordinate PB/MC, full CpHMD/RT and restart scientific validation remain pending.

## Build decisions

The first candidate starts from the existing working ARM bootstrap SIF, SHA-256:

```text
6d1ddca5ce97f686cff36990a9696a2d311a73dc3581d97f30bc9fe1b73d08d6
```

This preserves the native legacy DelPhi solver and six NVHPC runtime libraries. GROMACS 2026.3, PLUMED, PETIT, fixgro, geom_center and calc_pkg_low are rebuilt from source. Helper sources were recovered from ARM commit `737a046`; source and build-source hashes are recorded in `DelphiTools/src/PROVENANCE.json`. The inherited solver still needs the fixed-coordinate PB/MC comparison before scientific acceptance.

The default target is A64FX SVE-512, mixed-precision GROMACS, OpenMP plus thread-MPI, no CUDA and no external MPI. FFTW is the native library already present in the bootstrap. PLUMED is built without MPI or x86 asmjit. Build parallelism defaults to four CPUs to limit peak memory. `--jobs 8` is supported when deliberately requested; the launcher rejects build parallelism exceeding the SLURM allocation.

The bootstrap SIF is an explicit reproducibility input, not a claim of a standalone public release recipe. Preserve it with the candidate, source bundle, manifest and logs. Its unsigned status is distinct from the recorded SHA-256. DelPhi/helper and exact NVHPC redistribution terms remain a publication gate.

Deucalion's project directory requires supplementary-group access, which fakeroot drops. The successful arrangement is:

- Authoritative source, Git bundles, source archives, build snapshots, logs and SIFs: `/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/`.
- Temporary copies for assembly, compiler work, and the image-under-construction: node-local `/tmp`, as explicitly authorized by the user.
- The ordinary host process stages inputs and copies artifacts/results back after fakeroot returns. The local-image build uses `--disable-cache`; no compiler downloads or OCI downloads occur in the fakeroot build.
- The project ACLs and production directories are unchanged. Failed temporary build work is not destructively cleaned by the launcher.

## 1. Record the native HEWL solution-preparation milestone locally

Run in the local desktop terminal, not on Deucalion:

```bash
cd '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/CpHMD-container'
git status --short --branch
git diff --check

git add -- container_build/slurm/hewl-solution.slurm tests/arm64/prepare_hewl_solution.sh tests/arm64/plan_hewl_ions.py tests/arm64/check_hewl_solution.py tests/arm64/hewl-solution tests/check_hewl_solution_helpers.py docs/aarch64
git diff --cached --check
git diff --cached --stat
git diff --cached -- container_build/slurm/hewl-solution.slurm tests/arm64 tests/check_hewl_solution_helpers.py docs/aarch64/HEWL_SOLUTION_2026-10-27.md
git commit -m 'Prepare and validate solvated HEWL snapshot on native ARM'
git push origin codex/arm64-deucalion-20261026
```

The agent has not staged, committed or pushed these changes. Raw build/scientific evidence has whitespace checking disabled through the narrow `.gitattributes` rule; source-code whitespace checking remains enabled.

## 2. Prepare and submit a future candidate when code changes

Job `2147983` already produced the candidate for scientific validation. The
commands below document the build workflow for a later implementation change;
do not submit another build just to record the successful milestone.

From the same local terminal:

```bash
bash container_build/submit_deucalion_arm64.sh --submit
```

The helper refuses a dirty checkout. It verifies the GROMACS source archive's pinned SHA-256, creates a Git bundle of the committed development branch, transfers that bundle and the archive to the project, and clones the source bundle there. GitHub private keys, tokens and credential configuration are not copied to Deucalion.

On Deucalion it freezes a new build context, renders the definition including the canonical helper-app interface, records metadata/hashes, and submits a four-hour `dev-arm` job using `f202500250cpcaa2a`. It prints the SLURM job ID and exact prepared-output directory. Save that output.

To prepare and inspect the rendered context before submitting instead:

```bash
bash container_build/submit_deucalion_arm64.sh
```

This prints the exact `ssh ... sbatch ...` command for that context. Review its `build.json` and `CpHMD.arm64.def`, then run the printed command. Do not submit both workflows for the same intended candidate.

For a separate NEON comparison candidate later:

```bash
bash container_build/submit_deucalion_arm64.sh --simd ARM_NEON_ASIMD --submit
```

This is a comparison on the tested ARM environment, not a claim of portability to every AArch64 CPU. The carried solver/runtime must also be checked on any additional hardware.

## 3. Inspect progress and result

The following commands are read-only. The second selects the most recently prepared candidate and prints its path before reading logs, so confirm that it is the candidate you intended to inspect.

```bash
ssh deucalion 'squeue -u "$USER" -o "%.18i %.12P %.24j %.10T %.20R"'
ssh deucalion 'cphmd_build=$(ls -1dt /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/* | head -n 1); printf "Candidate: %s\n" "$cphmd_build"; tail -n 60 "$cphmd_build"/slurm-*.log'
ssh deucalion 'cphmd_build=$(ls -1dt /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/* | head -n 1); printf "Candidate: %s\n" "$cphmd_build"; cat "$cphmd_build"/exit-*.txt; cat "$cphmd_build"/build-result.txt'
```

A successful build has all of:

- SLURM exit `0:0` and `exit-JOBID.txt` containing `0`;
- `build-result.txt` containing `BUILD_AND_SMOKE_TESTS_PASSED`;
- `CpHMD-arm64.sif` and its SHA-256 file;
- `image-inspect.json`, the rendered/executed definitions, source manifest, build metadata and logs;
- `artifacts-JOBID/` with compiler/package information, CMake configuration and targeted GROMACS unit-test output.

The targeted suites are `CommandLineUnitTests`, `FileIOTests`,
`HardwareUnitTests`, `MathUnitTests` and `MdtypesUnitTest`.
`gromacs-selected-tests.json` must list all five; `gromacs-ctest.log` must show
them executed and passed. `gromacs-test-build.log` records their compilation.

The embedded test verifies AArch64 ELF payloads and dependencies, GROMACS version/SIMD, native fixgro, analytic PETIT probabilities, and a short MD/PLUMED run with readable trajectory/energy output. Scientific PB/MC validation is not included in that success marker.

## 4. Next scientific gates, before performance claims

After the build succeeds, work from a new test directory and immutable input snapshot. Do not point this candidate at a production run directory.

1. Fixed-coordinate PB/MC comparison against x86: compare helper centers, intrinsic pK values and the interaction matrix, then PETIT probabilities with recorded seeds. Establish file units and freeze tolerances before evaluating ARM results.
2. Short all-site CpHMD run, followed by RT interval 5 through cycle 7; exercise full refreshes 1 and 6, active/fixed-template reconstruction and topology updates.
3. Finalize after a reduced cycle and continue from its checkpoint. Audit the restored active set, segment time continuity, final GRO/TOP/TPR and XTC/EDR.
4. Only after these pass, compare thread counts/affinity and SVE versus NEON on the same inputs, recording MD-only and complete CpHMD throughput.

The explicit-settings profiles require adapting every `CHANGE_ME` field. Historical settings that relied on hidden defaults must be upgraded in the copied test directory; do not bypass the contract to make an old input run.
