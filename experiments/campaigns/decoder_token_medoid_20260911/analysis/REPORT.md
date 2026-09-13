# Decoder-Token Medoid Transfer Results

Completed paired configurations: **180/180**. Integration only: **False**.
All comparisons use only configurations completed by all four strategies. Partial results are provisional.

## Protocol
K3, generated/executed H16, five denoising evaluations, 280 steps, joint action/future/value. Object, Environment and Position x0.2/y0.2; all ten Object-suite tasks. Fixed seed groups (1,999,998), (2,997,996), (3,995,994). This is an architecture transfer, not a reproduction of GR00T H4 or MIMIC H5.

## Success Rates
```text
     factor            arm  n  successes  micro_sr  mean_steps  mean_seconds  mean_candidate_calls       sr
Environment  action_medoid 60         24  0.400000  220.683333     58.640680             42.850000 0.400000
Environment decoder_medoid 60         26  0.433333  216.066667     57.459670             41.900000 0.433333
Environment          first 60         24  0.400000  220.900000     42.410939             14.266667 0.400000
Environment      max_value 60         24  0.400000  220.250000     58.293769             42.750000 0.400000
     Object  action_medoid 60         57  0.950000  143.766667     35.453839             28.200000 0.950000
     Object decoder_medoid 60         57  0.950000  143.350000     35.575242             28.250000 0.950000
     Object          first 60         56  0.933333  144.516667     25.702007              9.466667 0.933333
     Object      max_value 60         57  0.950000  145.733333     36.130545             28.800000 0.950000
   Position  action_medoid 60         29  0.483333  237.316667     58.337279             45.800000 0.483333
   Position decoder_medoid 60         29  0.483333  242.616667     60.056169             46.900000 0.483333
   Position          first 60         25  0.416667  248.733333     43.789141             16.033333 0.416667
   Position      max_value 60         31  0.516667  241.433333     59.699394             46.750000 0.516667
```

## Paired Effects
```text
           arm  paired_n  macro_delta  cluster_ci_low  cluster_ci_high  rescue  harm  mcnemar_descriptive_p
         first       180    -0.038889       -0.083333         0.000000       5    12               0.143463
 action_medoid       180    -0.011111       -0.044444         0.016667       7     9               0.803619
decoder_medoid       180     0.000000       -0.033333         0.033333       7     7               1.000000
```

Intervals resample tasks within each factor, retaining repeated seeds/inits together. McNemar values are descriptive; independent-episode inference is not justified for repeated seeds.

No automatic positive-result claim or holdout launch. Check consistency across factors and all three seed groups, then freeze an independent replication. Development improvement is not publication-ready confirmation.

Fixed noise seeds can induce a nearly constant medoid choice. Inspect episode_choice_frequencies.csv and q0_choice_frequencies.csv; if this persists, compare fixed-candidate baselines before claiming observation-adaptive selection.

[Four-way full video gallery](video_comparison.html)
[Per-query metrics](queries.csv)
[Per-seed results](seed_group_rates.csv)
