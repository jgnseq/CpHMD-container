#!/bin/bash
# CpHMD constant-pH molecular-dynamics controller.
prog=`basename $0`
usage="Usage: $prog <MyProtein_001>.settings\n
       <MyProtein_001>.settings  : Constant-pH MD settings file"
#
# Extended pattern matching is enabled for compatibility with sourced helpers.
#
shopt -s extglob
# message TYPE TEXT...: E=error, U=usage error, W=warning.
message ()
{
    case "$1" in
        E ) shift; echo -e "$prog: Error: $*" >&2 ; exit 1;;
        U ) shift; echo -e "$prog: Warning: $*\n$usage" >&2; exit 1;;
        W ) shift; echo -e "$prog: Warning: $*" >&2;;
        * ) message E "Wrong use of 'message' function.";;
    esac
}
#
# Require exactly one user settings file.
if [ $# != 1 ]; then message U "Wrong number of arguments."; fi

#
###############################################################################
# 1. Load and validate the explicit user settings
###############################################################################
settings_file="$1"

if [[ ! -r "${settings_file}" ]]; then
    message E "The user settings file is missing or unreadable: ${settings_file}"
fi

controller_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P)"
settings_contract="${controller_dir}/settings_contract.sh"

if [[ ! -r "${settings_contract}" ]]; then
    message E "The settings-contract helper is missing or unreadable: ${settings_contract}"
fi

source "${settings_contract}"

# Scientific and system choices must be exported explicitly by the user file.
# Only application-owned paths, safeguards and output-retention behavior are
# assigned internally by cphmd_apply_internal_runtime_configuration.
source "${settings_file}"     || message E "Could not source the user settings file: ${settings_file}"

cphmd_validate_explicit_user_settings "${settings_file}"     || message E "The user settings file did not satisfy the explicit settings contract."

cphmd_apply_internal_runtime_configuration

###############################################################################
# 2. Select the requested GROMACS implementation
###############################################################################
# The dual-build image provides independent CPU-only and CUDA executables:
#   GPU=0 -> GroDIRCPU
#   GPU=1 -> GroDIRGPU
#
# GroDIRCPU or GroDIRGPU selects the released image's corresponding build.
# GroDIR is retained only as a fallback when that mode-specific value is unset.
###############################################################################
case "${GPU:-0}" in
    0)
        selected_gromacs="${GroDIRCPU:-${GroDIR:-/gromacs/bin/gmx}}"
        selected_mode="CPU"
        ;;
    1)
        selected_gromacs="${GroDIRGPU:-${GroDIR:-/gromacs/bin/gmx-gpu}}"
        selected_mode="CUDA"
        ;;
    *)
        message E "GPU must be either 0 (CPU-only GROMACS) or 1 (CUDA GROMACS); received: ${GPU:-unset}"
        ;;
esac

# Fail immediately when the selected launcher is missing or not executable.
# Compile-mode and GPU-visibility checks run later, after functions.sh is
# loaded, but still before any PB/MC work.
if [[ ! -x "${selected_gromacs}" ]]; then
    message E "Selected ${selected_mode} GROMACS executable is missing or not executable: ${selected_gromacs}"
fi

export GroDIR="${selected_gromacs}"
message W "Selected ${selected_mode} GROMACS executable: ${GroDIR}"
#
###############################################################################
# 3. Define simulation, segment and scientific-state names
###############################################################################
export runname=${SysName}
export blockname="${SysName}_CpHrun"

#
# Explicit site/state names avoid ambiguous reuse of the temporary legacy
# ${runname}.sites file created internally by make_sites.
export CPHMD_ALL_SITES_FILE="${runname}-all.sites"
export CPHMD_RT_ACTIVE_SITES_FILE="${runname}-RT-active.sites"
export CPHMD_RT_HISTORY_FILE="${runname}-RT-history.sites"
export CPHMD_RT_TEMPLATE_OCC_FILE="TMP_RT_template.occ"
export CPHMD_RT_TEMPLATE_MOCC_FILE="TMP_RT_template.mocc"
export CPHMD_RT_CURRENT_OCC_FILE="TMP_RT_current.occ"
export CPHMD_RT_CURRENT_MOCC_FILE="TMP_RT_current.mocc"

