"""
Probe sender. Supports modes: shaper, compressor, spq.
Rate control: deadline-based at 4 Mbps (512-byte packets).
"""
import argparse
import json
import os
import random
import socket
import struct
import sys
import time

HEADER_FMT   = '!HHI'
HEADER_SZ    = struct.calcsize(HEADER_FMT)   # 8 bytes
PAYLOAD_SZ   = 476                            # data bytes
PKT_SZ       = HEADER_SZ + PAYLOAD_SZ        # 484 bytes on wire (UDP payload)
RATE_BPS     = 4e6
WIRE_BITS    = (20 + 8 + PKT_SZ) * 8         # IP+UDP+payload bits = 512*8
INTERVAL     = WIRE_BITS / RATE_BPS          # ~0.001024 s

RANDOM_DATA  = os.urandom(64 * 1024)         # pool for high-entropy payload
ZERO_DATA    = bytes(PAYLOAD_SZ)

DSCP_EF_TOS  = 46 << 2                       # 184


def make_payload(seq, trial, entropy_flag, entropy=True):
    hdr = struct.pack(HEADER_FMT, seq, trial, entropy_flag)
    if entropy:
        offset = random.randint(0, len(RANDOM_DATA) - PAYLOAD_SZ)
        data = RANDOM_DATA[offset:offset + PAYLOAD_SZ]
    else:
        data = ZERO_DATA
    return hdr + data


def send_train(sock, pkts_per_trial, trial, entropy_flag, entropy,
               src_port, dscp, is_probe_of_interest, records):
    train_start = time.time()
    for seq in range(pkts_per_trial):
        payload = make_payload(seq, trial, entropy_flag, entropy)
        sock.send(payload)
        records.append({
            'seq':                seq,
            'trial':              trial,
            'entropy_flag':       entropy_flag,
            'src_port':           src_port,
            'dscp':               dscp,
            'timestamp':          time.time(),
            'is_probe_of_interest': is_probe_of_interest,
        })
        next_slot  = train_start + (seq + 1) * INTERVAL
        remaining  = next_slot - time.time()
        if remaining > 0:
            time.sleep(remaining)

    elapsed = time.time() - train_start
    actual_mbps = (pkts_per_trial * WIRE_BITS) / elapsed / 1e6
    print(f'  Train ef={entropy_flag} trial={trial}: {actual_mbps:.2f} Mbps '
          f'({pkts_per_trial} pkts in {elapsed:.2f}s)')
    if actual_mbps < 2.5:
        print(f'  [WARN] Rate {actual_mbps:.2f} Mbps below 2.5 Mbps threshold')


def make_udp_sock(src_port, dscp=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, dscp)
    sock.bind(('', src_port))
    return sock


def run_shaper(dst_ip, dst_port, trial, records):
    """probe-A: port 9000, random; probe-B: port 9001, zeros"""
    sock_a = make_udp_sock(9000, dscp=0)
    sock_a.connect((dst_ip, dst_port))
    send_train(sock_a, 1000, trial, entropy_flag=1, entropy=True,
               src_port=9000, dscp=0, is_probe_of_interest=True, records=records)
    sock_a.close()

    print(f'  Waiting 30s between trains...')
    time.sleep(30)

    sock_b = make_udp_sock(9001, dscp=0)
    sock_b.connect((dst_ip, dst_port))
    send_train(sock_b, 1000, trial, entropy_flag=0, entropy=False,
               src_port=9001, dscp=0, is_probe_of_interest=True, records=records)
    sock_b.close()


def run_compressor(dst_ip, dst_port, trial, records):
    """probe-A: port 9000, random; probe-B: port 9000, zeros — same port"""
    sock_a = make_udp_sock(9000, dscp=0)
    sock_a.connect((dst_ip, dst_port))
    send_train(sock_a, 1000, trial, entropy_flag=1, entropy=True,
               src_port=9000, dscp=0, is_probe_of_interest=True, records=records)
    sock_a.close()

    print(f'  Waiting 30s between trains...')
    time.sleep(30)

    sock_b = make_udp_sock(9000, dscp=0)
    sock_b.connect((dst_ip, dst_port))
    send_train(sock_b, 1000, trial, entropy_flag=0, entropy=False,
               src_port=9000, dscp=0, is_probe_of_interest=True, records=records)
    sock_b.close()


