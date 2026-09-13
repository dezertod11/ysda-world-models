#!/usr/bin/env python3
"""Post-hoc CPU audit of physical probes; never changes the frozen controller."""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.probe_repair import ARMS
    from scripts.p5_repeat_feedback import atomic_json,digest
    from scripts.analyze_probe_repair import analyze
    from scripts.analyze_feedback_controls import contrast
except ModuleNotFoundError:
    from probe_repair import ARMS
    from p5_repeat_feedback import atomic_json,digest
    from analyze_probe_repair import analyze
    from analyze_feedback_controls import contrast


def exact_cluster_p(data,left,right):
    wide=data.pivot(index=['cell','init_state_id','repeat'],columns='arm',values='terminal_success')
    delta=(wide[left].astype(int)-wide[right].astype(int)).groupby(level=['cell','init_state_id']).mean()
    cells=delta.index.get_level_values('cell').unique()
    contributions=np.array([v/len(delta.loc[c])/len(cells) for (c,_),v in delta.items()])
    contributions=contributions[np.abs(contributions)>1e-12]
    if len(contributions)>18:
        raise ValueError('Too many nonzero clusters for this exact diagnostic')
    signs=np.asarray(list(itertools.product((-1.,1.),repeat=len(contributions))))
    if len(contributions)==0:return 1.0
    return float(np.mean(np.abs(signs@contributions)>=abs(contributions.sum())-1e-12))


def target_probe_motion(prefix,trace,target,steps):
    """Recover object order from named prefix observations and verify the mapping."""
    objects=[(k[len('obs__'):-len('_pos')],np.asarray(prefix[k])) for k in prefix
        if k.startswith('obs__') and k.endswith('_pos') and not k.startswith('obs__robot') and '_to_' not in k]
    names=[name for name,_ in objects]
    start=np.stack([pos for _,pos in objects])
    positions=trace['signal_field__object_positions']
    if positions.shape[1:]!=start.shape:raise ValueError('Object array shape mismatch')
    distances=np.linalg.norm(start[:,None]-positions[0][None,:],axis=2)
    if not np.array_equal(distances.argmin(axis=1),np.arange(len(objects))):
        raise ValueError('Object order is not uniquely consistent with named observations')
    if len(positions)<steps or steps<1:raise ValueError('Incomplete probe trace')
    target_delta=positions[steps-1,names.index(target)]-start[names.index(target)]
    eef_delta=trace['signal_field__eef_position'][steps-1]-prefix['obs__robot0_eef_pos']
    return target_delta,eef_delta


def collect(directory):
    cfg=json.loads((directory/'config.json').read_text());rows=[];motions=[]
    for job in cfg['jobs']:
        if job['phase']!='screen':continue
        d=directory/'screen'/job['id']
        with np.load(d/'prefix.npz',allow_pickle=False) as z:prefix={k:z[k].copy() for k in z.files}
        for arm in ARMS:
            row=json.loads((d/(arm+'.json')).read_text());inter=row['intervention']
            repair=inter.get('regrasp_diagnostics',{})
            row.update(verification=inter['verification'],probe_steps=inter['probe_steps'],
                repair_requested=inter.get('repair_requested',False),repair_steps=inter['regrasp_steps'],
                initial_trigger_passed=inter['initial_trigger_passed'],
                post_probe_confidence=inter.get('post_probe_confidence'),
                full_primitive_executed=repair.get('perception_regrasp_executed',False),
                guard_pass=repair.get('perception_guard_pass'),query_count=len(row['queries']))
            rows.append(row)
            if arm!='probe_verify_repair' or not inter['probe_steps']:continue
            with np.load(d/(arm+'.npz'),allow_pickle=False) as z:
                delta,eef=target_probe_motion(prefix,z,row['terminal_episode_target_objects'],inter['probe_steps'])
                signals=pd.DataFrame(z['signals'],columns=z['signal_keys'])
                part=signals.iloc[:inter['probe_steps']]
                np.testing.assert_array_equal(part.t,np.arange(row['prefix_t']+1,row['prefix_t']+inter['probe_steps']+1))
            motions.append(dict(job_id=job['id'],cell=job['cell'],verification=inter['verification'],
                success=row['terminal_success'],target_displacement_mm=float(np.linalg.norm(delta)*1000),
                target_dz_mm=float(delta[2]*1000),eef_displacement_mm=float(np.linalg.norm(eef)*1000),
                contact_steps=int(part.robot_target_contact_count.gt(0).sum()),
                target_eef_distance_m=float(part.target_eef_distance_min.iloc[-1]),
                optical_flow_pixels=float(np.linalg.norm(inter['object_flow'])),
                eef_projection_pixels=float(np.linalg.norm(inter['eef_flow'])),
                confidence=inter['post_probe_confidence']))
    return pd.DataFrame(rows),pd.DataFrame(motions)


