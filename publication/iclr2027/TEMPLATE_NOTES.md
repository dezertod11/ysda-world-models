# Что сохранено и что исправлено

[user_original.tex](templates/user_original.tex) является точной копией
прикреплённого текста. Он не редактировался. [main.tex](manuscript/main.tex)
сохраняет его логику Introduction → Related Work → Preliminaries → Consensus
Planning и развивает её в рабочую рукопись с результатами и ограничениями.

| В присланном тексте | В рукописи текущих экспериментов | Причина |
| --- | --- | --- |
| `ICRA2027 - WAMPlan` | Рабочее название WAMPlan; отдельная сборка ICLR 2027 | Цель пользователя сейчас ICLR, не ICRA |
| `Aleksandr Panov` | Anonymous authors | Авторская строка сохранена в оригинале; состав команды нельзя устанавливать по шаблону; review анонимный |
| `article` | `article` для черновой вёрстки + официальный ICLR wrapper | Исходный шаблон не является официальным ICLR style |
| K=3, seeds 0,1,2 | K=4 в valid199; K=1 контроль; K=8 pilot | Это фактически измеренные настройки |
| Translation 3D + rotation 6D + gripper | Native LIBERO OSC: 3 translation + 3 rotation-vector + 1 gripper | Нельзя ортонормировать rotvec как 6D rotation |
| Мгновенные команды, нормировки sqrt(3), pi | Накопленные OSC proxies, масштабы 0.05 m и 0.5 rad | Соответствие реально вызываемому selector |
| Discount 0.9 | Discount 0.95, alignment window 0 | Настройки протестированного OSC-medoid |
| Полностью value-free | Расстояние без value, но равные scores разрешаются большим value | Tie-break в реализации существенен для точности описания |
| `We introduce consensus planning` | `We evaluate ...` с KeyStone/KDPE/self-consistency | Медоид и consensus не являются нашей новой общей идеей |
| Planning без указания режима | Joint/parallel action, future, value | Нельзя называть эту таблицу авторским AR a→s→v Cosmos planning |

Контракт проверен по
[trajectory_consensus.py](../../cosmos-policy/cosmos_policy/experiments/robot/libero/trajectory_consensus.py),
[protocol](../../experiments/TRAJECTORY_CONSENSUS_PROTOCOL_20260908.md) и
[итоговому отчёту](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md).
Исходная 6D-формула остаётся возможной отдельной постановкой для другого
контроллера, но не подставляется задним числом в результаты native7D.

Официальный архив скачан с
[ICLR 2027](https://media.iclr.cc/Conferences/ICLR2027/iclr-2027-style-files.zip),
сами стили не изменены. Источники и SHA-256: [toolchain_sources.json](templates/toolchain_sources.json).
