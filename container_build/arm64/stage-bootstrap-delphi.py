#!/usr/bin/env python3
"""Stage the pinned generic solver before clearing inherited rootfs payloads.

Called only in portable %post. A legacy derivation can provide its own generic
runtime context; a normal portable build retains the already validated runtime
from the exact portable bootstrap. Every retained byte and ELF header is checked
before staging. install-portable-delphi.py then installs the same explicit
payload after the old native-library tree has been removed. Host files and the
original SIF are never modified. The root argument supports inert unit fixtures.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil

from profiles import PROFILES, validate_generic_solver


def digest(path):
    """Hash libraries with bounded memory use."""
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def stage_bootstrap(root):
    """Verify the bootstrap runtime, then create a new explicit install context."""
    metadata = json.loads((root / 'etc/cphmd/build.json').read_text())
    assert metadata['isa_profile'] == 'portable-armv8-a'
    stage = root / 'opt/cphmd-build/portable-delphi'
    if stage.exists():
        assert (stage / 'provenance.json').is_file()
        print('Generic solver supplied by the frozen context; installer will verify it')
        return
    assert metadata['base_sha256'] == PROFILES['portable']['base_sha256'], 'Wrong portable bootstrap'
    report = json.loads((root / 'usr/share/cphmd/build/delphi-portable.json').read_text())
    assert report['compiler_target'] == 'px'
    provenance = report['provenance']
    validate_generic_solver(provenance)
    assert provenance['runtime_sha256']['delphi_pgf90'] == PROFILES['portable']['delphi_sha256']
    sources = {}
    for name, expected in provenance['runtime_sha256'].items():
        assert Path(name).name == name
        relative = 'Delphi/delphi_pgf90' if name == 'delphi_pgf90' else 'opt/nvhpc/lib/' + name
        source = root / relative
        assert source.is_file() and not source.is_symlink()
        assert report['installed_sha256']['/' + relative] == expected and digest(source) == expected
        with source.open('rb') as stream:
            header = stream.read(20)
        assert header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == 183
        sources[name] = source
    # No staged payload is published until all source bytes/targets passed.
    (stage / 'runtime').mkdir(parents=True)
    for name, source in sources.items():
        shutil.copyfile(str(source), str(stage / 'runtime' / name))
    (stage / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    (stage / 'bootstrap-origin.json').write_text(json.dumps({
        'base_sha256': metadata['base_sha256'], 'origin': 'validated portable bootstrap',
        'retained_runtime_sha256': provenance['runtime_sha256']}, indent=2) + '\n')
    print('PASS: staged byte-verified generic solver from the pinned portable bootstrap')


if __name__ == '__main__':
    assert os.getuid() == 0, 'Run inside the disposable fakeroot build only'
    stage_bootstrap(Path('/'))
