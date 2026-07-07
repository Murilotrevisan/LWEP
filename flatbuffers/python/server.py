#!/usr/bin/env python3
"""LWEP flatbuffers tester — SERVER (Python).

Decodes each framed message, prints a field dump, then FULLY re-encodes it
(decode -> dict -> build) and echoes it back — exercising the Python encode path
so the peer's decode is tested too.

Usage:  python server.py [port]     (default 9001)
"""
import os
import socket
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lwepfb


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_frame(sock):
    hdr = recv_exact(sock, 5)
    if hdr is None:
        return None
    length, msg_type = struct.unpack(">IB", hdr)
    payload = recv_exact(sock, length) if length else b""
    if payload is None:
        return None
    return msg_type, payload


def send_frame(sock, msg_type, payload):
    sock.sendall(struct.pack(">IB", len(payload), msg_type) + payload)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    print(f"[server] listening on :{port}")
    conn, addr = srv.accept()
    print(f"[server] client connected from {addr}")
    with conn:
        count = 0
        while True:
            frame = recv_frame(conn)
            if frame is None:
                break
            msg_type, payload = frame
            d = lwepfb.decode(msg_type, payload)
            print(f"[server] recv type={msg_type} ({lwepfb.NAMES.get(msg_type,'?')}): {d}")
            send_frame(conn, msg_type, lwepfb.encode(msg_type, d))  # full re-encode echo
            count += 1
    print(f"[server] done, echoed {count} message(s)")


if __name__ == "__main__":
    main()
