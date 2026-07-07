# 03 — `DeviceStatus` (bitfields)

**Purpose:** exercise packed bit flags. Neither Protobuf nor FlatBuffers has a
native bitfield type, so we define a single unsigned integer (`flags:uint32`) with
a **documented bit layout** and pack/unpack with shifts and masks in every
harness. This mirrors what real embedded firmware does with a `uint32_t` register.

**Message type id:** `3`

## Fields

| field       | logical type | notes                         |
|-------------|--------------|-------------------------------|
| `device_id` | `uint16`     |                               |
| `flags`     | `uint32`     | packed bitfield, layout below |
| `error_code`| `uint8`      | 0 = no error                  |

## `flags` bit layout

Bit 0 is the least-significant bit.

| bits   | width | name          | meaning                                  |
|--------|-------|---------------|------------------------------------------|
| 0      | 1     | `POWER_ON`    | 1 = powered                              |
| 1      | 1     | `FAULT`       | 1 = fault latched                        |
| 2      | 1     | `CALIBRATED`  | 1 = calibration valid                    |
| 3      | 1     | `OVERHEAT`    | 1 = thermal warning                      |
| 4–7    | 4     | `MODE`        | operating mode, 0..15                    |
| 8–15   | 8     | `BATTERY_PCT` | battery percentage, 0..100               |
| 16–31  | 16    | *reserved*    | must be 0                                |

### Pack / unpack reference

```
POWER_ON     = flags        & 0x1
FAULT        = (flags >> 1)  & 0x1
CALIBRATED   = (flags >> 2)  & 0x1
OVERHEAT     = (flags >> 3)  & 0x1
MODE         = (flags >> 4)  & 0xF
BATTERY_PCT  = (flags >> 8)  & 0xFF

flags = (POWER_ON    & 0x1)  << 0
      | (FAULT       & 0x1)  << 1
      | (CALIBRATED  & 0x1)  << 2
      | (OVERHEAT    & 0x1)  << 3
      | (MODE        & 0xF)  << 4
      | (BATTERY_PCT & 0xFF) << 8
```

## Protobuf mapping (`lwep.proto`)

```proto
message DeviceStatus {
  uint32 device_id  = 1;   // logical uint16
  uint32 flags      = 2;   // packed bitfield, see layout
  uint32 error_code = 3;   // logical uint8
}
```

### nanopb options (`lwep.options`)

```
DeviceStatus.device_id  int_size:IS_16
DeviceStatus.flags      int_size:IS_32
DeviceStatus.error_code int_size:IS_8
```

## FlatBuffers mapping (`lwep.fbs`)

```fbs
table DeviceStatus {
  device_id:  ushort;
  flags:      uint;    // packed bitfield, see layout
  error_code: ubyte;
}
```

## Canonical test values

```
device_id  = 0x2A2A (10794)
error_code = 0

flags fields:
  POWER_ON    = 1
  FAULT       = 0
  CALIBRATED  = 1
  OVERHEAT    = 0
  MODE        = 6        (0..15)
  BATTERY_PCT = 87       (0..100)

=> flags = 1<<0 | 1<<2 | 6<<4 | 87<<8
         = 0x01 | 0x04 | 0x60 | 0x5700
         = 0x5765   (22373)
```
