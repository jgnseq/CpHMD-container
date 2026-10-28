# Deferred CpHMD preparation issues and ARM priorities

User steering, 27 October 2026: ARM access ends **31 October 2026**. Prioritize
a usable ordinary-user ARM image, native scientific checks and exported evidence.
Document general CpHMD/preparation issues; do not repair the canonical workflow
or force-field parameterization during this sprint unless they block ARM work.
No GitHub issue has been created by the agent. The text below is ready to paste.

## Deferred: Amber terminal preparation contract

**Suggested GitHub title:** Make Amber CpHMD terminal preparation explicit and validate it with grompp

**Suggested issue body:**

During HEWL preparation from PDB 4LZT with Amber14SBpH/TIP3P and GROMACS 2026.3,
we found an ambiguity between prefabricated terminal RTP blocks, terminal TDB
patches and the hydrogen database.

For HEWL's LY3-1 / LEU-129 ends:

- The current live menus offer N-terminal `CpH_NH3+` at index 3 and C-terminal
  `None` at index 5 / `CpH0-` at index 4. Numeric answers alone are not a safe
  preparation contract.
- With C-terminal `None`, the residue maps to the existing `CLEU` RTP block.
  That block already contains the charged carboxyl group and four CpHMD dummy
  hydrogens, but the supplied CLEU HDB has six construction rules and omits
  HC11/HC12/HC21/HC22. pdb2gmx with `-ignh` fails with four missing atoms.
- Choosing `CpH0-` in addition to the existing CLEU block constructs all 2,004
  atoms and passes a simple site/charge check, but miswires terminal bonds.
  `grompp -maxwarn 0` then reports 16 missing angle/proper-dihedral types. It
  must not be accepted merely because pdb2gmx returned success.

For the isolated validation fixture only, a prototype copied the four missing
hydrogen construction rules from the supplied CpH0- TDB into the *copied* CLEU
HDB and selected `None`, retaining the complete CLEU RTP. This passed x86
preprocessing with no warnings and kept physical parameter files unchanged.
This is investigation evidence, not a merged/general force-field fix. It needs
expert review and broader residue/terminal coverage before adoption.

The same isolated supplement subsequently passed native ARM topology
verification in job 2148669, including all 21 sites, matching parsed x86/ARM
topologies and preprocessing with `-maxwarn 0`. This still does not establish
general terminal coverage or PB/MC/MD scientific equivalence.

Proposed follow-up:

1. Define which terminal construction route is supported for each Amber
   residue class; avoid applying an existing terminal RTP and a second TDB.
2. Reconcile RTP/HDB/TDB atom construction and audit other terminal residues.
3. Select terminal states by name and verify the actual resulting RTP/atom
   graph; do not reuse unchecked numeric answers.
4. Add topology/site/ST-charge validation and `grompp -maxwarn 0` to a small
   preparation regression. Include independent terminal and side-chain sites
   on the same residue (e.g. N-terminal Lys).
5. Preserve reproduction inputs, logs and original file hashes; do not hide
   missing parameters with `-missing` or increased `-maxwarn`.

Evidence: `docs/aarch64/evidence/2026-10-27/hewl-topology/`; source input
`tests/fixtures/hewl-4lzt/source/4LZT.pdb`, SHA-256
`eec47d81860d9da162f3f8151126af361aba4d4c8055f686dd4cae9d29991941`.
The uncommitted `tests/arm64/*hewl*`, terminal-menu and CLEU HDB tools are
provisional validation/investigation code. Canonical `analysis/prepare-pdb.sh`
and `FFs/Amber14SBpH.ff/` have not been changed.

## Immediate ARM blocker: image runtime permissions

Job 2148556 exposed a separate delivery problem: the compiled image from build
2147983 passed embedded `%test` as fakeroot, but ordinary-user execution fails
with `bash: /analysis/prepare-pdb.sh: Permission denied` (exit 126).

The ARM build copies project-backed source with preserved modes/ACLs; runtime
access must therefore be normalized inside the image and checked independently
of root/fakeroot. This is in sprint scope because it blocks ordinary HPC use.
The original SIF and failed job remain preserved. Permission-repair job
`2148618` completed `0:0` in 27 seconds, with byte-identical runtime payloads
and passing ordinary-user dependency/PETIT/fixgro/MD/PLUMED checks. Its derived
SIF SHA-256 is `d153f31722e76f167080485942074633ce9e3d7abc51dfa97827f790947880ba`.

Acceptance: native ordinary-user UID, accessible application/data paths,
dependency/helper/PETIT/MD checks, followed by the HEWL native preparation gate.
Future full builds must repeat the ordinary-user check after leaving fakeroot.

## Deferred minor issue: preparation/submission status wording

**Suggested title:** Distinguish context preparation from scheduler submission in CLI output

