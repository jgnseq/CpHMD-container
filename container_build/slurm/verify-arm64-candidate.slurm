#!/bin/bash
#SBATCH --job-name=cphmd-arm-acceptance
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# Separate post-build scientific gate: byte identity of embedded controller/data,
# tight fixed-input PB/MC, full/RT cycles, two real continuation boundaries and
# deterministic serial component checks. Queue afterok of the fresh build.
# Parent-image acceptance is never substituted for this candidate's results.
set -Eeuo pipefail
out="$(realpath "${1:?Supply prepared candidate directory}")"
case "$out" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/*) ;; *) exit 2 ;; esac
exec > >(tee "$out/acceptance-driver-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    # Retain actual failure/success even after the submitting terminal closes.
    status=$?
    printf '%s\n' "$status" > "$out/acceptance-exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
[[ $(cat "$out/build-result.txt") == BUILD_AND_SMOKE_TESTS_PASSED ]]
(cd "$out" && sha256sum --quiet -c manifest.sha256 && sha256sum -c CpHMD-arm64.sif.sha256)
profile="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["isa_profile"])' "$out/build.json")"
case "$profile" in portable-armv8-a) scope=portable-armv8-a ;; a64fx-reference) scope='A64FX reference' ;; *) exit 2 ;; esac
mkdir "$out/acceptance" "$out/acceptance/tmp"
export TMPDIR="$out/acceptance/tmp" SINGULARITY_TMPDIR="$out/acceptance/tmp" APPTAINER_TMPDIR="$out/acceptance/tmp"
cp "${BASH_SOURCE[0]}" "$out/acceptance/executed-gate.slurm"
base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt
input="$base/solution.P4IU4M/solution"
(cd "$input/snapshot" && sha256sum --quiet -c manifest.sha256)
test -f "$out/context/portable-reference/PBMC.pkcrg"
# This accepted micro protocol is independent of the newly calculated PB table.
(cd "$base/performance.20261028.Xj0aHj/micro-input-paired" && sha256sum --quiet -c input.sha256)
cp -a "$base/performance.20261028.Xj0aHj/micro-input-paired" "$out/acceptance/micro-input"
image="$out/CpHMD-arm64.sif"
run=(singularity exec --cleanenv --bind "$out/context:/source:ro,$input:/input:ro,$out/acceptance:/out" \
    --pwd /out --env TMPDIR=/out/tmp,LC_ALL=C,OMP_NUM_THREADS=8,GMX_MAXBACKUP=-1 "$image")
# Diagnostic cycle wrappers call frozen sources. First prove those sources are
# the exact embedded controller/data, so mounting them cannot hide packaging bugs.
"${run[@]}" python3 - <<'PY'
from pathlib import Path
import hashlib,json
count=0
compiled={'CpHMD/scripts/fixgro','FFs/Amber14SBpH.ff/scripts/fixgro',
          'DelphiTools/delphi_pgf90','DelphiTools/geom_center','DelphiTools/calc_pkg_low'}
for original,installed in [('CpHMD','CpHMD'),('DelphiTools','Delphi'),('FFs','FFs'),('STs','STs'),('Databases','Databases')]:
    for path in (Path('/source')/original).rglob('*'):
        if not path.is_file(): continue
        if str(path.relative_to('/source')) in compiled: continue
        target=Path('/')/installed/path.relative_to(Path('/source')/original)
        assert target.is_file(), str(target)
        assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest(), str(target)
        count+=1
assert count>=100
Path('/out/embedded-source-identity.json').write_text(json.dumps({'passed':True,'files':count},indent=2)+'\n')
PY
"${run[@]}" bash /source/tests/arm64/run_hewl_pbmc.sh /source /input/snapshot /input/npt.tpr /out/pbmc tight
"${run[@]}" python3 /source/tests/arm64/compare_hewl_pbmc.py /source/portable-reference /out/pbmc/raw \
    --contract /source/tests/arm64/hewl-pbmc-tight-contract.json --output /out/pbmc-comparison.json
"${run[@]}" python3 /source/tests/arm64/hewl_overnight.py all /source /input/snapshot /out/all --image-scope "$scope"
"${run[@]}" python3 /source/tests/arm64/hewl_overnight.py rt /source /input/snapshot /out/rt --image-scope "$scope"
"${run[@]}" python3 /source/tests/arm64/hewl_overnight.py continue /source /input/snapshot /out/continue \
    --previous /out/rt --image-scope "$scope"
"${run[@]}" python3 /source/tests/arm64/hewl_solver_performance.py /out/micro-input /out/micro
python3 - "$out" "$profile" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);work=root/'acceptance';checks={}
for name,count in [('all',2),('rt',7),('continue',8)]:
    audit=json.loads((work/name/'overnight-audit.json').read_text())
    state=json.loads((work/name/'cycle-audit.json').read_text())
    assert audit['passed'] and audit['cycles']==count
    assert state['passed'] and state['checkpoint']['CPHMD_DONE_CYCLES']==str(count)
    checks[name]=count
for name in ['embedded-source-identity.json','pbmc-comparison.json','micro/summary.json']:
    assert json.loads((work/name).read_text())['passed']
metadata=json.loads((root/'build.json').read_text())
result={'passed':True,'isa_profile':sys.argv[2],'image_sha256':(root/'CpHMD-arm64.sif.sha256').read_text().split()[0],
    'source_commit':metadata['source_commit'],'source_dirty':metadata['source_dirty'],
    'manifest_sha256':metadata['manifest_sha256'],'cycles':checks,
    'limits':'Native regression and controller GRO/TOP/RT continuation. Not bitwise CPT continuation, physical pKa validation or complete PB convergence. New-candidate non-SVE execution remains a separate gate.'}
(work/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
PY
echo NATIVE_CANDIDATE_ACCEPTANCE_PASSED_NON_SVE_PENDING | tee "$out/acceptance-result.txt"
