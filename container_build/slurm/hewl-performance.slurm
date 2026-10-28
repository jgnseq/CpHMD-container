#!/bin/bash
#SBATCH --job-name=cphmd-hewl-performance
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --exclusive
#SBATCH --mem=28G
#SBATCH --time=01:30:00
# Native timing experiment: one exclusive A64FX node per mode, no successors.
# All mutable paths and temporary files remain in the authorized project.
# The read-only image, snapshot and fixed production TPR are checksum pinned.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a fresh project performance root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/performance.*) ;; *) exit 2 ;; esac
mode="${2:?Use md or coupled}"
case "$mode" in md|coupled) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 && ${SLURM_CPUS_PER_TASK:-0} == 48 ]] || exit 2
mkdir "$root/tmp-$mode"
export TMPDIR="$root/tmp-$mode" SINGULARITY_TMPDIR="$root/tmp-$mode" APPTAINER_TMPDIR="$root/tmp-$mode"
exec > >(tee "$root/$mode-${SLURM_JOB_ID}.log") 2>&1
# Record the true job outcome even when a pin check, engine or auditor fails.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/$mode-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
image="$base/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif"
input="$base/solution.P4IU4M/solution/snapshot"
fixed="$base/cycle.all.wtFLwM/coupled/captures/cycle-1"
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
echo "7276106632db360dadc02f3cc0075006ee9de10d029e143a590c2a1e02113e48  $fixed/effective.tpr" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/$mode-source-verification.log")
(cd "$input" && sha256sum -c manifest.sha256 > "$root/$mode-snapshot-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-$mode.slurm"
hostname > "$root/$mode-hostname.txt"
lscpu > "$root/$mode-lscpu.txt"
date -Is
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$fixed:/fixed:ro,$root:/out" \
    --pwd /out --env "TMPDIR=/out/tmp-$mode,LC_ALL=C,GMX_MAXBACKUP=-1" "$image" \
    python3 /source/tests/arm64/hewl_performance.py "$mode" /source /input "/out/$mode" --tpr /fixed/effective.tpr
echo HEWL_PERFORMANCE_MODE_PASSED
