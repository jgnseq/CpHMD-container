#!/usr/bin/env python3
"""Install the screened A64FX solver in a disposable derived container rootfs.

Called only by repair-delphi-a64fx.slurm %post as root. Record original payload
hashes, install the native solver/dependencies with public read/execute modes,
prove all other runtime bytes unchanged, and append build provenance. This does
not alter host source, force fields, scientific drivers or existing SIFs.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil


def payload() -> dict:
    """Hash existing ordinary runtime files; skip links just as the build audit does."""
    roots = ("/CpHMD", "/Delphi", "/FFs", "/STs", "/Databases", "/analysis",
             "/gromacs", "/opt/plumed", "/opt/nvhpc", "/programs/petit1.6.1")
    result = {}
    for root in roots:
        for path in Path(root).rglob("*"):
            if path.is_file() and not path.is_symlink():
                result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> None:
    """Replace only the accepted binary/runtime and record byte-preservation evidence."""
    if os.getuid() != 0 or platform.machine() != "aarch64":
        raise SystemExit("Container-root installation on native ARM required")
    before = payload()
    staged = Path("/opt/cphmd-new-delphi")
    installed = {}
    for source in staged.iterdir():
        target = (Path("/Delphi/delphi_pgf90") if source.name == "delphi_pgf90"
                  else Path("/opt/nvhpc/lib") / source.name)
        shutil.copyfile(source, target)
        target.chmod(0o755)
        installed[str(target)] = hashlib.sha256(target.read_bytes()).hexdigest()
    after = payload()
    unchanged = [name for name in before if name not in installed]
    if any(before[name] != after.get(name) for name in unchanged):
        raise SystemExit("Unrelated runtime payload changed during solver installation")
    provenance = json.loads(Path("/opt/cphmd-solver-provenance.json").read_text())
    report = {"unchanged_runtime_files": len(unchanged), "installed_sha256": installed,
              "solver_provenance": provenance}
    destination = Path("/usr/share/cphmd/build/delphi-a64fx-repair.json")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    metadata = Path("/etc/cphmd/build.json")
    data = json.loads(metadata.read_text())
    data["delphi_a64fx_repair"] = report
    metadata.write_text(json.dumps(data, indent=2) + "\n")
    # Remove only our disposable staging files inside the newly assembled image.
    shutil.rmtree(staged)
    Path("/opt/cphmd-solver-provenance.json").unlink()
    Path("/opt/cphmd-install-solver.py").unlink()


if __name__ == "__main__":
    main()
