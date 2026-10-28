# Portable ARM64 target and disconnect-safe overnight work

## Delivery policy

The intended main delivery is a **portable Linux ARM64 baseline**, with an
explicit ARMv8-A/ASIMD instruction floor and no SVE requirement. The existing
SVE512/A64FX image remains a separately named hardware-specific reference.
Performance gains must not quietly raise the baseline or relax scientific
acceptance. After validation, the portable profile should become the main
launcher/release default; optimized hardware profiles should require opt-in.

Changing GROMACS to NEON alone does not make the previous image portable:
its DelPhi was compiled with `-tp=a64fx`. The new pipeline instead uses:

| Component | Portable-target policy |
|---|---|
| GROMACS | `ARM_NEON_ASIMD`, explicit `-march=armv8-a -mtune=generic`, no fixed SVE width |
| DelPhi | Matched source, NVFORTRAN 25.1 `-O2 -tp=px -Kieee`, existing stdout-only compatibility edit |
| PETIT and C helpers | Explicit `-march=armv8-a -mtune=generic`, unchanged scientific source and conservative existing optimization |
| PLUMED | Same explicit baseline C/C++/Fortran flags; asmjit remains disabled |
| Inherited optimized variants | Replace whole owned GROMACS/PLUMED/PETIT/native-Fortran-library trees so obsolete executables cannot remain under alternate names |

