# Portable ARM64 candidate: acceptance and access-end handover

## Result

The fresh portable-default candidate passed its native build, ordinary-user
smoke, fixed-input PB/MC, coupled HEWL/RT/continuation and candidate-specific
non-SVE execution gates. Recovery completed and the image/archive hashes were
independently rechecked on mini05 on **30 October 2026**. No job from this
pipeline remains pending; no further ARM allocation is required for these gates.

This is an accepted **engineering candidate**, not a production pKa validation,
universal ARM hardware certification or published release. It uses the portable
ARMv8-A/ASIMD profile and the verified generic DelPhi runtime. The explicit
A64FX/SVE reference remains separate. No canonical controller, force field,
titration interval, PB convergence setting or scheduler-generator fix was made
in this finalization step.

| Stage | Result |
|---|---|
| Fresh build 2165989 | `COMPLETED 0:0`, 25m10s; five selected GROMACS suites and ordinary-user dependency/helper/PETIT/MD/PLUMED smoke passed. |
| Native acceptance 2165990 | `COMPLETED 0:0`, 19m27s; embedded source identity, PB/MC and all/RT/continuation gates passed. |
| Recovery 2166011 | `COMPLETED 0:0`, 5m38s; content-verified archive produced. |
| Detached mini05 follow-up | `verification.exit=0`, `pull.exit=0`; archive SHA, exact image SHA and Cortex-A53 non-SVE execution passed. Its timeout process has exited normally. |

The combined receipt is
[`acceptance-summary.json`](evidence/2026-10-30/final-portable-candidate/acceptance-summary.json).
Original native and emulation receipts are preserved alongside it. The native
marker's text `NON_SVE_PENDING` describes that earlier stage; the later
mini05 receipt resolves it. Do not edit the original receipt to imply otherwise.

## Exact deliverable and preservation

```text
Image SHA256:
d4d4278861eb1e9917db8b0ca74b32304fca69674a109f9813574807b85fb5f4

Recovery archive SHA256:
77a4cb39167dc98fe9d9e893de9321ebaff74a3570055e198dfda3c98af26745

Frozen context manifest SHA256:
0e40c2cb38ae22cbda5437dd250d19168c975b31ff1a48e5dfb8da0bb4eadfac
```

The recovery archive is 1,174,273,130 bytes and records **8,313 regular files**.
All **3,360 context members** match its content manifest, including the pinned
GROMACS archive and frozen x86 reference. The accepted SIF is 310,665,216 bytes.
The archive contains the image, full frozen context, recipe/provenance and
native scientific outputs. mini05 separately retains its non-SVE audit/results.

Deucalion candidate:

```text
/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/portable-default.20261029.Q6nWxw/candidate
```

Verified off-cluster copy on mini05:

```text
/home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.default-portable.20261029.Hl8Yxh/image.sif
/home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.default-portable.20261029.Hl8Yxh/candidate/CpHMD-portable-default-validation.tar.gz
```

The complete original source-only snapshot is also preserved on the workstation
outside Git under `artifacts/arm64/portable-default-20261029/inputs/`.
The earlier build/reference/performance/wrapper archives remain independently
verified on mini05; see the [29 October recovery inventory](PORTABLE_ARM64_NIGHT_STATUS_2026-10-29.md).
This handover does not claim the new full SIF/archive has already been downloaded
to the workstation. That optional second off-cluster copy can be fetched later.
The workstation transfer path was exercised, then deliberately interrupted
because of the slow link. A 33,751,040-byte rsync partial remains outside Git;
it is not an accepted local image. No transfer is left running. Repeating the
fetch command resumes it and verifies the completed image before reporting pass.

## Source association without rewriting provenance

The image truthfully retains `source_commit=d6607de...`, `source_dirty=true`:
it was built from the frozen development snapshot. The subsequent reviewed and
pushed packaging commit is **`cebf3a4a017455caef8324d7763e30ec7831b357`**.

A read-only audit compared every repository-sourced context member with that
commit's Git blobs, including files reached through committed directory symlinks.
All **3,353 repository files match byte-for-byte**, with no differences. The
seven external inputs are the pinned GROMACS archive and six frozen scientific
reference files. Rendering the committed definition template with recorded
inputs also reproduces the candidate recipe hash exactly.

This associates the accepted inputs with reviewed code; it does **not** relabel
the image as a clean-commit build. Full excluded-file/build-host reproducibility
is outside the comparison. The exact result and reproducible audit are in
[`committed-input-association.json`](evidence/2026-10-30/final-portable-candidate/committed-input-association.json)
and `committed_input_audit.py` beside it. The audit's `main` compares the context
and recipe; `committed_files` reads immutable blobs; `resolve` handles in-tree
file/directory symlinks. It never changes Git or the image.

## Scientific and portability scope

The native gate independently checked **395 embedded controller/data files**.
The tight PB/MC comparison covers 21 sites, 69 pseudostates and 4,761 matrix
elements. Maximum intrinsic-pK difference against the frozen x86 reference was
**0.000686** (predeclared limit 0.005); maximum raw interaction difference was
**0.000242568 kBT**. All three MC seeds passed, with maximum site-occupancy
difference **0.000130**. Original tolerances were unchanged.

