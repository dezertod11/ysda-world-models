"""Audited publication assets for the scoped RGB recovery paper."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
CAMPAIGNS = PROJECT / "experiments/campaigns"
FROZEN = PROJECT / "experiments/frozen_models/perception_regrasp_20260904"
CELLS = ("x0.2_t5", "x0.2_t6", "x0.2_t9", "y0.2_t4",
         "y0.2_t6", "y0.2_t9", "y0.3_t1", "y0.3_t5")
TABLES = ("recovery_primary.tex", "recovery_cells.tex", "recovery_ablation.tex",
          "recovery_confirmation.tex", "recovery_oracle.tex", "recovery_gate.tex",
          "provenance.json", "recovery_evidence.json", "recovery_broad.tex")
FIGURES = ("recovery_evidence.pdf", "recovery_evidence.png",
           "recovery_timing.pdf", "recovery_timing.png",
           "recovery_cell_effects.pdf", "recovery_cell_effects.png")
INPUTS = {
    "historical_audit": CAMPAIGNS / "p3c_audit_20260910/comparisons.csv",
    "ablation": CAMPAIGNS / "perception_regrasp_transfer_ablation_20260905/analysis/development/cohort_method_summary.csv",
    "ablation_pairs": CAMPAIGNS / "perception_regrasp_transfer_ablation_20260905/analysis/development/paired_cases.csv",
    "confirmation": CAMPAIGNS / "recovery_confirmation_20260913/analysis/review/cohort_scores.csv",
    "confirmation_pairs": CAMPAIGNS / "recovery_confirmation_20260913/analysis/main/paired_effects.csv",
    "cells": CAMPAIGNS / "recovery_confirmation_20260913/analysis/review/cell_scores.csv",
    "timing": CAMPAIGNS / "recovery_confirmation_20260913/analysis/timing/aggregate_scores.csv",
    "oracle": CAMPAIGNS / "recovery_grounding_diagnostic_20260913/analysis/scores.csv",
    "localization": CAMPAIGNS / "recovery_confirmation_20260913/analysis/review/summary.json",
    "geometry": CAMPAIGNS / "recovery_grounding_diagnostic_20260913/analysis/geometry.csv",
    "calibration": FROZEN / "calibration_manifest.csv",
    "localizer": FROZEN / "perception_regrasp_localizer.npz",
    "trigger": FROZEN / "perception_regrasp_trigger_v1.json",
    "configuration": CAMPAIGNS / "recovery_confirmation_20260913/config.json",
    "implementation_audit": PROJECT / "experiments/P3C_IMPLEMENTATION_AUDIT_20260910.md",
    "broad_scores": CAMPAIGNS / "p3_benchmark_closure_20260914_v3/analysis/factor_scores.csv",
    "broad_summary": CAMPAIGNS / "p3_benchmark_closure_20260914_v3/analysis/summary.json",
    "broad_effects": CAMPAIGNS / "p3_benchmark_closure_20260914_v3/analysis/paired_effects.csv",
}


def checked_broad(scores, summary):
    if not summary['complete'] or summary['matched_cases'] != 199:
        raise ValueError('Broad comparison is incomplete')
    expected = dict(first_k1=[48,20,29], max_value_h16=[47,20,26],
                    h8_at72=[47,21,26], p3_at72=[44,21,30], p3_event=[47,20,26])
    factors = ['Object','Environment','Position']
    if len(scores) != 15 or scores.duplicated(['arm','factor']).any() or set(scores.arm) != set(expected):
        raise ValueError('Broad support changed')
    rows = []
    labels = ['K1 / H16','Max-value / H16','H8 after 72','RGB recovery at 72','Event recovery']
    for (arm, counts), label in zip(expected.items(), labels):
        part = scores[scores.arm.eq(arm)].set_index('factor').loc[factors]
        if list(part.n) != [50,50,99] or list(part.successes) != counts:
            raise ValueError('Broad counts changed')
        rates = 100 * part.successes / part.n
        np.testing.assert_allclose(part.sr, rates/100, rtol=0, atol=1e-12)
        rows.append([label,*[f'{x:.2f}' for x in rates],f'{rates.mean():.2f}',f'{sum(counts)}/199'])
    return rows


def checked_pair(label, n, baseline, method, rescue, harm, low, high):
    if not (0 <= baseline <= n and 0 <= method <= n
            and 0 <= rescue <= n - baseline and 0 <= harm <= baseline):
        raise ValueError("Invalid paired counts")
    delta = 100 * (method - baseline) / n
    if rescue - harm != method - baseline or not low <= delta <= high:
        raise ValueError("Paired effect disagrees with recorded counts")
    return dict(label=label, n=n, baseline=baseline, method=method, rescue=rescue,
                harm=harm, delta_pp=delta, low_pp=low, high_pp=high)


def checked_cells(data):
    part = data[data.cohort.eq("replication")].copy()
    if set(part.cell) != set(CELLS):
        raise ValueError("Primary support changed; do not select only successful cells")
    arms = ["baseline_h16", "continue_h8", "physical_regrasp", "refresh_preserve_only"]
    if part.duplicated(["cell", "arm"]).any() or len(part) != 32 or not (part.n == 8).all():
        raise ValueError("Unbalanced primary cell support")
    if set(part.arm) != set(arms):
        raise ValueError("Incomplete control arms")
    wide = part.pivot(index="cell", columns="arm", values="successes").loc[list(CELLS), arms]
    assert wide.sum().to_dict() == dict(zip(arms, [17, 16, 41, 41]))
    return wide


def tex_table(path, columns, header, rows):
    text = [r"\begin{tabular}{" + columns + "}", r"\toprule",
            " & ".join(header) + r" \\", r"\midrule"]
    text += [" & ".join(map(str, row)) + r" \\" for row in rows]
    path.write_text("\n".join(text + [r"\bottomrule", r"\end{tabular}"]) + "\n")


def cell_contrasts(wide):
    """Descriptive effects keep both continuation controls and all fixed cells."""
    return [dict(cell=cell, n=8, h16=int(row.baseline_h16), h8=int(row.continue_h8),
                 recovery=int(row.physical_regrasp),
                 net_vs_h8=int(row.physical_regrasp - row.continue_h8),
                 net_vs_h16=int(row.physical_regrasp - row.baseline_h16))
            for cell, row in wide.iterrows()]


def save_figure(fig, folder, name):
    for ext in ("pdf", "png"):
        fig.savefig(folder / f"{name}.{ext}", dpi=180)
    plt.close(fig)


def generate():
    tables, figures = ROOT / "manuscript/tables", ROOT / "manuscript/figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    audit = pd.read_csv(INPUTS["historical_audit"])
    primary = []
    for label, cohort, expected in [
        ("New init (P3c)", "perception_regrasp_online_trigger_20260904/holdout", (40, 13, 24, 12, 1)),
        ("Replication (P3d)", "perception_regrasp_transfer_ablation_20260905/replication", (40, 6, 25, 20, 1)),
    ]:
        row = audit[audit.cohort.eq(cohort) & audit.method.eq("workspace_calibrated")]
        assert len(row) == 1
        row = row.iloc[0]
        counts = tuple(int(row[k]) for k in ("n", "baseline_successes", "method_successes", "rescues", "harms"))
        assert counts == expected
        primary.append(checked_pair(label, *counts, row.ci_low_pp, row.ci_high_pp))

    scores = pd.read_csv(INPUTS["confirmation"])
    expected = {"replication": [17, 16, 41, 41], "transfer": [0, 0, 1, 1]}
    arms = ["baseline_h16", "continue_h8", "physical_regrasp", "refresh_preserve_only"]
    for cohort, counts in expected.items():
        part = scores[scores.cohort.eq(cohort)].set_index("arm").loc[arms]
        assert len(part) == 4 and (part.n == 64).all() and list(part.successes) == counts
        assert ((part.sr - part.successes / part.n).abs() < 1e-12).all()
    contrasts = pd.read_csv(INPUTS["confirmation_pairs"])
    row = contrasts[contrasts.scope.eq("replication") & contrasts.left.eq("physical_regrasp")
                    & contrasts.right.eq("continue_h8")]
    assert len(row) == 1
    row = row.iloc[0]
    assert row.pairs == 64 and row.rescues == 27 and row.harms == 2
    primary.append(checked_pair("Confirmation", 64, 16, 41, 27, 2, 100 * row.ci_low, 100 * row.ci_high))
    tex_table(tables / "recovery_primary.tex", "lrrrrr",
              ["Evaluation", "H8", "Recovery", r"$\Delta$ pp", "95\\% CI", "R/H"],
              [[r["label"], f'{r["baseline"]}/{r["n"]}', f'{r["method"]}/{r["n"]}',
                f'{r["delta_pp"]:.2f}', f'[{r["low_pp"]:.2f}, {r["high_pp"]:.2f}]',
                f'{r["rescue"]}/{r["harm"]}'] for r in primary])
    wide = checked_cells(pd.read_csv(INPUTS["cells"]))
    cell_effects = cell_contrasts(wide)
    names = {1: "Cream cheese", 4: "Ketchup", 5: "Tomato sauce", 6: "Butter", 9: "Orange juice"}
    tex_table(tables / "recovery_cells.tex", "llrrrr",
              ["Cell", "Target", "H16", "H8", "Recovery", r"$\Delta$ pp"],
              [[cell.replace("_", r"\_"), names[int(cell.split("_t")[1])],
                f'{int(r.baseline_h16)}/8', f'{int(r.continue_h8)}/8',
                f'{int(r.physical_regrasp)}/8', f'{100*(r.physical_regrasp-r.continue_h8)/8:.1f}']
               for cell, r in wide.iterrows()])

    ablation = pd.read_csv(INPUTS["ablation"])
    ablation_rows = []
    for cohort, label, counts in [("replication", "Primary cells", (40, 6, 8, 25)),
                                  ("novel_cell", "Other calibrated cells", (35, 26, 28, 31)),
                                  ("all", "All P3d cells", (75, 32, 36, 56))]:
        part = ablation[ablation.cohort.eq(cohort)].set_index("method")
        n, baseline, retreat, full = counts
        assert (part.n_cases == n).all() and (part.baseline_successes == baseline).all()
        assert int(part.loc["workspace_calibrated", "method_successes"]) == full
        assert int(part.loc["workspace_retreat_only", "method_successes"]) == retreat
        ablation_rows.append([label, f"{baseline}/{n}", f"{retreat}/{n}", f"{full}/{n}",
                              f"{100*(full-retreat)/n:.2f}"])
    tex_table(tables / "recovery_ablation.tex", "lrrrr",
              ["Population", "H8", "Retreat", "Recovery", r"$\Delta_{\rm R-retreat}$ pp"], ablation_rows)
    pairs = pd.read_csv(INPUTS["ablation_pairs"])
    pair_counts = {}
    for cohort, count in [("replication", (17, 0)), ("all", (23, 3))]:
        part = pairs if cohort == "all" else pairs[pairs.evaluation_cohort.eq(cohort)]
        paired = part.pivot(index="case_id", columns="method", values="method_success")
        delta = paired.workspace_calibrated.astype(int) - paired.workspace_retreat_only.astype(int)
        observed = (int(delta.eq(1).sum()), int(delta.eq(-1).sum()))
        assert observed == count
        pair_counts[cohort] = dict(full_only=count[0], retreat_only=count[1])

    tex_table(tables / "recovery_confirmation.tex", "lrr",
              ["Controller", "Primary / 64", "x0.3 / 64"],
              [[label, expected["replication"][i], expected["transfer"][i]] for i, label in enumerate(
                  ["Max-value H16", "H8 after 72", "RGB recovery", "Preserve-only extension"])])
    oracle = pd.read_csv(INPUTS["oracle"])
    oracle_arms = ["rgb_replay", "oracle_xy_fixed_gate", "oracle_xyz_fixed_gate", "oracle_xyz_physical_gate"]
    values = {}
    for cohort, counts in [("replication", [10, 11, 10, 12]), ("transfer", [0, 3, 2, 2])]:
        part = oracle[oracle.cohort.eq(cohort)].set_index("arm").loc[oracle_arms]
        assert (part.n == 16).all() and list(part.successes) == counts
        values[cohort] = counts
    tex_table(tables / "recovery_oracle.tex", "lrr",
              ["Waypoint / eligibility", "Primary / 16", "Transfer / 16"],
              [[label, values["replication"][i], values["transfer"][i]] for i, label in enumerate(
                  ["RGB replay", "GT XY, fixed gate", "GT XYZ, fixed gate", "GT XYZ, physical gate"])])

    trigger = json.loads(INPUTS["trigger"].read_text())
    calibration = pd.read_csv(INPUTS["calibration"], usecols=["independent_group", "init_state_id"])
    assert len(calibration) == 388 and calibration.independent_group.nunique() == 194
    assert set(calibration.init_state_id) == set(range(5, 25))
    with np.load(INPUTS["localizer"], allow_pickle=False) as z:
        assert z["localizer_type"].item() == "deeplab_heatmap_v2"
    gate_rows = []
    for name, spec in trigger["objects"].items():
        box = lambda key: "(" + ", ".join(f"{x:.3f}" for x in spec[key]) + ")"
        gate_rows.append([name.title(), f'{spec["score_range_lower"]:.3f}',
                          box("workspace_lower_xyz"), box("workspace_upper_xyz")])
    tex_table(tables / "recovery_gate.tex", "lrrr",
              ["Object", r"$c_\ell$", "Lower XYZ", "Upper XYZ"], gate_rows)

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.8), layout="constrained")
    x = np.arange(3)
    for offset, key, color, label in [(-.18, "baseline", "#287a83", "H8 control"),
                                     (.18, "method", "#348655", "RGB recovery")]:
        rates = [100*r[key]/r["n"] for r in primary]
        bars = axes[0].bar(x + offset, rates, width=.34, color=color, label=label)
        axes[0].bar_label(bars, labels=[f'{r[key]}/{r["n"]}' for r in primary], padding=3, fontsize=9)
    axes[0].set_xticks(x, ["P3c\nnew init", "P3d\nreplication", "Latest\nconfirmation"])
    axes[0].set_title("Three evaluations on fixed primary cells", fontsize=11)
    axes[0].legend(fontsize=9)
    bars = axes[1].bar(range(3), [15, 20, 62.5], color=["#287a83", "#ad7924", "#348655"])
    axes[1].bar_label(bars, labels=["6/40", "8/40", "25/40"], padding=3, fontsize=9)
    axes[1].set_xticks(range(3), ["H8", "Retreat +\nrequery", "Full RGB\nrecovery"])
    axes[1].set_title("Matched mechanism ablation (P3d)", fontsize=11)
    for ax in axes:
        ax.set_ylim(0, 100)
        ax.set_ylabel("Terminal success (%)")
        ax.spines[["top", "right"]].set_visible(False)
    save_figure(fig, figures, "recovery_evidence")

    timing = pd.read_csv(INPUTS["timing"])
    times, control, method = [56, 72, 88], [16, 16, 18], [31, 41, 34]
    for t, b, m in zip(times, control, method):
        part = (scores[scores.cohort.eq("replication")] if t == 72 else
                timing[timing.boundary.eq(t) & timing.cohort.eq("replication")]).set_index("arm")
        assert int(part.loc["continue_h8", "successes"]) == b
        assert int(part.loc["physical_regrasp", "successes"]) == m
        assert (part.n == 64).all()
    fig, ax = plt.subplots(figsize=(7, 3.1), layout="constrained")
    for counts, color, label, offset in [(control, "#287a83", "H8 control", -8),
                                       (method, "#348655", "RGB recovery", 6)]:
        ax.scatter(times, 100*np.asarray(counts)/64, color=color, s=48, label=label)
        for t, n in zip(times, counts):
            ax.annotate(f"{n}/64", (t, 100*n/64), xytext=(0, offset),
                        textcoords="offset points", ha="center", va="bottom" if offset > 0 else "top")
    ax.set(xticks=times, xlabel="Scheduled assessment step", ylabel="Terminal success (%)",
           ylim=(0, 100), xlim=(50, 94), title="Same 64 primary cases; three sampled times")
    ax.legend(loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    save_figure(fig, figures, "recovery_timing")

    fig, ax = plt.subplots(figsize=(8.5, 4.5), layout="constrained")
    y = np.arange(len(cell_effects))
    for offset, key, color, label in [(-.18, "net_vs_h8", "#287a83", "Recovery - matched H8"),
                                     (.18, "net_vs_h16", "#348655", "Recovery - uninterrupted H16")]:
        values = [100 * row[key] / row["n"] for row in cell_effects]
        bars = ax.barh(y + offset, values, height=.34, color=color, label=label)
        ax.bar_label(bars, labels=[f'{row[key]:+d}/8' for row in cell_effects], padding=3, fontsize=9)
    ax.set(yticks=y, yticklabels=[row["cell"] for row in cell_effects],
           xlabel="Success-rate difference (percentage points)", xlim=(-25, 125),
           title="All eight primary cells: effect depends on the comparator")
    ax.invert_yaxis()
    ax.axvline(0, color="#555555", linewidth=.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", fontsize=9)
    save_figure(fig, figures, "recovery_cell_effects")

    broad_summary = json.loads(INPUTS['broad_summary'].read_text())
    broad = checked_broad(pd.read_csv(INPUTS['broad_scores']), broad_summary)
    tex_table(tables / 'recovery_broad.tex', 'lrrrrr',
              ['Controller',r'Obj. (\%)',r'Env. (\%)',r'Pos. (\%)',r'Macro (\%)','Success'], broad)
    evidence = dict(primary=primary, full_vs_retreat=pair_counts, cells=list(CELLS),
                    descriptive_cell_contrasts=cell_effects,
                    support_selected_on_evaluation_outcomes=False,
                    narrative_selected_after_broader_exploration=True,
                    uncalibrated_transfer=dict(n=64, control=0, recovery=1),
                    broader_p3_benchmark_included=True, broader_p3_cases=199,
                    broader_p3_seed_replication_complete=False)
    (tables / "recovery_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    provenance = dict(evidence_snapshot="2026-09-15", manuscript_focus="gated_rgb_recovery",
        inputs=[dict(role=role, path=str(path.relative_to(PROJECT)),
                     sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for role, path in INPUTS.items()])
    (tables / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
