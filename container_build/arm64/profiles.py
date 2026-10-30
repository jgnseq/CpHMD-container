#!/usr/bin/env python3
"""Shared ARM build policy for the preparer, workstation CLI and rootfs gate.

Portable is the default. An optimized solver/SVE build requires explicit A64FX
selection. Bootstrap hashes identify previously validated, immutable images;
they do not transfer scientific acceptance to a newly built candidate.
This module remains compatible with the login node's Python 3.6.
"""
import argparse

PROFILES = {
    'portable': {
        'base_sha256': 'dd7872704d2a8780ea52b4e3003c5a0519d8bbc20d179069df740a010b2ce479',
        'base_relative_path': 'portable.20261028.MZWHAj/candidate/CpHMD-arm64.sif',
        'isa_profile': 'portable-armv8-a', 'default_simd': 'ARM_NEON_ASIMD',
        'cpu_baseline': 'armv8-a+asimd', 'delphi_target': 'px',
        'delphi_sha256': '1326727ff2a2a7e64279acec6d06d1e3d4e4b894ca7c62ef205af754c187f713',
        'portability_note': 'Baseline Linux ARM64 target; new candidate execution gates remain required.'},
    'a64fx': {
        'base_sha256': '1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d',
        'base_relative_path': 'validation/hewl-4lzt/solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif',
        'isa_profile': 'a64fx-reference', 'default_simd': 'ARM_SVE',
        'cpu_baseline': 'a64fx-specific', 'delphi_target': 'a64fx',
        'portability_note': 'Hardware-specific reference; selecting NEON alone does not make its DelPhi portable.'}}


def select_profile(name='portable', simd=None):
    """Resolve an explicit policy; never infer the target from the build host."""
    if name not in PROFILES:
        raise ValueError('Use portable or a64fx profile')
    result = dict(PROFILES[name])
    simd = result['default_simd'] if simd is None else simd
    if simd not in ('ARM_NEON_ASIMD', 'ARM_SVE'):
        raise ValueError('Unsupported ARM SIMD selection')
    if name == 'portable' and simd != 'ARM_NEON_ASIMD':
        raise ValueError('Portable requires ARM_NEON_ASIMD; use --profile a64fx explicitly for SVE')
    result.update(name=name, simd=simd, sve_bits=512 if simd == 'ARM_SVE' else 0)
    return result


def validate_generic_solver(provenance):
    """Reject mixed CPU targets and unsafe math in a declared generic runtime."""
    flags = provenance['fortran_flags'].split()
    assert provenance['target'] == 'px'
    assert [flag for flag in flags if flag.startswith('-tp=')] == ['-tp=px']
    assert '-Kieee' in flags and not any(flag in flags for flag in ('-fast', '-Ofast', '-ffast-math'))
    c_flags = provenance['c_flags'].split()
    assert [flag for flag in c_flags if flag.startswith('-march=')] == ['-march=armv8-a']
    assert '-mtune=generic' in c_flags and not any(flag in c_flags for flag in ('-Ofast', '-ffast-math'))


def main():
    """Print fixed data lines for Bash; callers consume data without shell eval."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=sorted(PROFILES), default='portable')
    parser.add_argument('--simd', choices=['ARM_NEON_ASIMD', 'ARM_SVE'])
    args = parser.parse_args()
    try:
        profile = select_profile(args.profile, args.simd)
    except ValueError as error:
        parser.error(str(error))
    for name in ('name', 'simd', 'base_relative_path', 'base_sha256'):
        print(profile[name])


if __name__ == '__main__':
    main()
