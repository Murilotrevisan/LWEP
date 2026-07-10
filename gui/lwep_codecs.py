"""IDL-neutral codec layer for the LWEP GUI and interop tests.

Both stacks (Protobuf/nanopb and FlatBuffers/FlatCC) describe the SAME four
messages, so every message is represented here as a plain Python dict with an
identical shape across IDLs (the same shape lwepfb already uses). A single field
schema then drives the editor form for both stacks.

    codec = get_codec("protobuf")      # or "flatbuffer"
    buf   = codec.encode(T_SENSOR, d)  # dict -> bytes
    d2    = codec.decode(T_SENSOR, buf)# bytes -> dict

The FlatBuffers codec reuses flatbuffers/python/lwepfb.py verbatim (single source
of truth for its builders/readers); the Protobuf codec mirrors the builders in
protobuf/python/client.py but is driven by the editable dict.
"""
import copy
import os
import sys

from wire import (T_SENSOR, T_WAVEFORM, T_STATUS, T_TELEMETRY,  # noqa: F401
                  NAMES, MSG_TYPES)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_PB_PY = os.path.join(_ROOT, "protobuf", "python")
_FB_PY = os.path.join(_ROOT, "flatbuffers", "python")

# ---- SensorType enum (identical integer values in both IDLs) --------------
SENSOR_TYPES = [("UNKNOWN", 0), ("TEMPERATURE", 1), ("PRESSURE", 2),
                ("HUMIDITY", 3), ("VOLTAGE", 4)]
SENSOR_TYPE_NAME = {v: k for k, v in SENSOR_TYPES}

# ---- canonical test values (mirror ../messages/ and the existing harnesses) --
CANON = {
    T_SENSOR: {
        "id": 4097, "sensor_type": 1, "value": 23.5, "value_precise": 23.481523,
        "timestamp": 1720224000000, "is_valid": True, "raw_count": -12345,
        "label": "cabin-temp",
    },
    T_WAVEFORM: {
        "channel": 3,
        "samples": [0, 100, -100, 32767, -32768, 5, 6, 7, 8, 9],
        "gains": [1.0, 0.5, 0.25, 2.0],
        "tags": ["ch3", "raw", "v2"],
        "checksum": 0xDEADBEEF,
    },
    T_STATUS: {
        "device_id": 0x2A2A,
        "flags": (1 << 0) | (1 << 2) | (6 << 4) | (87 << 8),  # 0x5765
        "error_code": 0,
    },
}
CANON[T_TELEMETRY] = {
    "header": {"version": 2, "seq": 42, "source_addr": 0x00A5},
    "reading": CANON[T_SENSOR],
    "waveform": CANON[T_WAVEFORM],
    "status": CANON[T_STATUS],
    "extra_readings": [
        {"id": 1, "sensor_type": 2, "value": 101.3, "value_precise": 101.325,
         "timestamp": 1720224000001, "is_valid": True, "raw_count": 2048, "label": "baro"},
        {"id": 2, "sensor_type": 3, "value": 45.0, "value_precise": 45.0,
         "timestamp": 1720224000002, "is_valid": False, "raw_count": 0, "label": "rh"},
    ],
    "payload": bytes([0x01, 0x02, 0x03, 0x04, 0xFF, 0xFE, 0xFD, 0x00]),
}


def canonical(msg_type):
    """A fresh, mutable copy of the canonical values for one message type."""
    return copy.deepcopy(CANON[msg_type])


# ---- editor field schema (decision 3: scalars/bitfield editable first) -----
# kind: uint | int | float | double | bool | enum | string | hexint
# Ranges let the form reject out-of-range input before it ever hits the wire.
U16, U32, U64, U8 = (0, 0xFFFF), (0, 0xFFFFFFFF), (0, 0xFFFFFFFFFFFFFFFF), (0, 0xFF)
I32 = (-2147483648, 2147483647)

FIELD_SCHEMA = {
    T_SENSOR: [
        {"key": "id",            "label": "id (uint16)",        "kind": "uint",   "range": U16},
        {"key": "sensor_type",   "label": "sensor_type (enum)", "kind": "enum",   "choices": SENSOR_TYPES},
        {"key": "value",         "label": "value (float32)",    "kind": "float"},
        {"key": "value_precise", "label": "value_precise (f64)","kind": "double"},
        {"key": "timestamp",     "label": "timestamp (uint64)", "kind": "uint",   "range": U64},
        {"key": "is_valid",      "label": "is_valid (bool)",    "kind": "bool"},
        {"key": "raw_count",     "label": "raw_count (int32)",  "kind": "int",    "range": I32},
        {"key": "label",         "label": "label (string<=16)", "kind": "string", "maxbytes": 16},
    ],
    T_STATUS: [
        {"key": "device_id",  "label": "device_id (uint16)",  "kind": "uint",   "range": U16},
        {"key": "flags",      "label": "flags (uint32, hex)", "kind": "hexint", "range": U32},
        {"key": "error_code", "label": "error_code (uint8)",  "kind": "uint",   "range": U8},
    ],
}
# Messages not in FIELD_SCHEMA are sent from their canonical values (read-only in
# the editor) — Waveform and TelemetryPacket for now.
EDITABLE = set(FIELD_SCHEMA)


# ---- pretty field dump (generic; same dict shape for both IDLs) ------------
def format_fields(msg_type, d):
    """Human-readable field dump for the serialization / parse panels."""
    return f"{NAMES[msg_type]} {{\n{_fmt(d, 1)}\n}}"


def _fmt(value, depth):
    pad = "  " * depth
    if isinstance(value, dict):
        lines = [f"{pad}{k}: {_fmt_inline(k, v, depth)}" for k, v in value.items()]
        return "\n".join(lines)
    return f"{pad}{value}"


