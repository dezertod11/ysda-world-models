"""State-conditioned feedback; no absolute episode time is a decision feature.

Thresholds are development hyperparameters, not calibrated failure probabilities.
The pure control loop is also used by CPU replay tests and the LIBERO collector.
"""
from collections import deque
from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np


METHODS = ('requery', 'regrasp', 'preserve_probe', 'verify_regrasp')


@dataclass(frozen=True)
class EventConfig:
    generated_horizon: int = 16
    execution_horizon: int = 16
    monitor_stride: int = 4
    min_prefix: int = 8
    history_steps: int = 8
    persistence: int = 2
    cooldown_steps: int = 16
    max_interventions: int = 1
    max_steps: int = 280
    action_std_threshold: float = .25
    value_std_threshold: float = .10
    overlap_rmse_threshold: float = .30
    commanded_motion_threshold: float = .20
    stalled_eef_threshold_m: float = .002
    grasp_near_m: float = .06
    action_scale: tuple = (1., 1., 1., 1., 1., 1., 1.)

    def __post_init__(self):
        integers = (self.generated_horizon, self.execution_horizon, self.monitor_stride,
                    self.min_prefix, self.history_steps, self.persistence,
                    self.cooldown_steps, self.max_interventions, self.max_steps)
        if any(type(x) is not int for x in integers):
            raise ValueError('Step counts must be integers')
        if min(integers[:6]) <= 0 or min(integers[6:]) < 0 or self.max_steps == 0:
            raise ValueError('Invalid step counts or budget')
        if not self.min_prefix < self.execution_horizon <= self.generated_horizon:
            raise ValueError('Need min_prefix < execution_horizon <= generated_horizon')
        if self.history_steps % self.monitor_stride or self.min_prefix % self.monitor_stride:
            raise ValueError('History and prefix must be divisible by monitor stride')
        positive = (self.action_std_threshold, self.value_std_threshold,
                    self.overlap_rmse_threshold, self.commanded_motion_threshold,
                    self.stalled_eef_threshold_m, self.grasp_near_m)
        if not np.isfinite(positive).all() or min(positive) <= 0:
            raise ValueError('Thresholds must be positive and finite')
        if len(self.action_scale) != 7 or not np.isfinite(self.action_scale).all() or min(self.action_scale) <= 0:
            raise ValueError('Need seven positive action scales')


def chunk_metrics(actions, values, config):
    """Population std across samples, then mean over prefix positions and axes."""
    a, v = np.asarray(actions, dtype=float), np.asarray(values, dtype=float)
    if (a.ndim != 3 or a.shape[1:] != (config.generated_horizon, 7)
            or a.shape[0] < 1 or v.shape != (len(a),)
            or not np.isfinite(a).all() or not np.isfinite(v).all()):
        raise ValueError('Expected finite K x H x 7 actions and K values')
    scaled = a / np.asarray(config.action_scale)
    return dict(action_prefix_std=float(scaled[:, :config.min_prefix, :6].std(axis=0).mean()),
                gripper_prefix_std=float(a[:, :config.min_prefix, 6].std(axis=0).mean()),
                value_std=float(v.std()), value_range=float(np.ptp(v)), samples=len(a))


class PlanMemory:
    """Only compare predictions for the same physical action indices."""
    def __init__(self, config):
        self.config = config
        self.previous = None

    def update(self, t, actions, selected):
        a = np.asarray(actions, dtype=float)
        if self.previous is None:
            result = dict(overlap_steps=0, overlap_pose_rmse=None, overlap_gripper_disagreement=None)
        else:
            old_t, old = self.previous
            if t <= old_t:
                raise ValueError('Query timestamps must strictly increase')
            n = max(0, min(old_t + len(old), t + len(a[selected])) - t)
            result = dict(overlap_steps=n, overlap_pose_rmse=None, overlap_gripper_disagreement=None)
            if n:
                previous = old[t - old_t:t - old_t + n]
                current = a[selected, :n]
                delta = (previous[:, :6] - current[:, :6]) / np.asarray(self.config.action_scale[:6])
                result.update(overlap_pose_rmse=float(np.sqrt(np.mean(delta ** 2))),
                              overlap_gripper_disagreement=float(np.mean(
                                  (previous[:, 6] > 0) != (current[:, 6] > 0))))
        self.previous = (t, a[selected].copy())
        return result

    def clear(self):
        self.previous = None


