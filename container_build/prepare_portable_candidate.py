#!/usr/bin/env python3
"""Derive a portable-target build context after the native generic solver build.

Called by build-portable-arm64.slurm on Deucalion. The uploaded seed stays
immutable. Copy it into a fresh candidate, add only the compiled -tp=px runtime
and provenance, select armv8-a/ASIMD everywhere, then regenerate all manifests
and recipe hashes before the existing rootfs build driver runs. No Git operation
or job submission occurs here. Compatible with login-node Python 3.6.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def digest(path):
    """Identify large binary/source payloads with bounded memory use."""
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def main():
    """Create a fresh derived context with explicit baseline and pending claims."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('seed', type=Path)
    parser.add_argument('solver', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    seed, solver, output = [path.resolve() for path in (args.seed, args.solver, args.output)]
    subprocess.run(['sha256sum', '--quiet', '-c', 'manifest.sha256'], cwd=str(seed), check=True)
    metadata = json.loads((seed / 'build.json').read_text())
    assert digest(seed / 'manifest.sha256') == metadata['manifest_sha256']
    assert metadata['portable_derivation_seed'] and metadata['simd'] == 'ARM_NEON_ASIMD'
    assert digest(seed / 'CpHMD.arm64.def') == metadata['definition_sha256']
    provenance = json.loads((solver / 'provenance.json').read_text())
    assert provenance['target'] == 'px' and '-tp=px' in provenance['fortran_flags'].split()
    assert not any(value in provenance['fortran_flags'] for value in ('a64fx', '-fast', '-tp=host', '-tp=native'))
    assert not output.exists()
    shutil.copytree(str(seed), str(output))
    stage = output / 'context/portable-delphi'
    stage.mkdir()
    shutil.copytree(str(solver / 'runtime'), str(stage / 'runtime'))
    shutil.copyfile(str(solver / 'provenance.json'), str(stage / 'provenance.json'))
    for name, expected in provenance['runtime_sha256'].items():
        assert Path(name).name == name and digest(stage / 'runtime' / name) == expected
    metadata.update(isa_profile='portable-armv8-a', build_profile='portable', candidate_solver_target='px', sve_bits=0,
        portability_note='Generic ARM64 Linux target; native A64FX validation does not establish all-device support.',
        cross_hardware_validation='non-SVE execution pending', solver_provenance=provenance,
        parent_seed_manifest_sha256=digest(seed / 'manifest.sha256'))
    manifest = ''.join('{}  {}\n'.format(digest(path), path.relative_to(output))
                       for path in sorted((output / 'context').rglob('*')) if path.is_file())
    (output / 'manifest.sha256').write_text(manifest)
    metadata['manifest_sha256'] = digest(output / 'manifest.sha256')
    recipe = (seed / 'CpHMD.arm64.def').read_text()
    recipe = re.sub(r'(?m)^    source.manifest.sha256 .*$',
                    '    source.manifest.sha256 ' + metadata['manifest_sha256'], recipe)
    for key, value in [('cpu.profile', 'portable-armv8-a'), ('cpu.baseline', 'armv8-a+asimd'),
                       ('cphmd.delphi-target', 'px'), ('portability.status', 'non-SVE-execution-pending')]:
        pattern = r'(?m)^    ' + re.escape(key) + r' .*$'
        if re.search(pattern, recipe):
            recipe = re.sub(pattern, '    ' + key + ' ' + value, recipe)
        else:
            recipe = recipe.replace('%labels\n', '%labels\n    ' + key + ' ' + value + '\n', 1)
    (output / 'CpHMD.arm64.def').write_text(recipe)
    metadata['definition_sha256'] = digest(output / 'CpHMD.arm64.def')
    (output / 'build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('Prepared portable-target candidate:', output)


if __name__ == '__main__':
    main()
