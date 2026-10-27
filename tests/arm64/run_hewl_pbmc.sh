#!/bin/bash
# Fixed-coordinate PB/MC gate, used unchanged in the x86 and ARM containers.
# Inputs: frozen source, verified solution snapshot and its original NPT TPR.
# Output: new directory with actual controller logs, raw PB files and three
# seeded PETIT runs. No dynamics or topology-state updates are performed.
set -Eeo pipefail
source_root="$(realpath "${1:?Supply frozen source}")"
input="$(realpath "${2:?Supply the verified solution snapshot}")"
tpr="$(realpath "${3:?Supply its NPT TPR}")"
work="${4:?Supply a new PBMC directory}"
profile="${5:-standard}"
case "$profile" in standard|tight) ;; *) echo 'Use standard or tight PB profile' >&2; exit 2 ;; esac
mkdir "$work"
cd "$work"
work="$PWD"
export LC_ALL=C OMP_NUM_THREADS=1 GMX_MAXBACKUP=-1
(cd "$input" && sha256sum -c manifest.sha256) > snapshot-verification.log
cp -a "$input/Amber14SBpH.ff" .
cp "$input/HEWL.gro" TMP_effective.gro
cp "$input/HEWL.top" TMP_CpHMD.top
cp "$input/index.ndx" TMP_CpHMD.ndx
cp "$tpr" TMP_CpHMD.tpr
mkdir tools raw