# Use a short PB/MC basename for disposable legacy Delphi/PETIT files.
# Keeping it independent of SysName avoids silent Fortran filename failures.
export CPHMD_PBMC_BASENAME="PBMC"

###############################################################################
# 4. Create the application-owned output layout
###############################################################################
# Under the scheduler wrapper, node-local scratch is mounted as /out and this
# script starts there. These directories are therefore created in scratch.
# The wrapper synchronizes only validated finalized content to persistent
# project storage.
#
# Directory names are a fixed contract shared by CpHMD.sh and the scheduler
# wrapper. CpHMD owns scientific directories and checkpoint.state; the wrapper
# owns slurm_files/, RUNNING/DONE/FAILED and the resubmission counter.
#
# Relative-path validation prevents absolute paths and parent traversal.
export CPHMD_SEGMENT_DIR="segments"
export CPHMD_RESTART_DIR="restart"
export CPHMD_LOG_DIR="log-files"
export CPHMD_RESUB_DIR="resub_maint"

for output_dir in \
    "${CPHMD_SEGMENT_DIR}" \
    "${CPHMD_RESTART_DIR}" \
    "${CPHMD_LOG_DIR}" \
    "${CPHMD_RESUB_DIR}"
do
    if [[ -z "${output_dir}" || "${output_dir}" == /* || "${output_dir}" == *".."* ]]; then
        message E "CpHMD output directories must be non-empty relative paths without '..': ${output_dir}"
    fi

    mkdir -p -- "${output_dir}" \
        || message E "Could not create CpHMD output directory ${output_dir}."
done

message W "CpHMD output layout: ${CPHMD_SEGMENT_DIR}/, ${CPHMD_RESTART_DIR}/, ${CPHMD_LOG_DIR}/ and ${CPHMD_RESUB_DIR}/."

###############################################################################
# 5. Initialize checkpoint, walltime and exit-code state
###############################################################################
# CPHMD_MAX_SECONDS=0 disables the cycle-boundary walltime guard.
# When enabled, the run stops only after a complete CpHMD cycle, finalizes the
# current scheduler segment and returns exit code 10 for clean resubmission.
#
# Cycle checkpoints are complete local restart snapshots but remain
# non-finalized until segment-level validation succeeds.
###############################################################################
export CPHMD_CHECKPOINT_FILE="${CPHMD_CHECKPOINT_FILE:-${CPHMD_RESUB_DIR}/checkpoint.state}"
export CPHMD_WALL_START_EPOCH="${CPHMD_WALL_START_EPOCH:-$(date +%s)}"
export CPHMD_MAX_SECONDS="${CPHMD_MAX_SECONDS:-0}"

# Exit code 10 marks a validated scheduler boundary.
# Exit code 42 marks an MD/output-contract failure; 43 marks a PB/MC failure.
# Failure codes are never eligible for automatic scheduler resubmission.
readonly CPHMD_EXIT_CLEAN_RESUBMIT=10
readonly CPHMD_EXIT_OUTPUT_FAILURE=42
readonly CPHMD_EXIT_PBMC_FAILURE=43
export CPHMD_EXIT_CLEAN_RESUBMIT CPHMD_EXIT_OUTPUT_FAILURE CPHMD_EXIT_PBMC_FAILURE

export CPHMD_DONE_CYCLES=0
export CPHMD_LAST_SEGMENT_START=0
export CPHMD_LAST_SEGMENT_END=0
export CPHMD_SEGMENT_FINALIZED=0
export CPHMD_REDUCED_TITRATION="${ReduceTitration:-0}"
export CPHMD_RT_LAST_FULL_CYCLE=0
export CPHMD_RT_ACTIVE_COUNT=0

if [[ -f "${CPHMD_CHECKPOINT_FILE}" ]]; then
    # The state file is written atomically by functions.sh and contains only
    # simple shell assignments.
    source "${CPHMD_CHECKPOINT_FILE}"
fi

if [[ -z "${CPHMD_DONE_CYCLES:-}" ]]; then
    export CPHMD_DONE_CYCLES=0
fi

# Restore compact restart inputs only when checkpoint.state reports completed
# cycles from a finalized scheduler segment.
if (( CPHMD_DONE_CYCLES > 0 )); then
    message W "Restart checkpoint found: ${CPHMD_DONE_CYCLES} completed cycles."

    # A new job may continue only from a fully validated scheduler segment.
    # A cycle-level scratch checkpoint is deliberately insufficient because
    # its accumulated XTC/EDR may not have been committed.
    if (( ${CPHMD_SEGMENT_FINALIZED:-0} != 1 )); then
        message E "Checkpoint ${CPHMD_CHECKPOINT_FILE} is not marked as a finalized segment. Refusing automatic continuation."
    fi

    restart_gro="${CPHMD_RESTART_DIR}/${blockname}.gro"
    restart_top="${CPHMD_RESTART_DIR}/${blockname}.top"

    if [[ -f "${restart_gro}" ]]; then
        export GROin="./${restart_gro}"
    else
        message E "Checkpoint says cycles were completed, but ${restart_gro} is missing."
    fi

    if [[ -f "${restart_top}" ]]; then
        export TOPin="./${restart_top}"
    else
        message E "Checkpoint says cycles were completed, but ${restart_top} is missing."
    fi
fi
#
###############################################################################
if [[ $ffID != G54a7pH && $ffID != CHARMM36pH && $ffID != Amber14SBpH ]]; then
    message W "\n***** WARNING *****\n**** You are using a force-field which is not standard.\n**** The use of  $ffID implies that the paths for the Delphi databases, tautomer St files, and force field is given to the program."
fi

# Select a user-supplied tautomer-state directory or the container default.

if [[ -d $StDIR ]] ; then
    message W "StDIR inputed by the user at $StDIR"
else
    StDIR="/STs/St-${ffID}"
    message W "StDIR not found, using base container ST directory."
fi

# Load the shared CpHMD function library.
functions=$CpHDIR/scripts/functions.sh
if [[ -f $functions ]]; then
    source $functions
else
    message E "File $functions is missing. Check CpHDIR parameter in $1."
fi

###############################################################################
# 6. Extract and validate blocks embedded in the settings file
###############################################################################
# The #mdp# block is always required. #fixgro# and #plumed# blocks are
# materialized only when their workflows are active; otherwise they remain
# inert comments in the settings file.

mdp_file="${SysName}.mdp"
fixgro_file="${SysName}.fixgro"
plumed_file="${SysName}_plumed.dat"

awk '/#mdp#[[:space:]]/ {sub(/^.*#mdp#[[:space:]]*/, ""); print}' \
    "${settings_file}" > "${mdp_file}"
