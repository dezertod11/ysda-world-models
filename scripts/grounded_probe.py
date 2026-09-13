"""Object-specific RGB motion verification; no simulator object inputs online."""
from pathlib import Path
import json
import numpy as np

try:
    from scripts.probe_repair import motion_decision,PARAMS
except ModuleNotFoundError:
    from probe_repair import motion_decision,PARAMS

NAME='grounded_probe_20260911_v2'
ARMS=('continue_h8','physical_regrasp','probe_only','probe_verify_repair',
      'probe_always_regrasp','mask_verify_miss','mask_verify_conservative','delayed_regrasp_h8')
CANDIDATES=('mask_verify_conservative','mask_verify_miss','delayed_regrasp_h8')
TRANSFER_CELLS=(('x0.1',2),('x0.2',9),('y0.1',2),('y0.1',5),('y0.1',9),('y0.2',5))
MASK_PARAMS=dict(threshold=.8,min_area=12,max_area=2048,max_center_distance=40.,
    min_retention=.5,min_tracks=4,max_fb_error=1.,max_flow_mad=1.5,
    max_centroid_flow_error=2.,lk_window=7)
TRAIN_PARAMS=dict(epochs=30,batch_size=12,learning_rate=.0001,seed=20260911,
                  validation_fold=0,folds=4,validation_mean_iou_gate=.35,
                  validation_mean_precision_gate=.7)


def component_mask(probability,center,params=MASK_PARAMS):
    import cv2
    p=np.asarray(probability);center=np.asarray(center,dtype=float)
    if p.ndim!=2 or not np.isfinite(p).all() or center.shape!=(2,) or not np.isfinite(center).all():
        raise ValueError('Invalid RGB mask or center')
    count,labels,stats,centroids=cv2.connectedComponentsWithStats((p>=params['threshold']).astype(np.uint8),8)
    choices=[i for i in range(1,count) if params['min_area']<=stats[i,cv2.CC_STAT_AREA]<=params['max_area']
             and np.linalg.norm(centroids[i]-center)<=params['max_center_distance']]
    if not choices:return np.zeros_like(p,dtype=bool)
    index=min(choices,key=lambda i:float(np.linalg.norm(centroids[i]-center)))
    return labels==index


def masked_motion(before,after,mask0,mask1,eef_flow,confidence,params=MASK_PARAMS):
    import cv2
    images=[np.asarray(im,dtype=np.uint8) for im in (before,after)]
    masks=[np.asarray(m,dtype=bool) for m in (mask0,mask1)]
    if images[0].shape!=images[1].shape or any(m.shape!=images[0].shape[:2] for m in masks):
        raise ValueError('Mask/image size mismatch')
    result=dict(verification='unknown',tracks=0,mask_before_area=int(masks[0].sum()),
                mask_after_area=int(masks[1].sum()),flow=[0.,0.],retention=0.,reason='insufficient_mask')
    if any(m.sum()<params['min_area'] for m in masks):return result
    centroids=[np.argwhere(m).mean(axis=0)[::-1] for m in masks]
    centroid_flow=centroids[1]-centroids[0]
    eroded=cv2.erode(masks[0].astype(np.uint8),np.ones((3,3),np.uint8))
    gray=[cv2.cvtColor(im,cv2.COLOR_RGB2GRAY) for im in images]
    points=cv2.goodFeaturesToTrack(gray[0],maxCorners=80,qualityLevel=.005,minDistance=2,mask=eroded*255)
    if points is None:return dict(result,reason='no_object_corners')
    window=(params['lk_window'],)*2
    q,status,_=cv2.calcOpticalFlowPyrLK(*gray,points,None,winSize=window,maxLevel=2)
    if q is None:return dict(result,reason='no_forward_tracks')
    back,back_status,_=cv2.calcOpticalFlowPyrLK(gray[1],gray[0],q,None,winSize=window,maxLevel=2)
    if back is None:return dict(result,reason='no_backward_tracks')
    xy=q.reshape(-1,2);finite=np.isfinite(xy).all(axis=1)
    h,w=masks[1].shape
    indices=np.rint(np.nan_to_num(xy,nan=-1,posinf=-1,neginf=-1)).astype(int)
    inside=finite&(indices[:,0]>=0)&(indices[:,0]<w)&(indices[:,1]>=0)&(indices[:,1]<h)
    end_mask=np.zeros(len(points),dtype=bool)
    end_mask[inside]=masks[1][indices[inside,1],indices[inside,0]]
    good=(status.ravel()>0)&(back_status.ravel()>0)&end_mask&(
        np.linalg.norm((back-points).reshape(-1,2),axis=1)<=params['max_fb_error'])
    flow=(q-points).reshape(-1,2)[good]
    result.update(tracks=len(flow),retention=float(good.mean()),centroid_flow=centroid_flow.tolist())
    if len(flow)<params['min_tracks'] or result['retention']<params['min_retention']:
        return dict(result,reason='insufficient_object_tracks')
    median=np.median(flow,axis=0);mad=float(np.median(np.linalg.norm(flow-median,axis=1)))
    error=float(np.linalg.norm(median-centroid_flow))
    result.update(flow=median.tolist(),flow_mad=mad,centroid_flow_error=error)
    if mad>params['max_flow_mad'] or error>params['max_centroid_flow_error']:
        return dict(result,reason='inconsistent_object_motion')
    verdict=motion_decision(median,eef_flow,len(flow),confidence,PARAMS)
    # Require independent mask-centroid evidence for a positive grasp decision.
    if verdict=='held' and motion_decision(centroid_flow,eef_flow,len(flow),confidence,PARAMS)!='held':
        return dict(result,reason='centroid_does_not_confirm_held')
    return dict(result,verification=verdict,reason='object_motion')


