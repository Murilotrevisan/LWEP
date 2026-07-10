"""Schema-driven Tkinter form for the editable messages (SensorReading,
DeviceStatus). Driven entirely by lwep_codecs.FIELD_SCHEMA so the same code
serves both IDLs. Reads back a validated dict, raising a friendly ValueError on
bad input before anything reaches the wire.
"""
import tkinter as tk
from tkinter import ttk

from lwep_codecs import FIELD_SCHEMA, SENSOR_TYPES, EDITABLE, canonical

_ENUM_NAME_TO_INT = {name: val for name, val in SENSOR_TYPES}
_ENUM_INT_TO_NAME = {val: name for name, val in SENSOR_TYPES}


def is_editable(msg_type):
    return msg_type in EDITABLE


class FieldForm(ttk.Frame):
    """A grid of labelled widgets for one editable message type."""

    def __init__(self, parent, msg_type):
        super().__init__(parent)
        self.msg_type = msg_type
        self.schema = FIELD_SCHEMA[msg_type]
        self.vars = {}
        seed = canonical(msg_type)
        for row, spec in enumerate(self.schema):
            key, kind = spec["key"], spec["kind"]
            ttk.Label(self, text=spec["label"]).grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            val = seed[key]
            if kind == "bool":
                var = tk.BooleanVar(value=bool(val))
                ttk.Checkbutton(self, variable=var).grid(row=row, column=1, sticky="w", pady=2)
            elif kind == "enum":
                var = tk.StringVar(value=_ENUM_INT_TO_NAME.get(val, str(val)))
                ttk.Combobox(self, textvariable=var, state="readonly", width=18,
                             values=[n for n, _ in SENSOR_TYPES]).grid(
                    row=row, column=1, sticky="w", pady=2)
            else:
                text = f"0x{val:X}" if kind == "hexint" else str(val)
                var = tk.StringVar(value=text)
                ttk.Entry(self, textvariable=var, width=28).grid(
                    row=row, column=1, sticky="we", pady=2)
            self.vars[key] = var
        self.columnconfigure(1, weight=1)

    def values(self):
        """Return the edited message as a validated dict (mutating canonical)."""
        d = canonical(self.msg_type)
        for spec in self.schema:
            key, kind, label = spec["key"], spec["kind"], spec["label"]
            raw = self.vars[key].get()
            d[key] = _coerce(kind, raw, label, spec.get("range"), spec.get("maxbytes"))
        return d


def _coerce(kind, raw, label, rng, maxbytes):
    if kind == "bool":
        return bool(raw)
    if kind == "enum":
        if raw not in _ENUM_NAME_TO_INT:
            raise ValueError(f"{label}: escolha um valor válido")
        return _ENUM_NAME_TO_INT[raw]
    if kind in ("float", "double"):
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"{label}: número decimal inválido ({raw!r})")
    if kind == "string":
        if maxbytes is not None and len(raw.encode("utf-8")) > maxbytes:
            raise ValueError(f"{label}: máximo {maxbytes} bytes")
        return raw
    # uint / int / hexint  (int(_, 0) accepts decimal and 0x/0o/0b)
    try:
        n = int(raw, 0)
    except (ValueError, TypeError):
        raise ValueError(f"{label}: inteiro inválido ({raw!r})")
    if rng is not None and not (rng[0] <= n <= rng[1]):
        raise ValueError(f"{label}: fora do intervalo [{rng[0]}, {rng[1]}]")
    return n
