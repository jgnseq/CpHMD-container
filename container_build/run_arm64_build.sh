#!/bin/bash
# Host-side build driver, invoked by slurm/build-arm64.slurm on an ARM node.
# Verify the frozen candidate, stage private node-local copies for fakeroot,
# build/test the SIF, then preserve image and diagnostics under the project.
# build-inside.sh performs compilation; validate-arm64.sh performs image tests.
# This driver does not run the scientific CpHMD simulation cycle.
set -Eeuo pipefail
out="$(realpath "${1:?Supply a prepared output directory}")"
[[ $(uname -m) == aarch64 ]] || { echo 'Native ARM node required'; exit 2; }
[[ -n ${SLURM_JOB_ID:-} ]] || { echo 'Run inside a scheduler allocation'; exit 2; }
case "$out" in /projects/F202500250CPCAA2/*) ;; *) exit 2 ;; esac
[[ ! -e "$out/CpHMD-arm64.sif" && ! -e "$out/CpHMD-arm64.partial.sif" ]] || {
    echo 'Refusing to overwrite an image; prepare a new output directory' >&2; exit 2;
}
runtime="$(command -v singularity || command -v apptainer)"
test -n "$runtime"
export SINGULARITY_CACHEDIR=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/cache/singularity
export APPTAINER_CACHEDIR="$SINGULARITY_CACHEDIR"
mkdir -p "$SINGULARITY_CACHEDIR"
# User explicitly authorized node-local temporary rootfs assembly. All durable
# inputs, caches, SIFs and logs remain in the project, and failures are preserved.
umask 077
scratch="$(mktemp -d "/tmp/${USER}-cphmd-${SLURM_JOB_ID}.XXXXXX")"
export SINGULARITY_TMPDIR="$scratch/rootfs"
export APPTAINER_TMPDIR="$SINGULARITY_TMPDIR"
export TMPDIR="$SINGULARITY_TMPDIR"
mkdir -p "$TMPDIR" "$scratch/launch"
exec > >(tee "$out/build-${SLURM_JOB_ID}.log") 2>&1
echo "Node-local temporary directory: $scratch"
hostname
date -Is
lscpu
free -h
df -h "$scratch" "$out"
"$runtime" --version
cd "$out"
sha256sum --quiet -c manifest.sha256
python3 - "$out" <<'PY'
"""Reject changed build inputs or an undersized scheduler CPU allocation."""
import hashlib,json,sys,os
from pathlib import Path
p=Path(sys.argv[1]);m=json.loads((p/'build.json').read_text())
def digest(path):
    """Hash large bootstrap/source files in bounded-memory blocks."""
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
assert digest(p/'CpHMD.arm64.def')==m['definition_sha256'], 'Definition changed'
assert digest(p/'manifest.sha256')==m['manifest_sha256'], 'Manifest changed'
assert digest(Path(m['base_image']))==m['base_sha256'], 'Base image changed'
assert m['jobs']<=int(os.environ['SLURM_CPUS_PER_TASK']), 'Build jobs exceed allocated CPUs'
PY
mkdir "$out/artifacts-${SLURM_JOB_ID}"
mkdir "$scratch/artifacts"
# EXIT handler: return compiler diagnostics and the real build exit status to
# project storage even if compilation or %test fails. Keep scratch for diagnosis.
preserve_exit () {
    status=$?
    set +e
    cp -a "$scratch/artifacts/." "$out/artifacts-${SLURM_JOB_ID}/"
    cp "$scratch/launch/executed.def" "$out/executed-${SLURM_JOB_ID}.def"
    printf '%s\n' "$status" > "$out/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_exit EXIT
# Fakeroot clears supplementary groups and cannot traverse the project root.
# Stage temporary copies, preserving authoritative inputs under the project.
cp -a "$out/context" "$scratch/launch/context"
cp "$out/build.json" "$out/manifest.sha256" "$scratch/launch/"
mkdir "$scratch/launch/build-evidence"
base="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_image"])' "$out/build.json")"
cp "$base" "$scratch/bootstrap.sif"
python3 - "$out/CpHMD.arm64.def" "$scratch" <<'PY'
"""Change only the bootstrap path for fakeroot's project-access limitation.

The original hashed recipe stays in the project; preserve this executed copy
alongside it so the staging substitution is visible in the build evidence.
"""
from pathlib import Path
import sys
source=Path(sys.argv[1]).read_text();scratch=Path(sys.argv[2])
lines=source.splitlines()
assert lines[0]=='Bootstrap: localimage' and lines[1].startswith('From: ')
lines[1]='From: '+str(scratch/'bootstrap.sif')
(scratch/'launch/executed.def').write_text('\n'.join(lines)+'\n')
PY
cd "$scratch/launch"
sha256sum --quiet -c manifest.sha256
"$runtime" build --disable-cache --fakeroot --bind "$scratch/artifacts:/build-evidence" \
    "$scratch/CpHMD-arm64.partial.sif" "$scratch/launch/executed.def"
# %test ran as fakeroot. Repeat runtime acceptance as the ordinary account,
# with project-backed temporary simulation files, before publishing the image.
mkdir "$out/runtime-tmp"
"$runtime" exec --cleanenv --bind "$out:/validation" --pwd /validation \
    --env TMPDIR=/validation/runtime-tmp "$scratch/CpHMD-arm64.partial.sif" \
    bash /validation/context/container_build/arm64/check-unprivileged-runtime.sh \
    2>&1 | tee "$out/unprivileged-runtime.log"
cp "$scratch/CpHMD-arm64.partial.sif" "$out/CpHMD-arm64.partial.sif"
mv "$out/CpHMD-arm64.partial.sif" "$out/CpHMD-arm64.sif"
"$runtime" inspect --json "$out/CpHMD-arm64.sif" > "$out/image-inspect.json"
cd "$out"
sha256sum CpHMD-arm64.sif > CpHMD-arm64.sif.sha256
echo 'BUILD_AND_SMOKE_TESTS_PASSED' | tee build-result.txt
echo 'PB/MC comparison, CpHMD integration and RT/restart validation remain pending.'
