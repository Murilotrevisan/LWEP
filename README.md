# LWEP — Light Weight Embedded Protocols lab

A testbed for evaluating serialization IDLs for **embedded ↔ host** communication.
The embedded side is C/C++ on a microcontroller that **cannot use dynamic memory
allocation**; the host side is Python (with Java as a reference target).

Two candidate stacks are compared, each driven by a **single neutral schema file**
that is the only thing under version control for that stack:

| Stack | Host (Python / Java) | Embedded C (no malloc) | Neutral schema (versioned) |
|-------|----------------------|------------------------|----------------------------|
| Protocol Buffers | `protobuf` | **nanopb** | [`protobuf/schema/lwep.proto`](protobuf/schema/lwep.proto) + [`lwep.options`](protobuf/schema/lwep.options) |
| FlatBuffers      | `flatbuffers` | **FlatCC** | [`flatbuffers/schema/lwep.fbs`](flatbuffers/schema/lwep.fbs) |

nanopb reads the *same* `.proto` as protobuf (the sibling `.options` pins static
sizes → fixed C arrays, no heap). FlatCC reads the *same* `.fbs` as FlatBuffers
and decodes zero-copy. **All generated code is git-ignored** — see [`.gitignore`](.gitignore).

## Layout

```
messages/       neutral, human-readable message catalog (start here)
common/         wire framing spec shared by every language
protobuf/       schema/ + python/ + c/ (nanopb) + java/
flatbuffers/    schema/ + python/ + c/ (FlatCC) + java/
docs/           saved implementation plan
```

## The messages

Four messages, each exercising a protocol feature (full catalog in
[`messages/`](messages/README.md)):

1. **SensorReading** — every scalar data type
2. **Waveform** — vectors / fixed-max arrays
3. **DeviceStatus** — bitfields packed into a `uint32`
4. **TelemetryPacket** — all of the above nested together (+ nested vector + bytes)

Messages travel over TCP wrapped in a tiny `[uint32 len][uint8 type][payload]`
frame — see [`common/framing.md`](common/framing.md).

## Prerequisites

Toolchain used/validated: **MSYS2 UCRT64** on Windows 11 with `g++`/`gcc` 15.2,
`make`, `protoc` 35.1, `flatc` 25.12, Python 3.14 (`python-protobuf`,
`python-flatbuffers`), JDK 17. Install the host tools with pacman:

```sh
pacman -S --needed make \
  mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-protobuf \
  mingw-w64-ucrt-x86_64-flatbuffers mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-python-protobuf mingw-w64-ucrt-x86_64-python-flatbuffers
```

The two **C code generators** are pinned as **git submodules** under
`third_party/` (see [`.gitmodules`](.gitmodules)) so every checkout uses the exact
same IDL/generator version:

| submodule            | pinned release   | provides                              |
|----------------------|------------------|---------------------------------------|
| `third_party/nanopb` | `nanopb-0.4.9.1` | generator script + runtime `pb_*.c`    |
| `third_party/flatcc` | `v0.6.1`         | schema compiler + `libflatccrt`        |

Clone with submodules, then run the setup script (needs `git`, `gcc`, `ar` — no
CMake or `pip install`):

```sh
git clone --recurse-submodules https://github.com/Murilotrevisan/LWEP.git
# (already cloned? git submodule update --init --recursive)
powershell -ExecutionPolicy Bypass -File tools/setup-generators.ps1
```

The setup script updates the submodules to their pinned commits and **builds**
flatcc (`bin/flatcc.exe` + `lib/libflatccrt.a`) with gcc. To bump a generator
version later, move the submodule to a new tag and commit the new pointer — that
is the single place the version changes for everyone.

> Schemas are kept **ASCII-only** (some generator versions, e.g. flatcc 0.6.1,
> reject non-ASCII characters in schema comments).

## Quickstart — Python ↔ Python baseline

```sh
# Protobuf
cd protobuf/python && ./generate.ps1          # -> lwep_pb2.py
python server.py 9001 &                         # terminal A
python client.py 127.0.0.1 9001                 # terminal B -> ALL PASS

# FlatBuffers
cd flatbuffers/python && ./generate.ps1        # -> lwep/ package
python server.py 9002 &
python client.py 127.0.0.1 9002                 # -> ALL PASS
```

## The real test — cross-language interop matrix

Each stack ships a **server and a client in both Python and C++**, so any pairing
works. The client sends all four messages and asserts field-level round-trip
equality; the server prints a decoded dump of what it received.

| Direction | Protobuf / nanopb | FlatBuffers / FlatCC |
|-----------|-------------------|----------------------|
| Python server ↔ C++ client | `python protobuf/python/server.py 9001` + `protobuf/c/main client 127.0.0.1 9001` | `python flatbuffers/python/server.py 9002` + `flatbuffers/c/main client 127.0.0.1 9002` |
| C++ server ↔ Python client | `protobuf/c/main server 9001` + `python protobuf/python/client.py 127.0.0.1 9001` | `flatbuffers/c/main server 9002` + `python flatbuffers/python/client.py 127.0.0.1 9002` |

Build the C++ side first (after running the setup script above; the Makefiles
default `NANOPB_DIR`/`FLATCC_DIR` to `third_party/`):

```sh
make -C protobuf/c    generate && make -C protobuf/c
make -C flatbuffers/c generate && make -C flatbuffers/c
```

> Tip for running a server + client from one shell: start the server in the
> background, wait until its log prints `listening`, then run the client — don't
> "probe" the port by connecting, since the servers accept exactly one connection.

## Java (reference only)

Java is generated from the same schemas as a cross-language smoke check, not part
of the live tester. See [`protobuf/java/`](protobuf/java/README.md) and
[`flatbuffers/java/`](flatbuffers/java/README.md).
