# CpHMD settings and scheduler reference

## Explicit user settings

CpHMD v0.7.1 does not source a fallback scientific-settings file. It sources one
user settings file and checks that ordinary execution, simulation, system,
PB/MC, reduced-titration and input choices are explicitly exported there.

Missing declarations and unedited `CHANGE_ME` placeholders fail before GROMACS
or PB/MC work begins.

The validation code is:

```text
/CpHMD/scripts/settings_contract.sh
```

It is not a template and is never present under `/Templates`.

## Application-owned runtime configuration

Container executable/data paths, CPU/CUDA preflight policy, automatic `mdrun`
construction, and validated-segment retention are application behavior rather
than hidden scientific choices. They have internal values in
`settings_contract.sh`; advanced users may override them deliberately.

## Basic profiles

The soluble-protein starting profiles are:

- `CpHMD-basic-G54a7pH.settings`;
- `CpHMD-basic-CHARMM36pH.settings`;
- `CpHMD-basic-Amber14SBpH.settings`.

`CpHMD-basic.settings` is a byte-for-byte G54a7pH profile.

Required edits use `CHANGE_ME` for `SysName`, `SimTime`, `pH`, `TOPin`,
`GROin`, and `NDXin`. Every other ordinary choice remains visible for review.

## Reduced titration

The basic profiles explicitly contain:

```bash
export ReduceTitration=1
export RTThreshold=0.01
export RTInterval=20
export write_states="n"
```

Users can select the all-site protocol explicitly:

```bash
export ReduceTitration=0
```

There is no hidden reduced-titration fallback.

## Force-field-dependent MDP choices

| Profile | LJ/Coulomb cutoff | LJ treatment | Constraints |
|---|---:|---|---|
| G54a7pH | 1.4 nm | plain cut-off | all bonds |
| CHARMM36pH | 1.2 nm | force switch from 1.0 nm | H bonds |
| Amber14SBpH | 1.0 nm | potential shift plus `EnerPres` | H bonds |

These are reviewed starting points, not universal protocols. Membrane pressure
coupling, temperature groups, restraints and enhanced sampling remain
system-dependent.

## Custom ST definitions

`StDIR` is an advanced override. When unset, CpHMD uses
`/STs/St-${ffID}`. A custom value can select state/tautomer files prepared for
alternative Lennard-Jones radii, provided the ST set remains consistent with the
force field and Delphi databases.

## Explicit empty/disabled choices

`ionicstrMD=""` means the MD MDP inherits `ionicstr`.

`PosRe=""` means no production position-restraint file.

`plumed=0` disables PLUMED. When `plumed=1`, the PLUMED settings are required.
