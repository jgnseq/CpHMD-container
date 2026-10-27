#!/bin/bash
#SBATCH --job-name=cphmd-arm-runtime-access
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
# Derive a readable SIF from the compiled candidate without recompilation.
# Only permissions/ACLs change; payload byte hashes are checked in %post. Keep
# the original image, all inputs/logs and the derived image under the project.
# Rootfs assembly uses the previously approved node-local temporary exception;
# normal-user smoke-test temporary files remain in the project.
set -Eeuo pipefail
root="$(realpath "${1:?Supply the new project repair directory}")"
case "$root" in /projects/F202500250CPCAA2/cphmd-container/arm64-20261026/validation/runtime-permissions/*) ;; *) exit 2 ;; esac
[[ $(uname -m) == aarch64 ]] || exit 2
test ! -e "$root/CpHMD-arm64-readable.sif"
export SINGULARITY_CACHEDIR=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/cache/singularity
umask 077
scratch="$(mktemp -d "/tmp/${USER}-cphmd-access-${SLURM_JOB_ID}.XXXXXX")"
mkdir "$scratch/rootfs" "$scratch/evidence" "$root/runtime-tmp"
export SINGULARITY_TMPDIR="$scratch/rootfs"
exec > >(tee "$root/repair-${SLURM_JOB_ID}.log") 2>&1
# Copy build evidence back with the ordinary host user's project access, even
# when fakeroot assembly fails. Do not delete failed temporary diagnostics.
preserve_status () {
    status=$?
    set +e
    cp -a "$scratch/evidence/." "$root/"
    cp "$scratch/repair.def" "$root/executed-repair.def"
    printf '%s\n' "$status" > "$root/exit-${SLURM_JOB_ID}.txt"
    exit "$status"
}
trap preserve_status EXIT
hostname
date -Is
image=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/builds/31ca50688bc0158e44263a78c2b6d9c4ae438d0d-ARM_SVE-20261027T004036Z/CpHMD-arm64.sif
echo "7393d585ad790e1d53089d9199cf11bdbb6b9cbea1016d16b979b3999fb24343  $image" | sha256sum -c -
cp "$image" "$scratch/bootstrap.sif"
cp "$root/source/container_build/arm64/normalize-runtime-permissions.py" "$scratch/normalize.py"
sha256sum "$scratch/normalize.py" | tee "$root/normalizer.sha256"
cat > "$scratch/repair.def" <<EOF
Bootstrap: localimage
From: $scratch/bootstrap.sif

%labels
    cphmd.permission-repair-of 7393d585ad790e1d53089d9199cf11bdbb6b9cbea1016d16b979b3999fb24343
    validation.status ordinary-user-runtime-validation-pending

%files
    $scratch/normalize.py /opt/cphmd-normalize-runtime-permissions.py

%post
    python3 /opt/cphmd-normalize-runtime-permissions.py
    cp /usr/share/cphmd/build/runtime-permissions.json /build-evidence/
    rm /opt/cphmd-normalize-runtime-permissions.py
EOF
cd "$scratch"
singularity build --disable-cache --fakeroot --bind "$scratch/evidence:/build-evidence" \
    "$scratch/CpHMD-arm64-readable.sif" "$scratch/repair.def"
# This exec deliberately has no fakeroot flag. Require a nonzero UID inside
# the image and all runtime smoke gates before publishing the derived SIF.
singularity exec --cleanenv --bind "$root:/validation" --pwd /validation \
    --env TMPDIR=/validation/runtime-tmp "$scratch/CpHMD-arm64-readable.sif" \
    bash /validation/source/container_build/arm64/check-unprivileged-runtime.sh \
    2>&1 | tee "$root/unprivileged-runtime.log"
cp "$scratch/CpHMD-arm64-readable.sif" "$root/CpHMD-arm64-readable.sif"
cd "$root"
sha256sum CpHMD-arm64-readable.sif > CpHMD-arm64-readable.sif.sha256
singularity inspect --json CpHMD-arm64-readable.sif > image-inspect.json
echo 'PERMISSION_REPAIR_AND_UNPRIVILEGED_SMOKE_PASSED' | tee result.txt
