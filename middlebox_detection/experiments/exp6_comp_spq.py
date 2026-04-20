"""
EXP 6 — Compressor + SPQ (two-chain)
Purpose: Detect chained MB2+MB3
Expected: Median Dl complex, MIDDLEBOX DETECTED
Run: sudo python3 experiments/exp6_comp_spq.py
"""
import os, sys, time, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mininet.log import setLogLevel
from topology.two_chain_topo import create_two_chain_topo
from middleboxes.compressor import enable_compressor, disable_compressor
from middleboxes.spq import enable_spq, disable_spq

EXP_NAME = 'exp6_comp_spq'
MODE     = 'spq'
N_TRIALS = 5
DST_PORT = 5000
ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS  = os.path.join(ROOT, f'results/raw/{EXP_NAME}')
SENDER   = os.path.join(ROOT, 'probing/sender.py')
RECEIVER = os.path.join(ROOT, 'probing/receiver.py')
ANALYZE  = os.path.join(ROOT, 'analysis/analyze.py')
PLOT_CHAIN = os.path.join(ROOT, 'plots/plot_chain_comparison.py')


def run():
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'results/summary'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'plots/figures'), exist_ok=True)
    setLogLevel('warning')

    net, h1, h2, rn1, rn2, r_mb1, rn3, r_mb2, rn4 = create_two_chain_topo()
    iface1 = 'r_mb1-eth1'
    iface2 = 'r_mb2-eth1'
    daemon_proc = None

    try:
        with open(os.path.join(RESULTS, 'tc_config.txt'), 'w') as f:
            f.write('--- BEFORE ---\n')
            f.write(r_mb1.cmd(f'tc qdisc show dev {iface1}'))
            f.write(r_mb2.cmd(f'tc qdisc show dev {iface2}'))

        daemon_proc = enable_compressor(r_mb1, iface1, sigma_mbps=2,
                                         dst_port=DST_PORT, queue_num=1)
        enable_spq(r_mb2, iface2)

        with open(os.path.join(RESULTS, 'tc_config.txt'), 'a') as f:
            f.write('\n--- AFTER ENABLING MBs ---\n')
            f.write('r_mb1:\n')
            f.write(r_mb1.cmd(f'tc qdisc show dev {iface1}'))
            f.write(r_mb1.cmd(f'tc filter show dev {iface1}'))
            f.write('r_mb2:\n')
            f.write(r_mb2.cmd(f'tc qdisc show dev {iface2}'))
            f.write(r_mb2.cmd(f'tc filter show dev {iface2}'))

        with open(os.path.join(RESULTS, 'iptables_config.txt'), 'w') as f:
            f.write(r_mb1.cmd('iptables -L FORWARD -v -n'))

        with open(os.path.join(RESULTS, 'topology_info.txt'), 'w') as f:
            f.write(f'h1: {h1.IP()}\nh2: {h2.IP()}\n'
                    f'r_mb1: {r_mb1.IP()}\nr_mb2: {r_mb2.IP()}\n')

        recv_proc = h2.popen(
            ['python3', RECEIVER, '--port', str(DST_PORT),
             '--output', os.path.join(RESULTS, 'recv_log.json'), '--timeout', '600'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        recv_proc.stdout.readline()
        time.sleep(0.5)

        sent_logs = []
        for t in range(N_TRIALS):
            print(f'Trial {t+1}/{N_TRIALS}')
            out = os.path.join(RESULTS, f'sent_log_trial{t}.json')
            sent_logs.append(out)
            sp = h1.popen(
                ['python3', SENDER, '--mode', MODE,
                 '--dst', h2.IP(), '--dport', str(DST_PORT),
                 '--trial', str(t), '--output', out],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            for line in sp.stdout:
                print(f'  {line.decode().strip()}')
            sp.wait()
            time.sleep(5)

        recv_proc.terminate()
        recv_proc.wait()

        merged = []
        for p in sent_logs:
            if os.path.exists(p):
                with open(p) as f:
                    merged.extend(json.load(f))
        with open(os.path.join(RESULTS, 'sent_log.json'), 'w') as f:
            json.dump(merged, f, indent=2)

        subprocess.run(['python3', ANALYZE,
            '--sent', os.path.join(RESULTS, 'sent_log.json'),
            '--recv', os.path.join(RESULTS, 'recv_log.json'),
            '--mode', MODE, '--expname', EXP_NAME,
            '--outdir', RESULTS], check=True)

        subprocess.run(['python3', PLOT_CHAIN,
            '--summary', os.path.join(ROOT, 'results/summary/all_results.csv'),
            '--outdir', os.path.join(ROOT, 'plots/figures/')], check=True)

    finally:
        disable_compressor(r_mb1, iface1, daemon_proc)
        disable_spq(r_mb2, iface2)
        net.stop()
        os.system('sudo mn -c > /dev/null 2>&1')
        time.sleep(3)


if __name__ == '__main__':
    if os.geteuid() != 0:
        print('ERROR: Must run with sudo'); sys.exit(1)
    run()
