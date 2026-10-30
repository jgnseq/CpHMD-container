#!/usr/bin/env python3
"""Reconstruct a reviewed development snapshot using an immutable source cache.

This optional transport helper avoids re-uploading unchanged vendored sources.
The packet supplies current metadata and changed files; every other file must
match the new manifest in the cache. Only manifest-listed regular files enter
the fresh output. This does not build, submit, commit or trust cache metadata.
The normal workstation launcher still exports a verified committed Git bundle.
Compatible with the login node's Python 3.6.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess


def digest(path):
    """Identify source/archive bytes with bounded memory use."""
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def regular_file(base, relative):
    """Reject traversal and link-based reads outside either trusted input root."""
    path = base / relative
    assert path.is_file() and not path.is_symlink()
    path.resolve().relative_to(base.resolve())
    return path


def reconstruct(packet, cache, output):
    """Verify all sources before publishing a new, fully materialized context."""
    assert not output.exists(), 'Use a fresh candidate directory'
    metadata = json.loads(regular_file(packet, 'build.json').read_text())
    manifest = regular_file(packet, 'manifest.sha256')
    assert digest(manifest) == metadata['manifest_sha256']
    assert digest(regular_file(packet, 'CpHMD.arm64.def')) == metadata['definition_sha256']
    selected = {}
    for line in manifest.read_text().splitlines():
        expected, name = line.split('  ', 1)
        relative = PurePosixPath(name)
        assert len(expected) == 64 and all(c in '0123456789abcdef' for c in expected)
        assert not relative.is_absolute() and '..' not in relative.parts
        assert relative.parts[0] == 'context' and len(relative.parts) > 1 and name not in selected
        base = packet if (packet / name).exists() else cache
        source = regular_file(base, name)
        assert digest(source) == expected, 'Changed or missing source: ' + name
        selected[name] = source
    output.mkdir(parents=True)
    (output / 'build-evidence').mkdir()
    for name in ('build.json', 'manifest.sha256', 'CpHMD.arm64.def', 'source.patch'):
        shutil.copyfile(str(regular_file(packet, name)), str(output / name))
    for name, source in selected.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))
    # Check the copied bytes again; no unlisted cached payload was copied.
    subprocess.run(['sha256sum', '--quiet', '-c', 'manifest.sha256'], cwd=str(output), check=True)
    (output / 'source-transport.json').write_text(json.dumps({
        'method': 'manifest-verified development snapshot plus immutable source cache',
        'files': len(selected), 'manifest_sha256': metadata['manifest_sha256'],
        'cache': str(cache), 'source_dirty': metadata['source_dirty']}, indent=2) + '\n')
    print('RECONSTRUCTED_CONTEXT_MANIFEST_VERIFIED', str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('cache', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    reconstruct(args.packet.resolve(), args.cache.resolve(), args.output.resolve())
