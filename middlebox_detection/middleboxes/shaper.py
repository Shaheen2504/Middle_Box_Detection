"""
MB1 — Traffic Shaper using tc HTB.
Port 9000 -> 2 Mbps (probe-A). All others -> 10 Mbps (probe-B).
"""


def enable_shaper(router, iface, sigma_mbps=2, shaped_port=9000, queue_limit_pkts=10):
    queue_limit_bytes = queue_limit_pkts * 512

    router.cmd(f'tc qdisc del dev {iface} root 2>/dev/null || true')

    router.cmd(f'tc qdisc add dev {iface} root handle 1: htb default 20')
    router.cmd(f'tc class add dev {iface} parent 1: classid 1:10 htb rate {sigma_mbps}mbit burst 4k')
    router.cmd(f'tc class add dev {iface} parent 1: classid 1:20 htb rate 10mbit burst 100k')
    router.cmd(f'tc qdisc add dev {iface} parent 1:10 bfifo limit {queue_limit_bytes}')
    router.cmd(f'tc qdisc add dev {iface} parent 1:20 bfifo limit 100000')
    router.cmd(
        f'tc filter add dev {iface} protocol ip parent 1: prio 1 '
        f'u32 match ip sport {shaped_port} 0xffff flowid 1:10'
    )


def disable_shaper(router, iface):
    router.cmd(f'tc qdisc del dev {iface} root 2>/dev/null || true')


def verify_shaper(router, iface) -> str:
    out = router.cmd(f'tc qdisc show dev {iface}')
    out += router.cmd(f'tc class show dev {iface}')
    out += router.cmd(f'tc filter show dev {iface}')
    return out
