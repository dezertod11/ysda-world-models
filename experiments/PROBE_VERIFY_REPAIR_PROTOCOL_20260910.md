# Probe → Verify → Repair: замороженный протокол

Дата: 10 сентября 2026. Campaign: `probe_verify_repair_20260910_v2`.
Это новый механизм-screen и условный confirmatory этап, не полный LIBERO-PRO
benchmark. Результаты не известны на момент фиксации этого протокола.

**Техническая поправка до screen:** первый smoke остановлен после 16 ветвей:
optical flow нового verifier считался в OpenGL RGB, а EEF projection в OpenCV.
Геометрическая проверка рендером подтвердила различие; см.
[аудит](campaigns/probe_verify_repair_20260910/camera_audit/summary.json).
V2 отражает строки только для tracking RGB, сохраняя native input frozen
локализатора и Cosmos. Пороги, cells/seeds, arms и критерии не меняются;
старые 16 smoke-ветвей не входят в SR v2. Они сохранены вместе с исходниками v1.

## Гипотеза и архитектура

Обычный RGB regrasp полезен при промахе, но способен испортить уже состоявшийся
захват. Короткая проба с закрытым gripper создаёт дополнительное наблюдение:
движется ли целевой предмет вместе с рукой? В отличие от текстового исправления,
пробу нельзя откатить. Все последствия и шаги остаются частью rollout.

