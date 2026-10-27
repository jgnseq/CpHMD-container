#!/usr/bin/env python3
"""Summarize PB convergence diagnostics or independent-seed MC uncertainty.

Called after the fixed-coordinate tests. These are empirical diagnostics, not
new acceptance thresholds or proof of experimental pKa accuracy. MC mode uses
the same x86 PETIT engine on both saved energy tables, with disjoint seeds.
"""
import argparse
import json
import math
from pathlib import Path
import re
import statistics


def mc_rows(path: Path) -> tuple:
    """Read PETIT mean/error/name rows; retain only finite valid estimates."""
    means, errors, names = {}, {}, {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] in (".", "t") and len(fields) > 4 and fields[3].isdigit():
            index, value = int(fields[3]), float(fields[4])
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid MC mean/error")
            destination = means if fields[0] == "." else errors
            if index in destination:
                raise ValueError("Repeated MC site")
            destination[index] = value
        elif fields[0] == ">":
            names[int(fields[2])] = fields[1]
    if set(means) != set(range(21)) or set(errors) != set(means) or set(names) != set(means):
        raise ValueError("Incomplete 21-site MC uncertainty output")
    if any(value > 1 for value in means.values()):
        raise ValueError("Illegal mean proton occupancy")
    return means, errors, names


def uncertainty(directory: Path) -> dict:
    """Combine three independent-chain SE estimates for each energy table."""
    reference = [mc_rows(directory / f"x86-{seed}.out") for seed in (1729, 2718, 3141)]
    candidate = [mc_rows(directory / f"arm-{seed}.out") for seed in (91729, 92718, 93141)]
    if any(row[2] != reference[0][2] for row in reference + candidate):
        raise ValueError("MC site names/order differ")
    sites = []
    for index in range(21):
        ref_mean = statistics.mean(row[0][index] for row in reference)
        arm_mean = statistics.mean(row[0][index] for row in candidate)
        ref_se = math.sqrt(sum(row[1][index] ** 2 for row in reference)) / 3
        arm_se = math.sqrt(sum(row[1][index] ** 2 for row in candidate)) / 3
        combined = math.hypot(ref_se, arm_se)
        difference = arm_mean - ref_mean
        standardized = abs(difference) / combined if combined else (0 if difference == 0 else None)
        sites.append({"site": reference[0][2][index], "reference_energy_mean": ref_mean,
                      "ARM_energy_mean": arm_mean, "difference": difference,
                      "estimated_combined_MC_standard_error": combined,
                      "difference_in_estimated_standard_errors": standardized})
    return {"method": "PETIT -t 100, three independent 100000-step chains per energy table; "
                       "combined SE=sqrt(sum(chain_SE^2))/3, then quadrature across tables",
            "MC_engine_for_both_tables": "x86 PETIT 1.6.1 compiled from the frozen common source",
            "limitations": "Conditional on saved PB energies. Three replicates and lag cutoff 100; "
                           "estimated errors do not prove stationarity or equivalence. Zero empirical "
                           "error at saturated sites does not exclude unsampled rare transitions.",
            "max_absolute_mean_difference": max(abs(row["difference"]) for row in sites),
            "max_standardized_difference": max(row["difference_in_estimated_standard_errors"] or 0 for row in sites),
            "sites": sites}


def convergence(directory: Path) -> dict:
    """Compare requested maxc to each solver log's last reported max change."""
    folders = list(directory.glob("delphiT*/tmp"))
    if len(folders) != 1:
        raise ValueError("Expected one retained solver directory")
    pattern = re.compile(r"^\s*([+\d.Ee-]+)\s+([+\d.Ee-]+)\s+at\s+(\d+)\s+iterations", re.M)
    rows = []
    for parameter in sorted(folders[0].glob("*.prm")):
        fields = dict(line.split("=", 1) for line in parameter.read_text().splitlines() if "=" in line)
        stem = parameter.stem
        if stem.startswith("P_") and stem.endswith("f"):
            stem = stem[:-1]
        output = parameter.with_name(stem + ".out")
        iterations = pattern.findall(output.read_text())
        last = float(iterations[-1][1]) if iterations else None
        if last is not None and not math.isfinite(last):
            raise ValueError("Nonfinite convergence diagnostic")
        rows.append({"input": parameter.name, "requested_maxc": float(fields["maxc"]),
                     "linit": int(fields["linit"]), "last_reported_max_change": last,
                     "last_reported_iteration": int(iterations[-1][2]) if iterations else None,
                     "last_report_within_maxc": last <= float(fields["maxc"]) if last is not None else None})
    if not rows:
        raise ValueError("No solver parameters")
    return {"solves": len(rows), "requested_maxc_values": sorted({row["requested_maxc"] for row in rows}),
            "last_report_above_maxc": sum(row["last_report_within_maxc"] is False for row in rows),
            "unreported": sum(row["last_report_within_maxc"] is None for row in rows),
            "interpretation": "Last printed iteration diagnostic; empirical energy sensitivity "
                              "must be measured separately. This is not an energy-error bound.",
            "solvers": rows}


def main() -> None:
    """Write a complete JSON audit and keep the terminal summary compact."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mc-directory", type=Path)
    group.add_argument("--pb-directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = uncertainty(args.mc_directory) if args.mc_directory else convergence(args.pb_directory)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("sites", "solvers")}, indent=2))


if __name__ == "__main__":
    main()
