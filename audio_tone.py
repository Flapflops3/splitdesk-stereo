"""Six-band stereo equalizer shared by the router and local file player."""
import ctypes
import json
import math
import os
import tempfile
import time
from pathlib import Path

import numpy as np


RATE = 48000
PATH = Path(__file__).with_name("mix-controls.json")
BANDS = (80, 250, 800, 2500, 6000, 12000)
PRESETS = {
    "Flat": (0, 0, 0, 0, 0, 0),
    "Jazz": (0, 1, 0, 0.5, 1, 0.5),
    "Pop": (2, -1, 0, 1.5, 1, 0),
    "Rock": (1.5, -1, 0.5, 1, 0.5, -0.5),
    "Vocal": (-1.5, -1, 0.5, 2, 0, -0.5),
}
GRID = np.geomspace(10, RATE / 2, 420)
_Z = np.exp(-2j*np.pi*np.r_[0, GRID] / RATE)
_Z2 = _Z * _Z
_kernel = None


def kernel():
    global _kernel
    if _kernel is None:
        lib = ctypes.CDLL(str(Path(__file__).parent / 'mixer' / 'tone.dll'))
        _kernel = lib.filter_stereo
        _kernel.argtypes = [np.ctypeslib.ndpointer('float64', flags='C_CONTIGUOUS'),
                            np.ctypeslib.ndpointer('float64', flags='C_CONTIGUOUS'),
                            np.ctypeslib.ndpointer('float32', flags='C_CONTIGUOUS'),
                            np.ctypeslib.ndpointer('float32', flags='C_CONTIGUOUS'),
                            ctypes.c_int, ctypes.c_double]
        _kernel.restype = None
    return _kernel


def read_settings(path=PATH):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        gains = tuple(float(v) for v in data["gains"])
        if len(gains) != len(BANDS) or not all(-6 <= v <= 6 for v in gains):
            raise ValueError("Invalid gain")
        return gains, data.get("bypass") is True
    except (OSError, ValueError, TypeError, KeyError):
        return PRESETS["Flat"], False


def save_settings(gains, bypass, path=PATH):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False,
                                     encoding="utf-8") as tmp:
        json.dump(dict(gains=gains, bypass=bypass), tmp)
    try:
        os.replace(tmp.name, path)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def design(gains):
    rows = []
    for hz, db in zip(BANDS, gains):
        a = 10 ** (db / 40)
        w = 2 * math.pi * hz / RATE
        c, s = math.cos(w), math.sin(w)
        if hz in (BANDS[0], BANDS[-1]):
            # RBJ shelf, slope S=1. Sign selects low or high shelf.
            sign = -1 if hz == BANDS[0] else 1
            k = math.sqrt(2 * a) * s
            u, v = a + 1, a - 1
            b0 = a * (u + sign*v*c + k)
            b1 = -2*a*(c*u + sign*v)
            b2 = a * (u + sign*v*c - k)
            a0 = u - sign*v*c + k
            a1 = -2*(c*u - sign*v)
            a2 = u - sign*v*c - k
        else:
            alpha = s / 2  # Q=1
            b0, b1, b2 = 1+alpha*a, -2*c, 1-alpha*a
            a0, a1, a2 = 1+alpha/a, -2*c, 1-alpha/a
        rows.append((b0/a0, b1/a0, b2/a0, 1, a1/a0, a2/a0))
    sos = np.array(rows)
    response = np.ones_like(_Z)
    for b0, b1, b2, _, a1, a2 in rows:
        response *= (b0 + b1*_Z + b2*_Z2) / (1 + a1*_Z + a2*_Z2)
    db = 20*np.log10(np.maximum(abs(response), 1e-12))
    trim = max(0., float(db.max()))
    return sos, trim, db[1:]


class Filter:
    def __init__(self, gains, bypass):
        self.active = not bypass and any(gains)
        if self.active:
            self.run = kernel()
            self.sos, trim, _ = design(gains)
            self.scale = 10**(-trim / 20)
            self.state = np.zeros((len(gains), 2, 2))

    def apply(self, x):
        if not self.active:
            return x
        data = np.ascontiguousarray(x, dtype=np.float32)
        y = np.empty_like(data)
        self.run(self.sos, self.state, data, y, len(data), self.scale)
        return y


class LiveEQ:
    def __init__(self, path=PATH):
        self.path = path
        self.settings = read_settings(path)
        self.filter = Filter(*self.settings)
        self.poll_at = 0
        self.stamp = None
        self.old = None
        self.faded = 0

    def process(self, x):
        now = time.monotonic()
        if now >= self.poll_at:
            self.poll_at = now + .12
            try:
                stamp = self.path.stat().st_mtime_ns
            except FileNotFoundError:
                stamp = None
            if stamp != self.stamp:
                self.stamp = stamp
                settings = read_settings(self.path)
                if settings != self.settings:
                    self.old, self.filter = self.filter, Filter(*settings)
                    self.settings, self.faded = settings, 0
        y = self.filter.apply(x)
        if self.old:
            n = min(len(x), 480 - self.faded)
            blend = (np.arange(n) + self.faded + 1)[:, None] / 480
            y = y.copy()
            y[:n] = self.old.apply(x[:n]) * (1-blend) + y[:n] * blend
            self.faded += n
            if self.faded == 480:
                self.old = None
        if self.filter.active or y is not x:
            return np.clip(y, -1, 1, out=y)
        return x
