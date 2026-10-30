#!/bin/bash
# Optional workstation recovery after Deucalion access ends. Fetch the accepted
# portable image and, by default, its complete source/results archive from mini05.
# Uses existing SSH trust, resumes partial transfers and checks pinned hashes.
# Writes only under artifacts, outside Git. Never extracts/executes the archive.
# Use --image-only for the 311 MB SIF; default also copies the 1.17 GB archive.
set -Eeuo pipefail
image_only=0
case "${1:-}" in
    '') [[ $# == 0 ]] || exit 2 ;;
    --image-only) [[ $# == 1 ]] || exit 2; image_only=1 ;;
    *) echo 'Usage: bash container_build/fetch_accepted_arm64_candidate.sh [--image-only]' >&2; exit 2 ;;
esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
artifacts="$(cd "$repo/.." && pwd)/artifacts"
destination="$artifacts/arm64/accepted-portable-20261030"
mkdir -p "$destination"
exec 9>"$destination/fetch.lock"
flock -n 9 || { echo 'An accepted-candidate fetch is already active' >&2; exit 3; }
remote=/home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.default-portable.20261029.Hl8Yxh
connection=(ssh -o BatchMode=yes -o ConnectTimeout=15 -o ForwardX11=no
    -o ForwardAgent=no -o ControlMaster=no -o StrictHostKeyChecking=yes)
transport='ssh -o BatchMode=yes -o ConnectTimeout=15 -o ForwardX11=no -o ForwardAgent=no -o ControlMaster=no -o StrictHostKeyChecking=yes'
# Refuse incomplete mirrors before moving large files. The SHA checks below
# independently bind the bytes to the reviewed candidate rather than a filename.
"${connection[@]}" mini05 "test \"\$(cat '$remote/verification.exit')\" = 0 && test \"\$(cat '$remote/pull.exit')\" = 0"
rsync --archive --no-owner --no-group --checksum --partial --partial-dir=.rsync-partial \
    --info=progress2 -e "$transport" "mini05:$remote/image.sif" "$destination/CpHMD-arm64-portable.sif"
(cd "$destination" && printf '%s\n' \
    'd4d4278861eb1e9917db8b0ca74b32304fca69674a109f9813574807b85fb5f4  CpHMD-arm64-portable.sif' | sha256sum -c -)
if (( image_only == 0 )); then
    archive=CpHMD-portable-default-validation.tar.gz
    rsync --archive --no-owner --no-group --checksum --partial --partial-dir=.rsync-partial \
        --info=progress2 -e "$transport" "mini05:$remote/candidate/$archive" \
        "mini05:$remote/candidate/$archive.sha256" \
        "mini05:$remote/candidate/$archive.manifest.json" "$destination/"
    (cd "$destination" && printf '%s\n' \
        '77a4cb39167dc98fe9d9e893de9321ebaff74a3570055e198dfda3c98af26745  CpHMD-portable-default-validation.tar.gz' | sha256sum -c -)
fi
echo ACCEPTED_PORTABLE_CANDIDATE_FETCHED_AND_SHA256_VERIFIED
