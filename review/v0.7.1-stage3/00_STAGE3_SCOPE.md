# CpHMD v0.7.1 Stage 3 explicit-settings revision

Stage 3 removes the fallback scientific-settings file and introduces a fail-fast
explicit user-settings contract.

Implemented:

- remove `CpHMD/CpHMD-default.settings`;
- source only the user settings file;
- require ordinary settings to be explicitly exported;
- reject unedited `CHANGE_ME` placeholders;
- keep only application-owned paths, safeguards and output policy internal;
- retain force-field-specific basic profiles;
- recommend `ReduceTitration=1` and `RTInterval=20`;
- keep `ReduceTitration=0` as an explicit user choice.

Stage 4 will add force-field-specific advanced profiles and custom `StDIR`
examples. Stage 5 will add compact RT events to segment `.info` files.
