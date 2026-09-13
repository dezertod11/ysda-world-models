#!/usr/bin/env python3
"""Geometry-only camera orientation audit, with privileged labels strictly offline."""
import json
import os
from pathlib import Path

import numpy as np


def main():
    import collect_counterfactual_feedback as c
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from collect_perception_regrasp_calibration import render_segmentation_compat,_target_geom_ids
    from robosuite.utils.camera_utils import get_camera_extrinsic_matrix,get_camera_intrinsic_matrix
    from robosuite import macros
    from probe_repair import project_eef,track_crop
    from collect_feedback_controls import restore_observation
    from p5_repeat_feedback import atomic_json
    root=Path(__file__).resolve().parents[1]
    d=root/'experiments/campaigns/probe_verify_repair_20260910/smoke/x0.1_t5_i33_r0'
    cfg=c.default_policy_config('libero_object_temp',seed=0)
    suite=c.benchmark.get_benchmark_dict()['libero_object_temp']()
    task=suite.get_task(5)
    env,_=c.get_libero_env(task,cfg.model_family,resolution=cfg.env_img_res)
    try:
        with np.load(d/'prefix.npz',allow_pickle=False) as z:data={k:z[k].copy() for k in z.files}
        c._restore_snapshot(env,runtime_snapshot_from_arrays(data))
        obs=restore_observation(data,'obs__');image=obs['agentview_image']
        h,w=image.shape[:2]
        k=get_camera_intrinsic_matrix(env.sim,'agentview',h,w)
        transform=get_camera_extrinsic_matrix(env.sim,'agentview')
        tracker=c.SafetySignalTracker(env,obs)
        name=tracker.target_objects[0]
        target=tracker._object_positions(obs)[name]
        projected=project_eef(target,k,transform)
        seg=render_segmentation_compat(env.sim,'agentview',h,w)
        mask_cv=np.isin(seg[:,:,1],_target_geom_ids(env.sim,name))
        rr,cc=np.nonzero(mask_cv)
        if len(rr)<5:raise ValueError('No visible target for calibration audit')
        centroid_cv=np.array([np.median(cc),np.median(rr)])
        raw=env.sim.render(camera_name='agentview',height=h,width=w)
        image_raw_error=float(np.abs(image.astype(float)-raw).mean())
        image_flip_error=float(np.abs(image.astype(float)-raw[::-1]).mean())
        loc=json.loads((d/'localization.json').read_text())
        point=np.array([loc['perception_pixel_col'],loc['perception_pixel_row']])
        out=d.parent.parent/'camera_audit';out.mkdir(exist_ok=True)
        summary=dict(image_convention=macros.IMAGE_CONVENTION,offline_diagnostic_only=True,
            observation_vs_raw_render_mae=image_raw_error,observation_vs_flipped_render_mae=image_flip_error,
            target_projection_cv=projected.tolist(),target_segmentation_centroid_cv=centroid_cv.tolist(),
            localizer_output_cv=point.tolist(),localizer_cv_centroid_error=float(np.linalg.norm(point-centroid_cv)),
            row_reflection_needed_for_raw_crop=True)
        atomic_json(out/'summary.json',summary)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,2,figsize=(9,5),layout='constrained')
        for ax,im,title in zip(axes,[image,image[::-1]],['Native observation (OpenGL rows)','OpenCV camera coordinates']):
            ax.imshow(im);ax.set_title(title)
        axes[0].scatter([point[0]],[point[1]],marker='x',c='red',label='old raw crop')
        axes[0].scatter([point[0]],[h-1-point[1]],marker='+',c='lime',label='CV-to-native crop')
        axes[1].scatter([point[0]],[point[1]],marker='+',c='lime',label='localizer output')
        axes[1].scatter([projected[0]],[projected[1]],marker='x',c='red',label='GT projection (audit)')
        for ax in axes:ax.legend(fontsize=8)
        fig.savefig(out/'orientation.png',dpi=140);plt.close(fig)
        print(json.dumps(summary,indent=2))
    finally:env.close()


if __name__=='__main__':main()
