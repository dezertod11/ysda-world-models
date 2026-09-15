"""Regenerate audited result assets and build both manuscript formats."""

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SOURCE = PROJECT / "experiments/campaigns/consensus_references_20260909_valid199/matched_analysis"
METHODS = {
    "first_k1": "K1",
    "max_value": "Max-value K4",
    "osc_medoid": "OSC-medoid K4",
    "raw_medoid": "Raw-medoid K4",
    "keystone": "KeyStone-style K4",
    "kdpe_endpoint": "KDPE endpoint K4",
}
FACTORS = {"Object": 50, "Environment": 50, "Position": 99}
CAMPAIGNS = PROJECT / "experiments/campaigns"
DECODER = CAMPAIGNS / "decoder_token_medoid_20260911"
OBSERVATION = CAMPAIGNS / "observation_contract_20260911"


def checked_factor_rows(scores, methods, sizes, expected):
    """Keep factor-macro and pooled episode rates separate in every table."""
    assert not scores.duplicated(["arm", "factor"]).any()
    assert set(scores.arm) == set(methods)
    records = []
    for arm, label in methods.items():
        group = scores[scores.arm == arm].set_index("factor").loc[list(sizes)]
        assert group.n.to_dict() == sizes
        counts = group.successes.to_numpy()
        assert list(counts) == expected[arm], f"Changed source counts: {arm}"
        assert (counts >= 0).all() and (counts <= group.n).all()
        rate = counts / group.n.to_numpy()
        assert ((group.micro_sr - rate).abs() < 1e-12).all()
        records.append({"arm": arm, "label": label, "counts": list(map(int, counts)),
                        "successes": int(counts.sum()), "n": int(group.n.sum()),
                        "macro_sr": float(rate.mean()), "micro_sr": float(counts.sum() / group.n.sum())})
    return records


def write_count_table(path, records):
    lines = [r"\begin{tabular}{lrrrrr}", r"\toprule",
             r"Controller & Obj. & Env. & Pos. & Total & Macro (\%) \\", r"\midrule"]
    for row in records:
        lines.append(" & ".join([row["label"], *map(str, row["counts"]),
                                  str(row["successes"]), f'{100 * row["macro_sr"]:.2f}']) + r" \\")
    path.write_text("\n".join([*lines, r"\bottomrule", r"\end{tabular}"]) + "\n")


