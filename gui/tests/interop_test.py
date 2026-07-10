#!/usr/bin/env python3
"""Automated interop suite — the Definition-of-Done gate for the LWEP GUI.

Runs headless (no Tkinter) over the SAME wire/codecs/cpeer modules the GUI uses,
so a green run here is exactly the cross-language coherence the GUI demonstrates.

Matrix (2 IDLs x 4 messages):
  A. unit             — codec encode->decode is stable (no network)
  B. Python -> C      — GUI 'server' mode: Python encodes, C `main server`
                        decodes + re-encodes + echoes; assert the echo round-trips
  C. C -> Python      — GUI 'client' mode: C `main client` encodes the 4 canonical,
                        Python decodes + echoes; assert Python's parse matches and
                        the C client reports ALL PASS

Exit code 0 iff every case passes ("ALL PASS"), 1 otherwise. No pytest required.

Run:  C:\\msys64\\ucrt64\\bin\\python.exe gui\\tests\\interop_test.py
"""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # gui/

import wire  # noqa: E402
import lwep_codecs as C  # noqa: E402
from cpeer import CPeer  # noqa: E402
from wire import MSG_TYPES, NAMES  # noqa: E402

HOST = "127.0.0.1"
IDLS = ("protobuf", "flatbuffer")

_results = []  # (label, ok)


def record(label, ok, detail=""):
    _results.append((label, ok))
    tag = "PASS" if ok else "FAIL"
    line = f"  [{tag}] {label}"
    if detail and not ok:
        line += f"  -- {detail}"
    print(line, flush=True)
    return ok


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, 0))
    p = s.getsockname()[1]
    s.close()
    return p


def refs(codec):
    """Per-type reference dict = decode(encode(canonical)) (float32-normalized)."""
    return {t: codec.decode(t, codec.encode(t, C.canonical(t))) for t in MSG_TYPES}


# ---- A. unit round-trip (no network) --------------------------------------
def part_a():
    print("Part A - codec encode/decode idempotence (no network)")
    for idl in IDLS:
        codec = C.get_codec(idl)
        ref = refs(codec)
        for t in MSG_TYPES:
            again = codec.decode(t, codec.encode(t, ref[t]))
            record(f"unit {idl}/{NAMES[t]}", again == ref[t], "not idempotent")


# ---- B. Python encode -> C decode (GUI 'server' mode) ---------------------
def part_b():
    print("Part B - Python encode -> C decode+echo (GUI 'server' mode)")
    for idl in IDLS:
        codec = C.get_codec(idl)
        ref = refs(codec)
        port = free_port()
        peer = CPeer(idl, "server", HOST, port)
        sock = None
        try:
            peer.start()
            sock = wire.connect(HOST, port, timeout=5, retries=60, delay=0.1)
            sock.settimeout(5)
            for t in MSG_TYPES:
                wire.send_frame(sock, t, codec.encode(t, C.canonical(t)))
                frame = wire.recv_frame(sock)
                if frame is None:
                    record(f"py->C {idl}/{NAMES[t]}", False, "no echo (closed)")
                    continue
                rt, payload = frame
                got = codec.decode(rt, payload)
                record(f"py->C {idl}/{NAMES[t]}", rt == t and got == ref[t], "echo mismatch")
            sock.close()
            sock = None
            rc, lines = peer.finish(5)
            record(f"py->C {idl}: C server exit==0", rc == 0, f"rc={rc}")
            record(f"py->C {idl}: C echoed 4", any("echoed 4" in ln for ln in lines),
                   " | ".join(lines))
        except Exception as e:  # noqa: BLE001
            record(f"py->C {idl}", False, repr(e))
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
            peer.stop()


# ---- C. C encode -> Python decode (GUI 'client' mode) ---------------------
def part_c():
    print("Part C - C encode -> Python decode+echo (GUI 'client' mode)")
    for idl in IDLS:
        codec = C.get_codec(idl)
        ref = refs(codec)
        srv = wire.make_server_socket(HOST, 0)   # ephemeral, race-free
        port = srv.getsockname()[1]
        srv.settimeout(8)
        peer = CPeer(idl, "client", HOST, port)
        conn = None
        try:
            peer.start()
            conn, _ = srv.accept()
            conn.settimeout(5)
            for _ in range(len(MSG_TYPES)):
                frame = wire.recv_frame(conn)
                if frame is None:
                    record(f"C->py {idl}", False, "closed early")
                    break
                rt, payload = frame
                got = codec.decode(rt, payload)
                record(f"C->py {idl}/{NAMES[rt]}", got == ref[rt], "parse mismatch")
                wire.send_frame(conn, rt, codec.encode(rt, got))  # echo for the C client
            conn.close()
            conn = None
            rc, lines = peer.finish(5)
            record(f"C->py {idl}: C client exit==0", rc == 0, f"rc={rc}")
            record(f"C->py {idl}: C ALL PASS", any("ALL PASS" in ln for ln in lines),
                   " | ".join(lines))
        except Exception as e:  # noqa: BLE001
            record(f"C->py {idl}", False, repr(e))
        finally:
            if conn:
                try:
                    conn.close()
                except OSError:
                    pass
            srv.close()
            peer.stop()


def main():
    part_a()
    part_b()
    part_c()
    passed = sum(1 for _, ok in _results if ok)
    total = len(_results)
    print("-" * 60)
    all_ok = passed == total
    print(f"{'ALL PASS' if all_ok else 'FAILURES PRESENT'} ({passed}/{total})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
