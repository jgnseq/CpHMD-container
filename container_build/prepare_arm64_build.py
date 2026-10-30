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
import sys
from arm64.profiles import PROFILES, select_profile

# Defaults come from one shared policy; A64FX now requires explicit selection.
BASE_SHA256 = PROFILES['portable']['base_sha256']
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
    parser.add_argument('--recipe-base-image', type=Path,
                        help='Absolute execution-host path for the same checksum-pinned base')
    parser.add_argument('--gromacs-source', required=True, type=Path)
    parser.add_argument('--profile', choices=sorted(PROFILES), default='portable')
    parser.add_argument('--simd', choices=['ARM_SVE', 'ARM_NEON_ASIMD'],
                        help='Default follows profile; portable rejects SVE')
    parser.add_argument('--jobs', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--allow-dirty', action='store_true')
    parser.add_argument('--portable-seed', action='store_true',
                        help='Freeze the generic-solver derivation job; seed itself is not portable')
    parser.add_argument('--pbmc-reference', type=Path)
    args = parser.parse_args()
    try:
        profile = select_profile(args.profile, args.simd)
    except ValueError as error:
        parser.error(str(error))
    args.simd = profile['simd']
    if args.portable_seed and (args.profile != 'a64fx' or args.simd != 'ARM_NEON_ASIMD' or args.pbmc_reference is None):
        parser.error('Legacy portable seed requires --profile a64fx --simd ARM_NEON_ASIMD and --pbmc-reference')
    repo = Path(__file__).resolve().parent.parent
    base = args.base_image.resolve()
    archive = args.gromacs_source.resolve()
    out = args.output_dir.resolve()
    recipe_base = args.recipe_base_image if args.recipe_base_image is not None else base
    if not recipe_base.is_absolute() or any(c.isspace() for c in str(recipe_base)):
        parser.error('Use a base-image path without whitespace for the SIF header')
    if digest(base) != profile['base_sha256']:
        parser.error('Bootstrap image differs from the selected ' + args.profile + ' profile SHA-256')
    if digest(archive) != GROMACS_SHA256:
        parser.error('GROMACS source SHA-256 mismatch')
    def git(*argv):
        """Query source identity/status for metadata without changing the repo."""
        return subprocess.check_output(['git', '-C', str(repo)] + list(argv)).decode().strip()
    dirty = git('status', '--porcelain', '--untracked-files=all')
    if dirty and not args.allow_dirty:
        parser.error('Commit reviewed source first, or explicitly use --allow-dirty for a candidate')
    subprocess.run([sys.executable, str(repo / 'tests/check_repository_safety.py')], cwd=str(repo), check=True)
    if out.exists():
        parser.error('Refusing to overwrite an existing output directory: ' + str(out))
    out.mkdir(parents=True)
    context = out / 'context'
    context.mkdir()
    (out / 'build-evidence').mkdir()
    omissions = []
    # Broad runtime trees must not sweep ignored/untracked credentials into a
    # remote build. Permit tracked input plus these explicit new owned gates.
    allowed_files = set(subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).decode().split('\0'))
    allowed_files.update(('container_build/arm64/install-portable-delphi.py',
                          'container_build/arm64/profiles.py',
                          'container_build/arm64/stage-bootstrap-delphi.py',
                          'tests/arm64/hewl_overnight.py'))
    allowed_dirs = set()
    for name in allowed_files:
        allowed_dirs.update(str(parent) for parent in Path(name).parents)
    def ignore(directory, names):
        """Filter copytree entries and record all excluded host build products.

        Follow only repository-contained symlinks. Excluding ELF by magic,
        rather than filename, prevents an inherited x86 helper entering ARM.
        """
        ignored = []
        for name in names:
            p = Path(directory) / name
            relative = str(p.relative_to(repo))
            try:
                resolved_relative = str(p.resolve().relative_to(repo))
            except ValueError:
                resolved_relative = relative
            permit = allowed_dirs | allowed_files if p.is_dir() else allowed_files
            omit = relative not in permit and resolved_relative not in permit
            omit = omit or name in ('.git', '__pycache__') or name.endswith(('.pyc', '.o', '.a'))
            if omit:
                omissions.append(relative)
                ignored.append(name)
                continue
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
    gate = repo / 'container_build/slurm/verify-arm64-candidate.slurm'
    if gate.is_symlink() or not gate.is_file():
        parser.error('Expected regular candidate acceptance launcher')
    shutil.copy2(str(gate), str(context / gate.name))
    if args.portable_seed:
        for name in ('prepare_portable_candidate.py', 'slurm/build-portable-arm64.slurm'):
            path = repo / 'container_build' / name
            if path.is_symlink() or not path.is_file():
                parser.error('Expected regular portable driver: ' + name)
            shutil.copy2(str(path), str(context / path.name))
    if args.pbmc_reference is not None:
        reference = context / 'portable-reference'
        reference.mkdir()
        for name in ('PBMC.pkcrg', 'PBMC.g', 'PBMC.dat', 'petit-1729.out', 'petit-2718.out', 'petit-3141.out'):
            path = args.pbmc_reference / name
            if path.is_symlink() or not path.is_file() or b'\x00' in path.read_bytes():
                parser.error('Expected regular scientific reference text: ' + name)
            shutil.copy2(str(path), str(reference / name))
    shutil.copy2(str(archive), str(context / 'gromacs-2026.3.tar.gz'))
    manifest = []
    for p in sorted(context.rglob('*')):
        if p.is_file():
            if '\n' in str(p): raise RuntimeError('Newline in source filename')
            manifest.append('{}  {}'.format(digest(p), p.relative_to(out)))
    (out / 'manifest.sha256').write_text('\n'.join(manifest) + '\n')
    manifest_hash = digest(out / 'manifest.sha256')
    template = (repo / 'container_build/defs/CpHMD.arm64.def.in').read_text()
    for key, value in {'BASE_IMAGE': str(recipe_base), 'SIMD': args.simd,
                       'BASE_SHA256': profile['base_sha256'],
                       'ISA_PROFILE': profile['isa_profile'],
                       'CPU_BASELINE': profile['cpu_baseline'],
                       'DELPHI_TARGET': profile['delphi_target'],
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
        'base_image': str(recipe_base), 'base_sha256': profile['base_sha256'],
        'build_profile': args.profile, 'base_profile': args.profile,
        'base_checked_local': str(base),
        'gromacs_version': '2026.3', 'gromacs_sha256': GROMACS_SHA256,
        'simd': args.simd, 'sve_bits': 512 if args.simd == 'ARM_SVE' else 0,
        'jobs': args.jobs, 'manifest_sha256': manifest_hash,
        'definition_sha256': digest(out / 'CpHMD.arm64.def'),
        'excluded_host_products': omissions,
        'validation_status': 'prepared; build and scientific validation pending',
        'isa_profile': profile['isa_profile'],
        'portable_derivation_seed': args.portable_seed,
        'portability_note': profile['portability_note'],
        'candidate_solver_target': profile['delphi_target'],
        'cross_hardware_validation': 'pending for this newly built candidate',
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