def generate_recovery_assets(table_dir, figure_dir):
    confirmation = CAMPAIGNS / 'recovery_confirmation_20260913/analysis'
    grounding = CAMPAIGNS / 'recovery_grounding_diagnostic_20260913/analysis'
    score_path = confirmation / 'review/cohort_scores.csv'
    oracle_path = grounding / 'scores.csv'
    scores, oracle = pd.read_csv(score_path), pd.read_csv(oracle_path)
    methods = {'baseline_h16': 'Max-value H16', 'continue_h8': 'H8 after 72',
               'physical_regrasp': 'RGB recovery', 'refresh_preserve_only': 'Preserve-only'}
    expected = {'replication': [17, 16, 41, 41], 'transfer': [0, 0, 1, 1]}
    lines = [r'\begin{tabular}{lrr}', r'\toprule',
             r'Controller & Familiar (success / 64) & Transfer (success / 64) \\', r'\midrule']
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), layout='constrained')
    colors = ['#737373', '#287a83', '#348655', '#b74850']
    for ax, cohort in zip(axes[:2], expected):
        group = scores[scores.cohort.eq(cohort)].set_index('arm').loc[list(methods)]
        assert list(group.successes) == expected[cohort] and (group.n == 64).all()
        assert ((group.sr - group.successes / group.n).abs() < 1e-12).all()
        bars = ax.bar(range(4), group.sr * 100, color=colors)
        ax.bar_label(bars, labels=[f'{n}/64' for n in group.successes], padding=3)
        ax.set_xticks(range(4), list(methods.values()), rotation=25, ha='right')
        ax.set_title(('Familiar' if cohort == 'replication' else 'Transfer x0.3') + ': 64 paired cases')
    oracle_methods = ['rgb_replay', 'oracle_xy_fixed_gate', 'oracle_xyz_fixed_gate', 'oracle_xyz_physical_gate']
    group = oracle[oracle.cohort.eq('transfer')].set_index('arm').loc[oracle_methods]
    assert list(group.successes) == [0, 3, 2, 2] and (group.n == 16).all()
    bars = axes[2].bar(range(4), group.sr * 100, color=['#737373'] * 4)
    axes[2].bar_label(bars, labels=[f'{n}/16' for n in group.successes], padding=3)
    axes[2].set_xticks(range(4), ['RGB', 'GT XY', 'GT XYZ', 'GT + physical gate'], rotation=25, ha='right')
    axes[2].set_title('Privileged diagnostic: 16 transfer cases')
    for ax in axes:
        ax.set_ylim(0, 100)
        ax.set_ylabel('Terminal success (%)')
        ax.spines[['top', 'right']].set_visible(False)
    for suffix in ('pdf', 'png'):
        fig.savefig(figure_dir / f'recovery_confirmation_final.{suffix}', dpi=180)
    plt.close(fig)
    for i, label in enumerate(methods.values()):
        lines.append(f'{label} & {expected["replication"][i]} & {expected["transfer"][i]}' + r' \\')
    (table_dir / 'recovery_confirmation.tex').write_text('\n'.join(lines + [r'\bottomrule', r'\end{tabular}']) + '\n')
    return [score_path, oracle_path, confirmation / 'main/paired_effects.csv',
            confirmation / 'timing/aggregate_scores.csv', confirmation / 'review/summary.json',
            grounding / 'geometry.csv']


