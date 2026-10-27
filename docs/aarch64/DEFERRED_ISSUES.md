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