Two all-site cycles, seven reduced-titration cycles with a real finalized stop/
resume, and reduced cycle 7 → 8 continuation passed. This validates the
controller's GRO/TOP/RT continuation contract, not bitwise GROMACS CPT restart.

The non-SVE gate executed real DelPhi, PETIT, fixgro and water MD/PLUMED under
Cortex-A53 emulation. An actual SVE instruction succeeded under the positive
control and failed with SIGILL under the non-SVE control. The six printed
DelPhi energies and last iteration counts matched native results; PETIT means
and final states also matched. This is execution coverage, not a benchmark.

Four of those six PB decks still hit the existing 500-iteration cap without
meeting their requested maximum residual. That limitation is preserved in the
audit and [deferred issues](DEFERRED_ISSUES.md); numerical agreement must not be
presented as complete convergence or experimental pKa accuracy. Physical
non-SVE ARM hardware and broader force-field/system coverage remain untested.

## Performance and scheduler limits retained

The tested GROMACS, DelPhi, PETIT and fixgro executable hashes match those of
the previously benchmarked portable image. This is recorded in
`benchmark-binary-association.json`; it does not prove every library or runtime
setting is identical. Longer MD measurements remain attributed to that earlier
image and exact hardware/protocol, not falsely labeled as a new timing run.
See the [portable performance report](PORTABLE_ARM64_NIGHT_STATUS_2026-10-29.md)
and [cross-architecture component report](HEWL_PERFORMANCE_2026-10-28.md).

The generated scheduler wrapper was tested with the preceding portable image
and explicit container guard. Its default guard-forwarding defect remains
**REVIEW**, not fixed or accepted by this final candidate's scientific tests.
Use the documented explicit configuration and a production-appropriate budget;
the artificial one-second test value is not a production recommendation.
See [the batch report](HEWL_BATCH_2026-10-27.md).

## Recovery after Deucalion access ends

All queued work has finished. The workstation can shut down. mini05 no longer
has an active validation process; it only needs to be reachable for later
retrieval. The new optional fetch helper uses mini05 alone, retains rsync
partials, verifies pinned image/archive hashes and writes outside Git:

```bash
cd '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/CpHMD-container'
# Full accepted image + source/results archive, about 1.49 GB total.
bash container_build/fetch_accepted_arm64_candidate.sh

# Or fetch just the accepted image, about 311 MB.
bash container_build/fetch_accepted_arm64_candidate.sh --image-only
```

Run either when the workstation can stay on for the transfer. It does not
submit jobs or extract/execute downloaded payloads. The earlier
`shutdown-handover-20261029/resume_recovery.sh` still fetches the older backup set;
the new helper deliberately addresses the accepted candidate separately.
No SSH key, authentication configuration or credential is copied by either.

`fetch_accepted_arm64_candidate.sh` is a host-side delivery helper, outside
the image build and scientific cycle. It requires the mirror's zero statuses,
locks its local destination, resumes explicit files with rsync and checks
reviewed fixed SHA256 values. Its destination is the checkout's sibling
`artifacts/arm64/accepted-portable-20261030/`. No numerical code is changed.

## Remaining actions

Before access ends, record this final evidence in Git using the commands below.
An optional workstation copy provides another independent location; it does
not require Deucalion and is not a prerequisite for finishing ARM allocations.
No duplicate native build is needed solely to change provenance wording.

Follow-up work is already retained in [DEFERRED_ISSUES.md](DEFERRED_ISSUES.md):
default guard forwarding, topology/termini preparation, PB convergence policy,
full MD state restart, the finalized x86 2026.3 build and both-platform tuning.
Physical other-ARM testing and longer scientific validation can continue after
the cluster deadline. Public release/tagging remains a separate deliberate step.

```bash
cd '/home/jsequeira/Documents/ChatGPT/CpHMD Container — ARM64 & Publication/CpHMD-container'
git status --short --branch
python3 tests/check_repository_safety.py
git diff --check
git add -- \
  container_build/fetch_accepted_arm64_candidate.sh \
  docs/aarch64/PORTABLE_ARM64_ACCEPTANCE_2026-10-30.md \
  docs/aarch64/PORTABLE_DEFAULT_BUILD_2026-10-29.md \
  docs/aarch64/BUILD_AND_VALIDATE.md \
  docs/aarch64/DEVELOPER_GUIDE.md \
  docs/aarch64/evidence/2026-10-30/final-portable-candidate
python3 tests/check_repository_safety.py --staged && \
git diff --cached --check && \
git diff --cached --stat && \
git commit -m 'Record portable ARM64 candidate acceptance and final recovery handover' && \
git push origin codex/arm64-deucalion-20261026
```

The agent did not stage, commit, push, tag or publish. Generated images, archives
and raw simulation payloads stay outside Git. The unrelated pre-existing local
note remains untouched. Security evidence is a pattern/artifact scan with its
documented limits, not a malware or complete-history certification.