def generate_latest_assets(table_dir, figure_dir):
    h16_path = DECODER / "night_analysis/seed_controls__rates.csv"
    h8_path = DECODER / "night_analysis/horizon8__rates.csv"
    observation_path = OBSERVATION / "analysis/screen/aggregate_scores.csv"
    bias_path = DECODER / "review_20260912/decoder_seed_group_bias.csv"
    motion_path = OBSERVATION / "review_20260912/probe_motion.csv"
    h16 = pd.read_csv(h16_path)
    h8 = pd.read_csv(h8_path)
    methods16 = {"first": "First / K1", "max_value": "Max-value",
                 "action_medoid": "Action medoid", "decoder_medoid": "Decoder medoid",
                 "fixed_candidate_1": "Fixed index 1", "fixed_candidate_2": "Fixed index 2"}
    expected16 = {"first": [56, 24, 25], "max_value": [57, 24, 31],
                  "action_medoid": [57, 24, 29], "decoder_medoid": [57, 26, 29],
                  "fixed_candidate_1": [57, 25, 28], "fixed_candidate_2": [56, 24, 29]}
    rows16 = checked_factor_rows(h16, methods16, dict.fromkeys(FACTORS, 60), expected16)
    methods8 = {"max_value": "Max-value H16", "decoder_medoid": "Decoder H16",
                "max_value_h8": "Max-value H8", "decoder_full_h8": "Full decoder H8",
                "decoder_prefix_h8": "Prefix decoder H8"}
    expected8 = {"max_value": [28, 15, 31], "decoder_medoid": [30, 15, 29],
                 "max_value_h8": [28, 13, 25], "decoder_full_h8": [27, 12, 26],
                 "decoder_prefix_h8": [27, 12, 29]}
    rows8 = checked_factor_rows(h8, methods8, {"Object": 30, "Environment": 30, "Position": 60}, expected8)
    write_count_table(table_dir / "decoder_h16.tex", rows16)
    write_count_table(table_dir / "decoder_h8.tex", rows8)
    observation = pd.read_csv(observation_path).set_index("arm")
    obs_labels = {"continue_h8": "Continue H8", "physical_regrasp": "Physical regrasp",
                  "refresh_open_only": "Open refresh only", "refresh_preserve_only": "Preserve refresh only",
                  "refresh_open_regrasp": "Open refresh + regrasp",
                  "refresh_preserve_regrasp": "Preserve refresh + regrasp",
                  "oracle_calibrated": "Oracle: calibrated", "oracle_physical": "Oracle: physical"}
    observation = observation.loc[list(obs_labels)]
    assert list(observation.successes) == [128, 151, 154, 161, 138, 145, 156, 167]
    assert list(observation.drop_proxy) == [5, 7, 7, 7, 23, 23, 1, 6]
    assert (observation.n == 192).all()
    assert ((observation.sr - observation.successes / observation.n).abs() < 1e-12).all()
    lines = [r"\begin{tabular}{lrrrr}", r"\toprule",
             r"Controller & Success / 192 & SR (\%) & Drops & Regrasps \\", r"\midrule"]
    for arm, row in observation.iterrows():
        lines.append(f'{obs_labels[arm]} & {int(row.successes)} & {100*row.sr:.2f}'
                     f' & {int(row.drop_proxy)} & {int(row.full)}' + r" \\")
    (table_dir / "observation_contract.tex").write_text(
        "\n".join([*lines, r"\bottomrule", r"\end{tabular}"]) + "\n")

    colors = ["#287a83", "#b74850", "#6767a5", "#b18220"]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), layout="constrained")
    for index, arm in enumerate(["first", "max_value", "action_medoid", "decoder_medoid"]):
        group = h16[h16.arm == arm].set_index("factor").loc[list(FACTORS)]
        positions = [value + (index - 1.5) * .19 for value in range(3)]
        axes[0].bar(positions, 100 * group.micro_sr, width=.18, label=methods16[arm], color=colors[index])
    axes[0].set_xticks(range(3), ["Object", "Environment", "Position"])
    axes[0].set_ylim(0, 105)
    axes[0].set_ylabel("Success rate (%)")
    axes[0].set_title("H16: 60 configurations per factor", fontsize=10)
    axes[0].legend(fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(.5, -.14))
    labels8 = ["Max H16", "Decoder H16", "Max H8", "Full H8", "Prefix H8"]
    bars = axes[1].barh(labels8, [100 * row["macro_sr"] for row in rows8],
                        color=[colors[0], colors[1], colors[0], colors[1], colors[2]])
    axes[1].bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    axes[1].set_xlim(0, 78)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Equal-factor macro success (%)")
    axes[1].set_title("H8 comparison: matched 120-case subset", fontsize=10)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    for suffix in ["pdf", "png"]:
        fig.savefig(figure_dir / f"decoder_comparison.{suffix}", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.7), sharey=True, layout="constrained")
    labels = list(obs_labels.values())
    bars = axes[0].barh(labels, observation.sr * 100,
                       color=[colors[0]] * 6 + ["#969696"] * 2)
    axes[0].bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    axes[0].set_xlim(0, 103)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Success rate (%); 192 branches per arm")
    bars = axes[1].barh(labels, observation.drop_proxy, color=colors[1])
    axes[1].bar_label(bars, fmt="%.0f", padding=3, fontsize=8)
    axes[1].set_xlim(0, 28)
    axes[1].set_xlabel("Drop-proxy count (not official Safety)")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    for suffix in ["pdf", "png"]:
        fig.savefig(figure_dir / f"observation_contract.{suffix}", dpi=180)
    plt.close(fig)

    bias = pd.read_csv(bias_path)
    assert bias.queries.sum() == 2341
    motion = pd.read_csv(motion_path)
    harms = motion[motion.extra_regrasp_harms]
    assert len(harms) == 16 and (harms.contact_steps == 3).all()
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.3), layout="constrained")
    for index in range(3):
        part = bias[bias["index"] == index].set_index("seed_group").loc[range(3)]
        bottom = bias[bias["index"] < index].groupby("seed_group").fraction.sum().reindex(range(3), fill_value=0)
        axes[0].bar(range(3), 100 * part.fraction, bottom=100 * bottom,
                    color=colors[index], label=f"Candidate index {index}")
    axes[0].set_xticks(range(3), ["Group 0", "Group 1", "Group 2"])
    axes[0].set_ylabel("Fraction of decoder queries (%)")
    axes[0].legend(fontsize=7, loc="lower left")
    axes[0].set_title("Seed affinity (2341 H16 queries)", fontsize=10)
    other = motion[~motion.extra_regrasp_harms]
    axes[1].scatter(other.eef_displacement_mm, other.target_displacement_mm,
                    color="#929292", s=16, alpha=.6, label="Other probes")
    axes[1].scatter(harms.eef_displacement_mm, harms.target_displacement_mm,
                    color=colors[1], marker="x", s=40, label="16 extra-regrasp harms")
    axes[1].plot([0, 45], [0, 45], "--", color="#555555", linewidth=.8)
    axes[1].set_xlim(0, 45)
    axes[1].set_xlabel("EEF displacement during common probe (mm)")
    axes[1].set_ylabel("Target displacement (mm)")
    axes[1].legend(fontsize=7)
    axes[1].set_title("Pre-intervention motion: offline GT diagnostic", fontsize=10)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    for suffix in ["pdf", "png"]:
        fig.savefig(figure_dir / f"mechanism_audit.{suffix}", dpi=180)
    plt.close(fig)
    return [h16_path, h8_path, observation_path, bias_path, motion_path]


