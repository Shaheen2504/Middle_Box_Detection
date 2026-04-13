"""
MB3 — Strict Priority Queue (tc PRIO).
DSCP EF (TOS=0xB8) -> band 0 (highest, always served first).
DSCP 0              -> band 1 (served only when band 0 empty).
"""


def enable_spq(router, iface, link_rate_mbps=2):
    router.cmd(f'tc qdisc del dev {iface} root 2>/dev/null || true')

    # Step 1: HTB root enforces the 2 Mbps bottleneck (restores what TCLink had)
    router.cmd(f'tc qdisc add dev {iface} root handle 1: htb default 1')
    router.cmd(
        f'tc class add dev {iface} parent 1: classid 1:1 '
        f'htb rate {link_rate_mbps}mbit burst 4k'
    )

    # Step 2: PRIO qdisc under HTB — strict priority within the 2 Mbps budget
    router.cmd(
        f'tc qdisc add dev {iface} parent 1:1 handle 10: prio bands 2 '
        f'priomap 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1'
    )

    # Step 3: leaf qdiscs for each band
    router.cmd(f'tc qdisc add dev {iface} parent 10:1 handle 100: bfifo limit 5120')
    router.cmd(f'tc qdisc add dev {iface} parent 10:2 handle 200: bfifo limit 5120')

    # Step 4: DSCP EF -> band 0 (high priority)
    # Filter must point at PRIO handle (10:), not HTB handle (1:)
    router.cmd(
        f'tc filter add dev {iface} parent 10: protocol ip prio 1 '
        f'u32 match ip tos 0xb8 0xfc classid 10:1'
    )


def disable_spq(router, iface):
    router.cmd(f'tc qdisc del dev {iface} root 2>/dev/null || true')


def verify_spq(router, iface) -> str:
    out  = router.cmd(f'tc qdisc show dev {iface}')
    out += router.cmd(f'tc class show dev {iface}')
    out += router.cmd(f'tc filter show dev {iface}')
    return out
