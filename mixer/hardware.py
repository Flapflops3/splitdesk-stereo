"""Native-painted console parts. Controls retain Qt keyboard and accessibility support."""
import ctypes
import math
from pathlib import Path
from ctypes import wintypes
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QLinearGradient, QRadialGradient, QPainter, QPen, QPixmap, QImage, QTransform
from PySide6.QtWidgets import QWidget, QDial, QSlider, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMainWindow

def linear(x, y, x2, y2, stops):
    g = QLinearGradient(x, y, x2, y2)
    for at, color in stops:
        g.setColorAt(at, QColor(color))
    return g

def box(p, rect, brush, edge, radius):
    p.setBrush(brush)
    p.setPen(QPen(QColor(edge), 1))
    p.drawRoundedRect(rect, radius, radius)

class Chassis(QWidget):
    def __init__(self):
        super().__init__()
        grain=QImage(str(Path(__file__).with_name("american_walnut.jpg"))).convertToFormat(QImage.Format_Grayscale8)
        grain.reinterpretAsFormat(QImage.Format_Indexed8)
        # A warm oil stain keeps the photographed pores and growth rings visible.
        palette=[]
        for value in range(256):
            n=max(0,min(1,(value-58)/127))
            palette.append(QColor(round(53+130*n),round(26+89*n),round(16+59*n)).rgb())
        grain.setColorTable(palette)
        self.wood=QPixmap.fromImage(grain)
        self.endgrain=self.wood.transformed(QTransform().rotate(90))
        self.skin=None
        self.skin_key=None

    def paintEvent(self,event):
        w,h=self.width(),self.height()
        scale=self.devicePixelRatioF()
        key=w,h,scale
        if key!=self.skin_key:
            self.skin_key=key
            self.skin=QPixmap(round(w*scale),round(h*scale))
            self.skin.setDevicePixelRatio(scale)
            p=QPainter(self.skin)
            p.setRenderHint(QPainter.Antialiasing)
            p.drawPixmap(QRectF(0,0,w,h),self.wood,QRectF(0,120,1024,560))
            for pos in (0,w-21):
                p.drawPixmap(QRectF(pos,0,21,h),self.endgrain,QRectF(300 if pos else 64,0,33,1024))
                p.fillRect(QRectF(pos,0,21,h),linear(pos,0,pos+21,0,[(0,"#693d29"),(.085,"#539d7652"),(.16,"#00997050"),(.82,"#00754b33"),(1,"#593321")]))
            p.fillRect(QRectF(21,0,w-42,9),linear(0,0,0,9,[(0,"#9c7153"),(.18,"#99714f"),(1,"#00603c26")]))
            # The header is the exposed solid crosspiece above the inset faceplate.
            plate_top=67
            p.drawPixmap(QRectF(21,8,w-42,plate_top-8),self.wood,QRectF(0,160,1024,74))
            p.fillRect(QRectF(21,8,w-42,plate_top-8),linear(0,8,0,plate_top,[(0,"#267a583a"),(.22,"#100b0503"),(.82,"#220b0503"),(1,"#64321a0e")]))
            box(p,QRectF(21,plate_top,w-42,h-plate_top-21),linear(0,plate_top,0,h-21,[(0,"#242426"),(.12,"#1d1d1e"),(.65,"#141416"),(1,"#101012")]),"#100d0c",4)
            p.setPen(QColor("#4a4546"))
            p.drawLine(25,plate_top+1,w-26,plate_top+1)
            for x in (11,w-11):
                for y in (22,h-24):
                    box(p,QRectF(x-3.5,y-3.5,7,7),QColor("#292625"),"#946e51",3)
                    p.setPen(QColor("#0c0b0b"))
                    p.drawLine(x-2,y+1,x+2,y-1)
            p.end()
        QPainter(self).drawPixmap(0,0,self.skin)

