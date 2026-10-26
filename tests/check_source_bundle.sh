#!/bin/bash
# Regression for the shallow-history transfer failure: reject a shallow source,
# then prove a complete source can be exported and cloned without donor objects.
# Uses tiny temporary repositories; no network, HPC access or production data.
set -Eeuo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/cphmd-bundle-test.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
git init --quiet --initial-branch=development "$work/original"
git -C "$work/original" config user.name 'Bundle regression fixture'
git -C "$work/original" config user.email 'fixture@example.invalid'
for number in 1 2 3; do
    printf '%s\n' "$number" > "$work/original/input.txt"
    git -C "$work/original" add input.txt
    git -C "$work/original" -c commit.gpgsign=false commit --quiet -m "fixture $number"
done
# file:// is essential: plain local clones ignore --depth.
git clone --quiet --depth=1 "file://$work/original" "$work/shallow"
if bash "$repo/container_build/create_source_bundle.sh" \
    "$work/shallow" development "$work/rejected.bundle" > "$work/rejected.log" 2>&1; then
    echo 'FAIL: shallow history was accepted' >&2
    exit 1
fi
grep -q 'git fetch --unshallow upstream' "$work/rejected.log"
test ! -e "$work/rejected.bundle"
bash "$repo/container_build/create_source_bundle.sh" \
    "$work/original" development "$work/complete.bundle"
git clone --quiet --branch development "$work/complete.bundle" "$work/recipient"
test "$(git -C "$work/recipient" rev-list --count HEAD)" = 3
cmp "$work/original/input.txt" "$work/recipient/input.txt"
git -C "$work/recipient" fsck --connectivity-only --no-dangling
echo 'PASS: shallow export refused; complete bundle restores history and files'
