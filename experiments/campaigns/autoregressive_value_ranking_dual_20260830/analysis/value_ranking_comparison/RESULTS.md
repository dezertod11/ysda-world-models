# Action-conditioned autoregressive value: results

Сравнение выполнено в одном forward lineage для каждого candidate:
action генерируется один раз, затем из того же latent получаются
parallel value и последовательный `action -> future -> value`. Метка
успеха означает terminal success после общей frozen parallel continuation
policy; меняется только способ получения candidate value.

## Validity

- Matched candidates: 80.
- Action-signature max abs difference: 0.000e+00.
- Stored parallel-value alias error: 0.000e+00.
- Matched terminal-outcome agreement: 100.000%.
- Validity gate: **PASS**.
- Candidate-level parallel/AR value Spearman: 0.6212.
- Parallel/AR future-proprio L2 mean / p95: 0.0136 / 0.0224.

## Ranking results

| factor   |   states |   mixed_states |   oracle_success_rate |   parallel_all_state_success_rate |   autoregressive_all_state_success_rate |   parallel_mixed_top1_success_rate |   autoregressive_mixed_top1_success_rate |   mixed_top1_delta_states |   parallel_pairwise_accuracy |   autoregressive_pairwise_accuracy |   switches |   rescues |   harms |   paired_sign_pvalue |   parallel_autoregressive_value_spearman_mean |   future_proprio_l2_mean |
|:---------|---------:|---------------:|----------------------:|----------------------------------:|----------------------------------------:|-----------------------------------:|-----------------------------------------:|--------------------------:|-----------------------------:|-----------------------------------:|-----------:|----------:|--------:|---------------------:|----------------------------------------------:|-------------------------:|
| Object   |        5 |              3 |                   0.8 |                               0.6 |                                     0.6 |                           0.666667 |                                 0.666667 |                         0 |                     0.604167 |                          0.458333  |          3 |         1 |       1 |                    1 |                                      0.338095 |                0.0155492 |
| Position |        5 |              2 |                   0.4 |                               0   |                                     0   |                           0        |                                 0        |                         0 |                     0.166667 |                          0.0833333 |          2 |         0 |       0 |                    1 |                                      0.57619  |                0.0116134 |
| All      |       10 |              5 |                   0.6 |                               0.3 |                                     0.3 |                           0.4      |                                 0.4      |                         0 |                     0.429167 |                          0.308333  |          5 |         1 |       1 |                    1 |                                      0.457143 |                0.0135813 |

Overall preregistered gate: **FAIL**.

## Interpretation

Авторегрессионный value не дал устойчивого paired улучшения.
Следующий приоритет: learned within-state advantage critic на
action-conditioned features, с отдельными development/holdout init.
