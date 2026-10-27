#!/bin/bash
#SBATCH --job-name=cphmd-delphi-nv-a64fx
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
# Build the source adjacent to the byte-identical x86 reference executable.
# Explicit A64FX targeting avoids importing another ARM host's instruction set.
set -Eeuo pipefail
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
work="$base/delphi-v5-matched-$SLURM_JOB_ID"
mkdir -p "$work/tmp" "$work/runtime"
export TMPDIR="$work/tmp"
exec > >(tee "$work/build.log") 2>&1
trap 'status=$?; echo "$status" > "$work/exit.txt"; exit "$status"' EXIT
source_archive="$base/cphmd-delphi5-matched-source.tar.gz"
echo "e42194bac9255b658c5637da32a8f7a7203dccc78ac087d3f15c118fc8a97026  $source_archive" | sha256sum -c -
tar -xzf "$source_archive" -C "$work"
# NVFORTRAN rejects one continued diagnostic literal in the frozen source archive.
# Split only that stdout message into two literals. Keep the pristine archive
# and exact patch; no arithmetic, parameters, allocation or scientific I/O changes.
python3 - "$work" <<'COMPAT'
from pathlib import Path
import sys,difflib
work=Path(sys.argv[1]);p=work/'DelPhi5-matched-source/src/setcrg.f'
original=p.read_text()
old='write(6,*) "## out of them,",ico," charged points \n     &are in solution ## Increased resolution is needed"'
new="write(6,*) '## out of them,',ico,' charged points',\n     & ' are in solution ## Increased resolution is needed'"
assert original.count(old)==1
updated=original.replace(old,new)
p.write_text(updated)
(work/'compatibility.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),fromfile='pristine/src/setcrg.f',tofile='build/src/setcrg.f')))
COMPAT
module load nvidia-compilers/25.1-prof
module list 2> "$work/modules.txt"
nvfortran -V > "$work/compiler.txt" 2>&1
cd "$work/DelPhi5-matched-source"
flags='-O2 -g -I./src/ -Mpreprocess -DLINUX -DIFC -Mcray=pointer -Mextend -tp=a64fx -Kieee'
printf '%s\n' "$flags" > "$work/flags.txt"
find src -type f -print0 | sort -z | xargs -0 sha256sum > "$work/source.sha256"
make -j1 delphi FC=nvfortran CC=gcc RECFLAGS="$flags" FLAGS="$flags" CFLAGS="-O2 -g -DLINUX -mcpu=a64fx" LFLAGS="-O2 -g -tp=a64fx -Kieee"
cp delphi "$work/runtime/delphi_pgf90"
ldd delphi | tee "$work/ldd.txt"
# Keep every compiler-specific resolved dependency; use the container's glibc.
python3 - "$work" <<'LIBS'
import pathlib,shutil,sys
work=pathlib.Path(sys.argv[1])
for line in (work/'ldd.txt').read_text().splitlines():
    fields=line.split()
    if len(fields)>=3 and fields[1]=='=>':
        path=pathlib.Path(fields[2])
        if path.is_file() and not str(path).startswith(('/lib64/','/usr/lib64/')):
            shutil.copy2(path,work/'runtime'/fields[0])
LIBS
sha256sum "$work"/runtime/* > "$work/runtime.sha256"
