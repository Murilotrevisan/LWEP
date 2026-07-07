# 04 — `TelemetryPacket` (everything nested)

**Purpose:** the stress message. It nests all previous messages plus a nested
**vector of messages**, a fixed **struct-like header**, and a raw **bytes**
payload — the realistic "one packet that carries a full telemetry frame".

**Message type id:** `4`

## Fields

| field            | logical type              | notes                                  |
|------------------|---------------------------|----------------------------------------|
| `header`         | nested `PacketHeader`     | fixed-size preamble                    |
| `reading`        | nested `SensorReading`    | see [01](01-scalars.md)                |
| `waveform`       | nested `Waveform`         | see [02](02-vectors.md)                |
| `status`         | nested `DeviceStatus`     | see [03](03-bitfields.md)              |
| `extra_readings` | `SensorReading[]`         | up to **4** — nested vector of messages|
| `payload`        | `bytes`                   | up to **32** raw bytes                 |

### `PacketHeader`

| field         | logical type | notes                    |
|---------------|--------------|--------------------------|
| `version`     | `uint8`      | protocol version         |
| `seq`         | `uint32`     | monotonic sequence no.   |
| `source_addr` | `uint16`     | originating node address |

## Protobuf mapping (`lwep.proto`)

```proto
message PacketHeader {
  uint32 version     = 1;   // logical uint8
  uint32 seq         = 2;
  uint32 source_addr = 3;   // logical uint16
}

message TelemetryPacket {
  PacketHeader           header         = 1;
  SensorReading          reading        = 2;
  Waveform               waveform       = 3;
  DeviceStatus           status         = 4;
  repeated SensorReading extra_readings = 5;
  bytes                  payload        = 6;
}
```

### nanopb options (`lwep.options`)

```
PacketHeader.version         int_size:IS_8
PacketHeader.source_addr     int_size:IS_16
TelemetryPacket.extra_readings max_count:4
TelemetryPacket.payload        max_size:32
```

Because `header`/`reading`/`waveform`/`status` are sub-messages whose own fields
are all statically bounded, and `extra_readings`/`payload` are capped here, the
entire `TelemetryPacket` C struct is a fixed-size nested aggregate — still no heap.

## FlatBuffers mapping (`lwep.fbs`)

```fbs
// fields ordered largest-alignment-first (uint, ushort, ubyte) => no padding
struct PacketHeader {   // struct = fixed inline layout, ideal for a preamble
  seq:         uint;
  source_addr: ushort;
  version:     ubyte;
}

table TelemetryPacket {
  header:         PacketHeader;   // inline struct
  reading:        SensorReading;
  waveform:       Waveform;
  status:         DeviceStatus;
  extra_readings: [SensorReading];
  payload:        [ubyte];
}
```

> Field order inside `PacketHeader` is arranged largest-alignment-first
> (`uint` then `ushort` then `ubyte`) so the FlatBuffers struct has no internal
> padding surprises across compilers.

## Canonical test values

```
header = { version=2, seq=42, source_addr=0x00A5 }
reading  = <canonical SensorReading from 01-scalars.md>
waveform = <canonical Waveform from 02-vectors.md>
status   = <canonical DeviceStatus from 03-bitfields.md>
extra_readings = [
  { id=1, sensor_type=PRESSURE, value=101.3,  value_precise=101.325, timestamp=1720224000001, is_valid=true,  raw_count=2048,  label="baro" },
  { id=2, sensor_type=HUMIDITY, value=45.0,   value_precise=45.0,    timestamp=1720224000002, is_valid=false, raw_count=0,     label="rh"   },
]
payload = bytes [0x01 0x02 0x03 0x04 0xFF 0xFE 0xFD 0x00]   (8 of max 32)
```
