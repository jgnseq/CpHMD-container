#!/usr/bin/env python3
"""Test portable defaults and reject specialized/corrupted bootstrap retention.

All payloads are inert twenty-byte fixtures. No image or fixture binary is
executed, no network is used and the user's Git index is never changed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'container_build/arm64'))
import profiles
spec = importlib.util.spec_from_file_location('stage_bootstrap', ROOT / 'container_build/arm64/stage-bootstrap-delphi.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class ProfilePolicy(unittest.TestCase):
    """Hardware-specific settings must never silently narrow the default."""
    def test_portable_default(self):
        selected = profiles.select_profile()
        self.assertEqual((selected['simd'], selected['sve_bits'], selected['delphi_target']),
                         ('ARM_NEON_ASIMD', 0, 'px'))

    def test_sve_requires_explicit_a64fx(self):
        with self.assertRaises(ValueError):
            profiles.select_profile(simd='ARM_SVE')
        self.assertEqual(profiles.select_profile('a64fx')['sve_bits'], 512)
        self.assertEqual(profiles.select_profile('a64fx', 'ARM_NEON_ASIMD')['isa_profile'], 'a64fx-reference')


class BootstrapRetention(unittest.TestCase):
    """Only a pinned, generic and byte-verified runtime may survive rebuilding."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cphmd-profile-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # AArch64 ELF header only: deliberately too short to execute.
        payload = bytearray(20);payload[:6] = b'\x7fELF\x02\x01';payload[18:20] = (183).to_bytes(2, 'little')
        self.sha = hashlib.sha256(payload).hexdigest()
        self.pinned = patch.dict(profiles.PROFILES['portable'], delphi_sha256=self.sha)
        self.pinned.start();self.addCleanup(self.pinned.stop)
        for name in ('etc/cphmd', 'usr/share/cphmd/build', 'Delphi', 'opt/nvhpc/lib'):
            (self.root / name).mkdir(parents=True)
        for name in ('Delphi/delphi_pgf90', 'opt/nvhpc/lib/libfixture.so'):
            (self.root / name).write_bytes(payload)
        self.metadata = {'isa_profile': 'portable-armv8-a',
                         'base_sha256': profiles.PROFILES['portable']['base_sha256']}
        self.provenance = {'target': 'px', 'fortran_flags': '-O2 -tp=px -Kieee',
            'c_flags': '-O2 -march=armv8-a -mtune=generic',
            'runtime_sha256': {'delphi_pgf90': self.sha, 'libfixture.so': self.sha}}
        self.save()

    def save(self):
        """Write the fixture's independently pinned metadata and installed map."""
        (self.root / 'etc/cphmd/build.json').write_text(json.dumps(self.metadata))
        report = {'compiler_target': 'px', 'provenance': self.provenance,
                  'installed_sha256': {'/Delphi/delphi_pgf90': self.sha, '/opt/nvhpc/lib/libfixture.so': self.sha}}
        (self.root / 'usr/share/cphmd/build/delphi-portable.json').write_text(json.dumps(report))

    def test_valid_retention_keeps_source(self):
        stage.stage_bootstrap(self.root)
        retained = self.root / 'opt/cphmd-build/portable-delphi/runtime/delphi_pgf90'
        self.assertEqual(retained.read_bytes(), (self.root / 'Delphi/delphi_pgf90').read_bytes())

    def test_reject_other_bootstrap(self):
        self.metadata['base_sha256'] = profiles.PROFILES['a64fx']['base_sha256'];self.save()
        with self.assertRaises(AssertionError):stage.stage_bootstrap(self.root)
        self.assertFalse((self.root / 'opt/cphmd-build/portable-delphi').exists())

    def test_reject_changed_runtime(self):
        (self.root / 'opt/nvhpc/lib/libfixture.so').write_bytes(b'changed inert payload')
        with self.assertRaises(AssertionError):stage.stage_bootstrap(self.root)
        self.assertFalse((self.root / 'opt/cphmd-build/portable-delphi').exists())

    def test_reject_mixed_target_and_math(self):
        for flags in ('-O2 -tp=px -tp=a64fx -Kieee', '-fast -tp=px -Kieee'):
            self.provenance['fortran_flags'] = flags;self.save()
            with self.assertRaises(AssertionError):stage.stage_bootstrap(self.root)
        self.assertFalse((self.root / 'opt/cphmd-build/portable-delphi').exists())


if __name__ == '__main__':
    unittest.main()
