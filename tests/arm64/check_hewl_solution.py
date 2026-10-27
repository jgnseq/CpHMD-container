#!/usr/bin/env python3
"""Check bounded HEWL solution preparation and freeze a portable snapshot.

Called after minimization and after restrained NVT/NPT. Require converged contact
minimization, complete finite energy/coordinate output, preserved protein/site
identity and disulfides, neutral ion inventory, plausible temperature/density.
These health gates do not establish thermodynamic or protonation convergence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from statistics import mean

from check_hewl_topology import sections, atoms_from_topology
from plan_hewl_ions import read_gro, AVOGADRO_NM3


def xvg(path, names):
    """Read finite energy columns by their actual legends, not selection order."""
    text = path.read_text()
    legends = {match[2]: int(match[1]) + 1 for match in
               re.finditer(r'@\s+s(\d+)\s+legend\s+"([^"]+)"', text)}
    if set(legends) != set(names):
        raise ValueError('Unexpected energy columns: ' + str(legends))
    rows = [list(map(float, line.split())) for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith(('#', '@'))]
    if len(rows) < 3 or any(len(row) != len(names) + 1 or not all(math.isfinite(v) for v in row) for row in rows):
        raise ValueError('Incomplete/nonfinite energy data: ' + str(path))
    if any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError('Non-increasing energy time: ' + str(path))
    return rows, legends


def check_minimization(root):
    """Demand the declared Fmax <1000 kJ/mol/nm criterion before integrating."""
    text = (root / 'em.log').read_text()
    matches = re.findall(r'Maximum force\s*=\s*([0-9.eE+\-]+)', text)
    if not matches or not math.isfinite(float(matches[-1])) or float(matches[-1]) >= 1000:
        raise ValueError('Contact minimization did not reach Fmax <1000 kJ/mol/nm')
    if not (root / 'em.gro').is_file():
        raise ValueError('Missing minimized coordinates')
    print('PASS: minimization Fmax={:.3f} kJ/mol/nm'.format(float(matches[-1])))
    return float(matches[-1])


def check_final(root):
    """Validate actual short equilibration outputs, then create a new snapshot."""
    maximum_force = check_minimization(root)
    plan = json.loads((root / 'ion-plan.json').read_text())
    initial, initial_volume = read_gro(root / 'ionized.gro')
    final, final_volume = read_gro(root / 'npt.gro')
    if len(final) != plan['total_atoms'] or len(final) != len(initial):
        raise ValueError('Final atom inventory changed')
    if any(p[:20] != q[:20] for p, q in zip(initial, final)):
        raise ValueError('Atom identities/order changed during preparation')
    if not all(math.isfinite(float(row[i:i+8])) for row in final for i in (20, 28, 36)):
        raise ValueError('Nonfinite final coordinates')
    top = sections(root / 'HEWL.top')
    protein = atoms_from_topology(top)
    if len(protein) != 2004:
        raise ValueError('Protein topology atom inventory changed')
    charge = sum(atom['charge'] for atom in protein)
    molecules = {row[0]: int(row[1]) for row in top['molecules']}
    expected = {'Protein_chain_A': 1, 'SOL': plan['water_molecules'],
                'NA': plan['positive_ions'], 'CL': plan['negative_ions']}
    if set(molecules) - set(expected) or any(molecules.get(name, 0) != value for name, value in expected.items()):
        raise ValueError('Topology molecule inventory does not match coordinates')
    if abs(charge + plan['positive_ions'] - plan['negative_ions']) > 1e-4:
        raise ValueError('Initial ionized system is not neutral')
    # Protein is restrained and remains whole in this preparation. Independently
    # check the final S–S distances; a split/wrapped protein requires inspection.
    sulfur = {atom['residue_number']: atom['number'] for atom in protein if atom['name'] == 'SG'}
    distances = []
    for first, second in ((6, 127), (30, 115), (64, 80), (76, 94)):
        a, b = final[sulfur[first]-1], final[sulfur[second]-1]
        distance = math.sqrt(sum((float(a[i:i+8])-float(b[i:i+8]))**2 for i in (20, 28, 36)))
        if not 0.18 < distance < 0.23:
            raise ValueError('Final S–S distance requires inspection: {} {}'.format(first, second))
        distances.append({'pair': [first, second], 'distance_nm': distance})
    stages = {}
    for stage, duration, names in [('nvt', 10, ['Potential', 'Temperature']),
                                    ('npt', 20, ['Potential', 'Temperature', 'Pressure', 'Density', 'Volume'])]:
        log = (root / (stage + '.log')).read_text()
        if re.search(r'LINCS WARNING|Fatal error|Constraint error|can not be settled', log, re.I):
            raise ValueError('Integration/constraint diagnostic in ' + stage)
        rows, legends = xvg(root / (stage + '-energy.xvg'), names)
        if abs(rows[-1][0] - rows[0][0] - duration) > 0.01:
            raise ValueError('Incomplete requested integration duration: ' + stage)
        tail = rows[len(rows)//2:]
        temperature = mean(row[legends['Temperature']] for row in tail)
        if not 290 <= temperature <= 330:
            raise ValueError('Tail temperature outside preparation health range: ' + stage)
        stages[stage] = {'duration_ps': duration, 'tail_temperature_K': temperature,
                         'energy_records': len(rows), 'all_selected_energy_records_finite': True}
        if stage == 'npt':
            density = mean(row[legends['Density']] for row in tail)
            volume = mean(row[legends['Volume']] for row in tail)
            if not 800 <= density <= 1200 or not 0.8 <= final_volume / initial_volume <= 1.2:
                raise ValueError('NPT density/volume needs inspection')
            stages[stage].update({'tail_density_kg_m3': density, 'tail_volume_nm3': volume,
                                  'tail_pressure_bar': mean(row[legends['Pressure']] for row in tail)})
    report = {'status': 'BOUNDED_SOLUTION_PREPARATION_PASSED', 'minimization_Fmax_kJ_mol_nm': maximum_force,
              'ion_plan': plan, 'stages': stages, 'disulfide_distances': distances,
              'final_box_volume_nm3': final_volume,
              'final_mobile_ionic_strength_M': (plan['positive_ions']+plan['negative_ions'])/(2*AVOGADRO_NM3*final_volume),
              'warning_policy': 'Every grompp uses maxwarn 0',
              'scope': 'Restrained 10+20 ps validation preparation, not production/equilibration convergence',
              'pending': ['matched-source fixed-coordinate PB/MC', 'CpHMD all-site/RT and batch restart validation']}
    (root / 'solution-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    snapshot = root / 'snapshot'
    snapshot.mkdir()
    for original, dest in [('npt.gro', 'HEWL.gro'), ('HEWL.top', 'HEWL.top'), ('index.ndx', 'index.ndx'),
                            ('posre.itp', 'posre.itp'), ('HEWL-all.sites', 'HEWL-all.sites'),
                            ('solution-audit.json', 'solution-audit.json')]:
        shutil.copy2(root / original, snapshot / dest)
    # The FF scripts directory contains architecture-specific legacy binaries
    # and is not included by the topology; omit it from this portable input set.
    shutil.copytree(root / 'Amber14SBpH.ff', snapshot / 'Amber14SBpH.ff', ignore=shutil.ignore_patterns('scripts'))
    manifest = ['{}  {}'.format(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(snapshot))
                for p in sorted(snapshot.rglob('*')) if p.is_file()]
    (snapshot / 'manifest.sha256').write_text('\n'.join(manifest) + '\n')
    print('PASS: restrained solution preparation; portable snapshot frozen')


def main():
    """Select the pre-integration minimization gate or the final snapshot gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minimization-only', action='store_true')
    args = parser.parse_args()
    if args.minimization_only:
        check_minimization(Path.cwd())
    else:
        check_final(Path.cwd())


if __name__ == '__main__':
    main()
