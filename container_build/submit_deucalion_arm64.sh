#!/bin/bash
# Workstation entry point: committed source -> verified Git bundle -> project
# checkout -> frozen context -> optional SLURM jobs. No MD executes locally;
# --verify-hewl queues a separate scientific acceptance allocation.
# Default: prepare only. Add --submit to queue the inspected build pipeline.
# See docs/aarch64/DEVELOPER_GUIDE.md for the file/function and cycle map.
set -Eeuo pipefail
submit=0
verify_hewl=0
profile=portable
simd=
jobs=4
usage () {
    # Show the safe default and the explicit hardware-specific alternative.
    echo 'Usage: bash container_build/submit_deucalion_arm64.sh [--submit] [--verify-hewl] [--profile portable|a64fx] [--simd ARM_NEON_ASIMD|ARM_SVE] [--jobs 1..8]'
    echo 'Default: portable ARMv8-A/ASIMD with generic DelPhi. --verify-hewl requires --submit.'
}
while (( $# )); do
    case "$1" in
        --submit) submit=1; shift ;;
        --verify-hewl) verify_hewl=1; shift ;;
        --profile) profile="${2:?}"; shift 2 ;;
        --simd) simd="${2:?}"; shift 2 ;;
        --jobs) jobs="${2:?}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
[[ $jobs =~ ^[1-8]$ ]] || exit 2
(( verify_hewl == 0 || submit == 1 )) || { echo 'Use --submit with --verify-hewl' >&2; exit 2; }
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
selection=(--profile "$profile")
[[ -z $simd ]] || selection+=(--simd "$simd")
# Read fixed policy values as data, never evaluate generated shell commands.
selected="$(python3 "$repo/container_build/arm64/profiles.py" "${selection[@]}")"
readarray -t chosen <<< "$selected"
profile="${chosen[0]}"; simd="${chosen[1]}"; base_relative="${chosen[2]}"
branch="$(git branch --show-current)"
[[ $branch =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || {
    echo 'Use a named Git branch with letters, digits, dot, underscore, slash or hyphen.' >&2; exit 2;
}
[[ -z $(git status --porcelain --untracked-files=no) ]] || {
    echo 'Review, validate and commit tracked changes before transfer.' >&2; exit 2;
}
# Bundles contain committed objects only; unrelated untracked notes stay local.
# Required new build files must themselves be committed, never silently omitted.
git ls-files --error-unmatch -- container_build/arm64/profiles.py \
    container_build/arm64/stage-bootstrap-delphi.py \
    container_build/arm64/install-portable-delphi.py \
    container_build/slurm/verify-arm64-candidate.slurm >/dev/null 2>&1 || {
        echo 'Commit the ARM profile/installer/acceptance files before exporting.' >&2; exit 2;
    }
python3 "$repo/tests/check_repository_safety.py"
revision="$(git rev-parse HEAD)"
# Fail before downloading/uploading anything when history is incomplete. The
# bundle helper repeats this check and independently clones the actual pack.
if [[ $(git rev-parse --is-shallow-repository) != false ]]; then
    echo 'Run git fetch --unshallow upstream, then retry this command.' >&2
    exit 2
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
task_root=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
source_root="$task_root/sources/$revision"
output="$task_root/builds/$revision-$profile-$simd-$stamp"
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
bash "$repo/container_build/create_source_bundle.sh" "$repo" "$branch" "$bundle_dir/source.bundle"
ssh_opts=(-o BatchMode=yes -o ConnectTimeout=15 -o ForwardX11=no -o ForwardAgent=no -o ControlMaster=no -o StrictHostKeyChecking=yes)
ssh "${ssh_opts[@]}" deucalion "mkdir -p '$task_root/inputs' '$task_root/sources' '$task_root/logs'"
# Incoming files use unique names; existing scientific/build results are retained.
scp "${ssh_opts[@]}" "$bundle_dir/source.bundle" "deucalion:$task_root/inputs/source-$revision-$stamp.bundle"
scp "${ssh_opts[@]}" "$archive" "deucalion:$task_root/inputs/gromacs-$revision-$stamp.tar.gz"
reference_args=
if (( verify_hewl )); then
    reference_args="--pbmc-reference '$task_root/portable.20261028.MZWHAj/seed/context/portable-reference'"
fi
ssh "${ssh_opts[@]}" deucalion "set -eu
if [ ! -e '$source_root' ]; then
    # Publish the checkout only after both clone and connectivity checks pass.
    # Any staging directory left after a failure is retained for inspection;
    # later attempts use a fresh timestamp without deleting existing data.
    git clone --branch '$branch' '$task_root/inputs/source-$revision-$stamp.bundle' '$source_root.incoming-$stamp'
    git -C '$source_root.incoming-$stamp' fsck --connectivity-only --no-dangling
    test \"\$(git -C '$source_root.incoming-$stamp' rev-parse HEAD)\" = '$revision'
    mv -T '$source_root.incoming-$stamp' '$source_root'
fi
# Reusing an existing checkout is allowed only if it is complete and unmodified.
git -C '$source_root' fsck --connectivity-only --no-dangling
test \"\$(git -C '$source_root' rev-parse HEAD)\" = '$revision'
test -z \"\$(git -C '$source_root' status --porcelain --untracked-files=all)\"
python3 '$source_root/container_build/prepare_arm64_build.py' \\
    --output-dir '$output' \\
    --base-image '$task_root/$base_relative' \\
    --gromacs-source '$task_root/inputs/gromacs-$revision-$stamp.tar.gz' \\
    --profile '$profile' --simd '$simd' --jobs '$jobs' $reference_args
if [ '$submit' = 1 ]; then
    build_job=\$(sbatch --parsable --cpus-per-task='$jobs' --output='$output/slurm-%j.log' \\
        '$source_root/container_build/slurm/build-arm64.slurm' '$output')
    printf 'build\\t%s\\n' \"\$build_job\" | tee '$output/submissions.tsv'
    if [ '$verify_hewl' = 1 ]; then
        gate_job=\$(sbatch --parsable --kill-on-invalid-dep=yes --dependency=\"afterok:\$build_job\" \\
            --output='$output/acceptance-%j.log' \\
            '$output/context/verify-arm64-candidate.slurm' '$output')
        printf 'acceptance\\t%s\\n' \"\$gate_job\" | tee -a '$output/submissions.tsv'
    fi
fi
"
printf 'Selected profile: %s (%s)\n' "$profile" "$simd"
printf 'Prepared output: %s\n' "$output"
if (( submit == 0 )); then
    printf "Submit after inspection:\nssh deucalion sbatch --cpus-per-task=%s --output=%s/slurm-%%j.log %s/container_build/slurm/build-arm64.slurm %s\n" \
        "$jobs" "$output" "$source_root" "$output"
fi
