#!/usr/bin/env python3
"""Build the common article with separate ICRA and ICLR conference styles."""
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from markdown_it import MarkdownIt
import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
LEGACY = ROOT.parent / 'iclr2027'
REGISTRY = PROJECT / 'experiments/RESULTS2.md'
REGISTRY_SHA = '003932f4e55889895ac7bda1ac2b2de75984bc4e9884614314d6800334deae6d'
SCOPED = PROJECT / 'experiments/campaigns/recovery_scoped_runtime_v2_20260915'
SCOPED_SHA = '91c8a14d9c0bd1caf50b645f53f9caff49df1d3a4edecf4517b70142d30a9b32'
ABLATION = PROJECT / 'experiments/campaigns/recovery_retreat_runtime_v2_20260915'
plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_rows(text):
    tokens = MarkdownIt('commonmark').enable('table').parse(text)
    section = model = ''
    rows = []
    header = []
    current = None
    in_header = False
    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            if token.tag == 'h2':
                section, model = tokens[i + 1].content, ''
            elif token.tag == 'h3':
                model = tokens[i + 1].content
        elif token.type == 'thead_open':
            in_header = True
        elif token.type == 'thead_close':
            in_header = False
        elif token.type == 'tr_open':
            current = []
        elif token.type == 'inline' and current is not None:
            current.append(token.content.strip().replace('`', ''))
        elif token.type == 'tr_close':
            if in_header:
                header = current
            elif 'Success' in header:
                data = dict(zip(header, current))
                count = re.fullmatch(r'(\d+)/(\d+)', data['Success'])
                if not count:
                    raise ValueError('Invalid success count')
                success, n = map(int, count.groups())
                if not 0 <= success <= n or n <= 0:
                    raise ValueError('Impossible success count')
                rows.append(dict(section=section, model=data.get('Модель', model),
                    method=data['Метод'], sampling=next((v for k, v in data.items()
                        if 'Seed' in k or 'seeds' in k), ''), successes=success, n=n,
                    sr=success / n, reported_ci=next((v for k, v in data.items()
                        if k.startswith('SR')), '')))
            current = None
    return rows


def triple(rows, model, section, method):
    chosen = [r for r in rows if r['model'].startswith(model)
              and r['section'].startswith(section) and r['method'] == method]
    keys = ['1', '2', '3'] if method == 'Baseline' else ['[1,999,998]', '[2,997,996]', '[3,995,994]']
    found = {r['sampling']: r for r in chosen}
    if len(found) != len(chosen) or not all(key in found for key in keys):
        raise ValueError('Missing/duplicate seed-group result')
    result = [found[key] for key in keys]
    if len({r['n'] for r in result}) != 1:
        raise ValueError('Unequal seed support')
    return result


def table(path, columns, header, rows):
    body = [r'\begin{tabular}{' + columns + '}', r'\toprule', header + r' \\', r'\midrule']
    body.extend(' & '.join(map(str, row)) + r' \\' for row in rows)
    path.write_text('\n'.join([*body, r'\bottomrule', r'\end{tabular}']) + '\n')


def checked_counts(result, arms):
    rows = result['aggregate']
    expected = {(cohort, arm) for cohort in ('replication', 'transfer') for arm in arms}
    actual = [(r['cohort'], r['arm']) for r in rows]
    assert len(actual) == len(set(actual)) and set(actual) == expected, 'Incomplete/duplicate arms'
    for row in rows:
        assert row['n'] == 64 and row['boundary'] == 72, 'Wrong experimental support'
        assert isinstance(row['successes'], int) and 0 <= row['successes'] <= row['n']
    return {(r['cohort'], r['arm']): r['successes'] for r in rows}


