"""
TTL-limited prober. Sends probe-A and probe-B at each TTL and collects
ICMP Time Exceeded to infer per-hop apparent loss rate difference.
Requires sudo (Scapy raw socket).
"""
import argparse
import json
import os
import struct
import sys
import time

from scapy.all import IP, UDP, Raw, ICMP, sr, conf

HEADER_FMT = '!HHI'
HEADER_SZ  = struct.calcsize(HEADER_FMT)   # 8 bytes
PAYLOAD_SZ = 476
ZERO_DATA  = bytes(PAYLOAD_SZ)

conf.verb = 0


def make_probe(seq, trial, entropy_flag, entropy, src_port, dst_ip, dst_port, ttl):
    hdr = struct.pack(HEADER_FMT, seq, trial, entropy_flag)
    data = os.urandom(PAYLOAD_SZ) if entropy else ZERO_DATA
    return IP(dst=dst_ip, ttl=ttl) / UDP(sport=src_port, dport=dst_port) / Raw(hdr + data)


def probe_ttl(dst_ip, dst_port, ttl, pkts_per_ttl, trial=0):
    """Send probe-A and probe-B at given TTL, return per-ttl stats."""
    # Probe-A: port 9000, random, entropy_flag=1
    pkts_a = [make_probe(seq, trial, 1, True,  9000, dst_ip, dst_port, ttl)
               for seq in range(pkts_per_ttl)]
    ans_a, _ = sr(pkts_a, timeout=3, retry=0)

    time.sleep(2)

    # Probe-B: port 9001, zeros, entropy_flag=0
    pkts_b = [make_probe(seq, trial, 0, False, 9001, dst_ip, dst_port, ttl)
               for seq in range(pkts_per_ttl)]
    ans_b, _ = sr(pkts_b, timeout=3, retry=0)

    time.sleep(2)

    # Parse ICMP responses
    hop_ip = None
    icmp_a = 0
    for sent, received in ans_a:
        if received and received.haslayer(ICMP):
            # RFC 792: ICMP payload = original IP header (20B) + first 8B of UDP
            icmp_payload = bytes(received[ICMP].payload)
            if len(icmp_payload) >= 28:
                quoted_sport = struct.unpack('!H', icmp_payload[20:22])[0]
                if quoted_sport == 9000:
                    icmp_a += 1
                    if hop_ip is None:
                        hop_ip = received[IP].src

    icmp_b = 0
    for sent, received in ans_b:
        if received and received.haslayer(ICMP):
            icmp_payload = bytes(received[ICMP].payload)
            if len(icmp_payload) >= 28:
                quoted_sport = struct.unpack('!H', icmp_payload[20:22])[0]
                if quoted_sport == 9001:
                    icmp_b += 1
                    if hop_ip is None:
                        hop_ip = received[IP].src

    apparent_lA = 1 - icmp_a / pkts_per_ttl
    apparent_lB = 1 - icmp_b / pkts_per_ttl
    apparent_Dl = apparent_lA - apparent_lB

    return {
        'ttl':          ttl,
        'hop_ip':       hop_ip or '*',
        'icmp_A':       icmp_a,
        'icmp_B':       icmp_b,
        'apparent_lA':  round(apparent_lA, 4),
        'apparent_lB':  round(apparent_lB, 4),
        'apparent_Dl':  round(apparent_Dl, 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dst',         required=True)
    ap.add_argument('--max_ttl',     type=int, default=5)
    ap.add_argument('--pkts_per_ttl',type=int, default=200)
    ap.add_argument('--output',      required=True)
    ap.add_argument('--known_mb_hop',type=int, default=3)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print('ERROR: Must run as root (sudo)'); sys.exit(1)

    hops = []
    for ttl in range(1, args.max_ttl + 1):
        print(f'Probing TTL={ttl}...')
        hop = probe_ttl(args.dst, 5000, ttl, args.pkts_per_ttl)
        hops.append(hop)
        print(f'  hop_ip={hop["hop_ip"]} icmp_A={hop["icmp_A"]} icmp_B={hop["icmp_B"]} '
              f'Dl={hop["apparent_Dl"]:.3f}')
        time.sleep(3)

    max_apparent_Dl = max((h['apparent_Dl'] for h in hops), default=0.0)
    ttl_localization_detected = max_apparent_Dl > 0.20

    result = {
        'hops':                       hops,
        'max_apparent_Dl':            round(max_apparent_Dl, 4),
        'ttl_localization_detected':  ttl_localization_detected,
        'known_mb_hop':               args.known_mb_hop,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f'\nMax apparent Dl: {max_apparent_Dl:.3f}')
    print(f'TTL localization detected: {ttl_localization_detected}')
    print(f'Saved: {args.output}')


if __name__ == '__main__':
    main()
