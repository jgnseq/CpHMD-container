#!/bin/bash
# Container-side native HEWL solution preparation, using the verified topology.
# Preserve a complete new work directory and command/log trail. Stages are
# box/solvent -> neutral ion inventory -> restrained EM -> 10 ps NVT -> 20 ps NPT
# -> health checks and portable snapshot. No PB/MC or CpHMD cycles are run here.
set -Eeuo pipefail
source_root="${1:?Supply the frozen source directory}"
input="${2:?Supply the verified topology directory}"
work="${3:?Supply a new solution output directory}"
threads="${4:?Supply allocated CPU threads}"
mkdir "$work"
cd "$work"
export GMXLIB=/FFs GMX_MAXBACKUP=-1 OMP_NUM_THREADS="$threads"
gmx=/gromacs/bin/gmx

# run_logged LOG COMMAND... records the exact argv before execution and keeps
# each stage's stdout/stderr. Failures propagate through set -e and pipefail.
run_logged () {
    local log="$1"; shift
    printf '%q ' "$@" >> commands.log; printf '\n' >> commands.log
    "$@" > "$log" 2>&1
}

# Freeze inputs locally; production/original topology directories stay read-only.
cp "$input/HEWL.gro" protein.gro
cp "$input/HEWL.top" "$input/posre.itp" "$input/HEWL-all.sites" .
cp -a "$input/Amber14SBpH.ff" .
cp "$source_root/tests/arm64/hewl-solution/"*.mdp .
run_logged version.log "$gmx" --version
run_logged box.log "$gmx" editconf -f protein.gro -o box.gro -bt dodecahedron -d 1.2
# spc216 supplies three-site coordinates; the copied topology defines TIP3P
# interactions and SETTLE geometry. It is not an SPC force-field simulation.
run_logged solvate.log "$gmx" solvate -cp box.gro \
    -cs /gromacs/gromacs-2026.3/share/gromacs/top/spc216.gro -o solvated.gro -p HEWL.top
python3 "$source_root/tests/arm64/plan_hewl_ions.py" | tee ion-plan.log
run_logged ions-grompp.log "$gmx" grompp -f ions.mdp -c solvated.gro -p HEWL.top -o ions.tpr -maxwarn 0
readarray -t counts < <(python3 -c 'import json; p=json.load(open("ion-plan.json")); print(p["positive_ions"]); print(p["negative_ions"])')
printf 'SOL\n' | run_logged genion.log "$gmx" genion -s ions.tpr -o ionized.gro -p HEWL.top \
    -np "${counts[0]}" -nn "${counts[1]}" -pname NA -nname CL -seed 1729
python3 "$source_root/tests/arm64/plan_hewl_ions.py" --index
run_logged em-grompp.log "$gmx" grompp -f minimize.mdp -c ionized.gro -r ionized.gro \
    -n index.ndx -p HEWL.top -o em.tpr -pp em-processed.top -po em-out.mdp -maxwarn 0
run_logged em-run.log "$gmx" mdrun -deffnm em -ntmpi 1 -ntomp "$threads" -pin on
python3 "$source_root/tests/arm64/check_hewl_solution.py" --minimization-only
run_logged nvt-grompp.log "$gmx" grompp -f nvt.mdp -c em.gro -r ionized.gro \
    -n index.ndx -p HEWL.top -o nvt.tpr -pp nvt-processed.top -po nvt-out.mdp -maxwarn 0
run_logged nvt-run.log "$gmx" mdrun -deffnm nvt -ntmpi 1 -ntomp "$threads" -pin on
run_logged npt-grompp.log "$gmx" grompp -f npt.mdp -c nvt.gro -t nvt.cpt -r ionized.gro \
    -n index.ndx -p HEWL.top -o npt.tpr -pp npt-processed.top -po npt-out.mdp -maxwarn 0
run_logged npt-run.log "$gmx" mdrun -deffnm npt -ntmpi 1 -ntomp "$threads" -pin on
for stage in nvt npt; do
    run_logged "$stage-xtc-check.log" "$gmx" check -f "$stage.xtc"
    run_logged "$stage-edr-check.log" "$gmx" check -e "$stage.edr"
done
printf 'Potential\nTemperature\n0\n' | run_logged nvt-energy.log "$gmx" energy -f nvt.edr -o nvt-energy.xvg
printf 'Potential\nTemperature\nPressure\nDensity\nVolume\n0\n' | run_logged npt-energy.log "$gmx" energy -f npt.edr -o npt-energy.xvg
python3 "$source_root/tests/arm64/check_hewl_solution.py"
(cd snapshot && sha256sum --quiet -c manifest.sha256)
echo 'SOLUTION_PREPARATION_AND_SNAPSHOT_PASSED' | tee result.txt
