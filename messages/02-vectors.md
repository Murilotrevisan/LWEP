# 02 — `Waveform` (vectors / fixed-max arrays)

**Purpose:** exercise repeated fields (vectors) of scalars and of strings, with
**bounded** capacities so the embedded C side needs no dynamic allocation.

**Message type id:** `2`

## Fields

| field      | logical type      | capacity                          |
|------------|-------------------|-----------------------------------|
| `channel`  | `uint8`           | 0..255                            |
| `samples`  | `int16[]`         | up to **64** elements             |
| `gains`    | `float[]`         | up to **4** elements              |
| `tags`     | `string[]`        | up to **8** strings, each ≤ **12** bytes |
| `checksum` | `uint32`          | producer-computed over `samples`  |

## Protobuf mapping (`lwep.proto`)

```proto
message Waveform {
  uint32          channel  = 1;   // logical uint8
  repeated sint32 samples  = 2;   // logical int16; sint32 zig-zags negatives
  repeated float  gains    = 3;
  repeated string tags     = 4;
  uint32          checksum = 5;
}
```

> `sint32` (zig-zag) is used for `samples` because they are signed and often
> small-magnitude; it encodes negatives compactly. The logical width is `int16`.

### nanopb options (`lwep.options`)

```
Waveform.channel   int_size:IS_8
Waveform.samples   int_size:IS_16   max_count:64
Waveform.gains     max_count:4
Waveform.tags      max_count:8      max_size:12
Waveform.checksum  int_size:IS_32
```

Result on the C side: `int16_t samples[64]; pb_size_t samples_count;` — a plain
fixed array plus a count, no heap. Same for `gains`, and `char tags[8][12];`.

## FlatBuffers mapping (`lwep.fbs`)

```fbs
table Waveform {
  channel:  ubyte;
  samples:  [short];
  gains:    [float];
  tags:     [string];
  checksum: uint;
}
```

FlatBuffers vectors are read zero-copy. The *producer* is responsible for
respecting the documented caps (64/4/8×12); the FlatCC builder writes them into a
buffer the caller sizes.

## Canonical test values

```
channel  = 3
samples  = [0, 100, -100, 32767, -32768, 5, 6, 7, 8, 9]   (10 of max 64)
gains    = [1.0, 0.5, 0.25, 2.0]                          (4 of max 4)
tags     = ["ch3", "raw", "v2"]                           (3 of max 8)
checksum = 0xDEADBEEF
```