Мотив: [CRITIC](https://arxiv.org/abs/2305.11738), проверка внешним инструментом
перед исправлением; [обзор self-correction](https://aclanthology.org/2024.tacl-1.78/).
Это робототехническая адаптация общей идеи, не реплика CRITIC и не утверждение
новизны active perception/проверки захвата как таковых.

Frozen Cosmos Policy: joint/parallel action/future/value, 5 diffusion steps,
K4 max-value. Общий H16 prefix до t72 (4 полных chunk +8 действий). Затем
однократное вмешательство и K4/H8 suffix во всех ветвях. Генерируется H16,
исполняются первые 8. Сuffix RNG согласован по порядковому номеру query q5, q6,
а не по физическому времени после разного по длительности primitive.
280 действий, включая probe/regrasp; 10 settling steps отдельно.
**t72 остаётся фиксированным контрольным временем, не универсальным trigger.**

## Четыре ветви из одного состояния

| Arm | Что реально выполняется |
|---|---|
| continue_h8 | Продолжить K4/H8 без вмешательства |
| physical_regrasp | Frozen workspace-calibrated P3c trigger и полный RGB regrasp |
| probe_only | Тот же trigger; короткое движение вверх с закрытым gripper, затем K4/H8 |
| probe_verify_repair | Та же проба; regrasp только при уверенном `miss`; `held`/`unknown` продолжают K4/H8 |

Если начальный trigger не сработал, вмешательства нет. У full regrasp
post-retreat guard может прервать primitive, но продолжение идёт **из реального
состояния после выполненных действий**, без исторического rollback fallback.
Поэтому primary baseline называется physical_regrasp, не подменяется старым SR P3c.
Goal во время префикса учитывается как общий success, не выбрасывается из SR.

## RGB-проверка

Проба: servo к EEF+[0,0,0.04] м, до 3 шагов, gripper=+1 (закрыт), tolerance
0.005 м; остановка при goal/лимите. Центр crop определяет frozen RGB localizer.
Lucas–Kanade optical flow (OpenCV) на crop радиуса16px, до40 Shi–Tomasi
corners, quality=.01, minDistance=3; LK window21, pyramid3, forward/backward
error≤1.5px. Берём медиану векторов валидных треков.
Tracking RGB преобразуется из native OpenGL в OpenCV отражением строк;
центр crop и проекция EEF уже в OpenCV. Локализатор по-прежнему получает
native RGB: его выходные heatmap coordinates обучены на OpenCV masks.

$$
d_o=\operatorname{median}_j(p_j^{after}-p_j^{before}),\qquad
d_e=\Pi(eef^{after})-\Pi(eef^{before}),\qquad
\rho=\frac{\|d_o\|_2}{\|d_e\|_2},\quad
c=\frac{d_o^\top d_e}{\max(\|d_o\|_2\|d_e\|_2,10^{-8})}.
$$

При отсутствии calibrated confidence, <4 треков, движении EEF<2px или
нечисловых данных: `unknown`. Иначе `held`, если c≥0.7 и 0.3≤ρ≤2.5;
иначе `miss`, если ||d_o||≤0.75px; иначе `unknown`.

Онлайн используются RGB, task text, EEF proprio и известная калибровка камеры.
GT object poses/contacts не идут в verifier: они только в диагностике и
проверке replay. Не используем inferred object-z для проверки подъёма,
поскольку локализатор может проецировать на фиксированную плоскость.
Crop может содержать gripper/background; `held` не ground truth. Частота
неопределённых/ошибочных ответов является результатом проверки, а не поводом
подобрать пороги на holdout. Это не гарантия физической безопасности.

## Данные и бюджет

| Cell | Встречалась в calibration локализатора |
|---|---|
| Position x0.2 / task2 | Да |
| Position x0.2 / task5 | Да |
| Position y0.2 / task9 | Да |
| Position y0.2 / task2 | Нет |
| Position x0.1 / task5 | Нет |
| Position x0.1 / task9 | Нет |

Проверяется отсутствие `(position,task,init)` overlap с calibration_manifest.
Все task/object identities известны модели; unseen относится к этим сочетаниям
perturbation/task, не к новым предметам или нетронутости всех прошлых кампаний.

- Smoke: init33 ×1 seed ×6cells ×4arms =24 ветви. Только технический допуск.
- Screen: init25–28 ×2 seeds ×6cells ×4arms =192 ветви (48 paired states).
- Conditional holdout: init29–32 ×2 seeds ×6cells ×4arms =192 ветви.
- Итого до408 ветвей, максимум12ч от старта, не более3 idle-only GPU workers.

Это сознательно более дешёвый механизм-screen вместо прежнего проекта
6dev+6holdout cells. Holdout имеет новые init, но те же cells; для общего
переноса затем потребуется отдельный cell/задачный holdout.
Порядок arms вращается по repeat. Сохраняются prefix snapshot, raw observation,
SHA-256, actions, per-frame proxies, query uncertainty, probe decision и видео.
Повтор одной пробы в двух arms должен дать одинаковые observation hashes и
sim state до1e-9; при нарушении кампания падает, не записывает fake policy fail.
Видео от t72 до настоящего terminal state, H264/yuv420p, обе камеры.

## Метрики, допуск и остановка

Primary: paired terminal SR verified против physical_regrasp. Secondary:
против probe_only и continue_h8. Равный вес cells; bootstrap по init внутри
cell (5000), 95%CI; paired cluster sign-flip (100000 draws при >16 clusters),
Holm по3контрастам. Seed repeats не считаются независимыми init.
Дополнительно: rescue/harm, drop/wrong-object proxies, final step, query cost,
trigger coverage, held/miss/unknown, доля лишних/пропущенных regrasp.
Proxies не official LIBERO-Safety показатели.

После smoke нужны выполненные probes и полный artifact/replay audit.
Smoke имеет один init на cell: его вырожденные stratified bootstrap CI
не использовать для научных выводов. Его outcomes не входят в основную SR.
Holdout автоматически начинается, только если screen полностью собран,
verified-full≥5п.п., verified-probe>0, verified-continue>0, drop_count не
выше full и минимум8 eligible states избежали full regrasp. Это practical
screen gate, не статистическое подтверждение. Иначе сохранить отрицательный
результат и остановиться без расхода holdout.
Confirmatory PASS: holdout primary CI_low>0, Holm p≤.05 и нет увеличения
наблюдаемого drop count. Даже PASS требует отдельной оценки переносимости.
Дополнительные subgroups exploratory, не повод заявить общий успех после NO-GO.

## Команды

Из корня проекта на сервере:
```bash
.venv-cosmos/bin/python scripts/run_probe_repair.py --launch
.venv-cosmos/bin/python scripts/run_probe_repair.py --status
```

Из WSL:
```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/run_probe_repair.py --status'
```

Работа автономна от WSL. Кандидаты GPU0–7; занятые карты с чужими CUDA
процессами не используются даже при низкой utilization. Свободная память
не означает свободную GPU. До4 jobs одного position level на загрузку модели.
Timeout не обозначает policy fail: незавершённые ветви остаются pending.
Бюджет wall-clock включает ожидание GPU, поэтому408 не гарантируются.
