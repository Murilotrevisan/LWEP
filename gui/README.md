# LWEP Interop GUI (Tkinter)

A small Tkinter app to **validate that the serialized bytes are coherent between
Python and the generated C code**, for both stacks:

- **Protobuf / nanopb**
- **FlatBuffers / FlatCC**

You stay on the Python side. The GUI **auto-spawns the C harness**
(`protobuf/c/main.exe` or `flatbuffers/c/main.exe`) as the opposite peer and shows
its stdout, so you can see the C side decode/validate exactly what Python produced
(and vice-versa).

## Run

```powershell
# from the repo root
powershell -File run-gui.ps1
#   or directly:
C:\msys64\ucrt64\bin\python.exe gui\app.py
```

> Use the **MSYS2 UCRT64** Python (`C:\msys64\ucrt64\bin\python.exe`): it has
> `tkinter`, `flatbuffers` and `protobuf`. The bare `python` on PATH is the broken
> Microsoft Store stub. The C `main.exe` binaries must be built (they already are;
> rebuild with `make -C flatbuffers/c` / `make -C protobuf/c` if needed).

## What each role does

Pick an **IDL** and a **role** at the top, plus host/port (default `127.0.0.1:9001`).

| Role     | Python does                                        | Auto-spawned C peer                         | TCP        |
|----------|----------------------------------------------------|---------------------------------------------|------------|
| **server** | edits a message → serializes → **sends** → shows the echo round-trip | `main server` (decodes, **re-encodes**, echoes) | Python connects as client |
| **client** | **listens** → receives → parses/displays → echoes back | `main client` (encodes the 4 canonical msgs) | Python listens as server |

The naming follows *who produces vs. consumes the data* (server serves/produces,
client receives), which is the opposite of the underlying TCP roles — handled
automatically.

### server mode (editor)
1. Choose a message. `SensorReading` and `DeviceStatus` are fully **editable**;
   `Waveform` and `TelemetryPacket` are sent from their canonical values (vector/
   nested editing is a future addition).
2. Click **Serializar & Enviar**. Panels show:
   - **Serialização (Python)** — payload length, hexdump, field dump.
   - **Echo re-parseado** — PASS/FAIL of the Python→C→Python round-trip.
   - **Saída do C (stdout)** — the C server's own decode dump (proof it read your bytes).
3. Keep editing and sending on the same session; **Encerrar sessão** closes it
   (the C server then prints `done, echoed N`).

### client mode (receiver)
1. Click **Escutar & Receber**. The C `main client` is spawned and sends the four
   canonical messages. Panels show:
   - **Mensagens recebidas + parse (Python)** — per message: hexdump + parsed fields.
   - **Saída do C (stdout)** — the C client's `PASS` / `ALL PASS`.
2. **Parar** stops the listener.

## Modules

| File | Responsibility |
|------|----------------|
| `wire.py`        | `[len][type][payload]` framing (mirrors `common/framing.md`) + hexdump |
| `lwep_codecs.py` | IDL-neutral dicts, `CANON`, `FIELD_SCHEMA`, `PbCodec`, `FbCodec` |
| `forms.py`       | schema-driven editable form + validation |
| `cpeer.py`       | spawns/drives the C `main.exe`, captures stdout |
| `app.py`         | the Tkinter application |
| `tests/interop_test.py` | headless interop suite (the DoD gate) |

## Tests (Definition of Done)

```powershell
powershell -File run-tests.ps1
```

Rebuilds the FlatBuffers C harness and runs `gui/tests/interop_test.py`:
**2 IDLs × 4 messages × (unit + Python→C + C→Python)**. Delivery is considered
done only on `ALL PASS` (exit 0).
