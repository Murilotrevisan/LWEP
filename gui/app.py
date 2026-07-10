#!/usr/bin/env python3
"""LWEP Interop GUI (Tkinter).

Pick an IDL (Protobuf/nanopb or FlatBuffers/FlatCC) and a role, then validate that
the bytes are coherent across languages against the generated C harness, which the
GUI spawns automatically:

  * server  -> Python EDITS a message, serializes it, sends it, and shows the echo
               round-trip. The C `main server` (auto-spawned) decodes + re-encodes.
  * client  -> Python RECEIVES the messages the C `main client` (auto-spawned) sends
               and shows how each was parsed, echoing them back.

Run with the MSYS2 UCRT64 interpreter (has tkinter + flatbuffers + protobuf):
  C:\\msys64\\ucrt64\\bin\\python.exe gui\\app.py      (or: run-gui.ps1)
"""
import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wire  # noqa: E402
from wire import NAMES, MSG_TYPES, hexdump  # noqa: E402
from lwep_codecs import canonical, format_fields, get_codec  # noqa: E402
from forms import FieldForm, is_editable  # noqa: E402
from cpeer import CPeer  # noqa: E402

MONO = ("Consolas", 9)
NAME_TO_TYPE = {NAMES[t]: t for t in MSG_TYPES}


