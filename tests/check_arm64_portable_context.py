#!/usr/bin/env python3
"""Test portable-context rejection of specialized or corrupted build inputs.

Tiny inert byte fixtures stand in for payload files; nothing is executed or
installed. A valid derivation must retain its seed unchanged. Wrong CPU targets,
mixed target flags and changed source/runtime bytes must fail before a build
could be accepted. Native execution and non-SVE compatibility need real gates.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DRIVER = Path(__file__).resolve().parent.parent / 'container_build/prepare_portable_candidate.py'


def digest(path):
    """Identify a temporary test input; never inspect a host executable."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PortableDerivation(unittest.TestCase):
    """Ensure metadata cannot silently carry an A64FX solver into the baseline."""
    def setUp(self):
        """Create a frozen, minimal seed and a clearly inert runtime fixture."""
        self.temp = tempfile.TemporaryDirectory(prefix='cphmd-portable-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed, self.solver, self.output = [self.root / name for name in ('seed', 'solver', 'candidate')]
        (self.seed / 'context').mkdir(parents=True)
        (self.seed / 'context/input.txt').write_text('frozen scientific source\n')
        (self.seed / 'manifest.sha256').write_text(digest(self.seed / 'context/input.txt') + '  context/input.txt\n')
        (self.seed / 'CpHMD.arm64.def').write_text('%labels\n    source.manifest.sha256 ' + digest(self.seed / 'manifest.sha256') + '\n')
        metadata = {'portable_derivation_seed': True, 'simd': 'ARM_NEON_ASIMD',
                    'manifest_sha256': digest(self.seed / 'manifest.sha256'),
                    'definition_sha256': digest(self.seed / 'CpHMD.arm64.def')}
        (self.seed / 'build.json').write_text(json.dumps(metadata))
        (self.solver / 'runtime').mkdir(parents=True)
        (self.solver / 'runtime/delphi_pgf90').write_bytes(b'inert test payload; not executable')
        self.provenance = {'target': 'px', 'fortran_flags': '-O2 -tp=px -Kieee',
            'runtime_sha256': {'delphi_pgf90': digest(self.solver / 'runtime/delphi_pgf90')}}
        self.save_provenance()

    def save_provenance(self):
        """Write only the temporary test's declared runtime identity."""
        (self.solver / 'provenance.json').write_text(json.dumps(self.provenance))

    def derive(self):
        """Invoke the real derivation process and retain its failure status."""
        return subprocess.run([sys.executable, str(DRIVER), str(self.seed), str(self.solver), str(self.output)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_valid_and_seed_immutable(self):
        """A valid context declares the baseline without claiming all-device QA."""
        before = {str(p.relative_to(self.seed)): digest(p) for p in self.seed.rglob('*') if p.is_file()}
        self.assertEqual(self.derive().returncode, 0)
        metadata = json.loads((self.output / 'build.json').read_text())
        self.assertEqual(metadata['isa_profile'], 'portable-armv8-a')
        self.assertEqual(metadata['sve_bits'], 0)
        self.assertEqual(metadata['cross_hardware_validation'], 'non-SVE execution pending')
        self.assertEqual(before, {str(p.relative_to(self.seed)): digest(p) for p in self.seed.rglob('*') if p.is_file()})
        result = subprocess.run(['sha256sum', '--quiet', '-c', 'manifest.sha256'], cwd=self.output)
        self.assertEqual(result.returncode, 0)

    def test_reject_specialized_or_mixed_target(self):
        """Both an explicitly specialized target and a hidden second target fail."""
        for target, flags in [('a64fx', '-O2 -tp=a64fx'), ('px', '-O2 -tp=px -tp=a64fx')]:
            self.provenance.update(target=target, fortran_flags=flags)
            self.save_provenance()
            self.assertNotEqual(self.derive().returncode, 0)
            self.assertFalse(self.output.exists())

    def test_reject_changed_source(self):
        """A modified frozen source never becomes a supposedly accepted seed."""
        (self.seed / 'context/input.txt').write_text('changed source\n')
        self.assertNotEqual(self.derive().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_reject_changed_runtime(self):
        """A changed compiled payload fails its recorded digest."""
        (self.solver / 'runtime/delphi_pgf90').write_bytes(b'changed inert test data')
        self.assertNotEqual(self.derive().returncode, 0)
        self.assertFalse((self.output / 'CpHMD-arm64.sif').exists())


if __name__ == '__main__':
    unittest.main()
