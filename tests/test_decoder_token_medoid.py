import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.decoder_token_medoid import (
    ARMS, SEED_GROUPS, ActionHiddenCapture, action_patch_incidence, make_jobs,
    patch_weights, token_cosine_medoid,
)


def test_layout_matches_literal_c_h_w_flatten_and_ignores_partial_copy():
    for channels, height, width, patch in ((16, 28, 28, 2), (3, 8, 8, 2), (1, 4, 28, 1)):
        result = action_patch_incidence(channels, height, width, patch)
        expected = np.zeros_like(result)
        used = channels * height * width // 112 * 112
        for c in range(channels):
            for h in range(height):
                for w in range(width):
                    flat = (c * height + h) * width + w
                    if flat < used:
                        expected[h // patch * (width // patch) + w // patch, flat % 112 // 7] += 1
        np.testing.assert_array_equal(result, expected)
        np.testing.assert_array_equal(result.sum(0), np.full(16, used // 16))


def test_weighted_cosine_matches_upstream_function():
    root = Path(__file__).resolve().parents[1]
    relative = Path('scripts/eval/groot_n17_decoder_action_token_medoid_server.py')
    path = root / '.external/Robotics_project_YSDA' / relative
    if not path.exists():
        path = root / 'experiments/campaigns/decoder_token_medoid_20260911/reference' / relative
    if not path.exists():
        pytest.skip('Optional isolated upstream checkout not present')
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    function = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_costs')
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {'np': np}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    tokens = np.random.default_rng(5).normal(size=(3, 16, 13)).astype(np.float32)
    original = namespace['_costs']([t[None] for t in tokens])[0]
    selected, costs, distances = token_cosine_medoid(tokens, patch_weights(np.eye(16)))
    np.testing.assert_allclose(costs, original, atol=1e-12, rtol=0)
    assert selected == original.argmin()
    np.testing.assert_array_equal(distances, distances.T)


def test_weights_are_nonuniform_but_spatial_tokens_mix_action_times():
    incidence = action_patch_incidence(16, 28, 28, 2)
    assert incidence.shape == (196, 16)
    assert np.max(np.count_nonzero(incidence, axis=1)) > 1
    weights = patch_weights(incidence)
    assert weights.max() > weights.min()
    assert weights.sum() == pytest.approx(1.)
    assert not np.array_equal(weights, patch_weights(incidence, prefix=8))


def test_no_early_weight_is_uniform_for_complete_layout():
    incidence = action_patch_incidence(16, 28, 28, 2)
    np.testing.assert_allclose(patch_weights(incidence, early_weight=1.), np.full(196, 1 / 196))


def test_cosine_scale_invariance_stable_tie_and_bad_input():
    tokens = np.array([[[1., 0]], [[1., 1]], [[0., 1]]])
    assert token_cosine_medoid(tokens, [1.])[0] == 1
    np.testing.assert_allclose(token_cosine_medoid(tokens, [1.])[1],
        token_cosine_medoid(tokens * np.array([2., 8., .3])[:, None, None], [1.])[1], atol=1e-7)
    assert token_cosine_medoid(np.ones((3, 2, 4)), [1., 1.])[0] == 0
    with pytest.raises(ValueError):
        token_cosine_medoid(tokens[:2], [1.])
    with pytest.raises(ValueError):
        token_cosine_medoid(tokens * np.nan, [1.])


def test_capture_last_action_slice_only_and_no_mutation():
    import torch
    class Net:
        patch_temporal = 1
        patch_spatial = 2
        is_context_parallel_enabled = False
        blocks = list(range(28))
        final_layer = torch.nn.Identity()
    model = SimpleNamespace(net=Net(), conditioner=SimpleNamespace(embedders={}),
                            config=SimpleNamespace(use_flowunipc_scheduler=False))
    reader = ActionHiddenCapture(model)
    before = torch.randn(1, 9, 14, 14, 4)
    newer = before + 3
    try:
        torch.testing.assert_close(model.net.final_layer(before), before, rtol=0, atol=0)
        model.net.final_layer(newer)
        hidden, incidence, audit = reader.finish(dict(generated_latent=torch.zeros(1, 16, 9, 28, 28),
            latent_indices={'action_latent_idx': 4}))
        np.testing.assert_array_equal(hidden, newer[0, 4].numpy().reshape(196, 4))
        assert audit['calls'] == 2
        assert incidence.sum() == 12544
    finally:
        reader.close()
    assert not model.net.final_layer._forward_pre_hooks
    model.config.use_flowunipc_scheduler = True
    with pytest.raises(ValueError):
        ActionHiddenCapture(model)


def test_paired_design_all_factors_tasks_seed_groups_without_t72():
    jobs = make_jobs()
    assert len(jobs) == 183
    assert len(ARMS) == 4
    screen = [j for j in jobs if j['phase'] == 'screen']
    assert len({j['id'] for j in screen}) == 180
    for factor in ('Object', 'Environment', 'Position'):
        rows = [j for j in screen if j['factor'] == factor]
        assert len(rows) == 60
        assert {j['task_id'] for j in rows} == set(range(10))
        assert {tuple(j['candidate_seeds']) for j in rows} == set(SEED_GROUPS)
    assert all('prefix_t' not in j for j in jobs)


def test_analysis_excludes_incomplete_pairs_and_preserves_clustering():
    from scripts.analyze_decoder_token_medoid import matched_tables
    rows = []
    for task in range(3):
        for group in range(3):
            for arm in ARMS:
                rows.append(dict(id=f't{task}g{group}', arm=arm, factor='Object', task_id=task,
                    terminal_success=arm == 'decoder_medoid', initial_sha256='initial', q0_pool_sha256='pool',
                    task_description='instruction', env_seed=0, terminal_final_t=280, elapsed_seconds=1.,
                    candidate_calls_logical=54))
    rows.append(dict(rows[0], id='incomplete'))
    summary, rates, pairs, matched = matched_tables(rows, expected=9)
    assert summary['complete_pairs'] == 9
    assert summary['available_rollouts'] == 37
    assert len(matched) == 36
    result = pairs.set_index('arm').loc['decoder_medoid']
    assert result.rescue == 9 and result.harm == 0
    assert result.cluster_ci_low == result.cluster_ci_high == result.macro_delta == 1.
    rows[1]['q0_pool_sha256'] = 'changed'
    with pytest.raises(ValueError, match='Paired contract'):
        matched_tables(rows)
