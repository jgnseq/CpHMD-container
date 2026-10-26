#!/bin/bash
#SBATCH --job-name=cphmd-arm-preflight
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:20:00
set -Eeuo pipefail

task_root="${1:?Supply the project sprint directory}"
source_root="${2:?Supply the immutable preflight source directory}"
case "$(realpath "$task_root")" in
    /projects/F202500250CPCAA2/*) ;;
    *) echo 'Refusing storage outside the selected project' >&2; exit 2 ;;
esac
[[ $(uname -m) == aarch64 ]] || { echo 'An ARM node is required'; exit 2; }
run="$task_root/preflight-${SLURM_JOB_ID}"
mkdir "$run"
mkdir -p "$task_root/cache/singularity"
scratch="$(mktemp -d "/tmp/${USER}-cphmd-preflight-${SLURM_JOB_ID}.XXXXXX")"
mkdir "$scratch/rootfs"
export SINGULARITY_CACHEDIR="$task_root/cache/singularity"
export SINGULARITY_TMPDIR="$scratch/rootfs"
export TMPDIR="$scratch/rootfs"
cd "$scratch"
base="$task_root/images/CpHMD-aarch64-phase6-sve512.sif"
test -s "$base"
cp "$base" "$scratch/bootstrap.sif"
hostname
date -Is
lscpu
free -h
sha256sum "$base"
singularity exec --cleanenv "$base" file /programs/petit1.6.1/petit
singularity exec --cleanenv "$base" /programs/petit1.6.1/petit -v
singularity exec --cleanenv --bind "$source_root:/source:ro,$run:/results" "$base" \
    gcc -std=c99 -O2 /source/CpHMD/src/fixgro.c -lm -o /results/fixgro
singularity exec --cleanenv --bind "$source_root:/source:ro,$run:/results" "$base" \
    env TMPDIR=/results python3 /source/tests/arm64/check_fixgro.py --binary /results/fixgro
singularity exec --cleanenv --fakeroot "$scratch/bootstrap.sif" sh -c 'id; test "$(id -u)" -eq 0'
printf 'Bootstrap: localimage\nFrom: %s\n\n%%post\n    test "$(id -u)" -eq 0\n' "$scratch/bootstrap.sif" > "$scratch/fakeroot.def"
cp "$scratch/fakeroot.def" "$run/fakeroot.def"
singularity build --disable-cache --fakeroot "$scratch/fakeroot-probe.sif" "$scratch/fakeroot.def"
cp "$scratch/fakeroot-probe.sif" "$run/fakeroot-probe.sif"
sha256sum "$run/fakeroot-probe.sif"
echo 'PASS: native fixgro, ARM PETIT, and node-local fakeroot assembly with project outputs'
