"""Observation-only probe/verify/repair: frozen design and RGB motion verifier."""
import numpy as np

NAME = 'probe_verify_repair_20260910_v2'
ARMS = ('continue_h8', 'physical_regrasp', 'probe_only', 'probe_verify_repair')
CELLS = (('x0.2',2),('x0.2',5),('y0.2',9),('y0.2',2),('x0.1',5),('x0.1',9))
PARAMS = dict(probe_height_m=.04, probe_steps=3, min_eef_pixels=2.,
              min_tracks=4, max_forward_backward_error=1.5,
              hold_cosine=.7, hold_ratio_low=.3, hold_ratio_high=2.5,
              static_object_pixels=.75, crop_radius=16)


def tracking_rgb(image,convention):
    """Match robosuite camera projection and calibrated heatmap output coordinates."""
    if convention=='opengl':return np.asarray(image)[::-1].copy()
    if convention=='opencv':return np.asarray(image).copy()
    raise ValueError('Unsupported RGB convention: '+str(convention))


def motion_decision(object_flow, eef_flow, tracks, confidence, params=PARAMS):
    obj, eef = np.asarray(object_flow,dtype=float),np.asarray(eef_flow,dtype=float)
    if obj.shape!=(2,) or eef.shape!=(2,) or not np.isfinite(obj).all() or not np.isfinite(eef).all():
        return 'unknown'
    en,on=float(np.linalg.norm(eef)),float(np.linalg.norm(obj))
    if not confidence or tracks<params['min_tracks'] or en<params['min_eef_pixels']:
        return 'unknown'
    ratio=on/en
    cosine=float(obj@eef/max(on*en,1e-8))
    if params['hold_ratio_low']<=ratio<=params['hold_ratio_high'] and cosine>=params['hold_cosine']:
        return 'held'
    if on<=params['static_object_pixels']:
        return 'miss'
    return 'unknown'


def track_crop(before,after,center,params=PARAMS):
    import cv2
    a,b=[cv2.cvtColor(np.asarray(im,dtype=np.uint8),cv2.COLOR_RGB2GRAY) for im in (before,after)]
    if a.shape!=b.shape:
        raise ValueError('Image sizes differ')
    x,y=map(float,center)
    if not np.isfinite([x,y]).all():
        return dict(flow=[0.,0.],tracks=0)
    x,y=int(round(x)),int(round(y)); h,w=a.shape
    if not 0<=x<w or not 0<=y<h:
        return dict(flow=[0.,0.],tracks=0)
    mask=np.zeros_like(a); r=params['crop_radius']
    mask[max(0,y-r):min(h,y+r+1),max(0,x-r):min(w,x+r+1)]=255
    p=cv2.goodFeaturesToTrack(a,maxCorners=40,qualityLevel=.01,minDistance=3,mask=mask)
    if p is None:
        return dict(flow=[0.,0.],tracks=0)
    q,status,_=cv2.calcOpticalFlowPyrLK(a,b,p,None,winSize=(21,21),maxLevel=3)
    if q is None:
        return dict(flow=[0.,0.],tracks=0)
    back,back_status,_=cv2.calcOpticalFlowPyrLK(b,a,q,None,winSize=(21,21),maxLevel=3)
    if back is None:
        return dict(flow=[0.,0.],tracks=0)
    good=(status.ravel()>0)&(back_status.ravel()>0)&(
        np.linalg.norm((back-p).reshape(-1,2),axis=1)<=params['max_forward_backward_error'])
    flow=(q-p).reshape(-1,2)[good]
    return dict(flow=np.median(flow,axis=0).tolist() if len(flow) else [0.,0.],tracks=int(len(flow)))


def project_eef(eef,intrinsic,camera_to_world):
    xyz=np.linalg.inv(camera_to_world)@np.r_[eef,1.]
    pixel=np.asarray(intrinsic)@xyz[:3]
    if pixel[2]<=1e-8:
        return np.full(2,np.nan)
    return pixel[:2]/pixel[2]


def make_jobs(calibration):
    seen=set(zip(calibration.position_level.astype(str),calibration.task_id.astype(int)))
    jobs=[]
    for ci,(level,task) in enumerate(CELLS):
        for phase,inits,repeats in [('smoke',(33,),(0,)),('screen',range(25,29),(0,1)),('holdout',range(29,33),(0,1))]:
            for init in inits:
                if ((calibration.position_level==level)&(calibration.task_id==task)&(calibration.init_state_id==init)).any():
                    raise ValueError('Perception calibration init overlap')
                for repeat in repeats:
                    jobs.append(dict(id=f'{level}_t{task}_i{init}_r{repeat}',cell=f'{level}_t{task}',
                        phase=phase,position_level=level,task_id=task,init_state_id=init,repeat=repeat,
                        suite='libero_object_temp',calibration_cell_seen=(level,task) in seen,
                        rollout_seed=1_800_000_000+ci*10_000_000+init*100_000+repeat*10_000))
    return jobs


def validation_gate(summary):
    """Practical screen gate only; holdout, not the screen, tests confirmation."""
    return bool(summary.get('complete') and summary.get('pairs')==48
        and summary.get('verified_minus_full',-1)>=.05
        and summary.get('verified_minus_probe',-1)>0
        and summary.get('verified_minus_continue',-1)>0
        and summary.get('verified_drop_count',999)<=summary.get('full_drop_count',0)
        and summary.get('changed_from_full',0)>=8)


def validate_probe_pair(first,second):
    """Simulator state is only a replay audit, never a verifier input."""
    if first['t']!=second['t'] or first['observation_hashes']!=second['observation_hashes']:
        raise ValueError('Shared probe replay input mismatch')
    np.testing.assert_allclose(first['sim_state'],second['sim_state'],atol=1e-9,rtol=0)
