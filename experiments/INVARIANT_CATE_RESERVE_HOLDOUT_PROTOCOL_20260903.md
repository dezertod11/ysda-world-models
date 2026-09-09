# Frozen invariant-CATE full-reserve holdout protocol

Дата заморозки: 3 сентября 2026 года, до сбора feedback outcomes.

## Primary hypothesis

На новых сочетаниях LIBERO-PRO Object task и Position perturbation frozen
support-aware CATE router улучшает cost-adjusted terminal success относительно
commit-H16.

Для состояния $x_i$ замороженная модель вычисляет

$$
\widehat\tau_i=
\frac{1}{B}\sum_{b=1}^{B}
\left(\widehat p_{F,b}(x_i)-\widehat p_{C,b}(x_i)\right),
$$

и применяет

$$
I_i^{query}=\mathbb{1}
\left[x_i\in\mathcal S_{train}\ \land\ \widehat\tau_i>0.025\right].
$$

`beta=0`, feature family, `alpha=0.1`, 64 bootstrap heads, robust scaler,
clipping, KNN-q99 support reference и threshold зафиксированы в model artifact.

## Untouched cohort

- Все десять eligible boundary cells, не использованные в предыдущем holdout.
- Tasks 1, 2, 4, 6, 7, 8 и 9; tasks 1, 2, 7 и 9 полностью новые для CATE
  training data.
- Init states 5-24, два model rollout seed на init.
- `10 cells x 20 init x 2 seeds = 400` exact-state pairs.
- Query index 4, Cosmos candidate pool K=4, action chunk H=16.
- Commit branch исполняет старый H16; feedback branch исполняет H8, получает
  реальное наблюдение и исполняет H8 нового chunk.
- Обе ветви стартуют из одного snapshot внутри одного процесса и продолжаются
  до terminal success или 280 simulator steps.

Atlas init 0-4 использовались только для outcome-blind проверки query/support
rate. Ни одного feedback terminal outcome для reserve cells при выборе модели
не было.

## Estimands and frozen gates

Primary contribution:

$$
Z_i=I_i^{query}(S_i^F-S_i^C)-0.025I_i^{query}.
$$

95% CI строится 10 000 bootstrap-повторами по независимым
`(position level, task, init state)` clusters.

Efficacy gate проходит только при одновременном выполнении:

1. не менее 380/400 strict pairs;
2. raw success delta frozen router положительна;
3. нижняя граница cluster 95% CI для $E[Z_i]$ положительна;
4. query rate не выше 60%;
5. macro adjusted gain на полностью новых tasks 1, 2, 7 и 9 неотрицателен.

Отдельный strong-superiority gate требует положительной нижней границы CI для
cost-adjusted разности frozen router против always re-query. Он не заменяет
primary efficacy gate.

Always commit, always re-query, oracle query, AUROC, rescue/harm, cell/task
effects, support coverage и query-cost sensitivity являются заранее
объявленными secondary analyses. Нельзя исключать cells, менять threshold или
добавлять task exceptions после просмотра outcomes.
