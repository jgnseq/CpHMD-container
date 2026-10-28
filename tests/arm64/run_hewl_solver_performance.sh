#!/bin/bash
# Serial engine timer shared by ARM and legacy x86 images without Python.
# The caller verifies source/input/image hashes first and pins one allowed CPU.
# No container startup is included in individual observations. The Python
# auditor runs afterwards, outside the timed region, and must accept the result.
set -Eeuo pipefail
input="$(realpath "${1:?Supply frozen micro inputs}")"
work="${2:?Supply a new output directory}"
mkdir "$work"
work="$(realpath "$work")"
export LC_ALL=C OMP_NUM_THREADS=1
(cd "$input" && sha256sum -c input.sha256) > "$work/input-verification.log"
uname -m > "$work/architecture.txt"
grep Cpus_allowed_list /proc/self/status > "$work/cpu-affinity.txt"
sha256sum /Delphi/delphi_pgf90 /programs/petit1.6.1/petit > "$work/binaries.sha256"
decks=(258-Asp2N P_258-Asp2Nb P_258-Asp2Nf 279-Ntr1N P_279-Ntr1Nb P_279-Ntr1Nf)
for repeat in 1 2 3; do
    mkdir "$work/repeat-$repeat"
    cp "$input"/* "$work/repeat-$repeat/"
    cd "$work/repeat-$repeat"
    for deck in "${decks[@]}"; do
        start="$(date +%s%N)"
        # DelPhi 5 takes the parameter filename as argv[1], not deck contents
        # on stdin. It can STOP with status 0 on bad input, hence the audit.
        /Delphi/delphi_pgf90 "$deck.prm" > "$deck.out" 2>&1
        end="$(date +%s%N)"
        printf 'delphi\t%s\t%s\t%s\n' "$repeat" "$deck.prm" "$((end-start))" >> "$work/timings.tsv"
    done
    start="$(date +%s%N)"
    /programs/petit1.6.1/petit -H 6,6,1 -E 0,0,1 -T 310 -c 2 -r 1729 \
        -q 1000 100000 < PBMC.dat > petit.out 2> petit.err
    end="$(date +%s%N)"
    printf 'petit\t%s\tPBMC.dat\t%s\n' "$repeat" "$((end-start))" >> "$work/timings.tsv"
done
printf '%s\n' ENGINE_EXECUTION_COMPLETE_AUDIT_REQUIRED > "$work/result.txt"
