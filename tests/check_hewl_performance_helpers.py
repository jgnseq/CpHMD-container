#!/usr/bin/env python3
"""Check timing interpretation against real native logs and damaged records.

The old two-column-only performance parser misses GROMACS 2026's four fields.
These tests ensure the new stage reads wall time, rejects ambiguous/incomplete
records and cannot rank non-finite or failed dynamics as a fast observation.
"""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "arm64"))
from hewl_performance import performance
from hewl_solver_performance import solver_record
from compare_hewl_performance import compare, workflow

LOG = """Using 1 MPI thread
Using 8 OpenMP threads
Time: 91.704 11.464 800.0
Performance: 7.544 3.181 11.452 2.444
Finished mdrun on rank 0
"""


class TimingAcceptance(unittest.TestCase):
    """Validate interpretation and fail closed for damaged timing provenance."""
    def test_current_format(self):
        """CPU time and wall time must remain distinct in the 2026 format."""
        row = performance(LOG)
        self.assertEqual(row["gmx_wall_seconds"], 11.464)
        self.assertEqual(row["gmx_core_seconds"], 91.704)
        self.assertEqual(row["omp_threads"], 8)

    def test_legacy_format(self):
        """An earlier two-field rate row remains explicitly supported."""
        self.assertEqual(performance(LOG.replace(" 11.452 2.444", ""))["ns_per_day"], 7.544)

    def test_reject_damage(self):
        """Incomplete, ambiguous, nonfinite and failed logs cannot pass."""
        damaged = [LOG.replace("Finished mdrun", "Stopped"), LOG + LOG,
                   LOG.replace("11.464", "nan"), LOG.replace("11.464", "0"),
                   LOG + "LINCS WARNING\n", LOG.replace("Using 8 OpenMP threads", ""),
                   LOG.replace(" 11.452 2.444", " 11.452")]
        for text in damaged:
            with self.subTest(text=text), self.assertRaises(AssertionError):
                performance(text)


class LegacySolverAcceptance(unittest.TestCase):
    """Catch DelPhi STOP-with-zero and retain iteration-cap limitations."""
    def test_numerical_work_and_residual(self):
        """A capped solve is measurable but must not be called converged."""
        text = """1.6834836E-06 3.0517578E-04 at 500 iterations
All required energy terms but grid and self_react.: -222.3568 kt
energy calculations done at 0.2200000
"""
        row = solver_record(text)
        self.assertEqual(row["last_reported_iterations"], 500)
        self.assertFalse(row["requested_tolerance_met_at_last_report"])
        with self.assertRaises(AssertionError):
            solver_record(text.replace("-222.3568", "NaN"))

    def test_zero_exit_is_not_acceptance(self):
        """Missing fort.10 can produce exit 0 without any scientific work."""
        with self.assertRaises(AssertionError):
            solver_record("FORTRAN STOP\nparameter file fort.10 does not seem to exist\n")


class CrossArchitectureIdentity(unittest.TestCase):
    """Reject faster observations when their scientific inputs have changed."""
    evidence = Path(__file__).resolve().parent.parent / "docs/aarch64/evidence/2026-10-28/hewl-performance"

    def test_accepted_native_evidence(self):
        """The saved accepted runs provide a real positive comparison control."""
        self.assertTrue(compare(self.evidence / "x86/micro-rc3", self.evidence / "arm/micro-shell")
                        ["input_identity_and_independent_component_audits_passed"])
        self.assertEqual(workflow(self.evidence / "x86", self.evidence / "arm")
                         ["identical_scientific_text_files"], 147)

    def test_reject_mismatched_solver_protocol(self):
        """A changed solver input protocol cannot inherit a speed ratio pass."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("summary.json", "observations.json", "architecture.txt"):
                shutil.copyfile(self.evidence / "arm/micro-shell" / name, root / name)
            path = root / "summary.json"
            data = json.loads(path.read_text())
            data["input_protocol_sha256"] = "changed-input"
            path.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):
                compare(self.evidence / "x86/micro-rc3", root)
            data = json.loads((self.evidence / "arm/micro-shell/summary.json").read_text())
            data["components"].pop()
            path.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):
                compare(self.evidence / "x86/micro-rc3", root)

    def test_reject_changed_controller_source(self):
        """The workflow comparison rejects a controller/source mismatch first."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source-paired").mkdir()
            path = root / "source-paired/source-snapshot.json"
            data = json.loads((self.evidence / "x86/source-paired/source-snapshot.json").read_text())
            data["file_sha256"]["CpHMD/scripts/CpHMD.sh"] = "changed-controller"
            path.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):
                workflow(root, self.evidence / "arm")


if __name__ == "__main__":
    unittest.main()
