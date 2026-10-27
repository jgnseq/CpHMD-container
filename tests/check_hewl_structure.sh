#!/bin/bash
# Gate the real pinned HEWL fixture before topology or compute jobs are created.
# Verify protein completeness, specific alternate choices and disulfide geometry;
# reject a changed source and accidental overwrite. No MD/container is needed.
set -Eeuo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/cphmd-hewl-structure.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
source_pdb="$repo/tests/fixtures/hewl-4lzt/source/4LZT.pdb"
prepare="$repo/tests/arm64/prepare_hewl_structure.py"
python3 "$prepare" --source "$source_pdb" --output-dir "$work/prepared"
python3 - "$work/prepared" <<'PY'
"""Check deposited-structure invariants and independently measure S–S distances."""
import json, math, sys
from pathlib import Path
root=Path(sys.argv[1]); audit=json.loads((root/'structure-audit.json').read_text())
assert len(audit['residues'])==129
rows=(root/'4LZT-protein.pdb').read_text().splitlines()
atoms=[row for row in rows if row.startswith('ATOM  ')]
assert len(atoms)==1001 and all(row[16]==' ' for row in atoms)
assert not any(row.startswith(('HETATM','ANISOU')) for row in rows)
choices={row['residue'][1]:row['selected'] for row in audit['alternate_location_choices']}
assert choices[43]=='A'  # Equal occupancy: documented A tie-break.
assert choices[85]==choices[86]==choices[109]=='B'  # Higher-occupancy B states.
sulfur={int(row[22:26]):tuple(float(row[i:i+8]) for i in (30,38,46))
        for row in atoms if row[12:16].strip()=='SG'}
assert len(sulfur)==8
for first,second in [(6,127),(30,115),(64,80),(76,94)]:
    distance=math.sqrt(sum((a-b)**2 for a,b in zip(sulfur[first],sulfur[second])))
    assert 1.8<distance<2.3, (first,second,distance)
    print('PASS: deposited CYS {}–{} S–S distance {:.3f} Å'.format(first,second,distance))
PY
if python3 "$prepare" --source "$source_pdb" --output-dir "$work/prepared" > "$work/overwrite.log" 2>&1; then
    echo 'FAIL: existing preparation was overwritten' >&2; exit 1
fi
grep -q 'Refusing to overwrite' "$work/overwrite.log"
cp "$source_pdb" "$work/changed.pdb"
printf '\n' >> "$work/changed.pdb"
if python3 "$prepare" --source "$work/changed.pdb" --output-dir "$work/rejected" > "$work/changed.log" 2>&1; then
    echo 'FAIL: unpinned source was accepted' >&2; exit 1
fi
test ! -e "$work/rejected"
grep -q 'Source differs from the pinned' "$work/changed.log"
echo 'PASS: HEWL fixture geometry, provenance and overwrite safeguards'
