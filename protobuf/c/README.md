# protobuf/c — nanopb (embedded C, no malloc)

The C++ harness ([`main.cpp`](main.cpp)) links the **generated C** bindings
(`lwep.pb.c`) and the **nanopb runtime** to encode/decode the four catalog
messages with only stack/static buffers.

## Prerequisites

| tool           | install                                                            |
|----------------|--------------------------------------------------------------------|
| `protoc`       | `pacman -S mingw-w64-ucrt-x86_64-protobuf` (or a protobuf release)  |
| `python`       | to run the nanopb generator (no `pip install nanopb` needed)        |
| nanopb source  | git submodule `../../third_party/nanopb` @ `nanopb-0.4.9.1` (generator **and** runtime `pb_*.c`); `git submodule update --init` or run `tools/setup-generators.ps1` |
| `g++` + `make` | Windows: [MSYS2](https://www.msys2.org/) UCRT64 (`pacman -S mingw-w64-ucrt-x86_64-gcc make`) |

## Generate + build

```sh
make generate     # -> lwep.pb.c, lwep.pb.h (from ../schema/lwep.proto + lwep.options)
make              # -> main.exe (main on Linux/macOS)
```

`NANOPB_DIR` defaults to `../../third_party/nanopb`; override it (`make
NANOPB_DIR=/path/to/nanopb`) if your checkout lives elsewhere. The same tree
supplies both the generator (`generator/nanopb_generator.py`) and the runtime
sources the Makefile compiles.

## Run (interop)

```sh
# this C++ side as server, Python client connects:
./main server 9001
python ../python/client.py 127.0.0.1 9001

# or this C++ side as client against the Python server:
python ../python/server.py 9001
./main client 127.0.0.1 9001
```

The client prints `PASS`/`FAIL` per message and exits non-zero on any mismatch.

## No-dynamic-allocation note

Because [`../schema/lwep.options`](../schema/lwep.options) pins every string /
bytes / repeated field to a fixed maximum, nanopb emits plain fixed arrays (e.g.
`int16_t samples[64]; char label[16];`). The harness never calls `malloc`/`new`
for messages — all buffers are `static` or stack. This is what makes the schema
usable on a microcontroller.
