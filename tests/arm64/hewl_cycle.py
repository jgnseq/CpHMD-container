#!/usr/bin/env python3
"""Stage and independently audit the native HEWL coupled-cycle fixture.

prepare creates explicit settings and transparent executable wrappers in a new
work directory. Wrappers retain real controller inputs/outputs before cleanup;
they do not replace PB, MC, topology algebra or MD. check independently verifies
state-to-dictionary mapping, coordinate inventory, dynamics and finalized output.
run_hewl_cycle.sh and hewl-cycle.slurm are the callers; canonical drivers and the
portable snapshot are never edited. These short runs test integration, not pKas.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from compare_hewl_pbmc import electrostatics, petit_input, populations


def digest(path: Path) -> str:
    """Identify a saved byte stream for provenance and restart continuity."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable(path: Path, text: str) -> None:
    """Write a fixture-owned wrapper, never a source/image executable."""
    path.write_text(text)
    path.chmod(0o750)


def prepare(source: Path, snapshot: Path, work: Path, mode: str) -> None:
    """Build a fully explicit two-cycle all-site or seven-cycle RT experiment."""
    tools = work / "tools"
    tools.mkdir()
    (work / "captures").mkdir()
    (work / "ff").mkdir()
    shutil.copytree(snapshot / "Amber14SBpH.ff", work / "ff/Amber14SBpH.ff")
    for original, target in [("HEWL.gro", "HEWL-start.gro"), ("HEWL.top", "HEWL-start.top"), ("index.ndx", "index.ndx")]:
        shutil.copyfile(snapshot / original, work / target)
    for path in (source / "DelphiTools").iterdir():
        if path.is_file() and path.read_bytes()[:4] != b"\x7fELF":
            shutil.copyfile(path, tools / path.name)
            (tools / path.name).chmod(0o750)
    for name in ["delphi_pgf90", "geom_center", "calc_pkg_low"]:
        (tools / name).symlink_to("/Delphi/" + name)
    # The helper rereads DELPHI.pbp. Set the proven tighter profile in the
    # disposable template, then audit generated parameters after each PB call.
    pbp = tools / "DELPHI_Prot.pbp"
    text = pbp.read_text()
    for old, new in [("export maxc=0.01", "export maxc=0.0001"), ("export linit=100", "export linit=1000")]:
        assert text.count(old) == 1, "Unexpected PB template"
        text = text.replace(old, new)
    pbp.write_text(text)
    text = (tools / "delphiT").read_text()
    old = "nice -n 19 /bin/rm -rf delphiT$$ &"
    assert text.count(old) == 1, "Unexpected diagnostic cleanup"
    executable(tools / "delphiT-real", text.replace(old, 'echo "Retained diagnostics in delphiT$$"'))
    executable(tools / "delphiT", r'''#!/bin/bash
# Actual solver pipeline; save diagnostics before the controller cleans up.
set -eo pipefail
capture="$CPHMD_GATE_WORK/captures/cycle-$Cycle"
mkdir -p "$capture"
bash "$DelphiDir/delphiT-real" "$@"
cp "$2.pkcrg" "$2.g" "$2.sites" "$capture/"
python3 - "$capture" <<'PY'
from pathlib import Path
import json,sys
rows=[]
for path in Path('.').glob('delphiT*/tmp/*.prm'):
    values=dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
    assert float(values['maxc'])==0.0001, 'PB maxc override not effective'
    assert int(values['linit'])==(1000 if path.name.endswith('b.prm') else 500)
    rows.append({'file':path.name,'maxc':float(values['maxc']),'linit':int(values['linit'])})
assert rows, 'No actual PB parameter files'
Path(sys.argv[1], 'solver-profile.json').write_text(json.dumps(rows,indent=2)+'\n')
PY
''')
    executable(tools / "petit", r'''#!/bin/bash
# Preserve unmodified PETIT input/output and exact pipeline status.
set -eo pipefail
capture="$CPHMD_GATE_WORK/captures/cycle-$Cycle"
mkdir -p "$capture"
cat > "$capture/PBMC.dat"
/programs/petit1.6.1/petit "$@" < "$capture/PBMC.dat" | tee "$capture/petit.out"
''')
    # Stage a helper directory so only update-top gains a retention wrapper.
    # All other script bytes resolve directly to the frozen read-only source.
    scripts = work / "controller/scripts"
    scripts.mkdir(parents=True)
    for path in (source / "CpHMD/scripts").iterdir():
        if path.name != "update-top":
            (scripts / path.name).symlink_to(path)
    executable(scripts / "update-top", r'''#!/bin/bash
# Capture the complete applied vector and real dictionary transformation.
set -eo pipefail
capture="$CPHMD_GATE_WORK/captures/cycle-$Cycle"
mkdir -p "$capture"
cp "$1" "$capture/states.dat"
cp "$3" "$capture/before.top"
cp TMP_effective.gro "$capture/before.gro"
cp "$CPHMD_ALL_SITES_FILE" "$capture/all.sites"
for name in "$CPHMD_RT_CURRENT_OCC_FILE" "$CPHMD_RT_CURRENT_MOCC_FILE" \
            "$CPHMD_RT_ACTIVE_SITES_FILE" "$CPHMD_RT_TEMPLATE_OCC_FILE" "$CPHMD_RT_TEMPLATE_MOCC_FILE"; do
    [[ ! -f $name ]] || cp "$name" "$capture/"
done
"$CPHMD_GATE_SOURCE/CpHMD/scripts/update-top" "$@" > "$capture/after.top"
cat "$capture/after.top"
''')
    executable(tools / "gmx", r'''#!/bin/bash
# Transparent GROMACS launcher: preserve real stage outputs on success.
# The zero-step execution probe remains enabled and uses the same executable.
set -o pipefail
/gromacs/bin/gmx "$@"
status=$?
if [[ $status == 0 && ${1:-} == mdrun && ${Cycle:-} =~ ^[0-9]+$ ]]; then
    args=("$@")
    stage=
    for ((i=0;i<${#args[@]}-1;i++)); do
        if [[ ${args[i]} == -s ]]; then
            case "${args[i+1]}" in TMP_effective.tpr) stage=effective ;; TMP_relax.tpr) stage=relax ;; esac
        fi
    done
    if [[ -n $stage ]]; then
        capture="$CPHMD_GATE_WORK/captures/cycle-$Cycle"
        mkdir -p "$capture"
        for ext in gro log edr tpr xtc; do
            [[ ! -f TMP_$stage.$ext ]] || cp "TMP_$stage.$ext" "$capture/$stage.$ext" || exit 125
        done
        cp TMP_processed.top "$capture/$stage-processed.top" || exit 125
        cp "TMP_${stage}_out.mdp" "$capture/$stage.mdp" || exit 125
    fi
fi
exit "$status"
''')
    settings = (source / "template/CpHMD-basic-Amber14SBpH.settings").read_text().splitlines()
    values = {"SysName": '"HEWL"', "SimTime": "0.007" if mode == "rt" else "0.002",
              "pH": "6.0", "sites": '"all 1N 129C"', "seed": "1729",
              "RelaxSteps": "100", "EffectiveSteps": "1000", "ReduceTitration": "1" if mode == "rt" else "0",
              "RTThreshold": "0.01", "RTInterval": "5", "write_states": '"y"',
              "TOPin": '"HEWL-start.top"', "GROin": '"HEWL-start.gro"', "NDXin": '"index.ndx"',
              "maxc": "0.0001"}
    # SimTime is ns: 1000 steps * .001 ps = 1 ps = .001 ns per cycle.
    output = []
    for line in settings:
        if line.startswith("#mdp#"):
            continue
        match = re.match(r"export (\w+)=", line)
        if match and match[1] in values:
            line = f"export {match[1]}={values[match[1]]}"
        output.append(line)
    paths = {"CpHDIR": work / "controller", "GroDIRCPU": tools / "gmx", "DelphiDir": tools,
             "PetitDIR": tools, "StDIR": source / "STs/St-Amber14SBpH", "DatabaseDIR": source / "Databases",
             "ffDIR": work / "ff", "CPHMD_GATE_WORK": work, "CPHMD_GATE_SOURCE": source}
    for name, path in paths.items():
        assert "'" not in str(path), "Fixture paths must not contain shell quotes"
        output.append(f"export {name}='{path}'")
    output += ["export Cycle", "export CPHMD_KEEP_RT_DEBUG=1", "export CPHMD_COMPRESS_SEGMENT_LOGS=0",
               "export CPHMD_COMPRESS_SEGMENT_TPR=0", "export CPHMD_COMPRESS_SEGMENT_STRUCTURES=0",
               "export CPHMD_MAX_SECONDS=" + ("1" if mode == "rt" else "0")]
    # Short unrestrained NVT after the already restrained NPT preparation.
    # Keep legacy parser spellings/case for relaxation and ref_t substitution.
    mdp = """define =
integrator = md
dt = 0.001
nsteps = 1000
continuation = yes
gen-vel = no
ld-seed = 314159
cutoff-scheme = verlet
nstlist = 20
coulombtype = PME
rcoulomb = 1.0
vdwtype = Cut-Off
vdw-modifier = Potential-shift
rvdw = 1.0
rlist = 1.0
DispCorr = EnerPres
fourierspacing = 0.12
pme-order = 4
pbc = xyz
constraints = h-bonds
constraint-algorithm = lincs
lincs-order = 8
lincs-iter = 2
tcoupl = v-rescale
tc-grps = Protein SOL
tau_t = 0.5 0.5
ref_t = 310 310
Pcoupl = no
energygrps = System
nstcalcenergy = 10
nstenergy = 100
nstlog = 100
nstxout-compressed = 100
nstxout = 0
nstvout = 0
nstfout = 0
"""
    output += ["#mdp# " + line for line in mdp.splitlines()]
    (work / "HEWL.settings").write_text("\n".join(output) + "\n")
    (work / "protocol.json").write_text(json.dumps({"mode": mode, "cycles": 7 if mode == "rt" else 2,
        "effective_ps_per_cycle": 1.0, "relaxation_ps_per_cycle": 0.1, "dt_ps": 0.001,
        "source_commit": "recorded in source/source-snapshot.json", "RTInterval": 5,
        "physical_claim": "Bounded native integration test; no equilibration or pKa accuracy claim."}, indent=2) + "\n")


