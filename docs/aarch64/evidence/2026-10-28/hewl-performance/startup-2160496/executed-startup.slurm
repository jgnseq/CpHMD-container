#!/bin/bash
#SBATCH --job-name=cphmd-hewl-startup
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --exclusive
#SBATCH --mem=8G
#SBATCH --time=00:10:00
# A single follow-up to separate process startup from integration throughput.
# Use the same eight-thread workload and checksum-pinned TPR/SIF; no rebuild.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new startup-probe root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/performance.startup.*) ;; *) exit 2 ;; esac
mkdir "$root/tmp"
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
exec > >(tee "$root/startup-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
image="$base/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif"
input="$base/solution.P4IU4M/solution/snapshot"
fixed="$base/cycle.all.wtFLwM/coupled/captures/cycle-1"
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/source-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-startup.slurm"
hostname > "$root/hostname.txt"
lscpu > "$root/lscpu.txt"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$fixed:/fixed:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp,LC_ALL=C "$image" \
    python3 /source/tests/arm64/hewl_startup_probe.py /input /fixed/effective.tpr /out/startup
echo HEWL_STARTUP_PROBE_PASSED
