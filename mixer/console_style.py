STYLE = """
QMainWindow {background:#141415}
QWidget {color:#e8e3df;background:transparent}
QFrame#panel {background:qlineargradient(x1:0,y1:0,x2:0.22,y2:1,stop:0 #28282a,stop:0.06 #212123,stop:0.9 #1d1d1f,stop:1 #171719);border:1px solid #101011;border-top-color:#4b494b;border-left-color:#333235;border-radius:5px}
QFrame#track {background:#232325;border:1px solid #49474a;border-radius:3px}
QPushButton,QTabBar::tab {color:#e3dcd8;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4b494b,stop:0.12 #333235,stop:0.9 #323133,stop:1 #242325);border:1px solid #181b16;border-top-color:#6a6566;border-left-color:#535050;border-radius:3px;padding:4px 11px;min-height:20px}
QPushButton:hover,QTabBar::tab:hover {color:#ffdbd7;border-top-color:#ca6561}
QPushButton:checked,QPushButton:pressed,QTabBar::tab:selected,QPushButton#play:enabled {color:#fff4ed;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #c14b49,stop:0.4 #9c302f,stop:1 #702021);border:1px solid #201f19;border-top-color:#e07670;font-weight:bold}
QPushButton:disabled {color:#938c8a;border-color:#302d30;background:#272628}
QPushButton#frameKey {padding:0;min-height:0;font:16px 'Segoe UI';border-radius:2px}
QTabWidget::pane {border:0;border-top:1px solid #494347}
QTabBar::tab {margin-right:3px;padding:4px 15px}
QSlider::groove:horizontal {height:6px;background:#121113;border:1px solid #484247;border-radius:2px}
QSlider::sub-page:horizontal {background:#aa4345}
QSlider::handle:horizontal {width:13px;margin:-5px 0;background:#bab0ad;border:1px solid #696163;border-radius:2px}
QScrollArea {border:none;background:transparent}
QScrollBar:vertical {background:#1b191b;width:8px}
QScrollBar::handle:vertical {background:#655e61;min-height:20px;border-radius:2px}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0}
"""