def video_frames(path,indices):
    import imageio_ffmpeg
    reader=imageio_ffmpeg.read_frames(str(path),pix_fmt='rgb24');meta=next(reader)
    selected={};count=0
    try:
        for i,raw in enumerate(reader):
            if i in indices:selected[i]=np.frombuffer(raw,np.uint8).reshape(meta['size'][1],meta['size'][0],3).copy()
            count+=1
    finally:reader.close()
    return selected,count,meta


def audit_noop_paths(directory,data):
    counts=dict(no_trigger=0,probe_without_repair=0)
    for row in data[data.arm.eq('probe_verify_repair')].itertuples():
        if not row.initial_trigger_passed:
            group='no_trigger';arms=ARMS
        elif row.verification in ('held','unknown'):
            group='probe_without_repair';arms=('probe_only','probe_verify_repair')
        else:continue
        counts[group]+=1
        d=directory/'screen'/row.job_id
        with np.load(d/(arms[0]+'.npz'),allow_pickle=False) as z:
            reference={k:z[k].copy() for k in ('executed_actions','final_state','signals')}
        for arm in arms[1:]:
            with np.load(d/(arm+'.npz'),allow_pickle=False) as z:
                for key,value in reference.items():
                    if not np.array_equal(value,z[key],equal_nan=True):
                        raise ValueError(f'No-op parity mismatch: {row.job_id}/{arm}/{key}')
    return counts


def figures(directory,out,data,motion):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for label,color in [('held','#d44b3d'),('miss','#377eb8'),('unknown','#757575')]:
        part=motion[motion.verification.eq(label)]
        axes[0].scatter(part.eef_displacement_mm,part.target_displacement_mm,label=label,color=color,s=40)
        axes[1].scatter(part.eef_projection_pixels,part.optical_flow_pixels,label=label,color=color,s=40)
    axes[0].plot([0,32],[0,32],':',color='gray')
    axes[0].set(xlabel='EEF displacement during probe (mm)',ylabel='Actual target displacement (mm)',title='Offline simulator audit (not online input)')
    axes[1].set(xlabel='Projected EEF displacement (pixels)',ylabel='Median tracked displacement (pixels)',title='RGB verifier inputs')
    for ax in axes:ax.legend();ax.grid(alpha=.2)
    fig.savefig(out/'probe_motion_audit.png',dpi=160);plt.close(fig)

    case='x0.2_t5_i26_r0';d=directory/'screen'/case
    fig,axes=plt.subplots(4,5,figsize=(15,8),layout='constrained')
    for i,arm in enumerate(ARMS):
        row=data[(data.job_id.eq(case))&data.arm.eq(arm)].iloc[0]
        absolute=[72,75,112,168,int(row.terminal_final_t)]
        indices=[max(0,min(t,int(row.terminal_final_t))-int(row.prefix_t)) for t in absolute]
        frames,count,meta=video_frames(d/(arm+'.mp4'),indices)
        if count!=row.video_frames:raise ValueError('Decoded frame count')
        for j,index in enumerate(indices):
            axes[i,j].imshow(frames[index][:,:256]);axes[i,j].set_xticks([]);axes[i,j].set_yticks([])
            axes[i,j].set_title(f't={int(row.prefix_t)+index}'+(' (terminal)' if j==4 else ''),fontsize=10)
        axes[i,0].set_ylabel(f'{arm}\nsuccess={bool(row.terminal_success)}',fontsize=9)
    fig.suptitle(case+' | same prefix, front camera; H264 frames for illustration',fontsize=12)
    fig.savefig(out/'false_held_storyboard.png',dpi=160);plt.close(fig)

    row=data[(data.job_id.eq(case))&data.arm.eq('probe_verify_repair')].iloc[0]
    loc=json.loads((d/'localization.json').read_text())
    center=np.array([loc['perception_pixel_col'],loc['perception_pixel_row']])
    with np.load(d/'prefix.npz',allow_pickle=False) as z:before=z['obs__agentview_image'][::-1].copy()
    frames,_,_=video_frames(d/'probe_verify_repair.mp4',{3});after=frames[3][:,:256]
    flow=np.array(row.intervention['object_flow'])
    fig,axes=plt.subplots(1,3,figsize=(11,4),layout='constrained')
    for ax,im,title in zip(axes[:2],[before,after],['Before probe, t=72 (lossless)','After probe, t=75 (video)']):
        ax.imshow(im);ax.add_patch(Rectangle(center-16,33,33,fill=False,edgecolor='red',linewidth=1.5))
        ax.set_title(title,fontsize=10);ax.set_xticks([]);ax.set_yticks([])
    axes[2].imshow(before);axes[2].set_xlim(center[0]-18,center[0]+18);axes[2].set_ylim(center[1]+18,center[1]-18)
    axes[2].arrow(*center,*flow,color='yellow',width=.2,head_width=1.8,length_includes_head=True)
    axes[2].set_title('Tracking crop; saved median flow',fontsize=10)
    fig.suptitle('False held: target is stationary; no target contact during the probe',fontsize=11)
    fig.savefig(out/'false_held_crop.png',dpi=160);plt.close(fig)


