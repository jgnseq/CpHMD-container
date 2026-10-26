#!/bin/bash
# Transfer committed source as a Git bundle; no GitHub credentials on the HPC.
# Default: prepare only. Add --submit to queue the inspected build pipeline.
set -Eeuo pipefail
submit=0
simd=ARM_SVE
jobs=4
while (( $# )); do
    case "$1" in
        --submit) submit=1; shift ;;
        --simd) simd="${2:?}"; shift 2 ;;
        --jobs) jobs="${2:?}"; shift 2 ;;
        *) echo 'Usage: bash container_build/submit_deucalion_arm64.sh [--submit] [--simd ARM_SVE|ARM_NEON_ASIMD] [--jobs 1..8]' >&2; exit 2 ;;
    esac
done
case "$simd" in ARM_SVE|ARM_NEON_ASIMD) ;; *) exit 2 ;; esac
[[ $jobs =~ ^[1-8]$ ]] || exit 2
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
branch=codex/arm64-deucalion-20261026
[[ $(git branch --show-current) == "$branch" ]] || { echo "Switch to $branch first" >&2; exit 2; }
[[ -z $(git status --porcelain --untracked-files=all) ]] || {
    echo 'Review, validate and commit the source before transfer.' >&2; exit 2;
}
revision="$(git rev-parse HEAD)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
task_root=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
source_root="$task_root/sources/$revision"
output="$task_root/builds/$revision-$simd-$stamp"
archive="${CPHMD_GROMACS_SOURCE:-/tmp/cphmd-gromacs-2026.3.tar.gz}"
expected=1094b7bbc6a3960223827114626657110b40096cdf9598a727935fc84ebf8aa0
if [[ ! -e $archive ]]; then
    download="$(mktemp /tmp/cphmd-gromacs-download.XXXXXX)"
    curl --fail --location --retry 3 -o "$download" https://ftp.gromacs.org/gromacs/gromacs-2026.3.tar.gz
    [[ $(sha256sum "$download" | cut -d' ' -f1) == "$expected" ]] || exit 1
    mv "$download" "$archive"
fi
[[ $(sha256sum "$archive" | cut -d' ' -f1) == "$expected" ]] || { echo 'Source checksum mismatch'; exit 1; }
bundle_dir="$(mktemp -d /tmp/cphmd-arm-bundle.XXXXXX)"
git bundle create "$bundle_dir/source.bundle" "$branch"
git bundle verify "$bundle_dir/source.bundle"
ssh_opts=(-o BatchMode=yes -o ConnectTimeout=15 -o ForwardX11=no -o ForwardAgent=no -o ControlMaster=no -o StrictHostKeyChecking=yes)
ssh "${ssh_opts[@]}" deucalion "mkdir -p '$task_root/inputs' '$task_root/sources' '$task_root/logs'"
# Incoming files use unique names; existing scientific/build results are retained.
scp "${ssh_opts[@]}" "$bundle_dir/source.bundle" "deucalion:$task_root/inputs/source-$revision-$stamp.bundle"
scp "${ssh_opts[@]}" "$archive" "deucalion:$task_root/inputs/gromacs-$revision-$stamp.tar.gz"
ssh "${ssh_opts[@]}" deucalion "set -eu
if [ ! -d '$source_root' ]; then
    git clone --branch '$branch' '$task_root/inputs/source-$revision-$stamp.bundle' '$source_root'
fi
test \"\$(git -C '$source_root' rev-parse HEAD)\" = '$revision'
test -z \"\$(git -C '$source_root' status --porcelain --untracked-files=all)\"
python3 '$source_root/container_build/prepare_arm64_build.py' \\
    --output-dir '$output' \\
    --base-image '$task_root/images/CpHMD-aarch64-phase6-sve512.sif' \\
    --gromacs-source '$task_root/inputs/gromacs-$revision-$stamp.tar.gz' \\
    --simd '$simd' --jobs '$jobs'
if [ '$submit' = 1 ]; then
    sbatch --parsable --cpus-per-task='$jobs' --output='$output/slurm-%j.log' \\
        '$source_root/container_build/slurm/build-arm64.slurm' '$output'
fi
"
printf 'Prepared output: %s\n' "$output"
if (( submit == 0 )); then
    printf "Submit after inspection:\nssh deucalion sbatch --cpus-per-task=%s --output=%s/slurm-%%j.log %s/container_build/slurm/build-arm64.slurm %s\n" \
        "$jobs" "$output" "$source_root" "$output"
fi
