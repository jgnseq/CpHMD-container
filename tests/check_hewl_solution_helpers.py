#!/usr/bin/env python3
"""Check scientific input bookkeeping independently of the native MD job.

Exercise neutrality/ionic-strength rounding, triclinic volume, energy-column
identity and finite/time checks. These portable gates do not simulate HEWL or
replace inspection of the native preparation outputs.
"""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests/arm64'))
from plan_hewl_ions import ion_counts, read_gro
from check_hewl_solution import xvg


class SolutionBookkeepingTests(unittest.TestCase):
    """Protect the physical meaning of generated counts and analysis columns."""

    def test_neutrality_and_nearest_integer_strength(self):
        """Counterions count toward I; compare the chosen counts to adjacent pairs."""
        for volume in (100, 150, 200):
            plan = ion_counts(volume)
            plus, minus = plan['positive_ions'], plan['negative_ions']
            self.assertEqual(minus - plus, 9)
            error = abs(plan['actual_initial_ionic_strength_M'] - .1)
            self.assertLessEqual(error, plan['integer_rounding_half_step_M'] + 1e-12)
            conversion = .602214076 * volume
            for shift in (-1, 1):
                if plus + shift >= 0:
                    neighbor = (plus + minus + 2 * shift) / (2 * conversion)
                    self.assertLessEqual(error, abs(neighbor - .1) + 1e-12)

    def test_negative_protein_charge(self):
        """The bookkeeping also handles excess positive counterions correctly."""
        plan = ion_counts(150, charge=-9)
        self.assertEqual(plan['positive_ions'] - plan['negative_ions'], 9)

    def test_impossible_neutralization_strength(self):
        """Do not silently claim 0.1 M when counterions alone already exceed it."""
        with self.assertRaisesRegex(ValueError, 'Box too small'):
            ion_counts(10)

    def test_triclinic_volume(self):
        """Use the determinant, preserving the off-diagonal GRO component order."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'box.gro'
            p.write_text('Triclinic test\n0\n2 3 4 0 0 0 0 1 1\n')
            rows, volume = read_gro(p)
            self.assertEqual(rows, [])
            self.assertEqual(volume, 24)

    def energy_file(self, root, values):
        """Create a deliberately reordered labeled XVG fixture."""
        p = Path(root) / 'energy.xvg'
        p.write_text('@ s0 legend "Temperature"\n@ s1 legend "Potential"\n' + values)
        return p

    def test_energy_columns_by_name(self):
        """Temperature must not depend on the order requested from gmx energy."""
        with tempfile.TemporaryDirectory() as tmp:
            p = self.energy_file(tmp, '0 310 -100\n1 311 -101\n2 309 -102\n')
            rows, names = xvg(p, ['Potential', 'Temperature'])
            self.assertEqual(rows[1][names['Temperature']], 311)
            self.assertEqual(rows[1][names['Potential']], -101)

    def test_nonfinite_energy_rejected(self):
        """A nonempty energy file with NaN is not valid output."""
        with tempfile.TemporaryDirectory() as tmp:
            p = self.energy_file(tmp, '0 310 -100\n1 nan -101\n2 309 -102\n')
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                xvg(p, ['Potential', 'Temperature'])

    def test_duplicate_energy_times_rejected(self):
        """Reject repeated/non-increasing records rather than averaging them."""
        with tempfile.TemporaryDirectory() as tmp:
            p = self.energy_file(tmp, '0 310 -100\n0 311 -101\n2 309 -102\n')
            with self.assertRaisesRegex(ValueError, 'Non-increasing'):
                xvg(p, ['Potential', 'Temperature'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
