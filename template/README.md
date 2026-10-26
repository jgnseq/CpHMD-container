# CpHMD settings templates

`/Templates` contains only user-facing settings files. CpHMD does not ship or
source a fallback scientific-settings template.

The basic profiles explicitly export ordinary simulation, system, PB/MC,
reduced-titration and input choices. `CHANGE_ME` placeholders force users to
edit the run identity, simulation time, pH and required input paths.

Every basic profile enables reduced titration with `RTInterval=20`. Set
`ReduceTitration=0` to use all configured sites every cycle.

Application-owned paths, fail-fast safeguards and output-retention behavior are
implemented in `/CpHMD/scripts/settings_contract.sh`. That file is program code,
not a settings template, and is never copied to `/Templates`.

Force-field-specific advanced profiles and custom `StDIR` examples are added in
Stage 4.
