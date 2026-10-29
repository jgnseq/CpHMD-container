#!/bin/bash
#SBATCH --job-name=cphmd-portable-gate
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# Portable-image follow-up after build 2160578: all -> RT -> fresh-allocation
# continuation. Submit md separately with --array=1,3,5%2, --exclusive,
# --cpus-per-task=48 and --time=04:00:00. Those cases repeat 50/200 ps at
# 4/16/48 threads with -reprod, matched to the accepted reference observations.
# For a slower case use md-single with --array=0-3%2 and the same MD allocation
# overrides: each task runs one unchanged four-thread observation. All four
# indices are required for the final two-repeat/duration case acceptance.
# Every mode uses a fresh output path and records its actual status. No retry
# or resubmission occurs; all persistent and simulation temporary files stay
# in the project. Sources and the starting snapshot are mounted read-only.
set -Eeuo pipefail
root="$(realpath "${1:?Supply new portable-validation project root}")"
mode="${2:?Use all, rt, continue, md or md-single}"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/portable-validation.*) ;; *) exit 2 ;; esac
case "$mode" in all|rt|continue) label="$mode" ;; md|md-single) label="$mode-${SLURM_ARRAY_TASK_ID:?Array required}" ;; *) exit 2 ;; esac
if [[ $mode == md ]]; then
    case "$SLURM_ARRAY_TASK_ID" in 1|3|5) ;; *) exit 2 ;; esac
fi
if [[ $mode == md-single ]]; then
    case "$SLURM_ARRAY_TASK_ID" in 0|1|2|3) ;; *) exit 2 ;; esac
fi
mkdir "$root/tmp-$label"
export TMPDIR="$root/tmp-$label" SINGULARITY_TMPDIR="$root/tmp-$label" APPTAINER_TMPDIR="$root/tmp-$label"
exec > >(tee "$root/$label-${SLURM_JOB_ID}.log") 2>&1
# Retain failures independently of the submitting terminal and Slurm accounting.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/$label-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
task=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
base="$task/validation/hewl-4lzt"
build="$task/portable.20261028.MZWHAj"
image="$build/candidate/CpHMD-arm64.sif"
input="$base/solution.P4IU4M/solution/snapshot"
fixed="$base/cycle.all.wtFLwM/coupled/captures/cycle-1"
[[ $(cat "$build/result.txt") == PORTABLE_TARGET_NATIVE_GATES_PASSED_NON_SVE_EXECUTION_PENDING ]]
echo "dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/$label-source-verification.log")
(cd "$input" && sha256sum -c manifest.sha256 > "$root/$label-snapshot-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-$label.slurm"
hostname > "$root/$label-hostname.txt"
lscpu > "$root/$label-lscpu.txt"
args=("$mode" /source /input "/out/$mode" --image-scope portable-armv8-a)
if [[ $mode == continue ]]; then args+=(--previous /out/rt); fi
if [[ $mode == md ]]; then
    args=(md /source /input "/out/md-case-$SLURM_ARRAY_TASK_ID" --image-scope portable-armv8-a
          --tpr /fixed/effective.tpr --case "$SLURM_ARRAY_TASK_ID")
fi
if [[ $mode == md-single ]]; then
    args=(md /source /input "/out/md-single-$SLURM_ARRAY_TASK_ID" --image-scope portable-armv8-a
          --tpr /fixed/effective.tpr --case 1 --observation "$SLURM_ARRAY_TASK_ID")
fi
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$fixed:/fixed:ro,$root:/out" \
    --pwd /out --env "TMPDIR=/out/tmp-$label,LC_ALL=C,OMP_NUM_THREADS=8,GMX_MAXBACKUP=-1" "$image" \
    python3 /source/tests/arm64/hewl_overnight.py "${args[@]}"
echo PORTABLE_NATIVE_FOLLOWUP_MODE_PASSED
