# MLSpace SR006: Cosmos Policy + LIBERO-PRO

## Paths

- SSH host: `mlspace-sr006`
- Project:
  `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP`
- Environment:
  `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos`
- Results:
  `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/uncertainty`
- Model-eval videos:
  `/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/cosmos-policy/rollouts`

The local project remains authoritative. The server copy has no `.git` directories
and contains no GitHub, Hugging Face, or W&B tokens.

### Storage exception, September 11

NFS2 reached zero free space before `observation_contract_20260911` started.
The canonical project and environment paths have not changed. Only this new
campaign directory is a symlink to the separate project-owned directory
`/home/jovyan/.local/share/malnev_world_model_spill/observation_contract_20260911`
on the NFS-home volume, which had about 2 TB available. This is persistent
server storage, not node-local `/tmp`, and contains no credentials.

An old unused `.runtime/libero_safety/libero_t5_embeddings.pkl.backup` was
copied to `malnev_world_model_spill/preserved_backups/`, SHA256-verified, then
replaced by a symlink at its old path. The active T5 file was not modified.
Details and checksum: [observation protocol](experiments/OBSERVATION_CONTRACT_PROTOCOL_20260911.md).
No previous experiment artifacts were removed. Do not overwrite the campaign
symlink with a blanket project sync. To download its actual contents, use the
canonical campaign path with a trailing slash as the rsync source.

## Project layout

- `ysda_world_models.ipynb`: executable experiments and result analysis.
- `ysda_world_models_research.ipynb`: literature review and research direction.
- `experiments/uncertainty`: collected traces, metrics, plots, and videos.
- `articles`: local paper PDFs.
- `scripts`: setup, collectors, analysis, and experiment launchers.
- `cosmos-policy`: Cosmos Policy plus the local uncertainty/planning changes.
- `LIBERO-PRO`: OOD simulator and benchmark definitions.

## First setup

```bash
cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
bash scripts/setup_mlspace_cosmos.sh
```

The setup creates a Python 3.10 environment, installs the Cosmos Policy CUDA 12.8
dependencies, installs the local LIBERO-PRO checkout, registers the
`ysda-cosmos-policy-libero` Jupyter kernel, applies the robosuite logical-EGL
device compatibility patch, and verifies CUDA/import paths.

## Every shell session

```bash
cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
source scripts/mlspace_env.sh
```

`mlspace_env.sh` defaults to physical GPU 2 and rejects physical GPU 0 without
explicit authorization. The idle-only campaign queue passes that authorization
only to an admitted GPU0 worker. Inside
PyTorch the only visible physical GPU is named `cuda:0`.

Before a long run:

```bash
nvidia-smi
nvidia-smi pmon -c 1
```

Choose another training GPU when needed:

```bash
export CUDA_VISIBLE_DEVICES=3
source scripts/mlspace_env.sh
```

GPU policy, amended by the user on 2026-09-09 for this project:

- Physical GPUs 0-7 may be used when idle; do not start alongside another
  project's CUDA process just because utilization is low.
- GPU0 requires `--allow-gpu-zero` and a dynamic idle-only campaign. The current
  consensus/P5 launcher supplies this explicit opt-in automatically.
- Admission requires two idle readings, memory below 256 MiB, utilization
  below 5%, and no compute processes. Unknown GPU status is treated as busy.
- Never stop or reconfigure other users' processes. This admission check is
  not a reservation against a third party starting later; stronger isolation
  requires coordination or a shared resource scheduler.

[Current resource amendment and restart](experiments/GPU07_RESOURCE_POLICY_20260909.md).

The reference campaign also has a parity-gated resident executor: up to eight
compatible jobs share one model load, while bounded CPU workers encode videos
and build reports. Idle admission applies before each batch; existing model
work continues between its jobs without requiring an empty GPU again.
This is not a GPU reservation. P5 remains on its original executor.
See [resident protocol and deployment status](experiments/RESIDENT_WORKER_PROTOCOL_20260909.md).

## Smoke tests

Environment and import paths:

```bash
source scripts/mlspace_env.sh
python scripts/verify_mlspace_cosmos.py
```

LIBERO-PRO simulator:

```bash
source scripts/mlspace_env.sh
python scripts/smoke_libero_pro_simulator.py
```

One model evaluation:

```bash
source scripts/mlspace_env.sh
LIBERO_PRO_NUM_TRIALS=1 LIBERO_PRO_MAX_TASKS=1 \
  scripts/run_libero_pro_eval_smoke.sh
```

The shared server Hugging Face cache already contains the required NVIDIA
checkpoints. `mlspace_env.sh` enables `HF_HUB_OFFLINE=1`, so no access token is
needed or stored in the project.

### E0 denoising trace and VFD sanity check

Run the pure and sampler-level checks:

```bash
source scripts/mlspace_env.sh
PYTHONPATH=cosmos-policy python -m pytest -q \
  cosmos-policy/tests/test_vfd_metrics.py
```

Run one real Cosmos Policy query with and without tracing:

```bash
source scripts/mlspace_env.sh
python scripts/smoke_cosmos_vfd_e0.py
```

The report is written to
`experiments/uncertainty/vfd_e0_smoke.json`. A full collector can enable the
compact metrics with `--record-denoising-trace` in either `collect` or
`collect-paired` mode. The resulting `flow_path_*` columns compare stochastic
paths of one checkpoint; they are not cross-model epistemic VFD. Exact VFD
requires two or more independently trained model/LoRA members and
cross-evaluation of each member along every member trajectory.

