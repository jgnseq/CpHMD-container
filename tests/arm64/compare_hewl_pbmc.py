#!/usr/bin/env python3
"""Compare retained fixed-coordinate PB/MC outputs against the frozen contract.

Arguments are raw output directories from run_hewl_pbmc.sh. Check identity/order,
finite full matrices, pK shifts, interaction energies in kBT, legal final states,
normalized state populations and seeded mean occupancies. This is an architecture
regression screen, not an experimental pKa or statistical-equivalence test.
"""
import argparse
import json
import math
from pathlib import Path


def number(value: str) -> float:
    """Reject NaN/Inf explicitly; they otherwise evade ordinary comparisons."""
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite PB/MC value")
    return result


def electrostatics(root: Path) -> tuple:
    """Read every pseudostate and the complete ordered square .g matrix."""
    rows = [line.split() for line in (root / "PBMC.pkcrg").read_text().splitlines() if line.strip()]
    identities, pk = [], []
    for row in rows:
        if len(row) != 4 or row[1] not in ("A", "C") or row[3] != "1":
            raise ValueError("Unexpected HEWL pseudostate definition")
        identities.append(tuple(row[1:]))
        pk.append(number(row[0]))
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate pseudostates")
    n = len(pk)
    interactions = {}
    for line in (root / "PBMC.g").read_text().splitlines():
        a, b, value = line.split()
        key = (int(a), int(b))
        if key in interactions:
            raise ValueError("Duplicate matrix element")
        interactions[key] = number(value)
    if set(interactions) != {(a, b) for a in range(1, n + 1) for b in range(1, n + 1)}:
        raise ValueError("Incomplete or incorrectly indexed PB interaction matrix")
    for (a, b), value in interactions.items():
        if abs(value - interactions[b, a]) > 1e-10:
            raise ValueError("Asymmetric averaged PB matrix")
        if a == b and value != 0:
            raise ValueError("Nonzero interaction diagonal")
    return identities, pk, interactions


def petit_input(root: Path, expected: int) -> tuple:
    """Read PETIT's site/state blocks and verify every pairwise interaction key."""
    lines = iter(line.split() for line in (root / "PBMC.dat").read_text().splitlines() if line.strip())
    if next(lines) != [str(expected)]:
        raise ValueError("Incorrect PETIT site count")
    sites, energies = [], []
    for _ in range(expected):
        name, count, ligand, mode = next(lines)
        count = int(count)
        states = [next(lines) for _ in range(count)]
        if count < 2 or ligand != "P" or mode != "*":
            raise ValueError("Unexpected titration-state model")
        occupancies = tuple(int(row[0]) for row in states)
        if set(occupancies) != {0, 1}:
            raise ValueError("Illegal proton occupation")
        sites.append((name, count, ligand, mode, occupancies))
        energies.extend(number(row[1]) for row in states)
    pairs = {}
    for row in lines:
        if len(row) != 5:
            raise ValueError("Malformed PETIT interaction")
        key = tuple(map(int, row[:4]))
        if key in pairs:
            raise ValueError("Duplicate PETIT interaction")
        pairs[key] = number(row[4])
    # PETIT uses zero-based site and state indices. It ignores the printed
    # indices internally, so checking these here catches misordered converters.
    expected_keys = [(i, si, j, sj) for i in range(expected) for j in range(i + 1, expected)
                     for si in range(sites[i][1]) for sj in range(sites[j][1])]
    if list(pairs) != expected_keys:
        raise ValueError("Incomplete/misordered PETIT state interactions")
    return sites, energies, pairs


def populations(path: Path, sites: list) -> tuple:
    """Validate every sampled site and final microstate, then return means."""
    means, names, final = {}, {}, []
    for line in path.read_text().splitlines():
        row = line.split()
        if not row:
            continue
        if row[0] == "." and row[3].isdigit():
            index = int(row[3])
            if index >= len(sites) or index in means or list(map(number, row[1:3])) != [0.0, 6.0]:
                raise ValueError("Wrong/repeated PETIT site or pH")
            values = list(map(number, row[4:]))
            if len(values) != 1 + sites[index][1]:
                raise ValueError("Wrong number of PETIT state populations")
            if any(v < 0 or v > 1 for v in values) or abs(sum(values[1:]) - 1) > 2e-6:
                raise ValueError("Unnormalized or illegal populations")
            calculated = sum(occ * prob for occ, prob in zip(sites[index][4], values[1:]))
            if abs(calculated - values[0]) > 2e-6:
                raise ValueError("Mean occupancy disagrees with state populations")
            means[index] = values[0]
        elif row[0] == ">":
            index = int(row[2])
            if index in names:
                raise ValueError("Repeated site name")
            names[index] = row[1]
        elif row[0] == "f":
            if final:
                raise ValueError("Repeated final state vector")
            final = list(map(int, row[1:]))
    if set(means) != set(range(len(sites))) or names != {i: s[0] for i, s in enumerate(sites)}:
        raise ValueError("Missing site populations or different site order/names")
    if len(final) != len(sites) or any(state < 0 or state >= sites[i][1] for i, state in enumerate(final)):
        raise ValueError("Incomplete or illegal final state vector")
    return means, final


