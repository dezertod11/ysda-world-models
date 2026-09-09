# Cosmos query reproducibility diagnostic

## Question

The separate-process deployment experiments sometimes diverged before the
query-4 intervention despite identical LIBERO simulator states. This diagnostic
tests whether repeating the same Cosmos query is reproducible within one model
process and across two freshly loaded processes.

The diagnostic is explanatory only. It does not change the frozen controller,
endpoint or gates of the shared-prefix efficacy experiment.

## Design

- Suite/task: `libero_object_object`, task 0.
- Init states: 0, 16 and 41.
- Query: the initial observation (`query=0`).
- Candidate seeds: 0, 1, 2 and 3.
- Each process repeats the identical four-candidate query twice.
- Two freshly loaded processes are compared for each runtime mode.
- Compared tensors: complete action chunks, candidate values and selected
  `argmax(value)` indices.
- Frozen numerical tolerance: `1e-5` for actions and values.

`default` uses the normal Cosmos runtime. `warn` requests deterministic
algorithms with `warn_only=True`, disables TF32 and sets
`CUBLAS_WORKSPACE_CONFIG=:4096:8`.

## Results

| Runtime | Within-process exact | Cross-process action max abs diff | Cross-process value max abs diff | Selected-index match | Cross-process strict |
|---|---:|---:|---:|---:|---:|
| `default` | yes | 0.0074497 | 0.0003763 | 3/3 | no |
| `warn` | yes | 0.0050989 | 0.0004331 | 3/3 | no |

For tensors $A_{p,r,i,k,t,d}$ and values $V_{p,r,i,k}$, where $p$ is the
process, $r$ the repeated call, $i$ the init state and $k$ the stochastic
candidate, the reported differences are

$$
D_A=\max_{r,i,k,t,d}|A_{1,r,i,k,t,d}-A_{2,r,i,k,t,d}|,
\qquad
D_V=\max_{r,i,k}|V_{1,r,i,k}-V_{2,r,i,k}|.
$$

Both $D_A$ and $D_V$ are exactly zero between repeated calls inside each
individual process. They exceed `1e-5` between freshly loaded processes.

Strict deterministic mode (`warn_only=False`) could not execute the model. It
disabled every CUDA scaled-dot-product attention kernel available to this
Cosmos/PyTorch build and stopped with `RuntimeError: No available kernel`.
This is a runtime compatibility result, not an efficacy failure.

## Interpretation

The earlier common-prefix failure is consistent with process-level CUDA/model
nondeterminism rather than observation mismatch: identical calls are stable
inside a process but not bitwise reproducible after loading the model in a new
process. The tested perturbation was too small to change `argmax(value)` on the
three diagnostic states, but closed-loop execution can amplify small action
differences over four queries.

`warn` mode reduced the largest action difference but did not make inference
strictly reproducible, so it is not a repair for separate-process pairing. The
valid counterfactual design is to generate the prefix and candidate pool once,
capture the full environment/controller state, and evaluate both terminal
branches in that same process. That design is used by the frozen shared-prefix
replication.

## Artifacts

Machine-readable results are in
[`campaigns/cosmos_query_reproducibility_20260902/analysis/summary.json`](campaigns/cosmos_query_reproducibility_20260902/analysis/summary.json).
Raw `.npz` tensors and per-process metadata remain in the campaign `raw/`
directory on the experiment server.
