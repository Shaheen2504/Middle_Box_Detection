"""
Analyze sent/recv logs to compute per-trial lA, lB, delta_l, and detection decision.
"""
import argparse
import csv
import json
import os
import statistics
import sys

THRESHOLD = 0.20
SUMMARY_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'results', 'summary', 'all_results.csv'
)
SUMMARY_HEADER = [
    'expname', 'mode',
    'lA_t0', 'lB_t0', 'Dl_t0',
    'lA_t1', 'lB_t1', 'Dl_t1',
    'lA_t2', 'lB_t2', 'Dl_t2',
    'lA_t3', 'lB_t3', 'Dl_t3',
    'lA_t4', 'lB_t4', 'Dl_t4',
    'median_Dl', 'threshold', 'detected',
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sent',    required=True)
    ap.add_argument('--recv',    required=True)
    ap.add_argument('--mode',    required=True)
    ap.add_argument('--expname', required=True)
    ap.add_argument('--outdir',  required=True)
    args = ap.parse_args()

    with open(args.sent) as f:
        sent = json.load(f)
    with open(args.recv) as f:
        recv = json.load(f)

    trials = sorted({p['trial'] for p in sent if p.get('is_probe_of_interest')})

    per_trial = []
    for t in trials:
        sent_A = {p['seq'] for p in sent
                  if p['trial'] == t and p['entropy_flag'] == 1
                  and p.get('is_probe_of_interest')}
        recv_A = {p['seq'] for p in recv
                  if p['trial'] == t and p['entropy_flag'] == 1}

        sent_B = {p['seq'] for p in sent
                  if p['trial'] == t and p['entropy_flag'] == 0
                  and p.get('is_probe_of_interest')}
        recv_B = {p['seq'] for p in recv
                  if p['trial'] == t and p['entropy_flag'] == 0}

        lA = 1 - len(recv_A & sent_A) / len(sent_A) if sent_A else 0.0
        lB = 1 - len(recv_B & sent_B) / len(sent_B) if sent_B else 0.0
        dl = lA - lB
        per_trial.append({'trial': t, 'lA': lA, 'lB': lB, 'delta_l': dl})

    delta_vals  = [r['delta_l'] for r in per_trial]
    median_dl   = statistics.median(delta_vals) if delta_vals else 0.0
    detected    = median_dl > THRESHOLD

    result = {
        'expname':    args.expname,
        'mode':       args.mode,
        'per_trial':  per_trial,
        'median_Dl':  median_dl,
        'threshold':  THRESHOLD,
        'detected':   detected,
    }

    # Print summary
    print(f'=== {args.expname} ({args.mode}) ===')
    for r in per_trial:
        sign = '+' if r['delta_l'] >= 0 else ''
        print(f"Trial {r['trial']}: lA={r['lA']*100:.1f}%  "
              f"lB={r['lB']*100:.1f}%  Dl={sign}{r['delta_l']*100:.1f}%")
    decision = 'MIDDLEBOX DETECTED' if detected else 'NO MIDDLEBOX'
    print(f'Median Dl: {median_dl*100:.1f}%  Threshold: {THRESHOLD*100:.1f}%  Decision: {decision}')

    # Save JSON
    os.makedirs(args.outdir, exist_ok=True)
    json_path = os.path.join(args.outdir, 'analysis_result.json')
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)

    # Save per-experiment CSV
    csv_path = os.path.join(args.outdir, 'analysis_result.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(SUMMARY_HEADER)
        writer.writerow(_make_row(result))

    # Append to summary CSV
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    write_header = not os.path.exists(SUMMARY_CSV)
    with open(SUMMARY_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(SUMMARY_HEADER)
        writer.writerow(_make_row(result))

    print(f'Saved: {json_path}')
    print(f'Saved: {csv_path}')
    print(f'Appended: {SUMMARY_CSV}')


def _make_row(result):
    row = [result['expname'], result['mode']]
    for t in range(5):
        if t < len(result['per_trial']):
            r = result['per_trial'][t]
            row += [f"{r['lA']:.4f}", f"{r['lB']:.4f}", f"{r['delta_l']:.4f}"]
        else:
            row += ['', '', '']
    row += [f"{result['median_Dl']:.4f}",
            f"{result['threshold']:.2f}",
            str(result['detected'])]
    return row


if __name__ == '__main__':
    main()