**Issue text:** `prepare_arm64_build.py` prints “No job submitted” even when its
caller was invoked with `--submit` and submits immediately afterwards. Prefix
messages by stage and print an explicit submitted job ID after sbatch. Preserve
the useful separation between preparation and submission, but avoid suggesting
the overall operation failed to submit. No behavior change is needed during
the ARM sprint; the live queue/accounting remain authoritative.

## Deferred runtime policy: unrestricted initial grompp warning allowance

**Suggested title:** Replace the unconditional initial grompp maxwarn allowance with a reviewed policy

**Issue text:** `make_auxiliary_files` in `CpHMD/scripts/functions.sh` currently
passes `-maxwarn 1000` to its initial grompp. The HEWL preparation diagnostic
used `-maxwarn 0`, so missing parameters were caught before simulation. Audit
the controller's warning policy separately: distinguish explicitly reviewed
benign warnings from scientific/configuration problems, preserve diagnostics,
and add a failure regression before changing existing workflows. This issue is
recorded for later review; the canonical controller is unchanged in this step.
The native coupled-cycle audit also confirms that `run_dynamics` uses the same
`-maxwarn 1000` allowance for relaxation/effective preprocessing. Include all
preprocessing stages when designing the later reviewed warning policy.

## Deferred: distinguish controller restart from full MD checkpoint continuation

**Suggested title:** Define and validate the complete GROMACS state retained across CpHMD scheduler boundaries

**Suggested issue body:** The native HEWL integration test validates finalized
GRO/TOP/RT continuation. The controller checkpoints coordinates/topology and RT
templates, then builds new TPRs on continuation. It does not preserve/restore a
GROMACS CPT through the restart contract, so complete integrator/thermostat/
barostat state and exact binary coordinate/velocity precision are not restored.
This is not evidence that the intended CpHMD algorithm is invalid; define which
state transitions are intentional at PB/MC/relaxation boundaries and which should
be continuous across scheduler boundaries. Document that distinction, then test
an uninterrupted run against a split run with the intended statistical/state
invariants. Do not promise bitwise MD continuation from a GRO/TOP restart.
This general policy question remains deferred during the ARM sprint.

## Deferred: remove inherited compiled payloads from source version control

**Suggested title:** Separate legacy executable/library build artifacts from versioned scientific source

**Suggested issue body:** The 27 October 2026 repository review found 50 existing
ELF files (scientific utilities and PLUMED objects/libraries), plus a historical
tutorial archive and large shared library. None was added by the PB/MC milestone
commit `5e20356`. They are not classified as malware, but complicate platform
portability, provenance and review. Plan a source/build/download policy with
license/provenance records and appropriate release artifacts; remove generated
payloads in a separate reviewed change without silently rewriting shared history.
The new local repository guard rejects new/modified payloads while allowing only
byte-identical inherited files from the recorded baseline. SIFs, native result
archives and trajectories remain outside Git.

## Deferred: changing net charge in the CpHMD PME protocol

**Suggested title:** Document and validate the electrostatic treatment of net-charge changes during CpHMD

**Suggested issue body:** The native HEWL pH-6 integration gate samples protein
charges +9/+10/+7/+8 e while the original explicit ions contribute -9 e. The
resulting MD systems include total charges 0/+1/-2/-1 e. GROMACS correctly emits
charged-system Ewald/PME warnings; the existing controller's `-maxwarn 1000`
allows the calculation. The ARM port's dictionary/state/MD/restart checks pass,
but do not establish physical accuracy of this charge-changing protocol.

Document the intended treatment of the PME neutralizing background, finite-size
and electrostatic free-energy effects and any accepted charge-compensation
strategy. Review this against the chosen stochastic-titration method before
changing ions or charges: automatically adding counterions per cycle would be
a scientific-method change, not a routine warning fix. Define appropriate
validation/controls for pKa/ensemble claims and a reviewed preprocessing-warning
policy. Preserve the observed warnings and distinguish native execution success
from physical-method acceptance. Evidence is under
`docs/aarch64/evidence/2026-10-27/hewl-cycle/charge-policy-observation.json` and
`observed-charge-warnings.txt`. No method/force-field change is included in the
ARM sprint.

## Deferred: scheduler walltime guard is lost through cleanenv

**Suggested title:** Explicitly forward the scheduler's computed cycle-boundary guard into cleanenv containers

**Suggested issue body:** Native generated-wrapper testing on Deucalion shows
that `CPHMD_MAX_SECONDS_OVERRIDE=1` prints a 1-second host guard, but the actual
CpHMD process records `CPHMD_MAX_SECONDS=0`. The generator exports the computed
guard and `CPHMD_WALL_START_EPOCH` only on the host, then uses `exec --cleanenv`
without explicitly forwarding them. CpHMD consequently defaults to a disabled
cycle-boundary guard. This is a general scheduler/environment contract defect,
not an ARM solver or MD failure; do not infer walltime safety from a completed
short simulation.

