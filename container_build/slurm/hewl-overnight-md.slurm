#!/bin/bash
#SBATCH --job-name=cphmd-overnight-md
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --exclusive
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --array=0-5%2
# Two simultaneous exclusive-node timing cases at most. Each case measures
# 50/200 ps twice for one of 4/16/48 threads and default/-reprod. Walltime and
# job count are bounded; no resubmission, laptop mount or SSH session is needed.
set -Eeuo pipefail
root="$(realpath "${1:?Supply overnight project root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/overnight.*) ;; *) exit 2 ;; esac
case_id="${SLURM_ARRAY_TASK_ID:?Array submission required}"
[[ $case_id =~ ^[0-5]$ ]] || exit 2
mkdir "$root/tmp-md-$case_id"
export TMPDIR="$root/tmp-md-$case_id" SINGULARITY_TMPDIR="$root/tmp-md-$case_id" APPTAINER_TMPDIR="$root/tmp-md-$case_id"
exec > >(tee "$root/md-$case_id-${SLURM_JOB_ID}.log") 2>&1
# Record actual outcomes independently for every array task.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/md-$case_id-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
image="$base/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif"
input="$base/solution.P4IU4M/solution/snapshot"
fixed="$base/cycle.all.wtFLwM/coupled/captures/cycle-1"
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/md-$case_id-source-verification.log")
(cd "$input" && sha256sum -c manifest.sha256 > "$root/md-$case_id-snapshot-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-md-$case_id.slurm"
hostname > "$root/md-$case_id-hostname.txt"
lscpu > "$root/md-$case_id-lscpu.txt"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$fixed:/fixed:ro,$root:/out" \
    --pwd /out --env "TMPDIR=/out/tmp-md-$case_id,LC_ALL=C,GMX_MAXBACKUP=-1" "$image" \
    python3 /source/tests/arm64/hewl_overnight.py md /source /input "/out/md-case-$case_id" \
    --tpr /fixed/effective.tpr --case "$case_id"
echo OVERNIGHT_MD_CASE_PASSED
