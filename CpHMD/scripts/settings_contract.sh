#!/usr/bin/env bash
# Explicit user-settings contract for CpHMD.
#
# This is validation/runtime-configuration code, not a settings template.
# It is installed under /CpHMD/scripts and is never copied to /Templates.
# CpHMD.sh sources it before functions.sh or any PB/MC/MD work: validate the
# user's scientific choices first, then supply application paths and policies.

CPHMD_REQUIRED_USER_SETTINGS=(
    GPU
    nCPU
    SysName
    SimTime
    StartTime
    ffID
    pH
    sites
    temp
    ionicstr
    ionicstrMD
    RelaxSteps
    EffectiveSteps
    memb
    multiple_solutes
    include_itp
    MembraneCenteringProtocol
    PBMCDebugPDB
    epsin
    epssol
    PBdim
    cutoff
    GridSize
    scaleP
    scaleM
    bndcon
    maxc
    pot
    offset
    UseInputOffset
    seed
    ReduceTitration
    RTThreshold
    RTInterval
    write_states
    plumed
    TOPin
    GROin
    NDXin
    PosRe
    mdpoverride
)

# cphmd_settings_declares SETTINGS_FILE NAME
# Return success when the file explicitly exports NAME; an inherited shell
# value alone must not satisfy the reproducible scientific-settings contract.
cphmd_settings_declares ()
{
    local settings_file="$1"
    local name="$2"

    grep -Eq \
        "^[[:space:]]*export[[:space:]]+${name}[[:space:]]*=" \
        "${settings_file}"
}

