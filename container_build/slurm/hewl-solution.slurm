#!/bin/bash
#SBATCH --job-name=cphmd-hewl-solution
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# Native, ordinary-user solution preparation from the verified HEWL topology.
# A frozen source snapshot and input-topology audit pin this job. All work and
# temporary simulation files remain in the project; no automatic resubmission.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new project solution-validation directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || exit 2
test ! -e "$root/solution"
mkdir "$root/tmp"
export TMPDIR="$root/tmp"
export SINGULARITY_TMPDIR="$TMPDIR" APPTAINER_TMPDIR="$TMPDIR"
exec > >(tee "$root/solution-${SLURM_JOB_ID}.log") 2>&1
# Capture the original outcome without deleting any failed preparation outputs.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
hostname
date -Is
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/topology.zfP6K8/topology
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/runtime-permissions/repair.G02c6n/CpHMD-arm64-readable.sif
echo "d153f31722e76f167080485942074633ce9e3d7abc51dfa97827f790947880ba  $image" | sha256sum -c -
python3 - "$root/source" "$input" <<'PY'
"""Verify frozen tools and the previously audited topology before preparing MD."""
import hashlib,json,sys
from pathlib import Path
source=Path(sys.argv[1]); top=Path(sys.argv[2])
metadata=json.loads((source/'source-snapshot.json').read_text())
for name,expected in metadata['files'].items():
    if hashlib.sha256((source/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Frozen source changed: '+name)
audit=json.loads((top/'topology-audit.json').read_text())
for name,expected in audit['source_file_sha256'].items():
    if hashlib.sha256((top/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Verified topology changed: '+name)
parameters=json.loads((top/'runtime-input-sha256.json').read_text())
for name,expected in parameters.items():
    if name.startswith('Amber14SBpH.ff/') and hashlib.sha256((top/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Prepared force field changed: '+name)
print('PASS: frozen source and input-topology hashes')
PY
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/topology:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp "$image" \
    bash /source/tests/arm64/prepare_hewl_solution.sh /source /topology /out/solution "$SLURM_CPUS_PER_TASK"
test "$(cat "$root/solution/result.txt")" = SOLUTION_PREPARATION_AND_SNAPSHOT_PASSED
tar -czf "$root/HEWL-snapshot.tar.gz" -C "$root/solution" snapshot
(cd "$root" && sha256sum HEWL-snapshot.tar.gz > HEWL-snapshot.tar.gz.sha256)
