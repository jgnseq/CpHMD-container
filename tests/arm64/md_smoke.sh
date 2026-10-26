#!/bin/bash
# Architecture-independent MD/PLUMED smoke test for the two CPU images.
set -Eeuo pipefail
tests="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gmx="${1:-/gromacs/bin/gmx}"
work="$(mktemp -d "${TMPDIR:-/tmp}/cphmd-md-check.XXXXXX")"
trap 'rm -rf "$work"' EXIT
cd "$work"
export GMXLIB=/gromacs/gromacs-2026.3/share/gromacs/top
"$gmx" grompp -f "$tests/water.mdp" -c "$GMXLIB/spc216.gro" \
    -p "$tests/water.top" -o water.tpr
"$gmx" mdrun -s water.tpr -deffnm water -ntmpi 1 -ntomp 1 -pin off \
    -plumed "$tests/water.plumed.dat"
"$gmx" check -f water.xtc
"$gmx" check -e water.edr
test -s water.gro
test -s COLVAR
python3 - <<'PY'
import math
rows=[list(map(float,line.split())) for line in open('COLVAR')
      if line.strip() and not line.startswith('#')]
assert rows and all(all(math.isfinite(x) for x in row) for row in rows)
print('PASS: MD, readable XTC/EDR and finite PLUMED distance records')
PY
