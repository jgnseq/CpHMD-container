#!/bin/bash
#SBATCH --job-name=cphmd-hewl-cycle
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
# Ordinary-user coupled CpHMD/RT gate. Every mutable file, including temporary
# solver/MD files, stays under the authorized project. No resubmission logic.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new project cycle validation directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || exit 2
mode="${2:-all}"
case "$mode" in all|rt) ;; *) exit 2 ;; esac
mkdir "$root/tmp"
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
exec > >(tee "$root/cycle-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution/snapshot
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256)
hostname
date -Is
cp "${BASH_SOURCE[0]}" "$root/executed-slurm.sh"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp "$image" \
    bash /source/tests/arm64/run_hewl_cycle.sh /source /input /out/coupled "$mode"
test "$(cat "$root/coupled/result.txt")" = COUPLED_CYCLE_GATE_PASSED
