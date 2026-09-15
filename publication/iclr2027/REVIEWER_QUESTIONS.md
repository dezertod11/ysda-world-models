# Вопросы рецензента и состояние доказательств

15 сентября2026. Это внутренний checklist подготовки, не симуляция принятого
review и не текст, который нужно выдавать за чужое мнение.

| Вероятный вопрос | Что можем ответить данными | Что ещё нужно |
|---|---|---|
| Чем это отличается от известного recovery? | Конкретная RGB-коррекция frozen Cosmos; парный контроль physical vs retreat/requery; фиксированный physical budget | Авторская оценка новизны и сопоставимости с Sentinel/Rewind-IL; empirical contribution не автоматически algorithmic novelty |
| Это просто H8 вместоH16? | В scoped confirmation H16 17/64,H8 16/64,P3 41/64;P3d retreat8/40,full25/40 | Воспроизвести основной scoped эффект наv2 |
| Почему выбраны именно эти tasks? | Восемь cells выбраны в development; все оставлены; calibration/init и роль cohorts раскрыты | Не называть их случайной выборкой всегоPRO или untouched test |
| Почему t72? | Историческая фиксированная точка; соседние56/88 проверены; positive estimates не исчезают | Не переименовывать её в выученный trigger; event0/199 не успешная замена |
| Система training-free? | Backbone frozen; auxiliary DeepLab обучен отдельно на388изображениях | Сохранить calibration details, не утверждать отсутствие обучения всей системы |
| Не используются GT poses online? | Online RGB/proprio/camera calibration; GT только для supervision и явно названного oracle | Исполняемый release и проверка data flow |
| Действительно общий OOD gain? | Нет: broadv2 Macro54.10 vs53.42,CI включает0; x0.3 слабый | Сформулировать bounded claim, полную broad таблицу оставить вappendix |
| Gate знает, когда recovery полезно? | Он оценивает геометрию, не advantage; harms наблюдались | Не выдавать формулу advantage за обученный router |
| Надёжна парность? | Новая broadS0-v2 прошла strict audit и hash-проверки; scoped older runtime | P0 изsubmission checklist, без переноса статуса broad наscoped |
| Где статистическая независимость? | Bootstrap init-clusters внутри fixedcells; не суммируем повторы в новые tasks | Межtaskgeneralization и межseedrobustness не завышать |
| Compute честно сопоставлен? | Recovery входит в280actions; logical queries показаны | Нет controlled standalone latency из-за shared cache; не рисовать speedup |
| Как интерпретировать shared-prefix? | Локальный46/100→64/100,31/13; это отдельная feedback-постановка | Отдельный runtime audit; нельзя объяснять им автоматически P3 |
| Что готово к проверке авторами? | PDF, исходники, CSV-linked figures, provenance, полный отчёт | Анонимный executable release, raw-data policy, human sign-off |

## Приоритет ответа

Сначала закрыть воспроизводимость headline, затем подкреплять механизм.
Новые коэффициентные sweeps на том же тесте имеют меньшую ценность, чем
валидная репликация. Отрицательные прямые controls не делают статью бессмысленной:
они уточняют, какой вклад действительно установлен. Но один крупный scoped
SR сам по себе не гарантирует достаточной новизны для ICLR main track.

Результаты других авторов и различия протоколов:
[RELATED_WORK_RESULTS.md](RELATED_WORK_RESULTS.md).
Текущий пакет: [README.md](README.md).
