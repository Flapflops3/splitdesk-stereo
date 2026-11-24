"""Desktop entry point. The first launch prompts for device names and endpoints."""
import os
import sys
import traceback
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"]="1"
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"mixer"))
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import Qt
app=QApplication(sys.argv)
app.setAttribute(Qt.AA_DontUseNativeDialogs,True)
try:
    from devices import CONFIG, configure
    if not CONFIG.exists() and not configure():
        sys.exit(0)
    from mixer import main
    main()
except Exception:
    (ROOT/"startup.log").write_text(traceback.format_exc(),encoding="utf-8")
    QMessageBox.critical(None,"SplitDesk Stereo","Startup failed. See startup.log in the installation folder.")
    raise