if ! grep -Eq '^[[:space:]]*[^;#[:space:]]' "${mdp_file}"; then
    message E "The settings file contains no usable #mdp# block."
fi

# Validate simple feature flags before selecting optional input blocks.
for flag_name in memb multiple_solutes include_itp plumed; do
    flag_value="${!flag_name:-0}"
    case "${flag_value}" in
        0|1) ;;
        *) message E "${flag_name} must be 0 or 1; received '${flag_value}'." ;;
    esac
done

rm -f -- "${fixgro_file}"
export CPHMD_FIXGRO_REQUIRED=0
if cphmd_fixgro_required; then
    export CPHMD_FIXGRO_REQUIRED=1
    awk '/#fixgro#[[:space:]]/ {sub(/^.*#fixgro#[[:space:]]*/, ""); print}' \
        "${settings_file}" > "${fixgro_file}"
    cphmd_validate_fixgro_file "${fixgro_file}"
    message W "Using the #fixgro# settings block for non-membrane PBC repair."
else
    message W "The #fixgro# settings block is inactive for this system configuration."
fi

rm -f -- "${plumed_file}"
if (( plumed == 1 )); then
    case "${plumedtype:-}" in
        grid|hill|static) ;;
        *) message E "plumedtype must be grid, hill or static when plumed=1; received '${plumedtype:-unset}'." ;;
    esac

    awk '/#plumed#[[:space:]]/ {sub(/^.*#plumed#[[:space:]]*/, ""); print}' \
        "${settings_file}" > "${plumed_file}"

    # Replace documented PLUMED template tokens only while PLUMED is active.
    # Missing required values stop the run before simulation work begins.
    : "${colvar_stride:?Set colvar_stride when plumed=1}"
    : "${colvar_name:?Set colvar_name when plumed=1}"
    : "${hills:?Set hills when plumed=1}"

    sed -i \
        -e "s|&colvar_stride|${colvar_stride}|g" \
        -e "s|&colvar_name|${colvar_name}|g" \
        -e "s|&hills|${hills}|g" \
        "${plumed_file}"

    if [[ ${plumedtype} == "grid" ]]; then
        : "${grid_name:?Set grid_name when plumedtype=grid}"
        sed -i -e "s|&grid_name|${grid_name}|g" "${plumed_file}"
    fi

    cphmd_validate_plumed_file "${plumed_file}"

    # Continuation requires a PLUMED RESTART directive. run_dynamics creates a
    # temporary first-cycle copy when that directive must be suppressed.
    if ! grep -Eq '^[[:space:]]*RESTART([[:space:]]|$)' "${plumed_file}"; then
        plumed_tmp="${plumed_file}.tmp.$$"
        {
            echo "RESTART"
            cat "${plumed_file}"
        } > "${plumed_tmp}" || message E "Could not add RESTART to ${plumed_file}."
        mv -f -- "${plumed_tmp}" "${plumed_file}" \
            || message E "Could not finalize ${plumed_file}."
    fi
    message W "PLUMED is enabled with plumedtype=${plumedtype}."
