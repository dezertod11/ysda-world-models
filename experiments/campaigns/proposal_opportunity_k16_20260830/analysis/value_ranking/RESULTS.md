# Candidate value-ranking diagnostics

Анализ выполнен только после завершения K16 campaign. Он сравнивает
predicted value с terminal success внутри одного exact-state pool.

## Summary

- Mixed outcome pools: 9/50.
- Failing top-1 при наличии success: 5.
- Top-1 accuracy на mixed pools: 0.444.
- Mean within-state pairwise accuracy: 0.475.
- Median positive misranking margin: 0.000231.
- Maximum positive misranking margin: 0.003808.

## By perturbation and query

| factor      | case_id                          |   query_idx |   states |   heterogeneous_states |   all_candidates_fail |   top1_success_on_heterogeneous |   within_state_pairwise_accuracy |   misranked_rescues |   misranking_margin_mean |   misranking_margin_max |   k4_to_k8_oracle_gains |   k8_to_k16_oracle_gains |   k4_to_k8_greedy_harms |   k4_to_k8_greedy_rescues |   k8_to_k16_greedy_harms |   k8_to_k16_greedy_rescues |
|:------------|:---------------------------------|------------:|---------:|-----------------------:|----------------------:|--------------------------------:|---------------------------------:|--------------------:|-------------------------:|------------------------:|------------------------:|-------------------------:|------------------------:|--------------------------:|-------------------------:|---------------------------:|
| Environment | proposal_k16_environment_task0   |           0 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |
| Environment | proposal_k16_environment_task0   |           3 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |
| Environment | proposal_k16_environment_task2   |           0 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |
| Environment | proposal_k16_environment_task2   |           3 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |
| Object      | proposal_k16_object_task0        |           0 |        5 |                      4 |                     1 |                        0.75     |                         0.49793  |                   1 |              0.00285777  |             0.00285777  |                       0 |                        0 |                       0 |                         1 |                        0 |                          1 |
| Object      | proposal_k16_object_task0        |           3 |        5 |                      3 |                     1 |                        0.333333 |                         0.423671 |                   2 |              0.000172824 |             0.000230521 |                       0 |                        0 |                       1 |                         0 |                        1 |                          1 |
| Position    | proposal_k16_position_x0p3_task0 |           0 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |
| Position    | proposal_k16_position_x0p3_task0 |           3 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |
| Position    | proposal_k16_position_y0p3_task0 |           0 |        5 |                      2 |                     3 |                        0        |                         0.508333 |                   2 |              0.00198723  |             0.00380799  |                       1 |                        0 |                       1 |                         0 |                        0 |                          0 |
| Position    | proposal_k16_position_y0p3_task0 |           3 |        5 |                      0 |                     5 |                      nan        |                       nan        |                   0 |            nan           |           nan           |                       0 |                        0 |                       0 |                         0 |                        0 |                          0 |

## Interpretation

Ненулевой oracle gap вызван value misranking, а не отсутствием хорошего
action во всех mixed pools. Небольшой абсолютный value margin делает
жадный argmax чувствительным к добавлению stochastic proposals. Поэтому
следующий evaluator должен быть action-conditioned и calibrated по
within-state advantage; увеличение K сверх точки насыщения не является
самостоятельным решением.