def should_repair(arm,verdict):
    if verdict not in ('held','miss','unknown'):raise ValueError('Unknown verdict')
    if arm in ('probe_verify_repair','mask_verify_miss'):return verdict=='miss'
    if arm=='mask_verify_conservative':return verdict!='held'
    if arm=='probe_always_regrasp':return True
    if arm=='probe_only':return False
    raise ValueError('Not a probe arm: '+arm)


def build_mask_model(objects,pretrained=False):
    from torch import nn
    from torchvision.models.segmentation import deeplabv3_resnet50,DeepLabV3_ResNet50_Weights
    model=deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT if pretrained else None,
        weights_backbone=None,aux_loss=True)
    model.classifier[-1]=nn.Conv2d(256,len(objects),1)
    model.aux_classifier[-1]=nn.Conv2d(256,len(objects),1)
    return model


class FrozenObjectMask:
    def __init__(self,directory,device='cuda'):
        import torch
        self.directory=Path(directory);self.device=device
        self.metadata=json.loads((self.directory/'mask.json').read_text())
        self.objects=self.metadata['objects']
        self.model=build_mask_model(self.objects).to(device)
        self.model.load_state_dict(torch.load(self.directory/'mask.pt',map_location=device,weights_only=True))
        self.model.eval()

    def probability(self,opencv_rgb,description):
        import torch
        try:from scripts.perception_regrasp import canonical_object_name,heatmap_image_tensor
        except ModuleNotFoundError:from perception_regrasp import canonical_object_name,heatmap_image_tensor
        index=self.objects.index(canonical_object_name(description))
        with torch.inference_mode():
            tensor=heatmap_image_tensor(opencv_rgb,device=self.device)
            return self.model(tensor)['out'][0,index].sigmoid().float().cpu().numpy()


def make_jobs(calibration,cells,transfer_cells=()):
    seen=set(zip(calibration.position_level.astype(str),calibration.task_id.astype(int)))
    jobs=[]
    cohorts=[(ci,level,task,[('smoke',(33,)),('screen',range(34,38)),('holdout',range(38,46))])
             for ci,(level,task) in enumerate(cells)]
    cohorts.extend((10+ci,level,task,[('transfer',range(34,38))]) for ci,(level,task) in enumerate(transfer_cells))
    if set(cells)&set(transfer_cells):raise ValueError('Transfer cells overlap main screen')
    for ci,level,task,phases in cohorts:
        for phase,inits in phases:
            for init in inits:
                if ((calibration.position_level==level)&(calibration.task_id==task)&(calibration.init_state_id==init)).any():
                    raise ValueError('Calibration group overlap')
                for repeat in range(1 if phase=='smoke' else 2):
                    jobs.append(dict(id=f'{level}_t{task}_i{init}_r{repeat}',cell=f'{level}_t{task}',
                        phase=phase,position_level=level,task_id=task,init_state_id=init,repeat=repeat,
                        suite='libero_object_temp',calibration_cell_seen=(level,task) in seen,
                        rollout_seed=1_950_000_000+ci*10_000_000+init*100_000+repeat*10_000))
    return jobs
