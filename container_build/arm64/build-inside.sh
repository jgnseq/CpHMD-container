#!/bin/bash
# Singularity %post entry point; runs inside the disposable ARM rootfs.
# Rebuild native PB/MC helpers, PETIT, PLUMED and GROMACS from the frozen
# context. Retain the audited DelPhi solver/runtime, then install the runtime
# controller and embedded smoke tests. No CpHMD trajectory is generated here.
set -Eeuo pipefail
[[ $(uname -m) == aarch64 ]] || { echo 'Native ARM build required'; exit 2; }
src=/opt/cphmd-build
# EXIT handler: export configure/compiler/unit-test evidence through the host
# bind mount before the rootfs disappears; do not mask the original failure.
preserve_build_evidence () {
    status=$?
    set +e
    cp -a /usr/share/cphmd/build/. /build-evidence/ 2>/dev/null
    cp /build/gmx/CMakeCache.txt /build-evidence/ 2>/dev/null
    cp /build/gmx/CMakeFiles/CMakeConfigureLog.yaml /build-evidence/ 2>/dev/null
    cp /build/gmx/Testing/Temporary/LastTest.log /build-evidence/ 2>/dev/null
    cp "$src/plumed/config.log" /build-evidence/plumed-config.log 2>/dev/null
    printf '%s\n' "$status" > /build-evidence/post-exit-code.txt
    exit "$status"
}
trap preserve_build_evidence EXIT
readarray -t config < <(python3 - <<'PY'
"""Read only recorded candidate choices; do not infer SIMD from the login host."""
import json
m=json.load(open('/etc/cphmd/build.json'))
print(m['jobs']);print(m['simd']);print(m['sve_bits']);print(m.get('isa_profile','a64fx-reference'))
PY
)
jobs="${config[0]}"
simd="${config[1]}"
sve_bits="${config[2]}"
profile="${config[3]}"
cpu_flags=()
if [[ $profile == portable-armv8-a ]]; then
    [[ $simd == ARM_NEON_ASIMD && $sve_bits == 0 ]] || exit 2
    # Explicit instruction floor, independent of the machine doing compilation.
    cpu_flags=(-march=armv8-a -mtune=generic)
fi
export MAKEFLAGS="-j${jobs}"
export OMP_NUM_THREADS=1
export LD_LIBRARY_PATH="/opt/nvhpc/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# The portable bootstrap's provenance/libraries must be staged before clearing
# inherited payloads/evidence. Explicit legacy derivations supply their own
# staged solver and are still checked by the same installer below.
if [[ $profile == portable-armv8-a ]]; then
    python3 "$src/container_build/arm64/stage-bootstrap-delphi.py"
elif [[ -f /usr/share/cphmd/build/delphi-a64fx-repair.json ]]; then
    cp /usr/share/cphmd/build/delphi-a64fx-repair.json "$src/delphi-bootstrap-provenance.json"
fi
# Fresh compiler/test evidence prevents inherited passes being mistaken for
# this candidate's results. Original evidence remains in the immutable base.
rm -rf /usr/share/cphmd/build /usr/share/cphmd/tests
mkdir -p /etc/cphmd /usr/share/cphmd/build /usr/local/libexec/cphmd
if [[ -f $src/delphi-bootstrap-provenance.json ]]; then
    cp "$src/delphi-bootstrap-provenance.json" /usr/share/cphmd/build/
fi
test -x /Delphi/delphi_pgf90
# Preserve the solver before replacing its directory. Fixed-coordinate PB/MC
# comparison is a separate acceptance gate for this inherited native binary.
cp /Delphi/delphi_pgf90 "$src/delphi.base"
sha256sum "$src/delphi.base" > /usr/share/cphmd/build/delphi.sha256
dpkg-query -W > /usr/share/cphmd/build/base-packages.tsv
gcc --version > /usr/share/cphmd/build/gcc.txt
g++ --version > /usr/share/cphmd/build/gxx.txt
cmake --version > /usr/share/cphmd/build/cmake.txt

# Replace only container-owned payloads in this disposable rootfs. The host
# repository, bootstrap SIF and production directories are never writable here.
rm -rf /CpHMD /Delphi /FFs /STs /Databases /analysis /Templates /Tutorials /gromacs
cp -a "$src/CpHMD" /CpHMD
cp -a "$src/DelphiTools" /Delphi
cp -a "$src/FFs" /FFs
cp -a "$src/STs" /STs
cp -a "$src/Databases" /Databases
cp -a "$src/analysis" /analysis
cp -a "$src/template" /Templates
cp -a "$src/tutorials" /Tutorials
cp "$src/delphi.base" /Delphi/delphi_pgf90
chmod 755 /Delphi/delphi_pgf90
if [[ $profile == portable-armv8-a ]]; then
    # Rebuild entire owned native trees, so obsolete optimized variants cannot
    # survive beside the new generic executables under another filename.
    rm -rf /opt/nvhpc/lib /opt/plumed /programs/petit1.6.1
    cp /usr/share/cphmd/build/delphi.sha256 /usr/share/cphmd/build/delphi-parent.sha256
    python3 "$src/container_build/arm64/install-portable-delphi.py"
