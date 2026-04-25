#!/usr/bin/env bash
# Run every experiment in sequence, clearing Mininet state between runs.
# Usage: sudo ./run_exp_in_order.sh   (from middlebox_detection/)
set -u
cd "$(dirname "$0")"

for exp in exp0_baseline exp1_shaper exp2_compressor exp3_spq \
           exp4_shaper_comp exp5_shaper_spq exp6_comp_spq exp7_three_chain \
           exp_ttl_shaper exp_ttl_compressor; do
    mn -c >/dev/null 2>&1
    echo "=== $exp ==="
    python3 "experiments/$exp.py" || echo "!!! $exp failed"
done
mn -c >/dev/null 2>&1
