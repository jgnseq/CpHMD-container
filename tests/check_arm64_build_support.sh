#!/bin/bash
# Workstation/CI gates before exporting a candidate: parse build scripts, check
# independent Git transfer, then compile/test portable helper and PETIT sources.
# Native image/dependency/MD checks run later in arm64/validate-arm64.sh.
set -Eeuo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
work="$(mktemp -d "${TMPDIR:-/tmp}/cphmd-arm-support.XXXXXX")"
trap 'rm -rf "$work"' EXIT
for script in container_build/arm64/*.sh container_build/slurm/*.slurm \
    container_build/run_arm64_build.sh container_build/submit_deucalion_arm64.sh \
    container_build/create_source_bundle.sh tests/check_source_bundle.sh \
    tests/check_gromacs_test_gate.sh \
    tests/arm64/md_smoke.sh; do
    bash -n "$script"
done
python3 container_build/prepare_arm64_build.py --help >/dev/null
bash tests/check_source_bundle.sh
gcc -std=c99 -O2 CpHMD/src/fixgro.c -lm -o "$work/fixgro"
python3 tests/arm64/check_fixgro.py --binary "$work/fixgro"
gcc -O2 petit1.6.1/petit.c -lm -o "$work/petit"
python3 tests/arm64/check_petit.py --binary "$work/petit"
gcc -O2 DelphiTools/src/geom_center.c DelphiTools/src/my_mem.c -lm -o "$work/geom_center"
gcc -O2 DelphiTools/src/calc_pkg_low.c DelphiTools/src/my_mem.c -lm -o "$work/calc_pkg_low"
echo 'PASS: ARM build support parses; native helper sources and PETIT fixtures pass.'
