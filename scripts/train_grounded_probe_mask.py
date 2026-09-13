#!/usr/bin/env python3
"""Train target masks on historical calibration only; freeze before new rollouts."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import torch
from torch.nn import functional as F

from grounded_probe import build_mask_model,TRAIN_PARAMS,MASK_PARAMS
from p5_repeat_feedback import atomic_json,digest
from train_perception_regrasp_heatmap import _load_rows,_load_arrays,_normalized_images,_resolve


def evaluate(model,images,masks,objects,indices):
    model.eval();rows=[]
    with torch.inference_mode():
        for start in range(0,len(indices),12):
            ix=indices[start:start+12]
            x=_normalized_images(images[ix],'cuda')
            y=masks[ix].cuda();obj=objects[ix].cuda()
            pred=model(x)['out'][torch.arange(len(ix),device='cuda'),obj].sigmoid()>=MASK_PARAMS['threshold']
            inter=(pred&y).sum((1,2));union=(pred|y).sum((1,2));area=pred.sum((1,2))
            for i in range(len(ix)):
                rows.append(dict(index=int(ix[i]),iou=float(inter[i]/union[i].clamp(min=1)),
                    precision=float(inter[i]/area[i].clamp(min=1)),predicted_area=int(area[i]),true_area=int(y[i].sum())))
    return pd.DataFrame(rows)


def train(campaign):
    cfg=json.loads((campaign/'config.json').read_text());params=cfg['train_params']
    output=campaign/'mask_model';output.mkdir(exist_ok=True)
    if (output/'freeze.json').exists():
        frozen=json.loads((output/'freeze.json').read_text())
        for name,sha in frozen['sha256'].items():
            if digest(output/name)!=sha:raise ValueError('Changed frozen mask model')
        print('Frozen model already complete',flush=True);return
    frame=_load_rows(Path(cfg['calibration_dir']),params['folds'])
    if digest(Path(cfg['calibration_manifest']))!=cfg['calibration_manifest_sha256']:
        raise ValueError('Calibration membership changed')
    allowed=pd.read_csv(cfg['calibration_manifest'])
    if set(frame.row_uid)!=set(allowed.row_uid):raise ValueError('Mask rows differ from historical calibration')
    frame['sample_sha256']=[digest(_resolve(str(path))) for path in frame.sample_path]
    arrays=_load_arrays(frame)
    # Calibration RGB is native OpenGL, masks are already OpenCV-oriented.
    images=torch.from_numpy(arrays['images'][:,::-1].copy())
    masks=torch.from_numpy(arrays['target_masks'].copy())
    names=sorted(frame.object_name.unique());lookup={name:i for i,name in enumerate(names)}
    objects=torch.tensor([lookup[x] for x in frame.object_name],dtype=torch.long)
    train_ids=np.flatnonzero(frame.fold.to_numpy()!=params['validation_fold'])
    val_ids=np.flatnonzero(frame.fold.to_numpy()==params['validation_fold'])
    if not len(val_ids) or set(frame.iloc[val_ids].object_name)-set(frame.iloc[train_ids].object_name):
        raise ValueError('Calibration fold has unsupported objects')
    if set(frame.iloc[val_ids].independent_group)&set(frame.iloc[train_ids].independent_group):
        raise ValueError('Calibration group leakage')
    frame.assign(split=np.where(frame.fold==params['validation_fold'],'validation','train')).to_csv(output/'manifest.csv',index=False)
    torch.manual_seed(params['seed']);np.random.seed(params['seed'])
    model=build_mask_model(names,pretrained=True).cuda()
    optimizer=torch.optim.AdamW(model.parameters(),lr=params['learning_rate'],weight_decay=.0001)
    generator=torch.Generator().manual_seed(params['seed'])
    started=time.time()
    for epoch in range(params['epochs']):
        model.train();losses=[]
        order=train_ids[torch.randperm(len(train_ids),generator=generator).numpy()]
        for start in range(0,len(order),params['batch_size']):
            ix=order[start:start+params['batch_size']]
            if len(ix)==1:ix=np.r_[ix,order[:1]]
            x=_normalized_images(images[ix],'cuda');y=masks[ix].cuda().float();obj=objects[ix].cuda()
            with torch.autocast('cuda',dtype=torch.bfloat16):
                result=model(x);batch=torch.arange(len(ix),device='cuda')
                logits=result['out'][batch,obj];prob=logits.sigmoid()
                weight=((1-y).sum()/y.sum().clamp(min=1)).clamp(max=30)
                bce=F.binary_cross_entropy_with_logits(logits.float(),y,pos_weight=weight)
                dice=1-((2*(prob*y).sum((1,2))+1)/(prob.sum((1,2))+y.sum((1,2))+1)).mean()
                aux=F.binary_cross_entropy_with_logits(result['aux'][batch,obj].float(),y,pos_weight=weight)
                loss=bce+dice+.3*aux
            optimizer.zero_grad(set_to_none=True);loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step();losses.append(float(loss.detach()))
        atomic_json(output/'training_status.json',dict(epoch=epoch+1,epochs=params['epochs'],loss=float(np.mean(losses)),elapsed_seconds=time.time()-started))
        print(f'[mask] epoch={epoch+1}/{params["epochs"]} loss={np.mean(losses):.5f}',flush=True)
    metrics=evaluate(model,images,masks,objects,val_ids)
    metrics['object_name']=frame.iloc[metrics['index']].object_name.to_numpy()
    metrics.to_csv(output/'validation.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(min(6,len(val_ids)),3,figsize=(9,12),squeeze=False,layout='constrained')
    model.eval()
    with torch.inference_mode():
        for axes_row,index in zip(axes,val_ids[:6]):
            image=images[index].numpy();truth=masks[index].numpy()
            pred=model(_normalized_images(images[index:index+1],'cuda'))['out'][0,objects[index]].sigmoid().cpu().numpy()
            for ax,value,title in zip(axes_row,(image,truth,pred>=MASK_PARAMS['threshold']),('RGB OpenCV','GT calibration mask','Predicted mask >=0.8')):
                ax.imshow(value);ax.set_title(title);ax.axis('off')
    fig.savefig(output/'validation_masks.png',dpi=120);plt.close(fig)
    grouped=metrics.groupby('object_name')[['iou','precision']].mean()
    score=grouped.mean();gate=bool(score.iou>=params['validation_mean_iou_gate'] and score.precision>=params['validation_mean_precision_gate'])
    temp=output/'mask.tmp.pt';torch.save({k:v.cpu() for k,v in model.state_dict().items()},temp);temp.replace(output/'mask.pt')
    atomic_json(output/'mask.json',dict(objects=names,params=params,mask_params=MASK_PARAMS,
        input_coordinates='opencv',output_coordinates='opencv',validation_gate_pass=gate,
        validation_macro_iou=float(score.iou),validation_macro_precision=float(score.precision),
        training_rows=len(train_ids),validation_rows=len(val_ids),no_terminal_labels_used=True,
        training_source='historical_calibration_after_retreat',checkpoint='fixed_final_epoch_not_best_on_screen'))
    atomic_json(output/'freeze.json',dict(sha256={p:digest(output/p) for p in ('mask.pt','mask.json','manifest.csv','validation.csv')},
        frozen_before_rollouts=True,validation_gate_pass=gate))
    print((output/'mask.json').read_text(),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',required=True,type=Path)
    train(p.parse_args().campaign)