else
    message W "The #plumed# settings block is inactive because plumed=0."
fi

###############################################################################
# 7. Calculate the requested CpHMD cycle range
###############################################################################
dt=`awk '/dt/ {print $3}' ${SysName}.mdp`
if [ -z "$dt" ] ;
then
    dt=0.002
    message W "dt was not defined in the .mdp, falling back to 0.002 default dt."
fi

EndCycle=`echo ${SimTime} $EffectiveSteps $dt | awk '{print int(($1*1000)/($2*$3)+0.5)}'`

if (( CPHMD_DONE_CYCLES >= EndCycle )); then
    message W "CpHMD checkpoint indicates that ${CPHMD_DONE_CYCLES}/${EndCycle} cycles are already complete."
    exit 0
fi

FirstCycle=$((CPHMD_DONE_CYCLES + 1))
export CPHMD_SEGMENT_START_CYCLE="${FirstCycle}"

message W "Running CpHMD cycles from ${FirstCycle} until ${EndCycle} with 20 ps each cycle."
message W "Checkpoint restart: completed cycles = ${CPHMD_DONE_CYCLES}; starting at cycle ${FirstCycle} of ${EndCycle}."
if (( CPHMD_MAX_SECONDS > 0 )); then
    message W "CpHMD cycle-boundary walltime guard: ${CPHMD_MAX_SECONDS} seconds."
fi

###############################################################################
# Native PLUMED integration
###############################################################################
# Both CPU and CUDA GROMACS builds use the same native PLUMED integration.
# The previous executable-rebasing approach is retained only as historical
# context and is intentionally inactive.
#
# Known follow-up item:
#   The status message below states a fixed 20 ps cycle length although the
#   calculation uses EffectiveSteps multiplied by dt.
#   The historical wording and dt fallbacks remain unchanged in Stage 2.
###############################################################################

###############################################################################
# 8. Build mdrun command and perform fail-fast runtime checks
###############################################################################
# This block runs before the private working directory and before PB/MC.
# It validates:
#   * GPU, nCPU and runtime-safety settings;
#   * the selected GROMACS executable and compile mode;
#   * NVIDIA device and driver visibility when GPU=1.
#
# A CUDA build launched without container GPU passthrough terminates here.
# A second zero-step mdrun probe runs after the initial TPR is generated,
# still before site generation or PB/MC.
###############################################################################
cphmd_build_mdrun_command
cphmd_preflight_gromacs_runtime

