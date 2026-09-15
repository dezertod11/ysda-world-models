# P3 night: seed replication and coverage audit

Generated: 2026-09-15T10:06:16.013559+00:00

Same historical task/init support, new rollout seeds. Not an unseen-task/init holdout.
Partial stages are descriptive only. Missing cases are not failures. No best-seed selection.

|   seed_group |   matched_cases |   planned_cases | complete   |
|-------------:|----------------:|----------------:|:-----------|
|            0 |             199 |             199 | True       |

## Per-seed table

|                      |   Object |   Environment |   Position |   Macro-SR, % | Success/N   |
|:---------------------|---------:|--------------:|-----------:|--------------:|:------------|
| (0, 'first_k1')      |    96.00 |         40.00 |      29.29 |         55.10 | 97/199      |
| (0, 'h8_at72')       |    96.00 |         42.00 |      26.26 |         54.75 | 95/199      |
| (0, 'max_value_h16') |    94.00 |         40.00 |      26.26 |         53.42 | 93/199      |
| (0, 'p3_at72')       |    90.00 |         42.00 |      30.30 |         54.10 | 96/199      |
| (0, 'p3_event')      |    94.00 |         40.00 |      26.26 |         53.42 | 93/199      |

## Descriptive rescue/harm versus H16

|                 |   rescues |   harms |   pairs |
|:----------------|----------:|--------:|--------:|
| (0, 'h8_at72')  |         5 |       3 |     199 |
| (0, 'p3_at72')  |         9 |       6 |     199 |
| (0, 'p3_event') |         0 |       0 |     199 |

## Event coverage

Episode columns count whether evidence occurred at least once; they are not independent events or a calibrated failure detector.
|   seed_group |   supported_target |   physical_interventions |   localization_valid_episode |   close_near_episode |   grasp_attempt_episode |   mask_miss_episode |   attempt_and_miss_episode |   persistent_miss_episode |   persistent_miss_and_geometry_episode |   episodes |
|-------------:|-------------------:|-------------------------:|-----------------------------:|---------------------:|------------------------:|--------------------:|---------------------------:|--------------------------:|---------------------------------------:|-----------:|
|            0 |                159 |                        0 |                           70 |                   10 |                      10 |                  24 |                          3 |                         0 |                                      0 |        199 |

## Completed seeds only

| arm           |   count |   mean |   std |   min |   max |
|:--------------|--------:|-------:|------:|------:|------:|
| first_k1      |    1.00 |  55.10 |   nan | 55.10 | 55.10 |
| h8_at72       |    1.00 |  54.75 |   nan | 54.75 | 54.75 |
| max_value_h16 |    1.00 |  53.42 |   nan | 53.42 | 53.42 |
| p3_at72       |    1.00 |  54.10 |   nan | 54.10 | 54.10 |
| p3_event      |    1.00 |  53.42 |   nan | 53.42 | 53.42 |

Std is between-seed descriptive spread, not a task-cluster confidence interval.
