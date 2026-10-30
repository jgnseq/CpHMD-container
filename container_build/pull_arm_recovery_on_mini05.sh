#!/bin/bash
# Pull verified Deucalion recovery archives directly onto mini05, independently
# of the workstation. Uses mini05's existing SSH authentication/known hosts;
# never copies keys or enables agent forwarding. Run under a detached bounded
# timeout on mini05. No submissions, source edits or destructive cleanup occur.
set -Eeuo pipefail
root="$(realpath "${1:?Supply the mini05 recovery-pull directory}")"
case "$root" in /home/jsequeira/Projects/side/06_CpHMD-container/validation/recovery-pull.*) ;; *) exit 2 ;; esac
[[ $# == 1 || $# == 3 ]] || { echo 'Use ROOT [REMOTE_RECOVERY_ROOT LABEL]' >&2; exit 2; }
wait_attempts="${CPHMD_RECOVERY_WAIT_ATTEMPTS:-120}"
[[ $wait_attempts =~ ^[0-9]+$ ]] || exit 2
wait_attempts="$((10#$wait_attempts))"
(( wait_attempts >= 1 && wait_attempts <= 840 )) || exit 2
if [[ $# == 3 ]]; then
    # The source enters an SSH command: accept only this project's simple
    # recovery-folder names, never shell metacharacters or traversal paths.
    [[ $2 =~ ^/projects/F202500250CPCAA2/cphmd-container/arm64-20261026/recovery\.[A-Za-z0-9._-]+$ ]] || exit 2
    [[ $3 =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && $3 != *..* ]] || exit 2
fi
# A second invocation must not race an active transfer or its status markers.
exec 9>"$root/pull.lock"
flock -n 9 || { echo 'Recovery pull already active' >&2; exit 3; }
preserve_status () {
    status=$?
    printf '%s\n' "$status" > "$root/pull.exit"
    exit "$status"
}
trap preserve_status EXIT
printf '%s\n' RUNNING > "$root/pull.exit"
mkdir -p "$root/tmp"
export TMPDIR="$root/tmp"
connection=(ssh -o BatchMode=yes -o ConnectTimeout=15 -o ForwardX11=no
    -o ForwardAgent=no -o ControlMaster=no -o StrictHostKeyChecking=yes)
rsync_connection='ssh -o BatchMode=yes -o ConnectTimeout=15 -o ForwardX11=no -o ForwardAgent=no -o ControlMaster=no -o StrictHostKeyChecking=yes'

wait_and_copy () {
    # Wait one hour by default; an explicit build-pipeline caller may allow up
    # to seven hours (840 checks). Nonzero status or
    # SSH failures stop this pull; there is no automatic job/transfer retry.
    # Every rsync partial stays on mini05 and can be reused by a later rerun.
    local source="$1" label="$2" status attempt ready=0
    for ((attempt=1; attempt<=wait_attempts; attempt++)); do
        status="$("${connection[@]}" deucalion "if test -f '$source/pack.exit'; then cat '$source/pack.exit'; else printf '%s\\n' PENDING; fi")"
        case "$status" in
            0) ready=1; break ;;
            PENDING) sleep 30 ;;
            *) echo "Archive preparation failed or has unexpected status: $status" >&2; return 1 ;;
        esac
    done
    [[ $ready == 1 ]] || { echo 'Archive preparation wait expired' >&2; return 1; }
    mkdir -p "$root/$label"
    rsync --archive --no-owner --no-group --checksum --partial --partial-dir=.rsync-partial --info=progress2 \
        -e "$rsync_connection" --include='*.tar.gz' --include='*.tar.gz.sha256' \
        --include='*.tar.gz.manifest.json' --exclude='*' \
        "deucalion:$source/" "$root/$label/"
    (cd "$root/$label" && sha256sum -c ./*.tar.gz.sha256)
    printf 'RECOVERY_FOLDER_SHA256_VERIFIED %s\n' "$label"
}

base=/projects/F202500250CPCAA2/cphmd-container/arm64-20261026
if [[ $# == 3 ]]; then
    wait_and_copy "$2" "$3"
else
    wait_and_copy "$base/recovery.20261029.YOLhIH" build-and-reference
    wait_and_copy "$base/recovery.portable-final.20261029.WZ0lBZ" portable-validation
fi
echo OFF_CLUSTER_RECOVERY_ON_MINI05_PASSED
