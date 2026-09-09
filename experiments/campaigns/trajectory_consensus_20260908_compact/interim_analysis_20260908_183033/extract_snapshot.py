import json, sys, hashlib, itertools
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP")
from scripts.analyze_trajectory_consensus_campaign import interval, KEYS
root=Path("/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP")
campaign=root/"experiments/campaigns/trajectory_consensus_20260908_compact"
manifest=json.loads((campaign/"manifest.json").read_text())
frames=[]; audit=[]; query_stats=[]
columns=[*KEYS, "query_idx", "t", "t_after", "executed_steps", "success", "final_t", "num_queries",
"num_open_loop_steps", "prediction_mode", "max_value_selected", "sim_state_json",
"candidate_action_chunks_json", "target_drop_candidate", "failure_type", "task_description",
"video_path", "prediction_error_horizon_aligned"]
for job in manifest["jobs"]:
    marker=Path(job["completion_marker"])
    if not marker.exists(): continue
    name=job["name"]
    label=next(m for m in ["first","max_value","winner"] if name.endswith("_"+m))
    factor="Position" if "position" in job["kind"] else "Environment" if "environment" in job["kind"] else "Object"
    paths=list((campaign/"runs").glob(job["environment"]["LIBERO_PRO_PLANNING_GRID_PREFIX"]+"__*__query_traces.parquet"))
    assert len(paths)==1,(name,paths)
    x=pd.read_parquet(paths[0],columns=columns)
    assert not x.duplicated([*KEYS,"query_idx"]).any()
    for key,g in x.groupby(KEYS):
        g=g.sort_values("query_idx")
        assert np.array_equal(g.query_idx,np.arange(len(g)))
        assert g.num_queries.eq(len(g)).all()
        assert g.success.nunique()==1 and g.final_t.nunique()==1
        assert g.t.iloc[0]==0 and g.t_after.iloc[-1]==g.final_t.iloc[-1]
        assert np.array_equal(g.t_after.iloc[:-1],g.t.iloc[1:])
        assert np.array_equal(g.t_after-g.t,g.executed_steps)
        assert g.num_open_loop_steps.eq(16).all() and g.prediction_mode.eq("parallel").all()
        assert len(json.loads(g.candidate_action_chunks_json.iloc[0]))==(1 if label=="first" else 4)
        assert Path(g.video_path.iloc[0]).stat().st_size>1024
    e=x[x.query_idx.eq(0)].copy()
    e["method"]=label; e["factor"]=factor
    e["q0_hash"]=e.candidate_action_chunks_json.map(lambda s:hashlib.sha256(np.asarray(json.loads(s),dtype="<f8").tobytes()).hexdigest())
    frames.append(e.drop(columns="candidate_action_chunks_json"))
    audit.append(dict(job=name,trace=str(paths[0]),sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest(),episodes=len(e)))
    query_stats.append(dict(method=label,factor=factor,queries=len(x),switched=int((~x.max_value_selected.astype(bool)).sum())))
episodes=pd.concat(frames,ignore_index=True)
assert not episodes.duplicated([*KEYS,"method"]).any()
matched_keys=episodes.groupby(KEYS).method.nunique()
matched_keys=matched_keys[matched_keys.eq(3)].reset_index()[KEYS]
matched=episodes.merge(matched_keys,on=KEYS,validate="many_to_one")
scores=lambda d:d.groupby(["factor","method"]).agg(episodes=("success","size"),successes=("success","sum"),sr=("success","mean"),drops=("target_drop_candidate","sum"),mean_queries=("num_queries","mean")).reset_index().to_dict("records")
effects=[]
for reference,method in [("max_value","winner"),("first","winner"),("first","max_value")]:
    pair=matched[matched.method.eq(reference)].merge(matched[matched.method.eq(method)],on=[*KEYS,"factor"],suffixes=("_a","_b"),validate="one_to_one")
    for a,b in zip(pair.sim_state_json_a,pair.sim_state_json_b): np.testing.assert_allclose(json.loads(a),json.loads(b),rtol=0,atol=1e-9)
    pair["delta"]=pair.success_b.astype(int)-pair.success_a.astype(int)
    for scope,g in [("All",pair),*pair.groupby("factor")]:
        lo,hi=interval(g)
        effects.append(dict(reference=reference,method=method,scope=scope,n=len(g),macro_delta=g.groupby("factor").delta.mean().mean(),ci95=[lo,hi],rescues=int(g.delta.eq(1).sum()),harms=int(g.delta.eq(-1).sum()),q0_pool_exact_rate=g.q0_hash_a.eq(g.q0_hash_b).mean()))
refs=root/"experiments/campaigns/consensus_references_20260908"
out=dict(as_of=datetime.now(ZoneInfo("Europe/Moscow")).isoformat(),status="interim_not_final",campaign_status=manifest["status"],
    completed_jobs=len(audit),total_jobs=len(manifest["jobs"]),completed_rollouts=len(episodes),expected_rollouts=600,
    complete_matched_cases=len(matched_keys),unmatched_rollouts=len(episodes)-len(matched),factor_scores_all_completed=scores(episodes),
    factor_scores_matched=scores(matched),paired_effects=effects,
    task_scores=matched.groupby(["factor","task_id","method"]).success.agg(["size","sum","mean"]).reset_index().to_dict("records"),
    failure_types=matched.groupby(["method","success","failure_type"],dropna=False).size().reset_index(name="n").to_dict("records"),
    failed_final_steps=matched[~matched.success].groupby(["method","final_t"]).size().reset_index(name="n").to_dict("records"),
    position_cells=matched[matched.factor.eq("Position")].groupby(["case_id","method"]).success.agg(["size","sum","mean"]).reset_index().to_dict("records"),
    query_counts=pd.DataFrame(query_stats).groupby(["factor","method"]).sum(numeric_only=True).reset_index().to_dict("records"),
    reference_sequence=json.loads((refs/"sequence_status.json").read_text()),trace_audit=audit)
print(json.dumps(out,default=lambda o:o.item() if isinstance(o,np.generic) else str(o),allow_nan=False))
