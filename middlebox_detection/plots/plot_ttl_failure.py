"""
Generates three figures for the TTL failure demonstration:
  1. ttl_failure_shaper.png  — end-to-end Dl vs per-hop apparent Dl
  2. ttl_nat_control.png     — TTL=3 header comparison showing NAT modification
  3. results_summary_table.png — heatmap of all 11 experiments
"""
import argparse
import csv
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

THRESHOLD = 0.20
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY_CSV = os.path.join(ROOT, 'results', 'summary', 'all_results.csv')

ALL_EXPS = [
    'exp0_baseline', 'exp1_shaper', 'exp2_compressor', 'exp3_spq',
    'exp4_shaper_comp', 'exp5_shaper_spq', 'exp6_comp_spq', 'exp7_three_chain',
    'exp_ttl_shaper', 'exp_ttl_compressor', 'exp_ttl_nat',
]


def plot_ttl_failure(ttl_data, e2e_data, outdir, name='shaper'):
    hops     = ttl_data['hops']
    ttls     = [h['ttl'] for h in hops]
    apparent = [h['apparent_Dl'] * 100 for h in hops]
    e2e_dl   = e2e_data.get('median_Dl', 0) * 100

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left: per-hop apparent Dl
    ax = axes[0]
    ax.bar(ttls, apparent, color='#9b59b6', alpha=0.8, edgecolor='black')
    ax.axhline(THRESHOLD * 100, color='red', linestyle='--', linewidth=1.5,
               label=f'τ = {THRESHOLD*100:.0f}%')
    ax.set_xlabel('TTL (hop)', fontsize=12)
    ax.set_ylabel('Apparent Δl (%)', fontsize=12)
    ax.set_title('Per-Hop Apparent Δl (TTL probe)', fontsize=12)
    ax.set_xticks(ttls)
    ax.legend(fontsize=10)
    ax.set_ylim(0, max(25, max(apparent) + 5))
    ax.grid(axis='y', alpha=0.3)

    # Right: end-to-end Dl vs max per-hop
    ax2 = axes[1]
    max_apparent = max(apparent) if apparent else 0
    labels = ['End-to-End Δl', 'Max per-hop\napparent Δl']
    values = [e2e_dl, max_apparent]
    colors = ['#2ecc71' if v > THRESHOLD * 100 else '#e74c3c' for v in values]
    ax2.bar(labels, values, color=colors, alpha=0.85, edgecolor='black')
    ax2.axhline(THRESHOLD * 100, color='red', linestyle='--', linewidth=1.5,
                label=f'τ = {THRESHOLD*100:.0f}%')
    ax2.set_ylabel('Δl (%)', fontsize=12)
    ax2.set_title('E2E vs TTL-based Detection', fontsize=12)
    ax2.legend(fontsize=10)
    ax2.set_ylim(0, max(100, e2e_dl + 10))
    ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    path = os.path.join(outdir, f'ttl_failure_{name}.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {path}')


def plot_nat_control(nat_data, outdir):
    hops = nat_data.get('hops', [])
    # Find TTL=3 hop
    hop3 = next((h for h in hops if h['ttl'] == 3), None)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis('off')

    rows = [
        ['TTL', 'Hop IP', 'icmp_A', 'icmp_B', 'apparent Δl'],
    ]
    for h in hops:
        rows.append([
            str(h['ttl']),
            h.get('hop_ip', '*'),
            str(h.get('icmp_A', '')),
            str(h.get('icmp_B', '')),
            f"{h.get('apparent_Dl', 0)*100:.2f}%",
        ])

    table = ax.table(cellText=rows[1:], colLabels=rows[0],
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)

    # Highlight TTL=3 row (NAT hop) in yellow
    if hop3:
        idx = next((i for i, h in enumerate(hops) if h['ttl'] == 3), None)
        if idx is not None:
            for col in range(5):
                table[(idx + 1, col)].set_facecolor('#f9e79f')

    ax.set_title('NAT Control — TTL=3 Header Modification', fontsize=12, pad=20)

    path = os.path.join(outdir, 'ttl_nat_control.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {path}')


def plot_summary_table(outdir):
    if not os.path.exists(SUMMARY_CSV):
        print('[plot_ttl_failure] summary CSV not found, skipping table.')
        return

    medians = {}
    detected = {}
    with open(SUMMARY_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            exp = row['expname']
            try:
                medians[exp]  = float(row['median_Dl']) * 100
                detected[exp] = row['detected'].strip().lower() == 'true'
            except (KeyError, ValueError):
                pass

    labels  = ALL_EXPS
    present = [e for e in labels if e in medians]
    if not present:
        return

    values  = np.array([[medians[e] for e in present]])
    det_row = [detected[e] for e in present]

    fig, ax = plt.subplots(figsize=(max(10, len(present) * 1.2), 3))
    cmap = mcolors.LinearSegmentedColormap.from_list('rg', ['#e74c3c', '#f9e79f', '#2ecc71'])
    im = ax.imshow(values, aspect='auto', cmap=cmap, vmin=0, vmax=100)

    ax.set_xticks(range(len(present)))
    ax.set_xticklabels([e.replace('exp', 'EXP\n').replace('_', ' ') for e in present],
                       fontsize=9, rotation=30, ha='right')
    ax.set_yticks([0])
    ax.set_yticklabels(['Median Δl (%)'], fontsize=10)

    for i, exp in enumerate(present):
        v = medians[exp]
        d = det_row[i]
        label = f'{v:.1f}%\n{"DETECTED" if d else "NONE"}'
        ax.text(i, 0, label, ha='center', va='center', fontsize=8,
                color='black', fontweight='bold')

    plt.colorbar(im, ax=ax, orientation='vertical', label='Median Δl (%)')
    ax.set_title('All Experiments — Detection Summary Heatmap', fontsize=12)
    fig.tight_layout()

    path = os.path.join(outdir, 'results_summary_table.png')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ttl_result', required=True)
    ap.add_argument('--e2e_result', required=True)
    ap.add_argument('--nat_result', default=None)
    ap.add_argument('--outdir',     required=True)
    ap.add_argument('--name', default='shaper')

    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    with open(args.ttl_result) as f:
        ttl_data = json.load(f)
    with open(args.e2e_result) as f:
        e2e_data = json.load(f)

    plot_ttl_failure(ttl_data, e2e_data, args.outdir, args.name)

    if args.nat_result and os.path.exists(args.nat_result):
        with open(args.nat_result) as f:
            nat_data = json.load(f)
        plot_nat_control(nat_data, args.outdir)

    plot_summary_table(args.outdir)


if __name__ == '__main__':
    main()
