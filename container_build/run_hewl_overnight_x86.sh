#!/bin/bash
# Bounded x86 comparison on mini05. Launch with nohup + timeout from its project
# validation directory; no laptop filesystem or live SSH connection is needed.
# Cases run sequentially on four physical cores to avoid self-interference.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a prepared mini05 overnight root}")"
case "$root" in /home/jsequeira/Projects/side/06_CpHMD-container/validation/overnight.*) ;; *) exit 2 ;; esac
cd "$root"
mkdir tmp
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
# Persist the real result even if one engine or scientific reader fails.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > x86-exit.txt
    uptime > load-after.txt
    exit "$status"
}
trap preserve_status EXIT
image=/home/jsequeira/Projects/side/06_CpHMD-container/02_CpH-reduced-ASICs/CpHMD-container/tests/gpu-output-contract/build/artifacts/CpHMD-container-v0.7.0-rc3-x86_64-gromacs-2026.3-cuda-12.6.3.sif
echo "195139e9bf25cd6cf24b13fae50e1c7cb5b504688d35ede1f24581940684bd0a  $image" | sha256sum -c -
(cd source && sha256sum -c source.sha256 > ../source-verification.log)
(cd input && sha256sum -c manifest.sha256 > ../snapshot-verification.log)
hostname > hostname.txt
lscpu > lscpu.txt
uptime > load-before.txt
for case_id in 0 1; do
    singularity exec --cleanenv --bind "$root/source:/source:ro,$root/input:/input:ro,$root/fixed:/fixed:ro,$root:/out" \
        --pwd /out --env TMPDIR=/out/tmp,LC_ALL=C,GMX_MAXBACKUP=-1 "$image" \
        taskset -c 0-3 python3 /source/tests/arm64/hewl_overnight.py md /source /input "/out/md-case-$case_id" \
        --tpr /fixed/effective.tpr --case "$case_id"
done
echo OVERNIGHT_X86_MD_PASSED
