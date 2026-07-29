#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cosmos_env.sh"
cd "$COSMOS_REPO"

python -m cosmos_policy.experiments.robot.libero.run_libero_eval \
  --config cosmos_predict2_2b_480p_libero__inference_only \
  --ckpt_path nvidia/Cosmos-Policy-LIBERO-Predict2-2B \
  --config_file cosmos_policy/config/config.py \
  --use_wrist_image True \
  --use_proprio True \
  --normalize_proprio True \
  --unnormalize_actions True \
  --dataset_stats_path nvidia/Cosmos-Policy-LIBERO-Predict2-2B/libero_dataset_statistics.json \
  --t5_text_embeddings_path nvidia/Cosmos-Policy-LIBERO-Predict2-2B/libero_t5_embeddings.pkl \
  --trained_with_image_aug True \
  --chunk_size 16 \
  --num_open_loop_steps 16 \
  --task_suite_name libero_spatial \
  --num_trials_per_task 1 \
  --max_eval_tasks 1 \
  --local_log_dir cosmos_policy/experiments/robot/libero/logs/ \
  --randomize_seed False \
  --data_collection False \
  --available_gpus "0" \
  --seed 195 \
  --use_variance_scale False \
  --deterministic True \
  --run_id_note local-smoke-libero-spatial \
  --ar_future_prediction False \
  --ar_value_prediction False \
  --use_jpeg_compression True \
  --flip_images True \
  --num_denoising_steps_action 5 \
  --num_denoising_steps_future_state 1 \
  --num_denoising_steps_value 1
