#!/bin/bash
# Native coupled-cycle gate. Stage only disposable fixture configuration, then
# invoke the unmodified CpHMD controller. Original source/snapshot stay read-only.
# A successful result requires the independent cycle auditor, not exit 0 alone.
set -Eeuo pipefail
source_root="$(realpath "${1:?Supply frozen source}")"
snapshot="$(realpath "${2:?Supply verified snapshot}")"
work="${3:?Supply a new output directory}"
mode="${4:-all}"
case "$mode" in all|rt|continue) ;; *) echo 'Use all, rt or continue' >&2; exit 2 ;; esac
if [[ $mode == continue ]]; then
    # A separate allocation continues a real finalized reduced cycle (7 -> 8).
    # Clone into a new output tree; the seven-cycle result remains read-only.
    previous="$(realpath "${5:?Supply the finalized seven-cycle result}")"
    [[ ! -e $work ]] || { echo 'Continuation output already exists' >&2; exit 2; }
    cp -a "$previous" "$work"
    work="$(realpath "$work")"
    cd "$work"
    rm -f result.txt
    export LC_ALL=C OMP_NUM_THREADS=8 GMX_MAXBACKUP=-1
    (cd "$snapshot" && sha256sum -c manifest.sha256) > continuation-snapshot-verification.log
    cp -a restart restart-reduced-boundary
    cp resub_maint/checkpoint.state reduced-boundary.state
    python3 - <<'PY'
from pathlib import Path
import json
audit=json.loads(Path('cycle-audit.json').read_text())
assert audit['passed'] and audit['mode']=='rt'
assert audit['checkpoint']['CPHMD_DONE_CYCLES']=='7'
assert audit['checkpoint']['CPHMD_SEGMENT_FINALIZED']=='1'
Path('cycle-audit.json').rename('parent-cycle-audit.json')
path=Path('HEWL.settings');text=path.read_text()
assert text.count('export SimTime=0.007')==1
path.write_text(text.replace('export SimTime=0.007','export SimTime=0.008'))
protocol=json.loads(Path('protocol.json').read_text())
protocol.update(cycles=8,continuation_from_finalized_reduced_cycle=7)
Path('protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
PY
    set +e
    bash "$source_root/CpHMD/scripts/CpHMD.sh" HEWL.settings > controller-reduced-resume.log 2>&1
    status=$?
    set -e
    printf '%s\n' "$status" > controller-reduced-resume.exit
    [[ $status == 0 ]] || { tail -n 40 controller-reduced-resume.log; exit "$status"; }
    python3 "$source_root/tests/arm64/hewl_cycle.py" check "$source_root" "$snapshot" "$work" rt --cycles 8
    echo COUPLED_CYCLE_GATE_PASSED | tee result.txt
    exit 0
fi
mkdir "$work"
work="$(realpath "$work")"
export LC_ALL=C OMP_NUM_THREADS=8 GMX_MAXBACKUP=-1
(cd "$snapshot" && sha256sum -c manifest.sha256) > "$work/snapshot-verification.log"
python3 "$source_root/tests/arm64/hewl_cycle.py" prepare "$source_root" "$snapshot" "$work" "$mode"
cd "$work"
uname -m > architecture.txt
/gromacs/bin/gmx --version > gromacs-version.txt 2>&1
sha256sum /Delphi/delphi_pgf90 /programs/petit1.6.1/petit /gromacs/bin/gmx > runtime.sha256
ldd /Delphi/delphi_pgf90 > delphi-ldd.txt
# Keep the controller's own error handling: never source it into this errexit
# shell. Its return code is captured exactly, including clean boundary code 10.
set +e
bash "$source_root/CpHMD/scripts/CpHMD.sh" HEWL.settings > controller-first.log 2>&1
status=$?
set -e
printf '%s\n' "$status" > controller-first.exit
if [[ $mode == rt ]]; then
    [[ $status == 10 ]] || { tail -n 35 controller-first.log; exit 1; }
    # Freeze the finalized boundary before continuing from its actual restart
    # topology/coordinates and active/fixed templates. No synthetic checkpoint.
    cp -a restart restart-boundary
    cp resub_maint/checkpoint.state boundary.state
    # Disable only the bounded walltime test; retain the same seven-cycle target.
    sed -i 's/export CPHMD_MAX_SECONDS=1/export CPHMD_MAX_SECONDS=0/' HEWL.settings
    set +e
    bash "$source_root/CpHMD/scripts/CpHMD.sh" HEWL.settings > controller-resume.log 2>&1
    status=$?
    set -e
    printf '%s\n' "$status" > controller-resume.exit
fi
[[ $status == 0 ]] || { tail -n 40 controller-*.log; exit "$status"; }
python3 "$source_root/tests/arm64/hewl_cycle.py" check "$source_root" "$snapshot" "$work" "$mode"
echo COUPLED_CYCLE_GATE_PASSED | tee result.txt