def run_spq(dst_ip, dst_port, trial, records):
    """
    LP Phase: 4 initial DSCP-EF separation + [LP, HP, HP, HP, HP] x 1000
    Wait 30s
    HP Phase: [HP, LP, LP, LP, LP] x 1000
    """
    sock_hi = make_udp_sock(9001, dscp=DSCP_EF_TOS)
    sock_hi.connect((dst_ip, dst_port))
    sock_lo = make_udp_sock(9000, dscp=0)
    sock_lo.connect((dst_ip, dst_port))

    # LP Phase — initial 4 separation packets to fill QH
    for i in range(4):
        sep_payload = struct.pack(HEADER_FMT, i, trial, 99) + ZERO_DATA
        sock_hi.send(sep_payload)
        records.append({
            'seq': i, 'trial': trial, 'entropy_flag': 99,
            'src_port': 9001, 'dscp': DSCP_EF_TOS,
            'timestamp': time.time(), 'is_probe_of_interest': False,
        })
        time.sleep(INTERVAL)

    # LP Phase interleaved: 1 LP + 4 HP-separation per iteration
    lp_start = time.time()
    pkt_num  = 0
    for seq in range(1000):
        # LP probe of interest
        payload = make_payload(seq, trial, entropy_flag=1, entropy=False)
        sock_lo.send(payload)
        records.append({
            'seq': seq, 'trial': trial, 'entropy_flag': 1,
            'src_port': 9000, 'dscp': 0,
            'timestamp': time.time(), 'is_probe_of_interest': True,
        })
        pkt_num += 1
        next_slot = lp_start + pkt_num * INTERVAL
        rem = next_slot - time.time()
        if rem > 0: time.sleep(rem)

        # 4 HP separation packets
        for _ in range(4):
            sep_payload = struct.pack(HEADER_FMT, seq, trial, 99) + ZERO_DATA
            sock_hi.send(sep_payload)
            records.append({
                'seq': seq, 'trial': trial, 'entropy_flag': 99,
                'src_port': 9001, 'dscp': DSCP_EF_TOS,
                'timestamp': time.time(), 'is_probe_of_interest': False,
            })
            pkt_num += 1
            next_slot = lp_start + pkt_num * INTERVAL
            rem = next_slot - time.time()
            if rem > 0: time.sleep(rem)

    elapsed = time.time() - lp_start
    lp_pkts = 1000 + 4 * 1000 + 4
    actual_mbps = (lp_pkts * WIRE_BITS) / elapsed / 1e6
    print(f'  LP Phase trial={trial}: {actual_mbps:.2f} Mbps')

    print(f'  Waiting 30s between phases...')
    time.sleep(30)

    # HP Phase: 1 HP probe of interest + 4 LP separation
    hp_start = time.time()
    pkt_num  = 0
    for seq in range(1000):
        # HP probe of interest
        payload = make_payload(seq, trial, entropy_flag=0, entropy=False)
        sock_hi.send(payload)
        records.append({
            'seq': seq, 'trial': trial, 'entropy_flag': 0,
            'src_port': 9001, 'dscp': DSCP_EF_TOS,
            'timestamp': time.time(), 'is_probe_of_interest': True,
        })
        pkt_num += 1
        next_slot = hp_start + pkt_num * INTERVAL
        rem = next_slot - time.time()
        if rem > 0: time.sleep(rem)

        # 4 LP separation packets
        for _ in range(4):
            sep_payload = struct.pack(HEADER_FMT, seq, trial, 99) + ZERO_DATA
            sock_lo.send(sep_payload)
            records.append({
                'seq': seq, 'trial': trial, 'entropy_flag': 99,
                'src_port': 9000, 'dscp': 0,
                'timestamp': time.time(), 'is_probe_of_interest': False,
            })
            pkt_num += 1
            next_slot = hp_start + pkt_num * INTERVAL
            rem = next_slot - time.time()
            if rem > 0: time.sleep(rem)

    elapsed = time.time() - hp_start
    hp_pkts = 1000 + 4 * 1000
    actual_mbps = (hp_pkts * WIRE_BITS) / elapsed / 1e6
    print(f'  HP Phase trial={trial}: {actual_mbps:.2f} Mbps')

    sock_hi.close()
    sock_lo.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode',   required=True, choices=['shaper', 'compressor', 'spq'])
    ap.add_argument('--dst',    required=True)
    ap.add_argument('--dport',  type=int, default=5000)
    ap.add_argument('--trial',  type=int, required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()

    records = []

    if args.mode == 'shaper':
        run_shaper(args.dst, args.dport, args.trial, records)
    elif args.mode == 'compressor':
        run_compressor(args.dst, args.dport, args.trial, records)
    elif args.mode == 'spq':
        run_spq(args.dst, args.dport, args.trial, records)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(records, f, indent=2)

    print(f'  Wrote {len(records)} sent records to {args.output}')


if __name__ == '__main__':
    main()
