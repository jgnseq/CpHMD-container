#!/bin/bash
#SBATCH --job-name=cphmd-arm-build
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=28G
#SBATCH --time=04:00:00
set -Eeuo pipefail
out="$(realpath "${1:?Supply the prepared build directory}")"
exec bash "$out/context/run_arm64_build.sh" "$out"