def _fmt_inline(key, v, depth):
    if isinstance(v, (bytes, bytearray)):
        return f"bytes[{len(v)}] " + " ".join(f"{b:02X}" for b in v)
    if isinstance(v, dict):
        return "{\n" + _fmt(v, depth + 1) + "\n" + "  " * depth + "}"
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            parts = ["\n" + "  " * (depth + 1) + "{\n" + _fmt(e, depth + 2) +
                     "\n" + "  " * (depth + 1) + "}" for e in v]
            return f"[{len(v)}]" + "".join(parts)
        return f"{v}"
    if key == "sensor_type" and isinstance(v, int):
        return f"{v} ({SENSOR_TYPE_NAME.get(v, '?')})"
    if key in ("flags", "checksum", "device_id", "source_addr") and isinstance(v, int):
        return f"{v} (0x{v:X})"
    return f"{v}"


# =========================================================================
#  Protobuf / nanopb codec
# =========================================================================
class PbCodec:
    idl = "protobuf"
    name = "Protobuf / nanopb"

    def __init__(self):
        if _PB_PY not in sys.path:
            sys.path.insert(0, _PB_PY)
        try:
            import lwep_pb2
        except ImportError as e:  # pragma: no cover
            raise SystemExit("lwep_pb2 not found — run protobuf/python/generate.ps1") from e
        self.pb = lwep_pb2
        self._cls = {
            T_SENSOR: lwep_pb2.SensorReading, T_WAVEFORM: lwep_pb2.Waveform,
            T_STATUS: lwep_pb2.DeviceStatus, T_TELEMETRY: lwep_pb2.TelemetryPacket,
        }

    # -- build (dict -> message) --
    def _sensor(self, d):
        m = self.pb.SensorReading()
        m.id, m.sensor_type, m.value = d["id"], d["sensor_type"], d["value"]
        m.value_precise, m.timestamp = d["value_precise"], d["timestamp"]
        m.is_valid, m.raw_count, m.label = d["is_valid"], d["raw_count"], d["label"]
        return m

    def _waveform(self, d):
        m = self.pb.Waveform()
        m.channel = d["channel"]
        m.samples.extend(d["samples"])
        m.gains.extend(d["gains"])
        m.tags.extend(d["tags"])
        m.checksum = d["checksum"]
        return m

    def _status(self, d):
        m = self.pb.DeviceStatus()
        m.device_id, m.flags, m.error_code = d["device_id"], d["flags"], d["error_code"]
        return m

    def _telemetry(self, d):
        m = self.pb.TelemetryPacket()
        h = d["header"]
        m.header.version, m.header.seq, m.header.source_addr = h["version"], h["seq"], h["source_addr"]
        m.reading.CopyFrom(self._sensor(d["reading"]))
        m.waveform.CopyFrom(self._waveform(d["waveform"]))
        m.status.CopyFrom(self._status(d["status"]))
        for e in d["extra_readings"]:
            m.extra_readings.add().CopyFrom(self._sensor(e))
        m.payload = bytes(d["payload"])
        return m

    def _build(self, t, d):
        return {T_SENSOR: self._sensor, T_WAVEFORM: self._waveform,
                T_STATUS: self._status, T_TELEMETRY: self._telemetry}[t](d)

    def encode(self, t, d):
        return self._build(t, d).SerializeToString()

    # -- read (message -> dict) --
    def _read_sensor(self, m):
        return {"id": m.id, "sensor_type": int(m.sensor_type), "value": m.value,
                "value_precise": m.value_precise, "timestamp": m.timestamp,
                "is_valid": m.is_valid, "raw_count": m.raw_count, "label": m.label}

    def _read_waveform(self, m):
        return {"channel": m.channel, "samples": list(m.samples),
                "gains": list(m.gains), "tags": list(m.tags), "checksum": m.checksum}

    def _read_status(self, m):
        return {"device_id": m.device_id, "flags": m.flags, "error_code": m.error_code}

    def _read_telemetry(self, m):
        return {"header": {"version": m.header.version, "seq": m.header.seq,
                           "source_addr": m.header.source_addr},
                "reading": self._read_sensor(m.reading),
                "waveform": self._read_waveform(m.waveform),
                "status": self._read_status(m.status),
                "extra_readings": [self._read_sensor(e) for e in m.extra_readings],
                "payload": bytes(m.payload)}

    def decode(self, t, buf):
        msg = self._cls[t]()
        msg.ParseFromString(buf)
        return {T_SENSOR: self._read_sensor, T_WAVEFORM: self._read_waveform,
                T_STATUS: self._read_status, T_TELEMETRY: self._read_telemetry}[t](msg)


# =========================================================================
#  FlatBuffers / FlatCC codec — reuses flatbuffers/python/lwepfb.py
# =========================================================================
class FbCodec:
    idl = "flatbuffer"
    name = "FlatBuffers / FlatCC"

    def __init__(self):
        if _FB_PY not in sys.path:
            sys.path.insert(0, _FB_PY)
        try:
            import lwepfb
        except (ImportError, SystemExit) as e:  # pragma: no cover
            raise SystemExit("lwepfb / generated 'lwep' package not found — run "
                             "flatbuffers/python/generate.ps1") from e
        self.fb = lwepfb

    def encode(self, t, d):
        return self.fb.encode(t, d)

    def decode(self, t, buf):
        return self.fb.decode(t, buf)


_CODECS = {"protobuf": PbCodec, "flatbuffer": FbCodec}


def get_codec(idl):
    """Instantiate the codec for 'protobuf' or 'flatbuffer'."""
    try:
        return _CODECS[idl]()
    except KeyError:
        raise ValueError(f"unknown idl {idl!r} (expected 'protobuf' or 'flatbuffer')")
