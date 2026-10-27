#!/usr/bin/env python3
"""Complete hydrogen construction for HEWL's existing Amber CLEU RTP block.

Run only on the force field copied into a new preparation directory. CLEU
already defines the charged CpHMD carboxyl group and dummy hydrogens, so adding
a second C-terminal TDB patch corrupts connectivity. Its HDB lacks the four
dummy-H construction rules: copy those rules verbatim from the supplied CpH0-
TDB, without modifying RTP charges, atom types, bonded or nonbonded parameters.
Record the exact local change and original file for reproducibility/review.
"""
import hashlib
import json
from pathlib import Path
import re


def complete(force_field):
    """Append only the four missing CLEU HDB rules derived from this FF's TDB."""
    hdb = force_field / 'aminoacids.hdb'
    tdb = force_field / 'aminoacids.c.tdb'
    original = hdb.read_bytes()
    lines = original.decode().splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines) if re.fullmatch(r'CLEU\s+\d+\s*', line)]
    if len(headers) != 1:
        raise ValueError('Expected one CLEU hydrogen-database block')
    start = headers[0]
    count = int(lines[start].split()[1])
    if count != 6:
        raise ValueError('Expected the audited six-rule CLEU HDB; inspect this force field before applying')
    # TDB add records have an HDB-compatible construction line followed by a
    # parameter line. Retain only the four hydrogen construction lines.
    block = re.search(r'^\[ CpH0- \][^\n]*\n(.*?)(?=^\[ (?!replace |add |bonds |impropers |delete )[^]]+\]|\Z)',
                      tdb.read_text(), re.M | re.S)
    if not block:
        raise ValueError('CpH0- terminal patch absent')
    rules = [line.split() for line in block[1].splitlines()
             if re.match(r'\s*1\s+[23]\s+HC(?:11|12|21|22)\s', line)]
    if {row[2] for row in rules} != {'HC11', 'HC12', 'HC21', 'HC22'} or len(rules) != 4:
        raise ValueError('Expected exactly four supplied carboxyl dummy-H construction rules')
    for name in ('aminoacids.rtp', 'ffbonded.itp', 'ffnonbonded.itp'):
        if not (force_field / name).is_file():
            raise ValueError('Missing physical-parameter input ' + name)
    physical = {name: hashlib.sha256((force_field / name).read_bytes()).hexdigest()
                for name in ('aminoacids.rtp', 'ffbonded.itp', 'ffnonbonded.itp')}
    backup = Path('aminoacids.hdb.original')
    if backup.exists():
        raise ValueError('Refusing to overwrite the original HDB backup')
    backup.write_bytes(original)
    lines[start] = 'CLEU\t{}\n'.format(count + len(rules))
    lines[start + 1 + count:start + 1 + count] = ['\t'.join(row) + '\n' for row in rules]
    hdb.write_text(''.join(lines))
    report = {'reason': 'Construct existing CLEU dummy hydrogens without applying a second terminal patch',
              'added_construction_rules_from_cph0_tdb': rules,
              'hdb_original_sha256': hashlib.sha256(original).hexdigest(),
              'hdb_preparation_sha256': hashlib.sha256(hdb.read_bytes()).hexdigest(),
              'tdb_sha256': hashlib.sha256(tdb.read_bytes()).hexdigest(),
              'physical_parameter_files_unchanged_sha256': physical,
              'terminal_selection': 'N terminus CpH_NH3+; C terminus None, using pre-existing CLEU RTP'}
    Path('cleu-hdb-preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared CLEU hydrogen construction; existing RTP/force parameters unchanged')


if __name__ == '__main__':
    complete(Path('Amber14SBpH.ff'))
