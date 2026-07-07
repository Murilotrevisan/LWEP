# flatbuffers/c — FlatCC (embedded C, zero-copy reads)

The C++ harness ([`main.cpp`](main.cpp)) links the **generated C** headers and the
**FlatCC runtime** to encode/decode the four catalog messages. The **read path is
zero-copy and allocation-free** — readers index directly into the received buffer.

## Prerequisites

| tool               | install                                                        |
|--------------------|----------------------------------------------------------------|
| `flatcc` + runtime | git submodule `../../third_party/flatcc` @ `v0.6.1`; `tools/setup-generators.ps1` builds it (`bin/flatcc.exe`, `include/`, `lib/libflatccrt.a`) with gcc — no CMake needed |
| `g++` + `make`     | Windows: [MSYS2](https://www.msys2.org/) UCRT64 (`pacman -S mingw-w64-ucrt-x86_64-gcc make`) |

## Generate + build

```sh
make generate     # -> lwep_reader.h / lwep_builder.h / lwep_verifier.h (from ../schema/lwep.fbs)
make              # -> main.exe (main on Linux/macOS)
```

`FLATCC_DIR` defaults to `../../third_party/flatcc`; override it (`make
FLATCC_DIR=/path/to/flatcc`) if yours lives elsewhere.

## Run (interop)

```sh
# this C++ side as server:
./main server 9001
python ../python/client.py 127.0.0.1 9001

# or this C++ side as client:
python ../python/server.py 9001
./main client 127.0.0.1 9001
```

## Allocation notes

- **Reading** (server decode + client echo-verify): zero-copy, no `malloc`.
- **Building** (client encode): uses the default `flatcc_builder`, which allocates
  emitter pages via `malloc`. On a microcontroller you initialize the builder with
  a **custom emitter/allocator backed by a static buffer** — the `_add` / `_create`
  / `_push` field calls in `main.cpp` stay identical. The output is copied into a
  fixed `static` frame buffer via `flatcc_builder_copy_buffer`.
- The C++ FlatCC **server echoes the verified buffer unchanged** (already a valid
  FlatBuffer) to keep the embedded side minimal; the Python flatbuffers server
  demonstrates a full decode→re-encode round trip.

> Function names here follow flatcc's generated API for schema namespace `lwep`.
> If your flatcc version names things differently, adjust `main.cpp` accordingly.
