"""
UDP receiver. Binds on 0.0.0.0:<port>, prints READY, records every arriving packet.
Exits on SIGTERM or inactivity timeout.
"""
import argparse
import json
import os
import signal
import socket
import struct
import sys
import time

HEADER_FMT = '!HHI'   # seq(2) trial(2) entropy_flag(4)
HEADER_SZ  = struct.calcsize(HEADER_FMT)

records = []
last_pkt_time = None
running = True


def handle_sigterm(signum, frame):
    global running
    running = False


signal.signal(signal.SIGTERM, handle_sigterm)


def main():
    global last_pkt_time, running

    ap = argparse.ArgumentParser()
    ap.add_argument('--port',    type=int, required=True)
    ap.add_argument('--output',  required=True)
    ap.add_argument('--timeout', type=int, default=600)
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', args.port))
    sock.settimeout(1.0)

    # Synchronisation signal
    sys.stdout.write('READY\n')
    sys.stdout.flush()

    last_pkt_time = time.time()

    while running:
        now = time.time()
        if now - last_pkt_time > args.timeout:
            break
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue

        ts = time.time()
        last_pkt_time = ts

        if len(data) < HEADER_SZ:
            continue

        seq, trial, entropy_flag = struct.unpack(HEADER_FMT, data[:HEADER_SZ])
        src_port = addr[1]

        records.append({
            'seq':          seq,
            'trial':        trial,
            'entropy_flag': entropy_flag,
            'src_port':     src_port,
            'timestamp':    ts,
            'size':         len(data),
        })

    sock.close()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(records, f, indent=2)

    print(f'[receiver] wrote {len(records)} records to {args.output}', file=sys.stderr)


if __name__ == '__main__':
    main()
