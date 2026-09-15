"""Frozen P3 transfer comparison and an observation-triggered recovery ablation."""
from dataclasses import asdict
import importlib.util
from pathlib import Path

import numpy as np

from event_feedback import EventConfig, EventController, PlanMemory, chunk_metrics

NAME = 'p3_benchmark_closure_20260914_v3'
ARMS = ('first_k1', 'max_value_h16', 'h8_at72', 'p3_at72', 'p3_event')
FACTORS = ('Object', 'Environment', 'Position')
CONTRASTS = (('p3_at72', 'max_value_h16'), ('p3_at72', 'h8_at72'),
             ('p3_event', 'max_value_h16'), ('p3_event', 'p3_at72'))


def policy_source(module):
    """Namespace packages have no __file__; fingerprint their actual source tree."""
    file = getattr(module, '__file__', None)
    roots = [Path(file).resolve().parent] if file else [Path(p).resolve() for p in module.__path__]
    roots = sorted({p for p in roots if (p / 'experiments/robot/cosmos_utils.py').is_file()})
    if getattr(module, '__name__', None):
        spec = importlib.util.find_spec(module.__name__ + '.experiments.robot.cosmos_utils')
        if spec is not None and spec.origin:
            active = Path(spec.origin).resolve().parents[2]
            if active in roots:
                return active
    if len(roots) != 1:
        raise ValueError('Cannot identify one Cosmos policy source tree')
    return roots[0]


def benchmark_jobs(rows):
    rows = [r for r in rows if r['method'] == 'max_value']
    jobs = []
    for row in rows:
        factor = row['factor']
        level = row['case_id'].removeprefix('tc2_position_') if factor == 'Position' else ''
        task, init, seed = (int(row[k]) for k in ('task_id', 'init_state_id', 'rollout_seed'))
        jobs.append(dict(id=f'{factor.lower()}_{level}_t{task}_i{init}', phase='main',
            factor=factor, level=level, suite=row['suite'], task_id=task, init_state_id=init,
            rollout_seed=seed, task_description=row['task_description']))
    if len(jobs) != 199 or len({j['id'] for j in jobs}) != 199:
        raise ValueError('Expected exactly 199 unique valid-support cases')
    if {f: sum(j['factor'] == f for j in jobs) for f in FACTORS} != dict(Object=50, Environment=50, Position=99):
        raise ValueError('Benchmark support changed')
    # Interleave factors and tasks before collecting additional init repetitions.
    jobs.sort(key=lambda j: (max(0, j['init_state_id'] - 2) if j['factor'] != 'Position' else 0,
                             j['task_id'], FACTORS.index(j['factor']), j['level']))
    return jobs


def asset_root(job):
    if job['factor'] == 'Position':
        return Path('.runtime/libero_pro_position') / job['level']
    if job['factor'] == 'Environment':
        return Path('.runtime/trajectory_consensus_20260908_environment')
    return Path('LIBERO-PRO/libero/libero')


def run_episode(obs, *, arm, policy, step, recover, monitor=None, config=EventConfig(), check=lambda: None):
    """Callbacks receive current observations; recovery steps consume the episode budget.

    Event timing uses only persistent observed miss after a close near the target.
    Uncertainty is logged but cannot consume the single recovery opportunity.
    """
    if arm not in ARMS + ('shadow',):
        raise ValueError('Unknown arm')
    t, q, success, switched = 0, 0, False, False
    actions, queries, events, monitors, recent = [], [], [], [], []
    plan, plan_start, plan_end = None, 0, 0
    ctrl, memory = EventController(config, 'regrasp'), PlanMemory(config)
    watched = arm in ('p3_event', 'shadow')
    if watched:
        evidence = monitor(obs, [])
        monitors.append(dict(t=0, evidence=asdict(evidence), **ctrl.observe(0, evidence)))

    def apply_recovery():
        nonlocal obs, success, t, plan, switched
        start = t
        obs, success, physical, info = recover(obs, t, config.max_steps - t)
        physical = np.asarray(physical, dtype=np.float32).reshape(-1, 7)
        if len(physical) > config.max_steps - t or not np.isfinite(physical).all():
            raise ValueError('Invalid physical recovery actions')
        actions.extend(physical)
        t += len(physical)
        switched, plan = True, None
        memory.clear()
        recent.clear()
        return dict(t=start, end_t=t, physical_steps=len(physical), diagnostics=info, executed=True)

    while not success and t < config.max_steps:
        check()
        if not switched and arm in ('h8_at72', 'p3_at72') and t == 72:
            if arm == 'p3_at72':
                events.append(apply_recovery())
            else:
                switched, plan = True, None
                events.append(dict(t=t, end_t=t, physical_steps=0, executed=True, kind='horizon_switch'))
            if success or t >= config.max_steps:
                break
        if plan is None or t >= plan_end:
            candidates, values, extra = policy(obs, t, q, 1 if arm == 'first_k1' else 4)
            metrics = chunk_metrics(candidates, values, config)
            selected = 0 if arm == 'first_k1' else int(np.argmax(values))
            metrics.update(memory.update(t, candidates, selected))
            horizon = 8 if switched else 16
            plan = np.asarray(candidates[selected], dtype=np.float32).copy()
            plan_start, plan_end = t, min(config.max_steps, t + horizon)
            if not switched and arm in ('h8_at72', 'p3_at72') and t < 72 < plan_end:
                plan_end = 72
            queries.append(dict(t=t, query=q, selected=selected, metrics=metrics, metadata=extra,
                candidate_actions=np.asarray(candidates).tolist(), candidate_values=np.asarray(values).tolist(),
                planned_end=plan_end, executed_steps=0))
            q += 1
        action = plan[t - plan_start].copy()
        obs, success = step(action)
        actions.append(action)
        recent.append(action)
        t += 1
        queries[-1]['executed_steps'] += 1
        if success or t >= config.max_steps:
            break
        if watched and not switched and t % config.monitor_stride == 0:
            evidence = monitor(obs, recent)
            recent = []
            record = ctrl.observe(t, evidence)
            monitors.append(dict(t=t, evidence=asdict(evidence),
                diagnostics=getattr(monitor, 'diagnostics', {}), **record))
            fire = ('miss' in record['reasons'] and ctrl.route(evidence) == 'regrasp'
                    and ctrl.available(t) and config.max_steps - t >= 25)
            if fire:
                ctrl.mark(t)
                if arm == 'shadow':
                    events.append(dict(t=t, end_t=t, executed=False, physical_steps=0, kind='miss'))
                else:
                    event = apply_recovery()
                    event.update(kind='persistent_observed_miss', evidence=asdict(evidence))
                    events.append(event)
    return dict(success=bool(success), final_t=t, actions=np.asarray(actions, dtype=np.float32),
                queries=queries, events=events, monitors=monitors, model_calls=q)
