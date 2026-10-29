#!/usr/bin/env python3
"""Run bounded, disconnect-safe follow-ups from the overnight SLURM launchers.

rt validates -reprod through seven real RT cycles with a finalized cycle-1
stop/resume; continue validates a fresh allocation's reduced cycle 7 -> 8.
all validates two all-site cycles; md supplies one array case of repeated
50/200-ps fixed-TPR measurements. All
scientific settings remain fixed; longer MD-only runs do not change the CpHMD
titration interval. Launchers pin the image bytes; --image-scope records which
candidate is being tested. Inputs/source stay read-only, output is project backed.
"""
import argparse
import json
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import time

import hewl_cycle as cycle
from hewl_performance import TPR_SHA256, md_health, performance, run_logged, write_json


def setting(path, name, value):
    """Replace one fixture export; allow the documented optional mdruncpu override."""
    text = path.read_text()
    pattern = r"^export " + re.escape(name) + r"=.*$"
    text, count = re.subn(pattern, lambda match: "export " + name + "=" + value, text, flags=re.M)
    if count == 0 and name == "mdruncpu":
        text += "export mdruncpu=" + value + "\n"
        count = 1
    assert count == 1, "Missing/ambiguous setting: " + name
    path.write_text(text)


def controller(source, work, label, expected):
    """Retain controller output and its actual status, including boundary code 10."""
    with (work / (label + ".log")).open("w") as output:
        result = subprocess.run(["bash", str(source / "CpHMD/scripts/CpHMD.sh"), "HEWL.settings"],
                                cwd=work, stdout=output, stderr=subprocess.STDOUT)
    (work / (label + ".exit")).write_text(str(result.returncode) + "\n")
    assert result.returncode == expected, "Unexpected controller status; inspect " + label


def check_profile(work, count):
    """Require the tested option and eight-thread policy in every real MD log."""
    for index in range(1, count + 1):
        for stage in ("relax", "effective"):
            text = (work / f"captures/cycle-{index}/{stage}.log").read_text()
            assert "-reprod" in text and "Using 8 OpenMP threads" in text


def all_sites(source, snapshot, work, image_scope):
    """Validate two actual PB/MC/topology/MD cycles with all 21 sites active."""
    work.mkdir()
    cycle.prepare(source, snapshot, work, "all")
    setting(work / "HEWL.settings", "mdruncpu", '"mdrun -nt 8 -pin on -reprod"')
    controller(source, work, "controller-all", 0)
    cycle.check(source, snapshot, work, "all")
    check_profile(work, 2)
    write_json(work / "overnight-audit.json", {"passed": True, "cycles": 2,
        "runtime_profile": "-reprod; one MPI rank/eight OpenMP threads", "image_scope": image_scope})


def rt(source, snapshot, work, image_scope="A64FX reference"):
    """Exercise full/reduced refresh, complete state mapping and a real restart."""
    work.mkdir()
    cycle.prepare(source, snapshot, work, "rt")
    setting(work / "HEWL.settings", "mdruncpu", '"mdrun -nt 8 -pin on -reprod"')
    controller(source, work, "controller-first", 10)
    shutil.copytree(work / "restart", work / "restart-boundary")
    shutil.copyfile(work / "resub_maint/checkpoint.state", work / "boundary.state")
    # An explicit guard is still present after the forced one-cycle test. The
    # two-hour allocation leaves ample room beyond this 5400-second boundary.
    setting(work / "HEWL.settings", "CPHMD_MAX_SECONDS", "5400")
    controller(source, work, "controller-resume", 0)
    cycle.check(source, snapshot, work, "rt")
    check_profile(work, 7)
    write_json(work / "overnight-audit.json", {"passed": True, "cycles": 7,
        "runtime_profile": "-reprod; one MPI rank/eight OpenMP threads", "image_scope": image_scope})


def continuation(source, snapshot, previous, work, image_scope="A64FX reference"):
    """Continue a passed finalized reduced checkpoint in a separate allocation."""
    parent = json.loads((previous / "overnight-audit.json").read_text())
    assert parent["passed"] and parent.get("image_scope", "A64FX reference") == image_scope
    audit = json.loads((previous / "cycle-audit.json").read_text())
    assert audit["checkpoint"]["CPHMD_DONE_CYCLES"] == "7"
    assert audit["checkpoint"]["CPHMD_SEGMENT_FINALIZED"] == "1"
    shutil.copytree(previous, work, symlinks=True)
    shutil.copytree(work / "restart", work / "restart-reduced-boundary")
    shutil.copyfile(work / "resub_maint/checkpoint.state", work / "reduced-boundary.state")
    (work / "cycle-audit.json").rename(work / "parent-cycle-audit.json")
    setting(work / "HEWL.settings", "SimTime", "0.008")
    protocol = json.loads((work / "protocol.json").read_text())
    protocol.update(cycles=8, continuation_from_finalized_reduced_cycle=7,
                    runtime_option="-reprod")
    write_json(work / "protocol.json", protocol)
    # Diagnostic wrappers/settings contain absolute work paths. Rebind only
    # those owned references; source/image/force-field semantics are unchanged.
    for path in [work / "HEWL.settings", *list((work / "tools").glob("*")),
                 work / "controller/scripts/update-top"]:
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if not data.startswith(b"\x7fELF"):
                path.write_bytes(data.replace(str(previous).encode(), str(work).encode()))
    controller(source, work, "controller-reduced-resume", 0)
    cycle.check(source, snapshot, work, "rt", 8)
    check_profile(work, 8)
    write_json(work / "overnight-audit.json", {"passed": True, "cycles": 8,
        "image_scope": image_scope, "separate_allocation_continuation": True,
        "limits": "Controller GRO/TOP/RT restart, not GROMACS CPT bitwise continuation."})


