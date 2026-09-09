# P3e recovery outcome router: development OOF

- Development gate: **PASS**.
- Cases/cells: **75/15**.
- Validation: leave one complete position x task cell out.
- Features: seven pre-intervention RGB-localization and EEF-relation values.

| cohort | n_cases | workspace_calibrated_sr | router_sr | vs_full_delta | vs_full_rescues | vs_full_harms | selected_baseline | selected_retreat | selected_full |
|---|---|---|---|---|---|---|---|---|---|
| all | 75 | 0.746667 | 0.773333 | 0.0266667 | 2 | 0 | 21 | 2 | 52 |
| replication | 40 | 0.625 | 0.625 | 0 | 0 | 0 | 15 | 0 | 25 |
| novel_cell | 35 | 0.885714 | 0.942857 | 0.0571429 | 2 | 0 | 6 | 2 | 27 |

The router and all hyperparameters are frozen before holdout init 45--49.
