#!/usr/bin/env python3
"""Create a portable manifest and gallery for adaptive-planning video replays."""

from __future__ import annotations

import argparse
import csv
import html
import shutil
from pathlib import Path
from typing import Sequence

from analyze_adaptive_planning_campaign import episode_table, load_traces


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def read_selection(path: Path) -> dict[tuple[str, int], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    return {
        (row["case_id"], int(float(row["rollout_seed"]))): row for row in rows
    }


def find_video(video_root: Path, run_name: str) -> Path:
    matches = [
        path
        for path in video_root.rglob("*.mp4")
        if run_name in path.parts
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one video for {run_name}, found {len(matches)} under {video_root}"
        )
    return matches[0]


def portable_name(row) -> str:
    success = "success" if bool(row.success) else "fail"
    return (
        f"{row.case_id}__seed{int(row.rollout_seed)}__"
        f"{row.strategy_id}__{success}.mp4"
    )


def write_readme(rows: list[dict[str, object]], output_dir: Path) -> None:
    keys = sorted({(str(row["case_id"]), int(row["rollout_seed"])) for row in rows})
    reproduced = sum(
        bool(
            next(
                row["selected_pair_reproduced"]
                for row in rows
                if row["case_id"] == case_id
                and int(row["rollout_seed"]) == seed
            )
        )
        for case_id, seed in keys
    )
    lines = [
        "# Adaptive planning confirmatory videos",
        "",
        "These matched-seed videos were chosen mechanically from discordant frozen",
        "confirmatory outcomes. They are qualitative replays; success-rate estimates",
        "come from the complete campaign, not this selected gallery.",
        f"The original selected-strategy pair reproduced both outcomes in "
        f"{reproduced}/{len(keys)} exact replays.",
        "",
    ]
    for case_id, seed in keys:
        selected = [
            row
            for row in rows
            if row["case_id"] == case_id and int(row["rollout_seed"]) == seed
        ]
        reason = selected[0]["selection_reason"]
        category = selected[0]["selection_category"]
        selected_strategy = selected[0]["selected_strategy_id"]
        baseline_outcome = (
            "SUCCESS" if selected[0]["original_baseline_success"] else "FAIL"
        )
        strategy_outcome = (
            "SUCCESS" if selected[0]["original_selected_success"] else "FAIL"
        )
        reproduced = bool(selected[0]["selected_pair_reproduced"])
        lines.extend(
            [
                f"## {case_id}, seed {seed}",
                "",
                f"Selected as `{category}` / `{reason}` in the original confirmatory run.",
                f"Original pair: `max_value` {baseline_outcome}, "
                f"`{selected_strategy}` {strategy_outcome}. Exact replay pair "
                f"{'reproduced' if reproduced else 'did not reproduce'} both outcomes.",
                "",
                "<table><tr>",
            ]
        )
        for row in selected:
            outcome = "SUCCESS" if row["success"] else "FAIL"
            filename = html.escape(str(row["filename"]))
            lines.append(
                '<td style="vertical-align:top;padding:8px">'
                f"<b>{html.escape(str(row['strategy_id']))}</b><br>"
                f"{outcome}, t={int(row['final_t'])}<br>"
                f'<video controls preload="metadata" width="280" src="{filename}"></video>'
                f'<br><a href="{filename}">Open MP4</a></td>'
            )
        lines.extend(["</tr></table>", ""])
    (output_dir / "README.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    campaign_dir = args.campaign_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selections = read_selection(args.selection_manifest)
    episodes = episode_table(load_traces([campaign_dir])).sort_values(
        ["case_id", "rollout_seed", "strategy_id"]
    )
    rows: list[dict[str, object]] = []
    for episode in episodes.itertuples(index=False):
        key = (str(episode.case_id), int(episode.rollout_seed))
        if key not in selections:
            raise RuntimeError(f"Replay episode is absent from selection manifest: {key}")
        selection = selections[key]
        run_name = str(episode.source_run).split("/", 1)[-1]
        source_video = find_video(campaign_dir / "videos", run_name)
        filename = portable_name(episode)
        destination = output_dir / filename
        shutil.copy2(source_video, destination)
        rows.append(
            {
                "selection_category": selection["selection_category"],
                "selection_reason": selection["selection_reason"],
                "selected_strategy_id": selection["strategy_id"],
                "original_baseline_success": parse_bool(
                    selection["baseline_success"]
                ),
                "original_selected_success": parse_bool(selection["success"]),
                "case_stratum": selection["case_stratum"],
                "case_id": episode.case_id,
                "suite": episode.suite,
                "task_id": int(episode.task_id),
                "init_state_id": int(episode.init_state_id),
                "rollout_seed": int(episode.rollout_seed),
                "strategy_id": episode.strategy_id,
                "success": bool(episode.success),
                "final_t": int(episode.final_t),
                "num_queries": int(episode.num_queries_observed),
                "filename": filename,
                "bytes": destination.stat().st_size,
            }
        )
    for key in sorted(selections):
        selected = [
            row
            for row in rows
            if (str(row["case_id"]), int(row["rollout_seed"])) == key
        ]
        actual = {str(row["strategy_id"]): bool(row["success"]) for row in selected}
        original = selected[0]
        reproduced = (
            actual.get("max_value") == bool(original["original_baseline_success"])
            and actual.get(str(original["selected_strategy_id"]))
            == bool(original["original_selected_success"])
        )
        for row in selected:
            row["selected_pair_reproduced"] = reproduced
    columns = list(rows[0])
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write_readme(rows, output_dir)
    print(f"Copied {len(rows)} videos to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
