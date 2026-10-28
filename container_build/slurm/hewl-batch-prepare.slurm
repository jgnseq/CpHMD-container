#!/bin/bash
#SBATCH --job-name=cphmd-batch-prepare
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
# Generate real scheduler cases after native Python fixture preparation. This
# setup job never submits simulation jobs; each generated script is reviewable.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new project batch validation directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/batch.*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || exit 2
mkdir "$root/tmp"
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
exec > >(tee "$root/prepare-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/prepare-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution/snapshot
prior=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/cycle.rt.XNDQa2/coupled
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256 > "$root/source-verification.log")
cp "${BASH_SOURCE[0]}" "$root/executed-prepare.sh"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$prior:/prior:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp "$image" \
    python3 /source/tests/arm64/hewl_batch.py prepare /source /input /out \
        --host-root "$root" --image "$image" --prior /prior
for case_name in default-guard explicit-guard md-failure pb-failure invalid-checkpoint; do
    bash "$root/source/template/slurm/generate_CpHMD_slurm.sh" \
        "$root/configs/$case_name.settings" --no-submit > "$root/generation-$case_name.log" 2>&1
    bash -n "$root/runs/$case_name/slurm_files/HEWL-$case_name.slurm"
done
find "$root/runs" -name '*.slurm' -type f -exec sha256sum {} + > "$root/generated-scripts.sha256"
echo 'BATCH_FIXTURES_PREPARED: simulation jobs must be submitted separately.'
