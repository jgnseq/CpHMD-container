#!/bin/bash
# Detached, bounded mini05 follow-up for one portable candidate recovery root.
# Wait for its archive, pull/check it with existing SSH credentials, require the
# native acceptance receipt, then execute the exact SIF under non-SVE QEMU.
# Only explicit regular archive members are written. No root, binfmt, package
# installation, source edits or Git operation is needed. Run under timeout 8h.
set -Eeuo pipefail
root="$(realpath "${1:?Supply mini05 recovery-pull root}")"
remote="${2:?Supply project recovery root}"
case "$root" in /home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.*) ;; *) exit 2 ;; esac
exec 8>"$root/verification.lock"
flock -n 8 || exit 3
preserve_status () {
    # Preserve the combined result independently of a live SSH/client session.
    status=$?
    printf '%s\n' "$status" > "$root/verification.exit"
    exit "$status"
}
trap preserve_status EXIT
printf '%s\n' RUNNING > "$root/verification.exit"
export CPHMD_RECOVERY_WAIT_ATTEMPTS=840
bash "$root/pull_recovery.sh" "$root" "$remote" candidate
python3 - "$root" <<'PY'
"""Extract only the checked candidate and minimal same-candidate gate sources."""
from pathlib import Path
import hashlib,json,shutil,sys,tarfile
root=Path(sys.argv[1]);archive=root/'candidate/CpHMD-portable-default-validation.tar.gz'
wanted={'candidate/CpHMD-arm64.sif':'image.sif',
        'candidate/acceptance/acceptance.json':'native-acceptance.json',
        'candidate/acceptance/micro/observations.json':'native-micro-observations.json'}
for name in ['check_non_sve_runtime.py','hewl_solver_performance.py','compare_hewl_pbmc.py']:
    wanted['candidate/context/tests/arm64/'+name]='source/tests/arm64/'+name
seen=set()
with tarfile.open(archive,'r|gz') as source:
    for member in source:
        name=Path(member.name)
        assert not name.is_absolute() and '..' not in name.parts
        target=wanted.get(member.name)
        prefix='candidate/acceptance/micro-input/'
        if target is None and member.isfile() and member.name.startswith(prefix):
            target='micro-input/'+member.name[len(prefix):]
        if target is None:continue
        assert member.isfile()
        dest=root/target;dest.parent.mkdir(parents=True,exist_ok=True)
        with source.extractfile(member) as data,dest.open('wb') as output:
            shutil.copyfileobj(data,output)
        seen.add(member.name)
assert set(wanted)<=seen
native=json.loads((root/'native-acceptance.json').read_text())
assert native['passed'] and native['isa_profile']=='portable-armv8-a', 'Native candidate gates did not pass'
with (root/'image.sif').open('rb') as stream:
    assert hashlib.file_digest(stream,'sha256').hexdigest()==native['image_sha256']
files=sorted((root/'source').rglob('*.py'))
(root/'source/source.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root/'source'))+'\n' for p in files))
PY
# Derive the primary ARM64 filesystem partition from the installed SIF tool;
# profile/metadata growth may change its byte offset or descriptor ID.
singularity sif list "$root/image.sif" > "$root/sif-layout.txt"
partition="$(python3 - "$root/sif-layout.txt" <<'PY'
from pathlib import Path
import sys
rows=[line.split('|')[0].strip() for line in Path(sys.argv[1]).read_text().splitlines()
      if 'FS (' in line and 'Squashfs' in line and 'arm64' in line and 'System' in line]
assert len(rows)==1 and rows[0].isdigit()
print(rows[0])
PY
)"
singularity sif dump "$partition" "$root/image.sif" > "$root/runtime.squashfs"
unsquashfs -no-xattrs -no-progress -processors 2 -d "$root/rootfs" "$root/runtime.squashfs" > "$root/extraction.log" 2>&1
tools=/home/jsequeira/Projects/side/06_CpHMD-container/validation/non-sve.20261029.sj7GvV
"$tools/qemu/usr/bin/qemu-aarch64" --version > "$root/qemu-version.txt"
python3 "$root/source/tests/arm64/check_non_sve_runtime.py" --rootfs "$root/rootfs" \
    --qemu "$tools/qemu/usr/bin/qemu-aarch64" --cross "$tools/cross" \
    --source "$root/source" --inputs "$root/micro-input" --output "$root/non-sve"
python3 - "$root" <<'PY'
"""Combine independent gates; retain printed-energy/MC comparisons as evidence."""
from pathlib import Path
import json,sys
root=Path(sys.argv[1]);native=json.loads((root/'native-acceptance.json').read_text())
audit=json.loads((root/'non-sve/audit.json').read_text())
assert native['passed'] and audit['passed']
rows=json.loads((root/'native-micro-observations.json').read_text());comparison=[]
for row in audit['PB']:
    baseline=next(item for item in rows if item['component']=='delphi' and item['deck']==row['deck'])
    comparison.append({'deck':row['deck'],'printed_energy_difference_kT':abs(row['energy_kT']-baseline['energy_kT']),
                       'same_last_iteration_count':row['last_reported_iterations']==baseline['last_reported_iterations']})
mc=next(item for item in rows if item['component']=='petit')
result={'passed':True,'image_sha256':native['image_sha256'],'native_acceptance':True,
        'non_sve_executed_path_acceptance':True,'cpu_model':audit['cpu_model'],
        'printed_PB_comparison':comparison,'MC_means_equal':mc['means']==audit['MC_means'],
        'MC_final_states_equal':mc['final_states']==audit['MC_final_states'],
        'limits':'Candidate-specific native and non-SVE emulation gates; physical other-ARM hardware, absolute PB convergence and production pKa accuracy are not established.'}
(root/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
PY
echo PORTABLE_DEFAULT_CANDIDATE_NATIVE_AND_NON_SVE_GATES_PASSED
