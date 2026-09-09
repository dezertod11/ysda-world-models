# Cosmos identical-query reproducibility diagnostic

Artifacts: **4**.

```json
{
  "artifact_count": 4,
  "action_tolerance": 1e-05,
  "value_tolerance": 1e-05,
  "modes": {
    "default": {
      "within_process_exact": true,
      "cross_process_strict": false,
      "max_cross_action_abs_diff": 0.00744965672492981,
      "max_cross_value_abs_diff": 0.0003763437271118164,
      "min_cross_selected_index_match_rate": 1.0
    },
    "warn": {
      "within_process_exact": true,
      "cross_process_strict": false,
      "max_cross_action_abs_diff": 0.005098879337310791,
      "max_cross_value_abs_diff": 0.0004330575466156006,
      "min_cross_selected_index_match_rate": 1.0
    }
  }
}
```

Detailed comparisons are in `within_process.csv` and `cross_process.csv`.
