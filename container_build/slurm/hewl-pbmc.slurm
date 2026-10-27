#!/bin/bash
#SBATCH --job-name=cphmd-hewl-pbmc
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
# Native fixed-coordinate PB/MC. All data and temporary solver grids remain
# under the project. No automatic continuation or resubmission.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new project PBMC validation directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/pbmc.*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || exit 2
mkdir "$root/tmp"
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
exec > >(tee "$root/pbmc-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution
# Default to the repaired, ordinary-user execution-validated candidate. Passing
# an optional solver runtime below is only for explicit component experiments.
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif
echo "1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d  $image" | sha256sum -c -
(cd "$root/source" && sha256sum -c source.sha256)
hostname
date -Is
cp "${BASH_SOURCE[0]}" "$root/executed-slurm.sh"
binds="$root/source:/source:ro,$input:/input:ro,$root:/out"
environment=TMPDIR=/out/tmp
profile="${3:-standard}"
# A separately built solver can be screened before assembling another SIF.
# Verify its recorded runtime hashes and bind it read-only. The rest of the
# image, science drivers, parameters and coordinates remain exactly as before.
if [[ -n ${2:-} ]]; then
    runtime="$(realpath "$2")"
    case "$runtime" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/delphi-*/runtime) ;; *) exit 2 ;; esac
    sha256sum -c "$runtime/../runtime.sha256"
    binds+=",$runtime:/candidate-runtime:ro,$runtime/delphi_pgf90:/Delphi/delphi_pgf90:ro"
    environment+=",LD_LIBRARY_PATH=/candidate-runtime:/opt/nvhpc/lib:/opt/plumed/lib:/opt/plumed/lib64"
    printf '%s\n' "$runtime" > "$root/solver-runtime-override.txt"
fi
singularity exec --cleanenv --bind "$binds" \
    --pwd /out --env "$environment" "$image" \
    bash /source/tests/arm64/run_hewl_pbmc.sh /source /input/snapshot /input/npt.tpr /out/pbmc "$profile"
test "$(cat "$root/pbmc/result.txt")" = PBMC_EXECUTION_PASSED
