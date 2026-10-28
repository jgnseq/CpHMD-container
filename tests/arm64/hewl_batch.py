#!/usr/bin/env python3
"""Prepare and independently audit native tests of the real SLURM generator.

The prepare allocation creates isolated settings, capture-only wrappers and a
deliberately damaged *copy* of a finalized checkpoint. The actual generated
scripts are then submitted with sbatch, including one bounded successor job.
check reads their persistent results, retained failure scratch and actual logs;
scientific errors remain FAILED in Slurm. Canonical controller/generator files
are never edited. All fixtures/results live under the authorized project root.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

import hewl_cycle as cycle

CASES = ["default-guard", "explicit-guard", "md-failure", "pb-failure", "invalid-checkpoint"]


def write_json(path, data):
    """Write reviewable metadata; no shell execution or sourced audit data."""
    path.write_text(json.dumps(data, indent=2) + "\n")


def replace_export(text, name, value):
    """Replace exactly one fixture-owned export with a shell-quoted value."""
    expression = r"^export " + re.escape(name) + r"=.*$"
    assert len(re.findall(expression, text, re.M)) == 1, "Unexpected settings layout: " + name
    return re.sub(expression, lambda _: "export " + name + "=" + shlex.quote(str(value)), text, flags=re.M)


def settings_for_batch(path, case):
    """Bind immutable tools/inputs separately from wrapper-managed /out scratch."""
    text = path.read_text()
    values = {"CpHDIR": "/fixture/controller", "GroDIRCPU": "/fixture/tools/gmx",
              "DelphiDir": "/fixture/tools", "PetitDIR": "/fixture/tools",
              "ffDIR": "/fixture/ff", "CPHMD_GATE_WORK": "/capture",
              "CPHMD_GATE_SOURCE": "/source", "GROin": "/input/HEWL.gro",
              "TOPin": "/input/HEWL.top", "NDXin": "/input/index.ndx",
              "SimTime": "0.002", "ReduceTitration": "1"}
    for name, value in values.items():
        text = replace_export(text, name, value)
    # Let the scheduler own the walltime guard. The default-guard case tests
    # actual transport through --cleanenv, without a settings-file workaround.
    text, count = re.subn(r"^export CPHMD_MAX_SECONDS=.*\n", "", text, flags=re.M)
    assert count == 1
    text += "export CPHMD_GATE_FAULT=" + shlex.quote(case) + "\n"
    return text


def instrument(fixture):
    """Observe the real runtime guard and inject only the two named test faults."""
    gmx = fixture / "tools/gmx"
    body = gmx.read_text()
    prefix = r'''#!/bin/bash
# Fixture-only observability; the real executable still performs all good calls.
if [[ ${1:-} == mdrun ]]; then
    args=("$@")
    tpr=
    for ((i=0;i<${#args[@]}-1;i++)); do
        [[ ${args[i]} != -s ]] || tpr=${args[i+1]}
    done
    printf 'cycle=%s guard=%s tpr=%s\n' "${Cycle:-unset}" "${CPHMD_MAX_SECONDS:-unset}" "$tpr" \
        >> "$CPHMD_GATE_WORK/runtime-invocations.log"
    if [[ ${CPHMD_GATE_FAULT:-} == md-failure && $tpr == TMP_effective.tpr ]]; then
        echo '{"injected_fault":"effective MD command","returned_status":73}' > "$CPHMD_GATE_WORK/fault-injection.json"
        echo 'Controlled test fault: effective MD returns 73' >&2
        exit 73
    fi
fi
'''
    assert body.startswith("#!/bin/bash\n")
    cycle.executable(gmx, prefix + body.split("\n", 1)[1])
    delphi = fixture / "tools/delphiT"
    body = delphi.read_text()
    prefix = r'''#!/bin/bash
# This case fails before the solver; the ordinary MD preflight is still real.
if [[ ${CPHMD_GATE_FAULT:-} == pb-failure ]]; then
    echo '{"injected_fault":"PB driver","returned_status":73}' > "$CPHMD_GATE_WORK/fault-injection.json"
    echo 'Controlled test fault: PB driver returns 73' >&2
    exit 73
fi
'''
    assert body.startswith("#!/bin/bash\n")
    cycle.executable(delphi, prefix + body.split("\n", 1)[1])


def scheduler_config(host, case, image):
    """Use the generator's public settings interface, with one bounded successor."""
    run = host / "runs" / case
    values = {"CPHMD_RUN_DIR": run, "CPHMD_SETTINGS_FILE": run / "01_CpHMD.settings",
              "CPHMD_IMAGE": image, "CPHMD_ACCOUNT": "f202500250cpcaa2a",
              "CPHMD_CPU_PARTITION": "dev-arm", "CPHMD_CPUS": "8", "CPHMD_MEMORY": "8G",
              "CPHMD_WALLTIME": "01:00:00", "CPHMD_SIGNAL_SECONDS": "30",
              "CPHMD_STOP_BUFFER_SECONDS": "120", "CPHMD_MAX_SECONDS_OVERRIDE": "1",
              "CPHMD_MAX_RESUB": "0" if case == "default-guard" else "1",
              "CPHMD_SCRATCH_ROOT": host / "scratch", "CPHMD_SCRATCH_POLICY": "allow-network",
              "CPHMD_JOB_NAME": "HEWL-" + case, "CPHMD_HOST_CODE_DIR": "", "CPHMD_SUBMIT": "0"}
    lines = ["#!/bin/bash", "# Fixture scheduler inputs; generated script is canonical, unmodified."]
    lines += [key + "=" + shlex.quote(str(value)) for key, value in values.items()]
    snapshot = "/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution/snapshot"
    binds = [str(host / "source") + ":/source:ro", snapshot + ":/input:ro",
             str(host / "fixtures" / case) + ":/fixture:ro",
             str(host / "captures" / case) + ":/capture", str(host / "tmp") + ":/test-tmp"]
    env = ["TMPDIR=/test-tmp", "GMX_MAXBACKUP=-1", "OMP_NUM_THREADS=8"]
    if case == "explicit-guard":
        # Public advanced configuration, intentionally separate from the
        # default-transport test. Never relabel a broken default as passed.
        env.append("CPHMD_MAX_SECONDS=1")
    exports = "--export=ALL,TMPDIR={0},SINGULARITY_TMPDIR={0},APPTAINER_TMPDIR={0}".format(host / "tmp")
    arrays = {"CPHMD_BIND_PATHS": binds, "CPHMD_CONTAINER_ENV": env,
              "CPHMD_COMMON_SBATCH_DIRECTIVES": [exports],
              "CPHMD_CPU_SBATCH_DIRECTIVES": [], "CPHMD_GPU_SBATCH_DIRECTIVES": []}
    for name, items in arrays.items():
        lines.append(name + "=(" + " ".join(shlex.quote(item) for item in items) + ")")
    return "\n".join(lines) + "\n"


