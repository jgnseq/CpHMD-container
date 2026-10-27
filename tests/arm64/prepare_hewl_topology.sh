#!/bin/bash
# Container-side HEWL topology gate. Called in a new writable test directory,
# with a frozen repository snapshot mounted read-only as the first argument.
# Generate CpHMD names/topology, exercise the actual controller's terminal and
# site preparation, and preprocess a diagnostic TPR. No solvation or MD runs.
set -Eeuo pipefail
source_root="${1:?Supply the frozen repository snapshot}"
work="${2:?Supply a new topology output directory}"
mkdir "$work"
cd "$work"
export OMP_NUM_THREADS=1
export GMX_MAXBACKUP=-1
export GMXLIB=/FFs
python3 "$source_root/tests/arm64/prepare_hewl_structure.py" \
    --source "$source_root/tests/fixtures/hewl-4lzt/source/4LZT.pdb" --output-dir structure
cp structure/4LZT-protein.pdb protein.pdb
# Invoke the same image-owned helper as the pdb2cphmd app. CYS is deliberately
# absent: all eight HEWL cysteines are oxidized disulfides, not titratable thiols.
bash /analysis/prepare-pdb.sh -p protein.pdb -f Amber14SBpH -r asp glu his lys tyr > naming.log 2>&1
python3 "$source_root/tests/arm64/complete_amber_cleu_hdb.py"
python3 "$source_root/tests/arm64/pdb2gmx_termini.py"
/gromacs/bin/gmx editconf -f HEWL.gro -o HEWL.pdb > editconf.log 2>&1
printf 'q\n' | /gromacs/bin/gmx make_ndx -f HEWL.gro -o TMP_CpHMD.ndx > index.log 2>&1

# Minimal helper settings, not a simulation configuration. The tested make_sites
# function sources these values and writes its PB charge-topology view. Use the
# image's functions/helper/STs, not a separately reimplemented naming algorithm.
cat > site-check.settings <<'EOF'
export SysName=HEWL
export ffID=Amber14SBpH
export sites="all 1N 129C"
export StDIR=/STs/St-Amber14SBpH
export GroDIR=/gromacs/bin/gmx
EOF
source site-check.settings
export runname=HEWL CpHDIR=/CpHMD GROin=HEWL.gro offset=2000
export CPHMD_ALL_SITES_FILE=HEWL-all.sites
# functions.sh expects the controller's logging callback. Supply only that
# callback here so preparation can be tested without starting the controller.
message () {
    local kind="$1"; shift
    printf '%s: %s\n' "$kind" "$*" >&2
    [[ $kind != E && $kind != U ]] || exit 1
}
source /CpHMD/scripts/functions.sh
cp HEWL.top TMP_CpHMD.top
make_sites site-check.settings > site-generation.log 2>&1
python3 "$source_root/tests/arm64/check_hewl_topology.py" --directory . --st-dir "$StDIR"

# This unsolvated diagnostic only checks bonded/nonbonded parameter completeness
# and atom ordering. Cutoff electrostatics avoids interpreting a charged vacuum
# structure as a PME solution. Production settings/equilibration come later.
/gromacs/bin/gmx editconf -f HEWL.gro -o HEWL-check-box.gro -bt dodecahedron -d 1.2 > box-check.log 2>&1
cat > topology-check.mdp <<'EOF'
integrator = steep
nsteps = 0
cutoff-scheme = Verlet
coulombtype = Cut-off
rcoulomb = 1.0
vdwtype = Cut-off
rvdw = 1.0
rlist = 1.0
pbc = xyz
constraints = none
EOF
/gromacs/bin/gmx grompp -f topology-check.mdp -c HEWL-check-box.gro -p HEWL.top \
    -o HEWL-check.tpr -pp HEWL-processed.top -po topology-check-out.mdp -maxwarn 0 > grompp.log 2>&1
/gromacs/bin/gmx dump -s HEWL-check.tpr > HEWL-check.dump 2>&1
/gromacs/bin/gmx --version > gromacs-version.txt 2>&1
python3 - <<'PY'
"""Pin copied force-field, ST/database and image runtime sources for comparison."""
import hashlib, json
from pathlib import Path
paths = [Path('/analysis/prepare-pdb.sh'), Path('/CpHMD/scripts/make_sites'), Path('/CpHMD/scripts/functions.sh')]
for root in [Path('Amber14SBpH.ff'), Path('/STs/St-Amber14SBpH')]:
    paths.extend(sorted(p for p in root.rglob('*') if p.is_file()))
paths.extend([Path('residuetypes.dat'),Path('specbond.dat')])
Path('runtime-input-sha256.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+'\n')
PY
echo 'TOPOLOGY_AND_SITE_CHECKS_PASSED' | tee result.txt
