#!/usr/bin/env python3
"""Make the ARM image's public runtime payload readable by ordinary HPC users.

Run only inside a writable native ARM CpHMD image during %post. Source snapshots
can inherit project-only modes/ACLs; cp -a carries those into the rootfs, where
fakeroot tests pass but real users cannot read the application. Remove inherited
ACLs and add read/traversal permissions only to image-owned runtime trees.
Protect scientific file bytes with before/after SHA-256 and retain the report.
Never run this against host/project paths or modify the original source SIF.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import stat

ROOTS = ['/CpHMD', '/Delphi', '/FFs', '/STs', '/Databases', '/analysis',
         '/Templates', '/Tutorials', '/gromacs', '/opt/plumed', '/opt/nvhpc',
         '/programs/petit1.6.1', '/usr/share/cphmd', '/usr/local/libexec/cphmd', '/etc/cphmd']


def digest(path):
    """Stream the payload hash without loading shared libraries into memory."""
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def normalize(path):
    """Clear inherited ACL restrictions, preserve existing bits and add public rX."""
    if path.is_symlink():
        return
    for attribute in os.listxattr(str(path)):
        if attribute in ('system.posix_acl_access', 'system.posix_acl_default'):
            os.removexattr(str(path), attribute)
    mode = stat.S_IMODE(path.stat().st_mode)
    mode |= 0o555 if path.is_dir() or mode & 0o111 else 0o444
    path.chmod(mode)


def main():
    """Normalize known image trees and require byte-identical scientific payloads."""
    if os.getuid() != 0 or platform.machine() != 'aarch64' or not Path('/etc/cphmd/build.json').is_file():
        raise SystemExit('Run only as image-build root inside the native ARM CpHMD rootfs')
    roots = [Path(name) for name in ROOTS]
    if not all(path.is_dir() for path in roots):
        raise SystemExit('An expected runtime tree is missing; refusing partial normalization')
    before_modes = {str(path): oct(stat.S_IMODE(path.stat().st_mode)) for path in roots}
    paths = set(roots)
    for root in roots:
        paths.update(root.rglob('*'))
    files = [path for path in paths if path.is_file() and not path.is_symlink()]
    before = {str(path): digest(path) for path in files}
    # Ancestors need traversal too (e.g. /usr/local/libexec or /programs), but
    # their unrelated contents are not recursively modified.
    ancestors = {parent for root in roots for parent in root.parents}
    for path in sorted(ancestors | paths, key=lambda value: len(value.parts)):
        normalize(path)
    for path in files:
        if digest(path) != before[str(path)]:
            raise SystemExit('Payload bytes changed during permission repair: ' + str(path))
    report = Path('/usr/share/cphmd/build/runtime-permissions.json')
    report.write_text(json.dumps({'roots_before': before_modes,
                                 'roots_after': {str(path): oct(stat.S_IMODE(path.stat().st_mode)) for path in roots},
                                 'file_count_verified_byte_identical': len(files),
                                 'payload_sha256': before}, indent=2) + '\n')
    report.chmod(0o644)
    print('PASS: runtime permissions normalized; {} payload files byte-identical'.format(len(files)))


if __name__ == '__main__':
    main()
