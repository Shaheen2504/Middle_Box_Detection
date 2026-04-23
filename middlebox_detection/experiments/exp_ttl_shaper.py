"""
EXP TTL-A — TTL failure with Shaper
Purpose: Show TTL cannot localize shaper (apparent Dl < 2% per hop)
Expected: max_apparent_Dl < 5%, ttl_localization_detected = False
Run: sudo python3 experiments/exp_ttl_shaper.py
"""
import os, sys, time, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mininet.log import setLogLevel
from topology.single_mb_topo import create_single_mb_topo
from middleboxes.shaper import enable_shaper, disable_shaper

EXP_NAME = 'exp_ttl_shaper'
MODE     = 'shaper'
N_TRIALS = 5
DST_PORT = 5000
ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS  = os.path.join(ROOT, f'results/raw/{EXP_NAME}')
SENDER   = os.path.join(ROOT, 'probing/sender.py')
RECEIVER = os.path.join(ROOT, 'probing/receiver.py')
ANALYZE  = os.path.join(ROOT, 'analysis/analyze.py')
TTL_PROBER = os.path.join(ROOT, 'probing/ttl_prober.py')
PLOT_TTL   = os.path.join(ROOT, 'plots/plot_ttl_failure.py')


def run():
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'results/summary'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'plots/figures'), exist_ok=True)
    setLogLevel('warning')

    net, h1, h2, rn1, rn2, r_mb, rn3 = create_single_mb_topo()
    iface = 'r_mb-eth1'

    try:
        with open(os.path.join(RESULTS, 'tc_config.txt'), 'w') as f:
            f.write('--- BEFORE ---\n')
            f.write(r_mb.cmd(f'tc qdisc show dev {iface}'))

        enable_shaper(r_mb, iface)

        with open(os.path.join(RESULTS, 'tc_config.txt'), 'a') as f:
            f.write('\n--- AFTER ENABLING MB ---\n')
            f.write(r_mb.cmd(f'tc qdisc show dev {iface}'))
            f.write(r_mb.cmd(f'tc class show dev {iface}'))
            f.write(r_mb.cmd(f'tc filter show dev {iface}'))

        with open(os.path.join(RESULTS, 'topology_info.txt'), 'w') as f:
            f.write(f'h1: {h1.IP()}\nh2: {h2.IP()}\nr_mb: {r_mb.IP()}\n'
                    f'known_mb_hop: 3\n')

        # --- End-to-end probing (same as exp1) ---
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

        # --- TTL probing ---
        print('\nRunning TTL prober...')
        ttl_out = os.path.join(RESULTS, 'ttl_result.json')
        h1.cmd(
            f'python3 {TTL_PROBER} --dst {h2.IP()} --max_ttl 5 '
            f'--pkts_per_ttl 200 --output {ttl_out} --known_mb_hop 3'
        )

        # Auto-generate TTL plot if all required results exist
        e2e_result = os.path.join(RESULTS, 'analysis_result.json')
        nat_result  = os.path.join(ROOT, 'results/raw/exp_ttl_nat/ttl_result.json')
        if os.path.exists(ttl_out) and os.path.exists(e2e_result):
            args = [
                'python3', PLOT_TTL,
                '--ttl_result', ttl_out,
                '--e2e_result', e2e_result,
                '--outdir', os.path.join(ROOT, 'plots/figures/'),
                '--name', 'shaper',
            ]
            if os.path.exists(nat_result):
                args += ['--nat_result', nat_result]
            subprocess.run(args, check=False)

    finally:
        disable_shaper(r_mb, iface)
        net.stop()
        os.system('sudo mn -c > /dev/null 2>&1')
        time.sleep(3)


if __name__ == '__main__':
    if os.geteuid() != 0:
        print('ERROR: Must run with sudo'); sys.exit(1)
    run()