# cphmd_require_settings_declarations SETTINGS_FILE NAME...
# Report all missing declarations together before simulation initialization.
cphmd_require_settings_declarations ()
{
    local settings_file="$1"
    shift

    local name
    local -a missing=()

    for name in "$@"; do
        if ! cphmd_settings_declares "${settings_file}" "${name}"; then
            missing+=( "${name}" )
        fi
    done

    if (( ${#missing[@]} > 0 )); then
        message E "The user settings file must explicitly export these settings: ${missing[*]}"
        return 1
    fi
}

# cphmd_require_nonempty_setting_values NAME...
# Check already-sourced values by variable name; no files/state are changed.
cphmd_require_nonempty_setting_values ()
{
    local name
    local value
    local -a empty=()

    for name in "$@"; do
        value="${!name-}"
        if [[ -z "${value}" ]]; then
            empty+=( "${name}" )
        fi
    done

    if (( ${#empty[@]} > 0 )); then
        message E "These required user settings are empty: ${empty[*]}"
        return 1
    fi
}

# Reject unedited profile placeholders before they can become input filenames
# or scientific parameters. Called during initial settings validation only.
cphmd_reject_template_placeholders ()
{
    local name
    local value

    for name in SysName SimTime ffID pH TOPin GROin NDXin; do
        value="${!name-}"

        case "${value}" in
            CHANGE_ME|CHANGE_ME.*|CHANGE_ME_*|AAA|BBB|TTT|GGG|NNN|FORCEFIELD)
                message E "Setting ${name} still contains the template placeholder '${value}'. Edit the user settings file before running CpHMD."
                return 1
                ;;
        esac
    done
}

# cphmd_require_boolean_value NAME
# Require exactly 0/1 for switches used by later PB/MC and MD branch decisions.
cphmd_require_boolean_value ()
{
    local name="$1"
    local value="${!name-}"

    case "${value}" in
        0|1) ;;
        *)
            message E "${name} must be explicitly set to 0 or 1; received '${value:-unset}'."
            return 1
            ;;
    esac
}

# cphmd_validate_explicit_user_settings SETTINGS_FILE
# Controller entry point: declarations -> values/placeholders -> types ->
# conditional PLUMED requirements. Failure stops startup before any cycle.
cphmd_validate_explicit_user_settings ()
{
    local settings_file="$1"
    local name

    cphmd_require_settings_declarations \
        "${settings_file}" \
        "${CPHMD_REQUIRED_USER_SETTINGS[@]}" \
        || return 1

    cphmd_require_nonempty_setting_values \
        GPU nCPU SysName SimTime StartTime ffID pH sites temp ionicstr \
        RelaxSteps EffectiveSteps memb multiple_solutes include_itp \
        MembraneCenteringProtocol PBMCDebugPDB epsin epssol PBdim cutoff \
        GridSize scaleP scaleM bndcon maxc pot offset UseInputOffset seed \
        ReduceTitration RTThreshold RTInterval write_states plumed \
        TOPin GROin NDXin mdpoverride \
        || return 1

    # ionicstrMD and PosRe are required declarations but may be empty.
    cphmd_reject_template_placeholders || return 1

    for name in \
        GPU memb multiple_solutes include_itp PBMCDebugPDB UseInputOffset \
        ReduceTitration plumed mdpoverride
    do
        cphmd_require_boolean_value "${name}" || return 1
    done

    case "${write_states}" in
        y|n) ;;
        *)
            message E "write_states must be 'y' or 'n'; received '${write_states}'."
            return 1
            ;;
    esac

    if ! [[ "${nCPU}" =~ ^[1-9][0-9]*$ ]]; then
        message E "nCPU must be a positive integer; received '${nCPU}'."
        return 1
    fi

    if ! [[ "${RTInterval}" =~ ^[1-9][0-9]*$ ]]; then
        message E "RTInterval must be a positive integer; received '${RTInterval}'."
        return 1
    fi

    if (( plumed == 1 )); then
        cphmd_require_settings_declarations \
            "${settings_file}" \
            plumedtype colvar_name colvar_stride hills \
            || return 1

        cphmd_require_nonempty_setting_values \
            plumedtype colvar_name colvar_stride hills \
            || return 1

        if [[ "${plumedtype}" == "grid" ]]; then
            cphmd_require_settings_declarations "${settings_file}" grid_name \
                || return 1
            cphmd_require_nonempty_setting_values grid_name \
                || return 1
        fi
    fi
}

# Assign/export image-owned paths and runtime safeguards after validation.
# Scientific choices remain explicit user inputs; advanced path/policy overrides
# are preserved. The controller and functions.sh consume these exported values.
cphmd_apply_internal_runtime_configuration ()
{
    # Container/application paths. Advanced users may override these in their
    # settings file; ordinary users should rely on the image-owned locations.
    : "${CpHDIR:=/CpHMD}"
    : "${GroDIRCPU:=/gromacs/bin/gmx}"
    : "${GroDIRGPU:=/gromacs/bin/gmx-gpu}"
    : "${GroDIR:=/gromacs/bin/gmx}"
    : "${DelphiDir:=/Delphi}"
    : "${StDIR:=}"
    : "${PetitDIR:=/programs/petit1.6.1}"
    : "${ffDIR:=/FFs}"
    : "${DatabaseDIR:=/Databases}"
    : "${CpHcontainer:=}"

    # Fail-fast runtime safeguards. These are application policy, not hidden
    # scientific choices. Advanced settings may override them deliberately.
    : "${CPHMD_STRICT_GROMACS_MODE:=1}"
    : "${CPHMD_GPU_PREFLIGHT:=1}"
    : "${CPHMD_MDRUN_PREFLIGHT:=1}"
    : "${CPHMD_GPU_DEVICE_ID:=0}"

    # Empty values select the controller's validated automatic mdrun commands.
    : "${mdruncpu:=}"
    : "${mdrungpu:=}"

    # Organized-output validation and retention policy.
    : "${CPHMD_VALIDATE_SEGMENT_BINARIES:=1}"
    : "${CPHMD_COMPRESS_SEGMENT_LOGS:=1}"
    : "${CPHMD_COMPRESS_SEGMENT_TPR:=1}"
    : "${CPHMD_COMPRESS_SEGMENT_STRUCTURES:=1}"
    : "${CPHMD_GZIP_LEVEL:=6}"
    : "${CPHMD_KEEP_DRIVER_LOG:=1}"
    : "${CPHMD_KEEP_VALIDATION_LOG:=1}"
    : "${CPHMD_KEEP_RT_DEBUG:=0}"

    export \
        CpHDIR GroDIRCPU GroDIRGPU GroDIR DelphiDir StDIR PetitDIR ffDIR \
        DatabaseDIR CpHcontainer CPHMD_STRICT_GROMACS_MODE \
        CPHMD_GPU_PREFLIGHT CPHMD_MDRUN_PREFLIGHT CPHMD_GPU_DEVICE_ID \
        mdruncpu mdrungpu CPHMD_VALIDATE_SEGMENT_BINARIES \
        CPHMD_COMPRESS_SEGMENT_LOGS CPHMD_COMPRESS_SEGMENT_TPR \
        CPHMD_COMPRESS_SEGMENT_STRUCTURES CPHMD_GZIP_LEVEL \
        CPHMD_KEEP_DRIVER_LOG CPHMD_KEEP_VALIDATION_LOG CPHMD_KEEP_RT_DEBUG
}
