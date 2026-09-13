# Technical smoke attempt: do not include in scientific results

Dispatcher26970 was stopped by SIGTERM at22:35 MSK, 10 September2026.
All its workers exited; screen/holdout never started. 16 committed smoke
branches are retained, along with `config.json` and `source_v1/`.

The new verifier compared optical flow in native OpenGL observations to EEF
projection in OpenCV camera coordinates. The raw image rows must be reflected
for tracking. This was detected from opposite vertical flow signs and verified
with a geometry-only render/segmentation audit, without fitting to outcomes.

`camera_audit/summary.json` and `camera_audit/orientation.png` contain the
diagnosis. GT geometry is used only for this offline technical audit.
Historical P3c/localizer and the completed P5/feedback campaigns were not edited.

The replacement is `probe_verify_repair_20260910_v2`. Same scientific manifest,
thresholds and arm definitions; coordinate conversion is the only policy-path
correction. Repeat all smoke branches; never merge v1 and v2 success counts.