def prepare(source, snapshot, root, host, image, prior):
    """Create five new cases; copy/corrupt only an isolated prior checkpoint."""
    subprocess.run(["sha256sum", "-c", "manifest.sha256"], cwd=snapshot, check=True,
                   stdout=(root / "snapshot-verification.log").open("w"))
    for directory in ["fixtures", "runs", "captures", "configs", "scratch"]:
        (root / directory).mkdir()
    for case in CASES:
        fixture = root / "fixtures" / case
        fixture.mkdir()
        cycle.prepare(source, snapshot, fixture, "rt")
        instrument(fixture)
        capture = root / "captures" / case
        capture.mkdir()
        (capture / "captures").mkdir()
        run = root / "runs" / case
        run.mkdir()
        (run / "01_CpHMD.settings").write_text(settings_for_batch(fixture / "HEWL.settings", case))
        (root / "configs" / (case + ".settings")).write_text(scheduler_config(host, case, image))
    damaged = root / "runs/invalid-checkpoint"
    for directory in ["segments", "restart", "log-files"]:
        shutil.copytree(prior / directory, damaged / directory)
    (damaged / "resub_maint").mkdir()
    shutil.copyfile(prior / "resub_maint/checkpoint.state", damaged / "resub_maint/checkpoint.state")
    for name in ["HEWL-all.sites", "HEWL_RT-sites.dat"]:
        shutil.copyfile(prior / name, damaged / name)
    removed = damaged / "segments/HEWL_CpHrun_cycles2-7.xtc"
    assert removed.is_file()
    removed.unlink()
    fingerprints = {str(path.relative_to(damaged)): cycle.digest(path)
                    for path in damaged.rglob("*") if path.is_file() and path.name != "01_CpHMD.settings"}
    write_json(root / "invalid-checkpoint-baseline.json", fingerprints)
    write_json(root / "batch-contract.json", {
        "cases": CASES, "host_root": str(host), "cycles": 2, "effective_ps_per_cycle": 1,
        "max_successors": 1, "original_generator_sha256": cycle.digest(source / "template/slurm/generate_CpHMD_slurm.sh"),
        "default_guard_expected": "host guard 1 must reach controller; cap 0 prevents accidental successor",
        "explicit_guard_expected": "cycle 1 exit 10, one real successor, cycle 2 exit 0, DONE",
        "md_failure_expected": 42, "pb_failure_expected": 43, "invalid_checkpoint_expected": 42,
        "scientific_scope": "Same short HEWL protocol; wrapper/state transaction test, not physical pKa validation"})


