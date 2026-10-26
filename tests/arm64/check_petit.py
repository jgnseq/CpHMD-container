#!/usr/bin/env python3
"""Gate the MC executable used after PB energies in each CpHMD cycle.

An isolated one-site/two-state model has an analytic occupancy, so this fixture
can check the native binary independently of DelPhi and MD. Run by host support
checks and image %test; it does not replace the fixed-coordinate PB/MC comparison.
"""
import argparse
import math
from pathlib import Path
import subprocess

def check_ph(binary, ph):
    """Compare sampled occupancy at one pH to 1/(1+10**pH).

    Fix seed/chain length, distinguish site rows from total-protonation rows,
    and allow 0.02 sampling error. This is a stochastic smoke-test tolerance,
    not a cross-architecture scientific acceptance threshold.
    """
    result = subprocess.run(
        [str(binary.resolve()), '-H', f'{ph},{ph},1', '-q', '1000',
         '-r', '1729', '100000'], input='1\nTEST-1 2 P *\n0 0\n1 0\n',
        text=True, capture_output=True, check=True, timeout=30,
    )
    rows = [fields for line in result.stdout.splitlines()
            if line.startswith('. ')
            and len(fields := line.split()) == 7 and fields[3].isdigit()]
    finals = [line.split() for line in result.stdout.splitlines()
              if line.startswith('f ')]
    if len(rows) != 1 or len(finals) != 1 or len(finals[0]) != 2:
        raise AssertionError('Unexpected PETIT site/final-state output')
    mean, p0, p1 = map(float, rows[0][4:7])
    expected = 1 / (1 + 10 ** ph)
    if not all(math.isfinite(p) and 0 <= p <= 1 for p in (mean, p0, p1)):
        raise AssertionError('Non-finite or invalid probabilities')
    if abs(p0 + p1 - 1) > 1e-6 or abs(p1 - expected) > 0.02:
        raise AssertionError(f'pH={ph}: {p1} differs from analytic {expected}')
    print(f'PASS: PETIT pH={ph}, observed={p1:.6f}, analytic={expected:.6f}')


def main():
    """Test both saturated limits and the half-occupied state at pH zero."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    args = parser.parse_args()
    for ph in (-1, 0, 1):
        check_ph(args.binary, ph)


if __name__ == '__main__':
    main()