class ConsoleFrame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowTitle("SplitDesk · Stereo Mixer")

    def showEvent(self,event):
        super().showEvent(event)
        border=ctypes.c_uint(0xfffffffe)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(int(self.winId())),34,ctypes.byref(border),4)

    def nativeEvent(self, kind, message):
        msg=wintypes.MSG.from_address(int(message))
        if msg.message == 0x84 and not self.isMaximized():  # WM_NCHITTEST
            rc=wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(msg.hWnd,ctypes.byref(rc))
            x=ctypes.c_short(msg.lParam & 65535).value
            y=ctypes.c_short((msg.lParam >> 16) & 65535).value
            border=round(6*self.devicePixelRatioF())
            left,right=x<rc.left+border,x>=rc.right-border
            top,bottom=y<rc.top+border,y>=rc.bottom-border
            if top: return True, 13 if left else 14 if right else 12
            if bottom: return True,16 if left else 17 if right else 15
            if left or right: return True,10 if left else 11
        return super().nativeEvent(kind,message)

class TitleBar(QWidget):
    def __init__(self, window, status):
        super().__init__()
        self.host = window
        status.setStyleSheet("color:#fff0dd;background:transparent")
        self.setObjectName("titlebar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2,0,0,0)
        brand = QLabel("SplitDesk")
        brand.setStyleSheet("font: bold 23px 'Segoe UI';color:#f4f0e9;background:transparent")
        label = QLabel("Stereo Mixer")
        label.setStyleSheet("font-size:13px;color:#f1e3d4;background:transparent")
        for widget in (brand, label, status):
            widget.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(brand)
        layout.addSpacing(4)
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(status)
        layout.addSpacing(10)
        for title, glyph, action in (("Minimize","−",window.showMinimized),("Maximize or restore","□",self.toggle),("Close","×",window.close)):
            b=QPushButton(glyph)
            b.setObjectName("frameKey")
            b.setFixedSize(32,28)
            b.setAccessibleName(title)
            b.setToolTip(title)
            b.clicked.connect(action)
            layout.addWidget(b)
    def toggle(self):
        if self.host.isMaximized(): self.host.showNormal()
        else: self.host.showMaximized()
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.toggle()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.host.windowHandle():
            self.host.windowHandle().startSystemMove()

class Needle(QWidget):
    def __init__(self):
        super().__init__()
        self.level=0
        self.face=None
        self.face_key=None
        self.setMinimumSize(94,58)
        self.setMaximumHeight(88)
        self.setAccessibleName("Output peak meter, dBFS")
    def set_peak(self,v):
        value=max(v,self.level*.71)
        value = value if value > .0004 else 0
        if abs(self.level-value)>.0001 or self.level!=0 and value==0:
            self.level=value
            self.update()
    def paintEvent(self,event):
        scale = self.devicePixelRatioF()
        key=(self.width(),self.height(),scale)
        if self.face_key!=key:
            self.face_key=key
            self.face=QPixmap(round(self.width()*scale), round(self.height()*scale))
            self.face.setDevicePixelRatio(scale)
            self.face.fill(Qt.transparent)
            painter=QPainter(self.face)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.scale(self.width()/140,self.height()/82)
            self.draw_face(painter)
            painter.end()
        p=QPainter(self)
        p.drawPixmap(0,0,self.face)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width()/140,self.height()/82)
        center=QPointF(70,86)
        pos=max(0,min(1,(20*math.log10(max(self.level,.001))+54)/54))
        rad=math.radians(-54+108*pos)
        end=center+QPointF(69*math.sin(rad),-69*math.cos(rad))
        p.setClipRect(QRectF(6,6,128,67))
        p.setPen(QPen(QColor(60,40,20,75),2.3))
        p.drawLine(center+QPointF(2,0),end+QPointF(2,1))
        p.setPen(QPen(QColor("#f25451"),1.6))
        p.drawLine(center,end)

    @staticmethod
    def draw_face(p):
        box(p,QRectF(1,1,138,79), QColor("#131411"),"#64655b",5)
        box(p,QRectF(5,5,130,69),linear(0,5,0,74,[(0,"#161617"),(.17,"#242326"),(.62,"#28272a"),(1,"#1c1b1d")]),"#151713",2)
        center=QPointF(70,86)
        def polar(a,r):
            rad=math.radians(a)
            return QPointF(center.x()+r*math.sin(rad),center.y()-r*math.cos(rad))
        for i in range(25):
            ang=-54+4.5*i
            p.setPen(QPen(QColor("#e25150" if i>=21 else "#dfd6cb"),1.8 if i%4==0 else .85))
            p.drawLine(polar(ang,61 if i%4==0 else 64),polar(ang,68))
        for angle, label in ((-42,"−48"),(-6,"−30"),(18,"−18"),(42,"−6")):
            pt=polar(angle,50)
            p.setFont(QFont("Consolas",6))
            p.setPen(QColor("#c8bdb2"))
            p.drawText(QRectF(pt.x()-11,pt.y()-4,22,9),Qt.AlignCenter,label)
        p.setFont(QFont("Consolas",7,QFont.Bold))
        p.drawText(QRectF(33,52,74,15),Qt.AlignCenter,"PEAK  dBFS")

