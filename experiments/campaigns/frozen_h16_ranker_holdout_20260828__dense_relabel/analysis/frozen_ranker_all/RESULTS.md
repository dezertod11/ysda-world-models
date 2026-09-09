# Frozen H16 candidate ranker holdout

- Frozen model: `factor_h16_dense_ridge_v1` (`086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb`).
- Holdout: **240 states**, **69 independent task/init groups**.
- Formal gate: **PASS**.
- Primary delta is group-macro regret of `frozen_factor_ridge - cosmos_value`; negative is better.

## Regret

| factor      | method              |   snapshots |   independent_groups |   mean_selected_utility |   mean_regret |   top1_accuracy |   group_macro_mean_regret |
|:------------|:--------------------|------------:|---------------------:|------------------------:|--------------:|----------------:|--------------------------:|
| Environment | cosmos_value        |          80 |                   23 |              0.037026   |    0.0121131  |          0.1875 |                0.0113398  |
| Environment | frozen_factor_ridge |          80 |                   23 |              0.0391232  |    0.0100159  |          0.375  |                0.00962457 |
| Environment | oracle              |          80 |                   23 |              0.0491391  |    0          |          1      |                0          |
| Environment | random              |          80 |                   23 |              0.0354249  |    0.0137141  |          0.175  |                0.0130151  |
| Object      | cosmos_value        |          80 |                   26 |              0.463748   |    0.0025641  |          0.3375 |                0.00243615 |
| Object      | frozen_factor_ridge |          80 |                   26 |              0.46439    |    0.00192288 |          0.3375 |                0.00192066 |
| Object      | oracle              |          80 |                   26 |              0.466312   |    0          |          1      |                0          |
| Object      | random              |          80 |                   26 |              0.455632   |    0.0106803  |          0.1625 |                0.0105024  |
| Position    | cosmos_value        |          80 |                   20 |             -0.00620505 |    0.013223   |          0.1125 |                0.013223   |
| Position    | frozen_factor_ridge |          80 |                   20 |              0.0025998  |    0.00441813 |          0.2875 |                0.00441813 |
| Position    | oracle              |          80 |                   20 |              0.00701793 |    0          |          1      |                0          |
| Position    | random              |          80 |                   20 |             -0.00202328 |    0.00904121 |          0.2125 |                0.00904121 |

## Grouped bootstrap

| factor      |   independent_groups |   regret_delta_frozen_minus_cosmos |   ci95_lower |   ci95_upper |   probability_delta_below_zero |
|:------------|---------------------:|-----------------------------------:|-------------:|-------------:|-------------------------------:|
| Environment |                   23 |                       -0.00171519  |  -0.00364382 |  0.000426683 |                         0.9454 |
| Object      |                   26 |                       -0.000515483 |  -0.00179086 |  0.000725043 |                         0.7812 |
| Position    |                   20 |                       -0.00880485  |  -0.0140096  | -0.00469038  |                         1      |
| All         |                   69 |                       -0.00367851  |  -0.00555627 | -0.00211008  |                         1      |

## Gate

```json
{
  "passed": true,
  "required_groups_per_factor": 20,
  "enough_independent_groups": true,
  "every_factor_regret_improves": true,
  "macro_ci95_upper_below_zero": true,
  "no_train_holdout_group_overlap": true,
  "overlapping_groups": []
}
```

The model was not refit on holdout data. Phase is reported only for analysis and was not used to select states.
