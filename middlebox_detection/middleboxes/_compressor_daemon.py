#!/usr/bin/env python3
"""
nfqueue daemon — raw byte manipulation, large socket buffer, restart loop.
"""
import argparse
import errno
import socket as _socket
import sys
import zlib
from netfilterqueue import NetfilterQueue


def ip_checksum(header: bytearray) -> int:
    if len(header) % 2:
        header += b'\x00'
    s = 0
    for i in range(0, len(header), 2):
        s += (header[i] << 8) + header[i + 1]
    s = (s >> 16) + (s & 0xFFFF)
    s += (s >> 16)
    return ~s & 0xFFFF


def build_handler(dst_port: int):
    def handle_pkt(pkt):
        try:
            data = bytearray(pkt.get_payload())
            if len(data) < 28:
                pkt.accept()
                return
            if (data[0] >> 4) != 4 or data[9] != 17:
                pkt.accept()
                return
            ip_hdr_len = (data[0] & 0x0F) * 4
            udp_dst = (data[ip_hdr_len + 2] << 8) | data[ip_hdr_len + 3]
            if udp_dst != dst_port:
                pkt.accept()
                return
            udp_payload = bytes(data[ip_hdr_len + 8:])
            if not udp_payload:
                pkt.accept()
                return
            ratio   = len(zlib.compress(udp_payload, 1)) / len(udp_payload)
            dscp    = 46 if ratio > 0.85 else 0
            new_tos = dscp << 2
            data[1] = new_tos
            data[10] = 0
            data[11] = 0
            cksum = ip_checksum(data[:ip_hdr_len])
            data[10] = (cksum >> 8) & 0xFF
            data[11] =  cksum       & 0xFF
            pkt.set_payload(bytes(data))
            print(f'ratio={ratio:.3f} dscp={dscp}', flush=True)
        except Exception as e:
            print(f'DAEMON ERROR: {e}', flush=True)
        pkt.accept()
    return handle_pkt


def run_queue(queue_num: int, handler):
    """Bind queue and run with large socket buffer. Returns True to restart."""
    nfq = NetfilterQueue()
    nfq.bind(queue_num, handler, max_len=65536)

    # Increase kernel socket receive buffer to 4 MB
    fd   = nfq.get_fd()
    sock = _socket.fromfd(fd, _socket.AF_UNIX, _socket.SOCK_STREAM)
    try:
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_RCVBUF, 4 * 1024 * 1024)
    except Exception:
        pass

    should_restart = False
    try:
        nfq.run_socket(sock)
        # run_socket() returned normally — buffer overflow or signal, restart
        should_restart = True
        print('nfq.run_socket() returned, restarting...', flush=True)
    except KeyboardInterrupt:
        should_restart = False
    except OSError as e:
        if e.errno == errno.ENOBUFS:
            should_restart = True
            print('ENOBUFS, restarting...', flush=True)
        else:
            print(f'FATAL OSError: {e}', flush=True)
            should_restart = False
    except Exception as e:
        print(f'FATAL: {e}', flush=True)
        should_restart = False
    finally:
        try:
            sock.close()
        except Exception:
            pass
        try:
            nfq.unbind()
        except Exception:
            pass

    return should_restart


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--queue-num', type=int, default=1)
    ap.add_argument('--dst-port',  type=int, default=5000)
    args = ap.parse_args()

    handler = build_handler(args.dst_port)

    sys.stdout.write('DAEMON_READY\n')
    sys.stdout.flush()

    while run_queue(args.queue_num, handler):
        pass   # restart until clean exit or fatal error


if __name__ == '__main__':
    main()