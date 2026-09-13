# Matched-K feedback и continuity: замороженный механизм-screen

Дата: 10 сентября 2026. Campaign: `feedback_controls_20260910`.
Предпосылки: [fresh8 audit](FRESH8_IMPLEMENTATION_AUDIT_20260910.md),
[приоритеты](RESEARCH_PRIORITIES_20260910.md).
Это prospective screen, не готовый результат и не full LIBERO-PRO benchmark.

Запуск dispatcher подтверждён10 сентября13:19 MSK: PID3878088,
`waiting_predecessor`, текущий P5 не прерван. Config SHA256:
`c863c05fd42774af8bbc4f2b5cc8520d9dc8edd0e40c890e7a981984ba62c9ce`.
45 CPU-тестов на сервере,75 локально с regression suite. GPU smoke предстоит.
Перед первым remote launch исправлена только доставка: один SSH-сеанс вместо
нескольких. Предварительный config сохранён как `prelaunch_transport_config.json`;
метод, cases, seeds, hypotheses и коэффициенты не менялись, новых rollout до
этой технической поправки не было.

## Гипотезы

H1: fresh-K4 лучше open16 при неизменных K4 prefix/suffix.
H2: fresh-K4 лучше fresh-K1: часть прежнего ухудшения связана с потерей выбора.
H3: мягкое temporal consistency при том же fresh K4 pool улучшает выбор.
Если sign меняется между cells, не интерпретировать pooled эффект как общий.

## Модель и данные

Frozen Cosmos-Policy-LIBERO-Predict2-2B; parallel joint action/future/value,
5 denoising steps, H16, K4 max-value в префиксе и suffix, 280 env actions
включая интервенцию, 10 settling steps вне task counter, как в исходном
протоколе. Два текущих реальных RGB + 9D proprio + исходная `task.language`.

| Cell | Suite/task | Начало chunk | Повторное наблюдение |
|---|---|---:|---:|
| Положительный контроль Object | libero_object_object / task0 | t64, q4 | t72 |
| Position x0.2 | libero_object_temp / task2 | t48, q3 | t56 |
| Position y0.2 | libero_object_temp / task9 | t48, q3 | t56 |

Smoke: init12, один новый seed на cell, 15 branches. Screen: init13-16,
два новых seed на init, 24 состояния / 120 branches. Эти init не заявляются
никогда не использованными в проекте; они отделены от smoke и недавнего
P5 соседнего диапазона9-12, но имеют возможную историческую экспозицию.
Сравнение timing между разными cells конфундировано задачей: для эффекта
самого t понадобится отдельный within-cell timing factorial.

Seed namespaces: общий prefix seed, отдельный requery seed, отдельный suffix
seed. Fresh/stale K4 получают одинаковые requery seeds. Suffix seed зависит
от абсолютного t, не от числа уже сделанных queries. Между двумя repeats
меняются prefix, requery и suffix seeds; это не абляция источника шума.

## Пять ветвей

1. `open16`: выполнить все 16 действий выбранного initial K4 candidate.
2. `stale_k4`: выполнить первые8, пересемплировать по старому real observation,
   выбрать max-value из4, исполнить tail8:16 нового плана.
3. `fresh_k1`: после тех же8 действий взять candidate0 свежего K4 pool,
   исполнить его0:8. Это single-sample control, без выбора по value.
4. `fresh_k4`: по свежему real observation выбрать max-value из того же K4
   pool, исполнить0:8.
5. `fresh_continuity_k4`: из того же свежего K4 pool выбрать value-.10*cost,
   исполнить0:8. Без усреднения действий и без новой генерации.

Далее у всех K4/H16 max-value suffix. Только одна intervention на эпизод;
это не always-H8 policy. Stale-tail не условлен на реально выполненный
prefix, поэтому не является идеальным контролем «только старое наблюдение».
Main H2/H3 обходят этот недостаток: у них один fresh pool и один timeline.

## Формула continuity

Пусть $\bar a=\operatorname{clip}(a,-1,1)$, $u_j=\bar A^{old}_{8+j}$,
$v_{ij}=\bar A^{new}_{i,j}$, $j=0,\ldots,7$.

$$
C_i=\frac{1}{8}\sum_{j=0}^{7}\left[
\frac{0.5}{2\sqrt3}\|v^{xyz}_{ij}-u^{xyz}_j\|_2+
\frac{0.25}{2\sqrt3}\|v^{rot}_{ij}-u^{rot}_j\|_2+
0.25\,\mathbf1[\operatorname{sign}(v^{grip}_{ij})\ne
\operatorname{sign}(u^{grip}_j)]\right],\quad C_i\in[0,1].
$$

