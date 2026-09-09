# Consensus-medoid campaign result

Campaign: `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/consensus_medoid_pre_p5_20260907__architecture_development`

## Strategy-level SR

| planning_strategy        |   episodes |   successes |   success_rate |   mean_final_t |   mean_queries |
|:-------------------------|-----------:|------------:|---------------:|---------------:|---------------:|
| cosmos_consensus_guarded |         20 |           6 |         0.3000 |       251.7500 |        50.4500 |
| max_value                |         20 |           5 |         0.2500 |       249.0000 |        49.9000 |
| keystone_cluster_medoid  |         20 |           3 |         0.1500 |       268.5000 |        53.7500 |

## Exact paired effects

| reference                | method                  |   paired_episodes |   reference_success_rate |   method_success_rate |   delta_success_rate |   ci95_low |   ci95_high |   rescues |   harms |   mcnemar_exact_p |
|:-------------------------|:------------------------|------------------:|-------------------------:|----------------------:|---------------------:|-----------:|------------:|----------:|--------:|------------------:|
| cosmos_consensus_guarded | keystone_cluster_medoid |                20 |                   0.3000 |                0.1500 |              -0.1500 |    -0.4000 |      0.1000 |         2 |       5 |            0.4531 |
| cosmos_consensus_guarded | max_value               |                20 |                   0.3000 |                0.2500 |              -0.0500 |    -0.2500 |      0.1500 |         2 |       3 |            1.0000 |
| keystone_cluster_medoid  | max_value               |                20 |                   0.1500 |                0.2500 |               0.1000 |    -0.1000 |      0.3000 |         3 |       1 |            0.6250 |

## Query-level behavior

| planning_strategy        |   query_rows |   selected_not_max_value_rate |   guarded_switch_rate |
|:-------------------------|-------------:|------------------------------:|----------------------:|
| cosmos_consensus_guarded |         1009 |                        0.5689 |                0.5689 |
| keystone_cluster_medoid  |         1075 |                        0.8298 |                0.0000 |
| max_value                |          998 |                        0.0000 |                0.0000 |

The attached-file SR values are prior claims and are not merged into this table.
