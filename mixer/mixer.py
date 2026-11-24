"""SplitDesk local audio mixer."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json
import math
import subprocess
import sys
import time
from ctypes import POINTER,cast
from pathlib import Path

from comtypes import CLSCTX_ALL
from pycaw.api.endpointvolume import IAudioMeterInformation
from pycaw.pycaw import AudioUtilities
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QFont,QIcon,QPainter,QPen,QPixmap
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QPushButton,QSlider,QFrame,QScrollArea,QFileDialog,QMessageBox,QSizePolicy,QTabWidget)
from hardware import Chassis, ConsoleFrame, Fader, Needle, TitleBar
from console_style import STYLE
from playback import Player,inspect_files
from eq_panel import Equalizer

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'routing.json').read_text(encoding='utf-8-sig'))
TEAL='#e77470'
GOLD='#d2c9c4'
BG='#12171c'
PANEL='#1b2229'
LINE='#484347'
MUTED='#b8b2af'
WHITE='#f3eeea'

def txt(content,size=10,color=WHITE,bold=False):
    w=QLabel(content)
    font=w.font()
    font.setPointSizeF(size)
    font.setBold(bold)
    w.setFont(font)
    w.setStyleSheet(f'color:{color};background:transparent')
    return w

def row(parent=None):
    layout=QHBoxLayout(parent)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(9)
    return layout

def button(name,action=None,check=False):
    w=QPushButton(name)
    w.setCursor(Qt.PointingHandCursor)
    w.setCheckable(check)
    if action: w.clicked.connect(action)
    return w

def panel():
    w=QFrame()
    w.setObjectName('panel')
    return w

def logo():
    pic=QPixmap(64,64)
    pic.fill(Qt.transparent)
    p=QPainter(pic)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#202023'))
    p.drawRoundedRect(QRectF(2,2,60,60),15,15)
    p.setPen(QPen(QColor('#eb5757'),5,Qt.SolidLine,Qt.RoundCap))
    for i,h in enumerate((10,24,39,20,10)):
        x=14+i*9
        p.drawLine(x,32-h//2,x,32+h//2)
    p.end()
    return QIcon(pic)

class Strip(QWidget):
    def __init__(self,name,side,accent,endpoint):
        super().__init__()
        self.endpoint=endpoint
        self.color=accent
        self.vol=self.meter_api=None
        layout=QVBoxLayout(self)
        layout.setContentsMargins(6,2,6,4)
        layout.setSpacing(8)
        layout.addWidget(txt(side,9,accent,True),alignment=Qt.AlignCenter)
        self.name_label=txt('',15,WHITE,True)
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label)
        self.show_name(name)
        self.meter=Needle()
        layout.addWidget(self.meter)
        self.value=txt('—',17,WHITE,True)
        self.value.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value)
        path=row()
        path.setSpacing(12)
        path.addStretch()
        self.fader=Fader()
        self.fader.setAccessibleName(name+' volume')
        self.fader.setRange(0,100)
        self.fader.setPageStep(5)
        self.fader.setMinimumHeight(95)
        self.fader.setFixedWidth(54)
        path.addWidget(self.fader)
        scale=QVBoxLayout()
        scale.setSpacing(0)
        for i,v in enumerate(('100','75','50','25','0')):
            if i: scale.addStretch()
            scale.addWidget(txt(v,8,'#8997a1'))
        path.addLayout(scale)
        path.addStretch()
        layout.addLayout(path,1)
        self.mute=button('Mute',self.set_mute,True)
        self.mute.setAccessibleName(name+' mute')
        layout.addWidget(self.mute)
        self.fader.valueChanged.connect(self.change)
        self.bind()
    def show_name(self,name):
        self.name_label.setTextFormat(Qt.PlainText)
        self.name_label.setText(self.name_label.fontMetrics().elidedText(name,Qt.ElideRight,107))
        self.name_label.setToolTip(name)
    def bind(self):
        try:
            enum=AudioUtilities.GetDeviceEnumerator()
            dev=enum.GetDevice(self.endpoint)
            self.vol=AudioUtilities.CreateDevice(dev).EndpointVolume
            self.meter_api=cast(dev.Activate(IAudioMeterInformation._iid_,CLSCTX_ALL,None),
                                POINTER(IAudioMeterInformation))
            self.setEnabled(True)
        except Exception:
            self.offline()
    def offline(self):
        self.vol=self.meter_api=None
        self.value.setText('Offline')
        self.setEnabled(False)
        self.meter.set_peak(0)
    def change(self,value):
        try:
            self.vol.SetMasterVolumeLevelScalar(value/100,None)
            self.value.setText(f'{value}%')
        except Exception:
            self.offline()
    def set_mute(self,mute):
        try:
            self.vol.SetMute(bool(mute),None)
        except Exception:
            self.offline()
    def refresh(self):
        if self.vol is None:
            return
        try:
            value=round(self.vol.GetMasterVolumeLevelScalar()*100)
            muted=bool(self.vol.GetMute())
            self.meter.set_peak(0 if muted else self.meter_api.GetPeakValue())
            if not self.fader.isSliderDown():
                self.fader.blockSignals(True)
                self.fader.setValue(value)
                self.fader.blockSignals(False)
                if self.value.text() != f'{value}%':
                    self.value.setText(f'{value}%')
            self.mute.setChecked(muted)
        except Exception:
            self.offline()

class Mixer(ConsoleFrame):
    def __init__(self):
        super().__init__()
        self.player=Player()
        self.counter=0
        self.setWindowTitle('SplitDesk · Stereo Mixer')
        self.setWindowIcon(logo())
        self.resize(1060,620)
        self.setMinimumSize(910,550)
        shell=Chassis()
        self.setCentralWidget(shell)
        outer=QVBoxLayout(shell)
        outer.setContentsMargins(36,24,36,34)
        outer.setSpacing(16)
        self.status=txt('',10,TEAL,True)
        self.titlebar=TitleBar(self,self.status)
        outer.addWidget(self.titlebar)
        body=row()
        body.setSpacing(14)
        outer.addLayout(body,1)
        left=panel()
        left.setFixedWidth(284)
        ll=QVBoxLayout(left)
        ll.setContentsMargins(15,14,15,14)
        ll.setSpacing(12)
        ll.addWidget(txt('OUTPUT CHANNELS',12,WHITE,True))
        strips=row()
        self.remote=Strip(CFG['remote_name'],'CHANNEL L',TEAL,CFG['remote_output'])
        self.local=Strip(CFG['local_name'],'CHANNEL R',GOLD,CFG['local_output'])
        strips.addWidget(self.remote,1)
        divider=QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet('background:'+LINE)
        strips.addWidget(divider)
        strips.addWidget(self.local,1)
        ll.addLayout(strips,1)
        body.addWidget(left)
        right=panel()
        self.route_proc=None
        self.route_btn=button('Start split',self.change_route)
        self.devices_btn=button('Devices…',self.devices)
        bar=self.titlebar.layout()
        bar.insertWidget(bar.indexOf(self.status),self.devices_btn)
        bar.insertWidget(bar.indexOf(self.status),self.route_btn)
        tabs_layout=QVBoxLayout(right)
        self.tabs=QTabWidget()
        tabs_layout.addWidget(self.tabs)
        self.eq=Equalizer()
        self.tabs.addTab(self.eq,'Master EQ')
        track_page=QWidget()
        self.tabs.addTab(track_page,'Track Mixer')
        rl=QVBoxLayout(track_page)
        rl.setContentsMargins(17,14,17,12)
        rl.setSpacing(9)
        head=row()
        head.addWidget(txt('Track Mixer',12,WHITE,True))
        head.addStretch()
        self.open_btn=button('Open audio…',self.open_one)
        self.multi_btn=button('Import stems…',self.open_many)
        head.addWidget(self.open_btn)
        head.addWidget(self.multi_btn)
        rl.addLayout(head)
        self.file_label=txt('',10,TEAL)
        self.file_label.setWordWrap(True)
        session_row=row()
        session_row.addWidget(self.file_label,1)
        self.play=button('Play',self.toggle)
        self.stop=button('Stop',lambda:self.player.reset(0,False))
        for control in (self.play,self.stop):
            session_row.addWidget(control)
            control.hide()
        rl.addLayout(session_row)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        rl.addWidget(self.scroll,1)
        self.empty=QWidget()
        el=QVBoxLayout(self.empty)
        el.setContentsMargins(18,16,18,16)
        el.addStretch()
        el.addWidget(txt('Load a session',15,WHITE,True))
        hint=txt('Open a multitrack file or import stems that share a start time.',10,MUTED)
        hint.setWordWrap(True)
        el.addWidget(hint)
        el.addStretch()
        self.scroll.setWidget(self.empty)
        body.addWidget(right,1)
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(150)
        self.refresh()

    def change_route(self):
        mode='stop' if (ROOT/'previous-output.json').exists() else 'start'
        self.route_proc=subprocess.Popen([sys.executable,str(ROOT/'router.py'),mode],
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.route_btn.setEnabled(False)
        QTimer.singleShot(1200,lambda:self.route_btn.setEnabled(True))

    def devices(self):
        from devices import configure,CONFIG
        import playback
        if configure():
            CFG.update(json.loads(CONFIG.read_text(encoding='utf-8')))
            playback.MIX_ENDPOINT=CFG['desktop_mix']
            for strip,side in ((self.remote,'remote'),(self.local,'local')):
                name=CFG[side+'_name']
                strip.endpoint=CFG[side+'_output']
                strip.show_name(name)
                strip.fader.setAccessibleName(name+' volume')
                strip.mute.setAccessibleName(name+' mute')
                strip.bind()
            self.refresh()

    def open_one(self):
        name,_=QFileDialog.getOpenFileName(self,'Open audio or multitrack media',str(Path.home()/'Music'),
                    'Audio and video (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.aif *.aiff *.mka *.mkv *.mp4 *.mov *.ac3 *.m4v *.wma *.m4b);;All files (*)')
        if name:
            self.load([name])
    def open_many(self):
        names,_=QFileDialog.getOpenFileNames(self,'Import aligned stems',str(Path.home()/'Music'),
                                             'Media files (*.wav *.flac *.mp3 *.m4a *.aif *.aiff *.ogg *.opus *.mka *.mp4);;All files (*)')
        if names:
            self.load(names)
    def load(self,paths):
        try:
            project=inspect_files(paths)
        except Exception as exc:
            QMessageBox.warning(self,'Could not open file',str(exc))
            return
        self.player.load(project)
        self.tabs.setCurrentIndex(1)
        self.file_label.setText(project.title)
        content=QWidget()
        content.setObjectName('tracks')
        layout=QVBoxLayout(content)
        layout.setContentsMargins(0,3,6,6)
        layout.setSpacing(6)
        self.controls=[]
        for n,t in enumerate(project.tracks):
            strip=QFrame()
            strip.setObjectName('track')
            box=QVBoxLayout(strip)
            box.setContentsMargins(11,9,11,8)
            box.setSpacing(5)
            line=row()
            name=txt(t.name,11,WHITE,True)
            name.setWordWrap(True)
            line.addWidget(name,1)
            solo=button('Solo',None,True)
            mute=button('Mute',None,True)
            solo.setAccessibleName(t.name+' solo')
            mute.setAccessibleName(t.name+' mute')
            mute.setChecked(not t.enabled)
            line.addWidget(solo)
            line.addWidget(mute)
            box.addLayout(line)
            box.addWidget(txt(t.detail,8.5,MUTED))
            sliders=row()
            gain=QSlider(Qt.Horizontal)
            gain.setAccessibleName(t.name+' volume')
            gain.setRange(0,150)
            gain.setValue(100)
            readout=txt('100%',9,TEAL)
            readout.setMinimumWidth(36)
            sliders.addWidget(gain,1)
            sliders.addWidget(readout)
            box.addLayout(sliders)
            self.controls.append((gain,mute,solo,readout))
            solo.toggled.connect(lambda on,m=mute: m.setChecked(False) if on else None)
            mute.toggled.connect(lambda on,s=solo: s.setChecked(False) if on else None)
            for signal in (gain.valueChanged,mute.toggled,solo.toggled):
                signal.connect(lambda _,i=n:self.track_change(i))
            layout.addWidget(strip)
        layout.addStretch()
        self.scroll.setWidget(content)
        self.play.show()
        self.stop.show()
    def track_change(self,i):
        gain,mute,solo,readout=self.controls[i]
        with self.player.cv:
            self.player.settings[i]=(gain.value()/100,mute.isChecked(),solo.isChecked())
        readout.setText(f'{gain.value()}%')
    def toggle(self):
        with self.player.cv:
            if self.player.project:
                self.player.reset(self.player.pos,not self.player.playing)
    def refresh(self):
        hidden = self.isMinimized() or not self.isVisible()
        desired = 1800 if hidden else (150 if self.isActiveWindow() else 400)
        if self.timer.interval() != desired:
            self.timer.setInterval(desired)
        if hidden and self.counter:
            return
        self.counter+=1
        for strip in (self.remote,self.local):
            if strip.vol is None and self.counter%20==0:
                strip.bind()
            strip.refresh()
        if self.route_proc and self.route_proc.poll() is not None:
            rc=self.route_proc.returncode
            self.route_proc=None
            if rc:
                QMessageBox.warning(self,'Routing error','Check the four devices in Devices and see routing.log in the installation folder.')
        if self.counter%5==1:
            try:
                default=AudioUtilities.GetSpeakers().id
                combo=(ROOT/'previous-output.json').exists() and default.lower()==CFG['desktop_mix'].lower()
            except Exception:
                combo=False
            self.route_btn.setText('Stop split' if (ROOT/'previous-output.json').exists() else 'Start split')
            self.status.setText('●  Split stereo' if combo else '●  Local output')
        with self.player.cv:
            on=self.player.playing
            error,self.player.error=self.player.error,''
        if error:
            QMessageBox.warning(self,'Playback interrupted',error)
        self.play.setText('Pause' if on else 'Play')

    def closeEvent(self,event):
        if self.eq.writer.isActive():
            self.eq.writer.stop()
            self.eq.persist()
        self.player.close()
        super().closeEvent(event)

def main():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontUseNativeDialogs,True)
    app.setApplicationName('SplitDesk Mixer')
    font=QFont()
    font.setFamilies(['Inter','Segoe UI'])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    key='SplitDeskStereo-'+ROOT.name
    peer=QLocalSocket()
    peer.connectToServer(key)
    if peer.waitForConnected(180):
        peer.disconnectFromServer()
        return
    server=QLocalServer()
    if not server.listen(key):
        return
    window=Mixer()
    def show_existing():
        sock=server.nextPendingConnection()
        if sock:
            sock.deleteLater()
        window.showNormal()
        window.raise_()
        window.activateWindow()
    server.newConnection.connect(show_existing)
    window.show()
    sys.exit(app.exec())
if __name__=='__main__':
    main()
