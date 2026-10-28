#!/bin/bash
#SBATCH --job-name=cphmd-portable-arm64
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=28G
#SBATCH --time=04:00:00
# Independent overnight pipeline: generic DelPhi -> NEON/baseline rebuild ->
# ordinary-user smoke/unit checks -> tight PBMC comparison. Rootfs staging alone
# uses the authorized node-local exception. All persistent inputs/results stay
# in project storage. No original SIF or scientific source is overwritten.
set -Eeuo pipefail
root="$(realpath "${1:?Supply new portable project root}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/portable.*) ;; *) exit 2 ;; esac
mkdir "$root/tmp" "$root/solver" "$root/solver/runtime"
export TMPDIR="$root/tmp" SINGULARITY_TMPDIR="$root/tmp" APPTAINER_TMPDIR="$root/tmp"
exec > >(tee "$root/pipeline-${SLURM_JOB_ID}.log") 2>&1
# Retain the actual failure/success marker independently of a live connection.
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
seed="$root/seed"
(cd "$seed" && sha256sum --quiet -c manifest.sha256)
cp "${BASH_SOURCE[0]}" "$root/executed-portable.slurm"
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
archive="$base/cphmd-delphi5-matched-source.tar.gz"
echo "e42194bac9255b658c5637da32a8f7a7203dccc78ac087d3f15c118fc8a97026  $archive" | sha256sum -c -
tar -xzf "$archive" -C "$root/solver"
# Same stdout-only legacy-literal compatibility patch as the accepted A64FX
# build. No arithmetic, memory model, solver parameter or precision edits.
python3 - "$root/solver" <<'PY'
from pathlib import Path
import sys,difflib
work=Path(sys.argv[1]);p=work/'DelPhi5-matched-source/src/setcrg.f'
old=p.read_text()
before='write(6,*) "## out of them,",ico," charged points \n     &are in solution ## Increased resolution is needed"'
after="write(6,*) '## out of them,',ico,' charged points',\n     & ' are in solution ## Increased resolution is needed'"
assert old.count(before)==1
new=old.replace(before,after);p.write_text(new)
(work/'compatibility.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True))))
PY
module load nvidia-compilers/25.1-prof
module list 2> "$root/solver/modules.txt"
nvfortran -V > "$root/solver/compiler.txt" 2>&1
flags='-O2 -g -I./src/ -Mpreprocess -DLINUX -DIFC -Mcray=pointer -Mextend -tp=px -Kieee'
printf '%s\n' "$flags" > "$root/solver/flags.txt"
cd "$root/solver/DelPhi5-matched-source"
find src -type f -print0 | sort -z | xargs -0 sha256sum > "$root/solver/source.sha256"
make -j1 delphi FC=nvfortran CC=gcc RECFLAGS="$flags" FLAGS="$flags" \
    CFLAGS='-O2 -g -DLINUX -march=armv8-a -mtune=generic' LFLAGS='-O2 -g -tp=px -Kieee'
cp delphi "$root/solver/runtime/delphi_pgf90"
ldd delphi > "$root/solver/ldd.txt"
python3 - "$root/solver" <<'PY'
from pathlib import Path
import hashlib,json,shutil,sys
work=Path(sys.argv[1])
for line in (work/'ldd.txt').read_text().splitlines():
 fields=line.split()
 assert 'not found' not in line
 if len(fields)>=3 and fields[1]=='=>':
  path=Path(fields[2])
  if path.is_file() and not str(path).startswith(('/lib64/','/usr/lib64/')):
   shutil.copyfile(str(path),str(work/'runtime'/fields[0]))
data={'target':'px','fortran_flags':(work/'flags.txt').read_text().strip(),
      'c_flags':'-O2 -g -DLINUX -march=armv8-a -mtune=generic',
      'compiler':(work/'compiler.txt').read_text(),'source_archive_sha256':'e42194bac9255b658c5637da32a8f7a7203dccc78ac087d3f15c118fc8a97026',
      'runtime_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'runtime').iterdir()}}
(work/'provenance.json').write_text(json.dumps(data,indent=2)+'\n')
PY
python3 "$seed/context/prepare_portable_candidate.py" "$seed" "$root/solver" "$root/candidate"
bash "$root/candidate/context/run_arm64_build.sh" "$root/candidate"
# Subsequent simulation temporary files are project-backed again, never /tmp.
mkdir "$root/pbmc-tmp"
input="$base/solution.P4IU4M/solution"
image="$root/candidate/CpHMD-arm64.sif"
singularity exec --cleanenv --bind "$root/candidate/context:/source:ro,$input:/input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/pbmc-tmp "$image" bash /source/tests/arm64/run_hewl_pbmc.sh \
    /source /input/snapshot /input/npt.tpr /out/pbmc tight
singularity exec --cleanenv --bind "$root/candidate/context:/source:ro,$root:/out" --pwd /out \
    --env TMPDIR=/out/pbmc-tmp "$image" python3 /source/tests/arm64/compare_hewl_pbmc.py \
    /source/portable-reference /out/pbmc/raw --contract /source/tests/arm64/hewl-pbmc-tight-contract.json \
    --output /out/portable-pbmc-comparison.json
echo PORTABLE_TARGET_NATIVE_GATES_PASSED_NON_SVE_EXECUTION_PENDING | tee "$root/result.txt"
