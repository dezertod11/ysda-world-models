# Consensus-medoid campaign result

Campaign: `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/consensus_medoid_pre_p5_20260907__architecture_smoke`

## Strategy-level SR

| planning_strategy        |   episodes |   successes |   success_rate |   mean_final_t |   mean_queries |
|:-------------------------|-----------:|------------:|---------------:|---------------:|---------------:|
| cosmos_consensus_guarded |          1 |           0 |         0.0000 |       280.0000 |        56.0000 |
| keystone_cluster_medoid  |          1 |           0 |         0.0000 |       280.0000 |        56.0000 |
| max_value                |          1 |           0 |         0.0000 |       280.0000 |        56.0000 |

## Exact paired effects

| reference                | method                  |   paired_episodes |   reference_success_rate |   method_success_rate |   delta_success_rate |   ci95_low |   ci95_high |   rescues |   harms |   mcnemar_exact_p |
|:-------------------------|:------------------------|------------------:|-------------------------:|----------------------:|---------------------:|-----------:|------------:|----------:|--------:|------------------:|
| cosmos_consensus_guarded | keystone_cluster_medoid |                 1 |                   0.0000 |                0.0000 |               0.0000 |     0.0000 |      0.0000 |         0 |       0 |            1.0000 |
| cosmos_consensus_guarded | max_value               |                 1 |                   0.0000 |                0.0000 |               0.0000 |     0.0000 |      0.0000 |         0 |       0 |            1.0000 |
| keystone_cluster_medoid  | max_value               |                 1 |                   0.0000 |                0.0000 |               0.0000 |     0.0000 |      0.0000 |         0 |       0 |            1.0000 |

## Query-level behavior

| planning_strategy        |   query_rows |   selected_not_max_value_rate |   guarded_switch_rate |
|:-------------------------|-------------:|------------------------------:|----------------------:|
| cosmos_consensus_guarded |           56 |                        0.5357 |                0.5357 |
| keystone_cluster_medoid  |           56 |                        0.7321 |                0.0000 |
| max_value                |           56 |                        0.0000 |                0.0000 |

The attached-file SR values are prior claims and are not merged into this table.
