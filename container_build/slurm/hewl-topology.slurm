#!/bin/bash
#SBATCH --job-name=cphmd-hewl-topology
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
# Native preparation-only validation of the existing SIF from job 2147983.
# Source is a hashed, read-only snapshot. All work, logs and results stay in the
# project. No compilation, PB/MC solver, MD, or automatic resubmission occurs.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new project topology-validation directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || { echo 'Native ARM node required'; exit 2; }
test ! -e "$root/topology"
mkdir "$root/tmp"
export TMPDIR="$root/tmp"
export SINGULARITY_TMPDIR="$TMPDIR" APPTAINER_TMPDIR="$TMPDIR"
exec > >(tee "$root/topology-${SLURM_JOB_ID}.log") 2>&1
# Preserve the actual script outcome even if image execution/preprocessing fails.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
hostname
date -Is
python3 - "$root/source" <<'PY'
"""Verify every frozen preparation input before using it in the native image."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); metadata=json.loads((root/'source-snapshot.json').read_text())
for name,expected in metadata['files'].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Frozen source changed: '+name)
print('PASS: frozen preparation source hashes')
PY
image="${2:?Supply the validated ARM image}"
image_hash="${3:?Supply its expected SHA-256}"
[[ $image_hash =~ ^[0-9a-f]{64}$ ]] || exit 2
echo "$image_hash  $image" | sha256sum -c -
singularity exec --cleanenv --bind "$root/source:/source:ro,$root:/out" --pwd /out "$image" \
    bash /source/tests/arm64/prepare_hewl_topology.sh /source /out/topology
test "$(cat "$root/topology/result.txt")" = TOPOLOGY_AND_SITE_CHECKS_PASSED
