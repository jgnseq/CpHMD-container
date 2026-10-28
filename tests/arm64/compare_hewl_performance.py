#!/usr/bin/env python3
"""Compare accepted fixed-input DelPhi/PETIT performance observations.

Run locally on the two completed micro-shell directories after backup. Inputs,
repeat counts, actual iteration/residual/energy records and matched-seed MC
outputs accompany each timing ratio. This compares delivered implementations
on named machines; it cannot isolate the instruction set or compiler alone.
No new physical accuracy threshold is invented from the observed timings.
"""
import argparse
import json
from pathlib import Path
import statistics


def compare(x86, arm):
    """Require matching accepted protocols, then expose timing and work deltas."""
    left, right = [json.loads((root / "summary.json").read_text()) for root in (x86, arm)]
    assert left["passed"] and right["passed"]
    assert left["input_protocol_sha256"] == right["input_protocol_sha256"]
    raw_x, raw_a = [json.loads((root / "observations.json").read_text()) for root in (x86, arm)]
    assert len(raw_x) == len(raw_a) == 21
    assert len(left["components"]) == len(right["components"]) == 7
    keys = {(row["component"], row["input"]) for row in left["components"]}
    assert len(keys) == 7
    for raw in (raw_x, raw_a):
        assert {(row["component"], row["repeat"], row["input"]) for row in raw} == {
            (component, repeat, name) for component, name in keys for repeat in (1, 2, 3)}
    assert (x86 / "architecture.txt").read_text().strip() == "x86_64"
    assert (arm / "architecture.txt").read_text().strip() == "aarch64"
    records = []
    for x, a in zip(left["components"], right["components"]):
        assert (x["component"], x["input"]) == (a["component"], a["input"])
        row = {"component": x["component"], "input": x["input"],
               "x86_median_seconds": x["median_wall_seconds"],
               "arm_median_seconds": a["median_wall_seconds"],
               "arm_over_x86_seconds": a["median_wall_seconds"] / x["median_wall_seconds"],
               "x86_range_seconds": [x["min_wall_seconds"], x["max_wall_seconds"]],
               "arm_range_seconds": [a["min_wall_seconds"], a["max_wall_seconds"]]}
        first_x, first_a = [next(item for item in raw if item["component"] == row["component"]
                                and item["input"] == row["input"]) for raw in (raw_x, raw_a)]
        if row["component"] == "delphi":
            row.update(energy_difference_kT=abs(first_a["energy_kT"] - first_x["energy_kT"]),
                       x86_iterations=first_x["last_reported_iterations"],
                       arm_iterations=first_a["last_reported_iterations"],
                       x86_last_max_residual=first_x["last_reported_maximum"],
                       arm_last_max_residual=first_a["last_reported_maximum"],
                       both_requested_tolerances_met=first_x["requested_tolerance_met_at_last_report"]
                                                    and first_a["requested_tolerance_met_at_last_report"])
        else:
            assert set(first_x["means"]) == set(first_a["means"])
            row.update(max_site_mean_occupancy_difference=max(abs(first_x["means"][key] - first_a["means"][key])
                                                             for key in first_x["means"]),
                       final_states_equal=first_x["final_states"] == first_a["final_states"])
        records.append(row)
    return {"input_identity_and_independent_component_audits_passed": True,
            "input_protocol_sha256": left["input_protocol_sha256"], "comparisons": records,
            "ratio_definition": "ARM wall seconds / x86 wall seconds; above 1 means ARM took longer on these named systems.",
            "limits": "Three serial repeats of six representative PB decks plus one fixed PETIT table. No compiler-only/ISA-only attribution, no full PB convergence claim, and no end-to-end throughput claim."}


def workflow(x86, arm):
    """Compare full text evidence roots, retaining equal-input/allocation limits."""
    provenance_x = json.loads((x86 / "source-paired/source-snapshot.json").read_text())["file_sha256"]
    provenance_a = json.loads((arm / "source/source-snapshot.json").read_text())["file_sha256"]
    scientific = [name for name in provenance_a if name.startswith(("CpHMD/", "DelphiTools/", "STs/", "Databases/"))]
    assert scientific and all(provenance_a[name] == provenance_x[name] for name in scientific)
    md_x, md_a = [json.loads((root / "md/observations.json").read_text()) for root in (x86, arm)]
    protocols = [json.loads((root / "md/protocol.json").read_text()) for root in (x86, arm)]
    assert protocols[0]["tpr_sha256"] == protocols[1]["tpr_sha256"]
    assert all(row["health"]["passed"] for row in md_x + md_a)
    scaling = []
    for architecture, observations in [("x86", md_x), ("arm", md_a)]:
        for count in sorted({row["cpu_count"] for row in observations}):
            group = [row for row in observations if row["cpu_count"] == count]
            assert len(group) == 2
            scaling.append({"architecture": architecture, "cpu_count": count,
                "median_command_seconds": statistics.median(row["command_wall_seconds"] for row in group),
                "median_gmx_seconds": statistics.median(row["gmx_wall_seconds"] for row in group),
                "median_outside_gmx_timing_seconds": statistics.median(row["command_wall_seconds"]-row["gmx_wall_seconds"] for row in group),
                "median_gmx_ns_per_day": statistics.median(row["ns_per_day"] for row in group)})
    cx, ca = [json.loads((root / "coupled/summary.json").read_text())["observations"] for root in (x86, arm)]
    assert all(row["passed"] and row["cycles"] == 2 for row in cx + ca)
    assert len({row["initial_gro_sha256"] for row in cx + ca}) == 1
    x, a = [next(row for row in group if row["cpu_count"] == 4) for group in (cx, ca)]
    stage_comparison = [{"stage": name, "x86_seconds": x["stages_seconds"][name], "arm_seconds": value,
                         "arm_over_x86_seconds": value / x["stages_seconds"][name]}
                        for name, value in a["stages_seconds"].items()]
    m_x, m_a = [next(row for row in scaling if row["architecture"] == arch and row["cpu_count"] == 4)
                for arch in ("x86", "arm")]
    return {"input_identity_and_scientific_audits_passed": True,
            "identical_scientific_text_files": len(scientific), "fixed_md_tpr_sha256": protocols[0]["tpr_sha256"],
            "md_scaling": scaling, "four_cpu_md_command_arm_over_x86": m_a["median_command_seconds"] / m_x["median_command_seconds"],
            "four_cpu_md_gmx_time_arm_over_x86": m_a["median_gmx_seconds"] / m_x["median_gmx_seconds"],
            "four_cpu_coupled_controller_arm_over_x86": a["controller_wall_seconds"] / x["controller_wall_seconds"],
            "four_cpu_coupled_stages": stage_comparison, "coupled_observations": {"x86": cx, "arm": ca},
            "metadata_erratum": "Original x86 md/summary.json inherited an ARM-only 48-CPU reservation note. Mini05 actually used physical CPUs 0-5, with four/six OpenMP threads; no Slurm reservation. Raw file is preserved. Current helper uses a generic accounting note.",
            "limits": "5-ps MD screen with two repeats/count; single two-cycle all-site workflow/count with retained diagnostics. Coupled trajectories diverge; only initial structure and direct MD TPR are matched. Whole-stage timings include startup, capture and I/O. Different CPUs, storage, compilers and libraries prevent ISA-only attribution. x86 rc3 is provisional, not a finalized release."}


def main():
    """Write a compact result for review; retain the original raw observations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("x86", type=Path)
    parser.add_argument("arm", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workflow", action="store_true")
    args = parser.parse_args()
    result = workflow(args.x86, args.arm) if args.workflow else compare(args.x86, args.arm)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
