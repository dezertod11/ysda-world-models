# Remote exact-state sidecars

Compact candidate tables, logs and all analyses are available in this local
campaign tree. The larger runtime snapshot NPZ files remain on MLSpace at:

```text
/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/frozen_h16_ranker_holdout_20260828/runs
```

Inventory on 28 August 2026:

| Directory suffix | Size |
|---|---:|
| `environment_holdout__snapshots` | 194 MB |
| `object_holdout__snapshots` | 214 MB |
| `position_holdout_x0p3__snapshots` | 101 MB |
| `position_holdout_y0p3__snapshots` | 100 MB |

These files are needed only to relabel physical endpoints again. The current
H16 dense labels, frozen scores and bootstrap result can be reproduced from
the locally synchronized parquet tables without downloading the NPZ files.