def compare(reference: Path, candidate: Path, contract: dict) -> dict:
    """Evaluate predetermined tolerances; retain failed metrics in the report."""
    ident_r, pk_r, g_r = electrostatics(reference)
    ident_c, pk_c, g_c = electrostatics(candidate)
    if ident_r != ident_c:
        raise ValueError("Pseudostate identities/order differ")
    sites_r, e_r, pairs_r = petit_input(reference, contract["sites"])
    sites_c, e_c, pairs_c = petit_input(candidate, contract["sites"])
    if sites_r != sites_c:
        raise ValueError("PETIT site/state definitions differ")
    kbt = 5.98435e-6 * contract["temperature_K"]
    tolerance = contract["tolerances_frozen_before_execution"]
    pk_delta = max(abs(a - b) for a, b in zip(pk_r, pk_c))
    failures, matrix_delta = [], 0.0
    for key in g_r:
        delta = abs(g_r[key] - g_c[key]) / kbt
        matrix_delta = max(matrix_delta, delta)
        allowed = tolerance["interaction_energy_absolute_kBT"] + tolerance["interaction_energy_relative"] * abs(g_r[key]) / kbt
        if delta > allowed:
            failures.append(f"PB interaction {key}: {delta} kBT > {allowed}")
    state_delta = max(abs(a - b) / kbt for a, b in zip(e_r, e_c))
    if state_delta > math.log(10) * tolerance["intrinsic_pK_absolute"]:
        failures.append("Converted individual-state energy exceeds pK-derived tolerance")
    pair_delta = max(abs(pairs_r[key] - pairs_c[key]) / kbt for key in pairs_r)
    if any(abs(pairs_r[key] - pairs_c[key]) / kbt > tolerance["interaction_energy_absolute_kBT"]
           + tolerance["interaction_energy_relative"] * abs(pairs_r[key]) / kbt for key in pairs_r):
        failures.append("Converted PETIT pair energy exceeds tolerance")
    if pk_delta > tolerance["intrinsic_pK_absolute"]:
        failures.append("Intrinsic pK difference exceeds tolerance")
    mc = {}
    for seed in contract["seeds"]:
        r, final_r = populations(reference / f"petit-{seed}.out", sites_r)
        c, final_c = populations(candidate / f"petit-{seed}.out", sites_c)
        delta = max(abs(r[i] - c[i]) for i in r)
        mc[seed] = {"max_site_mean_occupancy_difference": delta, "final_microstates_equal": final_r == final_c}
        if delta > tolerance["site_mean_occupancy_absolute"]:
            failures.append(f"Seed {seed}: mean occupancy difference exceeds tolerance")
    return {"passed": not failures, "pseudostates": len(pk_r), "sites": len(sites_r),
            "matrix_elements": len(g_r), "max_intrinsic_pK_difference": pk_delta,
            "max_raw_interaction_difference_kBT": matrix_delta,
            "max_converted_state_energy_difference_kBT": state_delta,
            "max_converted_pair_energy_difference_kBT": pair_delta,
            "MC": mc, "failures": failures, "contract": contract}


def main() -> None:
    """Write a machine-readable audit and fail the process if any gate fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--contract", type=Path, default=Path(__file__).with_name("hewl-pbmc-contract.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(args.reference, args.candidate, json.loads(args.contract.read_text()))
    except (ValueError, IndexError, KeyError, StopIteration, OSError) as exc:
        result = {"passed": False, "failures": [str(exc)]}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    # Keep complete failed-element diagnostics in the artifact without flooding
    # scheduler/terminal logs with thousands of matrix rows.
    summary = {key: value for key, value in result.items() if key not in ("contract", "failures")}
    summary["failure_count"] = len(result["failures"])
    summary["first_failures"] = result["failures"][:5]
    summary["full_report"] = str(args.output)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