def scoped_evidence(tables):
    path = SCOPED / 'analysis/main/summary.json'
    text = (r'\newcommand{\ScopedRuntimeStatus}{A new scoped snapshot-v2 replication is pending; '
            r'it is not counted as a completed result in this manuscript.}' '\n'
            r'\newcommand{\ScopedRuntimeResults}{}' '\n')
    complete = False
    if path.exists():
        result = json.loads(path.read_text())
        if result.get('complete'):
            assert result['runtime_snapshot_version'] == 2 and not result['technical_only']
            assert result['cases'] == 128 and result['branches'] == 512
            assert result['checked_v2_prefixes'] == 128
            assert result['config_sha256'] == SCOPED_SHA == sha(SCOPED / 'config.json')
            labels = {'baseline_h16': 'H16', 'continue_h8': 'H8',
                      'physical_regrasp': 'Recovery', 'refresh_preserve_only': 'Preserve'}
            counts = checked_counts(result, labels)
            table(tables / 'scoped_v2.tex', 'lrr', 'Arm & Familiar /64 & Transfer /64',
                  [[label, counts['replication', arm], counts['transfer', arm]] for arm, label in labels.items()])
            text = (r'\newcommand{\ScopedRuntimeStatus}{The corrected scoped main comparison has '
                    r'completed with 128 paired cases and 512 rollouts; its counts are reported separately '
                    r'from historical results.}' '\n'
                    r'\newcommand{\ScopedRuntimeResults}{\begin{table}[t]\centering\small'
                    r'\caption{New scoped snapshot-v2 replication. All historical cells and controls '
                    r'are retained; counts must not be pooled with the earlier runtime.}'
                    r'\input{tables/scoped_v2}\end{table}}' '\n')
            complete = True
    (tables / 'current_evidence.tex').write_text(text)
    ablation = ABLATION / 'analysis/main/summary.json'
    extra = r'\newcommand{\ScopedAblationResults}{}' + '\n'
    if ablation.exists():
        result = json.loads(ablation.read_text())
        if result.get('complete'):
            assert complete and ready_ablation(result), 'Invalid completed ablation or missing parent audit'
            config = json.loads((ABLATION / 'config.json').read_text())
            assert config['reused_config_sha256'] == SCOPED_SHA
            counts = checked_counts(result, ('baseline_h16', 'continue_h8',
                                            'physical_regrasp', 'retreat_requery'))
            labels = {'continue_h8':'H8','physical_regrasp':'Full recovery','retreat_requery':'Retreat + requery'}
            table(tables/'retreat_v2.tex','lrr','Arm & Familiar /64 & Transfer /64',
                [[label,counts['replication',arm],counts['transfer',arm]] for arm,label in labels.items()])
            extra=(r'\newcommand{\ScopedAblationResults}{\begin{table}[t]\centering\small'
                r'\caption{Matched snapshot-v2 ablation. Only the 128 retreat arms are newly executed; '
                r'baseline and full-recovery rows reuse the scoped comparison. Initial gating and '
                r'physical action budget are identical.}\input{tables/retreat_v2}\end{table}}' '\n')
    with (tables/'current_evidence.tex').open('a') as handle:
        handle.write(extra)
    return complete


def ready_ablation(result):
    return (result.get('complete') is True and result.get('runtime_snapshot_version')==2 and result.get('cases')==128
        and result.get('branches')==512 and result.get('parent_config_sha256')==SCOPED_SHA
        and result.get('new_arm')=='retreat_requery'
        and len(result.get('aggregate',[]))==8
        and all(r['n']==64 for r in result.get('aggregate',[])))


