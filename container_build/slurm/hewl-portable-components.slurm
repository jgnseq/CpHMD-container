#!/bin/bash
#SBATCH --job-name=cphmd-portable-components
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
# Measure generic DelPhi/PETIT on the same six frozen decks and MC table as
# the accepted x86/A64FX component screen. This uses the identical Bash/date
# engine timer, then an independent scientific-output auditor. Container startup
# and audit are outside component timers. No compilation, resubmission or
# scientific-parameter changes occur here; all output/temp stays project-backed.
set -Eeuo pipefail
root="$(realpath "${1:?Supply portable-validation root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/portable-validation.*) ;; *) exit 2 ;; esac
mkdir "$root/tmp-components"
export TMPDIR="$root/tmp-components" SINGULARITY_TMPDIR="$root/tmp-components" APPTAINER_TMPDIR="$root/tmp-components"
exec > >(tee "$root/components-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/components-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
task=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
image="$task/portable.20261028.MZWHAj/candidate/CpHMD-arm64.sif"
input="$task/validation/hewl-4lzt/performance.20261028.Xj0aHj/micro-input-paired"
echo "dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479  $image" | sha256sum -c -
(cd "$root/source" && sha256sum --quiet -c source.sha256)
(cd "$input" && sha256sum --quiet -c input.sha256)
cp "${BASH_SOURCE[0]}" "$root/executed-components.slurm"
sha256sum "$root/executed-components.slurm" > "$root/executed-components.sha256"
hostname > "$root/components-hostname.txt"
lscpu > "$root/components-lscpu.txt"
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/micro-input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp-components,LC_ALL=C "$image" bash -c \
    'cpu=$(awk "/Cpus_allowed_list/ {print \$2}" /proc/self/status | cut -d, -f1 | cut -d- -f1); exec taskset -c "$cpu" bash /source/tests/arm64/run_hewl_solver_performance.sh /micro-input /out/components'
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/micro-input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp-components,LC_ALL=C "$image" \
    python3 /source/tests/arm64/hewl_solver_performance.py /micro-input /out/components --audit-shell
echo PORTABLE_COMPONENT_EXECUTION_AND_AUDIT_PASSED
