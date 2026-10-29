#!/usr/bin/env python3
"""Exercise delivered ARM executables under QEMU's non-SVE Cortex-A53 model.

Run on x86 with an unprivileged extraction of the checksum-verified portable
SIF. Explicit QEMU invocations avoid binfmt registration, root and host changes.
The instruction control proves that SVE is rejected by the selected CPU model;
real DelPhi model/coarse/focus work, MC, coordinate assembly and MD/PLUMED then
exercise the delivered binaries. This is an executed-path compatibility gate,
not a performance benchmark or a substitute for physical ARM hardware testing.
The caller preserves the SIF/package hashes and launcher/extraction receipts.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import subprocess
import sys


def digest(path):
    """Identify scientific inputs and actual delivered executables by bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logged(command, work, name, env=None):
    """Keep command, output and true status; never treat DelPhi exit 0 as proof."""
    (work / (name + '.command.json')).write_text(json.dumps(command, indent=2) + '\n')
    with (work / (name + '.log')).open('w') as output:
        result = subprocess.run(command, cwd=work, env=env, stdout=output,
                                stderr=subprocess.STDOUT, timeout=900)
    (work / (name + '.exit')).write_text(str(result.returncode) + '\n')
    assert result.returncode == 0, 'Execution failed: ' + name
    return (work / (name + '.log')).read_text()


