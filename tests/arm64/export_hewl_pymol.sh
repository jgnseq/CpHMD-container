#!/bin/bash
# Visualization-only export of job 2149846. Run inside either GROMACS 2026.3
# image with the original solution directory mounted read-only. Two trjconv
# passes make molecules whole/centered, then remove rigid-body translation and
# rotation by fitting the backbone. Keep each stage's original time axis.
set -Eeuo pipefail
input="$(realpath "${1:?Supply the original solution directory}")"
output="${2:?Supply a new export directory}"
mkdir "$output"
cd "$output"
export GMX_MAXBACKUP=-1 OMP_NUM_THREADS=1
gmx=/gromacs/bin/gmx
"$gmx" --version > gromacs-version.txt 2>&1
for phase in nvt npt; do
    printf 'Protein\nSystem\n' | "$gmx" trjconv -f "$input/$phase.xtc" \
        -s "$input/$phase.tpr" -n "$input/index.ndx" \
        -o "$phase-centered.xtc" -pbc mol -center > "$phase-center.log" 2>&1
    printf 'Backbone\nProtein\n' | "$gmx" trjconv -f "$phase-centered.xtc" \
        -s "$input/$phase.tpr" -n "$input/index.ndx" \
        -o "$phase-protein-native.pdb" -fit rot+trans > "$phase-fit.log" 2>&1
done
# An unfitted solvent/ion view retains the actual final periodic box. The
# compact unit-cell representation is for display only, not a PB/MC input.
printf 'Protein\nSystem\n' | "$gmx" trjconv -f "$input/npt.gro" \
    -s "$input/npt.tpr" -n "$input/index.ndx" -o final-system.pdb \
    -pbc mol -center -ur compact > final-system.log 2>&1
"$gmx" editconf -f "$input/em.gro" -n "$input/index.ndx" \
    -o minimized-native.pdb -label A <<<'Protein' > minimized.log 2>&1
sha256sum "$input"/{nvt,npt}.{xtc,tpr} "$input"/npt.gro > source-sha256.txt
