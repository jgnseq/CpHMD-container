#!/usr/bin/env python3
"""Verify HEWL's prepared topology and the controller-generated PB/site view.

Called inside the image after pdb2gmx and the actual make_sites function. Check
residue/atom identity, four S–S and 128 peptide bonds, distinct terminal/side-chain
sites, ST atom coverage and initial-state charges. This is preparation validation;
it runs neither the DelPhi solver nor PETIT/MD and proves no pKa convergence.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

RENAMES = {'ASP': 'AS4', 'GLU': 'GL4', 'HIS': 'HI2', 'LYS': 'LY3', 'TYR': 'TY0'}
DISULFIDES = {(6, 127), (30, 115), (64, 80), (76, 94)}


def require(condition, diagnostic):
    """Raise a readable, fatal preparation error without relying on assertions."""
    if not condition:
        raise ValueError(diagnostic)


def sections(path):
    """Read explicit topology sections; include expansion is tested by grompp."""
    result = defaultdict(list)
    section = None
    for line in path.read_text().splitlines():
        text = line.split(';', 1)[0].strip()
        header = re.fullmatch(r'\[\s*(\w+)\s*\]', text)
        if header:
            section = header[1]
        elif text and not text.startswith('#') and section:
            result[section].append(text.split())
    return result


def atoms_from_topology(data):
    """Return numbered atoms with identity, charge and mass from [ atoms ]."""
    atoms = []
    for row in data['atoms']:
        require(len(row) >= 8, 'Incomplete topology atom row')
        atoms.append({'number': int(row[0]), 'type': row[1], 'residue_number': int(row[2]),
                      'residue_name': row[3], 'name': row[4], 'charge': float(row[6]),
                      'mass': float(row[7])})
    require([a['number'] for a in atoms] == list(range(1, len(atoms) + 1)), 'Nonsequential atom indices')
    return atoms


def state_atoms(path, family):
    """Read an ST's atom names and protonated/deprotonated charge columns."""
    result = {}
    for line in path.read_text().splitlines()[1:]:
        row = line.split()
        if not row or row[0].startswith('#'):
            continue
        require(len(row) == 4 and row[0] == family, 'Unexpected ST row in ' + str(path))
        require(row[1] not in result, 'Duplicate ST atom in ' + str(path))
        result[row[1]] = (float(row[2]), float(row[3]))
    require(bool(result), 'Empty ST atom definition: ' + str(path))
    require(abs(sum(charges[0] - charges[1] for charges in result.values()) - 1) < 5e-4,
            'ST protonated/deprotonated charge difference is not +1: ' + str(path))
    return result


