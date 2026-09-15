# Grounding diagnostic

Exploratory privileged diagnostic, not a deployable method or independent holdout.
Geometry 32/32; committed outcomes 128/128; matched cases 32.

| Cohort | Arm | Success | SR |
|---|---|---:|---:|
| replication | rgb_replay | 10/16 | 62.50% |
| replication | oracle_xy_fixed_gate | 11/16 | 68.75% |
| replication | oracle_xyz_fixed_gate | 10/16 | 62.50% |
| replication | oracle_xyz_physical_gate | 12/16 | 75.00% |
| transfer | rgb_replay | 0/16 | 0.00% |
| transfer | oracle_xy_fixed_gate | 3/16 | 18.75% |
| transfer | oracle_xyz_fixed_gate | 2/16 | 12.50% |
| transfer | oracle_xyz_physical_gate | 2/16 | 12.50% |

Fixed-gate oracle arms retain initial and post-retreat RGB gates, with an explicit physical waypoint safety veto.
Physical-gate oracle changes confidence/workspace eligibility as well as the waypoint; separate coverage diagnostic.
See geometry.csv for pixel detection, backprojection, plane-height and target visibility measurements.
Shadow comparisons check action equality without executed interventions. Thresholds are not calibrated.

[Videos](videos.html)
