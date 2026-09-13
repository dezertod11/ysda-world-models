#!/usr/bin/env python3
"""Reproduce the final matched-K selection audit from locally saved pools."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.analyze_feedback_controls import analyze
    from scripts.feedback_controls import ARMS
    from scripts.p5_repeat_feedback import digest,atomic_json
except ModuleNotFoundError:
    from analyze_feedback_controls import analyze
    from feedback_controls import ARMS
    from p5_repeat_feedback import digest,atomic_json


def review(root):
    campaign=root/'experiments/campaigns/feedback_controls_20260910'
    analyze(campaign)
    config=json.loads((campaign/'config.json').read_text())
    rows=[]
    for job in config['jobs']:
        if job['phase']!='screen':continue
        d=campaign/'screen'/job['id']
        meta=json.loads((d/'pool.json').read_text())
        if digest(d/'pool.npz')!=meta['sha256']:raise ValueError('Pool checksum')
        outcomes={a:json.loads((d/(a+'.json')).read_text()) for a in ARMS}
        with np.load(d/'pool.npz',allow_pickle=False) as z:
            actions=z['fresh_actions'];values=z['fresh_values']
            indices={a:outcomes[a]['candidate_index'] for a in ('fresh_k1','fresh_k4','fresh_continuity_k4')}
            raw_delta=lambda a,b:float(np.max(np.abs(actions[indices[a],:8]-actions[indices[b],:8])))
            rows.append(dict(job_id=job['id'],cell=job['cell'],
                k4_vs_k1_index_changed=indices['fresh_k4']!=indices['fresh_k1'],
                continuity_vs_k4_index_changed=indices['fresh_continuity_k4']!=indices['fresh_k4'],
                k4_vs_k1_action_linf=raw_delta('fresh_k4','fresh_k1'),
                continuity_vs_k4_action_linf=raw_delta('fresh_continuity_k4','fresh_k4'),
                action_std_mean=float(actions.std(axis=0).mean()),value_min=float(values.min()),value_max=float(values.max()),
                value_range=float(np.ptp(values)),
                three_fresh_labels_equal=len({outcomes[a]['terminal_success'] for a in indices})==1))
    frame=pd.DataFrame(rows);out=campaign/'final_review';out.mkdir(exist_ok=True)
    frame.to_csv(out/'selection_audit.csv',index=False)
    summary=dict(pairs=len(frame),pool_integrity_pass=True,
        k4_vs_k1_index_changes=int(frame.k4_vs_k1_index_changed.sum()),
        continuity_vs_k4_index_changes=int(frame.continuity_vs_k4_index_changed.sum()),
        k4_vs_k1_actions_changed=int(frame.k4_vs_k1_action_linf.gt(0).sum()),
        continuity_vs_k4_actions_changed=int(frame.continuity_vs_k4_action_linf.gt(0).sum()),
        all_three_fresh_labels_equal=bool(frame.three_fresh_labels_equal.all()),
        fresh_value_min=float(frame.value_min.min()),fresh_value_max=float(frame.value_max.max()),
        action_std_mean_min=float(frame.action_std_mean.min()),action_std_mean_max=float(frame.action_std_mean.max()),
        source_config_sha256=digest(campaign/'config.json'))
    atomic_json(out/'summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':review(Path(__file__).resolve().parents[1])