Verified on 2026-07-23:

- E0 suite: 7/7 tests passed;
- tracing left both the action and full generated latent bitwise unchanged;
- the four solver evaluations were recorded for a five-step policy query;
- duplicated-model exact VFD was zero for action, future proprio, future image,
  wrist image, and value blocks;
- the end-to-end collector wrote 20 `flow_path_*` fields.

Verified on 2026-07-23 with physical GPU 2:

- Python 3.10.18 and PyTorch 2.7.0+cu128;
- H100 80 GB visible inside the process as `cuda:0`;
- headless LIBERO-PRO reset and stepping through EGL;
- complete one-trial Cosmos Policy evaluation;
- task success rate: 1/1 (100%);
- GPU memory released after the process exited.

## OOD and safety campaigns

The experiment matrix, failure definitions, and statistical protocol are in
`experiments/LIBERO_OOD_SAFETY_CAMPAIGN.md`. Campaign profiles are stored in
`experiments/configs/libero_campaign_v1.json`.

List profiles and render commands without running:

```bash
source scripts/mlspace_env.sh
python scripts/run_libero_experiment_campaign.py --list
python scripts/run_libero_experiment_campaign.py \
  --profile smoke \
  --run-prefix smoke_v1 \
  --gpus 2
```

Run a profile on multiple physical GPUs:

```bash
python scripts/run_libero_experiment_campaign.py \
  --profile boundary_search \
  --run-prefix boundary_v1 \
  --gpus 2,3,4,5,6,7 \
  --execute
```

Reuse the same `--run-prefix` after an interruption. Completed jobs are skipped.
All logs, traces, plots, videos, and completion markers are grouped under
`experiments/campaigns/<run-prefix>`.

### LIBERO-Safety

LIBERO-Safety must use a separate environment because it installs its own
`libero` package and robosuite fork:

```bash
bash scripts/setup_mlspace_libero_safety.sh
```

The setup pins the upstream source commit, downloads the public safety assets,
registers the `ysda-cosmos-policy-libero-safety` kernel, and verifies all five
15-task suites. The extracted archive has about 903,000 files, so it is kept in
the node-local `/tmp` scratch and linked into the checkout. Re-run setup after a
node restart; the downloaded archive remains cached. Then run:

```bash
COSMOS_VENV="$PWD/.venv-cosmos-safety" \
  source scripts/cosmos_env_libero_safety.sh
python scripts/verify_mlspace_libero_safety.py --simulator-smoke

python scripts/run_libero_experiment_campaign.py \
  --profile safety_physical \
  --run-prefix safety_v1 \
  --gpus 2,3,4,5 \
  --execute
```

## Notebook

Open `ysda_world_models.ipynb` and select:

```text
YSDA Cosmos Policy LIBERO (MLSpace Py3.10)
```

Restart the kernel and run the first setup cell before importing `torch`,
`mujoco`, or `libero`.

## Synchronization

The local tree is authoritative for source code, papers, and research notes.
The server is authoritative for newly generated experiment outputs. Pull results
before pushing source changes. Never use `--delete`.

Campaigns such as `observation_contract_20260911` and
`decoder_token_medoid_20260911` have intentional directory symlinks to the
free persistent home volume. A plain `rsync -aR` with a nested campaign file
can replace that destination symlink with a real directory. For explicitly
verified project-owned destination links, use `--keep-dirlinks --no-perms`,
or address the campaign directory directly with a trailing slash and transfer
only the intended file. Verify `readlink` after synchronization. Never push
stale local `sequence_status.json`, `launch.json`, `budget.json`, or lock files
over a live server campaign. The decoder-medoid link was restored and its
waiting dispatcher restarted on September 11 at 21:41 MSK; no GPU run was lost.

From WSL:

```bash
LOCAL=/mnt/d/Projects/YSDA/YSDA_WORD_MODELS_PP
REMOTE=/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP

rsync -a --no-perms --partial \
  "mlspace-sr006:$REMOTE/experiments/uncertainty/" \
  "$LOCAL/experiments/uncertainty/"

rsync -a --no-perms --partial \
  "mlspace-sr006:$REMOTE/cosmos-policy/rollouts/" \
  "$LOCAL/cosmos-policy/rollouts/"
```

Push the research notebook and papers:

```bash
rsync -a --no-perms --partial \
  "$LOCAL/ysda_world_models_research.ipynb" \
  "mlspace-sr006:$REMOTE/ysda_world_models_research.ipynb"

rsync -a --no-perms --partial \
  "$LOCAL/articles/" \
  "mlspace-sr006:$REMOTE/articles/"
```

The local `ysda_world_models.ipynb` keeps historical outputs and is therefore
large. The server copy intentionally has outputs cleared. Their full-file hashes
are different, while their cell types and source text must remain identical.
Do not overwrite the local notebook with the clean server copy merely to make
hashes equal.

Exclude `.git`, `.venv-cosmos`, `.runtime`, credentials, and W&B/Hugging Face
tokens from every source-code upload. Use `--no-perms` because the server uses a
shared `jovyan` UID and its permissions should not be copied back to WSL.

Do not store credentials in the server project. Use W&B offline mode and sync
the run from the local machine if W&B logging is needed.