def assets():
    assert sha(REGISTRY) == REGISTRY_SHA, 'Changed collaborator evidence: review before rebuilding'
    tables = ROOT / 'manuscript/tables'
    figures = ROOT / 'manuscript/figures'
    tables.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    rows = registry_rows(REGISTRY.read_text())
    with (tables / 'collaborator_results.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    comparisons, means = [], []
    fig, ax = plt.subplots(figsize=(6.7, 3.9), layout='constrained')
    specs = [('GR00T', 'SIMPLER', 'GR00T / SIMPLER'), ('GR00T', 'INT-ACT', 'GR00T / INT-ACT'),
             ('Xiaomi', 'SIMPLER', 'Xiaomi / SIMPLER'), ('Xiaomi', 'INT-ACT', 'Xiaomi / INT-ACT')]
    for i, (model, suite, label) in enumerate(specs):
        groups = [triple(rows, model, suite, method)
                  for method in ('Baseline', 'Consensus medoid', 'Decoder action-token medoid')]
        n = groups[0][0]['n']
        counts = [[r['successes'] for r in group] for group in groups]
        avg = [100 * sum(c) / (3 * n) for c in counts]
        comparisons.append([model, suite, n, *['/'.join(map(str, c)) for c in counts],
                            f'{avg[0]:.2f}', f'{avg[2]:.2f}'])
        means.append(dict(model=model, suite=suite, baseline=avg[0], action=avg[1], decoder=avg[2]))
        delta = 100 * (np.array(counts[2]) - counts[0]) / n
        for seed, (offset, color) in enumerate(zip([-.16, 0, .16], ['#287a83', '#b74850', '#817333'])):
            ax.scatter(delta[seed], i + offset, color=color, s=36,
                       label=f'Seed {seed+1}' if i == 0 else None)
        ax.plot([min(delta), max(delta)], [i, i], color='#aaaaaa', linewidth=1, zorder=0)
    table(tables / 'cross_seed.tex', 'llrrrrrr',
          r'Model & Suite & $n$ & K1 & Action & Decoder & K1 (\%) & Decoder (\%)', comparisons)
    pd.DataFrame(means).to_csv(tables / 'seed_means.csv', index=False)
    ax.axvline(0, color='#555555', linestyle='--', linewidth=.8)
    ax.set_yticks(range(4), [s[2] for s in specs]); ax.invert_yaxis()
    ax.set_xlabel('Decoder minus K1 success rate (percentage points)')
    ax.legend(loc='lower right', fontsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(figures / 'seed_effects.pdf'); fig.savefig(figures / 'seed_effects.png', dpi=170)
    plt.close(fig)
    table(tables / 'other_results.tex', 'llrrr', 'Model / slice & Sampling & K1 & Action & Decoder', [
        ['MIMIC / SIMPLER (96)', 'K1; action[0,1,2]; decoder[2,996,997]',45,52,42],
        ['MIMIC / INT-ACT (192)', 'primary0; candidates[0,1,2]',73,74,88],
        ['MIMIC / INT-ACT (192)', 'primary1 / primary2','33 / 9','--','--'],
        ['MIMIC / INT-ACT (192)', 'action[2,996,997] / [3,998,999]','--','50 / 39','--'],
        ['MIMIC / LIBERO Spatial (100)', 'reported default',69,75,64],
        ['GR00T / PRO Spatial (400)', 'primary1 / primary2 / primary3','246 / 244 / 246','248 / -- / --','253 / 241 / --'],
        ['GR00T / LIBERO Spatial (100)', 'decoder[2,997,996]','--','--',100],
        ['GR00T / Plus texture slice (100)', 'primary1; candidates[1,999,998]',100,100,100]])
    sys.path.insert(0, str(LEGACY / 'tools'))
    from recovery_assets import INPUTS, checked_broad
    broad = checked_broad(pd.read_csv(INPUTS['broad_scores']), json.loads(INPUTS['broad_summary'].read_text()))
    labels = ['K1', 'Value H16', 'H8 at72', 'Recovery at72', 'Event']
    table(tables / 'broad.tex', 'lrrrrr', r'Arm & Obj. & Env. & Pos. & Macro & /199',
          [[label, *row[1:]] for label, row in zip(labels, broad)])
    ready = scoped_evidence(tables)
    inputs = [REGISTRY, *INPUTS.values(),
              PROJECT / 'experiments/campaigns/decoder_token_medoid_20260911/night_analysis/seed_controls__rates.csv',
              PROJECT / 'experiments/campaigns/decoder_token_medoid_20260911/review_20260912/decoder_seed_group_bias.csv',
              PROJECT / 'experiments/campaigns/decoder_token_medoid_20260911/night_analysis/horizon8__rates.csv']
    inputs = list(dict.fromkeys(inputs))
    if ready:
        inputs += [SCOPED / 'config.json', SCOPED / 'analysis/main/summary.json']
    ablation_summary = ABLATION / 'analysis/main/summary.json'
    ablation_ready = ablation_summary.exists() and ready_ablation(json.loads(ablation_summary.read_text()))
    if ablation_ready:
        inputs += [ABLATION / 'config.json', ablation_summary]
    provenance = dict(snapshot='2026-09-15', contributed_rows=len(rows), scoped_v2_complete=ready,
        retreat_v2_complete=ablation_ready,
        scientifically_reviewed=False, submitted=False,
        inputs=[dict(path=str(p.relative_to(PROJECT)), sha256=sha(p)) for p in inputs],
        source_quality='Collaborator rows transcribed from supplied aggregate registry; raw audit pending')
    (tables / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return provenance


def resource_fonts(resources, seen=None):
    seen = set() if seen is None else seen
    resources = resources.get_object()
    if id(resources) in seen:
        return
    seen.add(id(resources))
    fonts = resources.get('/Font')
    if fonts:
        yield from (value.get_object() for value in fonts.get_object().values())
    objects = resources.get('/XObject')
    if objects:
        for value in objects.get_object().values():
            nested = value.get_object().get('/Resources')
            if nested:
                yield from resource_fonts(nested, seen)


def validate_pdf(pdf, log, limit):
    reader = PdfReader(pdf)
    text = '\n'.join(p.extract_text() or '' for p in reader.pages)
    assert len(reader.pages) <= limit, (pdf, len(reader.pages), limit)
    assert 'DISENTANGLING' in text.upper(), 'Wrong PDF'
    assert 'undefined' not in log.lower(), 'Undefined citations/references'
    assert 'Overfull' not in log, 'Overflow in compiled PDF'
    fonts = []
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 612) < 1
        assert abs(float(page.mediabox.height) - 792) < 1
        for font in resource_fonts(page['/Resources']):
            assert font.get('/Subtype') != '/Type3', 'Type3 font'
            descriptor = font.get('/FontDescriptor')
            children = font.get('/DescendantFonts', [])
            if children:
                descriptor = children[0].get_object().get('/FontDescriptor')
            assert descriptor, 'Font descriptor missing: ' + str(font.get('/BaseFont'))
            descriptor = descriptor.get_object()
            assert any(k in descriptor for k in ('/FontFile','/FontFile2','/FontFile3')), 'Unembedded font'
            fonts.append(str(font.get('/BaseFont')))
    return dict(file=pdf.name, pages=len(reader.pages), sha256=sha(pdf), fonts=sorted(set(fonts)))


def main():
    evidence = assets()
    output = ROOT / 'build'; output.mkdir(exist_ok=True)
    stage = output / 'source'
    shutil.copytree(ROOT / 'manuscript', stage, dirs_exist_ok=True)
    for path in (ROOT / 'templates/papercept').iterdir():
        if path.suffix in ('.cls','.bst'):
            shutil.copyfile(path, stage / path.name)
    for path in (LEGACY / 'templates/iclr2027').iterdir():
        if path.suffix in ('.sty','.bst'):
            shutil.copyfile(path, stage / path.name)
    report = dict(evidence=evidence, documents=[])
    for name, limit in [('icra2027',8), ('iclr2027',14)]:
        subprocess.run([str(LEGACY / '.tools/tectonic'), '--keep-logs', '--keep-intermediates',
                        '--outdir', str(output), name + '.tex'], cwd=stage, check=True)
        record = validate_pdf(output / (name+'.pdf'), (output / (name+'.log')).read_text(), limit)
        if name == 'iclr2027':
            aux=(output / (name+'.aux')).read_text()
            match=re.search(r'\\newlabel\{sec:main_end\}\{\{[^}]*\}\{(\d+)\}',aux)
            assert match and int(match.group(1)) <= 9, 'ICLR main text exceeds 9 pages'
            record['main_end_page']=int(match.group(1))
        report['documents'].append(record)
    with zipfile.ZipFile(output / 'joint_paper_sources.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file() and path.suffix in ('.tex','.bib','.bst','.sty','.cls','.pdf','.png','.csv','.json'):
                archive.write(path, path.relative_to(stage))
        archive.writestr('README.txt','Primary: icra2027.tex (PaperCept IEEE ICRA, numeric citations).\n'
            'Alternative: iclr2027.tex (ICLR 2027, author-year citations).\n'
            'Edit paper.tex. Do not submit both simultaneously. Human author approval required.\n'
            'Local: tectonic icra2027.tex or latexmk -pdf icra2027.tex.\n'
            'Scientific validation and contributor raw-data audit are tracked outside this typesetting package.\n')
    (output / 'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