The separate native explicit-configuration case uses the supported scheduler
array `CPHMD_CONTAINER_ENV+=("CPHMD_MAX_SECONDS=1")`, without changing the
canonical generator, and does reach controller code 10 and a bounded real
successor. This is a test workaround, not a repair of dynamic guard calculation.

Follow-up: explicitly pass the computed guard and start epoch across the
container boundary while retaining cleanenv; define precedence against user
overrides; test the real runtime environment, cycle-boundary finalization,
automatic successor and failure behavior. Include a small real-runtime or
faithful cleanenv regression so an inherited host variable cannot mask the bug.
Keep actual Slurm limits, worst-case cycle time and sync buffer in the policy.
Evidence and exact reproduction are in `HEWL_BATCH_2026-10-27.md` and
`evidence/2026-10-27/hewl-batch/`. The canonical generator remains unchanged
during the ARM sprint as requested; the default guard contract remains REVIEW.

## Deferred: batch-container locale warning

**Suggested title:** Make the generated batch environment select an installed and reproducible locale

**Suggested issue body:** Native generated-wrapper logs include
`setlocale: LC_ALL: cannot change locale (en_GB.UTF-8)`. The standalone cycle
fixture explicitly selected C, whereas the generated wrapper enters through
`bash -lc`; the origin of the unavailable locale (image environment or startup
configuration) has not been attributed. Preserve the warning, inspect the
installed locales and startup environment, and consistently select a supported
locale for reproducible text processing. The native scientific/file/status
checks passed despite this warning; it was not the cause of the deliberate
42/43 failures. Do not change the frozen evidence or canonical image/generator
during this ARM validation step.

## Deferred: direct USER.pbp solver-parameter overrides

**Suggested title:** Verify effective DelPhi parameters when applying USER.pbp overrides

**Issue text:** A fixed-coordinate validation control exported `maxc=0.0001`
and `linit=1000` from `USER.pbp`, but generated `.prm` files retained
`maxc=0.01` and coarse `linit=100`. `delphiT` sources the override, while
`gen_files.awk` independently parses `DELPHI.pbp`. Audit and document this
contract, including the main controller's own working-file rewrite and the
hardcoded focus/model iteration limits. Add a test of actual generated inputs
before changing canonical behavior. The ARM fixture now edits only its copied
`DELPHI.pbp` and checks every generated `.prm`; canonical drivers are unchanged.
The invalid first control is preserved and excluded from convergence conclusions.

## Deferred: effective convergence and fixed focus/model iteration caps

**Suggested title:** Expose focus/model PB iteration limits and audit achieved convergence

**Issue text:** `gen_files.awk` hardcodes linit=500 for focus/model solves while
coarse linit comes from DELPHI.pbp. In the HEWL convergence control, maxc=0.0001
and coarse linit=1000 improved x86/ARM agreement, but 162/270 x86 and 161/270 ARM
solves hit the focus/model cap with last printed max change above the requested
tolerance (largest 0.00048828125). Audit precision/stopping behavior and make
limits explicit before using a requested maxc as proof of achieved convergence.
Preserve solver diagnostics and distinguish numerical architecture agreement
from absolute physical convergence. No canonical solver/driver change is made
in this ARM sprint.

## ARM delivery note: architecture/dependency smoke is insufficient for DelPhi

Job 2150284 passed prior ELF/dependency checks but the inherited DelPhi 6.1
solver SIGILLed during a real calculation. The recovered matching x86 source
is DelPhi 5, and its A64FX rebuild completes PB/MC. Derived-image job 2150839
requires ordinary-user runtime smoke plus complete 21-site PB/MC before exporting
an experimental candidate. Future full-build/release acceptance must exercise
DelPhi itself and inspect its version/target, not infer correctness from PETIT
or water MD smoke alone. Numerical regression screens remain separate from
convergence and MC sampling uncertainty; exact bitwise identity is not a
scientific requirement.

## Priorities before 31 October (updated)

1. Resolve ordinary-user ARM runtime access and retain a verified usable SIF.
2. Run native topology/PBMC/CpHMD/RT/restart gates on frozen inputs, using only
   explicitly recorded fixture workarounds where necessary.
3. Record bounded CPU performance only after scientific gates pass.
4. Export images, source snapshots, scripts, logs, inputs and results off
   Deucalion before access ends. Confirm copies against hashes.
5. Generalize preparation safeguards, terminal fixes and broader force-field
   testing after the ARM evidence is secured.

## Near term: finalize a reproducible x86 GROMACS 2026.3 container

