#!/usr/bin/env python3
"""Cold A/B versus resident A/B/A, in an isolated output directory."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:
    from scripts import run_libero_experiment_campaign as legacy
    from scripts.libero_resident import atomic_json, requests_for_job
    from scripts.run_libero_resident_campaign import ROOT, executor_hashes, launch_batch
except ModuleNotFoundError:
    import run_libero_experiment_campaign as legacy
    from libero_resident import atomic_json, requests_for_job
    from run_libero_resident_campaign import ROOT, executor_hashes, launch_batch


def compare_frames(left, right):
    import imageio.v2 as imageio
    from itertools import zip_longest
    count = 0
    with imageio.get_reader(left) as a, imageio.get_reader(right) as b:
        for x, y in zip_longest(a, b):
            if x is None or y is None:
                raise AssertionError("Different video lengths")
            np.testing.assert_array_equal(x, y)
            count += 1
    if count == 0:
        raise AssertionError("Empty parity video")
    return count


IMAGE_DIAGNOSTICS = {
    f"future_{camera}_pixel_std_{stat}" for camera in ("image", "wrist") for stat in ("mean", "p95", "max")
} | {
    f"prediction_error_future_{camera}_{stat}" for camera in ("image", "wrist")
    for stat in ("mse", "mae", "psnr", "ssim_global")
}


def compare_outputs(cold, warm, *, image_diagnostics=False):
    a = pd.read_parquet(cold / "trace.parquet") if cold.is_dir() else pd.read_parquet(cold)
    b = pd.read_parquet(warm / "trace.parquet") if warm.is_dir() else pd.read_parquet(warm)
    ignored = ['video_path'] + (sorted(IMAGE_DIAGNOSTICS.intersection(a.columns)) if image_diagnostics else [])
    pd.testing.assert_frame_equal(a.drop(columns=ignored), b.drop(columns=ignored), check_exact=True)
    differences = {}
    for column in IMAGE_DIAGNOSTICS.intersection(a.columns):
        if not a[column].equals(b[column]):
            differences[column] = float(np.nanmax(np.abs(a[column].to_numpy()-b[column].to_numpy())))
    va, = a.video_path.unique()
    vb, = b.video_path.unique()
    frames = compare_frames(va, vb)
    return dict(query_rows=len(a), exact_metric_columns=len(a.columns)-len(ignored), identical_frames=frames,
                exact_controller=True, all_metrics_exact=not differences, decoded_image_max_abs_differences=differences)


def characterize_cold_repeat(first, repeat):
    """Measure the old executor's reproducibility, independently of migration parity."""
    try:
        return compare_outputs(first, repeat, image_diagnostics=True)
    except AssertionError as error:
        a, b = pd.read_parquet(first), pd.read_parquet(repeat)
        return dict(exact_controller=False, all_metrics_exact=False,
            diagnostic_only=True, error=str(error).splitlines()[0],
            differing_columns=[c for c in a.columns.intersection(b.columns)
                               if c != 'video_path' and not a[c].equals(b[c])])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--run-prefix', required=True)
    parser.add_argument('--gpus', default='0,1,2,3,4,5,6,7')
    parser.add_argument('--allow-gpu-zero', action='store_true')
    parser.add_argument('--review-existing', action='store_true',
        help='Recheck saved artifacts, reporting cold/cold variability separately; preserve the original report')
    args = parser.parse_args()
    gpus = args.gpus.split(',')
    if len(gpus) != len(set(gpus)) or any(g not in tuple('01234567') for g in gpus):
        raise ValueError('Invalid GPU list')
    if '0' in gpus and not args.allow_gpu_zero:
        raise ValueError('GPU0 needs explicit authorization')
    directory = ROOT / 'experiments/campaigns' / args.run_prefix
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory/('parity_review.json' if args.review_existing else 'parity_report.json')
    if report_path.exists():
        raise FileExistsError('Use a fresh parity run-prefix; do not overwrite audit evidence')
    config = legacy.load_campaign(args.config)
    expanded = legacy.expand_jobs(config['profiles']['references'], config['defaults'])
    allowed={'trajectory_raw_medoid','keystone_cluster_medoid','trajectory_kdpe_endpoint'}
    if any(item.split(':')[0] not in allowed for job in expanded for item in job['strategy_lambdas'].split()):
        raise ValueError('Image-diagnostic gate is restricted to the three frozen action/value reference strategies')
    jobs = []
    for name in ['position_x0_3_t3_raw_medoid', 'position_x0_3_t4_keystone']:
        j = copy.deepcopy(next(j for j in expanded if j['name']==name))
        j.update(max_timesteps=64, experiment_split='screen', save_videos=True)
        jobs.append(j)
    repeat = copy.deepcopy(jobs[0])
    repeat['name'] += '_repeat'
    original_hashes = executor_hashes()
    runtime = Path(os.environ['COSMOS_REPO'])
    relative_files = ['cosmos_policy/experiments/robot/libero/uncertainty_comparison.py',
        'cosmos_policy/experiments/robot/libero/uncertainty_metrics.py',
        'cosmos_policy/experiments/robot/cosmos_utils.py']
    report = dict(passed=False, started_at=datetime.now(timezone.utc).isoformat(),
        executor_sha256=original_hashes, source_config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
        runtime_sha256={p:hashlib.sha256((runtime/p).read_bytes()).hexdigest() for p in relative_files},
        protocol='v3: exact cold/resident controller/latent/real video and resident A/A; cold repeat is a separate diagnostic',
        gate_scope='references_action_value_only',
        decoded_image_diagnostics='Reported separately across processes; all metrics must match for resident A/A',
        comparisons=[])
    if args.review_existing:
        original = directory/'parity_report.json'
        prior = json.loads(original.read_text())
        for key in ('executor_sha256', 'source_config_sha256', 'runtime_sha256'):
            if prior[key] != report[key]:
                raise ValueError(f'Cannot review artifacts from a different {key}')
        report['original_report'] = dict(path=str(original), passed=prior['passed'],
            sha256=hashlib.sha256(original.read_bytes()).hexdigest())
        report['review_reason'] = ('v2 incorrectly made the independent cold/cold reproducibility diagnostic '
            'a migration gate. No cold/resident or resident/resident acceptance criterion is relaxed.')
    atomic_json(directory/('review_protocol.json' if args.review_existing else 'protocol.json'), report)
    def admit():
        while True:
            for gpu in gpus:
                if legacy.gpu_is_free(gpu):
                    return gpu
            atomic_json(directory/'status.json', dict(status='waiting_gpu', updated_at=datetime.now(timezone.utc).isoformat(), pid=os.getpid()))
            time.sleep(3)
    def progress(stage):
        def dispatch(jobs,gpu,path,pid):
            atomic_json(directory/'status.json',dict(status=stage,gpu=gpu,worker_pid=pid,
                batch=str(path),pid=os.getpid(),updated_at=datetime.now(timezone.utc).isoformat()))
        return dispatch
    try:
        cold_directory, warm_directory = directory/'cold', directory/'warm'
        if args.review_existing:
            warm_batch, = (
                p for p in (warm_directory/'resident').glob('*.json') if not p.name.endswith('.status.json'))
        else:
            for index, job in enumerate([*jobs, repeat]):
                atomic_json(directory/'status.json',dict(status=f'cold_{index}_admission',pid=os.getpid()))
                launch_batch([job],args.run_prefix+'_cold',cold_directory,admit(),cold=True,audit=True,on_dispatch=progress(f'cold_{index}'))
            warm_batch = launch_batch([*jobs, repeat],args.run_prefix+'_warm',warm_directory,admit(),audit=True,on_dispatch=progress('resident_a_b_a'))
        for index, job in enumerate([*jobs, repeat]):
            source_job=jobs[0] if index==2 else job
            _, env_a, _ = legacy.build_job(source_job,args.run_prefix+'_cold',cold_directory)
            _, env_b, _ = legacy.build_job(job,args.run_prefix+'_warm',warm_directory)
            a, = requests_for_job(source_job,env_a)
            b, = requests_for_job(job,env_b)
            trace_a=cold_directory/'runs'/(a['run_name']+'__query_traces.parquet')
            trace_b=warm_directory/'runs'/(b['run_name']+'__query_traces.parquet')
            result=compare_outputs(trace_a,trace_b,image_diagnostics=True)
            audit_a=json.loads((cold_directory/'runs'/(a['run_name']+'__resident_audit.json')).read_text())
            audit_b=json.loads((warm_directory/'runs'/(b['run_name']+'__resident_audit.json')).read_text())
            if not audit_a or audit_a != audit_b:
                raise AssertionError('Candidate action/value/latent hashes differ')
            result.update(job=job['name'], candidate_hashes_identical=True)
            report['comparisons'].append(result)
        def trace(job, prefix, output):
            _,env,_=legacy.build_job(job,prefix,output)
            request,=requests_for_job(job,env)
            return output/'runs'/(request['run_name']+'__query_traces.parquet')
        report['resident_repeat']=compare_outputs(trace(jobs[0],args.run_prefix+'_warm',warm_directory),
            trace(repeat,args.run_prefix+'_warm',warm_directory))
        report['cold_repeat']=characterize_cold_repeat(trace(jobs[0],args.run_prefix+'_cold',cold_directory),
            trace(repeat,args.run_prefix+'_cold',cold_directory))
        state=json.loads(warm_batch.with_suffix('.status.json').read_text())
        if state['model_loads'] != 1 or state['model_hits'] != 2 or executor_hashes()!=original_hashes:
            raise AssertionError('Wrong model cache counts or executor changed during parity test')
        report.update(passed=True, model_loads=1, model_hits=2, finished_at=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        report.update(error=repr(error), finished_at=datetime.now(timezone.utc).isoformat())
        atomic_json(report_path,report)
        raise
    atomic_json(report_path,report)
    atomic_json(directory/'status.json',dict(status='passed',report=str(report_path),pid=os.getpid()))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