# Create one process-specific directory for all mutable inner-run files.
mkdir -p ./CpHMD-run_$$

# Validate and stage the generated MDP plus external GRO, TOP and NDX inputs.
for f in ${SysName}.mdp $GROin $TOPin $NDXin
do
    if [ ! -f $f ]; then
        message E  "File $f is missing!!!... Program will crash"
    fi
done

cp "${settings_file}" "./CpHMD-run_$$/"
cp "${mdp_file}" "./CpHMD-run_$$/"
if (( CPHMD_FIXGRO_REQUIRED == 1 )); then
    cp "${fixgro_file}" "./CpHMD-run_$$/"
fi

cp $GROin ./CpHMD-run_$$/${SysName}.gro ; GROin="./${SysName}.gro"
cp $TOPin ./CpHMD-run_$$/${SysName}.top ; TOPin="./${SysName}.top"
cp $NDXin ./CpHMD-run_$$/${SysName}.ndx ; NDXin="./${SysName}.ndx"

# Copy PLUMED input only when the PLUMED workflow is active.
if (( plumed == 1 )); then
    cp "${plumed_file}" "./CpHMD-run_$$/"
fi

cd ./CpHMD-run_$$

###############################################################################
correct_variables #SC 17/3/2010
# 9. Initialize the private CpHMD working state
# Record run provenance and the initial wall-clock timestamp.
echo -e "Simulation run by $USER  @  $HOSTNAME\nInitial time: `date`" \
    > ${blockname}.info
