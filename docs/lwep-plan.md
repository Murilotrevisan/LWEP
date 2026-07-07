# LWEP Lab — Protobuf/nanopb & FlatBuffers/FlatCC Interop Testbed

## Context

This repo (`LWEP` — Light Weight Embedded Protocols) evaluates serialization IDLs
for embedded↔host communication, where the embedded side is C/C++ on a
microcontroller **without dynamic memory allocation**, and the host side is Python
(and Java as a reference target).

The two candidate stacks are:

| IDL family   | Host (Java / Python) | Embedded (C, no malloc) | Neutral schema file |
|--------------|----------------------|-------------------------|---------------------|
| Protocol Buffers | `protobuf` runtime | **nanopb**            | `lwep.proto` (+ `lwep.options`) |
| FlatBuffers      | `flatbuffers` runtime | **FlatCC**          | `lwep.fbs`          |

**Key requirement satisfied naturally:** each pair generates from *one* neutral
schema. nanopb consumes the same `.proto` as protobuf (a sibling `.options` file
pins static array/string sizes so no malloc is needed). FlatCC consumes the same
`.fbs` as FlatBuffers, and its read path is zero-copy / allocation-free by design.
Only the neutral files (`.proto`, `.options`, `.fbs`) plus hand-written harness
code are version-controlled; all generated code is git-ignored.

**Goal:** define a catalog of representative protocol messages (scalars, vectors,
bitfields, and a fully-nested message), generate bindings for each stack, and run
a Python↔C round-trip tester over TCP to prove real-life interop and the
no-dynamic-allocation constraint on the C side.

## Decisions (confirmed with user)

- **Transport:** TCP over localhost, frame `[uint32 len][uint8 msg_type][payload]`.
- **C side:** harness in **C++ (`.cpp`)**, compiled with `g++`, linking the
  generated **C** code and the nanopb / flatcc **C** runtimes.
- **Build:** a **Makefile** per C project (host needs `g++` + `make`; Windows: MSYS2/MinGW).
- **Java:** generated from the same schema + one minimal example; not in the live tester.
- **Generators (nanopb, flatcc, protoc, flatc):** installation documented; generation via scripts.

## Repository Layout

```
LWEP/
├─ README.md                     # overview + quickstart matrix
├─ .gitignore                    # ignores all generated code + build artifacts
├─ docs/lwep-plan.md             # this plan
├─ messages/                     # neutral, human-readable message catalog
│  ├─ README.md  01-scalars.md  02-vectors.md  03-bitfields.md  04-nested-all.md
├─ common/framing.md             # the [len][type][payload] wire frame + msg_type ids
├─ protobuf/
│  ├─ schema/  lwep.proto  lwep.options        # ★ versioned neutral schema
│  ├─ python/  server.py client.py generate.ps1
│  ├─ c/       main.cpp Makefile generate.ps1 README.md   (nanopb)
│  └─ java/    README.md Example.java
└─ flatbuffers/
   ├─ schema/  lwep.fbs                          # ★ versioned neutral schema
   ├─ python/  server.py client.py lwepfb.py generate.ps1
   ├─ c/       main.cpp Makefile generate.ps1 README.md   (FlatCC)
   └─ java/    README.md Example.java
```

## Message Catalog

1. **`SensorReading`** — scalar data types: `id:uint16`, `sensor_type:enum`,
   `value:float`, `value_precise:double`, `timestamp:uint64`, `is_valid:bool`,
   `raw_count:int32`, `label:string(16)`.
2. **`Waveform`** — vectors: `channel:uint8`, `samples:int16[64]`, `gains:float[4]`,
   `tags:string[8×12]`, `checksum:uint32`.
3. **`DeviceStatus`** — bitfields: `device_id:uint16`, `flags:uint32` (documented bit
   layout: POWER_ON, FAULT, CALIBRATED, OVERHEAT, MODE[4-7], BATTERY_PCT[8-15]),
   `error_code:uint8`.
4. **`TelemetryPacket`** — nested: `header{version,seq,source_addr}`, `reading`,
   `waveform`, `status`, `extra_readings:SensorReading[4]`, `payload:bytes[32]`.

## Schema Authoring Notes

- **proto3** lacks 8/16-bit ints → use `uint32`/`int32`, narrow on the C side via
  nanopb `int_size` in `lwep.options`; that file also pins `max_size`/`max_count`
  so nanopb emits fixed arrays (no malloc).
- **`.fbs`** uses exact-width scalars, a `struct` for the fixed `PacketHeader`
  (fields ordered largest-first → no padding), and `table`s elsewhere. No
  `root_type` so all four tables are usable as independent roots.

## Harnesses & Tester

- Framing mirrored in code; `msg_type` 1..4.
- Each stack: server + client in both Python and C++ → any cross-language pairing.
- Client builds the four canonical messages, sends each framed, receives echo,
  asserts field-level equality (non-zero exit on mismatch). Server decodes, prints,
  echoes. Protobuf and Python-flatbuffers servers fully re-encode; the C++ FlatCC
  server echoes the verified buffer unchanged (embedded side kept minimal).
- C++ harness: Winsock/BSD guarded by `#ifdef _WIN32`; only stack/static buffers.

## Generation & Build

- `generate.ps1` per target: `protoc --python_out` / `nanopb_generator` /
  `protoc --java_out` / `flatc --python` / `flatcc -a` / `flatc --java`.
- Makefiles (`protobuf/c`, `flatbuffers/c`): `generate`, build (`g++`), `clean`;
  `NANOPB_DIR` / `FLATCC_DIR` point at the runtime sources.

## Verification (end-to-end)

1. Run each `generate.ps1`; confirm generated files appear, no errors.
2. Python baseline: server + client for each stack → `ALL PASS`.
3. `make -C protobuf/c` and `make -C flatbuffers/c` compile cleanly.
4. Cross-language interop both directions (Py↔C++) for both stacks.
5. No-malloc check: nanopb structs use fixed arrays; C++ harness uses only
   stack/static buffers (FlatCC build path documented for MCU static allocator).
6. Java smoke: encode a `SensorReading` in Java, decode in Python.
