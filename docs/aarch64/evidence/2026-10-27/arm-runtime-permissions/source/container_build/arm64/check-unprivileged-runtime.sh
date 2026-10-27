#!/bin/bash
# Post-build acceptance gate, invoked by the ordinary host user with exec and
# no --fakeroot. Build-time %test runs as root and cannot prove these accesses.
# Check application/data entry points, then native dependency/PETIT/helper/MD
# smoke gates. TMPDIR must point to the project's writable validation directory.
set -Eeuo pipefail
[[ $(id -u) != 0 ]] || { echo 'Ordinary-user validation must not run as root' >&2; exit 2; }
id
for file in /analysis/prepare-pdb.sh /CpHMD/scripts/CpHMD.sh /CpHMD/scripts/functions.sh \
    /FFs/Amber14SBpH.ff/aminoacids.rtp /STs/St-Amber14SBpH/ASPtau1.st \
    /Databases/DataBaseT_Amber14SBpH.crg /Templates/CpHMD-basic.settings /etc/cphmd/build.json; do
    test -r "$file" || { echo "Unreadable runtime input: $file" >&2; exit 1; }
done
for file in /gromacs/bin/gmx /Delphi/delphi_pgf90 /CpHMD/scripts/fixgro /programs/petit1.6.1/petit; do
    test -x "$file" || { echo "Inaccessible runtime executable: $file" >&2; exit 1; }
done
bash -n /analysis/prepare-pdb.sh
bash /usr/local/libexec/cphmd/validate-arm64.sh
echo 'UNPRIVILEGED_RUNTIME_SMOKE_TESTS_PASSED'
