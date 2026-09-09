# Consensus-medoid campaign result

Campaign: `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/consensus_medoid_pre_p5_20260907__exact_development`

## Strategy-level SR

| planning_strategy     |   episodes |   successes |   success_rate |   mean_final_t |   mean_queries |
|:----------------------|-----------:|------------:|---------------:|---------------:|---------------:|
| first                 |         40 |          12 |         0.3000 |       253.3250 |        50.8000 |
| max_value             |         40 |           8 |         0.2000 |       263.1250 |        52.7250 |
| consensus_medoid_only |         40 |           7 |         0.1750 |       257.7500 |        51.6000 |

## Exact paired effects

| reference             | method    |   paired_episodes |   reference_success_rate |   method_success_rate |   delta_success_rate |   ci95_low |   ci95_high |   rescues |   harms |   mcnemar_exact_p |
|:----------------------|:----------|------------------:|-------------------------:|----------------------:|---------------------:|-----------:|------------:|----------:|--------:|------------------:|
| consensus_medoid_only | first     |                40 |                   0.1750 |                0.3000 |               0.1250 |    -0.0500 |      0.3000 |         9 |       4 |            0.2668 |
| consensus_medoid_only | max_value |                40 |                   0.1750 |                0.2000 |               0.0250 |    -0.1250 |      0.1750 |         6 |       5 |            1.0000 |
| first                 | max_value |                40 |                   0.3000 |                0.2000 |              -0.1000 |    -0.2500 |      0.0500 |         3 |       7 |            0.3438 |

## Query-level behavior

| planning_strategy     |   query_rows |   selected_not_max_value_rate |   guarded_switch_rate |
|:----------------------|-------------:|------------------------------:|----------------------:|
| consensus_medoid_only |         2064 |                        0.7006 |                0.0000 |
| first                 |         2032 |                        0.0000 |                0.0000 |
| max_value             |         2109 |                        0.0000 |                0.0000 |

The attached-file SR values are prior claims and are not merged into this table.
