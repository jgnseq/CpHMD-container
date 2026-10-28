#!/usr/bin/env python3
"""Test the large A64FX process overhead observed by hewl_performance.py.

Compare default/reproducible zero-step starts on one exclusive node, then two
5-ps reproducible observations using the same TPR. GROMACS 2026.3 maps its
reproducible FFT setup to FFTW_ESTIMATE rather than FFTW_MEASURE; this is a
diagnostic option, not an automatic production-policy change. Reuse the same
independent trajectory/energy/geometry checks as the original timing screen.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from hewl_performance import TPR_SHA256, md_health, performance, run_logged, write_json
from hewl_cycle import digest, gro


def main():
    """Save raw clocks/logs and accepted outputs, without editing a runtime file."""
    snapshot, tpr, output = map(Path, sys.argv[1:])
    assert digest(tpr) == TPR_SHA256
    output.mkdir()
    expected, _, _ = gro(snapshot / "HEWL.gro")
    env = dict(os.environ, OMP_NUM_THREADS="8", GMX_MAXBACKUP="-1")
    observations = []
    for label, steps, extra in [("default-zero", 0, []), ("reprod-zero", 0, ["-reprod"]),
                                ("reprod-five-ps-1", 5000, ["-reprod"]),
                                ("reprod-five-ps-2", 5000, ["-reprod"])]:
        folder = output / label
        folder.mkdir()
        command = ["/gromacs/bin/gmx", "mdrun", "-s", str(tpr), "-deffnm", "md",
                   "-nt", "8", "-pin", "on", "-nsteps", str(steps)] + extra
        start = time.perf_counter()
        run_logged(command, folder, "mdrun.stdout", env=env)
        elapsed = time.perf_counter() - start
        text = (folder / "md.log").read_text()
        assert "Finished mdrun" in text
        assert not re.search(r"LINCS WARNING|constraint failure|Fatal error|\bnan\b", text, re.I)
        ids, _, distances = gro(folder / "md.gro")
        assert ids == expected
        row = {"label": label, "steps": steps, "command": command,
               "command_wall_seconds": elapsed, "disulfide_nm": distances,
               "allowed_cpus": sorted(os.sched_getaffinity(0))}
        if steps:
            row.update(performance(text))
            row["health"] = md_health(folder, expected)
        else:
            # Zero-step probes test startup, never claim a simulated trajectory.
            run_logged(["/gromacs/bin/gmx", "check", "-e", "md.edr"], folder, "edr-check.log")
        observations.append(row)
        write_json(output / "observations.json", observations)
    write_json(output / "summary.json", {"passed": True, "observations": observations,
        "source_tar_sha256": "1094b7bbc6a3960223827114626657110b40096cdf9598a727935fc84ebf8aa0",
        "source_path": "src/gromacs/fft/parallel_3dfft.cpp: bReproducible -> FFT5D_NOMEASURE; fft5d.cpp -> FFTW_ESTIMATE",
        "limits": "-reprod affects other optimization choices too. This is a targeted startup experiment, not promotion of a production setting or proof of physical sampling accuracy."})


if __name__ == "__main__":
    main()
