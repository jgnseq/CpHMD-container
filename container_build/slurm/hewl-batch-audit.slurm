#!/bin/bash
#SBATCH --job-name=cphmd-batch-audit
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
# Independently audit completed generated jobs. Expected scientific failures
# remain failures in sacct; this audit evaluates whether containment worked.
# Pass the same optional portable/a64fx profile used for fixture preparation.
set -Eeuo pipefail
root="$(realpath "${1:?Supply the prepared batch validation root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/batch.*) ;; *) exit 2 ;; esac
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
exec > >(tee "$root/audit-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/audit-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
profile="${2:-a64fx}"
task=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
case "$profile" in
    a64fx)
        image="$task/validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif"
        image_sha=1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d ;;
    portable)
        image="$task/portable.20261028.MZWHAj/candidate/CpHMD-arm64.sif"
        image_sha=dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479 ;;
    *) echo 'Use a64fx or portable image profile' >&2; exit 2 ;;
esac
[[ $(cat "$root/image-profile.txt") == "$profile" ]]
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution/snapshot
echo "$image_sha  $image" | sha256sum -c -
sha256sum -c "$root/image-pin.sha256"
(cd "$root/source" && sha256sum -c source.sha256 > "$root/audit-source-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-audit.sh"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$root:/out,$root:$root" \
    --pwd /out --env TMPDIR=/out/tmp "$image" \
    python3 /source/tests/arm64/hewl_batch.py check /source /input /out
