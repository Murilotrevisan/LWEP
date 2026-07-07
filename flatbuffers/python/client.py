#!/usr/bin/env python3
"""LWEP flatbuffers tester — CLIENT (Python).

Encodes the four canonical messages, sends each framed, receives the echo and
asserts field-by-field equality. Floats are normalized by comparing against a
local encode->decode of the same canonical values (FlatBuffers stores `value` as
float32, so the decoded form is the fair reference). Exit 0 on success.

Usage:  python client.py [host] [port]     (default 127.0.0.1 9001)
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
    return msg_type, payload


def send_frame(sock, msg_type, payload):
    sock.sendall(struct.pack(">IB", len(payload), msg_type) + payload)


def roundtrip(sock, msg_type):
    canon = lwepfb.CANON[msg_type]
    payload = lwepfb.encode(msg_type, canon)
    send_frame(sock, msg_type, payload)
    rtype, echo = recv_frame(sock)
    got = lwepfb.decode(msg_type, echo)
    expected = lwepfb.decode(msg_type, payload)   # normalize float32 rounding
    ok = (rtype == msg_type) and (got == expected)
    print(f"[client] {lwepfb.NAMES[msg_type]:16s} {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("  expected:", expected)
        print("  got     :", got)
    return ok


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print(f"[client] connected to {host}:{port}")
    all_ok = True
    with sock:
        for t in (lwepfb.T_SENSOR, lwepfb.T_WAVEFORM, lwepfb.T_STATUS, lwepfb.T_TELEMETRY):
            all_ok &= roundtrip(sock, t)
    print(f"[client] {'ALL PASS' if all_ok else 'FAILURES PRESENT'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
