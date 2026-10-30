#!/usr/bin/env python3
"""Associate the frozen candidate's source bytes with a later reviewed commit.

Run from the checkout after collecting final receipts. Read committed Git blobs
and the native context manifest; follow only in-tree committed symlinks. Record
all mismatches and externally pinned inputs. This read-only audit never changes
the candidate's honest original source_commit/source_dirty metadata and does
not turn the development snapshot into a clean-commit build retroactively.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import posixpath
import subprocess


def git(*args):
    """Read repository metadata/blobs without modifying the checkout or index."""
    return subprocess.check_output(['git'] + list(args))


def committed_files(revision):
    """Read Git's immutable tree/blobs once, retaining symlink target bytes."""
    tree = {}
    for row in git('ls-tree', '-rz', revision).split(b'\0'):
        if not row:
            continue
        header, name = row.split(b'\t', 1)
        mode, kind, identity = header.decode().split()
        if kind == 'blob':
            tree[name.decode()] = (mode, identity)
    identities = sorted({entry[1] for entry in tree.values()})
    response = subprocess.run(['git', 'cat-file', '--batch'], check=True,
        input=('\n'.join(identities) + '\n').encode(), stdout=subprocess.PIPE).stdout
    digest, links, offset = {}, {}, 0
    link_ids = {identity for mode, identity in tree.values() if mode == '120000'}
    for identity in identities:
        end = response.index(b'\n', offset)
        found, kind, size = response[offset:end].decode().split()
        assert found == identity and kind == 'blob'
        start, size = end + 1, int(size)
        value = memoryview(response)[start:start + size]
        digest[identity] = hashlib.sha256(value).hexdigest()
        if identity in link_ids:
            links[identity] = bytes(value).decode()
        offset = start + size + 1
    return tree, digest, links


def resolve(path, tree, links):
    """Follow file or parent-directory symlinks, rejecting cycles/traversal."""
    seen = set()
    while True:
        assert path not in seen, 'Symlink cycle'
        seen.add(path)
        parts = path.split('/')
        for count in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:count])
            entry = tree.get(prefix)
            if entry and entry[0] == '120000':
                target = links[entry[1]]
                assert not target.startswith('/')
                path = posixpath.normpath(posixpath.join(
                    posixpath.dirname(prefix), target, *parts[count:]))
                assert path != '..' and not path.startswith('../')
                break
        else:
            return tree.get(path)


def main():
    """Compare every frozen manifest source; independently render the recipe."""
    folder = Path('docs/aarch64/evidence/2026-10-30/final-portable-candidate')
    revision = git('rev-parse', 'HEAD').decode().strip()
    tree, digest, links = committed_files(revision)
    metadata = json.loads((folder / 'native/build.json').read_text())
    manifest = (folder / 'native/manifest.sha256').read_bytes()
    assert hashlib.sha256(manifest).hexdigest() == metadata['manifest_sha256']
    names = {'run_arm64_build.sh': 'container_build/run_arm64_build.sh',
             'verify-arm64-candidate.slurm': 'container_build/slurm/verify-arm64-candidate.slurm'}
    matched, external, differences = [], [], []
    for line in manifest.decode().splitlines():
        expected, name = line.split('  ', 1)
        assert name.startswith('context/')
        relative = name[len('context/'):]
        if relative == 'gromacs-2026.3.tar.gz':
            assert expected == metadata['gromacs_sha256']
            external.append({'path': name, 'sha256': expected, 'source': 'pinned official archive'})
            continue
        if relative.startswith('portable-reference/'):
            external.append({'path': name, 'sha256': expected, 'source': 'frozen x86 scientific reference'})
            continue
        source = names.get(relative, relative)
        entry = resolve(source, tree, links)
        actual = digest[entry[1]] if entry else None
        if actual != expected:
            differences.append({'context': name, 'repository_path': source,
                                'frozen_sha256': expected, 'committed_sha256': actual})
        else:
            matched.append(source)
    # Validate the build definition too, using its recorded execution paths.
    template = git('show', revision + ':container_build/defs/CpHMD.arm64.def.in').decode()
    substitutions = {'BASE_IMAGE': metadata['base_image'], 'SIMD': metadata['simd'],
        'BASE_SHA256': metadata['base_sha256'], 'ISA_PROFILE': metadata['isa_profile'],
        'CPU_BASELINE': 'armv8-a+asimd', 'DELPHI_TARGET': 'px',
        'MANIFEST_SHA256': metadata['manifest_sha256']}
    for key, value in substitutions.items():
        template = template.replace('@' + key + '@', value)
    canonical = git('show', revision + ':container_build/CpHMD-suite.def').decode()
    rendered = template + '\n' + canonical[canonical.index('%apprun protonation'):]
    recipe_equal = hashlib.sha256(rendered.encode()).hexdigest() == metadata['definition_sha256']
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(),
        'passed': not differences and recipe_equal, 'reviewed_commit': revision,
        'original_source_commit': metadata['source_commit'],
        'original_source_dirty': metadata['source_dirty'],
        'manifest_sha256': metadata['manifest_sha256'],
        'matching_repository_files': len(matched), 'external_inputs': external,
        'differences': differences, 'rendered_recipe_equal': recipe_equal,
        'limits': 'Byte association of frozen context and rendered recipe only. Original dirty snapshot provenance is preserved; this is not a retroactive clean-commit build or proof about excluded files.'}
    (folder / 'committed-input-association.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
