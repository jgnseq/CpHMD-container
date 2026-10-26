#!/usr/bin/env bash

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
repo_root="$(cd "${script_dir}/.." 2>/dev/null && pwd)"

controller="${repo_root}/CpHMD/scripts/CpHMD.sh"
contract="${repo_root}/CpHMD/scripts/settings_contract.sh"
removed_defaults="${repo_root}/CpHMD/CpHMD-default.settings"
advanced="${repo_root}/template/CpHMD-advanced.settings"
generic="${repo_root}/template/CpHMD-basic.settings"
gromos="${repo_root}/template/CpHMD-basic-G54a7pH.settings"
charmm="${repo_root}/template/CpHMD-basic-CHARMM36pH.settings"
amber="${repo_root}/template/CpHMD-basic-Amber14SBpH.settings"
profiles=( "${generic}" "${gromos}" "${charmm}" "${amber}" )
failures=0

pass() { printf '    PASS: %s\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; failures=$((failures + 1)); }

export_value() {
    local file="$1" name="$2"
    awk -v name="${name}" '
        $0 ~ "^[[:space:]]*export[[:space:]]+" name "[[:space:]]*=" {
            value=$0
            sub("^[[:space:]]*export[[:space:]]+" name "[[:space:]]*=", "", value)
            sub(/[[:space:]]*#.*/, "", value)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            gsub(/^"|"$/, "", value)
            print value
            exit
        }
    ' "${file}"
}

mdp_value() {
    local file="$1" name="$2"
    awk -v name="${name}" '
        {
            line=$0
            sub(/^[[:space:]]*#mdp#[[:space:]]*/, "", line)
            split(line, fields, "=")
            key=fields[1]
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
        }
        key == name {
            value=substr(line, index(line, "=") + 1)
            sub(/;.*/, "", value)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            print value
            exit
        }
    ' "${file}"
}

require_file() {
    [[ -f "$1" ]] && pass "$2" || fail "missing $2: $1"
}
require_declared() {
    grep -Eq "^[[:space:]]*export[[:space:]]+$2[[:space:]]*=" "$1" \
        && pass "$3" || fail "$3: $2 is not explicitly exported"
}
require_export() {
    local observed
    observed="$(export_value "$1" "$2")"
    [[ "${observed}" == "$3" ]] && pass "$4" \
        || fail "$4: expected $2=$3, observed ${observed:-MISSING}"
}
require_mdp() {
    local observed
    observed="$(mdp_value "$1" "$2")"
    [[ "${observed,,}" == "${3,,}" ]] && pass "$4" \
        || fail "$4: expected $2=$3, observed ${observed:-MISSING}"
}

echo "==> Checking explicit CpHMD settings contract"
require_file "${controller}" "CpHMD controller"
require_file "${contract}" "settings-contract helper"
require_file "${advanced}" "advanced settings template"

if [[ -e "${removed_defaults}" ]]; then
    fail "fallback settings file still exists"
else
    pass "fallback settings file is absent"
fi

if grep -Eq 'source[[:space:]]+/CpHMD/CpHMD-default\.settings' "${controller}"; then
    fail "controller still sources the fallback settings file"
else
    pass "controller sources no fallback settings file"
fi

required=(
    GPU nCPU SysName SimTime StartTime ffID pH sites temp ionicstr ionicstrMD
    RelaxSteps EffectiveSteps memb multiple_solutes include_itp
    MembraneCenteringProtocol PBMCDebugPDB epsin epssol PBdim cutoff GridSize
    scaleP scaleM bndcon maxc pot offset UseInputOffset seed ReduceTitration
    RTThreshold RTInterval write_states plumed TOPin GROin NDXin PosRe
    mdpoverride
)

for profile in "${profiles[@]}"; do
    require_file "${profile}" "basic profile $(basename "${profile}")"
    for setting in "${required[@]}"; do
        require_declared "${profile}" "${setting}" "$(basename "${profile}"): ${setting}"
    done
    require_export "${profile}" ReduceTitration 1 "$(basename "${profile}"): RT enabled"
    require_export "${profile}" RTInterval 20 "$(basename "${profile}"): RTInterval"
    require_export "${profile}" write_states n "$(basename "${profile}"): RT debug output"
    require_export "${profile}" SysName CHANGE_ME "$(basename "${profile}"): SysName placeholder"
    require_export "${profile}" SimTime CHANGE_ME "$(basename "${profile}"): SimTime placeholder"
    require_export "${profile}" pH CHANGE_ME "$(basename "${profile}"): pH placeholder"
done

require_export "${advanced}" ReduceTitration 1 "advanced template: RT enabled"
require_export "${advanced}" RTInterval 20 "advanced template: RTInterval"
require_declared "${advanced}" ionicstrMD "advanced template: ionicstrMD"

cmp -s "${generic}" "${gromos}" \
    && pass "generic basic profile equals G54a7pH profile" \
    || fail "generic basic profile differs from G54a7pH profile"

require_export "${gromos}" ffID G54a7pH "GROMOS ffID"
require_mdp "${gromos}" rcoulomb 1.4 "GROMOS Coulomb cutoff"
require_mdp "${gromos}" rvdw 1.4 "GROMOS LJ cutoff"
require_export "${charmm}" ffID CHARMM36pH "CHARMM ffID"
require_mdp "${charmm}" vdw-modifier Force-switch "CHARMM force switch"
require_mdp "${charmm}" rvdw-switch 1.0 "CHARMM switch start"
require_mdp "${charmm}" rvdw 1.2 "CHARMM LJ cutoff"
require_export "${amber}" ffID Amber14SBpH "AMBER ffID"
require_mdp "${amber}" vdw-modifier Potential-shift "AMBER potential shift"
require_mdp "${amber}" rvdw 1.0 "AMBER LJ cutoff"

echo
echo "==> Exercising declaration and placeholder checks"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT
valid="${tmpdir}/valid.settings"
sed \
    -e 's/export SysName="CHANGE_ME"/export SysName="contract-test"/' \
    -e 's/export SimTime="CHANGE_ME"/export SimTime=1/' \
    -e 's/export pH="CHANGE_ME"/export pH=7.0/' \
    -e 's|export TOPin="CHANGE_ME.top"|export TOPin="system.top"|' \
    -e 's|export GROin="CHANGE_ME.gro"|export GROin="system.gro"|' \
    -e 's|export NDXin="CHANGE_ME.ndx"|export NDXin="index.ndx"|' \
    "${gromos}" > "${valid}"

validate_file() {
    bash -c '
        message() {
            if [[ "$1" == E ]]; then
                shift
                printf "%s\n" "$*" >&2
                return 1
            fi
        }
        source "$1"
        source "$2"
        cphmd_validate_explicit_user_settings "$2"
    ' _ "${contract}" "$1"
}

validate_file "${valid}" \
    && pass "edited basic profile satisfies the explicit contract" \
    || fail "edited basic profile failed the explicit contract"

missing="${tmpdir}/missing.settings"
grep -vE '^[[:space:]]*export[[:space:]]+pH[[:space:]]*=' "${valid}" > "${missing}"
if validate_file "${missing}" >/dev/null 2>&1; then
    fail "contract accepted a settings file with no explicit pH"
else
    pass "contract rejects a missing explicit pH"
fi

if validate_file "${gromos}" >/dev/null 2>&1; then
    fail "contract accepted an unedited basic template"
else
    pass "contract rejects CHANGE_ME placeholders"
fi

echo
echo "Settings-profile failures: ${failures}"
[[ ${failures} -eq 0 ]]
