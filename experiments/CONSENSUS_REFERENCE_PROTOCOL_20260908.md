# ICLR: проверка consensus на общих кандидатах и matched baseline

## Цель и статус

8 сентября запущен следующий этап после разбора
[trajectory-consensus](TRAJECTORY_CONSENSUS_ICLR_ASSESSMENT_20260908.md).
Цель: отделить качество ранжирования от качества самого набора действий
и сравнить OSC-medoid с ближайшими методами при одинаковом бюджете.

**Выполнено:** CPU-анализ 194 проверенных K4-наборов с уже измеренными
terminal outcomes; 12 фиксированных методов/контролей, включая ablations.
**Запущена автономная очередь:** `consensus_references_20260908`,
PID при старте **1549270**, 8 сентября **14:32 MSK**. Начальная стадия
`waiting_for_compact`: новые GPU-rollout начнутся только после успешного
окончания сбора и анализа `trajectory_consensus_20260908_compact`.

Основной compact600 не изменяется и не перезапускается. После ожидания:
**3 smoke -> 600 дополнительных rollout -> integrity checks -> общий
отчёт по 1200 rollout и шести методам**. Smoke проверяет интеграцию,
не используется для выбора winner или оценки эффективности.

## 1. Проверка на общих K4-наборах

Источник: `p4b_residual_risk_20260907/terminal_holdout_analysis/candidate_scores.parquet`
и 200 сохранённых NPZ. Данные уже использовались в прошлых исследованиях,
поэтому это **exploratory analysis**, не новый holdout.

Проверки: ровно четыре candidate_idx 0-3, доступные terminal labels, единый
snapshot/sidecar, одинаковые H16/parallel параметры, совпадение values в
таблице и NPZ. Необходим сохранённый main/open replay audit с максимальной
ошибкой не более 1e-9. Отсутствующая проверка не считается успешной.
По replay исключены 6 из 200 наборов; остаются **194 набора, 776 ветвей**.

Selectors получают только generated actions и predicted values. Terminal
outcomes и ошибки предсказания после выполнения не передаются selector.
После выбранного первого chunk исход определяется ранее выполненной
веткой с исходной continuation policy. Это не новый эпизод, в котором
проверяемый selector используется во всех последующих queries.

Контроли: max-value, first-K4, точное математическое ожидание uniform random,
OSC medoid/density, raw medoid, KeyStone-style, KDPE endpoint; ablations
без integration, rotation, gripper и с одинаковым весом всех t.
Для uniform random используем среднее четырёх реально измеренных исходов,
а не ещё один случайно выбранный seed. McNemar для дробного контроля не считаем.

Пусть $Y_i$ есть terminal success ветки i, а $i_V$ и $i_M$ выбираются по
value и medoid. Диагностика доступного улучшения и ошибки выбора:

$$
O(s)=\max_iY_i-Y_{i_V},\qquad R_M(s)=\max_iY_i-Y_{i_M}.
$$

Отдельно считаем all-fail / mixed / all-success pools, rescue/harm,
macro-SR по факторам и paired task/init-cluster bootstrap CI.
Within-pool concordance сравнивает score успешного и неуспешного кандидата
только **внутри одного pool**, с весом 0.5 для одинаковых scores.
Протокол не проверяет универсальную необратимость состояния: all-fail
означает отсутствие успеха именно в этих четырёх измеренных ветках.

Результаты: [русский разбор](CONSENSUS_COMMON_POOL_RESULTS_20260908.md),
[полный отчёт](campaigns/consensus_common_pool_20260908/analysis/RESULTS.md).

## 2. Дополнительные closed-loop методы

| Метод | Runtime strategy | Что фиксируем |
|---|---|---|
| Raw-action medoid | `trajectory_raw_medoid` | L2 flattened native H16 chunks, global medoid, value tie-break как у OSC medoid |
| KeyStone-style | `keystone_cluster_medoid` | Существующий guard tau=0.3, C=2, до 10 k-means iterations, RNG seed=0, actual sampled medoid |
| KDPE endpoint adaptation | `trajectory_kdpe_endpoint` | Gaussian manifold-aware kernel на induced OSC endpoint, фиксированные bandwidths |

Ни один метод не отбирается по результату CPU-анализа: запускаются все три.
Объём и протокол совпадают с compact, гиперпараметры medoid не меняются:

| Фактор Object-suite LIBERO-PRO | Задачи | Init | На новый метод | На 3 новых метода |
|---|---|---|---:|---:|
| Object | 0-9 | 2-6 | 50 | 150 |
| Environment | 0-9 | 2-6 | 50 | 150 |
| Position x/y 0.1-0.5, все 10 уровней | 0-9 | 1 | 100 | 300 |
| Итого | | | 200 | 600 |

Rollout seeds копируются из соответствующих compact max-value jobs,
без новой перенумерации init. Для каждого query K=4, Hgenerated=Hexecuted=16,
5 denoising steps, 280 action budget, prediction_mode=parallel. Объектные
assets, environment root/seed и checkpoints остаются прежними. Это не
воспроизведение авторского autoregressive Cosmos planning.

### KDPE: что совпадает со статьёй и что адаптировано

