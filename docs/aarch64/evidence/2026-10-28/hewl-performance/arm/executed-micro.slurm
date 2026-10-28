#!/bin/bash
#SBATCH --job-name=cphmd-solver-performance
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
# Serial component comparison against the original x86 DelPhi/PETIT binaries.
# Input decks, scientific data and source are frozen; output/temp stay in project.
set -Eeuo pipefail
root="$(realpath "${1:?Supply the performance project root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/performance.*) ;; *) exit 2 ;; esac
mkdir "$root/tmp-micro-shell"
export TMPDIR="$root/tmp-micro-shell" SINGULARITY_TMPDIR="$root/tmp-micro-shell" APPTAINER_TMPDIR="$root/tmp-micro-shell"
exec > >(tee "$root/micro-shell-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/micro-shell-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source-paired" && sha256sum -c source.sha256 > "$root/micro-shell-source-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-micro.slurm"
hostname > "$root/micro-hostname.txt"
lscpu > "$root/micro-lscpu.txt"
singularity exec --cleanenv --bind "$root/source-paired:/source:ro,$root/micro-input-paired:/micro-input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp-micro-shell,LC_ALL=C "$image" bash -c \
    'sha256sum /Delphi/delphi_pgf90 /programs/petit1.6.1/petit; ldd /Delphi/delphi_pgf90' > "$root/micro-runtime.txt"
singularity exec --cleanenv --bind "$root/source-paired:/source:ro,$root/micro-input-paired:/micro-input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp-micro-shell,LC_ALL=C "$image" bash -c \
    'cpu=$(awk "/Cpus_allowed_list/ {print \$2}" /proc/self/status | cut -d, -f1 | cut -d- -f1); exec taskset -c "$cpu" bash /source/tests/arm64/run_hewl_solver_performance.sh /micro-input /out/micro-shell'
singularity exec --cleanenv --bind "$root/source-paired:/source:ro,$root/micro-input-paired:/micro-input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp-micro-shell,LC_ALL=C "$image" \
    python3 /source/tests/arm64/hewl_solver_performance.py /micro-input /out/micro-shell --audit-shell
echo HEWL_SOLVER_PERFORMANCE_PASSED