#
# Remove stale temporary inner-run files without touching organized output.
clean_up
#
# Prepare the selected force-field data.
build_forcefield
#
# Validate inputs, paths, MDP compatibility and optional workflow files.
check_files
#
# Generate auxiliary files, including the initial TPR used by the execution
make_auxiliary_files || exit $?
# preflight.
# Run the configured mdrun command for zero integration steps before PB/MC.
# Invalid CPU/GPU execution therefore fails before electrostatics or Monte
# Carlo work is attempted.
cphmd_preflight_mdrun_execution || exit $?
#
# Build the immutable all-site definition. make_sites removes its temporary
# legacy ${runname}.sites file after the explicit all-site file is ready.
make_sites "$1"
# Restore reduced-titration state from a finalized checkpoint or initialize a
# clean first-run state before the first PB/MC cycle.
cphmd_initialize_or_restore_rt_state || exit $?
#
# Prepare state templates for the immutable all-site definition. Reduced
# cycles use subsets of these same site definitions.
"$DelphiDir"/getst "${CPHMD_ALL_SITES_FILE}" "$StDIR" ||     message E "getst failed for ${CPHMD_ALL_SITES_FILE}."
#
# Build the run-specific Delphi database.
make_delphi_DB
#
###############################################################################
# 10. Execute the constant-pH MD cycle
TimeStep=`awk '/dt *=/{print $3}' ${runname}.mdp`
# Historical TimeStep fallback behavior is preserved in this comment-only pass.
if [[ $TimeStep == "" ]]; then TimeStep=0.001; fi #SC 25-11-2011
WriteStep=`awk '/nstxout-compressed *=/{print $3}' ${runname}.mdp`
WriteTime=`echo "$WriteStep*$TimeStep" | bc -l`
#
for (( Cycle=FirstCycle ; Cycle <=$EndCycle ; Cycle++ )); do
    # Record simulation time and wall-clock time for the current cycle.
    # The existing debug message and timing expressions remain unchanged.
    sim_time=`echo "$EffectiveSteps*$TimeStep*($Cycle-1)+$WriteTime+($StartTime*1000)" | bc -l`
    message W "debug time  $sim_time $EffectiveSteps $TimeStep $Cycle $WriteTime $StartTime "
    echo -e "\nCycle = $Cycle; time = $sim_time ps; Date: `date "+%D %T"`" \
         >> ${blockname}.info
    #
    ######################## PB/MC and protonation state ########################
    all_site_count="$(cphmd_count_nonblank "${CPHMD_ALL_SITES_FILE}")" || {
        cphmd_preserve_failure_diagnostics "${Cycle}"
        exit "${CPHMD_EXIT_OUTPUT_FAILURE}"
    }

    if (( all_site_count > 0 )); then
        if (( ReduceTitration == 1 )); then
            if cphmd_rt_full_refresh_cycle "${Cycle}"; then
                echo -n "PB/MC (All) -        Cycle = $Cycle; Date: `date "+%D %T"` - " \
                    >> ${blockname}.info
                run_PBMC "${CPHMD_ALL_SITES_FILE}" "all-site refresh"
                rc=$?
                if (( rc != 0 )); then
                    cphmd_preserve_failure_diagnostics "${Cycle}"
                    exit "${rc}"
                fi
                cphmd_refresh_reduced_titration_state
                rc=$?
                if (( rc != 0 )); then
                    cphmd_preserve_failure_diagnostics "${Cycle}"
                    exit "${rc}"
                fi
                echo "`date "+%D %T"`" >> ${blockname}.info
            else
                active_site_count="$(cphmd_count_nonblank "${CPHMD_RT_ACTIVE_SITES_FILE}")" || {
                    cphmd_preserve_failure_diagnostics "${Cycle}"
                    exit "${CPHMD_EXIT_OUTPUT_FAILURE}"
                }

                if (( active_site_count > 0 )); then
                    echo -n "PB/MC (RT ${active_site_count}/${all_site_count}) - Cycle = $Cycle; Date: `date "+%D %T"` - " \
                        >> ${blockname}.info
                    run_PBMC "${CPHMD_RT_ACTIVE_SITES_FILE}" "reduced active-set"
                    rc=$?
                    if (( rc != 0 )); then
                        cphmd_preserve_failure_diagnostics "${Cycle}"
                        exit "${rc}"
                    fi
                    cphmd_merge_reduced_titration_cycle
                    rc=$?
                    if (( rc != 0 )); then
                        cphmd_preserve_failure_diagnostics "${Cycle}"
                        exit "${rc}"
                    fi
                    echo "`date "+%D %T"`" >> ${blockname}.info
                else
                    echo "PB/MC (RT 0/${all_site_count}; fixed-state reuse) - Cycle = $Cycle; Date: `date "+%D %T"`" \
                        >> ${blockname}.info
                    message W \
                        "Cycle ${Cycle}: active reduced-titration site set is empty; reusing validated fixed-state templates without running PB/MC."
                    cphmd_materialize_fixed_rt_cycle
                    rc=$?
                    if (( rc != 0 )); then
                        cphmd_preserve_failure_diagnostics "${Cycle}"
                        exit "${rc}"
                    fi
                fi
            fi
        else
            echo -n "PB/MC -        Cycle = $Cycle; Date: `date "+%D %T"` - " \
                >> ${blockname}.info
            run_PBMC "${CPHMD_ALL_SITES_FILE}" "all-site"
            rc=$?
            if (( rc != 0 )); then
                cphmd_preserve_failure_diagnostics "${Cycle}"
                exit "${rc}"
            fi
            cphmd_materialize_nonrt_cycle
            rc=$?
            if (( rc != 0 )); then
                cphmd_preserve_failure_diagnostics "${Cycle}"
                exit "${rc}"
            fi
            echo "`date "+%D %T"`" >> ${blockname}.info
        fi

        cphmd_record_current_fractions
        rc=$?
        if (( rc != 0 )); then
            cphmd_preserve_failure_diagnostics "${Cycle}"
            exit "${rc}"
        fi

        update_topology
        rc=$?
        if (( rc != 0 )); then
            cphmd_preserve_failure_diagnostics "${Cycle}"
            exit "${rc}"
        fi
    else
        message W "All-site definition ${CPHMD_ALL_SITES_FILE} is empty. PB/MC is not performed in cycle ${Cycle}."
        echo "" >> TMP_CpHMD.occ
        echo "" >> TMP_CpHMD.mocc
        mv TMP_processed.top TMP_CpHMD.top
    fi

    ############################ Molecular dynamics ############################
    # Propagate command failures and missing-output errors immediately.
    # Continuing with stale coordinates would invalidate both the structural
    # and protonation-state trajectories.
    if [ $RelaxSteps != 0 ]; then
        echo -n "MD relax     - Cycle = $Cycle; Date: `date "+%D %T"` - " \
            >> ${blockname}.info
        run_relaxation >> ${blockname}_MD.log 2>&1
        rc=$?
        if (( rc != 0 )); then
            cphmd_preserve_failure_diagnostics "${Cycle}"
            exit "${rc}"
        fi
        echo "`date "+%D %T"`" >> ${blockname}.info
    else
        mv TMP_effective.gro TMP_relax.gro
    fi

    echo -n "MD effective - Cycle = $Cycle; Date: `date "+%D %T"` - " \
        >> ${blockname}.info
    run_dynamics effective relax >> ${blockname}_MD.log 2>&1
    rc=$?
    if (( rc != 0 )); then
        cphmd_preserve_failure_diagnostics "${Cycle}"
        exit "${rc}"
    fi
    echo "`date "+%D %T"`" >> ${blockname}.info

    data_append
    rc=$?
    if (( rc != 0 )); then
        cphmd_preserve_failure_diagnostics "${Cycle}"
        exit "${rc}"
    fi

    # Write one complete atomic cycle checkpoint. It remains non-finalized
    # until segment-level binary validation and finalization succeed.
    cphmd_write_checkpoint "${Cycle}"
    rc=$?
    if (( rc != 0 )); then
        cphmd_preserve_failure_diagnostics "${Cycle}"
        exit "${rc}"
    fi

    if (( CPHMD_MAX_SECONDS > 0 && Cycle < EndCycle )); then
        now_epoch=$(date +%s)
        elapsed=$((now_epoch - CPHMD_WALL_START_EPOCH))

        if (( elapsed >= CPHMD_MAX_SECONDS )); then
            cphmd_finalize_segment "${Cycle}"
            rc=$?
            if (( rc != 0 )); then
                cphmd_preserve_failure_diagnostics "${Cycle}"
                exit "${rc}"
            fi
            message W "Reached validated CpHMD cycle-boundary walltime guard after cycle ${Cycle}/${EndCycle}; exiting cleanly for scheduler resubmission."
            exit "${CPHMD_EXIT_CLEAN_RESUBMIT}"
        fi
    fi
