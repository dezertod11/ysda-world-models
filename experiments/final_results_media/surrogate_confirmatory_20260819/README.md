# Surrogate/requery confirmatory replays

Status: queued. The 960/960 confirmatory executions and all statistical results
are complete; this directory only tracks post-hoc visual replays.

Seven matched `suite/task/init_state/rollout_seed` groups were selected
mechanically from discordant frozen outcomes:

| Category | Outcome | Case | Seed |
|---|---|---|---:|
| non-surrogate adaptive | win | long milk | 950679 |
| non-surrogate adaptive | loss | goal mug | 960388 |
| non-surrogate adaptive | win | new OOD spatial swap | 990000 |
| surrogate adaptive | win | long milk | 951164 |
| surrogate adaptive | loss | goal mug | 960097 |
| surrogate adaptive | win | new OOD spatial swap | 990873 |
| surrogate adaptive | loss | new OOD spatial swap | 990485 |

The replay campaign is waiting for GPU 2-7 capacity because a shared-server
eight-GPU training process currently occupies the server. It will write H.264
MP4 files and replace this status with the actual replay manifest when capacity
becomes available.

Selection is recorded in
[`../../configs/libero_campaign_surrogate_video_replays.csv`](../../configs/libero_campaign_surrogate_video_replays.csv).
Selected videos are explanatory artifacts only; the success-rate estimate is
computed from the full confirmatory dataset.