# Execute identical text drivers and native helper C source on both machines.
# One retention-only edit keeps delphiT's diagnostic directory. Assert and log
# the substitution; never edit the repository or image-owned program. The
# normal run_PBMC cleanup still runs, exercising the actual controller function.
python3 - "$source_root" <<'PY'
"""Stage shared drivers with an explicit diagnostic-retention substitution."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
for p in (root/'DelphiTools').iterdir():
    if p.is_file() and p.read_bytes()[:4] != b'\x7fELF':
        (Path('tools')/p.name).write_bytes(p.read_bytes())
text=(root/'DelphiTools/delphiT').read_text()
old='nice -n 19 /bin/rm -rf delphiT$$ &'
assert text.count(old)==1, 'Unexpected delphiT cleanup; review retention hook'
Path('tools/delphiT-retained').write_text(text.replace(old, 'echo "Retained PB diagnostics in delphiT$$"'))
Path('retention-hook.txt').write_text(old+'\n=>\necho "Retained PB diagnostics in delphiT$$"\n')
PY
chmod +x tools/*
ln -s /Delphi/delphi_pgf90 tools/delphi_pgf90
# ARM uses the rebuilt, audited candidate helpers. x86 uses binaries compiled
# from the identical pinned sources by the host GCC before this call. Compiler
# and flags are recorded outside the container. Neither build uses fast-math.
native="${CPHMD_MATCHED_BINARIES:-/Delphi}"
cp "$native/geom_center" "$native/calc_pkg_low" tools/
if [[ -n ${CPHMD_MATCHED_BINARIES:-} ]]; then
    petit="$native/petit"
else
    petit=/programs/petit1.6.1/petit
fi
export CPHMD_REAL_PETIT="$petit" CPHMD_GATE_WORK="$work"
cat > tools/delphiT <<'EOF'
#!/bin/bash
# Preserve real outputs before run_PBMC performs its ordinary cleanup.
set -e
bash "$DelphiDir/delphiT-retained" "$@"
cp "$2.pkcrg" "$2.g" "$CPHMD_GATE_WORK/raw/"
EOF
cat > tools/petit <<'EOF'
#!/bin/bash
# Save converter output and stdout without changing PETIT's input or status.
set -eo pipefail
cat > "$CPHMD_GATE_WORK/raw/PBMC.dat"
"$CPHMD_REAL_PETIT" "$@" < "$CPHMD_GATE_WORK/raw/PBMC.dat" | tee "$CPHMD_GATE_WORK/raw/petit-1729.out"
EOF
chmod +x tools/delphiT tools/petit
export SysName=HEWL runname=HEWL blockname=HEWL Cycle=1
export ffID=Amber14SBpH sites='all 1N 129C' GROin=TMP_effective.gro
export GroDIR=/gromacs/bin/gmx CpHDIR="$source_root/CpHMD"
export DelphiDir="$work/tools" PetitDIR="$work/tools"
export StDIR="$source_root/STs/St-Amber14SBpH" DatabaseDIR="$source_root/Databases" ffDIR="$work"
export CPHMD_ALL_SITES_FILE=HEWL-all.sites UseInputOffset=0 offset=2000
export memb=0 multiple_solutes=0 include_itp=0 PBdim=0 cutoff=-1 nCPU=8
export pH=6 temp=310 pot=0 seed=1729 PBMCDebugPDB=0 write_states=n ReduceTitration=0
export rdir="$work"
# Freeze the protein PB grid/convergence profile on both architectures.
# Continuum salt is 0.1 M; explicit solvent and ions are omitted from PB.
cp "$source_root/DelphiTools/DELPHI_Prot.pbp" DELPHI.pbp
cat > USER.pbp <<'EOF'
export ionicstr=0.1
export epsin=2.0
EOF
if [[ $profile == tight ]]; then
    # Numerical-convergence control, applied identically on both architectures.
    # Keep the physical model, coordinates and original acceptance limits. The
    # standard-profile comparison remains recorded independently, even if this
    # more converged calculation agrees better.
    # gen_files.awk reads this file directly; exported USER.pbp overrides do
    # not reach its numeric parser. Change only our disposable working copy.
    python3 - <<'PY'
from pathlib import Path
path=Path('DELPHI.pbp');text=path.read_text()
for old,new in [('export maxc=0.01','export maxc=0.0001'),('export linit=100','export linit=1000')]:
    assert text.count(old)==1, 'Unexpected PB profile template'
    text=text.replace(old,new)
path.write_text(text)
PY
fi
cat > site-check.settings <<EOF
export SysName=HEWL
export ffID=Amber14SBpH
export sites="all 1N 129C"
export StDIR="$StDIR"
export GroDIR="$GroDIR"
EOF
# Supply the controller's logging callback. Do not enable nounset: the
# historical function library deliberately uses optional unset globals.
message () {
    local kind="$1"; shift
    printf '%s: %s\n' "$kind" "$*" >&2
    [[ $kind != E && $kind != U ]] || exit 1
}
source "$source_root/CpHMD/scripts/functions.sh"
make_sites site-check.settings > site-generation.log 2>&1
cmp HEWL-all.sites "$input/HEWL-all.sites"
"$DelphiDir/getst" HEWL-all.sites "$StDIR" > getst.log 2>&1
make_delphi_DB > database.log 2>&1
uname -m > architecture.txt
"$GroDIR" --version > gromacs-version.txt 2>&1
sha256sum tools/{delphi_pgf90,geom_center,calc_pkg_low} "$petit" > native-binaries.sha256
ldd tools/delphi_pgf90 > delphi-ldd.txt
cp "$source_root/tests/arm64/hewl-pbmc-contract.json" contract.json
if [[ $profile == tight ]]; then
    cp "$source_root/tests/arm64/hewl-pbmc-tight-contract.json" contract.json
fi
run_PBMC HEWL-all.sites fixed-coordinate > pbmc.log 2>&1
for replicate_seed in 2718 3141; do
    "$petit" -H 6,6,1 -E 0,0,1 -T 310 -c 2 -r "$replicate_seed" \
        -q 1000 100000 < raw/PBMC.dat > "raw/petit-$replicate_seed.out" \
        2> "raw/petit-$replicate_seed.err"
    cphmd_validate_petit_output "raw/petit-$replicate_seed.out" 21
done
# Audit actual generated solver input, not just requested/exported settings.
python3 - "$profile" <<'PY'
from pathlib import Path
import json,sys
tight=sys.argv[1]=='tight';target=0.0001 if tight else 0.01
rows=[]
for path in Path('.').glob('delphiT*/tmp/*.prm'):
    values=dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
    assert float(values['maxc'])==target, 'Convergence override did not reach '+str(path)
    expected=(1000 if tight else 100) if path.name.endswith('b.prm') else 500
    assert int(values['linit'])==expected, 'Wrong actual iteration limit: '+str(path)
    rows.append({'file':path.name,'maxc':float(values['maxc']),'linit':int(values['linit'])})
assert rows, 'No retained solver parameter files'
Path('solver-profile-audit.json').write_text(json.dumps({'profile':sys.argv[1],'solves':len(rows),'parameters':rows},indent=2)+'\n')
PY
echo PBMC_EXECUTION_PASSED | tee result.txt