**Suggested title:** Build and validate the finalized x86 GROMACS 2026.3 reference container

**Suggested issue body:** A finalized, reproducibly built x86 GROMACS 2026.3
container is still required. The current comparison uses an experimental rc3
artifact from `tests/gpu-output-contract/build/artifacts/`, image SHA256
`195139e9bf25cd6cf24b13fae50e1c7cb5b504688d35ede1f24581940684bd0a`.
Its CPU launcher reports 2026.3/AVX2_256 and was useful as an explicitly
provisional mini05 performance reference. This does not establish release
readiness or replace the requested reproducible build.

Freeze the source/definition, compiler/library versions and build options;
produce named CPU and any intended GPU variants with clear launchers; verify
ordinary-user runtime, GROMACS/PLUMED, PETIT, fixed PB/MC and coupled/RT/restart
acceptance. Repeat component/whole-cycle performance on the same x86 machine
and frozen inputs before replacing a reference. Record license/redistribution
requirements and complete image/source hashes.

Preserve the original optimized x86 DelPhi binary unchanged, SHA256
`973e9b99e893ffdf76f78a941920417bb7935e2507259e7f4e7acbeda7068cc6`.
Its historical compiler build has been difficult to reproduce. Any rebuilt
solver must be a separate, named candidate with numerical/convergence and
same-hardware timing comparisons; do not overwrite the baseline or infer
performance equivalence from a successful compile. Benchmark evidence and
limitations are in `docs/aarch64/HEWL_PERFORMANCE_2026-10-28.md`.

## ARM performance follow-up: process startup and component costs

**Suggested title:** Validate lower-startup-cost ARM MD settings and preserve matched DelPhi performance controls

**Suggested issue body:** Bounded A64FX HEWL measurements show approximately
45 seconds outside GROMACS's reported integration time per process at 4–16
threads, and 61 seconds at 24–48. This dominates short relaxation/effective MD
cycles. The 2026.3 source maps reproducible FFT setup to FFTW_ESTIMATE; a bounded
default/reproducible startup diagnostic passed as job 2160496: zero-step time
fell from 45.49 to 16.28 seconds, and 5-ps command time from 101.61 to 72.77
seconds with nearly unchanged integration time and passing health checks.
About 16 seconds of additional process overhead remain unattributed. Treat any
resulting configuration as an experiment until coupled/RT/continuation gates
and a longer representative workload pass. Keep the original candidate and
baseline results unchanged, and separate startup, integration and retained-I/O
costs. Do not silently change the scientific protocol or promote a single
short-run timing optimum to a general production default.

The original x86 DelPhi takes less serial time on mini05 than the NVFORTRAN 25.1
A64FX rebuild: representative model ratios ARM/x86 are about 1.3, and protein
coarse/focus ratios about 2.5–2.8. One coarse solve has different last printed
iteration counts. Preserve parameter decks, structures, residuals, cap status,
energy output and executable/runtime hashes beside timings. Different CPU
hardware, clocks, storage and compilers prevent an ISA-only or compiler-only
attribution. Compiler experiments need same-hardware controls and unchanged
scientific acceptance thresholds; do not substitute fast-math or loosen PB
convergence to obtain a favorable timing. See the performance report and compact
evidence under `docs/aarch64/evidence/2026-10-28/hewl-performance/`.

## After the ARM deadline: tune the x86 container's performance

**Suggested title:** Profile and optimize the finalized x86 container while preserving the historical DelPhi baseline

**Suggested issue body:** After producing the reproducible x86 GROMACS 2026.3
reference, measure longer fixed-input MD and complete CpHMD runs on mini05.
Benchmark individual components and whole-cycle cost before choosing targets.
Separate startup, steady integration, PB preparation/solves, MC and output costs;
retain both matched-core comparisons and practical throughput/resource costs.

Evaluate GROMACS rank/thread layout, affinity, FFT planning/backend and supported
SIMD variants; test CPU-specific compiler builds as explicitly machine-targeted
variants alongside a portable baseline. Test PETIT/helper compiler options only
where their absolute contribution justifies the effort. Benchmark PLUMED with
a representative observable if that path is used; it was inactive in the HEWL
performance screen. Changes to the MD/titration interval, PB accuracy or MC
sampling length must not be presented as compiler/runtime optimizations.

Keep the original x86 DelPhi executable and runtime as an immutable performance
and numerical reference. Compare any solver rebuild on the same x86 hardware
with identical parameter decks, coordinates, iteration/residual records and
unchanged scientific acceptance criteria. Preserve raw timings, variation,
compiler diagnostics, exact flags and source/executable hashes. An optimization
is accepted only when representative full-workflow performance improves and
scientific/continuation checks pass; a faster isolated component alone is
insufficient. This work can continue after Deucalion ARM access ends.
