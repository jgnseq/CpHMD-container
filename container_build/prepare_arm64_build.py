#!/usr/bin/env python3
"""Freeze committed source into the immutable input consumed by the ARM job.

Called on the login node by submit_deucalion_arm64.sh, before any allocation.
Copy portable sources, exclude host binaries, pin the bootstrap/source hashes,
and render the Singularity definition. run_arm64_build.sh consumes the result;
no compilation, simulation cycle or job submission happens in this module.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

# Execution-validated A64FX candidate from job 2150839. Its DelPhi 5 solver
# replaces the inherited 6.1 executable that SIGILLs on A64FX. Numerical
# convergence/sampling evidence is recorded separately from runtime acceptance.
BASE_SHA256 = '1ee92b674c8808dd6e63d3f487fde5e2ea659c706eafefb43cede9b89070407d'
GROMACS_SHA256 = '1094b7bbc6a3960223827114626657110b40096cdf9598a727935fc84ebf8aa0'


def digest(path):
    """Stream a file's SHA-256 without loading a source archive/SIF into memory."""
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    """Validate inputs and write a new context, recipe, manifest and provenance.

    Refuse existing output directories so each candidate retains its own
    evidence. --allow-dirty is only for explicit local development experiments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--base-image', required=True, type=Path)
    parser.add_argument('--gromacs-source', required=True, type=Path)
    parser.add_argument('--simd', choices=['ARM_SVE', 'ARM_NEON_ASIMD'], default='ARM_SVE')
    parser.add_argument('--jobs', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--allow-dirty', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    base = args.base_image.resolve()
    archive = args.gromacs_source.resolve()
    out = args.output_dir.resolve()
    if any(c.isspace() for c in str(base)):
        parser.error('Use a base-image path without whitespace for the SIF header')
    if digest(base) != BASE_SHA256:
        parser.error('Bootstrap image differs from the audited ARM base SHA-256')
    if digest(archive) != GROMACS_SHA256:
        parser.error('GROMACS source SHA-256 mismatch')
    def git(*argv):
        """Query source identity/status for metadata without changing the repo."""
        return subprocess.check_output(['git', '-C', str(repo)] + list(argv)).decode().strip()
    dirty = git('status', '--porcelain', '--untracked-files=all')
    if dirty and not args.allow_dirty:
        parser.error('Commit reviewed source first, or explicitly use --allow-dirty for a candidate')
    if out.exists():
        parser.error('Refusing to overwrite an existing output directory: ' + str(out))
    out.mkdir(parents=True)
    context = out / 'context'
    context.mkdir()
    (out / 'build-evidence').mkdir()
    omissions = []
    def ignore(directory, names):
        """Filter copytree entries and record all excluded host build products.

        Follow only repository-contained symlinks. Excluding ELF by magic,
        rather than filename, prevents an inherited x86 helper entering ARM.
        """
        ignored = []
        for name in names:
            p = Path(directory) / name
            omit = name in ('.git', '__pycache__') or name.endswith(('.pyc', '.o', '.a'))
            if p.is_symlink():
                try:
                    p.resolve().relative_to(repo)
                except ValueError:
                    raise RuntimeError('Source symlink leaves repository: ' + str(p))
                omit = omit or not p.exists()
            if not omit and p.is_file():
                with p.open('rb') as stream:
                    omit = stream.read(4) == b'\x7fELF'
            if omit:
                omissions.append(str(p.relative_to(repo)))
                ignored.append(name)
        return ignored
    # Runtime trees + vendored compilers' inputs + embedded smoke tests. The
    # manifest covers their copied bytes, including the frozen host launcher.
    for name in ('CpHMD', 'DelphiTools', 'FFs', 'STs', 'Databases', 'analysis',
                 'template', 'tutorials', 'petit1.6.1', 'plumed', 'tests/arm64',
                 'container_build/arm64'):
        dest = context / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(repo / name), str(dest), ignore=ignore)
    shutil.copy2(str(repo / 'container_build/run_arm64_build.sh'),
                 str(context / 'run_arm64_build.sh'))
    shutil.copy2(str(archive), str(context / 'gromacs-2026.3.tar.gz'))
    manifest = []
    for p in sorted(context.rglob('*')):
        if p.is_file():
            if '\n' in str(p): raise RuntimeError('Newline in source filename')
            manifest.append('{}  {}'.format(digest(p), p.relative_to(out)))
    (out / 'manifest.sha256').write_text('\n'.join(manifest) + '\n')
    manifest_hash = digest(out / 'manifest.sha256')
    template = (repo / 'container_build/defs/CpHMD.arm64.def.in').read_text()
    for key, value in {'BASE_IMAGE': str(base), 'SIMD': args.simd,
                       'BASE_SHA256': BASE_SHA256,
                       'MANIFEST_SHA256': manifest_hash}.items():
        template = template.replace('@' + key + '@', value)
    # Preserve the canonical user-facing app interface in the rendered recipe.
    canonical = (repo / 'container_build/CpHMD-suite.def').read_text()
    apps = canonical[canonical.index('%apprun protonation'):]
    (out / 'CpHMD.arm64.def').write_text(template + '\n' + apps)
    metadata = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_commit': git('rev-parse', 'HEAD'),
        'source_branch': git('branch', '--show-current'),
        'source_dirty': bool(dirty), 'source_status': dirty.splitlines(),
        'base_image': str(base), 'base_sha256': BASE_SHA256,
        'gromacs_version': '2026.3', 'gromacs_sha256': GROMACS_SHA256,
        'simd': args.simd, 'sve_bits': 512 if args.simd == 'ARM_SVE' else 0,
        'jobs': args.jobs, 'manifest_sha256': manifest_hash,
        'definition_sha256': digest(out / 'CpHMD.arm64.def'),
        'excluded_host_products': omissions,
        'validation_status': 'prepared; build and scientific validation pending',
    }
    (out / 'build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # Supplement the exact commit with any explicitly permitted development
    # diff. The context manifest, rather than this patch alone, pins its bytes.
    patch = subprocess.check_output(['git', '-C', str(repo), 'diff', '--binary', 'HEAD'])
    (out / 'source.patch').write_bytes(patch)
    print('Prepared:', out)
    print('Manifest SHA-256:', manifest_hash)
    print('Excluded host build products:', len(omissions))
    print('No job submitted. Review build.json and CpHMD.arm64.def before building.')


if __name__ == '__main__':
    main()