def assignments(path):
    """Read marker/checkpoint assignments as data rather than sourcing them."""
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def logs_and_jobs(run):
    """Read actual generated-job logs and IDs, including the sbatch successor."""
    logs = sorted((run / "slurm_files").glob("HEWL-*.log"))
    assert logs, "No generated job logs"
    jobs = [int(re.search(r"_(\d+)\.log$", path.name)[1]) for path in logs]
    return jobs, "\n".join(path.read_text() for path in logs)


def successful_case(root, snapshot, case):
    """Require valid synchronized science, clean markers and expected job count."""
    run = root / "runs" / case
    captures = root / "captures" / case / "captures"
    jobs, log = logs_and_jobs(run)
    state = assignments(run / "resub_maint/checkpoint.state")
    assert state["CPHMD_DONE_CYCLES"] == "2" and state["CPHMD_SEGMENT_FINALIZED"] == "1"
    assert assignments(run / "resub_maint/DONE")["EXIT_CODE"] == "0"
    assert not (run / "resub_maint/FAILED").exists() and not (run / "resub_maint/RUNNING").exists()
    assert len(jobs) == (2 if case == "explicit-guard" else 1), "Unexpected number of actual batch allocations"
    if case == "explicit-guard":
        assert (run / "resub_maint/resub_count").read_text().strip() == "1"
        assert "CpHMD.sh exit code: 10" in log and "CpHMD.sh exit code: 0" in log
        assert "Restart checkpoint found: 1 completed cycles" in log
        child = re.search(r"Submitted batch job (\d+)", log)
        assert child and int(child[1]) in jobs, "No actual submitted successor"
    else:
        assert not (run / "resub_maint/resub_count").exists()
    initial_ids, _, _ = cycle.gro(snapshot / "HEWL.gro")
    prior = snapshot / "HEWL.gro"
    summaries = []
    for number in [1, 2]:
        capture = captures / f"cycle-{number}"
        assert cycle.digest(capture / "before.gro") == cycle.digest(prior)
        mapping = cycle.topology_mapping(capture, snapshot / "Amber14SBpH.ff/protstates.dic")
        rt = cycle.reduced_mapping(capture, number == 1, captures / "cycle-1" if number == 2 else None)
        pseudo, _, _ = cycle.electrostatics(capture)
        stage_health = {}
        for stage in ["relax", "effective"]:
            ids, _, distances = cycle.gro(capture / (stage + ".gro"))
            assert ids == initial_ids
            stage_health[stage] = cycle.energy(capture, stage)
        summaries.append({"cycle": number, "pseudostates": len(pseudo), "topology": mapping,
                          "RT": rt, "energy": stage_health, "disulfide_nm": distances})
        prior = capture / "effective.gro"
    for extension, captured in [("gro", "effective.gro"), ("top", "after.top"), ("tpr", "effective.tpr")]:
        assert cycle.digest(run / "restart" / ("HEWL_CpHrun." + extension)) == cycle.digest(captures / "cycle-2" / captured)
    for suffix, captured in [("RT-active.sites", "HEWL-RT-active.sites"),
                             ("RT-template.occ", "TMP_RT_template.occ"), ("RT-template.mocc", "TMP_RT_template.mocc")]:
        assert (run / "restart" / ("HEWL_CpHrun." + suffix)).read_bytes() == (captures / "cycle-2" / captured).read_bytes()
    records, segments = [], []
    for path in sorted((run / "segments").glob("*.occ")):
        match = re.fullmatch(r"HEWL_CpHrun_cycles(\d+)-(\d+)\.occ", path.name)
        assert match
        start, end = map(int, match.groups())
        rows = [line.split() for line in path.read_text().splitlines() if line.strip()]
        assert len(rows) == end-start+1 and all(len(row)==21 for row in rows)
        for number, row in zip(range(start,end+1), rows):
            assert row == (captures / f"cycle-{number}/TMP_RT_current.occ").read_text().split()
            records.append(number)
        validation = (run / "log-files" / (path.stem + ".validation.log")).read_text()
        times = list(map(float,re.findall(r"(?:Reading|Last) frame\s+\d+\s+time\s+([-+\d.eE]+)", validation)))
        assert times and abs(times[0]-(start-1))<1e-4 and abs(times[-1]-end)<1e-4
        for extension, option in [("xtc", "-f"), ("edr", "-e")]:
            subprocess.run(["/gromacs/bin/gmx", "check", option, str(path.with_suffix('.'+extension))],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segments.append({"cycles":[start,end], "times_ps":[times[0],times[-1]]})
    assert sorted(records) == [1,2]
    assert not any(path.name.startswith(("TMP_", "CpHMD-run_")) for path in run.iterdir())
    scratch = root / "scratch"
    assert not any(path.is_dir() for job in jobs for path in scratch.glob(f"*/CpHMD/HEWL-{case}_{job}")), "Successful scratch not cleaned"
    observed = (root / "captures" / case / "runtime-invocations.log").read_text()
    guards = sorted(set(re.findall(r"guard=(\S+)", observed)))
    return {"passed": True, "jobs": jobs, "controller_guards": guards,
            "checkpoint": state, "cycles": summaries, "segments": segments}


def failed_case(root, case, code):
    """Require correct FAILED status, no successor and no partial publication."""
    run = root / "runs" / case
    jobs, log = logs_and_jobs(run)
    assert len(jobs) == 1 and "Submitted batch job" not in log
    marker = assignments(run / "resub_maint/FAILED")
    assert marker["EXIT_CODE"] == str(code)
    assert not (run / "resub_maint/DONE").exists() and not (run / "resub_maint/RUNNING").exists()
    assert not (run / "resub_maint/resub_count").exists()
    if case == "invalid-checkpoint":
        assert marker["STATUS"] == "persistent_checkpoint_invalid" and "MISSING:" in log
        assert not (root / "captures" / case / "runtime-invocations.log").exists()
        before = json.loads((root / "invalid-checkpoint-baseline.json").read_text())
        assert all(cycle.digest(run / name) == sha for name,sha in before.items())
        return {"passed": True, "jobs": jobs, "exit_code": code, "original_copy_unchanged": True}
    assert "not resubmitting" in log and "CpHMD.sh exit code: " + str(code) in log
    assert not (run / "resub_maint/checkpoint.state").exists()
    assert not list((run / "segments").glob("*")) and not list((run / "restart").glob("*"))
    scratch = Path(marker["SCRATCH_DIR"])
    host = Path(json.loads((root / "batch-contract.json").read_text())["host_root"])
    relative = scratch.relative_to(host)
    scratch = root / relative
    assert scratch.is_dir() and list((scratch / "log-files").glob("*failure*"))
    assert list((run / "log-files").glob("failure_job-*.log"))
    injection = json.loads((root / "captures" / case / "fault-injection.json").read_text())
    assert injection["returned_status"] == 73
    runtime = (root / "captures" / case / "runtime-invocations.log").read_text()
    assert "guard=" in runtime, "Real execution preflight missing"
    return {"passed": True, "jobs": jobs, "exit_code": code, "retained_scratch": str(relative), "fault": injection}


def check(root, snapshot):
    """Keep default guard failure distinct from supported explicit-env behavior."""
    report = {"cases": {}}
    default = successful_case(root, snapshot, "default-guard")
    default["default_guard_contract_passed"] = default["controller_guards"] == ["1"]
    # Completing both cycles proves data synchronization but fails the requested
    # guard=1 boundary contract. Keep this observation visible as REVIEW.
    assert default["controller_guards"] == ["0"], "Unexpected default guard behavior; inspect rather than assume"
    default["review"] = "Host guard 1 was not transported through --cleanenv; controller observed 0"
    report["cases"]["default-guard"] = default
    report["cases"]["explicit-guard"] = successful_case(root, snapshot, "explicit-guard")
    assert report["cases"]["explicit-guard"]["controller_guards"] == ["1"]
    for case,code in [("md-failure",42),("pb-failure",43),("invalid-checkpoint",42)]:
        report["cases"][case] = failed_case(root, case, code)
    report["explicit_configuration_and_failure_cases_passed"] = True
    report["default_guard_transport_passed"] = False
    report["status"] = "EXPLICIT_ENV_BATCH_GATE_PASSED_DEFAULT_GUARD_REVIEW_REQUIRED"
    write_json(root / "batch-audit.json", report)
    (root / "result.txt").write_text(report["status"] + "\n")
    print(json.dumps({"status":report["status"], "jobs":{key:value["jobs"] for key,value in report["cases"].items()}},indent=2))


def main():
    """Dispatch native fixture preparation or post-job scientific/status audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "check"])
    parser.add_argument("source", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--host-root", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--prior", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        assert args.host_root and args.image and args.prior
        prepare(args.source, args.snapshot, args.root, args.host_root, args.image, args.prior)
    else:
        check(args.root, args.snapshot)


if __name__ == "__main__":
    main()
