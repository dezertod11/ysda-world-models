# Consensus-medoid campaign result

Campaign: `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/consensus_medoid_pre_p5_20260907__exact_smoke`

## Strategy-level SR

| planning_strategy     |   episodes |   successes |   success_rate |   mean_final_t |   mean_queries |
|:----------------------|-----------:|------------:|---------------:|---------------:|---------------:|
| consensus_medoid_only |          1 |           1 |         1.0000 |       123.0000 |        25.0000 |
| first                 |          1 |           0 |         0.0000 |       280.0000 |        56.0000 |
| max_value             |          1 |           0 |         0.0000 |       280.0000 |        56.0000 |

## Exact paired effects

| reference             | method    |   paired_episodes |   reference_success_rate |   method_success_rate |   delta_success_rate |   ci95_low |   ci95_high |   rescues |   harms |   mcnemar_exact_p |
|:----------------------|:----------|------------------:|-------------------------:|----------------------:|---------------------:|-----------:|------------:|----------:|--------:|------------------:|
| consensus_medoid_only | first     |                 1 |                   1.0000 |                0.0000 |              -1.0000 |    -1.0000 |     -1.0000 |         0 |       1 |            1.0000 |
| consensus_medoid_only | max_value |                 1 |                   1.0000 |                0.0000 |              -1.0000 |    -1.0000 |     -1.0000 |         0 |       1 |            1.0000 |
| first                 | max_value |                 1 |                   0.0000 |                0.0000 |               0.0000 |     0.0000 |      0.0000 |         0 |       0 |            1.0000 |

## Query-level behavior

| planning_strategy     |   query_rows |   selected_not_max_value_rate |   guarded_switch_rate |
|:----------------------|-------------:|------------------------------:|----------------------:|
| consensus_medoid_only |           25 |                        0.6800 |                0.0000 |
| first                 |           56 |                        0.0000 |                0.0000 |
| max_value             |           56 |                        0.0000 |                0.0000 |

The attached-file SR values are prior claims and are not merged into this table.
