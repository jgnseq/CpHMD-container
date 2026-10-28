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
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution/snapshot
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/audit-source-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-audit.sh"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$root:/out,$root:$root" \
    --pwd /out --env TMPDIR=/out/tmp "$image" \
    python3 /source/tests/arm64/hewl_batch.py check /source /input /out
