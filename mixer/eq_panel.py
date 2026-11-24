"""Master tone controls with a computed transfer curve."""
import math
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QSlider, QVBoxLayout,
                               QHBoxLayout, QSizePolicy)
from hardware import Rotary
from audio_tone import BANDS, GRID, PRESETS, design, read_settings, save_settings

NOTES = {
    "Flat": "Unity gain across all six bands.",
    "Jazz": "Warm low mids with a light lift for cymbals.",
    "Pop": "Low-end punch with a gentle presence lift.",
    "Rock": "More weight for kick and guitars, with a softer top end.",
    "Vocal": "Less low-end masking for clearer vocals and speech.",
    "Custom": "Custom curve. Each step adjusts gain by 0.5 dB.",
}


class Curve(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(116)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName("Filter response before output trim")
        self.values = [0] * len(GRID)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111113"))
        p.drawRoundedRect(QRectF(0, 0, w, h), 9, 9)
        left, top, bottom = 37, 12, h - 22
        width = w - left - 19
        def x(hz):
            return left + width*math.log(hz/20)/math.log(1000)
        def y(db):
            return top + (8-db)*(bottom-top)/16
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        for val in (-6, 0, 6):
            p.setPen(QColor("#4a4143" if val == 0 else "#2b2729"))
            p.drawLine(left, int(y(val)), w-12, int(y(val)))
            p.setPen(QColor("#a69b9d"))
            p.drawText(6, int(y(val))+4, f"{val:+d}")
        for hz, label in ((30,"30"), (100,"100"), (1000,"1k"), (10000,"10k")):
            pos = int(x(hz))
            p.setPen(QColor("#282527"))
            p.drawLine(pos, top, pos, bottom)
            p.setPen(QColor("#a69b9d"))
            p.drawText(pos-7, h-5, label)
        line = QPainterPath()
        for hz, db in zip(GRID, self.values):
            if 20 <= hz <= 20000:
                if line.elementCount():
                    line.lineTo(x(hz), y(db))
                else:
                    line.moveTo(x(hz), y(db))
        p.setPen(QPen(QColor("#f36a65"), 2.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(line)


class Equalizer(QWidget):
    def __init__(self):
        super().__init__()
        gains, bypass = read_settings()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 11, 12, 7)
        layout.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("Six-band equalizer")
        title.setStyleSheet("font-size:17px;font-weight:600")
        header.addWidget(title)
        header.addStretch()
        self.bypass = QPushButton("Bypass")
        self.bypass.setCheckable(True)
        self.bypass.setChecked(bypass)
        self.bypass.setToolTip("Bypass the EQ and retain its settings")
        header.addWidget(self.bypass)
        layout.addLayout(header)
        presets = QHBoxLayout()
        self.buttons = {}
        for name in PRESETS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, n=name: self.select(n))
            presets.addWidget(btn)
            self.buttons[name] = btn
        layout.addLayout(presets)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#cdc4c1")
        layout.addWidget(self.note)
        self.curve = Curve()
        layout.addWidget(self.curve, 1)
        row = QHBoxLayout()
        self.sliders = []
        self.values = []
        for hz, gain in zip(BANDS, gains):
            col = QVBoxLayout()
            col.setSpacing(2)
            value = QLabel()
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("color:#e7d9d5")
            col.addWidget(value)
            fader = Rotary(hz)
            fader.setRange(-12, 12)
            fader.setValue(round(gain*2))
            fader.setAccessibleName(f"{hz} Hz gain")
            col.addWidget(fader, 0, Qt.AlignHCenter)
            label = QLabel(f"{hz} Hz" if hz<1000 else f"{hz/1000:g} kHz")
            label.setAlignment(Qt.AlignCenter)
            col.addWidget(label)
            row.addLayout(col, 1)
            self.sliders.append(fader)
            self.values.append(value)
        layout.addLayout(row)
        self.margin = QLabel()
        self.margin.setWordWrap(True)
        self.margin.setStyleSheet("color:#b8afad;font-size:12px")
        layout.addWidget(self.margin)
        self.writer = QTimer(self)
        self.writer.setSingleShot(True)
        self.writer.timeout.connect(self.persist)
        self.bypass.toggled.connect(self.changed)
        for slider in self.sliders:
            slider.valueChanged.connect(self.changed)
        self.draw()

    def settings(self):
        return tuple(s.value()/2 for s in self.sliders), self.bypass.isChecked()

    def select(self, name):
        for slider, gain in zip(self.sliders, PRESETS[name]):
            slider.blockSignals(True)
            slider.setValue(round(gain*2))
            slider.blockSignals(False)
        self.bypass.setChecked(False)
        self.changed()

    def draw(self):
        gains, bypass = self.settings()
        name = next((n for n, g in PRESETS.items() if g == gains), "Custom")
        for n, btn in self.buttons.items():
            btn.setChecked(n == name)
        for val, gain in zip(self.values, gains):
            val.setText(f"{gain:+.1f}")
        _, trim, curve = design(gains)
        self.curve.values = curve*0 if bypass else curve
        self.curve.update()
        self.note.setText("Bypass engaged. Your settings are retained." if bypass else NOTES[name])
        trim = 0 if bypass or trim < .05 else -trim
        self.margin.setText(f"Filter response   /   Output trim {trim:.1f} dB")

    def changed(self, *_):
        self.draw()
        if not self.writer.isActive():
            self.writer.start(45)

    def persist(self):
        try:
            save_settings(*self.settings())
        except OSError as exc:
            self.margin.setText(f"Could not save settings: {exc}")
