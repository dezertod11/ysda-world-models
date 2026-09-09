#!/usr/bin/env python3
"""Build a compact, portable index for selected P3b mechanism replays."""

from __future__ import annotations

import argparse
import html
import shutil
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_branches(run_dir: Path) -> pd.DataFrame:
    paths = sorted(run_dir.glob("*__recovery_branches.parquet"))
    if not paths:
        raise FileNotFoundError(f"No recovery branch tables in {run_dir}")
    return pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)


def _one(frame: pd.DataFrame, *, row_uid: str, proposal: str) -> pd.Series:
    rows = frame.loc[
        frame["row_uid"].astype(str).eq(row_uid)
        & frame["proposal"].astype(str).eq(proposal)
    ]
    if len(rows) != 1:
        raise RuntimeError(
            f"Expected one row for {proposal=} {row_uid=}, found {len(rows)}"
        )
    return rows.iloc[0]


def _copy_video(source: Path, destination: Path) -> str:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination.name


def build_index(campaign_dir: Path, reference_campaign: Path) -> pd.DataFrame:
    selection = pd.read_csv(campaign_dir / "mechanism_video_selection.csv")
    learned = _read_branches(campaign_dir / "runs")
    reference = _read_branches(reference_campaign / "runs")
    media_dir = campaign_dir / "media"
    records: list[dict[str, object]] = []

    for order, selected in selection.reset_index(drop=True).iterrows():
        row_uid = str(selected["row_uid"])
        role = str(selected["mechanism_role"])
        learned_row = _one(learned, row_uid=row_uid, proposal="perception_regrasp_h8")
        expected = bool(selected["expected_learned_success"])
        actual = bool(learned_row["terminal_success"])
        if actual != expected:
            raise RuntimeError(f"Non-reproducible learned outcome for {role}: {actual} != {expected}")

        learned_name = _copy_video(
            PROJECT_ROOT / str(learned_row["video_path"]),
            media_dir / f"{order + 1:02d}_{role}__learned_rgb.mp4",
        )
        privileged_name = ""
        privileged_success: object = ""
        if str(selected["mechanism_split"]) == "development":
            privileged_row = _one(
                reference, row_uid=row_uid, proposal="privileged_regrasp_h8"
            )
            privileged_success = bool(privileged_row["terminal_success"])
            privileged_name = _copy_video(
                PROJECT_ROOT / str(privileged_row["video_path"]),
                media_dir / f"{order + 1:02d}_{role}__privileged_pose.mp4",
            )

        records.append(
            {
                "order": order + 1,
                "role": role,
                "split": str(selected["mechanism_split"]),
                "position_level": str(selected["position_level"]),
                "task_id": int(selected["task_id"]),
                "init_state_id": int(selected["init_state_id"]),
                "rollout_id": int(selected["rollout_id"]),
                "target_object": str(selected["target_object"]),
                "learned_success": actual,
                "learned_failure_type": str(learned_row["terminal_failure_type"]),
                "learned_final_t": int(learned_row["terminal_final_t"]),
                "learned_video": f"media/{learned_name}",
                "privileged_success": privileged_success,
                "privileged_video": (
                    f"media/{privileged_name}" if privileged_name else ""
                ),
                "row_uid": row_uid,
            }
        )

    summary = pd.DataFrame(records)
    summary.to_csv(campaign_dir / "video_summary.csv", index=False)

    rows = []
    for record in records:
        learned_video = html.escape(str(record["learned_video"]))
        privileged_video = str(record["privileged_video"])
        privileged_cell = "not evaluated on reserve"
        if privileged_video:
            escaped = html.escape(privileged_video)
            privileged_cell = (
                f'<video controls preload="metadata" width="420" src="{escaped}"></video>'
                f'<br>success={record["privileged_success"]}'
            )
        rows.append(
            "<tr>"
            f'<td><strong>{html.escape(str(record["role"]))}</strong><br>'
            f'{html.escape(str(record["split"]))}; '
            f'{html.escape(str(record["position_level"]))}/task{record["task_id"]}; '
            f'init={record["init_state_id"]}, rollout={record["rollout_id"]}<br>'
            f'target={html.escape(str(record["target_object"]))}</td>'
            f'<td><video controls preload="metadata" width="420" src="{learned_video}"></video>'
            f'<br>success={record["learned_success"]}; '
            f'failure={html.escape(str(record["learned_failure_type"]))}; '
            f'final_t={record["learned_final_t"]}</td>'
            f"<td>{privileged_cell}</td>"
            "</tr>"
        )
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>P3b perception regrasp mechanism replays</title>
<style>
body { font-family: sans-serif; margin: 24px; color: #202124; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #bbb; padding: 10px; vertical-align: top; }
th { background: #f2f3f5; text-align: left; }
video { max-width: 100%; background: #111; }
</style></head><body>
<h1>P3b perception-backed regrasp: selected exact-state replays</h1>
<p>Illustrative mechanism evidence selected after aggregate evaluation. These five
replays are not an additional statistical test.</p>
<table><thead><tr><th>Case</th><th>Learned RGB regrasp</th>
<th>Privileged-pose upper bound</th></tr></thead><tbody>
""" + "\n".join(rows) + """
</tbody></table></body></html>
"""
    (campaign_dir / "video_index.html").write_text(page, encoding="utf-8")

    readme = """# P3b mechanism videos

Five exact-state replays illustrate the confirmed perception-backed regrasp
result and its boundary. Open `video_index.html` to compare learned RGB regrasp
with the privileged-pose upper bound side by side. Reserve rows have no
privileged replay because that split was opened only once for the frozen
deployable method.

The selection was made after the aggregate evaluation, so these videos are
mechanism illustrations rather than additional statistical evidence. Numeric
outcomes and exact state identifiers are in `video_summary.csv`.
"""
    (campaign_dir / "README.md").write_text(readme, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--reference-campaign", type=Path, required=True)
    args = parser.parse_args()
    summary = build_index(
        args.campaign_dir.expanduser().resolve(),
        args.reference_campaign.expanduser().resolve(),
    )
    print(summary.drop(columns=["row_uid"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
