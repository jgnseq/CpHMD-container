#!/usr/bin/env python3
"""Measure native A64FX HEWL costs without changing the scientific controller.

hewl-performance.slurm calls md for repeated fixed-TPR CPU scaling, or coupled
for three independently prepared two-cycle runs. timed wraps existing diagnostic
launchers, preserving stdin/stdout/status and recording wall time. Scientific
acceptance reuses hewl_cycle's independent auditor; timing alone never passes a
run. Large trajectories and the image stay outside Git in project storage.
"""
import argparse
import json
import math
import os
from pathlib import Path
import random
import re
import shlex
import statistics
import subprocess
import sys
import time

import hewl_cycle as cycle

COUNTS = [4, 8, 16, 24, 48]
STEPS = 5000
TPR_SHA256 = "7276106632db360dadc02f3cc0075006ee9de10d029e143a590c2a1e02113e48"


def write_json(path, value):
    """Save readable provenance/acceptance data for the off-cluster evidence set."""
    path.write_text(json.dumps(value, indent=2) + "\n")


def performance(text):
    """Parse one completed GROMACS log, including 2026's four performance fields.

    Wall time is the second Time column. Never infer it from the CPU column or
    silently select one of several concatenated runs. Require finite positive
    values and the expected MPI/OpenMP topology before ranking observations.
    """
    assert "Finished mdrun" in text, "Incomplete dynamics log"
    assert not re.search(r"LINCS WARNING|constraint failure|Fatal error|\bnan\b", text, re.I)
    times = re.findall(r"^\s*Time:\s+(.+)$", text, re.M)
    rates = re.findall(r"^\s*Performance:\s+(.+)$", text, re.M)
    assert len(times) == len(rates) == 1, "Expected one complete timing record"
    timing, rate = [float(x) for x in times[0].split()], [float(x) for x in rates[0].split()]
    assert len(timing) == 3 and len(rate) in (2, 4), "Unknown GROMACS timing format"
    assert all(math.isfinite(x) and x > 0 for x in timing + rate)
    mpi = re.search(r"Using (\d+) MPI (?:thread|process)", text)
    omp = re.search(r"Using (\d+) OpenMP threads?", text)
    assert mpi and omp, "Missing actual thread topology"
    return {"gmx_core_seconds": timing[0], "gmx_wall_seconds": timing[1],
            "ns_per_day": rate[0], "mpi_ranks": int(mpi[1]), "omp_threads": int(omp[1])}


def timed(output, name, command):
    """Time one real command with inherited streams, append one atomic JSON row.

    Wrappers can be nested (PB invokes GROMACS conversion). The coupled summary
    deliberately sums only named, disjoint top-level PB/MC/topology/MD stages.
    """
    start = time.perf_counter()
    result = subprocess.run(command)
    row = {"tool": name, "argv": command, "cycle": os.environ.get("Cycle"),
           "wall_seconds": time.perf_counter() - start, "returncode": result.returncode,
           "allowed_cpus": sorted(os.sched_getaffinity(0))}
    with output.open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    return result.returncode


def run_logged(command, folder, log, env=None, stdin=None):
    """Execute a real engine/reader and retain output; fail on its actual status."""
    with (folder / log).open("w") as stream:
        subprocess.run(command, cwd=folder, env=env, input=stdin, text=True,
                       stdout=stream, stderr=subprocess.STDOUT, check=True)


