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

`mlspace_env.sh` defaults to physical GPU 2 and rejects physical GPU 0. Inside
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

GPU policy:

- GPU 0: never use.
- GPU 1: short tests only when free.
- GPU 2-7: experiments and training.

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
