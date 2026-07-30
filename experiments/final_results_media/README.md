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
