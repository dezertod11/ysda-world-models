#!/usr/bin/env python3
"""Universal progress and ETA monitor for manifest-based LIBERO campaigns."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN_ROOT = PROJECT_ROOT / "experiments" / "campaigns"
FINAL_STATES = {"READY", "FAILED", "STALLED", "MISSING"}
EPISODE_KEYS = ("pair_id", "rollout_id", "episode_id", "rollout_seed", "seed")


@dataclass(frozen=True)
class TraceStats:
    files: int = 0
    rollouts: int = 0
    successes: int = 0
    failures: int = 0


@dataclass(frozen=True)
class JobStatus:
    name: str
    gpu: str
    state: str
    completed_rollouts: int
    expected_rollouts: int | None
    elapsed_seconds: float | None
    log_age_seconds: float | None


@dataclass(frozen=True)
class CampaignStatus:
    name: str
    path: str
    state: str
    manifest_status: str
    profile: str
    created_at: str | None
    finished_at: str | None
    elapsed_seconds: float | None
    completed_jobs: int
    total_jobs: int
    trace_stats: TraceStats
    expected_rollouts: int | None
    eta_seconds: float | None
    eta_at: str | None
    active_processes: tuple[str, ...]
    activity_age_seconds: float | None
    analysis_summaries: int
    analysis_reports: int
    jobs: tuple[JobStatus, ...]


class TraceCounter:
    """Cache trace counts while watch mode repeatedly polls unchanged files."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], TraceStats] = {}

    def count(self, path: Path) -> TraceStats:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        value = _count_trace(path)
        self._cache = {item: result for item, result in self._cache.items() if item[0] != str(path)}
        self._cache[key] = value
        return value


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _selector_count(value: Any) -> int:
    """Count comma-separated ids, including inclusive integer ranges such as 0-3."""

    text = str(value or "").strip()
    if not text:
        return 1
    count = 0
    for token in re.split(r"[\s,]+", text):
        if not token:
            continue
        match = re.fullmatch(r"(-?\d+)-(-?\d+)", token)
        if match:
            start, end = map(int, match.groups())
            count += abs(end - start) + 1
        else:
            count += 1
    return max(count, 1)


def _env_value(environment: Mapping[str, Any], suffixes: Sequence[str]) -> str | None:
    for suffix in suffixes:
        for key, value in environment.items():
            if key.endswith(suffix):
                return str(value)
    return None


def expected_job_rollouts(job: Mapping[str, Any]) -> int | None:
    """Infer the maximum planned strategy executions from a manifest job."""

    environment = job.get("environment", {})
    if not isinstance(environment, Mapping):
        return None
    maximum = _env_value(
        environment,
        ("MAX_ROLLOUTS_PER_INIT", "MAX_ROLLOUTS", "EPISODES_PER_TASK"),
    )
    if maximum is None:
        return None
    try:
        per_init = int(maximum)
    except ValueError:
        return None

    suites = _selector_count(_env_value(environment, ("SUITES",)) or "")
    tasks = _selector_count(_env_value(environment, ("TASK_IDS",)) or "")
    inits = _selector_count(_env_value(environment, ("INIT_STATE_IDS",)) or "")
    strategy_text = _env_value(environment, ("STRATEGY_LAMBDAS",))
    strategies = len(shlex.split(strategy_text)) if strategy_text else 1
    return per_init * suites * tasks * inits * max(strategies, 1)


def _trace_columns(path: Path) -> list[str]:
    desired = {*EPISODE_KEYS, "success"}
    if path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq

            available = set(pq.ParquetFile(path).schema.names)
        except Exception:
            return []
    else:
        try:
            available = set(pd.read_csv(path, nrows=0).columns)
        except Exception:
            return []
    return [column for column in (*EPISODE_KEYS, "success") if column in available and column in desired]


