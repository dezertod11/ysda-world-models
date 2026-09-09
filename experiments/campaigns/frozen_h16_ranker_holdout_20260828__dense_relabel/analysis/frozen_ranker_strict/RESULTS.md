# Frozen H16 candidate ranker holdout

- Frozen model: `factor_h16_dense_ridge_v1` (`086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb`).
- Holdout: **230 states**, **69 independent task/init groups**.
- Formal gate: **PASS**.
- Primary delta is group-macro regret of `frozen_factor_ridge - cosmos_value`; negative is better.

## Regret

| factor      | method              |   snapshots |   independent_groups |   mean_selected_utility |   mean_regret |   top1_accuracy |   group_macro_mean_regret |
|:------------|:--------------------|------------:|---------------------:|------------------------:|--------------:|----------------:|--------------------------:|
| Environment | cosmos_value        |          75 |                   23 |              0.0376626  |    0.0122347  |        0.186667 |                0.0111888  |
| Environment | frozen_factor_ridge |          75 |                   23 |              0.0397689  |    0.0101283  |        0.373333 |                0.00927116 |
| Environment | oracle              |          75 |                   23 |              0.0498972  |    0          |        1        |                0          |
| Environment | random              |          75 |                   23 |              0.0362975  |    0.0135997  |        0.16     |                0.0122927  |
| Object      | cosmos_value        |          75 |                   26 |              0.4811     |    0.00268946 |        0.333333 |                0.0025815  |
| Object      | frozen_factor_ridge |          75 |                   26 |              0.482118   |    0.00167086 |        0.333333 |                0.0016831  |
| Object      | oracle              |          75 |                   26 |              0.483789   |    0          |        1        |                0          |
| Object      | random              |          75 |                   26 |              0.472817   |    0.0109727  |        0.16     |                0.0110304  |
| Position    | cosmos_value        |          80 |                   20 |             -0.00620505 |    0.013223   |        0.1125   |                0.013223   |
| Position    | frozen_factor_ridge |          80 |                   20 |              0.0025998  |    0.00441813 |        0.2875   |                0.00441813 |
| Position    | oracle              |          80 |                   20 |              0.00701793 |    0          |        1        |                0          |
| Position    | random              |          80 |                   20 |             -0.00202328 |    0.00904121 |        0.2125   |                0.00904121 |

## Grouped bootstrap

| factor      |   independent_groups |   regret_delta_frozen_minus_cosmos |   ci95_lower |   ci95_upper |   probability_delta_below_zero |
|:------------|---------------------:|-----------------------------------:|-------------:|-------------:|-------------------------------:|
| Environment |                   23 |                       -0.00191766  |  -0.00392815 |  0.000301027 |                         0.957  |
| Object      |                   26 |                       -0.000898402 |  -0.00224871 |  0.00044283  |                         0.9056 |
| Position    |                   20 |                       -0.00880485  |  -0.0140096  | -0.00469038  |                         1      |
| All         |                   69 |                       -0.00387364  |  -0.00576824 | -0.00229842  |                         1      |

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