Используем Gaussian kernel из Eq. 5 и bandwidths из Table 4
[KDPE, CoRL 2025](https://arxiv.org/html/2508.10511v2):

$$
\log k_{ij}=C-\frac12\left[
\frac{\lVert p_i-p_j\rVert^2}{0.05^2}
+\frac{\theta(R_j^\top R_i)^2}{0.25^2}
+\frac{(g_i-g_j)^2}{1.0^2}\right],\qquad
i^*=\arg\max_i\sum_j k_{ij}.
$$

В статье используются pose actions; у Cosmos приращения OSC, поэтому
$p_i,R_i$ берём из накопленного command descriptor на t=16, а $g_i$ есть
бинарная команда захвата. Это не measured future pose и не физическая
симуляция. В статье N=100 и execution horizon=8, здесь K4/H16 намеренно
согласованы с нашим тестом. По одному такому сравнению нельзя отвергать
KDPE вообще. Нормировочная константа и одинаковый self-kernel не меняют
argmax; в коде off-diagonal density вычисляется через logsumexp для устойчивости.

Для [KeyStone](https://arxiv.org/html/2605.08638v1) используется уже имеющаяся
реализация selector, а не заявляется воспроизведение всей инфраструктуры
shared-context batching и опубликованной latency. Raw medoid даёт контроль
новизны самой OSC-геометрии при равном sampling budget.

## 3. Заморозка, безопасность запуска и анализ

В `consensus_references_20260908/freeze.json` сохранены методы, SHA compact
config, исходного source manifest, нового geometry module и orchestration.
Runtime скопирован из старого immutable snapshot; заменён только geometry
module с дополнительными стратегиями. На сервере проверено побитовое
совпадение прежних distances/scores/choices на 100 pools x 4 старых selector.
Четыре старых стратегии остаются без изменения поведения.

Первая подготовительная конфигурация использовала unsupported название
experiment_split. Это обнаружено **до запуска**; она сохранена в
`consensus_references_20260908__preflight_invalid_split`. В действующей
конфигурации используются поддерживаемые `screen`/`holdout`; ни одного
rollout со старой подготовительной конфигурацией не запускалось.

Новая очередь использует только свободные **GPU 3-7**, по одному worker на
карту. Занятые карты ждут; чужие процессы не завершаются. На момент проверки
GPU 4-7 заняты другим проектом, поэтому нельзя обещать расчёт на пяти картах
или переносить прежний ETA без поправки на доступность ресурсов.

Монитор обновлён: до появления manifest показывает `WAITING`, а для общей
очереди считает ETA по числу фактически работающих workers и последним
20 завершённым новым jobs. Перенесённые эпизоды не входят в оценку скорости.
При отсутствии активного worker ETA не выдумывается. На последнем срезе
compact продолжал работать: **418/600**, оценка около **5.5 часа** при
сохранении текущей доступности GPU. Это не срок следующей reference-кампании.

Проверки до запуска: 86 серверных тестов основных модулей прошли; после
уточнения монитора отдельно проверены его 10 тестов. Hashes runtime и
orchestration действующей reference-очереди повторно сверены после запуска.

`flock` защищает от второй копии launcher. Completed jobs переиспользуются
при resume. При ошибке prerequisite или smoke цепочка останавливается,
а не пропускает проверки. После старта не следует править frozen runtime
или общие collection/analysis scripts; новый метод требует отдельного run.

Итоговый отчёт требует ровно 200 эпизодов на метод, полные timelines/videos,
matched task/init/seed и одинаковые q0 simulator states. Показывает SR по
факторам, равновесный macro-SR, rescue/harm, bootstrap CI, McNemar и Holm
для пяти основных сравнений с max-value. При этом разные process seeds
не гарантируют побитово одинаковые candidate pools: это проверяется
отдельно на q0 и не подменяет common-pool анализ.

Видео сохраняются для каждого полного rollout; общий `videos.html`
группирует шесть методов для каждой конфигурации. Пути серверные, не
автономный переносимый video-export. Job seconds содержат initialization
и I/O, поэтому не используются для claim о низкой inference latency.

## 4. Где смотреть

Из WSL:

```bash
./scripts/mlspace_experiment_status.sh trajectory_consensus_20260908_compact
./scripts/mlspace_experiment_status.sh consensus_references_20260908
```

Автономная цепочка и её результаты на сервере:

```text
experiments/campaigns/consensus_references_20260908/
  freeze.json
  config.json
  sequence_status.json
  sequence.log
  trajectory_analysis/RESULTS.md
  matched_analysis/RESULTS.md
  matched_analysis/factor_success_rates.png
  matched_analysis/paired_effects.csv
  matched_analysis/videos.html
```

`waiting_for_compact` означает, что следующий запуск действительно поставлен
в очередь, но его GPU-rollout ещё не начались. `completed` в sequence status
означает окончание всех стадий, включая итоговый анализ.

После этой проверки не подбираем ещё один consensus coefficient по test:
либо фиксируем устойчивую пользу geometry, либо оставляем consensus как
baseline/отрицательный результат и возвращаемся к P5 outcome heads.
Запуск второй модели и нового большого benchmark пока не делается: сначала
закрываем этот конкретный вопрос на замороженном сравнении.
