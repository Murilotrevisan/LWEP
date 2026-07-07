"""Shared FlatBuffers build/read helpers for the LWEP Python harness.

Messages are represented as plain Python dicts (see CANON) so the same builders
serve the client (encoding canonical values) and the server (re-encoding what it
decoded). Requires the generated `lwep` package (run generate.ps1) and
`pip install flatbuffers` (>= 2.0, where Builder.EndVector() takes no argument).
"""
import flatbuffers

try:
    from lwep import (SensorReading, Waveform, DeviceStatus,
                      PacketHeader, TelemetryPacket, SensorType)
except ImportError as e:  # pragma: no cover
    raise SystemExit("generated 'lwep' package not found — run generate.ps1 first") from e

# msg_type ids (see ../../common/framing.md)
T_SENSOR, T_WAVEFORM, T_STATUS, T_TELEMETRY = 1, 2, 3, 4

# ---- canonical test values (mirror ../../messages/) ----------------------
CANON = {
    T_SENSOR: {
        "id": 4097, "sensor_type": SensorType.SensorType.TEMPERATURE,
        "value": 23.5, "value_precise": 23.481523, "timestamp": 1720224000000,
        "is_valid": True, "raw_count": -12345, "label": "cabin-temp",
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
        {"id": 1, "sensor_type": SensorType.SensorType.PRESSURE, "value": 101.3,
         "value_precise": 101.325, "timestamp": 1720224000001, "is_valid": True,
         "raw_count": 2048, "label": "baro"},
        {"id": 2, "sensor_type": SensorType.SensorType.HUMIDITY, "value": 45.0,
         "value_precise": 45.0, "timestamp": 1720224000002, "is_valid": False,
         "raw_count": 0, "label": "rh"},
    ],
    "payload": bytes([0x01, 0x02, 0x03, 0x04, 0xFF, 0xFE, 0xFD, 0x00]),
}


# ---- builders (return a table offset) ------------------------------------
def build_sensor(b, d):
    label = b.CreateString(d["label"])
    SensorReading.SensorReadingStart(b)
    SensorReading.SensorReadingAddId(b, d["id"])
    SensorReading.SensorReadingAddSensorType(b, d["sensor_type"])
    SensorReading.SensorReadingAddValue(b, d["value"])
    SensorReading.SensorReadingAddValuePrecise(b, d["value_precise"])
    SensorReading.SensorReadingAddTimestamp(b, d["timestamp"])
    SensorReading.SensorReadingAddIsValid(b, d["is_valid"])
    SensorReading.SensorReadingAddRawCount(b, d["raw_count"])
    SensorReading.SensorReadingAddLabel(b, label)
    return SensorReading.SensorReadingEnd(b)


def build_waveform(b, d):
    Waveform.WaveformStartSamplesVector(b, len(d["samples"]))
    for x in reversed(d["samples"]):
        b.PrependInt16(x)
    samples = b.EndVector()

    Waveform.WaveformStartGainsVector(b, len(d["gains"]))
    for x in reversed(d["gains"]):
        b.PrependFloat32(x)
    gains = b.EndVector()

    tag_offs = [b.CreateString(t) for t in d["tags"]]
    Waveform.WaveformStartTagsVector(b, len(tag_offs))
    for o in reversed(tag_offs):
        b.PrependUOffsetTRelative(o)
    tags = b.EndVector()

    Waveform.WaveformStart(b)
    Waveform.WaveformAddChannel(b, d["channel"])
    Waveform.WaveformAddSamples(b, samples)
    Waveform.WaveformAddGains(b, gains)
    Waveform.WaveformAddTags(b, tags)
    Waveform.WaveformAddChecksum(b, d["checksum"])
    return Waveform.WaveformEnd(b)


def build_status(b, d):
    DeviceStatus.DeviceStatusStart(b)
    DeviceStatus.DeviceStatusAddDeviceId(b, d["device_id"])
    DeviceStatus.DeviceStatusAddFlags(b, d["flags"])
    DeviceStatus.DeviceStatusAddErrorCode(b, d["error_code"])
    return DeviceStatus.DeviceStatusEnd(b)


