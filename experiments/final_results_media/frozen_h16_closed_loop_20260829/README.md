# Frozen H16 closed-loop: plots and videos

Portable media bundle for the 29 August 2026 paired validation.

## Statistical result

- Primary run: 360 pairs / 720 episodes.
- `maxV-H16`: 165/360 success, 45.83%.
- `frozen-ranker-H16`: 164/360 success, 45.56%.
- Factor-macro delta: -0.28 percentage points.
- Grouped 95% CI: [-2.22; +1.39] percentage points.
- Preregistered terminal-SR gate: **FAIL**.

The full interpretation and formulas are in
[`../../FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md`](../../FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md).

## Videos

Open [`VIDEO_INDEX.html`](VIDEO_INDEX.html) to view the nine selected seed pairs
side by side. All 18 MP4 files are self-contained under [`videos`](videos).

These are post-hoc model replays, not frames captured during the primary
statistical run. The HTML therefore displays both the primary outcome and the
actual replay outcome for every strategy.

Replay fidelity:

| Check | Result |
|---|---:|
| Complete videos | 18/18 |
| Encoded frames equal executed frames | 18/18 |
| Episode outcome reproduced | 14/18 |
| Full paired outcome reproduced | 5/9 |
| Query-zero selected index reproduced | 16/18 |
| Max query-zero value difference | 0.002005 |
| Max query-zero score difference | 0.004263 |
| Max query-zero first-action difference | 0.003703 |

All nine maxV outcomes reproduced. Four near-boundary ranker outcomes changed
under a new H100 inference process. This does not alter the primary result; it
shows that visual replay of diffusion policies must be labelled separately from
the original rollout outcome.

Exact paired outcomes reproduced for seeds `5270485`, `5270388`, `5340582`,
`5450097`, and `5470388`. The HTML marks the four non-exact pairs explicitly.
Machine-readable checks are in [`replay_fidelity.csv`](replay_fidelity.csv) and
[`video_pairs.csv`](video_pairs.csv).

## Plots

- [`paired_terminal_success.png`](plots/paired_terminal_success.png): SR for
  maxV and ranker by OOD factor.
- [`paired_sr_delta_ci.png`](plots/paired_sr_delta_ci.png): grouped-bootstrap
  terminal-SR deltas and 95% intervals.
- [`paired_discordances.png`](plots/paired_discordances.png): gains and losses.
- [`ranker_selection_by_query.png`](plots/ranker_selection_by_query.png): how
  often the ranker rejects maxV during an episode.
- [`candidate_preference_heatmap.png`](plots/candidate_preference_heatmap.png):
  selected-minus-maxV feature shifts in within-pool standard deviations.
- [`failure_mode_composition.png`](plots/failure_mode_composition.png): terminal
  failure categories.
- [`prediction_error_proprio.png`](plots/prediction_error_proprio.png):
  future-proprio prediction error after executing selected chunks.

The compact CSV tables used by these plots are under [`data`](data).
