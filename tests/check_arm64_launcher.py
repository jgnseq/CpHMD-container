#!/usr/bin/env python3
"""Exercise the real CLI in an isolated Git fixture with inert transport stubs.

Verify the default/opt-in policy and remote dependency wiring without network,
scheduler access, real runtime payloads or edits to the user's Git repository.
Source-bundle connectivity has its own independent existing regression gate.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent


class LauncherPolicy(unittest.TestCase):
    """Require portable defaults and reject invalid profiles before transport."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cphmd-launcher-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.repo = self.root / 'repo';self.repo.mkdir()
        for name in ('container_build/submit_deucalion_arm64.sh', 'container_build/arm64/profiles.py',
                     'container_build/arm64/stage-bootstrap-delphi.py',
                     'container_build/arm64/install-portable-delphi.py',
                     'container_build/slurm/verify-arm64-candidate.slurm'):
            target = self.repo / name;target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        bundle = self.repo / 'container_build/create_source_bundle.sh'
        bundle.write_text('#!/bin/bash\nprintf fixture > "$3"\n')
        (self.repo/'tests').mkdir()
        (self.repo/'tests/check_repository_safety.py').write_text('# Inert transport fixture; the real guard has separate checks.\n')
        for args in (['init', '-q'], ['checkout', '-qb', 'codex/test'],
                     ['config', 'user.name', 'Fixture'], ['config', 'user.email', 'fixture@example.invalid'],
                     ['add', '.'], ['commit', '-qm', 'fixture']):
            subprocess.run(['git', '-C', str(self.repo)] + args, check=True)
        self.bin = self.root / 'bin';self.bin.mkdir();self.log = self.root / 'transport.jsonl'
        recorder = '#!/usr/bin/env python3\nimport json,os,sys\nwith open(os.environ["FIXTURE_LOG"],"a") as f:f.write(json.dumps(sys.argv)+"\\n")\n'
        for name in ('ssh', 'scp'):
            path = self.bin / name;path.write_text(recorder);path.chmod(0o755)
        (self.bin / 'curl').write_text('#!/bin/bash\nexit 99\n');(self.bin / 'curl').chmod(0o755)
        (self.bin / 'sha256sum').write_text('#!/bin/bash\nprintf "1094b7bbc6a3960223827114626657110b40096cdf9598a727935fc84ebf8aa0  %s\\n" "$1"\n')
        (self.bin / 'sha256sum').chmod(0o755)
        self.archive = self.root / 'inert-source.tar.gz';self.archive.write_text('inert test input')
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'],
                        FIXTURE_LOG=str(self.log), CPHMD_GROMACS_SOURCE=str(self.archive))

    def launch(self, *args):
        """Capture CLI behavior while every transport executable is a stub."""
        return subprocess.run(['bash', str(self.repo / 'container_build/submit_deucalion_arm64.sh')] + list(args),
                              cwd=self.repo, env=self.env, text=True, capture_output=True)

    def remote_script(self):
        """Return the generated remote script and independently parse its syntax."""
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        scripts = [row[-1] for row in calls if Path(row[0]).name == 'ssh' and row[-1].startswith('set -eu')]
        self.assertEqual(len(scripts), 1)
        subprocess.run(['bash', '-n'], input=scripts[0], text=True, check=True)
        return scripts[0]

    def test_default_portable(self):
        result = self.launch();self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('fatal:', result.stderr)
        script = self.remote_script()
        self.assertIn('--profile \'portable\' --simd \'ARM_NEON_ASIMD\'', script)
        self.assertIn('portable.20261028.MZWHAj/candidate/CpHMD-arm64.sif', script)
        self.assertIn('$(git -C ', script)

    def test_sve_needs_opt_in_before_transport(self):
        result = self.launch('--simd', 'ARM_SVE')
        self.assertNotEqual(result.returncode, 0);self.assertFalse(self.log.exists())

    def test_explicit_a64fx(self):
        result = self.launch('--profile', 'a64fx');self.assertEqual(result.returncode, 0, result.stderr)
        script = self.remote_script()
        self.assertIn('--profile \'a64fx\' --simd \'ARM_SVE\'', script)
        self.assertIn('solver-image.fDpShj/CpHMD-arm64-a64fx-pbmc-candidate.sif', script)

    def test_acceptance_after_successful_build(self):
        result = self.launch('--submit', '--verify-hewl', '--jobs', '8')
        self.assertEqual(result.returncode, 0, result.stderr)
        script = self.remote_script()
        self.assertIn('afterok:$build_job', script)
        self.assertIn('verify-arm64-candidate.slurm', script)
        self.assertIn('--pbmc-reference', script)

    def test_untracked_note_stays_local(self):
        """An unrelated note cannot enter the committed-source transport."""
        (self.repo/'local-note.txt').write_text('local fixture note\n')
        result=self.launch();self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('local-note.txt',self.log.read_text())

    def test_dirty_tracked_source_stops_before_transport(self):
        """The launcher cannot export a commit while implying dirty code is included."""
        with (self.repo/'container_build/arm64/profiles.py').open('a') as stream:
            stream.write('\n# changed fixture\n')
        result=self.launch();self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