[GROMACS documents NEON/ASIMD for 64-bit ARMv8 and later](https://manual.gromacs.org/2026.3/install-guide/index.html),
whereas SVE builds require the chosen vector width. [NVIDIA 25.1 documents
the Arm `px` target](https://docs.nvidia.com/hpc-sdk/archive/25.1/compilers/hpc-compilers-ref-guide/index.html)
as the generic Arm processor target; omitting the target can select the build
host's features. No `native`, `a64fx`, `-fast` or SVE target is permitted in the
portable solver's declared flags.

This is a compilation target, not a claim that every ARM machine has been
tested. Non-SVE execution (emulation and preferably real hardware) is still
required before broad compatibility is claimed. The image also requires a
compatible Linux/container environment. AArch64 ELF headers alone do not prove
instruction-level portability. The pipeline records these limits explicitly.

## What runs without the workstation

All uploads/submissions are complete. Jobs read only persistent remote files;
no SSH tunnel, laptop mount or running assistant is required. Closing the chat,
logging out or shutting down the workstation does not cancel them. No Git
commit or push is needed to keep submitted jobs running.

| Work | ID / location | Bounds and acceptance |
|---|---|---|
| Seven RT cycles with `-reprod`, forced finalized stop at cycle 1 and fresh-process resume | 2160556 | Passed `0:0`, 9:19; independent state/dictionary/geometry/energy/RT checks |
| Separate-allocation continuation of reduced cycle 7 -> 8 | 2160557 | Passed `0:0`, 2:15; complete cycle auditor and runtime-option checks |
| Longer ARM MD array | 2160558, tasks 0–5 | 4/16/48 threads × default/reprod; two repeats each at 50/200 ps; at most two exclusive nodes simultaneously; four hours/task |
| Portable-target rebuild and tight PBMC comparison | 2160578 | Four hours, eight build CPUs; generic solver, new baseline stack, five GROMACS unit suites, ordinary-user smoke, fixed PBMC under original tighter-profile limits |
| Longer x86 MD | mini05 timeout PID 185338 | Four physical cores; default then reprod, two repeats at 50/200 ps; detached with `nohup` and a four-hour timeout |

The ARM array depends on successful RT and continuation jobs. Invalid
dependencies are canceled; nothing resubmits itself. Array cases 0/1 are four
threads default/reprod, 2/3 sixteen threads, and 4/5 forty-eight threads.
Each task reserves an exclusive 48-core node for timing isolation; its requested
thread count is not the billed allocation size. The longest cases can take
several hours, and queue time can extend completion. Exit status alone is not
scientific acceptance: require the saved audit/summary as well.

The longer timing jobs use the **existing A64FX reference**. Their results must
not be labeled portable-image performance. The portable candidate needs its own
runtime/scientific and performance checks after assembly. Longer fixed-TPR MD
does not change the CpHMD titration interval. RT uses the existing 1-ps effective
cycle length, explicit boundary guard and original PB/MC controls.

Persistent roots:

```text
ARM validation:
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/overnight.20261028.pveYvR

Portable build:
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/portable.20261028.MZWHAj

x86 comparison:
/home/jsequeira/Projects/side/06_CpHMD-container/validation/overnight.20261028.Tst8Pb
```

The only node-local storage exception is the already authorized temporary
rootfs/build staging. Authoritative source, compiler output, caches, candidate
images, logs and simulation temporary/output files remain in the project.

## Tomorrow: inspect existing work, do not submit it again

On a Deucalion SSH terminal:

```bash
cphmd_night=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/overnight.20261028.pveYvR
cphmd_portable=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/portable.20261028.MZWHAj
squeue -j 2160556,2160557,2160558,2160578 -o '%.20i %.26j %.10T %.10M %R'
sacct -j 2160556,2160557,2160558,2160578 -o JobID,JobName,State,ExitCode,Elapsed
cat "$cphmd_night/submissions.tsv"
cat "$cphmd_night/rt/overnight-audit.json"
cat "$cphmd_night/continue/overnight-audit.json"
find "$cphmd_night" -maxdepth 2 -name summary.json -print
tail -n 60 "$cphmd_portable/slurm-2160578.log"
```

Only after the corresponding job finishes:

```bash
cat "$cphmd_portable/exit-2160578.txt"
cat "$cphmd_portable/result.txt"
cat "$cphmd_portable/portable-pbmc-comparison.json"
cat "$cphmd_portable/candidate/CpHMD-arm64.sif.sha256"
```

The intended success marker is
`PORTABLE_TARGET_NATIVE_GATES_PASSED_NON_SVE_EXECUTION_PENDING`.
It deliberately leaves non-SVE execution pending. If compilation, smoke or PBMC
fails, preserve the complete root and inspect the actual error; a built SIF
alone is not acceptance. Never reuse an output directory to hide a failed case.

On mini05:

```bash
cphmd_x86=/home/jsequeira/Projects/side/06_CpHMD-container/validation/overnight.20261028.Tst8Pb
cat "$cphmd_x86/launcher.pid"
ps -p "$(cat "$cphmd_x86/launcher.pid")" -o pid,etime,args
tail -n 40 "$cphmd_x86/launch.log"
find "$cphmd_x86" -maxdepth 2 -name summary.json -print
```

Check `x86-exit.txt` after completion; a live PID is meaningful only if its
command matches this recorded timeout/launcher. No blanket kill/cleanup command
is part of the handover. Failure/timeouts leave diagnostic files intact.

The persistent locator files are `validation/hewl-4lzt/LATEST-OVERNIGHT.txt` and
`LATEST-PORTABLE.txt` below the ARM task root, and `validation/LATEST-OVERNIGHT.txt`
on mini05. The explicit roots/job IDs above remain the authoritative record.

## Next acceptance steps

1. Inspect all outcomes and save accounting; copy completed results off cluster
   and verify their hashes. Preserve failed/partial output separately.
2. Check longer default/reproducible timings and variation, rather than assuming
   the 5-ps speedup persists. Keep fixed-TPR and full-cycle costs separate.
3. If the portable candidate passes native gates, run non-SVE smoke and real
   DelPhi/MC/MD workloads. Confirm compiler/library targets and absence of an
   unconditional SVE requirement; do not benchmark under emulation.
4. Run coupled all-site/RT/continuation gates with the portable image itself.
   Passing these gates with the A64FX reference does not transfer automatically.
5. Benchmark the portable baseline and freeze the selected image, exact runtime,
   source/recipe, settings, limitations and recovery instructions before access
   ends. Hardware-specific optimization remains optional and separately named.

General termini/preparation issues and default scheduler-guard forwarding remain
deferred as previously agreed. This phase uses explicit fixture configuration;
it makes no force-field, titration-interval or PB/MC-accuracy compromise.

## Files, functions and security boundaries

| File | Place in the workflow |
|---|---|
| `prepare_arm64_build.py` | Guard repository; copy tracked scientific/build sources plus explicit new gates; omit inherited ELF/ignored/untracked payloads; pin local checked base to the same remote execution path. `--portable-seed` freezes a derivation seed, not a portable image. |
| `prepare_portable_candidate.py` | Verify immutable seed and generic solver provenance; derive a fresh context, add declared runtime, select portable metadata and regenerate manifests/recipe hashes. Reject wrong/mixed targets and changed bytes. |
| `slurm/build-portable-arm64.slurm` | Compile matched source with `-tp=px`; capture compiler/runtime provenance; derive context and invoke existing rootfs driver; gate finished image with native smoke/unit and tight PBMC comparison. |
| `arm64/install-portable-delphi.py` | During disposable-rootfs `%post` only, verify hashes/AArch64 headers and target declaration, install generic runtime and record provenance. |
| `arm64/build-inside.sh` / `validate-arm64.sh` | Portable branch rebuilds all owned native trees with baseline flags and checks declared targets. Reference branch remains separate. No original SIF is overwritten. |
| `prepare_hewl_performance.py --overnight` | Freeze allowlisted RT/longer-MD launchers and scientific text with hashes; no submission. |
| `tests/arm64/hewl_overnight.py` | `rt` performs the seven-cycle gate; `continuation` clones and rebinds fixture-owned paths for a new allocation; `long_md` measures fixed-input repeats; all use independent acceptance. |
| `slurm/hewl-overnight-rt.slurm` / `hewl-overnight-md.slurm` | Bounded scheduler execution, per-job project temporary paths, immutable inputs and explicit status/log retention. |
| `run_hewl_overnight_x86.sh` | Sequential matched x86 measurements, physical-core affinity and persistent status; launched through bounded detached timeout. |
| `tests/check_arm64_portable_context.py` | Inert local fixtures test valid immutable derivation and reject changed source/runtime, specialized targets and mixed flags. No test payload is executed or uploaded. |

Source-only uploads contain no Git authentication state or inherited ELF.
The official checksum-pinned GROMACS archive and selected scientific reference
data are explicit build inputs. Compiled portable runtime is created remotely,
added explicitly to the derived build manifest and kept outside Git. Only code,
documentation and compact receipts/audits are selected for version control.

Frozen inputs:

```text
Overnight source archive: 06ab5e197a83984319e1783e461542b41ae8b97ea2040649a2a036fa7a2a3b99
Portable seed archive: ec7148f2ee65db667f31bf8204b4ef20c7e8386491ec55ee01744db7cf9405ff
Portable seed manifest: 0d77558f31f2cc476511384f32dd49b6a3a6a3f66aaaaead45cb46d2ce6eb07d
```

The portable seed has 3362 regular files, no inherited ELF and no Git directory.
An off-cluster copy is at `../artifacts/arm64/CpHMD-portable-seed-20261028.tar.gz`.
Contexts record the current commit plus explicit dirty-tree provenance; later
committing these changes does not retroactively alter the running inputs.
