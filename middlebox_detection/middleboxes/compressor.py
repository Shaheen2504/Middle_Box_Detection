"""
MB2 — Network Compressor (nfqueue + zlib + tc HTB).
Classifies by payload entropy, rewrites IP TOS to DSCP EF for high-entropy packets,
then tc HTB shapes EF-marked traffic to sigma_mbps.
"""
import os
import subprocess
import threading

DAEMON_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_compressor_daemon.py')


def enable_compressor(router, iface, sigma_mbps=2, dst_port=5000, queue_num=1):
    router.cmd('sysctl -w net.core.rmem_max=4194304 net.core.rmem_default=4194304')
    # Start nfqueue daemon in router namespace
    daemon_proc = router.popen(
        ['python3', DAEMON_SCRIPT, '--queue-num', str(queue_num), '--dst-port', str(dst_port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    # Wait for daemon ready signal
    ready = daemon_proc.stdout.readline()
    if b'DAEMON_READY' not in ready:
        raise RuntimeError(f'Compressor daemon failed to start. Got: {ready}')
    def _drain(proc):
        for _ in proc.stdout:
            pass

    threading.Thread(target=_drain, args=(daemon_proc,), daemon=True).start()

    # iptables rule: intercept forwarded UDP to dst_port
    router.cmd(
        f'iptables -I FORWARD -o {iface} -p udp --dport {dst_port} '
        f'-j NFQUEUE --queue-num {queue_num}'
    )

    # tc HTB: shape DSCP EF traffic to sigma_mbps
    router.cmd(f'tc qdisc del dev {iface} root 2>/dev/null || true')
    router.cmd(f'tc qdisc add dev {iface} root handle 1: htb default 20')
    router.cmd(f'tc class add dev {iface} parent 1: classid 1:10 htb rate {sigma_mbps}mbit burst 4k')
    router.cmd(f'tc class add dev {iface} parent 1: classid 1:20 htb rate 10mbit burst 100k')
    router.cmd(f'tc qdisc add dev {iface} parent 1:10 bfifo limit 5120')
    # DSCP EF = TOS 0xb8, mask 0xfc (upper 6 bits = DSCP field)
    router.cmd(
        f'tc filter add dev {iface} protocol ip parent 1: prio 1 '
        f'u32 match ip tos 0xb8 0xfc flowid 1:10'
    )

    return daemon_proc


def disable_compressor(router, iface, daemon_proc):
    router.cmd('iptables -D FORWARD -o ' + iface +
               ' -p udp --dport 5000 -j NFQUEUE --queue-num 1 2>/dev/null || true')
    router.cmd(f'tc qdisc del dev {iface} root 2>/dev/null || true')
    if daemon_proc and daemon_proc.poll() is None:
        daemon_proc.terminate()
        daemon_proc.wait()
