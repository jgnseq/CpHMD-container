#!/usr/bin/env python3
"""Plan neutral HEWL ion counts and write explicit solvent/index groups.

Preparation helper for prepare_hewl_solution.sh. Target total mobile monovalent
ionic strength, including counterions, rather than adding a salt concentration
and then neutralizing on top. The second mode checks the actual genion result
and makes SOL include water plus ions for CpHMD's thermostat convention.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

AVOGADRO_NM3 = 0.602214076  # Molecules/nm^3 per mol/litre.


def read_gro(path):
    """Return fixed-column atom records and the full triclinic box volume."""
    lines = path.read_text().splitlines()
    count = int(lines[1])
    if len(lines) != count + 3:
        raise ValueError('GRO atom count/shape mismatch')
    rows = lines[2:-1]
    box = list(map(float, lines[-1].split()))
    if len(box) == 3:
        box += [0.0] * 6
    if len(box) != 9:
        raise ValueError('Expected orthogonal or triclinic GRO box')
    a, b, c = (box[0], box[3], box[4]), (box[5], box[1], box[6]), (box[7], box[8], box[2])
    volume = abs(a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0]))
    if not math.isfinite(volume) or volume <= 0:
        raise ValueError('Invalid box volume')
    return rows, volume


def ion_counts(volume, charge=9, target=0.1):
    """Choose the nearest nonnegative integer counts satisfying Nminus-Nplus=Q."""
    conversion = AVOGADRO_NM3 * volume
    minimum = abs(charge) / (2 * conversion)
    if minimum > target:
        raise ValueError('Box too small to neutralize at the requested ionic strength')
    positive = max(0, -charge, int(math.floor(target * conversion - charge / 2 + 0.5)))
    negative = positive + charge
    return {'target_ionic_strength_M': target, 'box_volume_nm3': volume,
            'protein_charge_e': charge, 'positive_ions': positive, 'negative_ions': negative,
            'actual_initial_ionic_strength_M': (positive + negative) / (2 * conversion),
            'integer_rounding_half_step_M': 1 / (2 * conversion), 'ion_placement_seed': 1729,
            'convention': 'Total mobile monovalent ions, including neutralizing counterions; box volume'}


def write_index(gro, plan):
    """Verify actual solvent/ion inventory and write disjoint thermostat groups."""
    rows, volume = read_gro(gro)
    protein = rows[:2004]
    if len(protein) != 2004 or any(row[5:10].strip() in ('SOL', 'NA', 'CL') for row in protein):
        raise ValueError('Protein must retain the first 2004 atom indices')
    solvent = rows[2004:]
    counts = Counter(row[5:10].strip() for row in solvent)
    if set(counts) - {'SOL', 'NA', 'CL'} or not counts['SOL'] or counts['SOL'] % 3:
        raise ValueError('Unexpected solvent atom inventory')
    if counts['NA'] != plan['positive_ions'] or counts['CL'] != plan['negative_ions']:
        raise ValueError('genion output differs from requested ion counts')
    if abs(volume - plan['box_volume_nm3']) > 1e-5:
        raise ValueError('Box volume changed during ion placement')
    groups = {'System': list(range(1, len(rows) + 1)), 'Protein': list(range(1, 2005)),
              'Solute': list(range(1, 2005)), 'SOL': list(range(2005, len(rows) + 1)),
              'Water': [i for i, row in enumerate(rows, 1) if row[5:10].strip() == 'SOL'],
              'Ions': [i for i, row in enumerate(rows, 1) if row[5:10].strip() in ('NA', 'CL')],
              'Backbone': [i for i, row in enumerate(protein, 1) if row[10:15].strip() in ('N', 'CA', 'C')]}
    output = []
    for name, indices in groups.items():
        output.append('[ {} ]'.format(name))
        output.extend(' '.join(map(str, indices[i:i+15])) for i in range(0, len(indices), 15))
    Path('index.ndx').write_text('\n'.join(output) + '\n')
    plan.update({'total_atoms': len(rows), 'water_molecules': counts['SOL'] // 3,
                 'thermostat_SOL_includes_ions': True, 'initial_total_charge_e': 9 + counts['NA'] - counts['CL']})
    Path('ion-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print('Verified neutral ion inventory and Protein / SOL (water+ions) groups')


def main():
    """Plan from solvated.gro, then verify ionized.gro after genion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', action='store_true')
    args = parser.parse_args()
    if args.index:
        write_index(Path('ionized.gro'), json.loads(Path('ion-plan.json').read_text()))
    else:
        rows, volume = read_gro(Path('solvated.gro'))
        plan = ion_counts(volume)
        plan['solvated_atoms_before_ions'] = len(rows)
        Path('ion-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
        print('Ion plan: {} NA / {} CL, I={:.6f} M'.format(plan['positive_ions'], plan['negative_ions'], plan['actual_initial_ionic_strength_M']))


if __name__ == '__main__':
    main()
