# Final results media

This directory contains a small, portable video subset for
`LIBERO_FINAL_RESULTS.ipynb`.

All videos use the same LIBERO-PRO configuration:

- suite: `libero_spatial_with_milk`;
- task: `5`;
- init state: `0`;
- four planning strategies evaluated with the same rollout seed.

The selected seeds are visual case studies where `max(value)` failed and at
least one uncertainty-aware strategy succeeded. They come from the May 29
matched-seed pilot, not from the 1078-execution confirmatory campaign. They
must therefore be used to explain how candidate selection can change a
trajectory, not to estimate a strategy success rate.

`manifest.csv` records the strategy, hyperparameters, outcome and terminal
simulator step for every video.

## Adaptive planning confirmatory

[`adaptive_confirmatory_20260813`](adaptive_confirmatory_20260813/README.md)
contains 32 full-length H.264 videos: four planning strategies on eight
matched `suite/task/init_state/rollout_seed` configurations selected from the
frozen 1080-execution campaign. The per-video manifest distinguishes original
confirmatory outcomes from exact-replay outcomes; the selected binary pair
fully reproduced in 5/8 replays.

## Surrogate/requery confirmatory

[`surrogate_confirmatory_20260819`](surrogate_confirmatory_20260819/README.md)
tracks seven matched-seed groups selected from the latest 960-execution frozen
campaign. Their MP4 replays are queued until GPU 2-7 capacity becomes
available; the confirmatory statistics are already complete.

## LIBERO-Safety

[`safety_violations_20260730`](safety_violations_20260730/README.md) contains
the four official `checkcontact` violations from the 144-rollout physical
Safety campaign. Unlike the matched-seed pilot above, these videos terminate
at the exact official constraint event and support the reported violation
count.

## Frozen H16 closed-loop

[`frozen_h16_closed_loop_20260829`](frozen_h16_closed_loop_20260829/README.md)
contains the final plots and 18 full-length MP4 replays for all nine discordant
primary seeds from the 360-pair maxV versus frozen-ranker test. Its HTML index
shows primary and replay outcomes separately; 5/9 complete pairs reproduced
exactly, so the videos are mechanism diagnostics rather than statistical data.
