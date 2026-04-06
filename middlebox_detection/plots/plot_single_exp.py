"""
Generates per-trial bar chart for one experiment and cumulative single-MB summary.
"""
import argparse
import csv
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

THRESHOLD  = 0.20
SINGLE_EXPS = ['exp0_baseline', 'exp1_shaper', 'exp2_compressor', 'exp3_spq']
SUMMARY_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'results', 'summary', 'all_results.csv'
)


def plot_per_trial(result, outdir):
    expname   = result['expname']
    per_trial = result['per_trial']
    trials    = [r['trial'] for r in per_trial]
    dls       = [r['delta_l'] * 100 for r in per_trial]
    median_dl = result['median_Dl'] * 100
    detected  = result['detected']

    fig, ax = plt.subplots(figsize=(8, 5))
    color = '#2ecc71' if detected else '#e74c3c'
    bars  = ax.bar(trials, dls, color=color, alpha=0.8, edgecolor='black')
    ax.axhline(THRESHOLD * 100, color='red', linestyle='--', linewidth=1.5,
               label=f'τ = {THRESHOLD*100:.0f}%')
    ax.axhline(median_dl, color='navy', linestyle='-', linewidth=1.5,
               label=f'Median Δl = {median_dl:.1f}%')

    ax.set_xlabel('Trial', fontsize=12)
    ax.set_ylabel('Δl (loss difference %)', fontsize=12)
    decision = 'MIDDLEBOX DETECTED' if detected else 'NO MIDDLEBOX'
    ax.set_title(f'{expname} — {decision}', fontsize=13)
    ax.set_xticks(trials)
    ax.legend(fontsize=10)
    ax.set_ylim(bottom=min(0, min(dls) - 5), top=max(100, max(dls) + 10))
    ax.grid(axis='y', alpha=0.3)

    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f'{expname}_per_trial.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {path}')


def plot_single_mb_summary(outdir):
    if not os.path.exists(SUMMARY_CSV):
        return

    rows = {}
    with open(SUMMARY_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            exp = row['expname']
            if exp in SINGLE_EXPS:
                rows[exp] = float(row['median_Dl']) * 100

    if not rows:
        return

    labels  = [e for e in SINGLE_EXPS if e in rows]
    values  = [rows[e] for e in labels]
    short   = [e.replace('exp', 'EXP ').replace('_', '\n') for e in labels]
    colors  = ['#2ecc71' if v > THRESHOLD * 100 else '#e74c3c' for v in values]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(range(len(labels)), values, color=colors, alpha=0.85, edgecolor='black')
    ax.axhline(THRESHOLD * 100, color='red', linestyle='--', linewidth=1.5,
               label=f'τ = {THRESHOLD*100:.0f}%')
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(short, fontsize=10)
    ax.set_ylabel('Median Δl (%)', fontsize=12)
    ax.set_title('Single-MB Experiments — Summary', fontsize=13)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 110)
    ax.grid(axis='y', alpha=0.3)

    path = os.path.join(outdir, 'single_mb_summary.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--result', required=True)
    ap.add_argument('--outdir', required=True)
    args = ap.parse_args()

    with open(args.result) as f:
        result = json.load(f)

    plot_per_trial(result, args.outdir)
    plot_single_mb_summary(args.outdir)


if __name__ == '__main__':
    main()