def review(directory):
    analyze(directory,'screen')
    summary=json.loads((directory/'analysis/screen/summary.json').read_text())
    if not summary['complete']:raise ValueError('Review requires the complete frozen screen')
    data,motion=collect(directory);out=directory/'review_20260911';out.mkdir(exist_ok=True)
    noop_audit=audit_noop_paths(directory,data)
    data.drop(columns=['queries','intervention']).to_csv(out/'branch_diagnostics.csv',index=False)
    motion.to_csv(out/'probe_motion_audit.csv',index=False)
    aggregate=data.groupby('arm').agg(n=('terminal_success','size'),successes=('terminal_success','sum'),
        sr=('terminal_success','mean'),drop_proxy_count=('terminal_target_drop_candidate','sum'),
        mean_final_t=('terminal_final_t','mean'),mean_queries=('query_count','mean'),
        mean_branch_seconds=('elapsed_seconds','mean'),requested_repair=('repair_requested','sum'),
        full_primitive_executed=('full_primitive_executed','sum')).reindex(ARMS)
    aggregate.to_csv(out/'aggregate_scores.csv')
    effects=[]
    for left,right in [('probe_verify_repair','physical_regrasp'),('probe_verify_repair','probe_only'),
                       ('probe_verify_repair','continue_h8'),('probe_only','continue_h8'),('physical_regrasp','continue_h8')]:
        e=contrast(data,left,right);e['exact_nonzero_cluster_p']=exact_cluster_p(data,left,right);effects.append(e)
    pd.DataFrame(effects).to_csv(out/'additional_diagnostic_effects.csv',index=False)
    wide=data.pivot(index='job_id',columns='arm',values='terminal_success').astype(int)
    wide['verified_minus_full']=wide.probe_verify_repair-wide.physical_regrasp
    v=data[data.arm.eq('probe_verify_repair')].set_index('job_id')
    wide.join(v[['cell','verification','repair_steps','guard_pass','rollout_seed']]).to_csv(out/'paired_cases.csv')
    states=v[['cell','verification','initial_trigger_passed','repair_requested']].copy()
    for arm in ARMS:states[arm]=wide[arm]
    states.groupby(['cell','verification']).agg(n=('verification','size'),
        full_success=('physical_regrasp','sum'),verified_success=('probe_verify_repair','sum'),
        continue_success=('continue_h8','sum'),probe_success=('probe_only','sum')).to_csv(out/'verdict_outcomes.csv')
    false_held=motion.verification.eq('held')&motion.target_displacement_mm.lt(.001)&motion.contact_steps.eq(0)
    result=dict(status='completed_screen_no_go',pairs=len(wide),branches=len(data),
        source_config_sha256=digest(directory/'config.json'),probe_cases=len(motion),
        held_count=int(motion.verification.eq('held').sum()),held_static_no_contact=int(false_held.sum()),
        false_held_cells=sorted(motion.loc[false_held,'cell'].unique()),
        false_held_fails=int((false_held&~motion.success).sum()),
        lossless_gt_used_only_for_posthoc_audit=True,controller_unchanged=True,
        all_192_branch_hash_and_frame_accounting_checks_pass=True,
        bitwise_noop_action_final_state_signal_parity=noop_audit,
        effects=effects,aggregate=aggregate.reset_index().to_dict('records'))
    atomic_json(out/'summary.json',result)
    figures(directory,out,data,motion)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',type=Path,
        default=Path(__file__).resolve().parents[1]/'experiments/campaigns/probe_verify_repair_20260910_v2')
    review(p.parse_args().campaign)
