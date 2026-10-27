#!/bin/bash
#SBATCH --job-name=cphmd-delphi-image
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=00:20:00
# Package an execution-validated A64FX solver into a derived validation SIF. Only the
# solver/runtime and provenance change. Verify all other runtime file bytes,
# then repeat ordinary-user smoke and full fixed-coordinate PB/MC in the image
# without any executable/library override. Preserve the separate numerical
# screen honestly; small differences require convergence/sampling assessment,
# not deletion of a usable experimental artifact. Persistent results stay project-
# backed; rootfs assembly uses the previously authorized node-local exception.
set -Eeuo pipefail
root="$(realpath "${1:?Supply a new project solver-image directory}")"
solver="$(realpath "${2:?Supply the accepted native solver build directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solver-image.*) ;; *) exit 2 ;; esac
case "$solver" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/delphi-v5-*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || exit 2
python3 - "$root/prototype-comparison.json" <<'PY'
"""Require complete valid PB/MC execution before packaging an experimental image.

The engineering energy screen is reported separately from functional acceptance.
A comparator parsing/shape failure has no complete counts and must still stop.
"""
import json,sys
report=json.load(open(sys.argv[1]))
assert report['sites']==21 and report['pseudostates']==69 and report['matrix_elements']==4761
assert len(report['MC'])==3
assert all(value['max_site_mean_occupancy_difference'] <= 0.02 for value in report['MC'].values())
PY
sha256sum -c "$solver/runtime.sha256"
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/runtime-permissions/repair.G02c6n/CpHMD-arm64-readable.sif
echo "d153f31722e76f167080485942074633ce9e3d7abc51dfa97827f790947880ba  $image" | sha256sum -c -
scratch="$(mktemp -d "/tmp/${USER}-cphmd-delphi-${SLURM_JOB_ID}.XXXXXX")"
mkdir "$scratch/rootfs" "$scratch/evidence" "$root/tmp"
export SINGULARITY_TMPDIR="$scratch/rootfs"
export SINGULARITY_CACHEDIR=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/cache/singularity
exec > >(tee "$root/repair-${SLURM_JOB_ID}.log") 2>&1
preserve_status () {
    status=$?
    set +e
    cp -a "$scratch/evidence/." "$root/"
    cp "$scratch/repair.def" "$root/executed-repair.def"
    if (( status != 0 )) && [[ -f "$scratch/candidate.sif" ]]; then
        cp "$scratch/candidate.sif" "$root/CpHMD-arm64-a64fx-pbmc.failed.sif"
    fi
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
cp "${BASH_SOURCE[0]}" "$root/executed-slurm.sh"
cp "$image" "$scratch/bootstrap.sif"
cp -a "$solver/runtime" "$scratch/runtime"
cp "$root/install-solver.py" "$scratch/install-solver.py"
cp "$root/solver-provenance.json" "$scratch/solver-provenance.json"
cat > "$scratch/repair.def" <<EOF
Bootstrap: localimage
From: $scratch/bootstrap.sif

%labels
    cphmd.delphi-target a64fx
    cphmd.delphi-compiler NVFORTRAN-25.1
    cphmd.delphi-source matched-x86-973e9b99-source-e42194ba
    validation.status experimental-candidate-PBMC-check-required-after-assembly

%files
    $scratch/runtime /opt/cphmd-new-delphi
    $scratch/install-solver.py /opt/cphmd-install-solver.py
    $scratch/solver-provenance.json /opt/cphmd-solver-provenance.json

%post
    python3 /opt/cphmd-install-solver.py
    cp /usr/share/cphmd/build/delphi-a64fx-repair.json /build-evidence/
EOF
cd "$scratch"
singularity build --disable-cache --fakeroot --bind "$scratch/evidence:/build-evidence" \
    "$scratch/candidate.sif" "$scratch/repair.def"
# Leave fakeroot before either scientific test. No solver/library bind is used.
singularity exec --cleanenv --bind "$root:/out" --pwd /out --env TMPDIR=/out/tmp \
    "$scratch/candidate.sif" bash /out/check-unprivileged-runtime.sh \
    > "$root/unprivileged-runtime.log" 2>&1
input=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/hewl-4lzt/solution.P4IU4M/solution
singularity exec --cleanenv --bind "$root/source:/source:ro,$input:/input:ro,$root:/out" \
    --pwd /out --env TMPDIR=/out/tmp "$scratch/candidate.sif" \
    bash /source/tests/arm64/run_hewl_pbmc.sh /source /input/snapshot /input/npt.tpr /out/pbmc \
    > "$root/image-pbmc.log" 2>&1
if python3 "$root/compare_hewl_pbmc.py" "$root/reference" "$root/pbmc/raw" \
    --contract "$root/source/tests/arm64/hewl-pbmc-contract.json" \
    --output "$root/image-comparison.json"; then
    numerical=PASSED
else
    status=$?
    (( status == 1 )) || exit "$status"
    python3 - "$root/image-comparison.json" <<'PY'
"""Permit a reviewed numerical discrepancy, never malformed or incomplete data."""
import json,sys
report=json.load(open(sys.argv[1]))
assert report['sites']==21 and report['pseudostates']==69 and report['matrix_elements']==4761
assert len(report['MC'])==3
assert all(value['max_site_mean_occupancy_difference'] <= 0.02 for value in report['MC'].values())
PY
    numerical=REVIEW_REQUIRED
fi
cp "$scratch/candidate.sif" "$root/CpHMD-arm64-a64fx-pbmc-candidate.sif"
(cd "$root" && sha256sum CpHMD-arm64-a64fx-pbmc-candidate.sif > CpHMD-arm64-a64fx-pbmc-candidate.sif.sha256)
printf 'DELPHI_REPAIR_AND_IMAGE_EXECUTION_PASSED\nNUMERICAL_SCREEN=%s\n' "$numerical" | tee "$root/result.txt"
