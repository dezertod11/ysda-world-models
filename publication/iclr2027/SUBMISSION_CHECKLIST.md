# Готовность к ICLR 2027

Проверено 15 сентября 2026. Статус: **оформленный научный draft, не готовое
доказательство для отправки**. Ничего в OpenReview этим проходом не подано.
Положительные historical counts сохранены; новые результаты не выдумываются.

## Сроки и формат

Abstract: **18 сентября 2026, 23:59 AoE** (19 сентября14:59МСК).
Полная статья: **25 сентября, 23:59 AoE** (26 сентября14:59МСК).
Список авторов фиксируется к abstract deadline; нужны актуальные OpenReview
profiles и настоящий содержательный abstract. Основной текст до9страниц,
анонимны и paper, и supplement. References/appendix вне лимита.
[Официальные author guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines),
[Call for Papers](https://iclr.cc/Conferences/2027/CallForPapers).

AI-use statement обязателен; нужно описать фактическую помощь в идеях,
методологии, реализации, анализе и тексте. Нельзя утверждать авторскую
ручную проверку, пока она не выполнена.
[AI policy](https://iclr.cc/Conferences/2027/AIPolicyForAuthors).

Даты и правила повторно проверить перед отправкой. Сведения на overview
или reviewer pages не подменяют актуальные Author Guidelines/Call for Papers.

## Сделано

- [x] Английская статья сфокусирована на physical recovery и его механизме.
- [x] Unrelated selector sweeps отделены от основной статьи, данные сохранены.
- [x] Scoped gains, retreat-only, timing и grounding описаны с областью действия.
- [x] Включена полная corrected-runtime S0-v2,995main/199cases.
- [x] Старые scoped counts и новый broad runtime не смешаны.
- [x] AI disclosure, reproducibility, limits и анонимное оформление включены.
- [x] Таблицы/графики генерируются из проверенных источников; tests сохраняют
  все cells и controls. PDF/ZIP собираются одной командой.

Результаты последней технической проверки: [validation_report.json](build/validation_report.json).
Поле `scientific_submission_ready=false` не ошибка сборки, а незакрытая
научная проверка. Её нельзя заменить успешной компиляцией.

## Критический путь

### P0: перепроверить основной положительный эффект

- [ ] Новая, отдельно версионированная scoped v2-кампания на тех же восьми
  cells и init25–32. Сохранять обе cohort исходного confirmation:
  familiar64 и x0.3 transfer64; не оставлять только хорошую cohort.
- [ ] Минимальные controls: uninterrupted H16, H8 continuation, physical
  recovery;128cases×3=384main rollout плюс regression/no-intervention smoke.
  Это предложение нового протокола, не уже запущенная очередь и не точная
  четырёхсторонняя репликация512ветвей с preserve-only.
- [ ] Зафиксировать manifest, новые snapshot schema, исходные seeds, модель,
  localizer, thresholds, budget280 и contrasts до запуска. Не использовать
  старые snapshot как якобы полное v2-состояние и не ослаблять parity.
- [ ] Primary: recovery−H8 на знакомых cells; H16 как объявленный контроль;
  transfer отдельно. Cluster CI, rescue/harm, полная таблицаcells, расходы.
- [ ] Smoke проверяет input/action/state parity без intervention и полный
  action accounting. Технический сбой останавливает серию, не считается fail.
- [ ] Только после аудита независимо от знака результата обновить abstract,
  main table и поле readiness. Если gain не воспроизведётся, изменить claim,
  а не выбирать новые выигрышные seeds.

Время здесь не обещается: число rollout известно, скорость новой ветки пока
не измерена. Broad995rollout заняли около2часов на7GPU, но это другая схема
кэширования/префиксов. Её время нельзя автоматически переносить на384ветви.

### P1: механизм, новизна, сравнение

- [ ] После успешного P0 проверить переносимость вывода full vs retreat-only
  на новом runtime; controls и population объявить до сбора.
- [ ] Проверить, затрагивает ли missing-state issue старый shared-prefix
  feedback. Пока это supporting historical study, не современный causal proof.
- [ ] Авторская оценка, достаточно ли эмпирического вклада для main-track:
  метод использует известные recovery и receding-horizon идеи. Не заявлять
  первенство regrasp/monitoring или новый общий planning algorithm.
- [ ] Сопоставить близкие методы по input, training, intervention, tasks и cost;
  не выдавать benchmark-цифры из других работ за head-to-head comparison.

### P2: воспроизводимость и отправка

- [ ] Подготовить анонимный executable release с requirements, licensed
  dependency versions, manifests, CPU checks и инструкцией GPU evaluation.
  Текущий Overleaf ZIP содержит текст/рисунки, не запуск всего эксперимента.
- [ ] Проверить права на release localizer weights и benchmark assets;
  не включать HF/GitHub/W&B credentials, SSH keys или чужие paper PDFs.
- [ ] Приложить оригинальные representative rescue/harm videos с case IDs;
  поздние illustrative replay не выдавать за исходную статистическую ветвь.
- [ ] Все авторы проверяют числа, formulas, references, novelty, anonymity
  и фактическое AI disclosure. Проверить reviewing eligibility/exemption
  по официальным правилам, не назначать автора или reviewer автоматически.
- [ ] Зарегистрировать abstract, затем вручную загрузить проверенный PDF.
  Ни автоматической отправки, ни обещания acceptance нет.

## Команды локальной проверки

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/build.py
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q publication/iclr2027/tools/test_build.py publication/iclr2027/tools/test_recovery_assets.py
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/validate.py
```

Технические проверки дополняют, но не заменяют независимую научную проверку.
