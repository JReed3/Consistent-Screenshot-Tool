import sys
import os
import time
import json

from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import (
    QPainter,
    QPen,
    QCursor,
    QGuiApplication,
    QKeySequence,
    QPixmap,
    QColor,
)
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFileDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QShortcut,
)

CONFIG_FILE = "config.txt"

class Overlay(QWidget):
    def __init__(self, width, height, save_folder, on_closed):
        super().__init__(
            None,
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
        )
        self.w, self.h = width, height
        self.save_folder = save_folder
        self.on_closed = on_closed

        print(f"[DEBUG] Overlay init: size=({self.w}×{self.h}), folder='{self.save_folder}'")

        # Full-screen translucent overlay (per-pixel)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.showFullScreen()
        print("[DEBUG] Overlay shown full-screen")

        # Hide system cursor
        blank = QPixmap(1, 1); blank.fill(Qt.transparent)
        blank_cursor = QCursor(blank)
        QApplication.setOverrideCursor(blank_cursor)
        self.setCursor(blank_cursor)
        print("[DEBUG] System cursor hidden")

        # Grab mouse & keyboard once so the overlay never loses focus
        self.grabMouse()
        self.grabKeyboard()
        print("[DEBUG] Mouse and keyboard grabbed by overlay")

        # Shortcuts to close overlay
        QShortcut(QKeySequence("Ctrl+G"), self, context=Qt.ApplicationShortcut).activated.connect(self.close)
        QShortcut(QKeySequence("Escape"), self, context=Qt.ApplicationShortcut).activated.connect(self.close)
        print("[DEBUG] Shortcuts for Ctrl+G and Esc set")

        # Timer for smooth repaint
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(0)
        print("[DEBUG] Repaint timer started")

    def paintEvent(self, event):
        painter = QPainter(self)
        # 1) dim everything underneath by drawing a semi-transparent black fill
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        # 2) draw the red capture rectangle
        painter.setPen(QPen(Qt.red, 3))
        gp = QCursor.pos()
        lp = self.mapFromGlobal(gp)
        x = lp.x() - self.w // 2 + 1
        y = lp.y() - self.h // 2 + 1
        painter.drawRect(QRect(x, y, self.w, self.h))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            gp = QCursor.pos()
            x = gp.x() - self.w // 2
            y = gp.y() - self.h // 2
            print(f"[DEBUG] Click at global ({gp.x()},{gp.y()}), region=({x},{y},{self.w},{self.h})")
            img = QGuiApplication.primaryScreen().grabWindow(0, x, y, self.w, self.h)
            timestamp = int(time.time())
            filename = f"screenshot_{timestamp}.png"
            path = os.path.join(self.save_folder, filename)
            img.save(path)
            print(f"[DEBUG] Screenshot saved: {filename}")
            event.accept()  # consume the click, keep overlay up

    def closeEvent(self, event):
        print("[DEBUG] Closing overlay")
        self._timer.stop()
        self.releaseMouse()
        self.releaseKeyboard()
        QApplication.restoreOverrideCursor()
        print("[DEBUG] Restored cursor, released grabs, timer stopped")
        self.on_closed()
        super().closeEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Consistent Screenshot Tool")
        self.setFixedSize(450, 150)

        self.save_folder = ""
     
        self.overlay = None
        print("[DEBUG] MainWindow init")

        self._build_ui()
        self._load_config()

        QShortcut(QKeySequence("Ctrl+G"), self, context=Qt.ApplicationShortcut).activated.connect(self.toggle_overlay)
        print("[DEBUG] Ctrl+G shortcut for toggle set")

    def _build_ui(self):
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)

        # Folder picker
        row = QHBoxLayout()
        row.addWidget(QLabel("Save Folder:"))
        self.folder_edit = QLineEdit(); self.folder_edit.setReadOnly(True)
        row.addWidget(self.folder_edit, 1)
        btn = QPushButton("📁"); btn.setFixedWidth(30)
        btn.clicked.connect(self.choose_folder)
        row.addWidget(btn)
        layout.addLayout(row)

        # Width/Height inputs
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Width:"))
        self.w_edit = QLineEdit(str(self.width)); self.w_edit.setFixedWidth(60)
        self.w_edit.editingFinished.connect(lambda: self._save_size("width"))
        row2.addWidget(self.w_edit)
        row2.addSpacing(20)
        row2.addWidget(QLabel("Height:"))
        self.h_edit = QLineEdit(str(self.height)); self.h_edit.setFixedWidth(60)
        self.h_edit.editingFinished.connect(lambda: self._save_size("height"))
        row2.addWidget(self.h_edit)
        layout.addLayout(row2)

        # Status label
        self.status = QLabel("Select a folder and set size, then Ctrl+G to preview")
        layout.addStretch()
        layout.addWidget(self.status)
        print("[DEBUG] UI built")

    def choose_folder(self):
        fld = QFileDialog.getExistingDirectory(self, "Select Save Folder")
        if fld:
            self.save_folder = fld
            self.folder_edit.setText(fld)
            self._save_config()
            self.status.setText("Folder set! Now press Ctrl+G to preview")
            print(f"[DEBUG] Folder chosen: {fld}")

    def _save_size(self, key):
        try:
            val = int(self.w_edit.text() if key == "width" else self.h_edit.text())
            old = (self.width, self.height)
            if key == "width":
                self.width = val
            else:
                self.height = val
            self._save_config()
            print(f"[DEBUG] Size changed {key}: {old} → ({self.width}, {self.height})")
        except ValueError:
            print("[DEBUG] Invalid size input, ignoring")

    def _save_config(self):
        data = {"folder": self.save_folder, "width": self.width, "height": self.height}
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
        print("[DEBUG] Config saved")

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            print("[DEBUG] No config file found")
            return
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        fld = data.get("folder", "")
        if os.path.isdir(fld):
            self.save_folder = fld
            self.folder_edit.setText(fld)
            print(f"[DEBUG] Loaded folder: {fld}")
        self.width = int(data.get("width", self.width))
        self.height = int(data.get("height", self.height))
        self.w_edit.setText(str(self.width))
        self.h_edit.setText(str(self.height))
        print(f"[DEBUG] Loaded size: ({self.width}, {self.height})")

    def toggle_overlay(self):
        if self.overlay and self.overlay.isVisible():
            print("[DEBUG] Toggling overlay OFF")
            self.overlay.close()
        else:
            if not self.save_folder:
                self.status.setText("Please select a folder first!")
                print("[DEBUG] No folder selected, cannot open overlay")
                return
            print("[DEBUG] Toggling overlay ON")
            self.hide()
            self.overlay = Overlay(
                self.width, self.height,
                self.save_folder,
                on_closed=self._overlay_closed
            )

    def _overlay_closed(self):
        self.show()
        self.status.setText("Preview off. Ctrl+G to preview again")
        print("[DEBUG] Returned to main window")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    print("[DEBUG] Application started")
    sys.exit(app.exec_())
