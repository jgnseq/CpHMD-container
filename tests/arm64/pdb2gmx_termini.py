#!/usr/bin/env python3
"""Drive HEWL's pdb2gmx terminal menus by patch name, preserving the transcript.

Called inside the test image by prepare_hewl_topology.sh. Only the expected
LY3-1 / LEU-129 menus are accepted; choose CpH_NH3+ and None from their live
numbered options. CLEU's existing charged carboxyl block supplies the C terminus;
its dummy-H construction rules are completed separately. Do not patch it twice.
Bound the runtime so closed/changed menus cannot hang a job.
"""
import argparse
import json
from pathlib import Path
import re
import selectors
import subprocess
import time


def generate(command, log_path):
    """Run pdb2gmx, answer two named menus and fail on incomplete interaction."""
    wanted = [('start', 'LY3-1', 'CpH_NH3+'), ('end', 'LEU-129', 'None')]
    answers, active = [], None
    # Line buffering is required when GROMACS stdout is a pipe rather than a
    # terminal. Read bytes with os.read so Python text buffering cannot hide a
    # complete menu line from selectors while pdb2gmx waits for an answer.
    import os
    process = subprocess.Popen(['stdbuf', '-oL', '-eL'] + command,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    pending = b''
    deadline = time.monotonic() + 90
    try:
        with log_path.open('wb') as transcript:
            while selector.get_map():
                if time.monotonic() > deadline:
                    raise RuntimeError('Timed out waiting for the expected terminal menus')
                for key, _ in selector.select(timeout=1):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    transcript.write(chunk)
                    transcript.flush()
                    pending += chunk
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        text = line.decode(errors='replace')
                        menu = re.fullmatch(r'Select (start|end) terminus type for (\S+)', text)
                        if menu:
                            if len(answers) >= len(wanted) or tuple(menu.groups()) != wanted[len(answers)][:2]:
                                raise RuntimeError('Unexpected terminal menu: ' + text)
                            active = wanted[len(answers)]
                        option = re.fullmatch(r'\s*(\d+):\s*(\S+)\s*', text)
                        if active and option and option[2] == active[2]:
                            process.stdin.write((option[1] + '\n').encode())
                            process.stdin.flush()
                            answers.append({'end': active[0], 'residue': active[1],
                                            'patch': active[2], 'menu_index': int(option[1])})
                            active = None
            status = process.wait(timeout=5)
            if status or len(answers) != 2:
                raise RuntimeError('pdb2gmx failed or did not confirm both menus; exit {}'.format(status))
        return answers
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    """Use fixed HEWL filenames; record argv and the actual selected indices."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gmx', default='/gromacs/bin/gmx')
    args = parser.parse_args()
    command = [args.gmx, 'pdb2gmx', '-f', 'protein_CpHMD.pdb', '-o', 'HEWL.gro',
               '-p', 'HEWL.top', '-i', 'posre.itp', '-ff', 'Amber14SBpH',
               '-water', 'tip3p', '-ter', '-ignh', '-merge', 'all']
    answers = generate(command, Path('pdb2gmx.log'))
    Path('terminal-selection.json').write_text(json.dumps({'command': command, 'selections': answers}, indent=2) + '\n')
    print('PASS: selected CpH_NH3+ and None (existing CLEU) by live menu names')


if __name__ == '__main__':
    main()