def md_health(folder, expected_ids, steps=5000):
    """Check real outputs for the frozen 1-fs, every-100-step HEWL protocol.

    The default retains the original 5-ps gate. Overnight callers supply longer
    step counts; expected duration/frame/energy counts come from that protocol,
    never from whatever incomplete output happens to have been produced.
    """
    assert steps > 0 and steps % 100 == 0
    expected_frames, duration = steps // 100 + 1, steps * 0.001
    ids, _, distances = cycle.gro(folder / "md.gro")
    assert ids == expected_ids
    run_logged(["/gromacs/bin/gmx", "check", "-f", "md.xtc"], folder, "xtc-check.log")
    check = (folder / "xtc-check.log").read_text()
    frames = re.search(r"^Time\s+(\d+)\s+", check, re.M)
    clocks = list(map(float, re.findall(r"(?:Reading|Last) frame\s+\d+\s+time\s+([-+\d.eE]+)", check)))
    assert frames and int(frames[1]) == expected_frames and clocks
    assert abs(clocks[-1] - clocks[0] - duration) < 1e-4
    run_logged(["/gromacs/bin/gmx", "check", "-e", "md.edr"], folder, "edr-check.log")
    run_logged(["/gromacs/bin/gmx", "energy", "-f", "md.edr", "-o", "energy.xvg"],
               folder, "energy-analysis.log", stdin="Potential\nTemperature\n0\n")
    text = (folder / "energy.xvg").read_text()
    legends = {name: int(index) + 1 for index, name in re.findall(r'@\s+s(\d+)\s+legend\s+"([^"]+)"', text)}
    assert set(legends) == {"Potential", "Temperature"}
    rows = [list(map(float, line.split())) for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "@"))]
    assert len(rows) == expected_frames and all(len(row) == 3 and all(math.isfinite(x) for x in row) for row in rows)
    assert abs(rows[-1][0] - rows[0][0] - duration) < 1e-4
    temperature = statistics.mean(row[legends["Temperature"]] for row in rows)
    assert 290 <= temperature <= 330
    return {"passed": True, "frames": expected_frames, "duration_ps": duration,
            "mean_temperature_K": temperature, "disulfide_nm": distances}


def md(source, snapshot, root, tpr, counts=None):
    """Repeat the same 5-ps input twice per CPU count, on one exclusive node.

    A fixed randomized order reduces systematic order bias. Each observation
    starts a fresh engine with identical TPR bytes and thermostat seed, rather
    than continuing its predecessor. Output and startup costs are retained.
    """
    assert cycle.digest(tpr) == TPR_SHA256
    root.mkdir()
    ids, _, _ = cycle.gro(snapshot / "HEWL.gro")
    counts = COUNTS if counts is None else counts
    order = [(rep, count) for rep in (1, 2) for count in counts]
    random.Random(1729).shuffle(order)
    write_json(root / "protocol.json", {"order": order, "steps": STEPS, "dt_ps": 0.001,
        "tpr_sha256": TPR_SHA256, "allowed_cpus": sorted(os.sched_getaffinity(0)),
        "policy": "CPU controller default: -nt N -pin on, OMP_NUM_THREADS=N; fresh process each time",
        "limits": "Two timing repeats on one A64FX node; not independent scientific replicas or a universal ARM benchmark."})
    observations = []
    for rep, count in order:
        folder = root / f"cpu-{count}-repeat-{rep}"
        folder.mkdir()
        command = ["/gromacs/bin/gmx", "mdrun", "-s", str(tpr), "-deffnm", "md",
                   "-nt", str(count), "-pin", "on", "-nsteps", str(STEPS)]
        env = dict(os.environ, OMP_NUM_THREADS=str(count), GMX_MAXBACKUP="-1")
        start = time.perf_counter()
        run_logged(command, folder, "mdrun.stdout", env=env)
        elapsed = time.perf_counter() - start
        record = performance((folder / "md.log").read_text())
        assert record["mpi_ranks"] * record["omp_threads"] == count
        record.update(cpu_count=count, repeat=rep, command_wall_seconds=elapsed,
                      command=command, health=md_health(folder, ids))
        write_json(folder / "observation.json", record)
        observations.append(record)
        write_json(root / "observations.json", observations)
    summary = []
    for count in counts:
        rows = [row for row in observations if row["cpu_count"] == count]
        assert len(rows) == 2 and all(row["health"]["passed"] for row in rows)
        walls = [row["command_wall_seconds"] for row in rows]
        median = statistics.median(walls)
        summary.append({"cpu_count": count, "median_command_wall_seconds": median,
                        "min_seconds": min(walls), "max_seconds": max(walls),
                        "median_gmx_ns_per_day": statistics.median(row["ns_per_day"] for row in rows),
                        "median_thread_seconds": count * median})
    write_json(root / "summary.json", {"passed": True, "observations": len(observations), "counts": summary,
        "fastest_observed_cpu_count": min(summary, key=lambda row: row["median_command_wall_seconds"])["cpu_count"],
        "allocation_note": "Thread-seconds are computational demand, not billed allocation cost. See launcher/accounting for the reservation and protocol.json for the allowed CPU set."})