$$
i^*=\arg\max_{i=0,\ldots,3}\{\widehat V_i-0.10C_i\}.
$$

Это расстояние между **командами OSC** на одинаковые будущие моменты,
не расстояние в метрах, не дисперсия и не epistemic uncertainty. Rotation
команды не являются абсолютными ориентациями. Gripper сравнивается по знаку.
Value в диапазоне[0,1] остаётся joint prediction полного16-step sample,
а исполняется head8. Этот общий для двух fresh-K4 arms mismatch не скрываем.
Cost не запрещает большие необходимые коррекции; его полезность проверяется
по SR, не по уменьшению самого cost. Lambda=.10 не подбирается на screen.

Метод является простой адаптацией известных temporal consistency идей
[BID](https://arxiv.org/abs/2408.17355) и
[RTC](https://arxiv.org/abs/2506.07339), не их точной репликацией и не новой
архитектурой Cosmos. Здесь нет async inference delay или latent inpainting.

## Защита измерений

- Один snapshot MuJoCo + controller и initial K4 pool на все arms.
- Пулы fresh/stale фиксируются после общего8-step prefix до новых terminal
  labels; fresh-K1 является первым sample этого pool.
- При каждом branch проверяются restore state, состояние после8 действий
  (atol1e-9), время/termination и SHA256 реальных camera/proprio inputs.
  Camera/proprio hashes относятся к `prepare_observation` на входе policy API;
  это не утверждение о hash каждого внутреннего JPEG/VAE/DiT tensor.
- Сохраняются lossless исходные observations, action/value/future pools,
  executed actions, per-frame safety proxies, input hashes suffix queries.
- Success до decision отдельно исключается из conditional-denominator;
  success в общих первых8 считается одинаковым success всех arms. Missing
  assets / replay mismatch прекращают smoke, не становятся fail.
- H264 yuv420p видео всех arms идут от t48/t64 до terminal/280 без сокращения
  по query. Они не содержат ранний pre-decision префикс; `frame_t` задаёт
  абсолютное соответствие кадра и env-step.
- Shared pools экономят фактическое время сбора. В logical policy cost
  fresh-K1 считается как1 sample, fresh-K4 как4, open16 как0 новых samples.
  Фактическое wall-time ветвей с cached pools не выдаётся за deploy latency.
- SafetySignalTracker здесь даёт проектные proxy labels, не официальный
  LIBERO-Safety benchmark. Simulator signals не подаются в selector.

## Статистика и stop rules

Первичные H1/H2/H3: paired SR delta, rescue/harm, stratified init-cluster
bootstrap95%CI, cluster sign-flip p и Holm3. 24 состояния дают12 init clusters
на трёх фиксированных cells. Малый screen не обладает гарантированной мощностью;
CI conditional на этих cells, не на популяции новых задач.

Отдельно: SR каждой cell, drop/wrong-object proxies, executed steps,
logical candidate evaluations. Выводы только после завершения всех cases;
частичный файл маркируется partial. Независимый holdout и новый fit **не**
запускаются автоматически по промежуточной метрике.

Smoke требует все5 arms на всех3 cells. Ошибка источников/inputs/worker
останавливает очередь с отчётом, а не запускает следующие cells как ни в чём
не бывало. При передаче/запуске проверяются source SHA256; frozen исторические
скрипты не редактируются. Максимум3 workers, только idle GPU0-7
(две проверки: нет CUDA процессов, <256MiB, <5%util). Занятая GPU не удерживает
за собой job; другая свободная может забрать его. Между batch нет захвата
памяти фиктивным процессом. Shared cluster admission не является эксклюзивной
резервацией для других пользователей.

## Запуск и статус

Локально подготовить и поставить доставку (WSL должен оставаться включён):

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/run_feedback_controls.py --prepare
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/run_feedback_controls.py --delivery-launch
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/run_feedback_controls.py --status
```

На сервере после успешной доставки:

```bash
ssh mlspace-sr006 /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/run_feedback_controls.py --status
```

Dispatcher сначала ждёт освобождения lock текущего P5 candidate replication.
`completed` или явно завершённый `partial` допускает последующий screen;
partial predecessor остаётся partial, большой critic по нему не открывается.
`failed`/`analysis_failed` блокирует очередь. После ожидания начинается новый
48-часовой wall budget, ожидание свободных GPU входит в него. Это верхний
лимит, не ETA. При исчерпании нужен явный пересмотр бюджета, скрытого продления нет.

Результаты: `experiments/campaigns/feedback_controls_20260910/analysis/`:
`RESULTS.md`, `summary.json`, `scores.csv`, `paired_effects.csv`,
`success_rates.png`, `videos.html`. До фактического запуска этих данных нет.
