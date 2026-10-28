#!/usr/bin/env python3
"""Install the explicitly generic ARM solver during portable-image assembly.

Called by build-inside.sh only for isa_profile=portable-armv8-a. The native job
compiled the matched source with NVFORTRAN -tp=px, never host/native/a64fx.
Verify every staged binary/library hash and AArch64 header before installing;
record this replacement separately from the inherited A64FX bootstrap history.
No host file or original image is writable from this disposable rootfs.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct


def main():
    """Fail closed on wrong target/payload, then install only the declared runtime."""
    assert os.getuid() == 0
    stage = Path('/opt/cphmd-build/portable-delphi')
    provenance = json.loads((stage / 'provenance.json').read_text())
    assert provenance['target'] == 'px'
    assert '-tp=px' in provenance['fortran_flags'].split()
    assert not any(flag in provenance['fortran_flags'] for flag in ('a64fx', '-fast', '-tp=host', '-tp=native'))
    installed = {}
    for name, expected in provenance['runtime_sha256'].items():
        assert Path(name).name == name
        source = stage / 'runtime' / name
        data = source.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
        assert data[:4] == b'\x7fELF' and struct.unpack('<H', data[18:20])[0] == 183
        target = Path('/Delphi/delphi_pgf90') if name == 'delphi_pgf90' else Path('/opt/nvhpc/lib') / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o755)
        installed[str(target)] = expected
    assert '/Delphi/delphi_pgf90' in installed
    report = {'compiler_target': 'px', 'declared_isa_baseline': 'ARM64 generic; no SVE requirement',
              'installed_sha256': installed, 'provenance': provenance,
              'cross_hardware_validation': 'pending; native A64FX execution alone cannot certify every ARM CPU'}
    Path('/usr/share/cphmd/build/delphi-portable.json').write_text(json.dumps(report, indent=2) + '\n')
    Path('/usr/share/cphmd/build/delphi.sha256').write_text(installed['/Delphi/delphi_pgf90'] + '  /Delphi/delphi_pgf90\n')


if __name__ == '__main__':
    main()
