#!/usr/bin/env python3
"""Gate manifest-only reconstruction against stale payloads and changed bytes.

Inert text fixtures stay in temporary directories; no images, network or Git
operations are involved. A source cache must never introduce unlisted programs.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'container_build'))
from reconstruct_arm64_context import reconstruct, digest


class ContextTransport(unittest.TestCase):
    """Only current manifest-listed, byte-identical input may be materialized."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cphmd-context-transport-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet,self.cache,self.output = [self.root/name for name in ('packet','cache','output')]
        (self.packet/'context').mkdir(parents=True);(self.cache/'context').mkdir(parents=True)
        (self.cache/'context/keep.txt').write_text('cache input\n')
        (self.cache/'context/stale-unlisted.txt').write_text('must not enter context\n')
        (self.packet/'context/change.txt').write_text('reviewed new input\n')
        manifest=''.join(digest(path)+'  context/'+path.name+'\n' for path in
                         [self.cache/'context/keep.txt',self.packet/'context/change.txt'])
        (self.packet/'manifest.sha256').write_text(manifest)
        (self.packet/'CpHMD.arm64.def').write_text('inert recipe fixture\n')
        (self.packet/'source.patch').write_text('')
        self.save()

    def save(self):
        """Pin the fixture manifest and recipe exactly as the preparer does."""
        (self.packet/'build.json').write_text(json.dumps({'source_dirty':True,
            'manifest_sha256':digest(self.packet/'manifest.sha256'),
            'definition_sha256':digest(self.packet/'CpHMD.arm64.def')}))

    def test_manifest_only(self):
        reconstruct(self.packet,self.cache,self.output)
        self.assertEqual({p.name for p in (self.output/'context').iterdir()}, {'keep.txt','change.txt'})

    def test_changed_cache_rejected(self):
        (self.cache/'context/keep.txt').write_text('changed\n')
        with self.assertRaises(AssertionError):reconstruct(self.packet,self.cache,self.output)
        self.assertFalse(self.output.exists())

    def test_changed_overlay_rejected(self):
        (self.packet/'context/change.txt').write_text('changed\n')
        with self.assertRaises(AssertionError):reconstruct(self.packet,self.cache,self.output)

    def test_traversal_rejected(self):
        (self.packet/'manifest.sha256').write_text('0'*64+'  context/../../outside\n');self.save()
        with self.assertRaises(AssertionError):reconstruct(self.packet,self.cache,self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
