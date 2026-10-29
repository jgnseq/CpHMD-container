#!/bin/bash
#SBATCH --job-name=cphmd-batch-audit-dispatch
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
# Submit this with afterany dependencies on all five initial generated cases.
# Expected failure cases must not block the independent auditor. The explicit
# guard case may submit one successor after its initial job: read that real ID
# from its completed log and give the auditor an afterany dependency on it.
# This removes the workstation from the completion path, without polling or
# retries. A successful dispatcher means AUDIT SUBMITTED, never science passed.
set -Eeuo pipefail
root="$(realpath "${1:?Supply prepared batch root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/batch.*) ;; *) exit 2 ;; esac
export TMPDIR="$root/tmp"
exec > >(tee "$root/audit-dispatch-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/audit-dispatch-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
profile="$(cat "$root/image-profile.txt")"
case "$profile" in a64fx|portable) ;; *) exit 2 ;; esac
(cd "$root/source" && sha256sum --quiet -c source.sha256)
cp "${BASH_SOURCE[0]}" "$root/executed-audit-dispatch.slurm"
# The initial explicit job is terminal before this dispatcher runs, so any
# actual successor has been submitted and logged already. Missing successor
# evidence is left for the scientific auditor to reject, rather than waiting
# forever. Multiple successors are an orchestration error and stop dispatch.
child="$(python3 - "$root" <<'PY'
from pathlib import Path
import re,sys
folder=Path(sys.argv[1])/'runs/explicit-guard/slurm_files'
ids=set()
for path in folder.glob('HEWL-*.log'):
    ids.update(re.findall(r'Submitted batch job (\d+)',path.read_text()))
assert len(ids)<=1, 'More than one successor: inspect the bounded wrapper contract'
print(next(iter(ids)) if ids else '')
PY
)"
dependencies=()
if [[ -n $child ]]; then
    [[ $child =~ ^[0-9]+$ ]] || exit 2
    dependencies=(--dependency="afterany:$child")
fi
job="$(sbatch --parsable "${dependencies[@]}" --output="$root/slurm-%j.log" \
    "$root/source/container_build/slurm/hewl-batch-audit.slurm" "$root" "$profile")"
printf 'audit\t%s\n' "$job" | tee "$root/audit-submission.tsv"
echo INDEPENDENT_AUDIT_SUBMITTED_NOT_YET_ACCEPTED
