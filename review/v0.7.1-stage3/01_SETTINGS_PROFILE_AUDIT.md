# Stage 3 explicit-settings ownership audit

| Category | Owner | Behavior |
|---|---|---|
| Scientific/system settings | user settings file | explicit declaration required |
| MDP/fixgro/PLUMED blocks | user settings file | extracted from that file only |
| Executable/data paths | application | internal value; advanced override allowed |
| GROMACS/GPU safeguards | application | safe internal policy |
| Segment validation/retention | application | internal output policy |
| Fallback scientific settings | none | removed |
| `/Templates` | user templates only | no internal fallback file |

`ionicstrMD` and `PosRe` must be declared but may be empty. Unedited basic
profiles are rejected through `CHANGE_ME` placeholders.