def main():
    """Require a fresh output directory and preserve partial failures for review."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rootfs', 'qemu', 'cross', 'source', 'inputs', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root, qemu, cross, source, inputs, work = [getattr(args, name).resolve()
        for name in ('rootfs', 'qemu', 'cross', 'source', 'inputs', 'output')]
    assert os.uname().machine == 'x86_64', 'This gate records an x86 QEMU host'
    metadata = json.loads((root / 'etc/cphmd/build.json').read_text())
    assert metadata['isa_profile'] == 'portable-armv8-a'
    assert metadata['simd'] == 'ARM_NEON_ASIMD' and metadata['sve_bits'] == 0
    work.mkdir()
    # SIGILL is an intentional negative control. Suppress core dumps, including
    # QEMU guest dumps, rather than retaining an unnecessary runtime artifact.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.environ['TMPDIR'] = str(work)
    subprocess.run(['sha256sum', '--quiet', '-c', 'source.sha256'], cwd=source, check=True)
    protocol = json.loads((inputs / 'protocol.json').read_text())
    for name, expected in protocol['file_sha256'].items():
        assert digest(inputs / name) == expected
    sys.path.insert(0, str(source / 'tests/arm64'))
    from hewl_solver_performance import solver_record
    from compare_hewl_pbmc import petit_input, populations

    # Build a tiny, freestanding instruction probe using GNU cross-binutils.
    # It exits zero on an SVE-capable model and must SIGILL on Cortex-A53.
    asm = work / 'sve-control.S'
    asm.write_text('.arch armv8-a+sve\n.global _start\n.text\n_start:\n'
                   'ptrue p0.b\nmov x0, #0\nmov x8, #93\nsvc #0\n')
    tool_env = dict(os.environ, LD_LIBRARY_PATH=str(cross / 'usr/lib/x86_64-linux-gnu'))
    logged([str(cross / 'usr/bin/aarch64-linux-gnu-as'), str(asm), '-o', str(work / 'control.o')],
           work, 'assemble-control', tool_env)
    logged([str(cross / 'usr/bin/aarch64-linux-gnu-ld'), '-o', str(work / 'sve-control'),
            str(work / 'control.o')], work, 'link-control', tool_env)
    logged([str(qemu), '-cpu', 'max', str(work / 'sve-control')], work, 'sve-positive')
    with (work / 'sve-negative.log').open('w') as output:
        negative = subprocess.run([str(qemu), '-cpu', 'cortex-a53', str(work / 'sve-control')],
                                  stdout=output, stderr=subprocess.STDOUT, timeout=15)
    (work / 'sve-negative.exit').write_text(str(negative.returncode) + '\n')
    assert negative.returncode == -signal.SIGILL, 'CPU model failed to reject SVE'

    # Guest paths for loader dependencies use QEMU's interpreter/filesystem
    # prefix; explicit fixture paths use the host extraction directory. No
    # guest shell or host-wide automatic interpreter registration is needed.
    top = root / 'gromacs/gromacs-2026.3/share/gromacs/top'
    kernel = root / 'opt/plumed/lib/libplumedKernel.so'
    library = ':'.join(str(root / name) for name in
                       ('opt/nvhpc/lib', 'opt/plumed/lib', 'opt/plumed/lib64',
                        'gromacs/gromacs-2026.3/lib', 'gromacs/gromacs-2026.3/lib64'))
    prefix = [str(qemu), '-cpu', 'cortex-a53', '-L', str(root)]
    for name, value in {'LD_LIBRARY_PATH': library, 'GMXLIB': str(top),
                        'PLUMED_KERNEL': str(kernel), 'OMP_NUM_THREADS': '1',
                        'GMX_MAXBACKUP': '-1', 'LC_ALL': 'C'}.items():
        prefix += ['-E', name + '=' + value]
    binaries = {'gmx': root / 'gromacs/gromacs-2026.3/bin/gmx',
                'delphi': root / 'Delphi/delphi_pgf90',
                'petit': root / 'programs/petit1.6.1/petit',
                'fixgro': root / 'CpHMD/scripts/fixgro'}
    for binary in binaries.values():
        header = binary.read_bytes()[:20]
        assert header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == 183
    version = logged(prefix + [str(binaries['gmx']), '--version'], work, 'gmx-version')
    assert 'SIMD instructions:   ARM_NEON_ASIMD' in version
    # Existing independent helper/analytic MC checks invoke host wrappers that
    # explicitly emulate only the chosen ARM executable, never a host binary.
    for name, test in [('fixgro', 'check_fixgro.py'), ('petit', 'check_petit.py')]:
        wrapper = work / (name + '-qemu')
        wrapper.write_text('#!/bin/bash\nexec ' + shlex.join(prefix + [str(binaries[name])]) + ' "$@"\n')
        wrapper.chmod(0o750)
        logged([sys.executable, str(root / 'usr/share/cphmd/tests' / test), '--binary', str(wrapper)],
               work, name + '-independent-fixture')

    pb = work / 'pb'
    pb.mkdir()
    for name in protocol['file_sha256']:
        shutil.copyfile(inputs / name, pb / name)
    records = []
    for deck in protocol['decks_in_execution_order']:
        text = logged(prefix + [str(binaries['delphi']), deck], pb, Path(deck).stem)
        records.append(dict(deck=deck, **solver_record(text)))
    # The six real PB decks retain their outputs/residuals. MC below uses the
    # same frozen complete 21-site table as the native matched component screen.
    with (pb / 'PBMC.dat').open() as stdin, (pb / 'petit.out').open('w') as stdout:
        subprocess.run(prefix + [str(binaries['petit']), '-H', '6,6,1', '-E', '0,0,1',
            '-T', '310', '-c', '2', '-r', '1729', '-q', '1000', '100000'],
            cwd=pb, stdin=stdin, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=900)
    sites, _, _ = petit_input(inputs, 21)
    means, final = populations(pb / 'petit.out', sites)
    assert len(means) == len(final) == 21

    md = work / 'md'
    md.mkdir()
    tests = root / 'usr/share/cphmd/tests'
    logged(prefix + [str(binaries['gmx']), 'grompp', '-f', str(tests / 'water.mdp'),
                    '-c', str(top / 'spc216.gro'), '-p', str(tests / 'water.top'), '-o', 'water.tpr'],
           md, 'grompp')
    logged(prefix + [str(binaries['gmx']), 'mdrun', '-s', 'water.tpr', '-deffnm', 'water',
                    '-ntmpi', '1', '-ntomp', '1', '-pin', 'off', '-reprod',
                    '-plumed', str(tests / 'water.plumed.dat')], md, 'mdrun')
    logged(prefix + [str(binaries['gmx']), 'check', '-f', 'water.xtc'], md, 'check-xtc')
    logged(prefix + [str(binaries['gmx']), 'check', '-e', 'water.edr'], md, 'check-edr')
    mdlog = (md / 'water.log').read_text()
    assert 'Finished mdrun on rank 0' in mdlog and 'LINCS WARNING' not in mdlog
    rows = [list(map(float, line.split())) for line in (md / 'COLVAR').read_text().splitlines()
            if line.strip() and not line.startswith('#')]
    assert len(rows) == 5 and all(all(math.isfinite(x) for x in row) for row in rows)
    (work / 'audit.json').write_text(json.dumps({'passed': True, 'cpu_model': 'cortex-a53',
        'sve_negative_control_status': negative.returncode,
        'binary_sha256': {name: digest(path) for name, path in binaries.items()},
        'input_protocol_sha256': digest(inputs / 'protocol.json'), 'PB': records,
        'MC_means': means, 'MC_final_states': final, 'PLUMED_records': len(rows),
        'limits': 'Executed-path non-SVE emulation gate; no performance measurement, no physical ARM hardware coverage, no full PB convergence claim.'}, indent=2) + '\n')
    print('NON_SVE_EXECUTED_PATH_GATE_PASSED')


if __name__ == '__main__':
    main()