def atoms(path: Path) -> list:
    """Read only the inline protein atom table; solvent is represented by includes."""
    section = ""
    rows = []
    for line in path.read_text().splitlines():
        line = line.split(";", 1)[0].strip()
        if line.startswith("["):
            section = line.strip("[] ")
        elif section == "atoms" and line and not line.startswith("#"):
            row = line.split()
            if row[0].isdigit():
                rows.append(row)
    assert len(rows) == 2004, f"Protein atom inventory changed: {path}"
    return rows


def gro(path: Path) -> tuple:
    """Check finite coordinates/velocities and fixed atom order; return SG distances."""
    lines = path.read_text().splitlines()
    assert int(lines[1]) == 27989 and len(lines) == 27992, f"Changed GRO inventory: {path}"
    identities, xyz, sg = [], [], {}
    for line in lines[2:-1]:
        identities.append((int(line[:5]), line[10:15].strip(), int(line[15:20])))
        values = [float(line[i:i+8]) for i in range(20, 68, 8)]
        assert all(math.isfinite(value) for value in values), f"Non-finite GRO: {path}"
        xyz.append(values[:3])
        if line[10:15].strip() == "SG":
            sg[int(line[:5])] = values[:3]
    box = list(map(float, lines[-1].split()))
    assert all(math.isfinite(value) for value in box)
    distances = {f"{a}-{b}": math.dist(sg[a], sg[b]) for a, b in [(6,127),(30,115),(64,80),(76,94)]}
    assert all(0.18 <= value <= 0.23 for value in distances.values()), f"Disulfide separation: {path}: {distances}"
    return identities, xyz, distances


