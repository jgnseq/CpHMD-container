#!/bin/bash
# Build-time gate called by build-inside.sh after the main GROMACS compilation.
# In normal GROMACS builds, test executables are excluded from the default all
# target. Build the five intended suites explicitly before asking CTest to run
# them. This gate tests compiled engine components; image/runtime and scientific
# CpHMD-cycle checks happen later in validate-arm64.sh and separate validation.
set -Eeuo pipefail
build_dir="$(realpath "${1:?Supply the configured GROMACS build directory}")"
jobs="${2:?Supply compiler parallelism}"
evidence_dir="${3:?Supply the build evidence directory}"
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { echo 'Positive build parallelism required' >&2; exit 2; }
mkdir -p "$evidence_dir"

# Names and targets come from the pinned GROMACS 2026.3 module CMakeLists.txt.
# FileIOTests and MdtypesUnitTest have different suffixes from the other suites;
# an approximate .*UnitTests filter silently omitted these two in the first job.
targets=(commandline-test fileio-test hardware-test math-test mdtypes-test)
tests=(CommandLineUnitTests FileIOTests HardwareUnitTests MathUnitTests MdtypesUnitTest)
selection='^(CommandLineUnitTests|FileIOTests|HardwareUnitTests|MathUnitTests|MdtypesUnitTest)$'
cmake --build "$build_dir" --parallel "$jobs" --target "${targets[@]}" \
    2>&1 | tee "$evidence_dir/gromacs-test-build.log"

# Record the selected CTest inventory and require all five registrations. The
# --no-tests=error flag alone would detect zero matches, but not a partial set.
ctest --test-dir "$build_dir" --show-only=json-v1 -R "$selection" \
    > "$evidence_dir/gromacs-selected-tests.json"
python3 - "$evidence_dir/gromacs-selected-tests.json" "${tests[@]}" <<'PY'
"""Require every intended suite before execution; preserve inventory as evidence."""
import json
import sys
with open(sys.argv[1]) as stream:
    found = [test['name'] for test in json.load(stream)['tests']]
expected = sys.argv[2:]
if sorted(found) != sorted(expected):
    raise SystemExit('CTest selection mismatch: expected {}, found {}'.format(expected, found))
print('PASS: all five requested GROMACS suites are registered')
PY

# pipefail keeps a failed CTest result fatal even though its output is logged.
ctest --test-dir "$build_dir" --output-on-failure --no-tests=error \
    -R "$selection" 2>&1 | tee "$evidence_dir/gromacs-ctest.log"