def long_md(snapshot, tpr, work, case, image_scope="A64FX reference", observation=None):
    """Measure the complete case or one selected observation in a bounded job.

    Splitting changes scheduler grouping only: all inputs, lengths, output
    intervals and replicate identities stay fixed. A one-observation summary
    explicitly cannot claim completion of the four-observation case.
    """
    assert cycle.digest(tpr) == TPR_SHA256
    count, profile = [(count, profile) for count in (4, 16, 48)
                      for profile in ("default", "reprod")][case]
    work.mkdir()
    ids, _, _ = cycle.gro(snapshot / "HEWL.gro")
    order = [(steps, repeat) for steps in (50000, 200000) for repeat in (1, 2)]
    random.Random(1729).shuffle(order)
    if observation is not None:
        assert 0 <= observation < len(order)
        order = [order[observation]]
    write_json(work / "protocol.json", {"cpu_count": count, "profile": profile, "order": order,
        "image_scope": image_scope,
        "observation_index": observation,
        "tpr_sha256": TPR_SHA256, "dt_ps": 0.001, "saved_interval_steps": 100,
        "allowed_cpus": sorted(os.sched_getaffinity(0)),
        "limits": "Fixed-protonation MD timing/health screen. Does not change or validate a longer CpHMD titration interval."})
    observations = []
    for steps, repeat in order:
        folder = work / f"steps-{steps}-repeat-{repeat}"
        folder.mkdir()
        command = ["/gromacs/bin/gmx", "mdrun", "-s", str(tpr), "-deffnm", "md",
                   "-nt", str(count), "-pin", "on", "-nsteps", str(steps)]
        if profile == "reprod":
            command.append("-reprod")
        env = dict(os.environ, OMP_NUM_THREADS=str(count), GMX_MAXBACKUP="-1")
        start = time.perf_counter()
        run_logged(command, folder, "mdrun.stdout", env=env)
        elapsed = time.perf_counter() - start
        row = performance((folder / "md.log").read_text())
        assert row["mpi_ranks"] * row["omp_threads"] == count
        row.update(cpu_count=count, profile=profile, steps=steps, repeat=repeat,
                   command_wall_seconds=elapsed, command=command,
                   health=md_health(folder, ids, steps))
        write_json(folder / "observation.json", row)
        observations.append(row)
        write_json(work / "observations.json", observations)
    summaries = [{"duration_ps": steps * 0.001,
        "median_command_seconds": statistics.median(row["command_wall_seconds"] for row in observations if row["steps"] == steps),
        "median_gmx_seconds": statistics.median(row["gmx_wall_seconds"] for row in observations if row["steps"] == steps)}
        for steps in sorted({row["steps"] for row in observations})]
    write_json(work / "summary.json", {"passed": True, "cpu_count": count,
        "profile": profile, "observations": len(observations), "durations": summaries,
        "complete_case": observation is None, "observation_index": observation})


def main():
    """Dispatch an explicit bounded job mode; never submit or resubmit jobs here."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["all", "rt", "continue", "md"])
    parser.add_argument("source", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--tpr", type=Path)
    parser.add_argument("--case", type=int, choices=range(6))
    parser.add_argument("--observation", type=int, choices=range(4),
                        help="Run only this shuffled observation; case requires all four indices")
    parser.add_argument("--image-scope", choices=["A64FX reference", "portable-armv8-a"],
                        default="A64FX reference", help="Provenance label; launcher separately verifies image SHA256")
    args = parser.parse_args()
    source, snapshot, output = [path.resolve() for path in (args.source, args.snapshot, args.output)]
    if args.mode == "all":
        all_sites(source, snapshot, output, args.image_scope)
    elif args.mode == "rt":
        rt(source, snapshot, output, args.image_scope)
    elif args.mode == "continue":
        assert args.previous is not None
        continuation(source, snapshot, args.previous.resolve(), output, args.image_scope)
    else:
        assert args.tpr is not None and args.case is not None
        long_md(snapshot, args.tpr.resolve(), output, args.case, args.image_scope, args.observation)


if __name__ == "__main__":
    main()
