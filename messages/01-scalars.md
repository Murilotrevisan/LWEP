# 01 — `SensorReading` (scalar data types)

**Purpose:** exercise every scalar data type the protocol needs. This is the
baseline "does a plain flat record round-trip across languages" message.

**Message type id:** `1`

## Fields

| field           | logical type | range / notes                          |
|-----------------|--------------|----------------------------------------|
| `id`            | `uint16`     | device/reading id, 0..65535            |
| `sensor_type`   | `enum`       | `UNKNOWN=0, TEMPERATURE=1, PRESSURE=2, HUMIDITY=3, VOLTAGE=4` |
| `value`         | `float`      | 32-bit IEEE-754                        |
| `value_precise` | `double`     | 64-bit IEEE-754                        |
| `timestamp`     | `uint64`     | epoch milliseconds                     |
| `is_valid`      | `bool`       |                                        |
| `raw_count`     | `int32`      | signed ADC count                       |
| `label`         | `string`     | max **16** bytes (incl. no NUL needed) |

## Protobuf mapping (`lwep.proto`)

```proto
enum SensorType {
  SENSOR_UNKNOWN = 0;
  TEMPERATURE    = 1;
  PRESSURE       = 2;
  HUMIDITY       = 3;
  VOLTAGE        = 4;
}

message SensorReading {
  uint32     id            = 1;   // logical uint16
  SensorType sensor_type   = 2;
  float      value         = 3;
  double     value_precise = 4;
  uint64     timestamp     = 5;
  bool       is_valid      = 6;
  int32      raw_count     = 7;
  string     label         = 8;
}
```

### nanopb options (`lwep.options`)

```
SensorReading.id     int_size:IS_16
SensorReading.label  max_size:16
```

`int_size:IS_16` makes nanopb emit `uint16_t id;`. `max_size:16` makes `label` a
fixed `char label[16];` — no heap.

## FlatBuffers mapping (`lwep.fbs`)

```fbs
enum SensorType : byte { UNKNOWN = 0, TEMPERATURE, PRESSURE, HUMIDITY, VOLTAGE }

table SensorReading {
  id:            ushort;
  sensor_type:   SensorType;
  value:         float;
  value_precise: double;
  timestamp:     ulong;
  is_valid:      bool;
  raw_count:     int;
  label:         string;   // FlatCC reader is zero-copy; length capped by producer
}
```

## Canonical test values

Used by every client so round-trips are comparable across stacks:

```
id            = 4097          (0x1001)
sensor_type   = TEMPERATURE
value         = 23.5
value_precise = 23.481523
timestamp     = 1720224000000
is_valid      = true
raw_count     = -12345
label         = "cabin-temp"
```