def topology_mapping(capture: Path, dictionary: Path) -> dict:
    """Independently verify every dictionary-selected atom charge/type and name.

    Dictionary parsing is separate from AWK update-top. Atom indices, residue
    numbers, names and masses must survive; non-titrating atoms retain types and
    charges. The terminal and side-chain entries at residue 1 share a residue
    number but remain separate sites in the applied vector.
    """
    before, after = atoms(capture / "before.top"), atoms(capture / "after.top")
    states = [line.split() for line in (capture / "states.dat").read_text().splitlines() if line.strip()]
    sites = [line.split() for line in (capture / "all.sites").read_text().splitlines() if line.strip()]
    assert len(states) == len(sites) == 21
    entries = [line.split() for line in dictionary.read_text().splitlines() if line.strip() and not line.startswith("#")]
    expected, renames = {}, {}
    for (state, resid, kind), site in zip(states, sites):
        state, resid = int(state), int(resid)
        assert resid == int(site[0]) and kind == site[1][:3], "State/site order mismatch"
        assert 0 <= state < len(site), "Illegal applied state"
        if kind not in {"NTR", "CTR"}:
            renames[resid] = kind[:2] + str(state)
        for entry in entries:
            if entry[0] == kind and entry[1] in {"q", "t"}:
                count = int(entry[3])
                assert state < count and len(entry) == 4 + count
                expected[resid, entry[2], entry[1]] = entry[4 + state]
    checked = changed = 0
    for left, right in zip(before, after):
        assert [left[i] for i in [0,2,4,5,7]] == [right[i] for i in [0,2,4,5,7]], "Atom identity/mass changed"
        resid, name = int(left[2]), left[4]
        for kind, index in [("t",1),("q",6)]:
            target = expected.get((resid,name,kind), left[index])
            assert (abs(float(right[index])-float(target)) <= 1e-6 if kind == "q" else right[index] == target), f"Wrong {kind} for {resid}:{name}"
            checked += (resid,name,kind) in expected
        if resid in renames and left[3][:2] == renames[resid][:2]:
            assert right[3] == renames[resid], f"Wrong residue state name at {resid}:{name}"
        changed += left[1] != right[1] or abs(float(left[6])-float(right[6])) > 1e-6
    assert checked > 0
    return {"applied_sites": len(states), "dictionary_atom_parameters_checked": checked,
            "atoms_with_changed_type_or_charge": changed, "protein_charge_e": sum(float(row[6]) for row in after)}


