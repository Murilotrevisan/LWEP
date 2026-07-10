"""Wire framing shared by the LWEP GUI and its interop tests.

Mirrors the frame documented in ../common/framing.md and implemented identically
in every harness (protobuf/python/server.py, flatbuffers/python/client.py, the C++
harnesses):

    [uint32 length BIG-ENDIAN][uint8 msg_type][payload ... length bytes]

`length` counts only the payload. Big-endian keeps C (htonl/ntohl) and Python
(struct '>I') in agreement with no extra config.
"""
import socket
import struct

# msg_type ids (see ../common/framing.md)
T_SENSOR, T_WAVEFORM, T_STATUS, T_TELEMETRY = 1, 2, 3, 4
NAMES = {T_SENSOR: "SensorReading", T_WAVEFORM: "Waveform",
         T_STATUS: "DeviceStatus", T_TELEMETRY: "TelemetryPacket"}
MSG_TYPES = (T_SENSOR, T_WAVEFORM, T_STATUS, T_TELEMETRY)


def recv_exact(sock, n):
    """Read exactly n bytes, or return None if the peer closed early.

    TCP may deliver a frame in several chunks, so we loop until we have n bytes.
    """
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_frame(sock):
    """Return (msg_type, payload) or None if the connection closed."""
    hdr = recv_exact(sock, 5)
    if hdr is None:
        return None
    length, msg_type = struct.unpack(">IB", hdr)
    payload = recv_exact(sock, length) if length else b""
    if payload is None:
        return None
    return msg_type, payload


def send_frame(sock, msg_type, payload):
    """Send one framed message (5-byte header + payload)."""
    sock.sendall(struct.pack(">IB", len(payload), msg_type) + payload)


def hexdump(data, width=16):
    """Classic offset / hex / ASCII dump used by the serialization panels."""
    if not data:
        return "(0 bytes)"
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hexpart = " ".join(f"{b:02X}" for b in chunk)
        hexpart = f"{hexpart:<{width * 3 - 1}}"
        asciipart = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{off:04X}  {hexpart}  |{asciipart}|")
    return "\n".join(lines)


def make_server_socket(host, port, backlog=1):
    """Bind + listen with SO_REUSEADDR (used by the GUI 'client' / receiver mode)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(backlog)
    return srv


def connect(host, port, timeout=5.0, retries=50, delay=0.1):
    """Connect as a TCP client, retrying while the peer server comes up.

    Used by the GUI 'server' / encoder mode, which connects to the auto-spawned
    C `main server`. Returns a connected socket or raises the last OSError.
    """
    import time
    last = None
    for _ in range(retries):
        try:
            s = socket.create_connection((host, port), timeout=timeout)
            return s
        except OSError as e:  # server not listening yet
            last = e
            time.sleep(delay)
    raise last if last else OSError("connect failed")