done
###############################################################################
# 11. Finalize normal completion
###############################################################################
echo -e "\nEnd time:     `date`" >> ${blockname}.info
final_log_base="../${CPHMD_LOG_DIR}/${blockname}_cycles${CPHMD_SEGMENT_START_CYCLE}-${EndCycle}"
cphmd_copy_atomic "${blockname}.info" "${final_log_base}.info"

# The final cycle was checkpointed inside the loop. Validate and finalize the
# last scheduler segment once, including optional compression. restart/
# remains the authoritative endpoint and no duplicate *.final.* files are made.
cphmd_finalize_segment "${EndCycle}"
rc=$?
if (( rc != 0 )); then
    cphmd_preserve_failure_diagnostics "${EndCycle}"
    exit "${rc}"
fi

# Preserve historical PLUMED timestamp post-processing when the selected
# COLVAR file exists.
if [[ -n ${colvar_name:-} && -f ${colvar_name} ]]; then
    sed -i '/^ 20.0/d' ${colvar_name}
fi

#
# Clean temporary inner-run files after scientific output has been committed.

clean_up

# Checkpoint/finalization helpers have already copied scientific output to the
# organized parent scratch directories.
# The scheduler wrapper may now synchronize finalized content to persistent
# storage.

cd ../
sleep 3
rm -rf ./CpHMD-run_$$

# Normal completion.
exit 0