def state_file(path: Path) -> dict:
    """Parse checkpoint assignments as data; never source/eval them in the auditor."""
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def energy(capture: Path, stage: str) -> dict:
    """Read real EDR potential/temperature records, checking labels and duration.

    The broad 290--330 K mean-temperature range is a short-run health screen,
    not a sampling-accuracy claim. Relaxation has only two saved energy frames.
    """
    output = capture / f"{stage}-energy.xvg"
    result = subprocess.run(["/gromacs/bin/gmx", "energy", "-f", str(capture / f"{stage}.edr"),
                             "-o", str(output)], input="Potential\nTemperature\n0\n", text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (capture / f"{stage}-energy-analysis.log").write_text(result.stdout)
    assert result.returncode == 0, "EDR energy extraction failed"
    text = output.read_text()
    legends = {name: int(index) + 1 for index, name in re.findall(r'@\s+s(\d+)\s+legend\s+"([^"]+)"', text)}
    assert set(legends) == {"Potential", "Temperature"}, "Wrong energy quantities"
    rows = [list(map(float, line.split())) for line in text.splitlines() if line.strip() and not line.lstrip().startswith(("#", "@"))]
    assert len(rows) >= 2 and all(len(row) == 3 and all(math.isfinite(x) for x in row) for row in rows), "Incomplete/nonfinite energies"
    assert all(a[0] < b[0] for a,b in zip(rows,rows[1:])), "Non-increasing energy time"
    duration = 1.0 if stage == "effective" else 0.1
    assert abs(rows[-1][0] - rows[0][0] - duration) < 0.0001, "Wrong integration duration"
    temperature = sum(row[legends["Temperature"]] for row in rows) / len(rows)
    assert 290 <= temperature <= 330, "Short-run temperature health screen failed"
    return {"duration_ps": duration, "records": len(rows), "mean_temperature_K": temperature,
            "potential_min_kJ_mol": min(row[legends["Potential"]] for row in rows),
            "potential_max_kJ_mol": max(row[legends["Potential"]] for row in rows)}


def reduced_mapping(capture: Path, refresh: bool, previous: Path | None) -> dict:
    """Verify RT selection and full-vector merging independently of the AWK code."""
    all_rows = [line.split() for line in (capture / "all.sites").read_text().splitlines() if line.strip()]
    active = [line.split() for line in (capture / "HEWL-RT-active.sites").read_text().splitlines() if line.strip()]
    template = (capture / "TMP_RT_template.occ").read_text().split()
    template_means = (capture / "TMP_RT_template.mocc").read_text().split()
    current = list(map(int, (capture / "TMP_RT_current.occ").read_text().split()))
    current_means = list(map(float, (capture / "TMP_RT_current.mocc").read_text().split()))
    states = [int(line.split()[0]) for line in (capture / "states.dat").read_text().splitlines() if line.strip()]
    assert len(template) == len(template_means) == len(current) == len(current_means) == 21
    assert current == states, "Applied vector differs from recorded current vector"
    pb = [line.split() for line in (capture / "PBMC.sites").read_text().splitlines() if line.strip()]
    sites, _, _ = petit_input(capture, len(pb))
    means, final = populations(capture / "petit.out", sites)
    if refresh:
        probs = {}
        for line in (capture / "petit.out").read_text().splitlines():
            row = line.split()
            if row and row[0] == "." and row[3].isdigit():
                probs[int(row[3])] = list(map(float, row[5:]))
        keep = [i for i,row in enumerate(all_rows) if row[1][:3] in {"NTR","CTR"} or max(probs[i]) <= 0.99]
        assert active == [all_rows[i] for i in keep], "Wrong RT threshold/terminal selection"
        for i in range(21):
            if i in keep:
                assert template[i] == template_means[i] == "-" and current[i] == final[i]
            else:
                # Python and gawk both choose the first maximum on a tie.
                fixed = max(range(len(probs[i])), key=lambda j: probs[i][j])
                assert int(template[i]) == current[i] == fixed, "Wrong fixed state"
                assert abs(float(template_means[i]) - means[i]) < 2e-6
            assert abs(current_means[i] - means[i]) < 2e-6
    else:
        assert previous is not None
        for name in ["HEWL-RT-active.sites","TMP_RT_template.occ","TMP_RT_template.mocc"]:
            assert (capture / name).read_bytes() == (previous / name).read_bytes(), "RT templates changed between refreshes/restart"
        j = 0
        for i in range(21):
            if template[i] == "-":
                assert current[i] == final[j] and abs(current_means[i] - means[j]) < 2e-6
                j += 1
            else:
                assert current[i] == int(template[i]) and abs(current_means[i] - float(template_means[i])) < 2e-6
        assert j == len(active), "Incomplete active-to-full vector merge"
    return {"active_sites": len(active), "fixed_sites": 21-len(active), "independent_selection_and_merge_passed": True}


def check(source: Path, snapshot: Path, work: Path, mode: str, cycles: int | None = None) -> None:
    """Require real valid cycles, correct scientific mapping and finalized output."""
    count = cycles if cycles is not None else (7 if mode == "rt" else 2)
    assert (mode, count) in {("all",2),("rt",7),("rt",8)}, "Unsupported fixture cycle target"
    initial_ids, _, _ = gro(snapshot / "HEWL.gro")
    summaries = []
    all_sites = (snapshot / "HEWL-all.sites").read_bytes()
    previous = snapshot / "HEWL.gro"
    for cycle in range(1, count + 1):
        capture = work / f"captures/cycle-{cycle}"
        assert (capture / "all.sites").read_bytes() == all_sites, "All-site identity changed"
        assert digest(capture / "before.gro") == digest(previous), "Coordinates did not propagate between cycles/restart"
        mapping = topology_mapping(capture, snapshot / "Amber14SBpH.ff/protstates.dic")
        pb_sites = [line for line in (capture / "PBMC.sites").read_text().splitlines() if line.strip()]
        sites, _, _ = petit_input(capture, len(pb_sites))
        populations(capture / "petit.out", sites)
        pseudo, _, _ = electrostatics(capture)
        if mode == "all" or cycle in (1, 6):
            assert len(pb_sites) == 21 and len(pseudo) == 69, "Missing full-site refresh"
        else:
            active = [line for line in (capture / "HEWL-RT-active.sites").read_text().splitlines() if line.strip()]
            assert 0 < len(active) < 21 and pb_sites == active, "Wrong reduced site subset"
        energies = {}
        for stage in ["relax", "effective"]:
            ids, xyz, distances = gro(capture / f"{stage}.gro")
            assert ids == initial_ids, "Atom order changed"
            log = (capture / f"{stage}.log").read_text()
            assert "Finished mdrun" in log, "Incomplete native dynamics"
            assert not re.search(r"LINCS WARNING|constraint failure|Fatal error|\bnan\b", log, re.I), "MD failure diagnostic"
            subprocess.run(["/gromacs/bin/gmx", "check", "-e", str(capture / f"{stage}.edr")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if stage == "effective":
                subprocess.run(["/gromacs/bin/gmx", "check", "-f", str(capture / f"{stage}.xtc")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            energies[stage] = energy(capture, stage)
        _, before_xyz, _ = gro(capture / "before.gro")
        assert any(math.dist(a,b) > 1e-5 for a,b in zip(before_xyz, xyz)), "MD did not advance coordinates"
        rt = reduced_mapping(capture, cycle in (1,6), work / f"captures/cycle-{cycle-1}" if cycle > 1 else None) if mode == "rt" else None
        summaries.append({"cycle": cycle, "PB_sites": len(pb_sites), "PB_pseudostates": len(pseudo),
                          "topology_mapping": mapping, "disulfide_nm": distances, "energy_health": energies, "reduced_titration": rt})
        previous = capture / "effective.gro"
    state = state_file(work / "resub_maint/checkpoint.state")
    assert state["CPHMD_DONE_CYCLES"] == str(count) and state["CPHMD_SEGMENT_FINALIZED"] == "1"
    assert digest(work / "restart/HEWL_CpHrun.gro") == digest(previous)
    if mode == "rt":
        boundary = state_file(work / "boundary.state")
        assert boundary["CPHMD_DONE_CYCLES"] == "1" and boundary["CPHMD_SEGMENT_FINALIZED"] == "1"
        assert "Restart checkpoint found: 1 completed cycles" in (work / "controller-resume.log").read_text()
        assert state["CPHMD_RT_LAST_FULL_CYCLE"] == "6"
        if count == 8:
            reduced_boundary = state_file(work / "reduced-boundary.state")
            assert reduced_boundary["CPHMD_DONE_CYCLES"] == "7" and reduced_boundary["CPHMD_SEGMENT_FINALIZED"] == "1"
            assert digest(work / "restart-reduced-boundary/HEWL_CpHrun.gro") == digest(work / "captures/cycle-8/before.gro")
            assert "Restart checkpoint found: 7 completed cycles" in (work / "controller-reduced-resume.log").read_text()
    segments = []
    for path in sorted((work / "segments").glob("*.occ")):
        match = re.fullmatch(r"HEWL_CpHrun_cycles(\d+)-(\d+)\.occ", path.name)
        assert match, "Unexpected segment naming"
        start, end = map(int, match.groups())
        rows = [line.split() for line in path.read_text().splitlines() if line.strip()]
        assert len(rows) == end-start+1 and all(len(row) == 21 for row in rows), "Incomplete full-site occupation output"
        means = [list(map(float,line.split())) for line in path.with_suffix('.mocc').read_text().splitlines() if line.strip()]
        assert len(means) == len(rows) and all(len(row)==21 and all(math.isfinite(x) and 0<=x<=1 for x in row) for row in means), "Invalid mean-occupancy segment"
        validation = (work / "log-files" / (path.stem + ".validation.log")).read_text()
        times = list(map(float,re.findall(r"(?:Reading|Last) frame\s+\d+\s+time\s+([-+\d.eE]+)", validation)))
        assert times and abs(times[0]-(start-1))<1e-4 and abs(times[-1]-end)<1e-4, "Segment trajectory clock discontinuity"
        frame_count = re.search(r"^Time\s+(\d+)\s+", validation, re.M)
        assert frame_count and int(frame_count[1])==(end-start+1)*10+1, "Missing/duplicated segment trajectory frames"
        segments.append({"start_cycle":start,"end_cycle":end,"first_time_ps":times[0],"last_time_ps":times[-1],"frames":int(frame_count[1])})
    segments.sort(key=lambda row:row["start_cycle"])
    assert segments[0]['start_cycle']==1 and segments[-1]['end_cycle']==count
    assert all(a['end_cycle']+1==b['start_cycle'] for a,b in zip(segments,segments[1:])), "Missing/overlapping cycle segments"
    report = {"passed": True, "mode": mode, "cycles": summaries, "checkpoint": state,
              "segments":segments,
              "limits": "Short integration gate; restart is controller GRO/TOP/RT state, not bitwise GROMACS CPT continuation."}
    (work / "cycle-audit.json").write_text(json.dumps(report, indent=2) + "\n")


def main() -> None:
    """Dispatch staging or validation with explicit source/snapshot/work paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "check"])
    parser.add_argument("source", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("mode", choices=["all", "rt"])
    parser.add_argument("--cycles", type=int, choices=[2,7,8])
    args = parser.parse_args()
    if args.action == "prepare":
        assert args.cycles is None, "Cycle override is for continuation audit only"
        prepare(args.source.resolve(), args.snapshot.resolve(), args.work.resolve(), args.mode)
    else:
        check(args.source.resolve(), args.snapshot.resolve(), args.work.resolve(), args.mode, args.cycles)


if __name__ == "__main__":
    main()
