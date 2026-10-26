#!/bin/bash
# Singularity %test entry point, installed inside the candidate image.
# Check native architecture/dependencies, then isolated helper/PETIT and MD
# fixtures. These build gates precede fixed-coordinate PB/MC and complete
# CpHMD-cycle/restart validation; they cannot establish scientific equivalence.
set -Eeuo pipefail
[[ $(uname -m) == aarch64 ]] || { echo 'ARM runtime required'; exit 2; }
export PATH="/gromacs/bin:/opt/plumed/bin:$PATH"
export LD_LIBRARY_PATH="/opt/nvhpc/lib:/opt/plumed/lib:/opt/plumed/lib64"
export PLUMED_KERNEL=/opt/plumed/lib/libplumedKernel.so
version="$(gmx --version 2>&1)"
printf '%s\n' "$version"
grep -q 'GROMACS version:.*2026.3' <<< "$version"
grep -q 'GPU support:.*disabled' <<< "$version"
expected_simd="$(python3 -c 'import json; print(json.load(open("/etc/cphmd/build.json"))["simd"])')"
grep -q "SIMD instructions:.*${expected_simd}" <<< "$version"
mdrun_help="$(gmx mdrun -h 2>&1)"
grep -q -- '-plumed' <<< "$mdrun_help"
python3 - <<'PY'
"""Inspect ELF machine headers throughout the runtime payload for x86 leakage."""
from pathlib import Path
import struct
count=0
for root in ['/CpHMD','/Delphi','/FFs','/STs','/Databases','/analysis',
             '/gromacs','/opt/plumed','/opt/nvhpc','/programs/petit1.6.1']:
    for p in Path(root).rglob('*'):
        if not p.is_file() or p.is_symlink(): continue
        with p.open('rb') as h: b=h.read(20)
        if b[:4] != b'\x7fELF': continue
        machine=struct.unpack('<H' if b[5]==1 else '>H',b[18:20])[0]
        if machine!=183: raise SystemExit(f'Wrong ELF architecture {machine}: {p}')
        count+=1
assert count>=6
print(f'PASS: {count} ELF files are AArch64')
PY
for binary in /Delphi/delphi_pgf90 /Delphi/geom_center /Delphi/calc_pkg_low \
    /CpHMD/scripts/fixgro /programs/petit1.6.1/petit /opt/plumed/lib/libplumedKernel.so; do
    dependencies="$(ldd "$binary")"
    printf '%s\n%s\n' "$binary" "$dependencies"
    if grep -q 'not found' <<< "$dependencies"; then exit 1; fi
done
# Parse controller sources without executing a simulation or user settings.
bash -n /CpHMD/scripts/CpHMD.sh
bash -n /CpHMD/scripts/settings_contract.sh
bash -n /CpHMD/scripts/functions.sh
python3 /usr/share/cphmd/tests/check_fixgro.py --binary /CpHMD/scripts/fixgro
python3 /usr/share/cphmd/tests/check_petit.py --binary /programs/petit1.6.1/petit

bash /usr/share/cphmd/tests/md_smoke.sh /gromacs/bin/gmx
echo 'PASS: ARM dependency, helper, PETIT and 20-step water MD smoke checks'
echo 'Scientific PB/MC and CpHMD restart validation are still required.'