def build_telemetry(b, d):
    reading = build_sensor(b, d["reading"])
    waveform = build_waveform(b, d["waveform"])
    status = build_status(b, d["status"])

    extra_offs = [build_sensor(b, e) for e in d["extra_readings"]]
    TelemetryPacket.TelemetryPacketStartExtraReadingsVector(b, len(extra_offs))
    for o in reversed(extra_offs):
        b.PrependUOffsetTRelative(o)
    extra = b.EndVector()

    payload = b.CreateByteVector(bytes(d["payload"]))

    TelemetryPacket.TelemetryPacketStart(b)
    h = d["header"]
    TelemetryPacket.TelemetryPacketAddHeader(
        b, PacketHeader.CreatePacketHeader(b, h["seq"], h["source_addr"], h["version"]))
    TelemetryPacket.TelemetryPacketAddReading(b, reading)
    TelemetryPacket.TelemetryPacketAddWaveform(b, waveform)
    TelemetryPacket.TelemetryPacketAddStatus(b, status)
    TelemetryPacket.TelemetryPacketAddExtraReadings(b, extra)
    TelemetryPacket.TelemetryPacketAddPayload(b, payload)
    return TelemetryPacket.TelemetryPacketEnd(b)


_BUILD = {T_SENSOR: build_sensor, T_WAVEFORM: build_waveform,
          T_STATUS: build_status, T_TELEMETRY: build_telemetry}


def encode(msg_type, d):
    b = flatbuffers.Builder(256)
    b.Finish(_BUILD[msg_type](b, d))
    return bytes(b.Output())


# ---- readers (buffer -> plain dict, matching CANON shape) -----------------
def read_sensor(sr):
    return {
        "id": sr.Id(), "sensor_type": sr.SensorType(), "value": sr.Value(),
        "value_precise": sr.ValuePrecise(), "timestamp": sr.Timestamp(),
        "is_valid": sr.IsValid(), "raw_count": sr.RawCount(),
        "label": sr.Label().decode() if sr.Label() else "",
    }


def read_waveform(w):
    return {
        "channel": w.Channel(),
        "samples": [w.Samples(i) for i in range(w.SamplesLength())],
        "gains": [w.Gains(i) for i in range(w.GainsLength())],
        "tags": [w.Tags(i).decode() for i in range(w.TagsLength())],
        "checksum": w.Checksum(),
    }


def read_status(s):
    return {"device_id": s.DeviceId(), "flags": s.Flags(), "error_code": s.ErrorCode()}


def read_telemetry(t):
    h = t.Header()
    return {
        "header": {"version": h.Version(), "seq": h.Seq(), "source_addr": h.SourceAddr()},
        "reading": read_sensor(t.Reading()),
        "waveform": read_waveform(t.Waveform()),
        "status": read_status(t.Status()),
        "extra_readings": [read_sensor(t.ExtraReadings(i))
                           for i in range(t.ExtraReadingsLength())],
        "payload": bytes(t.Payload(i) for i in range(t.PayloadLength())),
    }


def decode(msg_type, buf):
    if msg_type == T_SENSOR:
        return read_sensor(SensorReading.SensorReading.GetRootAs(buf, 0))
    if msg_type == T_WAVEFORM:
        return read_waveform(Waveform.Waveform.GetRootAs(buf, 0))
    if msg_type == T_STATUS:
        return read_status(DeviceStatus.DeviceStatus.GetRootAs(buf, 0))
    if msg_type == T_TELEMETRY:
        return read_telemetry(TelemetryPacket.TelemetryPacket.GetRootAs(buf, 0))
    raise ValueError(f"unknown msg_type {msg_type}")


NAMES = {T_SENSOR: "SensorReading", T_WAVEFORM: "Waveform",
         T_STATUS: "DeviceStatus", T_TELEMETRY: "TelemetryPacket"}