def _as_success(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def _count_trace(path: Path) -> TraceStats:
    columns = _trace_columns(path)
    if "pair_id" in columns and "rollout_id" in columns:
        episode_keys = ["pair_id", "rollout_id"]
    else:
        episode_key = next((key for key in EPISODE_KEYS if key in columns), None)
        episode_keys = [episode_key] if episode_key else []
    if not episode_keys:
        return TraceStats(files=1)
    try:
        if path.suffix == ".parquet":
            frame = pd.read_parquet(path, columns=columns)
        else:
            frame = pd.read_csv(path, usecols=columns)
    except Exception:
        return TraceStats(files=1)
    if frame.empty:
        return TraceStats(files=1)
    episodes = frame.drop_duplicates(episode_keys, keep="first")
    if "success" not in episodes:
        return TraceStats(files=1, rollouts=len(episodes))
    success = _as_success(episodes["success"])
    return TraceStats(
        files=1,
        rollouts=len(episodes),
        successes=int(success.sum()),
        failures=int((~success).sum()),
    )


def _preferred_trace_paths(run_dir: Path) -> list[Path]:
    candidates = list((run_dir / "runs").glob("*__query_traces.parquet"))
    candidates += list((run_dir / "runs").glob("*__query_traces.csv"))
    selected: dict[str, Path] = {}
    for path in sorted(candidates):
        identity = path.with_suffix("").name
        current = selected.get(identity)
        if current is None or path.suffix == ".parquet":
            selected[identity] = path
    return sorted(selected.values())


def _sum_stats(values: Iterable[TraceStats]) -> TraceStats:
    values = list(values)
    return TraceStats(
        files=sum(value.files for value in values),
        rollouts=sum(value.rollouts for value in values),
        successes=sum(value.successes for value in values),
        failures=sum(value.failures for value in values),
    )


def _job_trace_stats(
    manifest: Mapping[str, Any],
    paths: Sequence[Path],
    counter: TraceCounter,
) -> tuple[TraceStats, dict[str, TraceStats]]:
    jobs = list(manifest.get("jobs", []))
    prefix = str(manifest.get("run_prefix", ""))
    names = sorted((str(job.get("name", "")) for job in jobs), key=len, reverse=True)
    by_job: dict[str, list[TraceStats]] = {name: [] for name in names}
    all_stats: list[TraceStats] = []
    for path in paths:
        stats = counter.count(path)
        all_stats.append(stats)
        filename = path.name
        for name in names:
            if filename.startswith(f"{prefix}__{name}__") or filename.startswith(
                f"{prefix}__{name}__query_traces"
            ):
                by_job[name].append(stats)
                break
    return _sum_stats(all_stats), {name: _sum_stats(items) for name, items in by_job.items()}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _last_job_start(log_path: Path) -> datetime | None:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    matches = re.findall(r"^\[([^]]+)]\s+GPU=.*?\s+job=", text, flags=re.MULTILINE)
    return _parse_time(matches[-1]) if matches else None


def _active_processes(campaign_dir: Path) -> tuple[str, ...]:
    try:
        output = subprocess.run(
            ["ps", "-eo", "pid=,etimes=,args="],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
    except OSError:
        return ()
    needles = (campaign_dir.name, str(campaign_dir))
    matches = []
    for line in output.splitlines():
        if not any(needle in line for needle in needles):
            continue
        if "status_libero_campaign.py" in line:
            continue
        matches.append(line.strip())
    return tuple(matches[:8])


def _latest_activity(paths: Iterable[Path]) -> datetime | None:
    timestamps = []
    for path in paths:
        try:
            timestamps.append(path.stat().st_mtime)
        except OSError:
            continue
    return datetime.fromtimestamp(max(timestamps)) if timestamps else None


def _format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "unknown"
    seconds = max(int(round(seconds)), 0)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def _marker_duration(marker: Mapping[str, Any]) -> float | None:
    started = _parse_time(marker.get("started_at"))
    finished = _parse_time(marker.get("finished_at"))
    if started is None or finished is None:
        return None
    return max((finished - started).total_seconds(), 0.0)


def _estimate_eta(
    jobs: Sequence[Mapping[str, Any]],
    markers: Mapping[str, Mapping[str, Any]],
    job_stats: Mapping[str, TraceStats],
    starts: Mapping[str, datetime | None],
    now: datetime,
) -> float | None:
    if jobs and all(str(job.get("name")) in markers for job in jobs):
        return 0.0

    seconds_per_rollout = []
    completed_durations = []
    for job in jobs:
        name = str(job.get("name", ""))
        marker = markers.get(name)
        if not marker:
            continue
        duration = _marker_duration(marker)
        if duration is None:
            continue
        completed_durations.append(duration)
        observed = job_stats.get(name, TraceStats()).rollouts
        denominator = observed or expected_job_rollouts(job)
        if denominator:
            seconds_per_rollout.append(duration / denominator)

    per_rollout = statistics.median(seconds_per_rollout) if seconds_per_rollout else None
    per_job = statistics.median(completed_durations) if completed_durations else None
    if per_rollout is None and per_job is None:
        active_observed = sum(value.rollouts for value in job_stats.values())
        active_starts = [value for value in starts.values() if value is not None]
        if active_observed and active_starts:
            elapsed = max((now - min(active_starts)).total_seconds(), 1.0)
            per_rollout = elapsed * max(len(active_starts), 1) / active_observed
        else:
            return None

    gpu_remaining: dict[str, float] = {}
    for job in jobs:
        name = str(job.get("name", ""))
        if name in markers:
            continue
        gpu = str(job.get("gpu", "?"))
        expected = expected_job_rollouts(job)
        observed = job_stats.get(name, TraceStats()).rollouts
        if expected is not None and per_rollout is not None:
            estimate = max(expected - observed, 0) * per_rollout
        elif per_job is not None:
            start = starts.get(name)
            elapsed = max((now - start).total_seconds(), 0.0) if start else 0.0
            estimate = max(per_job - elapsed, 0.0)
        else:
            return None
        gpu_remaining[gpu] = gpu_remaining.get(gpu, 0.0) + estimate
    return max(gpu_remaining.values(), default=0.0)


def inspect_campaign(
    campaign_dir: Path,
    counter: TraceCounter,
    *,
    include_traces: bool = True,
    stale_minutes: float = 30.0,
) -> CampaignStatus:
    manifest_path = campaign_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    if not manifest:
        return CampaignStatus(
            name=campaign_dir.name,
            path=str(campaign_dir),
            state="MISSING",
            manifest_status="missing",
            profile="",
            created_at=None,
            finished_at=None,
            elapsed_seconds=None,
            completed_jobs=0,
            total_jobs=0,
            trace_stats=TraceStats(),
            expected_rollouts=None,
            eta_seconds=None,
            eta_at=None,
            active_processes=(),
            activity_age_seconds=None,
            analysis_summaries=0,
            analysis_reports=0,
            jobs=(),
        )

    now = datetime.now()
    jobs = list(manifest.get("jobs", []))
    marker_records = {
        path.stem: _read_json(path)
        for path in (campaign_dir / "completed").glob("*.json")
        if path.is_file()
    }
    manifest_results = {
        str(result.get("job", "")): result
        for result in manifest.get("results", [])
        if isinstance(result, Mapping) and result.get("job")
    }
    completion_records = {
        name: result
        for name, result in manifest_results.items()
        if str(result.get("status", "")).lower() in {"completed", "skipped"}
    }
    completion_records.update(marker_records)
    trace_paths = _preferred_trace_paths(campaign_dir) if include_traces else []
    trace_stats, job_trace_stats = _job_trace_stats(manifest, trace_paths, counter)
    exclusion_payload = _read_json(campaign_dir / "benchmark_exclusions.json")
    excluded_by_job: dict[str, int] = {}
    for exclusion in exclusion_payload.get("exclusions", []):
        if not isinstance(exclusion, Mapping) or not exclusion.get("job"):
            continue
        name = str(exclusion["job"])
        excluded_by_job[name] = excluded_by_job.get(name, 0) + int(
            exclusion.get("method_episodes", 1)
        )

    def valid_expected_rollouts(job: Mapping[str, Any]) -> int | None:
        expected = expected_job_rollouts(job)
        if expected is None:
            return None
        return max(expected - excluded_by_job.get(str(job.get("name", "")), 0), 0)

    expected_values = [valid_expected_rollouts(job) for job in jobs]
    expected_rollouts = (
        sum(value for value in expected_values if value is not None)
        if expected_values and all(value is not None for value in expected_values)
        else None
    )

    starts: dict[str, datetime | None] = {}
    job_rows = []
    activity_paths = [manifest_path, *trace_paths, *campaign_dir.glob("completed/*.json")]
    for job in jobs:
        name = str(job.get("name", ""))
        log_path = campaign_dir / "logs" / f"{name}.log"
        activity_paths.append(log_path)
        record = completion_records.get(name) or manifest_results.get(name)
        start = _parse_time(record.get("started_at")) if record else _last_job_start(log_path)
        starts[name] = start
        if name in completion_records:
            state = "COMPLETED"
            elapsed = _marker_duration(completion_records[name])
        elif record and str(record.get("status", "")).lower() == "failed":
            state = "FAILED"
            elapsed = _marker_duration(record)
        elif start:
            state = "RUNNING"
            elapsed = max((now - start).total_seconds(), 0.0)
        else:
            state = "PENDING"
            elapsed = None
        try:
            log_age = max(now.timestamp() - log_path.stat().st_mtime, 0.0)
        except OSError:
            log_age = None
        job_rows.append(
            JobStatus(
                name=name,
                gpu=str(job.get("gpu", "?")),
                state=state,
                completed_rollouts=job_trace_stats.get(name, TraceStats()).rollouts,
                expected_rollouts=valid_expected_rollouts(job),
                elapsed_seconds=elapsed,
                log_age_seconds=log_age,
            )
        )

    active = _active_processes(campaign_dir)
    latest_activity = _latest_activity(activity_paths)
    activity_age = (
        max((now - latest_activity).total_seconds(), 0.0) if latest_activity else None
    )
    manifest_status = str(manifest.get("status", "missing")).lower()
    if manifest_status == "failed":
        state = "FAILED"
    elif manifest_status == "completed":
        state = "FINALIZING" if active else "READY"
    elif manifest_status == "planned":
        state = "PLANNED"
    elif manifest_status == "running":
        stale = activity_age is not None and activity_age > stale_minutes * 60
        state = "STALLED" if stale and not active else "RUNNING"
    else:
        state = manifest_status.upper() or "UNKNOWN"

    created = _parse_time(manifest.get("created_at"))
    finished = _parse_time(manifest.get("finished_at"))
    endpoint = finished or now
    elapsed = max((endpoint - created).total_seconds(), 0.0) if created else None
    eta_seconds = None
    if manifest_status == "running":
        eta_seconds = _estimate_eta(jobs, completion_records, job_trace_stats, starts, now)
    elif manifest_status == "completed":
        eta_seconds = 0.0
    eta_at = (now + timedelta(seconds=eta_seconds)).isoformat(timespec="minutes") if eta_seconds else None

    summary_files = list((campaign_dir / "analysis").rglob("summary.json"))
    report_files = list((campaign_dir / "analysis").rglob("README.md"))
    report_files += list((campaign_dir / "analysis").rglob("RESULTS.md"))
    return CampaignStatus(
        name=campaign_dir.name,
        path=str(campaign_dir),
        state=state,
        manifest_status=manifest_status,
        profile=str(manifest.get("profile", "")),
        created_at=str(manifest.get("created_at")) if manifest.get("created_at") else None,
        finished_at=str(manifest.get("finished_at")) if manifest.get("finished_at") else None,
        elapsed_seconds=elapsed,
        completed_jobs=len(completion_records),
        total_jobs=len(jobs),
        trace_stats=trace_stats,
        expected_rollouts=expected_rollouts,
        eta_seconds=eta_seconds,
        eta_at=eta_at,
        active_processes=active,
        activity_age_seconds=activity_age,
        analysis_summaries=len(summary_files),
        analysis_reports=len(report_files),
        jobs=tuple(job_rows),
    )


def _progress(current: int, total: int | None) -> str:
    if not total:
        return str(current)
    percentage = 100.0 * current / total
    return f"{current}/{total} ({percentage:.1f}%)"


def render_status(status: CampaignStatus, *, verbose: bool = False) -> str:
    marker = {
        "READY": "READY",
        "RUNNING": "RUNNING",
        "FINALIZING": "FINALIZING",
        "FAILED": "FAILED",
        "STALLED": "STALLED",
        "PLANNED": "PLANNED",
    }.get(status.state, status.state)
    lines = [
        f"Campaign : {status.name}",
        f"State    : {marker} (manifest={status.manifest_status})",
        f"Profile  : {status.profile or '-'}",
        f"Jobs     : {_progress(status.completed_jobs, status.total_jobs)}",
    ]
    if status.trace_stats.files:
        outcome = (
            f", success={status.trace_stats.successes}, fail={status.trace_stats.failures}"
            if status.trace_stats.successes + status.trace_stats.failures
            else ""
        )
        lines.append(
            f"Rollouts : {_progress(status.trace_stats.rollouts, status.expected_rollouts)}"
            f" in {status.trace_stats.files} traces{outcome}"
        )
    elif status.expected_rollouts:
        lines.append(
            f"Rollouts : traces unavailable in this copy; planned <= {status.expected_rollouts}"
        )
    lines.append(f"Elapsed  : {_format_duration(status.elapsed_seconds)}")
    if status.state == "RUNNING":
        eta = _format_duration(status.eta_seconds)
        suffix = f"; approximately {status.eta_at}" if status.eta_at else ""
        lines.append(f"ETA      : ~{eta}{suffix}")
    elif status.state == "FINALIZING":
        lines.append("ETA      : rollout finished; aggregate analysis is still active")
    elif status.state == "READY":
        lines.append("ETA      : complete")
    if status.activity_age_seconds is not None:
        lines.append(f"Activity : {_format_duration(status.activity_age_seconds)} ago")
    lines.append(
        f"Analysis : {status.analysis_summaries} summary.json, "
        f"{status.analysis_reports} report files"
    )
    if status.state == "READY":
        lines.append("Verdict  : execution is complete; results are safe to inspect")
    elif status.state == "STALLED":
        lines.append("Verdict  : manifest says running, but no process/recent activity was found")
    elif status.state == "FAILED":
        lines.append("Verdict  : inspect failed job logs before using partial results")
    else:
        lines.append("Verdict  : wait; do not treat partial results as final")

    visible_jobs = status.jobs if verbose else tuple(job for job in status.jobs if job.state != "COMPLETED")
    if visible_jobs:
        lines.append("Jobs:")
        for job in visible_jobs:
            rollout = _progress(job.completed_rollouts, job.expected_rollouts)
            age = f", log {_format_duration(job.log_age_seconds)} ago" if job.log_age_seconds is not None else ""
            elapsed = f", elapsed {_format_duration(job.elapsed_seconds)}" if job.elapsed_seconds is not None else ""
            lines.append(
                f"  GPU {job.gpu:>2}  {job.state:<9}  {rollout:<18}  {job.name}{elapsed}{age}"
            )
    if verbose and status.active_processes:
        lines.append("Active processes:")
        lines.extend(f"  {line}" for line in status.active_processes)
    return "\n".join(lines)


def _campaign_dirs(root: Path) -> list[Path]:
    return sorted(
        (path.parent for path in root.glob("*/manifest.json")),
        key=lambda path: path.joinpath("manifest.json").stat().st_mtime,
        reverse=True,
    )


def _campaign_activity_timestamp(campaign_dir: Path) -> float:
    paths = [campaign_dir / "manifest.json"]
    paths.extend((campaign_dir / "logs").glob("*.log"))
    paths.extend((campaign_dir / "completed").glob("*.json"))
    paths.extend((campaign_dir / "runs").glob("*__query_traces.*"))
    timestamps = []
    for path in paths:
        try:
            timestamps.append(path.stat().st_mtime)
        except OSError:
            continue
    return max(timestamps, default=0.0)


def resolve_campaign(root: Path, value: str, *, stale_minutes: float = 30.0) -> Path:
    candidate = Path(value).expanduser()
    if value not in {"latest", ""} and candidate.is_dir():
        return candidate.resolve()
    if value not in {"latest", ""}:
        return (root / value).resolve()
    directories = _campaign_dirs(root)
    now = time.time()
    for directory in directories:
        status = _read_json(directory / "manifest.json").get("status")
        activity_age = now - _campaign_activity_timestamp(directory)
        if status == "running" and activity_age <= stale_minutes * 60:
            return directory.resolve()
    return directories[0].resolve() if directories else (root / "missing").resolve()


def render_all(root: Path, counter: TraceCounter, limit: int, stale_minutes: float) -> str:
    rows = []
    for directory in _campaign_dirs(root)[:limit]:
        status = inspect_campaign(
            directory,
            counter,
            include_traces=False,
            stale_minutes=stale_minutes,
        )
        if status.state == "READY":
            eta = "done"
        elif status.eta_seconds is not None:
            eta = f"~{_format_duration(status.eta_seconds)}"
        else:
            eta = "-"
        rows.append(
            f"{status.state:<10} jobs={status.completed_jobs:>2}/{status.total_jobs:<2} "
            f"eta={eta:<10} {status.name}"
        )
    return "\n".join(rows) if rows else f"No manifests under {root}"


def _status_as_json(status: CampaignStatus) -> str:
    return json.dumps(asdict(status), ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show completion, active jobs, rollout progress and ETA for LIBERO campaigns."
    )
    parser.add_argument("campaign", nargs="?", default="latest", help="campaign name/path or latest")
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--all", action="store_true", help="list recent campaigns")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--watch", type=float, metavar="SECONDS", help="poll until a final state")
    parser.add_argument("--stale-minutes", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.campaign_root.expanduser().resolve()
    counter = TraceCounter()
    while True:
        if args.all:
            output = render_all(root, counter, args.limit, args.stale_minutes)
            state = "READY"
        else:
            campaign_dir = resolve_campaign(
                root,
                args.campaign,
                stale_minutes=args.stale_minutes,
            )
            status = inspect_campaign(
                campaign_dir,
                counter,
                include_traces=True,
                stale_minutes=args.stale_minutes,
            )
            output = _status_as_json(status) if args.json else render_status(status, verbose=args.verbose)
            state = status.state
        if args.watch and sys.stdout.isatty():
            print("\033[2J\033[H", end="")
        if args.json and not args.all:
            print(output, flush=True)
        else:
            print(f"Checked  : {datetime.now().isoformat(timespec='seconds')}")
            print(output, flush=True)
        if not args.watch or state in FINAL_STATES:
            if state == "READY":
                return 0
            if state in {"RUNNING", "FINALIZING", "PLANNED"}:
                return 3
            return 1
        time.sleep(max(args.watch, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
