#!/bin/bash
#SBATCH --job-name=cphmd-overnight-rt
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# Submitted as independent rt and afterok-dependent continuation allocations.
# All inputs are frozen in the project; closing the workstation has no effect.
set -Eeuo pipefail
root="$(realpath "${1:?Supply overnight project root}")"
mode="${2:?Use rt or continue}"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/overnight.*) ;; *) exit 2 ;; esac
case "$mode" in rt|continue) ;; *) exit 2 ;; esac
mkdir "$root/tmp-$mode"
export TMPDIR="$root/tmp-$mode" SINGULARITY_TMPDIR="$root/tmp-$mode" APPTAINER_TMPDIR="$root/tmp-$mode"
exec > >(tee "$root/$mode-${SLURM_JOB_ID}.log") 2>&1
# Save failure as well as success so tomorrow's audit needs no live terminal.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/$mode-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
image="$base/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif"
input="$base/solution.P4IU4M/solution/snapshot"
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/$mode-source-verification.log")
(cd "$input" && sha256sum -c manifest.sha256 > "$root/$mode-snapshot-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-$mode.slurm"
args=("$mode" /source /input "/out/$mode")
if [[ $mode == continue ]]; then args+=(--previous /out/rt); fi
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$root:/out" \
    --pwd /out --env "TMPDIR=/out/tmp-$mode,LC_ALL=C,OMP_NUM_THREADS=8,GMX_MAXBACKUP=-1" "$image" \
    python3 /source/tests/arm64/hewl_overnight.py "${args[@]}"
echo OVERNIGHT_RT_MODE_PASSED