def verify(root, st_dir):
    """Validate both MD and PB topology views against the same deposited chain.

    The initial LY3 residue 1 has two independent sites: its lysine side chain
    and its N terminus. Ownership is therefore (residue number, atom name), not
    just residue number. PB labels NTR/CTR must not change indices or charges.
    """
    original = {}
    for line in (root / 'protein.pdb').read_text().splitlines():
        if line.startswith('ATOM  '):
            original[int(line[22:26])] = line[17:20]
    require(sorted(original) == list(range(1, 130)), 'Original residue numbering differs from 1–129')
    # GROMACS retains CYS as the coordinate/topology residue label while using
    # the oxidized CYX RTP block. Verify both identities rather than requiring
    # the intermediate CYS2 specbond alias to appear in the final GRO.
    expected_names = {number: RENAMES.get(name, name)
                      for number, name in original.items()}
    converted = {}
    for line in (root / 'protein_CpHMD.pdb').read_text().splitlines():
        if line.startswith('ATOM  '):
            converted[int(line[22:26])] = line[17:20]
    require(converted == {n: RENAMES.get(name, name) for n, name in original.items()},
            'pdb2cphmd changed an unexpected residue or missed a titrating residue')
    data = sections(root / 'HEWL.top')
    building_blocks = {int(match[1]): match[3] for line in (root / 'HEWL.top').read_text().splitlines()
                       if (match := re.match(r'; residue\s+(\d+)\s+(\S+)\s+rtp\s+(\S+)', line))}
    require(len(building_blocks) == 129, 'Missing pdb2gmx residue/RTP provenance')
    require(all(building_blocks[n] == 'CYX' for n, name in original.items() if name == 'CYS'),
            'Disulfide cysteine did not use the oxidized CYX RTP block')
    require(building_blocks[129] == 'CLEU', 'C terminus must retain the supplied CLEU RTP block')
    atoms = atoms_from_topology(data)
    pb_atoms = atoms_from_topology(sections(root / 'TMP_CpHMD_charge.top'))
    require(len(atoms) == len(pb_atoms) == 2004, 'Expected 2004 atoms including CpHMD dummy hydrogens')
    gro = (root / 'HEWL.gro').read_text().splitlines()
    require(int(gro[1]) == len(atoms) and len(gro) == len(atoms) + 3, 'GRO atom count/shape mismatch')
    grouped = defaultdict(dict)
    for atom, pb, row in zip(atoms, pb_atoms, gro[2:-1]):
        number = atom['residue_number']
        require(atom['residue_name'] == expected_names[number], 'Wrong residue name at ' + str(number))
        require((int(row[:5]), row[5:10].strip(), row[10:15].strip(), int(row[15:20])) ==
                (number, atom['residue_name'], atom['name'], atom['number']), 'GRO/TOP atom identity/order mismatch')
        require(all(atom[key] == pb[key] for key in ('number', 'type', 'residue_number', 'name', 'charge', 'mass')),
                'PB label materialization changed physical atom properties')
        require(atom['name'] not in grouped[number], 'Duplicate atom name within residue ' + str(number))
        grouped[number][atom['name']] = pb
    bonds = [tuple(sorted((int(row[0]), int(row[1])))) for row in data['bonds']]
    require(len(bonds) == len(set(bonds)), 'Duplicate explicit bonds')
    bond_set = set(bonds)
    by_number = {atom['number']: atom for atom in atoms}
    observed = set()
    for first, second in bond_set:
        a, b = by_number[first], by_number[second]
        if a['name'] == b['name'] == 'SG':
            observed.add(tuple(sorted((a['residue_number'], b['residue_number']))))
        if a['name'] == 'SG' or b['name'] == 'SG':
            other = b if a['name'] == 'SG' else a
            require(not other['name'].startswith('H'), 'Disulfide sulfur is bonded to a thiol hydrogen')
    require(observed == DISULFIDES, 'Missing or incorrect disulfide connectivity')
    for number in range(1, 129):
        require(tuple(sorted((grouped[number]['C']['number'], grouped[number + 1]['N']['number']))) in bond_set,
                'Missing peptide bond after residue ' + str(number))
    n_index = grouped[1]['N']['number']
    n_neighbors = {by_number[b if a == n_index else a]['name'] for a, b in bond_set if n_index in (a, b)}
    require(n_neighbors == {'CA', 'H1', 'H2', 'H3'}, 'Incorrect N-terminal NH3+ connectivity')
    # A second carboxyl TDB patch can retain every atom/charge yet miswire the
    # dummy hydrogens. Check the full terminal subgraph, not just its atom list.
    terminal = grouped[129]
    for name, neighbors in {'C': {'CA', 'OC1', 'OC2'},
                            'OC1': {'C', 'HC11', 'HC12'}, 'OC2': {'C', 'HC21', 'HC22'},
                            'HC11': {'OC1'}, 'HC12': {'OC1'},
                            'HC21': {'OC2'}, 'HC22': {'OC2'}}.items():
        index = terminal[name]['number']
        actual = {by_number[b if a == index else a]['name'] for a, b in bond_set if index in (a, b)}
        require(actual == neighbors, 'Incorrect C-terminal connectivity at ' + name)
    total_charge = sum(atom['charge'] for atom in atoms)
    require(abs(total_charge - 9) < 1e-4, 'Initial topology charge differs from +9 e')
    expected_sites = {(number, name) for number, name in original.items() if name in RENAMES}
    expected_sites.update({(1, 'NTR'), (129, 'CTR')})
    found_sites, report, ownership = set(), [], {}
    for line in (root / 'HEWL-all.sites').read_text().splitlines():
        fields = line.split()
        require(len(fields) >= 2, 'Empty/incomplete generated site row')
        number = int(fields[0])
        families = [re.fullmatch(r'([A-Z]+)tau\d+', name) for name in fields[1:]]
        require(all(families), 'Unrecognized tautomer name')
        family = families[0][1]
        require(all(match[1] == family for match in families), 'Mixed site families in one row')
        identity = (number, family)
        require(identity in expected_sites and identity not in found_sites, 'Unexpected/duplicate generated site ' + str(identity))
        found_sites.add(identity)
        st_paths = sorted(st_dir.glob(family + 'tau*.st'))
        require(set(fields[1:]) == {path.stem for path in st_paths} and len(fields[1:]) == len(st_paths),
                'Generated site does not cover exactly the installed tautomer definitions')
        states = [state_atoms(path, family) for path in st_paths]
        names = set(states[0])
        require(all(set(state) == names for state in states), 'Tautomer atom-name sets differ')
        require(names.issubset(grouped[number]), 'Missing topology atoms required by ST: ' + str(identity))
        for name in names:
            key = (number, name)
            require(key not in ownership, 'Overlapping side-chain/terminal site atom: ' + str(key))
            ownership[key] = family
            expected_label = family if family in ('NTR', 'CTR') else expected_names[number]
            require(grouped[number][name]['residue_name'] == expected_label, 'Wrong PB residue label for ' + str(key))
        # Map the chosen starting residue/terminal patch to its ST charge state.
        column = 1 if family in ('ASP', 'GLU', 'CTR') else 0
        errors = [max(abs(grouped[number][name]['charge'] - state[name][column]) for name in names) for state in states]
        require(min(errors) < 1e-4, 'Initial topology charges do not match any intended ST state: ' + str(identity))
        report.append({'residue_number': number, 'family': family, 'tautomers': fields[1:],
                       'atom_names': sorted(names), 'initial_state': 'deprotonated' if column else 'protonated',
                       'best_st_charge_error': min(errors)})
    require(found_sites == expected_sites and len(found_sites) == 21, 'Missing generated sites; expected 21')
    return {'status': 'TOPOLOGY_AND_SITE_IDENTITY_PASSED', 'atom_count': len(atoms),
            'residue_count': 129, 'residue_name_counts': dict(Counter(expected_names.values())),
            'disulfide_pairs': sorted(observed), 'peptide_bonds_verified': 128,
            'disulfide_residue_label': 'CYS', 'disulfide_rtp_block': 'CYX',
            'initial_charge_e': round(total_charge, 6), 'site_count': len(report), 'sites': report,
            'source_file_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                   for name in ('HEWL.top', 'HEWL.gro', 'HEWL-all.sites', 'TMP_CpHMD_charge.top')},
            'pending': ['solvation/ions and equilibration', 'fixed-coordinate PB/MC comparison', 'CpHMD/RT/batch restart validation']}


def main():
    """Write the machine-readable successful audit only after every check passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--st-dir', type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.directory, args.st_dir)
    (args.directory / 'topology-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: 2004 atoms, four disulfides, 21 independent sites and matching ST charges; initial charge +9 e')


if __name__ == '__main__':
    main()
