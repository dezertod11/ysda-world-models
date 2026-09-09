# Pre-P5 consensus-medoid run card

## Итог запуска

Завершён 7 сентября 2026 в 14:53:47 MSK, `status=completed`, `exit_code=0`.
Все 12/12 jobs завершены: 180 development и 6 smoke rollouts.
Результаты скачаны локально; анализ, графики и ограничения:
[CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md](CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md).
Текущие selectors не прошли development gate; повторять завершённый запуск
для просмотра результатов не требуется.

## Автономный запуск

```bash
cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
nohup env CONSENSUS_GPUS=2,3,4 \
  bash scripts/run_consensus_medoid_pre_p5_sequence.sh \
  > experiments/campaigns/consensus_medoid_pre_p5_20260907/launcher.log \
  2>&1 </dev/null &
```

GPU 0 и 1 скрипт отклоняет. Он ждёт две последовательные проверки свободной
памяти на физических GPU 2-4, не завершает и не перемещает чужие процессы,
возобновляет уже завершённые campaign jobs и работает после закрытия SSH.

## Последовательность

1. server-side unit/integration import tests;
2. один rollout каждого exact метода;
3. 40 matched rollouts каждого exact метода;
4. анализ paired SR, rescues/harms, McNemar и bootstrap CI;
5. один rollout `max_value` / KeyStone / Cosmos-aware selector при $K=5$;
6. 20 matched development rollouts каждого K5 метода;
7. такой же paired анализ Stage B.

Stage B начинается только после успешного завершения и анализа Stage A.

## Статус из WSL

```bash
./scripts/mlspace_experiment_status.sh \
  experiments/campaigns/consensus_medoid_pre_p5_20260907
```

Или напрямую:

```bash
ssh mlspace-sr006 \
  "cat /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/consensus_medoid_pre_p5_20260907/sequence_status.json"
```

```bash
ssh mlspace-sr006 \
  "tail -n 80 /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/consensus_medoid_pre_p5_20260907/launcher.log"
```

## Результаты

Exact stage:

`experiments/campaigns/consensus_medoid_pre_p5_20260907__exact_development/consensus_analysis/RESULTS.md`

Architecture-aware stage:

`experiments/campaigns/consensus_medoid_pre_p5_20260907__architecture_development/consensus_analysis/RESULTS.md`

Primary raw traces остаются в `runs/`; каждый query содержит полный candidate
pool, structured distance matrix, component costs, cluster labels, proposed
candidate, switch/fallback reason и joint consensus costs.
