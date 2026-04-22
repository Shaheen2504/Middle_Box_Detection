"""
Grouped bar chart: actual Dl vs expected Dl (sum of individual MBs).
Gap between bars = masking effect.
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

THRESHOLD = 0.20

# Expected Dl = sum of individual single-MB medians
# Single-MB source experiments
SINGLE_MAP = {
    'shaper':     'exp1_shaper',
    'compressor': 'exp2_compressor',
    'spq':        'exp3_spq',
}

CHAIN_EXPS = [
    ('exp4_shaper_comp',  ['exp1_shaper', 'exp2_compressor'], 'Shaper+Comp'),
    ('exp5_shaper_spq',   ['exp1_shaper', 'exp3_spq'],        'Shaper+SPQ'),
    ('exp6_comp_spq',     ['exp2_compressor', 'exp3_spq'],    'Comp+SPQ'),
    ('exp7_three_chain',  ['exp1_shaper', 'exp2_compressor', 'exp3_spq'], 'All 3'),
]


def load_medians(summary_csv):
    medians = {}
    if not os.path.exists(summary_csv):
        return medians
    with open(summary_csv, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            exp = row['expname']
            try:
                medians[exp] = float(row['median_Dl']) * 100
            except (KeyError, ValueError):
                pass
    return medians


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--summary', required=True)
    ap.add_argument('--outdir',  required=True)
    args = ap.parse_args()

    medians = load_medians(args.summary)

    labels, actual_vals, expected_vals = [], [], []
    for exp, sources, label in CHAIN_EXPS:
        if exp not in medians:
            continue
        expected = sum(medians.get(s, 0) for s in sources)
        labels.append(label)
        actual_vals.append(medians[exp])
        expected_vals.append(min(expected, 100))   # cap at 100%

    if not labels:
        print('[plot_chain_comparison] No chain results found yet.')
        return

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_actual   = ax.bar(x - width/2, actual_vals,   width, label='Actual Δl',   color='#3498db', alpha=0.85, edgecolor='black')
    bars_expected = ax.bar(x + width/2, expected_vals, width, label='Expected Δl', color='#e67e22', alpha=0.85, edgecolor='black')

    ax.axhline(THRESHOLD * 100, color='red', linestyle='--', linewidth=1.5,
               label=f'τ = {THRESHOLD*100:.0f}%')

    ax.set_xlabel('Experiment', fontsize=12)
    ax.set_ylabel('Median Δl (%)', fontsize=12)
    ax.set_title('Chained Middlebox Experiments — Actual vs Expected Δl', fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 120)
    ax.grid(axis='y', alpha=0.3)

    # Annotate masking gap
    for i, (act, exp_v) in enumerate(zip(actual_vals, expected_vals)):
        gap = exp_v - act
        if gap > 1:
            ax.annotate(f'mask={gap:.1f}%',
                        xy=(x[i], max(act, exp_v) + 3),
                        ha='center', fontsize=9, color='#7f8c8d')

    os.makedirs(args.outdir, exist_ok=True)
    path = os.path.join(args.outdir, 'chain_comparison.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {path}')


if __name__ == '__main__':
    main()
