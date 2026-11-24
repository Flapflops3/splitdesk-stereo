"""Machine-local device selection and Sunshine integration values."""
import json
import os
import socket
import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QMessageBox, QSpinBox)
from pycaw.pycaw import AudioUtilities
from pycaw.constants import DEVICE_STATE, EDataFlow

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "routing.json"


def endpoints(flow):
    return [(d.id, d.FriendlyName) for d in AudioUtilities.GetAllDevices(
        data_flow=flow.value, device_state=DEVICE_STATE.ACTIVE.value)]


def save(config):
    temp = CONFIG.with_suffix(".tmp")
    temp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, CONFIG)
    (ROOT / "sunshine-audio.txt").write_text(
        "external_audio = enabled\naudio_sink = " + config["remote_output"] + "\n", encoding="utf-8")


def configure():
    if (ROOT/"previous-output.json").exists():
        QMessageBox.warning(None, "Devices", "Stop split stereo before changing devices.")
        return False
    existing = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    render = endpoints(EDataFlow.eRender)
    capture = endpoints(EDataFlow.eCapture)
    dialog = QDialog()
    dialog.setWindowTitle("SplitDesk Stereo · Device setup")
    layout = QFormLayout(dialog)
    remote_name = QLineEdit(existing.get("remote_name", ""))
    remote_name.setPlaceholderText("Enter the name shown on your Moonlight device")
    local_name = QLineEdit(existing.get("local_name", socket.gethostname()))
    for widget in (remote_name, local_name):
        widget.setMaxLength(60)
    layout.addRow("Left device name", remote_name)
    layout.addRow("Right device name", local_name)
    default = AudioUtilities.GetSpeakers().id
    choices = {}
    def choose(key, label, items, match):
        box = QComboBox()
        box.addItem("Select an endpoint…", None)
        for ident, name in items:
            box.addItem(name,ident)
        selected = existing.get(key)
        candidates = [i for i,n in items if match(i,n)]
        if not selected and len(candidates) == 1:
            selected = candidates[0]
        box.setCurrentIndex(max(0,box.findData(selected)))
        choices[key] = box
        layout.addRow(label,box)
    cable = lambda i,n: "vb-audio virtual cable" in n.lower() and "16 ch" not in n.lower()
    choose("desktop_mix","Windows mix · VB-CABLE playback", render,cable)
    choose("cable_recording","Cable return · VB-CABLE recording", capture,cable)
    choose("remote_output","Left · Sunshine capture endpoint", render,
           lambda i,n: "steam streaming speakers" in n.lower())
    choose("local_output","Right · Physical speakers", render,
           lambda i,n: i==default and not cable(i,n) and "steam streaming" not in n.lower())
    delay = QSpinBox()
    delay.setRange(0,300)
    delay.setSuffix(" ms")
    delay.setValue(existing.get("local_delay_ms",35))
    layout.addRow("Right channel delay",delay)
    info = QLabel("Device names are display labels. Choose three distinct playback endpoints.")
    layout.addRow(info)
    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    layout.addRow(buttons)
    def accept():
        values = {key:box.currentData() for key,box in choices.items()}
        if not all(values.values()) or not remote_name.text().strip() or not local_name.text().strip():
            info.setText("Enter both device names and select all four endpoints.")
            return
        if len({values[k] for k in ("desktop_mix","remote_output","local_output")}) != 3:
            info.setText("The Windows mix, streaming endpoint and physical speakers must be distinct.")
            return
        if not all(cable(None,choices[k].currentText()) for k in ("desktop_mix","cable_recording")):
            info.setText("Select the standard VB-Audio Virtual Cable playback and recording pair.")
            return
        values.update(remote_name=remote_name.text().strip(),local_name=local_name.text().strip(),
                      local_delay_ms=delay.value())
        save(values)
        dialog.accept()
    buttons.accepted.connect(accept)
    buttons.rejected.connect(dialog.reject)
    return dialog.exec()==QDialog.Accepted


if __name__ == "__main__":
    app=QApplication(sys.argv)
    if configure():
        QMessageBox.information(None,"Devices saved","Reopen the mixer to use these names. Sunshine settings are in sunshine-audio.txt.")
