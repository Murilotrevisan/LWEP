"""Spawn and drive the generated C harness (protobuf/c/main.exe or
flatbuffers/c/main.exe) so the GUI/tests can validate cross-language coherence.

The C binary's stdout (its decode dump / PASS lines) is captured on a background
thread into a queue — that captured text is the visual proof that the C side read
the bytes Python produced (and vice-versa).

Roles map to the existing C CLI (`main {server <port> | client <host> <port>}`):
  * GUI 'server' (Python encodes) -> C `main server`  (C decodes + echoes)
  * GUI 'client' (Python decodes) -> C `main client`  (C encodes the 4 canonical)
"""
import os
import queue
import subprocess
import sys
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# The C exes are built with the MSYS2 UCRT64 toolchain and need its bin/ on PATH
# for the runtime DLLs. We run under that same interpreter, so derive it from
# sys.executable (…\ucrt64\bin\python.exe) and fall back to the default location.
_UCRT_BIN = os.path.dirname(sys.executable)
if os.path.basename(_UCRT_BIN).lower() != "bin":
    _UCRT_BIN = r"C:\msys64\ucrt64\bin"

_IDL_DIR = {"protobuf": "protobuf", "flatbuffer": "flatbuffers"}


def exe_path(idl):
    """Absolute path to the built C harness for an IDL ('protobuf'/'flatbuffer')."""
    folder = _IDL_DIR.get(idl)
    if folder is None:
        raise ValueError(f"unknown idl {idl!r}")
    name = "main.exe" if os.name == "nt" else "main"
    return os.path.join(_ROOT, folder, "c", name)


class CPeer:
    """A running (or runnable) C harness process with captured stdout."""

    def __init__(self, idl, role, host="127.0.0.1", port=9001):
        if role not in ("server", "client"):
            raise ValueError("role must be 'server' or 'client'")
        self.idl, self.role, self.host, self.port = idl, role, host, port
        self.exe = exe_path(idl)
        self.lines = queue.Queue()
        self.proc = None
        self._reader = None

    def command(self):
        if self.role == "server":
            return [self.exe, "server", str(self.port)]
        return [self.exe, "client", self.host, str(self.port)]

    def start(self):
        if not os.path.exists(self.exe):
            raise FileNotFoundError(
                f"C harness not built: {self.exe}\nRun: make -C {self._make_dir()}")
        env = os.environ.copy()
        env["PATH"] = _UCRT_BIN + os.pathsep + env.get("PATH", "")
        # CREATE_NO_WINDOW keeps a console exe from flashing a window under the GUI.
        flags = 0x08000000 if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            self.command(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=os.path.dirname(self.exe), env=env, creationflags=flags)
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()
        return self

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self.lines.put(line.rstrip("\r\n"))
        finally:
            try:
                self.proc.stdout.close()
            except Exception:
                pass

    def drain(self):
        """Return all stdout lines captured so far (non-blocking)."""
        out = []
        while True:
            try:
                out.append(self.lines.get_nowait())
            except queue.Empty:
                break
        return out

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def wait(self, timeout=None):
        """Wait for exit; return the process return code (or None on timeout)."""
        if self.proc is None:
            return None
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def finish(self, timeout=5):
        """Wait for exit, drain the reader thread, return (returncode, all_lines)."""
        rc = self.wait(timeout)
        if self._reader:
            self._reader.join(timeout=1)
        return rc, self.drain()

    def stop(self):
        """Terminate the process if it is still running, then join the reader."""
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self._reader:
            self._reader.join(timeout=1)

    def _make_dir(self):
        return f"{_IDL_DIR[self.idl]}/c"
