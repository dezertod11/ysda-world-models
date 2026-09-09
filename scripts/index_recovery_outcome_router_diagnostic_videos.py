#!/usr/bin/env python3
"""Validate and index portable side-by-side P3e diagnostic replay videos."""

from __future__ import annotations

import argparse
import html
import shutil
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ("baseline_h8", "workspace_retreat_only", "workspace_calibrated")


def _read_branches(directory: Path) -> pd.DataFrame:
    paths = sorted(directory.glob("*__online_branches.parquet"))
    if not paths:
        raise FileNotFoundError(f"No online branch tables in {directory}")
    return pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)


def _resolve_video(path: object) -> Path:
    candidate = Path(str(path))
    if candidate.is_file():
        return candidate.resolve()
    candidate = PROJECT_ROOT / candidate
    if not candidate.is_file():
        raise FileNotFoundError(path)
    return candidate.resolve()


def _one(frame: pd.DataFrame, case_id: str, strategy: str) -> pd.Series:
    rows = frame.loc[
        frame["case_id"].astype(str).eq(case_id)
        & frame["strategy"].astype(str).eq(strategy)
    ]
    if len(rows) != 1:
        raise RuntimeError(
            f"Expected one branch for {case_id=} {strategy=}, found {len(rows)}"
        )
    return rows.iloc[0]


def build_index(
    replay_dir: Path,
    primary_dir: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    replay_threshold: float = 1e-9,
    require_outcome_fidelity: bool = True,
) -> pd.DataFrame:
    replay = _read_branches(replay_dir)
    primary = _read_branches(primary_dir)
    manifest = pd.read_parquet(manifest_path).sort_values(
        "diagnostic_order", kind="stable"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    for case in manifest.itertuples(index=False):
        case_id = str(case.case_id)
        strategy_rows: dict[str, pd.Series] = {}
        fidelity = True
        for strategy in STRATEGIES:
            observed = _one(replay, case_id, strategy)
            expected = _one(primary, case_id, strategy)
            source = _resolve_video(observed["video_path"])
            success = bool(observed["terminal_success"])
            name = (
                f"{int(case.diagnostic_order):02d}_{case.diagnostic_role}__{strategy}__"
                f"{'success' if success else 'fail'}.mp4"
            )
            shutil.copy2(source, media_dir / name)
            outcome_match = success == bool(expected["terminal_success"])
            state_match = str(observed["prefix_state_sha256"]) == str(
                expected["prefix_state_sha256"]
            )
            replay_ok = float(observed["snapshot_replay_max_abs"]) <= replay_threshold
            fidelity = fidelity and outcome_match and state_match and replay_ok
            strategy_rows[strategy] = observed
            records.append(
                {
                    "diagnostic_order": int(case.diagnostic_order),
                    "diagnostic_role": str(case.diagnostic_role),
                    "case_id": case_id,
                    "position_level": str(case.position_level),
                    "task_id": int(case.task_id),
                    "init_state_id": int(case.init_state_id),
                    "rollout_seed": int(case.rollout_seed),
                    "strategy": strategy,
                    "terminal_success": success,
                    "terminal_final_t": int(observed["terminal_final_t"]),
                    "terminal_failure_type": str(observed["terminal_failure_type"]),
                    "primary_success": bool(expected["terminal_success"]),
                    "outcome_reproduced": outcome_match,
                    "prefix_state_reproduced": state_match,
                    "snapshot_replay_max_abs": float(
                        observed["snapshot_replay_max_abs"]
                    ),
                    "video_path": f"media/{name}",
                    "video_bytes": int((media_dir / name).stat().st_size),
                }
            )
        if require_outcome_fidelity and not fidelity:
            raise RuntimeError(f"Diagnostic replay fidelity failed for {case_id}")

    summary = pd.DataFrame(records)
    summary.to_csv(output_dir / "diagnostic_video_summary.csv", index=False)
    summary.to_parquet(output_dir / "diagnostic_video_summary.parquet", index=False)

    rows = []
    for case in manifest.itertuples(index=False):
        case_rows = summary.loc[summary["case_id"].eq(str(case.case_id))]
        cells = []
        for strategy in STRATEGIES:
            row = case_rows.loc[case_rows["strategy"].eq(strategy)].iloc[0]
            cells.append(
                "<td>"
                f"<strong>{html.escape(strategy)}</strong><br>"
                f"success={bool(row.terminal_success)}; final_t={int(row.terminal_final_t)}<br>"
                f"failure={html.escape(str(row.terminal_failure_type))}<br>"
                f"<video controls preload='metadata' width='360' src='{html.escape(str(row.video_path))}'></video>"
                "</td>"
            )
        rows.append(
            "<tr><td>"
            f"<strong>{html.escape(str(case.diagnostic_role))}</strong><br>"
            f"{html.escape(str(case.position_level))}, task={int(case.task_id)}, "
            f"init={int(case.init_state_id)}, seed={int(case.rollout_seed)}<br>"
            f"{html.escape(str(case.case_id))}</td>{''.join(cells)}</tr>"
        )
    page = (
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>P3e recovery router diagnostic replays</title><style>
body { font-family: sans-serif; margin: 20px; color: #202124; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #bbb; padding: 8px; vertical-align: top; }
th { background: #f2f3f5; text-align: left; }
video { width: 360px; max-width: 100%; background: #111; }
</style></head><body><h1>P3e recovery router diagnostic replays</h1>
<p>Exact frozen cases replayed from a common prefix. Aggregate P3e statistics remain
the primary evidence; these videos expose the intervention mechanism and failure modes.</p>
<table><thead><tr><th>Case</th><th>Baseline</th><th>Retreat only</th><th>Full RGB regrasp</th>
</tr></thead><tbody>"""
        + "\n".join(rows)
        + "</tbody></table></body></html>"
    )
    (output_dir / "VIDEO_INDEX.html").write_text(page, encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# P3e diagnostic videos\n\n"
        "Open `VIDEO_INDEX.html` for side-by-side exact-prefix replays. "
        "`diagnostic_video_summary.csv` records outcomes and replay-fidelity checks.\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--primary-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replay-threshold", type=float, default=1e-9)
    parser.add_argument(
        "--require-outcome-fidelity",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()
    summary = build_index(
        args.replay_dir.expanduser().resolve(),
        args.primary_dir.expanduser().resolve(),
        args.manifest.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        replay_threshold=args.replay_threshold,
        require_outcome_fidelity=args.require_outcome_fidelity,
    )
    print(summary.drop(columns=["video_path"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