fi
# These helpers run before PB/MC: fixgro assembles solutes across PBC, while
# geom_center/calc_pkg_low support DelPhi geometry and parameter preparation.
gcc -std=c99 -O2 "${cpu_flags[@]}" /CpHMD/src/fixgro.c -lm -o /CpHMD/scripts/fixgro
# The force-field tree historically contains a second copy of this helper.
install -m755 /CpHMD/scripts/fixgro /FFs/Amber14SBpH.ff/scripts/fixgro
gcc -O2 "${cpu_flags[@]}" /Delphi/src/geom_center.c /Delphi/src/my_mem.c -lm -o /Delphi/geom_center
gcc -O2 "${cpu_flags[@]}" /Delphi/src/calc_pkg_low.c /Delphi/src/my_mem.c -lm -o /Delphi/calc_pkg_low
# PETIT samples protonation states after DelPhi supplies the PB energies.
# Avoid fast-math so this port does not silently change numerical semantics.
rm -rf /programs/petit1.6.1
mkdir -p /programs/petit1.6.1
cp "$src/petit1.6.1/"{petit.c,README,LICENSE,sample.dat} /programs/petit1.6.1/
gcc -O2 "${cpu_flags[@]}" /programs/petit1.6.1/petit.c -lm -o /programs/petit1.6.1/petit
ln -s petit /programs/petit1.6.1/petit-gcc

cd "$src/plumed"
# Host ELF/object/library products are excluded by context preparation.
make distclean >/dev/null 2>&1 || true
./configure --prefix=/opt/plumed --enable-shared --disable-mpi --disable-asmjit \
    CXXFLAGS="-O2 -fPIC ${cpu_flags[*]}" CFLAGS="-O2 -fPIC ${cpu_flags[*]}" \
    FCFLAGS="-O2 ${cpu_flags[*]}" FFLAGS="-O2 ${cpu_flags[*]}"
make -j"$jobs"
make install
cp config.log /usr/share/cphmd/build/plumed-config.log
sha256sum "$src/gromacs-2026.3.tar.gz" | tee /usr/share/cphmd/build/gromacs-source.sha256
echo '1094b7bbc6a3960223827114626657110b40096cdf9598a727935fc84ebf8aa0  /opt/cphmd-build/gromacs-2026.3.tar.gz' | sha256sum -c -
mkdir -p /build
tar -xzf "$src/gromacs-2026.3.tar.gz" -C /build
# GROMACS advances the MD portion of each CpHMD cycle. Match the x86 reference
# release, use the native FFTW library, and keep tests enabled in the build.
simd_args=( "-DGMX_SIMD=$simd" )
if [[ $profile == portable-armv8-a ]]; then
    simd_args+=("-DCMAKE_C_FLAGS=${cpu_flags[*]}" "-DCMAKE_CXX_FLAGS=${cpu_flags[*]}")
fi
if [[ $simd == ARM_SVE ]]; then
    simd_args+=( "-DGMX_SIMD_ARM_SVE_LENGTH=$sve_bits" )
fi
cmake -S /build/gromacs-2026.3 -B /build/gmx \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/gromacs/gromacs-2026.3 \
    -DGMX_GPU=OFF -DGMX_MPI=OFF -DGMX_THREAD_MPI=ON -DGMX_OPENMP=ON \
    -DGMX_DOUBLE=OFF -DGMX_FFT_LIBRARY=fftw3 -DGMX_BUILD_OWN_FFTW=OFF \
    -DGMX_USE_PLUMED=ON -DCMAKE_PREFIX_PATH=/opt/plumed \
    -DBUILD_TESTING=ON -DGMX_BUILD_UNITTESTS=ON -DREGRESSIONTEST_DOWNLOAD=OFF \
    "${simd_args[@]}"
cmake --build /build/gmx --parallel "$jobs"
# Enabling tests in CMake registers them but does not build their executables
# in a normal release build. Compile the selected suites, verify their exact
# registration names and run them before installation/image acceptance.
bash "$src/container_build/arm64/check-gromacs-build.sh" \
    /build/gmx "$jobs" /usr/share/cphmd/build
cmake --install /build/gmx
cp /build/gmx/CMakeCache.txt /usr/share/cphmd/build/CMakeCache.txt
cp /build/gmx/Testing/Temporary/LastTest.log /usr/share/cphmd/build/LastTest.log
mkdir -p /gromacs/bin
cat > /gromacs/bin/gmx <<'EOF'
#!/bin/bash
# Runtime launcher shared by the controller and smoke tests: select only this
# installed CPU build and expose its GROMACS/PLUMED shared libraries.
set -e
root=/gromacs/gromacs-2026.3
export LD_LIBRARY_PATH="$root/lib:$root/lib64:/opt/plumed/lib:/opt/plumed/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$root/bin/gmx" "$@"
EOF
chmod 755 /gromacs/bin/gmx
ln -sf /gromacs/bin/gmx /usr/local/bin/gmx
ln -sf /CpHMD/scripts/CpHMD.sh /usr/local/bin/CpHMD.sh
cp "$src/container_build/arm64/validate-arm64.sh" /usr/local/libexec/cphmd/
cp -a "$src/tests/arm64" /usr/share/cphmd/tests
ldconfig
export PATH="/gromacs/bin:/opt/plumed/bin:$PATH"
export PLUMED_KERNEL=/opt/plumed/lib/libplumedKernel.so
export LD_LIBRARY_PATH="/opt/nvhpc/lib:/opt/plumed/lib:/opt/plumed/lib64"
/gromacs/bin/gmx --version > /usr/share/cphmd/build/gromacs-version.txt
# Imported project modes/ACLs must not make the resulting SIF root-only.
# Ordinary-user smoke tests run separately after fakeroot image assembly.
python3 "$src/container_build/arm64/normalize-runtime-permissions.py"
cd /
# This cleanup is confined to the disposable image. Installed evidence remains
# under /usr/share/cphmd/build for the EXIT handler to export to the host.
# The installed image needs neither compiler trees nor source inputs.
rm -rf /build /opt/cphmd-build
