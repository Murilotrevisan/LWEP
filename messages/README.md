# LWEP Message Catalog

This folder is the **neutral, human-readable specification** of the messages our
Light Weight Embedded Protocol needs to move across the wire. It is intentionally
IDL-agnostic: it describes *what* each message contains, then shows how that maps
onto both candidate schema languages (Protocol Buffers and FlatBuffers).

The actual machine-readable schemas live next to their generators:

| Message concept        | Protobuf / nanopb                     | FlatBuffers / FlatCC          |
|------------------------|---------------------------------------|-------------------------------|
| Schema file (versioned)| [`protobuf/schema/lwep.proto`](../protobuf/schema/lwep.proto) + [`lwep.options`](../protobuf/schema/lwep.options) | [`flatbuffers/schema/lwep.fbs`](../flatbuffers/schema/lwep.fbs) |

> Only these schema files (and the hand-written harness code) are version
> controlled. All *generated* bindings are git-ignored — see [`.gitignore`](../.gitignore).

## The four messages

Each message is designed to exercise a specific protocol feature. Read them in
order:

1. [`01-scalars.md`](01-scalars.md) — **`SensorReading`**: every scalar data type.
2. [`02-vectors.md`](02-vectors.md) — **`Waveform`**: repeated fields / fixed-max arrays.
3. [`03-bitfields.md`](03-bitfields.md) — **`DeviceStatus`**: flags packed into a `uint32`.
4. [`04-nested-all.md`](04-nested-all.md) — **`TelemetryPacket`**: everything nested together.

## Cross-cutting conventions

### Logical integer widths

Protocol Buffers has **no 8- or 16-bit integer types** — its varint scalars are
`int32 / int64 / uint32 / uint64` (plus `sint`, `fixed`, `sfixed`). FlatBuffers
*does* have `byte/ubyte/short/ushort`. To keep one neutral contract:

- The catalog states the **logical width** (e.g. `uint16`).
- In `.proto` we use the smallest varint type that fits (`uint32`) and rely on the
  documented logical range. On the C/microcontroller side the nanopb field can be
  narrowed with the `int_size` option (e.g. `IS_16`) so it lands in a `uint16_t`.
- In `.fbs` we use the exact-width type (`ushort`).

### No dynamic memory on the embedded side

Every variable-length field (`string`, `bytes`, `repeated`/vector) has a **fixed
maximum size** declared in the catalog. For nanopb these caps are pinned in
`lwep.options` (`max_size`, `max_count`) so the generated C structs use plain
fixed arrays — **no `malloc`**. FlatBuffers' read path is zero-copy by
construction; its C build path (FlatCC) can use a static allocator on an MCU.

### Bitfields

Neither IDL has native bitfields. Where the protocol logically needs packed bits
we define a single unsigned integer plus a documented bit layout, and the
harnesses pack/unpack with shifts and masks. See [`03-bitfields.md`](03-bitfields.md).

### Wire framing

Messages are length-prefixed and tagged with a type id on the wire. That framing
(shared by every language/stack) is specified in
[`../common/framing.md`](../common/framing.md).