@dataclass(frozen=True)
class Evidence:
    # Typed whitelist: simulator object poses, success labels and query index are absent.
    eef: tuple
    gripper_command: float
    commanded_motion: float
    target_distance: float | None = None
    localization_valid: bool = False
    geometry_allowed: bool = False
    probe_allowed: bool = False
    grasp_verdict: str = 'unknown'

    def __post_init__(self):
        if len(self.eef) != 3 or not np.isfinite(self.eef).all():
            raise ValueError('Invalid EEF observation')
        if (not np.isfinite([self.gripper_command, self.commanded_motion]).all()
                or self.commanded_motion < 0):
            raise ValueError('Invalid executed action evidence')
        if self.target_distance is not None and (
                not np.isfinite(self.target_distance) or self.target_distance < 0):
            raise ValueError('Invalid target distance')
        if self.grasp_verdict not in ('held', 'miss', 'unknown'):
            raise ValueError('Unknown grasp verdict')


class EventController:
    def __init__(self, config, method='requery'):
        if method not in METHODS:
            raise ValueError('Unknown method')
        self.config, self.method = config, method
        self.history = deque(maxlen=config.history_steps // config.monitor_stride + 1)
        self.last_intervention = None
        self.interventions = 0
        self.grasp_attempt = False
        self.streaks = {'stalled': 0, 'miss': 0}

    def available(self, t):
        return self.interventions < self.config.max_interventions and (
            self.last_intervention is None or t - self.last_intervention >= self.config.cooldown_steps)

    def query_reasons(self, metrics):
        reasons = []
        if metrics['samples'] >= 2 and metrics['action_prefix_std'] > self.config.action_std_threshold:
            reasons.append('action_sample_disagreement')
        if metrics['samples'] >= 2 and metrics['value_std'] > self.config.value_std_threshold:
            reasons.append('value_sample_disagreement')
        if (metrics.get('overlap_pose_rmse') is not None
                and metrics['overlap_pose_rmse'] > self.config.overlap_rmse_threshold):
            reasons.append('past_plan_disagreement_after_query')
        return reasons

    def observe(self, t, evidence):
        if self.history and t <= self.history[-1][0]:
            raise ValueError('Do not count the same observation twice')
        if evidence.gripper_command <= 0:
            self.grasp_attempt = False
        elif (evidence.localization_valid and evidence.target_distance is not None
              and evidence.target_distance <= self.config.grasp_near_m):
            self.grasp_attempt = True
        self.history.append((t, evidence))
        old_t, old = self.history[0]
        full = t - old_t >= self.config.history_steps
        travel = sum(e.commanded_motion for _, e in list(self.history)[1:])
        displacement = float(np.linalg.norm(np.asarray(evidence.eef) - old.eef))
        stalled = (full and travel >= self.config.commanded_motion_threshold
                   and displacement < self.config.stalled_eef_threshold_m)
        # Absence of motion alone is not a missed grasp; require a prior close near the target.
        miss = self.grasp_attempt and evidence.grasp_verdict == 'miss'
        for key, active in (('stalled', stalled), ('miss', miss)):
            self.streaks[key] = self.streaks[key] + 1 if active else 0
        reasons = [key for key, count in self.streaks.items() if count >= self.config.persistence]
        return dict(reasons=reasons, grasp_attempt=self.grasp_attempt,
                    streaks=dict(self.streaks), history_span=t - old_t,
                    eef_displacement_m=displacement, commanded_motion=travel)

    def route(self, evidence):
        # No release, including the old probe+open route, on held/unknown evidence.
        miss = self.grasp_attempt and evidence.grasp_verdict == 'miss'
        if not miss:
            return 'requery'
        if self.method in ('regrasp', 'verify_regrasp') and evidence.geometry_allowed:
            return self.method
        if self.method == 'preserve_probe' and evidence.probe_allowed:
            return 'preserve_probe'
        return 'requery'

    def mark(self, t):
        if not self.available(t):
            raise ValueError('Intervention budget exhausted')
        self.interventions += 1
        self.last_intervention = t
        self.reset_evidence()

    def reset_evidence(self):
        self.history.clear()
        self.streaks = {'stalled': 0, 'miss': 0}
        self.grasp_attempt = False


def run_control_loop(obs, *, policy: Callable, step: Callable, monitor: Callable,
                     intervene: Callable, config=EventConfig(), method='requery',
                     timing='event', fixed_step=None, check=lambda: None):
    """Run from the first observation to terminal; callbacks never see future labels.

    policy(obs,t,q) returns K candidates, K values and serializable metadata.
    step(action) returns (obs, success). intervene(kind,obs,t,budget) returns
    (obs, success, executed_actions, diagnostics); all physical steps use step().
    One-off requery completes the replaced interval then returns to base horizon.
    """
    if timing not in ('event', 'shadow', 'fixed', 'none'):
        raise ValueError('Unknown timing mode')
    if (timing == 'fixed') != (fixed_step is not None):
        raise ValueError('Fixed step is required only for explicit fixed-time control')
    if fixed_step is not None and (type(fixed_step) is not int or not 0 < fixed_step < config.max_steps):
        raise ValueError('Invalid fixed control step')
    controller, memory = EventController(config, method), PlanMemory(config)
    t, q, success = 0, 0, False
    queries, events, monitors, actions = [], [], [], []
    pending = []
    stop_at, plan_start = 0, 0
    plan = None
    replacement_end = None
    recent_actions = []
    evidence = monitor(obs, [])
    monitors.append(dict(t=0, evidence=asdict(evidence), details=getattr(monitor, 'diagnostics', {}),
                         **controller.observe(0, evidence)))
    while not success and t < config.max_steps:
        check()
        if plan is None or t >= stop_at:
            candidates, values, extra = policy(obs, t, q)
            metrics = chunk_metrics(candidates, values, config)
            chosen = int(np.argmax(values))
            metrics.update(memory.update(t, candidates, chosen))
            plan = np.asarray(candidates[chosen], dtype=np.float32)
            plan_start = t
            stop_at = min(t + config.execution_horizon, config.max_steps)
            if replacement_end is not None:
                stop_at = min(stop_at, replacement_end)
                replacement_end = None
            pending = controller.query_reasons(metrics)
            queries.append(dict(t=t, query=q, selected=chosen, metrics=metrics, metadata=extra,
                                candidate_actions=np.asarray(candidates).tolist(),
                                candidate_values=np.asarray(values).tolist(), planned_end=stop_at))
            q += 1
        action = plan[t - plan_start].copy()
        obs, success = step(action)
        actions.append(action)
        recent_actions.append(action)
        t += 1
        # A terminal label stops execution; it is never an intervention feature.
        if success or t >= config.max_steps:
            break
        scheduled_check = t % config.monitor_stride == 0
        fixed_check = timing == 'fixed' and t == fixed_step
        reasons = []
        if scheduled_check or fixed_check:
            evidence = monitor(obs, recent_actions)
            recent_actions = []
            record = controller.observe(t, evidence)
            monitors.append(dict(t=t, evidence=asdict(evidence),
                                 details=getattr(monitor, 'diagnostics', {}), **record))
            reasons = record['reasons']
            if t - plan_start >= config.min_prefix:
                reasons = sorted(set(reasons + pending))
        allowed = controller.available(t)
        eligible = t - plan_start >= config.min_prefix and t < stop_at
        fire = allowed and ((timing in ('event', 'shadow') and reasons and eligible) or fixed_check)
        if not fire or timing == 'none':
            continue
        route = controller.route(evidence)
        required = {'requery': 0, 'preserve_probe': 3, 'regrasp': 25, 'verify_regrasp': 28}[route]
        if config.max_steps - t < required:
            route = 'requery'
            reasons = reasons + ['insufficient_recovery_budget']
        event = dict(t=t, kind=route, reasons=reasons if timing != 'fixed' else ['fixed_control'],
                     timing=timing, executed=timing != 'shadow', old_plan_end=stop_at,
                     old_tail=plan[t - plan_start:].tolist(), evidence=asdict(evidence))
        events.append(event)
        controller.mark(t)
        pending = []
        if timing == 'shadow':
            continue
        if route == 'requery':
            # New first actions replace ONLY the unexecuted part of this interval.
            replacement_end = stop_at if t < stop_at else None
        else:
            obs, success, physical, info = intervene(route, obs, t, config.max_steps - t)
            physical = np.asarray(physical, dtype=np.float32).reshape(-1, 7)
            if len(physical) > config.max_steps - t or not np.isfinite(physical).all():
                raise ValueError('Physical intervention exceeded budget or produced invalid actions')
            actions.extend(physical)
            t += len(physical)
            event.update(physical_steps=len(physical), diagnostics=info)
            memory.clear()
            # Do not carry pre-recovery grasp evidence or old predictions into a new attempt.
            controller.last_intervention = t
            replacement_end = None
        plan = None
        recent_actions = []
    return dict(success=bool(success), final_t=t, actions=np.asarray(actions, dtype=np.float32),
                queries=queries, events=events, monitors=monitors, model_calls=q)
