# Native ARM candidate: build and validation commands

This branch now combines the reviewed August explicit-settings work with the ARM build support. The legacy source worktree is unchanged. `settings-import.json` identifies the imported files and their original hashes. The released x86 0.7.0 image remains the scientific comparison baseline.

## What is ready, and what has passed

- The five settings/runtime repository checks pass after import.
- `check_arm64_build_support.sh` checks shell parsing, compiles fixgro, PETIT and the two PB helpers, and runs fixgro and analytic PETIT fixtures on the local host.
- Native A64FX job `2147469` passed PETIT architecture/version inspection, native fixgro compilation and both PBC fixtures, fakeroot execution and a minimal SIF build. Its exit was `0:0`; elapsed 27 seconds. The probe image and full log are preserved in the project.
- The 20-step water MD smoke fixture passed on the existing x86 GROMACS 2026.3 CPU image, including PLUMED distance output and XTC/EDR readability. The PETIT fixture passed at pH -1, 0 and 1 against analytic two-state probabilities.
- The source-context preparation tool was exercised locally: manifest verification passed, explicit settings/profiles were preserved, and all host ELF products were excluded (53 omitted host products in the tested snapshot).
- Full GROMACS/PLUMED ARM compilation, native image smoke checks and scientific CpHMD validation have **not** yet passed. No full compilation job has been submitted by the agent in this step.

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

## 1. Review and commit the implemented step locally

Run in the local desktop terminal, not on Deucalion:

```bash
cd '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/CpHMD-container'
git status --short --branch
git diff --check
bash tests/static_checks.sh
bash tests/check_databases.sh
bash tests/check_reduced_titration_logic.sh
bash tests/check_asic_settings.sh
bash tests/check_settings_profiles.sh
bash tests/check_arm64_build_support.sh

git add -- .gitattributes .github/workflows/ci.yml CpHMD DelphiTools/src container_build template tests review/v0.7.1-stage3 README.md docs/CPHMD_SETTINGS_REFERENCE.md docs/aarch64/BUILD_AND_VALIDATE.md docs/aarch64/evidence/2026-10-26
git diff --cached --check
git diff --cached --stat
git diff --cached -- CpHMD/scripts/CpHMD.sh CpHMD/scripts/settings_contract.sh container_build/arm64 container_build/prepare_arm64_build.py container_build/run_arm64_build.sh container_build/submit_deucalion_arm64.sh
git commit -m 'Integrate explicit settings and add native ARM build pipeline'
git push origin codex/arm64-deucalion-20261026
```

The agent has not staged, committed or pushed these changes. Raw build/scientific evidence has whitespace checking disabled through the narrow `.gitattributes` rule; source-code whitespace checking remains enabled.

## 2. Prepare an immutable candidate and submit its build

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

The embedded test verifies AArch64 ELF payloads and dependencies, GROMACS version/SIMD, native fixgro, analytic PETIT probabilities, and a short MD/PLUMED run with readable trajectory/energy output. Scientific PB/MC validation is not included in that success marker.

## 4. Next scientific gates, before performance claims

After the build succeeds, work from a new test directory and immutable input snapshot. Do not point this candidate at a production run directory.

1. Fixed-coordinate PB/MC comparison against x86: compare helper centers, intrinsic pK values and the interaction matrix, then PETIT probabilities with recorded seeds. Establish file units and freeze tolerances before evaluating ARM results.
2. Short all-site CpHMD run, followed by RT interval 5 through cycle 7; exercise full refreshes 1 and 6, active/fixed-template reconstruction and topology updates.
3. Finalize after a reduced cycle and continue from its checkpoint. Audit the restored active set, segment time continuity, final GRO/TOP/TPR and XTC/EDR.
4. Only after these pass, compare thread counts/affinity and SVE versus NEON on the same inputs, recording MD-only and complete CpHMD throughput.

The explicit-settings profiles require adapting every `CHANGE_ME` field. Historical settings that relied on hidden defaults must be upgraded in the copied test directory; do not bypass the contract to make an old input run.