class Fader(QSlider):
    def __init__(self):
        super().__init__(Qt.Vertical)
        # Keep the native hit area in step with the painted cap.
        self.setStyleSheet("QSlider::groove:vertical{margin:0px;width:8px} QSlider::handle:vertical{height:30px;margin:0 -14px}")
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        cx=w/2
        box(p,QRectF(cx-4,12,8,h-24),QColor("#121411"),"#66665c",3)
        for i in range(21):
            y=15+(h-30)*i/20
            tick=7 if i%5==0 else 3
            p.setPen(QColor("#a8a3a1" if i%5==0 else "#777474"))
            p.drawLine(QPointF(0,y),QPointF(tick,y))
        y=15+(h-30)*(100-self.value())/100
        face=QRectF(5,y-13,w-9,27)
        box(p,face.translated(1.5,3),QColor("#161917"),"#171a17",3)
        box(p,face,linear(0,y-13,0,y+14,[(0,"#808083"),(.14,"#535255"),(.44,"#373639"),(.50,"#434246"),(.54,"#525154"),(.85,"#333235"),(1,"#252427")]),"#66695e",3)
        p.fillRect(QRectF(6,y-1,w-11,2.4),QColor("#f0615c"))
        if self.hasFocus():
            p.setPen(QColor("#f15a57"))
            p.drawLine(6,int(y+11),w-6,int(y+11))

class Rotary(QDial):
    def __init__(self, band):
        super().__init__()
        self.band=band
        self.setFixedSize(69,69)
        self.setNotchesVisible(False)
        self.setWrapping(False)
        self.setToolTip("Drag vertically or use the arrow keys. Double-click for 0 dB.")
        self.drag_origin=None
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.setFocus()
            self.drag_origin=(event.globalPosition().y(),self.value())
            self.setSliderDown(True)
            event.accept()
    def mouseMoveEvent(self,event):
        if self.drag_origin is not None:
            y,v=self.drag_origin
            self.setValue(round(v+(y-event.globalPosition().y())/3))
    def mouseReleaseEvent(self,event):
        self.drag_origin=None
        self.setSliderDown(False)
    def mouseDoubleClickEvent(self,event):
        self.drag_origin=None
        self.setValue(0)
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(34.5,35)
        for i in range(13):
            p.save()
            p.rotate(-135+i*22.5)
            p.setPen(QPen(QColor("#e76760" if i==6 else "#a69e9b"),1.6 if i%3==0 else 1))
            p.drawLine(QPointF(0,-31),QPointF(0,-27.5))
            p.restore()
        p.setBrush(QColor("#101310"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(1,3),24.8,24.8)
        rim=linear(-17,-21,16,21,[(0,"#797779"),(.34,"#474648"),(.65,"#242325"),(1,"#141315")])
        p.setPen(QPen(QColor("#171916"),1))
        p.setBrush(rim)
        p.drawEllipse(QPointF(0,0),24,24)
        for i in range(36):
            p.save()
            p.rotate(10*i)
            p.setPen(QPen(QColor(9,12,10,110),1.3))
            p.drawLine(QPointF(0,-23),QPointF(0,-20))
            p.restore()
        body=QRadialGradient(-8,-10,39)
        body.setColorAt(0,QColor("#535153"))
        body.setColorAt(.75,QColor("#302f31"))
        body.setColorAt(1,QColor("#212022"))
        p.setBrush(body)
        p.setPen(QPen(QColor("#777173" if not self.hasFocus() else "#dc484b"),1))
        p.drawEllipse(QPointF(0,0),19,19)
        p.rotate(self.value()*135/12)
        p.setPen(QPen(QColor("#ff5a58"),2.8,Qt.SolidLine,Qt.RoundCap))
        p.drawLine(QPointF(0,-9),QPointF(0,-18))
