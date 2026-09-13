"""Predeclared deadline plan and controls for the frozen decoder-medoid study."""
from __future__ import annotations

from datetime import datetime
import math

BASE_CONFIG_SHA256 = '455587b0624f8253d5fc8b6c4b6dab8a0bc57aed64a8afa770f29e9cd8d49ac4'
DEADLINE = '2026-09-12T10:00:00+03:00'
PLAN_FILE = 'night_plan_20260912_1000.json'
STAGES = ('smoke', 'screen', 'seed_controls', 'horizon8')
EXTENSIONS = {
    'fixed_candidate_1': dict(horizon=16, fixed_index=1),
    'fixed_candidate_2': dict(horizon=16, fixed_index=2),
    'max_value_h8': dict(horizon=8, selector='max_value'),
    'decoder_full_h8': dict(horizon=8, selector='decoder_medoid'),
    'decoder_prefix_h8': dict(horizon=8, selector='prefix8'),
}
STAGE_ARMS = {
    'smoke': (),
    'screen': ('first', 'max_value', 'action_medoid', 'decoder_medoid'),
    'seed_controls': ('fixed_candidate_1', 'fixed_candidate_2'),
    'horizon8': ('max_value_h8', 'decoder_full_h8', 'decoder_prefix_h8'),
}
FLOOR_SECONDS = dict(smoke=180, screen=600, seed_controls=240, horizon8=900)


def deadline_times():
    end = datetime.fromisoformat(DEADLINE).timestamp()
    return dict(deadline_epoch=end, compute_deadline_epoch=end - 1200,
                report_deadline_epoch=end - 120, kill_deadline_epoch=end - 1080)


def ordered_jobs(base_jobs):
    """Latin seed ordering spreads early coverage across tasks and factors."""
    cells = [('Object', ''), ('Environment', ''), ('Position', 'x0.2'), ('Position', 'y0.2')]
    screen = [dict(j) for j in base_jobs if j['phase'] == 'screen']
    def key(j):
        cell = cells.index((j['factor'], j['level']))
        round_id = (j['seed_group'] - j['task_id'] - cell) % 3
        return j['init_state_id'], round_id, j['task_id'], cell
    screen.sort(key=key)
    return ([dict(j) for j in base_jobs if j['phase'] == 'smoke'] + screen
        + [dict(j, phase='seed_controls', parent_phase='screen') for j in screen]
        + [dict(j, phase='horizon8', parent_phase='screen') for j in screen if j['init_state_id'] == 0])


def group_estimate(stage, durations):
    values = sorted(float(x) for x in durations if math.isfinite(x) and x > 0)
    observed = values[max(0, math.ceil(.95 * len(values)) - 1)] * 1.5 if values else 0
    return max(FLOOR_SECONDS[stage], observed)


def admissible_batch(stage, remaining_seconds, available, durations=()):
    # Reserve a model bootstrap and save/close allowance; never shorten an episode.
    per_group = group_estimate(stage, durations)
    return max(0, min(3, available, int((remaining_seconds - 180) // per_group)))


def extension_choice(arm, choices, diagnostic):
    spec = EXTENSIONS[arm]
    if 'fixed_index' in spec:
        return spec['fixed_index']
    if spec['selector'] == 'prefix8':
        return int(diagnostic['prefix8_diagnostic_index'])
    return int(choices[spec['selector']])
