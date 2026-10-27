#!/usr/bin/env python3
"""Regress the scientific input audit using the real passing x86 HEWL fixture.

No simulation/container is needed: preserve the baseline, mutate copied inputs
and require rejection of lost sites, broken S–S/terminal bonds, wrong residue
conversion and state-table charge disagreement. This is a manual validation
fixture; canonical preparation changes and CI adoption are deferred.
"""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('hewl_audit', REPO / 'tests/arm64/check_hewl_topology.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
FIXTURE = REPO / 'docs/aarch64/evidence/2026-10-27/hewl-topology/x86/topology'
INPUTS = ['protein.pdb', 'protein_CpHMD.pdb', 'HEWL.top', 'HEWL.gro',
          'TMP_CpHMD_charge.top', 'HEWL-all.sites']


def change_bond(path, first, second, replacement=None):
    """Alter exactly one explicit bond in a copied topology; leave atoms intact."""
    lines, active, changed = [], False, 0
    for line in path.read_text().splitlines(keepends=True):
        stripped = line.split(';', 1)[0].strip()
        if stripped.startswith('['):
            active = stripped == '[ bonds ]'
        row = stripped.split()
        if active and row and row[0].isdigit() and set(map(int, row[:2])) == {first, second}:
            changed += 1
            if replacement:
                lines.append('{} {} 1\n'.format(*replacement))
            continue
        lines.append(line)
    if changed != 1:
        raise AssertionError('Mutation did not target exactly one bond')
    path.write_text(''.join(lines))


class TopologyAuditTests(unittest.TestCase):
    """Check actual HEWL invariants without modifying the saved evidence."""

    def setUp(self):
        """Make disposable copies of only the inputs needed by the pure audit."""
        self.temporary = tempfile.TemporaryDirectory(prefix='cphmd-hewl-audit-')
        self.root = Path(self.temporary.name)
        for name in INPUTS:
            shutil.copy2(FIXTURE / name, self.root / name)
        self.st_dir = REPO / 'STs/St-Amber14SBpH'

    def tearDown(self):
        """Remove only this test's disposable copies."""
        self.temporary.cleanup()

    def test_real_baseline(self):
        """The actual generated input retains 21 sites and all disulfides."""
        report = audit.verify(self.root, self.st_dir)
        self.assertEqual(report['site_count'], 21)
        self.assertEqual(report['atom_count'], 2004)
        self.assertEqual(report['initial_charge_e'], 9)

    def test_missing_n_terminal_site(self):
        """Residue 1's side chain must not hide a missing N-terminal site."""
        p = self.root / 'HEWL-all.sites'
        p.write_text(''.join(row for row in p.read_text().splitlines(keepends=True) if 'NTRtau' not in row))
        with self.assertRaisesRegex(ValueError, 'Missing generated sites'):
            audit.verify(self.root, self.st_dir)

    def test_missing_disulfide(self):
        """Cysteine names alone do not establish an S–S bond."""
        atoms = audit.atoms_from_topology(audit.sections(self.root / 'HEWL.top'))
        sulfur = {a['residue_number']: a['number'] for a in atoms if a['name'] == 'SG'}
        change_bond(self.root / 'HEWL.top', sulfur[6], sulfur[127])
        with self.assertRaisesRegex(ValueError, 'disulfide connectivity'):
            audit.verify(self.root, self.st_dir)

    def test_wrong_carboxyl_dummy_bond(self):
        """Reject the class of miswiring caused by applying CLEU and a TDB twice."""
        atoms = audit.atoms_from_topology(audit.sections(self.root / 'HEWL.top'))
        terminal = {a['name']: a['number'] for a in atoms if a['residue_number'] == 129}
        change_bond(self.root / 'HEWL.top', terminal['OC1'], terminal['HC11'],
                    (terminal['OC2'], terminal['HC11']))
        with self.assertRaisesRegex(ValueError, 'C-terminal connectivity'):
            audit.verify(self.root, self.st_dir)

    def test_accidental_cysteine_titration_name(self):
        """Oxidized cysteines must not be converted to CY0 thiol sites."""
        p = self.root / 'protein_CpHMD.pdb'
        p.write_text(p.read_text().replace('CYS A   6', 'CY0 A   6'))
        with self.assertRaisesRegex(ValueError, 'unexpected residue'):
            audit.verify(self.root, self.st_dir)

    def test_state_charge_disagreement(self):
        """Reject mismatched ST charges even when each state still changes by +1."""
        copied = self.root / 'states'
        shutil.copytree(self.st_dir, copied)
        for p in copied.glob('LYStau*.st'):
            rows = p.read_text().splitlines()
            for i, row in enumerate(rows):
                fields = row.split()
                if len(fields) == 4 and fields[1] == 'CB':
                    fields[2:] = ['{:.4f}'.format(float(value) + 0.005) for value in fields[2:]]
                    rows[i] = ' '.join(fields)
            p.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'charges do not match'):
            audit.verify(self.root, copied)


if __name__ == '__main__':
    unittest.main(verbosity=2)