def generate_assets():
    scores = pd.read_csv(SOURCE / "factor_scores.csv")
    effects = pd.read_csv(SOURCE / "paired_effects.csv")
    assert set(scores.method) == set(METHODS), "Unexpected methods: audit before updating the draft"
    assert set(scores.factor) == set(FACTORS)
    assert not scores.duplicated(["method", "factor"]).any()
    expected_successes = {"first_k1": 94, "max_value": 97, "osc_medoid": 94,
                          "raw_medoid": 96, "keystone": 98, "kdpe_endpoint": 92}
    rows = []
    for method, label in METHODS.items():
        group = scores[scores.method == method].set_index("factor").loc[list(FACTORS)]
        assert group.episodes.to_dict() == FACTORS
        assert int(group.successes.sum()) == expected_successes[method], "Source changed; re-audit manuscript claims"
        assert ((group.sr - group.successes / group.episodes).abs() < 1e-12).all()
        values = [100 * value for value in group.sr]
        rows.append(" & ".join([label, *(f"{value:.2f}" for value in values),
                                f"{sum(values) / 3:.2f}", str(int(group.successes.sum()))]) + r" \\")
    table_dir = ROOT / "manuscript/tables"
    figure_dir = ROOT / "manuscript/figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    table = [r"\begin{tabular}{lrrrrr}", r"\toprule",
             r"Method & Object & Env. & Position & Macro & Success \\", r"\midrule",
             *rows, r"\bottomrule", r"\end{tabular}"]
    (table_dir / "consensus_scores.tex").write_text("\n".join(table) + "\n")
    selected = [name for name in METHODS if name != "max_value"]
    paired = effects[effects.scope == "All"].set_index("method").loc[selected]
    assert (paired.reference == "max_value").all() and (paired.pairs == 199).all()
    macro = scores.groupby("method").sr.mean()
    for method in selected:
        assert abs(paired.loc[method, "macro_delta"] - (macro[method] - macro.max_value)) < 1e-12
    delta = 100 * paired.macro_delta.to_numpy()
    low, high = 100 * paired.ci95_low.to_numpy(), 100 * paired.ci95_high.to_numpy()
    fig, ax = plt.subplots(figsize=(7.3, 2.7), layout="constrained")
    ax.errorbar(delta, range(len(selected)), xerr=[delta - low, high - delta],
                fmt="o", color="#246a73", ecolor="#656565", capsize=4, markersize=5)
    ax.axvline(0, color="#b13f48", linewidth=1, linestyle="--")
    ax.set_yticks(range(len(selected)), [METHODS[name] for name in selected])
    ax.invert_yaxis()
    ax.set_xlabel("Macro success-rate difference vs. max-value (percentage points)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.18)
    fig.savefig(figure_dir / "consensus_effects.pdf")
    fig.savefig(figure_dir / "consensus_effects.png", dpi=180)
    plt.close(fig)
    inputs = [SOURCE / "factor_scores.csv", SOURCE / "paired_effects.csv"]
    inputs.extend(generate_latest_assets(table_dir, figure_dir))
    inputs.extend(generate_recovery_assets(table_dir, figure_dir))
    provenance = {"evidence_snapshot": "2026-09-14", "valid199_cases": 199, "valid199_methods": 6,
                  "generated_by": "publication/iclr2027/tools/build.py",
                  "inputs": [{"path": str(path.relative_to(PROJECT)),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                             for path in inputs]}
    (table_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


def package_sources(stage, output):
    """Export only manuscript dependencies, never caches or experimental data."""
    archive = output / "iclr2027_sources.zip"
    allowed = {".tex", ".bib", ".sty", ".bst", ".pdf", ".png", ".json"}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(stage.rglob("*")):
            if path.is_file() and path.suffix in allowed:
                bundle.write(path, path.relative_to(stage))
        bundle.writestr("README.txt", "ICLR 2027 manuscript, evidence snapshot 2026-09-14.\n"
                        "Main file: iclr2027.tex; edit main.tex.\n"
                        "Overleaf: upload this ZIP and select iclr2027.tex.\n"
                        "Local: latexmk -pdf iclr2027.tex, or tectonic iclr2027.tex.\n"
                        "Figures, tables, bibliography and official styles are included.\n"
                        "This is an anonymous working manuscript, not a submitted paper.\n"
                        "Human authors must review claims, references and AI-use disclosure before submission.\n")
    return archive


def main():
    generate_assets()
    engine = Path(os.environ.get("TECTONIC", str(ROOT / ".tools/tectonic")))
    if not engine.is_file():
        raise SystemExit("Tectonic missing. Install Tectonic or set TECTONIC to its executable; see README.md")
    styles = ROOT / "templates/iclr2027"
    if not (styles / "iclr2027_conference.sty").is_file():
        raise SystemExit("Download official ICLR 2027 styles into templates/iclr2027; see templates/toolchain_sources.json")
    output = ROOT / "build"
    stage = output / "source"
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "manuscript", stage, dirs_exist_ok=True, copy_function=shutil.copyfile)
    for path in styles.iterdir():
        if path.suffix in {".sty", ".bst"}:
            shutil.copyfile(path, stage / path.name)
    report = {"engine": str(engine), "documents": []}
    for name in ["main", "iclr2027"]:
        command = [str(engine), "--keep-logs", "--keep-intermediates", "--outdir", str(output), f"{name}.tex"]
        subprocess.run(command, cwd=stage, check=True)
        pdf = output / f"{name}.pdf"
        reader = PdfReader(pdf)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip() or "Consensus" not in text:
            raise RuntimeError(f"Unexpected or empty PDF: {pdf}")
        log = (output / f"{name}.log").read_text(errors="replace")
        warnings = [line for line in log.splitlines()
                    if "Overfull" in line or "Underfull" in line or "undefined" in line or "Warning:" in line]
        row = {"file": pdf.name, "pages": len(reader.pages), "bytes": pdf.stat().st_size,
               "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "warnings": warnings}
        report["documents"].append(row)
        print(json.dumps(row), flush=True)
    archive = package_sources(stage, output)
    report["source_archive"] = {"file": archive.name, "bytes": archive.stat().st_size,
                                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    (output / "build_report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
