#!/bin/bash
# Regression for ARM job 2147644: CTest registration is not compilation.
# A tiny real CMake project excludes test binaries from all, just like normal
# GROMACS. Prove our gate builds/runs five suites and propagates a failing test
# and a missing registration. No GROMACS download, container or HPC is needed.
set -Eeuo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v cmake >/dev/null || { echo 'CMake/CTest are required for this regression' >&2; exit 2; }
command -v ctest >/dev/null
work="$(mktemp -d "${TMPDIR:-/tmp}/cphmd-gmx-gate.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
mkdir "$work/source"
cat > "$work/source/probe.c" <<'C'
/* A command-line argument deliberately simulates a failing unit test. */
int main(int argc, char **argv) { (void)argv; return argc > 1 ? 7 : 0; }
C
cat > "$work/source/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.16)
project(CpHMDTestGateRegression C)
enable_testing()
option(SIMULATE_FAILURE "Make MathUnitTests fail" OFF)
option(OMIT_REGISTRATION "Omit one CTest suite but retain its build target" OFF)
set(targets commandline-test fileio-test hardware-test math-test mdtypes-test)
set(suites CommandLineUnitTests FileIOTests HardwareUnitTests MathUnitTests MdtypesUnitTest)
foreach(index RANGE 0 4)
    list(GET targets ${index} binary)
    list(GET suites ${index} suite)
    add_executable(${binary} EXCLUDE_FROM_ALL probe.c)
    if(OMIT_REGISTRATION AND suite STREQUAL "FileIOTests")
        continue()
    elseif(SIMULATE_FAILURE AND suite STREQUAL "MathUnitTests")
        add_test(NAME ${suite} COMMAND ${binary} --simulate-failure)
    else()
        add_test(NAME ${suite} COMMAND ${binary})
    endif()
endforeach()
CMAKE
cmake -S "$work/source" -B "$work/build" > "$work/configure.log" 2>&1
cmake --build "$work/build" > "$work/default-build.log" 2>&1
# Confirm the fixture really reproduces the missing-executable condition.
test ! -e "$work/build/math-test"
bash "$repo/container_build/arm64/check-gromacs-build.sh" \
    "$work/build" 2 "$work/pass-evidence"
for binary in commandline-test fileio-test hardware-test math-test mdtypes-test; do
    test -x "$work/build/$binary"
done
cmake -S "$work/source" -B "$work/build" -DSIMULATE_FAILURE=ON \
    > "$work/configure-failure.log" 2>&1
if bash "$repo/container_build/arm64/check-gromacs-build.sh" \
    "$work/build" 2 "$work/fail-evidence" > "$work/fail.log" 2>&1; then
    echo 'FAIL: failing unit test was accepted' >&2; exit 1
fi
grep -q 'MathUnitTests.*Failed' "$work/fail-evidence/gromacs-ctest.log"
cmake -S "$work/source" -B "$work/build" -DSIMULATE_FAILURE=OFF -DOMIT_REGISTRATION=ON \
    > "$work/configure-missing.log" 2>&1
if bash "$repo/container_build/arm64/check-gromacs-build.sh" \
    "$work/build" 2 "$work/missing-evidence" > "$work/missing.log" 2>&1; then
    echo 'FAIL: incomplete suite selection was accepted' >&2; exit 1
fi
grep -q 'CTest selection mismatch' "$work/missing.log"
echo 'PASS: excluded test binaries built; failed tests and missing registrations rejected'