def instrument(work, source):
    """Add transparent timers around existing retained-diagnostic fixture tools."""
    for relative, name in [("tools/gmx", "gmx"), ("tools/delphiT", "pb"),
                           ("tools/petit", "mc"), ("controller/scripts/update-top", "topology")]:
        path = work / relative
        actual = path.with_name(path.name + "-timed-target")
        path.rename(actual)
        command = ["python3", str(source / "tests/arm64/hewl_performance.py"), "timed",
                   str(work / "timings.jsonl"), name, str(actual)]
        cycle.executable(path, "#!/bin/bash\n# Retain original streams and command status through a timer.\nexec "
                         + shlex.join(command) + ' "$@"\n')


def coupled(source, snapshot, root, counts=None):
    """Measure full PB/MC/update/MD workflow at 4/8/16 CPUs, one sample each.

    Reuse all-site two-cycle fixtures and independent scientific audits. Keep
    diagnostic retention identical at all counts. A 2700-second explicit guard
    is bounded inside a 90-minute allocation; no scheduler resubmission occurs.
    """
    root.mkdir()
    summaries = []
    for count in ([16, 4, 8] if counts is None else counts):
        work = root / f"cpu-{count}"
        work.mkdir()
        cycle.prepare(source, snapshot, work, "all")
        path = work / "HEWL.settings"
        text = path.read_text()
        assert text.count("export nCPU=8") == text.count("export CPHMD_MAX_SECONDS=0") == 1
        path.write_text(text.replace("export nCPU=8", f"export nCPU={count}")
                        .replace("export CPHMD_MAX_SECONDS=0", "export CPHMD_MAX_SECONDS=2700"))
        instrument(work, source)
        start = time.perf_counter()
        run_logged(["bash", str(source / "CpHMD/scripts/CpHMD.sh"), "HEWL.settings"], work, "controller-first.log")
        elapsed = time.perf_counter() - start
        # Audit after timing, so analysis is not charged to controller runtime.
        cycle.check(source, snapshot, work, "all")
        rows = [json.loads(line) for line in (work / "timings.jsonl").read_text().splitlines()]
        assert rows and all(row["returncode"] == 0 for row in rows)
        stages = {"pb": 0.0, "mc": 0.0, "topology": 0.0, "relax_md": 0.0, "effective_md": 0.0}
        for row in rows:
            if row["tool"] in {"pb", "mc", "topology"}:
                stages[row["tool"]] += row["wall_seconds"]
            elif row["tool"] == "gmx" and row["argv"][1:2] == ["mdrun"]:
                for stage in ["relax", "effective"]:
                    if "TMP_" + stage + ".tpr" in row["argv"]:
                        stages[stage + "_md"] += row["wall_seconds"]
        assert all(value > 0 for value in stages.values())
        assert sum(stages.values()) <= elapsed
        stages["other_controller_and_io"] = elapsed - sum(stages.values())
        summary = {"cpu_count": count, "passed": True, "cycles": 2,
                   "controller_wall_seconds": elapsed, "stages_seconds": stages,
                   "first_pb_seconds": next(row["wall_seconds"] for row in rows if row["tool"] == "pb"),
                   "effective_md": [performance((work / f"captures/cycle-{i}/effective.log").read_text()) for i in (1, 2)],
                   "initial_gro_sha256": cycle.digest(work / "captures/cycle-1/before.gro")}
        summaries.append(summary)
        write_json(work / "performance.json", summary)
        write_json(root / "observations.json", summaries)
    assert len({row["initial_gro_sha256"] for row in summaries}) == 1
    write_json(root / "summary.json", {"passed": True, "observations": summaries,
        "limits": "One two-cycle observation/count, with diagnostic retention; screening only. Later structures diverge across counts. First PB starts from identical coordinates."})


def main():
    """Dispatch from the native SLURM harness or from a transparent tool timer."""
    if len(sys.argv) > 1 and sys.argv[1] == "timed":
        raise SystemExit(timed(Path(sys.argv[2]), sys.argv[3], sys.argv[4:]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["md", "coupled"])
    parser.add_argument("source", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tpr", type=Path)
    parser.add_argument("--counts", type=int, nargs="+")
    args = parser.parse_args()
    if args.counts is not None:
        assert args.counts and len(set(args.counts)) == len(args.counts)
        assert all(0 < count <= len(os.sched_getaffinity(0)) for count in args.counts)
    if args.mode == "md":
        assert args.tpr is not None
        md(args.source.resolve(), args.snapshot.resolve(), args.output.resolve(), args.tpr.resolve(), args.counts)
    else:
        coupled(args.source.resolve(), args.snapshot.resolve(), args.output.resolve(), args.counts)


if __name__ == "__main__":
    main()
