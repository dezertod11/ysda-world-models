"""Decoder-space consensus adapted to the tiled Cosmos action latent.

Reference: Doub1e05/Robotics_project_YSDA, commit
f1bb8d6221a7ee22bd34a72ec642cac244b4f89b (Apache-2.0).
Spatial DiT patches are NOT individual action-time tokens. The incidence
matrix below pulls action-time weights back through the actual decoder layout.
"""
from __future__ import annotations

import numpy as np

NAME = 'decoder_token_medoid_20260911'
ARMS = ('first', 'max_value', 'action_medoid', 'decoder_medoid')
SEED_GROUPS = ((1, 999, 998), (2, 997, 996), (3, 995, 994))
UPSTREAM = 'f1bb8d6221a7ee22bd34a72ec642cac244b4f89b'


def action_patch_incidence(channels, height, width, patch, horizon=16, action_dim=7):
    """Count decoded action scalars from each spatial patch and action time."""
    if min(channels, height, width, patch, horizon, action_dim) < 1:
        raise ValueError('Dimensions must be positive')
    if height % patch or width % patch:
        raise ValueError('Latent grid must be divisible by the spatial patch')
    scalar_count = channels * height * width
    block = horizon * action_dim
    used = scalar_count // block * block
    if used == 0:
        raise ValueError('No complete action copy')
    # extract_action_chunk_from_latent_sequence flattens C,H,W, not H,W,C.
    flat = np.arange(used)
    spatial = flat % (height * width)
    patch_id = (spatial // width // patch) * (width // patch) + spatial % width // patch
    action_time = (flat % block) // action_dim
    counts = np.zeros((height // patch * (width // patch), horizon), dtype=np.int64)
    np.add.at(counts, (patch_id, action_time), 1)
    return counts


def patch_weights(incidence, *, prefix=None, early_count=4, early_weight=4.):
    incidence = np.asarray(incidence)
    if incidence.ndim != 2 or np.any(incidence < 0):
        raise ValueError('Invalid incidence matrix')
    horizon = incidence.shape[1]
    length = horizon if prefix is None else int(prefix)
    if not 1 <= length <= horizon or early_count < 0 or early_weight <= 0:
        raise ValueError('Invalid temporal weights')
    weights = np.zeros(horizon, dtype=np.float64)
    weights[:length] = 1.
    weights[:min(early_count, length)] = early_weight
    result = incidence @ weights
    if not np.isfinite(result).all() or result.sum() <= 0:
        raise ValueError('Empty/non-finite patch weights')
    return result / result.sum()


def token_cosine_medoid(tokens, weights):
    """Aligned token cosine distance, followed by a stable observed medoid."""
    tokens = np.asarray(tokens, dtype=np.float32)
    weights = np.asarray(weights, dtype=np.float64)
    if tokens.ndim != 3 or tokens.shape[0] < 3 or min(tokens.shape[1:]) == 0:
        raise ValueError('Expected at least three [tokens, hidden] candidates')
    if weights.shape != (tokens.shape[1],) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError('Invalid token weights')
    if not np.isfinite(tokens).all() or not np.isfinite(weights).all():
        raise ValueError('Non-finite tokens/weights')
    normalized = tokens / np.maximum(np.linalg.norm(tokens, axis=-1, keepdims=True), 1e-12)
    count = len(tokens)
    distances = np.zeros((count, count), dtype=np.float64)
    for i in range(count):
        for j in range(i + 1, count):
            per_token = 1. - np.clip(np.sum(normalized[i] * normalized[j], axis=-1), -1., 1.)
            distances[i, j] = distances[j, i] = np.average(per_token, weights=weights)
    costs = distances.sum(axis=1) / (count - 1)
    return int(np.argmin(costs)), costs, distances


class ActionHiddenCapture:
    """Read-only capture of the last conditional denoising invocation.

    Only the action slice is retained on the GPU; conversion happens once per
    candidate. Refuse classifier-free guidance and temporal patches mixing
    action/observation frames instead of silently capturing the wrong branch.
    """
    def __init__(self, model, action_index=4):
        self.net = model.net
        if self.net.patch_temporal != 1 or self.net.is_context_parallel_enabled:
            raise ValueError('Only unsharded temporal-patch-1 Cosmos is supported')
        if any(e.dropout_rate > 1e-4 for e in model.conditioner.embedders.values()):
            raise ValueError('Unconditional guidance branch is not supported')
        if getattr(model.config, 'use_flowunipc_scheduler', False):
            raise ValueError('FlowUniPC guidance branch is not supported')
        self.action_index = action_index
        self.hidden = None
        self.calls = 0
        self.input_shapes = []
        self.handle = self.net.final_layer.register_forward_pre_hook(self._capture)

    def _capture(self, _module, inputs):
        hidden = inputs[0]
        if hidden.ndim != 5 or hidden.shape[0] != 1 or hidden.shape[1] != 9:
            raise ValueError('Expected LIBERO [1,9,Hpatch,Wpatch,D] decoder grid')
        self.hidden = hidden[0, self.action_index].detach().clone()
        self.input_shapes.append(list(hidden.shape))
        self.calls += 1

    def finish(self, sample):
        if self.hidden is None or not self.calls:
            raise ValueError('No action hidden state captured')
        if sample['latent_indices']['action_latent_idx'] != self.action_index:
            raise ValueError('Action frame contract changed')
        latent = sample['generated_latent']
        _, channels, time, height, width = latent.shape
        if time != 9 or self.hidden.shape[:2] != (height // self.net.patch_spatial, width // self.net.patch_spatial):
            raise ValueError('Hidden/output grids do not agree')
        incidence = action_patch_incidence(channels, height, width, self.net.patch_spatial)
        features = self.hidden.float().cpu().numpy().reshape(-1, self.hidden.shape[-1])
        if not np.isfinite(features).all():
            raise ValueError('Non-finite decoder activations')
        return features, incidence, dict(calls=self.calls, shapes=self.input_shapes,
            latent_shape=list(latent.shape), action_index=self.action_index,
            patch_spatial=self.net.patch_spatial, patch_temporal=self.net.patch_temporal,
            block_count=len(self.net.blocks), stage='last_conditional_forward_before_final_layer')

    def close(self):
        self.handle.remove()
        self.hidden = None


def make_jobs():
    cells = [('Object', '', 'libero_object_object', (0, 1)),
             ('Environment', '', 'libero_object_env', (0, 1)),
             ('Position', 'x0.2', 'libero_object_temp', (0,)),
             ('Position', 'y0.2', 'libero_object_temp', (0,))]
    jobs = []
    # Interleave groups/tasks/factors; a deadline must not only sample group 0.
    for init_slot in range(2):
        for task in range(10):
            for group in range(3):
                for factor, level, suite, inits in cells:
                    if init_slot >= len(inits):
                        continue
                    init = inits[init_slot]
                    jobs.append(dict(id=f'{factor}_{level or "base"}_t{task}_i{init}_g{group}',
                        phase='screen', factor=factor, level=level, suite=suite,
                        task_id=task, init_state_id=init, seed_group=group,
                        candidate_seeds=list(SEED_GROUPS[group]),
                        env_seed=170000000 + cells.index((factor, level, suite, inits)) * 1000000 + task * 1000 + init))
    smoke = [dict(next(j for j in jobs if j['factor'] == factor), phase='smoke')
             for factor in ('Object', 'Environment', 'Position')]
    return smoke + jobs