class LwepGui:
    def __init__(self, root):
        self.root = root
        root.title("LWEP Interop — Protobuf/nanopb & FlatBuffers/FlatCC")
        root.geometry("1000x780")
        root.minsize(820, 640)

        self.ui_q = queue.Queue()
        self.idl = tk.StringVar(value="protobuf")
        self.role = tk.StringVar(value="server")
        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value="9001")
        self.msg_name = tk.StringVar(value=NAMES[MSG_TYPES[0]])
        self.status = tk.StringVar(value="pronto")

        self._codecs = {}
        self.form = None
        self.session = None       # server mode: {idl, peer, sock, host, port}
        self.listener = None      # client mode: {srv, peer}
        self._active_peer = None  # CPeer whose stdout the poller streams
        self._active_cout = None  # target ScrolledText for that stdout

        self._build_controls()
        self._build_server_panel()
        self._build_client_panel()
        self._build_statusbar()
        self._rebuild_form()
        self._show_role()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(60, self._drain)

    # ---------------------------------------------------------------- build UI
    def _build_controls(self):
        bar = ttk.LabelFrame(self.root, text="Configuração")
        bar.pack(fill="x", padx=8, pady=(8, 4))

        idlf = ttk.Frame(bar); idlf.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(idlf, text="IDL:").pack(side="left")
        ttk.Radiobutton(idlf, text="Protobuf/nanopb", value="protobuf",
                        variable=self.idl, command=self._on_idl_change).pack(side="left", padx=4)
        ttk.Radiobutton(idlf, text="FlatBuffers/FlatCC", value="flatbuffer",
                        variable=self.idl, command=self._on_idl_change).pack(side="left", padx=4)

        rolef = ttk.Frame(bar); rolef.grid(row=0, column=1, sticky="w", padx=16, pady=6)
        ttk.Label(rolef, text="Papel:").pack(side="left")
        ttk.Radiobutton(rolef, text="server (edita/serializa)", value="server",
                        variable=self.role, command=self._show_role).pack(side="left", padx=4)
        ttk.Radiobutton(rolef, text="client (recebe/parse)", value="client",
                        variable=self.role, command=self._show_role).pack(side="left", padx=4)

        netf = ttk.Frame(bar); netf.grid(row=0, column=2, sticky="e", padx=8, pady=6)
        ttk.Label(netf, text="host:").pack(side="left")
        ttk.Entry(netf, textvariable=self.host, width=12).pack(side="left", padx=(2, 8))
        ttk.Label(netf, text="porta:").pack(side="left")
        ttk.Entry(netf, textvariable=self.port, width=6).pack(side="left", padx=2)
        bar.columnconfigure(2, weight=1)

    def _build_server_panel(self):
        f = ttk.Frame(self.root)
        self.server_frame = f

        sel = ttk.Frame(f); sel.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(sel, text="Mensagem:").pack(side="left")
        cb = ttk.Combobox(sel, textvariable=self.msg_name, state="readonly", width=20,
                          values=[NAMES[t] for t in MSG_TYPES])
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", self._rebuild_form)

        self.form_container = ttk.LabelFrame(f, text="Campos")
        self.form_container.pack(fill="x", padx=8, pady=6)
        self.form_note = ttk.Label(f, text="", foreground="#666")
        self.form_note.pack(fill="x", padx=10)

        btns = ttk.Frame(f); btns.pack(fill="x", padx=8, pady=6)
        self.send_btn = ttk.Button(btns, text="Serializar & Enviar", command=self.on_send)
        self.send_btn.pack(side="left")
        ttk.Button(btns, text="Encerrar sessão", command=self.on_close_session).pack(side="left", padx=6)

        self.ser_out = self._labeled_text(f, "Serialização (Python)", 9)
        self.echo_out = self._labeled_text(f, "Echo re-parseado (round-trip Python→C→Python)", 7)
        self.cout_out = self._labeled_text(f, "Saída do C (stdout)", 6)

    def _build_client_panel(self):
        f = ttk.Frame(self.root)
        self.client_frame = f
        btns = ttk.Frame(f); btns.pack(fill="x", padx=8, pady=6)
        self.listen_btn = ttk.Button(btns, text="Escutar & Receber", command=self.on_listen)
        self.listen_btn.pack(side="left")
        ttk.Button(btns, text="Parar", command=self.on_stop_listen).pack(side="left", padx=6)
        ttk.Label(f, text="A GUI escuta na porta e o C `main client` é iniciado automaticamente, "
                          "enviando as 4 mensagens canônicas.", foreground="#666").pack(fill="x", padx=10)

        self.recv_out = self._labeled_text(f, "Mensagens recebidas + parse (Python)", 18, expand=True)
        self.cout_out2 = self._labeled_text(f, "Saída do C (stdout)", 7)

    def _build_statusbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", side="bottom")
        ttk.Separator(self.root).pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status, anchor="w").pack(fill="x", padx=8, pady=3)

    def _labeled_text(self, parent, title, height, expand=False):
        ttk.Label(parent, text=title).pack(fill="x", padx=8, pady=(4, 0))
        txt = ScrolledText(parent, height=height, font=MONO, wrap="none")
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=expand, padx=8, pady=(0, 4))
        return txt

    # ---------------------------------------------------------------- helpers
    def _codec(self, idl):
        if idl not in self._codecs:
            self._codecs[idl] = get_codec(idl)
        return self._codecs[idl]

    def _set(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.configure(state="disabled")

    def _append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text)
        widget.see("end")
        widget.configure(state="disabled")

    def post(self, fn):
        self.ui_q.put(fn)

    def _set_status(self, text):
        self.post(lambda: self.status.set(text))

    def _drain(self):
        peer, cout = self._active_peer, self._active_cout
        if peer is not None and cout is not None:
            lines = peer.drain()
            if lines:
                self._append(cout, "\n".join(lines) + "\n")
        try:
            while True:
                self.ui_q.get_nowait()()
        except queue.Empty:
            pass
        except Exception as e:  # noqa: BLE001
            print("ui callback error:", e)
        self.root.after(60, self._drain)

    # ---------------------------------------------------------------- role/idl
    def _show_role(self):
        self._teardown_all()
        if self.role.get() == "server":
            self.client_frame.pack_forget()
            self.server_frame.pack(fill="both", expand=True)
        else:
            self.server_frame.pack_forget()
            self.client_frame.pack(fill="both", expand=True)
        self.status.set("pronto")

    def _on_idl_change(self):
        # the C peer is IDL-specific, so any open server session is now stale
        self._teardown_all()
        self.status.set(f"IDL = {self.idl.get()}")

    def _rebuild_form(self, *_):
        for w in self.form_container.winfo_children():
            w.destroy()
        t = NAME_TO_TYPE[self.msg_name.get()]
        if is_editable(t):
            self.form = FieldForm(self.form_container, t)
            self.form.pack(fill="x", anchor="w", padx=6, pady=4)
            self.form_note.config(text="Campos editáveis — altere e clique Serializar & Enviar.")
        else:
            self.form = None
            ro = ScrolledText(self.form_container, height=11, font=MONO, wrap="none")
            ro.insert("end", format_fields(t, canonical(t)))
            ro.configure(state="disabled")
            ro.pack(fill="x", padx=6, pady=4)
            self.form_note.config(
                text="Vetores/aninhados: enviada com valores canônicos (edição futura).")

    # ---------------------------------------------------------------- server mode
    def on_send(self):
        idl = self.idl.get()
        t = NAME_TO_TYPE[self.msg_name.get()]
        try:
            d = self.form.values() if (self.form and is_editable(t)) else canonical(t)
        except ValueError as e:
            messagebox.showerror("Entrada inválida", str(e))
            return
        try:
            port = int(self.port.get())
        except ValueError:
            messagebox.showerror("Porta inválida", "Informe um número de porta.")
            return
        try:
            codec = self._codec(idl)
            payload = codec.encode(t, d)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Erro de serialização", str(e))
            return
        self._set(self.ser_out, f"{NAMES[t]}   msg_type={t}   len={len(payload)} bytes\n\n"
                                f"{hexdump(payload)}\n\n{format_fields(t, d)}")
        self._set(self.echo_out, "enviando…")
        self.send_btn.config(state="disabled")
        threading.Thread(target=self._send_worker,
                         args=(idl, t, payload, self.host.get(), port, codec),
                         daemon=True).start()

    def _send_worker(self, idl, t, payload, host, port, codec):
        try:
            sess = self._ensure_session(idl, host, port)
            wire.send_frame(sess["sock"], t, payload)
            frame = wire.recv_frame(sess["sock"])
            if frame is None:
                self.post(lambda: self._set(self.echo_out, "conexão fechada pelo peer C."))
                self._teardown_all()
                return
            rt, echo = frame
            got = codec.decode(rt, echo)
            ref = codec.decode(t, payload)   # float32-normalized reference
            ok = (rt == t) and (got == ref)
            text = (f"{'PASS ✓' if ok else 'FAIL ✗'}   msg_type={rt}   len={len(echo)} bytes\n\n"
                    f"{format_fields(rt, got)}")
            if not ok:
                text += "\n\n[esperado]\n" + format_fields(t, ref)
            self.post(lambda: self._set(self.echo_out, text))
            self._set_status(f"{NAMES[t]} enviado — round-trip {'OK' if ok else 'FALHOU'}")
        except Exception as e:  # noqa: BLE001
            self.post(lambda: self._set(self.echo_out, f"FALHA: {e}"))
            self._teardown_all()
        finally:
            self.post(lambda: self.send_btn.config(state="normal"))

    def _ensure_session(self, idl, host, port):
        s = self.session
        if s and s["idl"] == idl and s.get("sock") and s["peer"].alive():
            return s
        self._teardown_all()
        peer = CPeer(idl, "server", host, port).start()
        self._active_peer, self._active_cout = peer, self.cout_out
        sock = wire.connect(host, port, timeout=5, retries=60, delay=0.1)
        self.session = {"idl": idl, "peer": peer, "sock": sock, "host": host, "port": port}
        self._set_status(f"sessão {idl} aberta — C server em {host}:{port}")
        return self.session

    def on_close_session(self):
        if not self.session:
            self.status.set("nenhuma sessão aberta")
            return
        self.status.set("encerrando sessão…")
        threading.Thread(target=self._close_session_worker, daemon=True).start()

    def _close_session_worker(self):
        s = self.session
        self.session = None
        if s:
            try:
                s["sock"].close()
            except OSError:
                pass
            peer = s.get("peer")
            if peer:
                self._active_peer = None
                time.sleep(0.15)
                rc, lines = peer.finish(5)
                if lines:
                    self.post(lambda: self._append(self.cout_out, "\n".join(lines) + "\n"))
        self._active_peer = None
        self._set_status("sessão encerrada")

    # ---------------------------------------------------------------- client mode
    def on_listen(self):
        if self.listener:
            self.status.set("já está escutando")
            return
        try:
            port = int(self.port.get())
        except ValueError:
            messagebox.showerror("Porta inválida", "Informe um número de porta.")
            return
        self._set(self.recv_out, "")
        self._set(self.cout_out2, "")
        self.listen_btn.config(state="disabled")
        threading.Thread(target=self._listen_worker,
                         args=(self.idl.get(), self.host.get(), port), daemon=True).start()

    def _listen_worker(self, idl, host, port):
        try:
            codec = self._codec(idl)
        except Exception as e:  # noqa: BLE001
            self.post(lambda: messagebox.showerror("Erro", str(e)))
            self.post(lambda: self.listen_btn.config(state="normal"))
            return
        try:
            srv = wire.make_server_socket(host, port)
            srv.settimeout(15)
        except OSError as e:
            self.post(lambda: messagebox.showerror("Erro de bind", f"porta {port}: {e}"))
            self.post(lambda: self.listen_btn.config(state="normal"))
            return
        peer = CPeer(idl, "client", host, port).start()
        self.listener = {"srv": srv, "peer": peer}
        self._active_peer, self._active_cout = peer, self.cout_out2
        self._set_status(f"escutando :{port} — aguardando C client…")
        conn = None
        try:
            conn, _ = srv.accept()
            conn.settimeout(5)
            idx = 0
            while True:
                frame = wire.recv_frame(conn)
                if frame is None:
                    break
                rt, payload = frame
                got = codec.decode(rt, payload)
                idx += 1
                block = (f"#{idx}  {NAMES[rt]}  msg_type={rt}  len={len(payload)} bytes\n"
                         f"{hexdump(payload)}\n\n{format_fields(rt, got)}\n" + "-" * 64 + "\n")
                self.post(lambda b=block: self._append(self.recv_out, b))
                wire.send_frame(conn, rt, codec.encode(rt, got))   # echo for the C client
            self._set_status(f"recepção concluída — {idx} mensagem(ns) parseada(s)")
        except socket.timeout:
            self._set_status("timeout — nenhum cliente C conectou/enviou a tempo")
        except Exception as e:  # noqa: BLE001
            self._set_status(f"erro na recepção: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except OSError:
                    pass
            self._active_peer = None
            time.sleep(0.15)
            rc, lines = peer.finish(3)
            if lines:
                self.post(lambda: self._append(self.cout_out2, "\n".join(lines) + "\n"))
            self._stop_listener()
            self.post(lambda: self.listen_btn.config(state="normal"))

    def on_stop_listen(self):
        self._stop_listener()
        self.status.set("parado")

    def _stop_listener(self):
        lst = self.listener
        self.listener = None
        if lst:
            try:
                lst["srv"].close()
            except OSError:
                pass
            peer = lst.get("peer")
            if peer:
                peer.stop()
        self._active_peer = None

    # ---------------------------------------------------------------- teardown
    def _teardown_all(self):
        s = self.session
        self.session = None
        if s:
            try:
                s["sock"].close()
            except OSError:
                pass
            if s.get("peer"):
                s["peer"].stop()
        self._stop_listener()
        self._active_peer = None

    def _on_close(self):
        self._teardown_all()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")   # nicer on Windows; ignore if unavailable
    except tk.TclError:
        pass
    LwepGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
