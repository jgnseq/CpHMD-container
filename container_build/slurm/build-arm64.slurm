#!/bin/bash
#SBATCH --job-name=cphmd-arm-build
#SBATCH --account=f202500250cpcaa2a
#SBATCH --partition=dev-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=28G
#SBATCH --time=04:00:00
# Scheduler boundary only: reserve native A64FX resources and delegate to the
# launcher frozen inside this candidate's context (not a mutable checkout).
# Source freezing/submission happens on the login node; MD validation follows
# the image build as a separate scientific task.
set -Eeuo pipefail
out="$(realpath "${1:?Supply the prepared build directory}")"
exec bash "$out/context/run_arm64_build.sh" "$out"
