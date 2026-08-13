# Source patches

The repository keeps local changes to third-party projects as patches instead
of vendoring complete upstream Git histories.

| Project | Upstream revision | Patch |
| --- | --- | --- |
| NVIDIA Cosmos Policy | `18a2accadf4e7a3531e56754102af5a24d2316da` | `cosmos-policy-ysda.patch` |
| LIBERO-PRO | `eafdb809426b13153aa1e4c42d6601844217dfec` | `libero-pro-ysda.patch` |

`cosmos-policy-ysda.patch` contains the policy sampling, uncertainty metrics,
fixed and adaptive planning selection, candidate-level diagnostics, replay
controls, VFD/safety instrumentation and focused tests used in the experiments.
`libero-pro-ysda.patch` contains the OOD benchmark definitions,
BDDL tasks and initialization states used by the project.

Restore both checkouts from the repository root:

```bash
./scripts/bootstrap_source_checkouts.sh
```

The patches were validated with `git apply --check` against clean clones at the
revisions above. Generated rollouts, caches, model weights and logs are not part
of either patch.
