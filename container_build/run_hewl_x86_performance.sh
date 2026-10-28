#!/bin/bash
# Execute the matched reference on mini05 after transferring frozen inputs.
# The source-paired context is immutable and shared with ARM. CPU-only GROMACS
# 2026.3 is selected by this rc3 image's existing /gromacs/bin/gmx launcher.
# Run cases sequentially to avoid competing with our own CPU benchmarks.
set -Eeuo pipefail
root="$(realpath "${1:?Supply the prepared mini05 validation root}")"
image="$(realpath "${2:?Supply the verified rc3 x86 image}")"
case "$root" in /home/jsequeira/Projects/side/06_CpHMD-container/validation/performance.*) ;; *) exit 2 ;; esac
[[ $(uname -m) == x86_64 ]] || exit 2
cd "$root"
echo "195139e9bf25cd6cf24b13fae50e1c7cb5b504688d35ede1f24581940684bd0a  $image" | sha256sum -c -
echo 'bd322b839e71c9bc8f7df3c22596b341e66c5b94dc6579f052bba69c3a1683b9  snapshot.tar.gz' | sha256sum -c -
echo '7276106632db360dadc02f3cc0075006ee9de10d029e143a590c2a1e02113e48  fixed-effective.tpr' | sha256sum -c -
mkdir input-context
tar -xzf snapshot.tar.gz -C input-context
cp "${BASH_SOURCE[0]}" executed-x86-performance.sh
mkdir tmp-reference
export TMPDIR="$root/tmp-reference" SINGULARITY_TMPDIR="$root/tmp-reference" APPTAINER_TMPDIR="$root/tmp-reference"
exec > >(tee x86-performance.log) 2>&1
# Retain the true launch/audit status and final host load for this reference run.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > x86-performance.exit
    uptime > x86-load-after.txt
    exit "$status"
}
trap preserve_status EXIT
uptime > x86-load-before.txt
lscpu > x86-lscpu.txt
(cd source-paired && sha256sum -c source.sha256 > ../x86-source-verification.log)
(cd input-context/snapshot && sha256sum -c manifest.sha256 > ../../x86-snapshot-verification.log)
binds="$root/source-paired:/source:ro,$root/input-context/snapshot:/input:ro,$root/micro-input-paired:/micro-input:ro,$root/fixed-effective.tpr:/fixed/effective.tpr:ro,$root:/out"
singularity exec --cleanenv --bind "$binds" --pwd /out --env TMPDIR=/out/tmp-reference,LC_ALL=C "$image" \
    bash -c '/gromacs/bin/gmx --version; sha256sum /gromacs/gromacs-2026.3/bin/gmx /Delphi/delphi_pgf90 /programs/petit1.6.1/petit; ldd /Delphi/delphi_pgf90' > x86-rc3-runtime.txt
# Repeat the original binary screen inside the actual 2026.3 reference image,
# preserving the older-image screen separately to expose runtime differences.
singularity exec --cleanenv --bind "$binds" --pwd /out --env TMPDIR=/out/tmp-reference,LC_ALL=C "$image" \
    taskset -c 0 bash /source/tests/arm64/run_hewl_solver_performance.sh /micro-input /out/micro-rc3
singularity exec --cleanenv --bind "$binds" --pwd /out --env TMPDIR=/out/tmp-reference,LC_ALL=C "$image" \
    python3 /source/tests/arm64/hewl_solver_performance.py /micro-input /out/micro-rc3 --audit-shell
# CPUs 0--5 are the six different physical cores in the saved mini05 CPU map.
# Avoid SMT; four cores provide the common allocation for the ARM comparison.
singularity exec --cleanenv --bind "$binds" --pwd /out --env TMPDIR=/out/tmp-reference,LC_ALL=C,GMX_MAXBACKUP=-1 "$image" \
    taskset -c 0-5 python3 /source/tests/arm64/hewl_performance.py md /source /input /out/md --tpr /fixed/effective.tpr --counts 4 6
singularity exec --cleanenv --bind "$binds" --pwd /out --env TMPDIR=/out/tmp-reference,LC_ALL=C,GMX_MAXBACKUP=-1 "$image" \
    taskset -c 0-3 python3 /source/tests/arm64/hewl_performance.py coupled /source /input /out/coupled --counts 4
echo HEWL_X86_PERFORMANCE_PASSED
