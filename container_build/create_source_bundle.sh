#!/bin/bash
# Export one committed branch for the workstation -> HPC transfer stage.
# A bundle is accepted only after a fresh repository can clone it, traverse its
# history and recover the exact branch tip. No network access or job submission.
set -Eeuo pipefail

# require_full_history REPOSITORY
# Reject shallow boundaries before packing: bundle verify in the source repo
# alone does not prove that a recipient without its objects can clone the pack.
require_full_history () {
    if [[ $(git -C "$1" rev-parse --is-shallow-repository) != false ]]; then
        echo 'Cannot export a self-contained build bundle from a shallow repository.' >&2
        echo 'Run in the source checkout: git fetch --unshallow upstream' >&2
        echo 'Then rerun the submission helper; no files have been uploaded.' >&2
        return 2
    fi
}

# create_verified_bundle REPOSITORY BRANCH BUNDLE
# Create a portable v2 bundle, check it independently and retain it for upload.
# Only the disposable verification clone is removed on exit; failed bundles
# remain available for diagnosis. Existing output files are never overwritten.
create_verified_bundle () (
    local repo="$1" branch="$2" bundle="$3" revision verify_dir
    require_full_history "$repo"
    [[ ! -e $bundle ]] || { echo "Bundle already exists: $bundle" >&2; return 2; }
    revision="$(git -C "$repo" rev-parse "refs/heads/$branch")"
    git -C "$repo" bundle create --version=2 "$bundle" "refs/heads/$branch"
    verify_dir="$(mktemp -d /tmp/cphmd-bundle-verify.XXXXXX)"
    # EXIT, rather than RETURN, also handles an interrupted/failed Git command.
    trap 'rm -rf -- "$verify_dir"' EXIT
    git init --quiet "$verify_dir/empty"
    git -C "$verify_dir/empty" bundle verify "$bundle"
    git clone --quiet --no-checkout --branch "$branch" "$bundle" "$verify_dir/clone"
    git -C "$verify_dir/clone" fsck --connectivity-only --no-dangling
    [[ $(git -C "$verify_dir/clone" rev-parse HEAD) == "$revision" ]]
    git -C "$verify_dir/clone" checkout --quiet "$branch"
    printf 'PASS: independent clone and history connectivity for %s\n' "$revision"
)

[[ $# == 3 ]] || { echo "Usage: $0 REPOSITORY BRANCH NEW_BUNDLE_PATH" >&2; exit 2; }
# Resolve before Git changes directory so relative caller paths remain correct.
create_verified_bundle "$(realpath "$1")" "$2" "$(realpath -m "$3")"
