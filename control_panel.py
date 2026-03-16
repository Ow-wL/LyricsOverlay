"""
control_panel.py
Main control panel window.
Provides:
  - Window selector dropdown
  - "Select Region" button → launches RegionSelector
  - Start / Stop capture
  - Opacity slider
  - Click-through toggle
  - FPS display
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSlider, QCheckBox, QGroupBox, QStatusBar,
    QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QFont

from window_enumerator import WindowEnumerator, WindowInfo
from region_selector import RegionSelector
from capture_engine import CaptureEngine
from overlay_window import OverlayWindow


class ControlPanel(QWidget):
    """Top-level control panel for the lyrics overlay."""

    def __init__(self) -> None:
        super().__init__()
        self._windows: list[WindowInfo] = []
        self._selected_hwnd: int | None = None
        self._capture_region: QRect | None = None
        self._engine: CaptureEngine | None = None
        self._overlay: OverlayWindow | None = None
        self._frame_count = 0
        self._fps_timer = QTimer(self)
        self._selector: RegionSelector | None = None   # ← GC 방지용 참조 보관

        self._build_ui()
        self._refresh_windows()
        self._fps_timer.timeout.connect(self._update_fps_label)
        self._fps_timer.start(1000)

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setWindowTitle("Lyrics Overlay – Control Panel")
        self.setMinimumWidth(420)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Title ──────────────────────────────────────────────────────
        title = QLabel("🎵 Lyrics Overlay")
        title.setObjectName("title")
        root.addWidget(title)

        # ── Source selection ───────────────────────────────────────────
        src_box = QGroupBox("1. Select Music Player Window")
        src_layout = QHBoxLayout(src_box)
        self._window_combo = QComboBox()
        self._window_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._window_combo.currentIndexChanged.connect(self._on_window_selected)
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(36)
        refresh_btn.setToolTip("Refresh window list")
        refresh_btn.clicked.connect(self._refresh_windows)
        src_layout.addWidget(self._window_combo)
        src_layout.addWidget(refresh_btn)
        root.addWidget(src_box)

        # ── Region selection ───────────────────────────────────────────
        region_box = QGroupBox("2. Select Lyrics Region")
        region_layout = QVBoxLayout(region_box)
        self._region_label = QLabel("No region selected")
        self._region_label.setObjectName("dimLabel")
        select_region_btn = QPushButton("🔲  Draw Region…")
        select_region_btn.clicked.connect(self._start_region_selection)
        region_layout.addWidget(self._region_label)
        region_layout.addWidget(select_region_btn)
        root.addWidget(region_box)

        # ── Overlay settings ───────────────────────────────────────────
        settings_box = QGroupBox("3. Overlay Settings")
        settings_layout = QVBoxLayout(settings_box)

        # Opacity
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity:"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(85)
        self._opacity_slider.setTickInterval(10)
        self._opacity_value_label = QLabel("85%")
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_value_label)
        settings_layout.addLayout(opacity_row)

        # FPS
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("Target FPS:"))
        self._fps_combo = QComboBox()
        for fps in ("15", "24", "30", "60"):
            self._fps_combo.addItem(fps)
        self._fps_combo.setCurrentText("30")
        fps_row.addWidget(self._fps_combo)
        fps_row.addStretch()
        settings_layout.addLayout(fps_row)

        # Click-through
        self._click_through_cb = QCheckBox("Click-through mode (overlay ignores mouse)")
        self._click_through_cb.stateChanged.connect(self._on_click_through_changed)
        settings_layout.addWidget(self._click_through_cb)

        root.addWidget(settings_box)

        # ── Controls ───────────────────────────────────────────────────
        ctrl_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  Start Overlay")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.clicked.connect(self._start_overlay)
        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_overlay)
        ctrl_row.addWidget(self._start_btn)
        ctrl_row.addWidget(self._stop_btn)
        root.addLayout(ctrl_row)

        # ── Status bar ─────────────────────────────────────────────────
        self._status = QLabel("Ready")
        self._status.setObjectName("dimLabel")
        self._fps_label = QLabel("FPS: —")
        self._fps_label.setObjectName("dimLabel")
        status_row = QHBoxLayout()
        status_row.addWidget(self._status)
        status_row.addStretch()
        status_row.addWidget(self._fps_label)
        root.addLayout(status_row)

    # ------------------------------------------------------------------ #
    #  Slots                                                               #
    # ------------------------------------------------------------------ #

    def _refresh_windows(self) -> None:
        self._windows = WindowEnumerator.get_all_windows()
        self._window_combo.clear()
        self._window_combo.addItem("— choose window —", userData=None)
        for w in self._windows:
            self._window_combo.addItem(w.title[:80], userData=w.hwnd)

    def _on_window_selected(self, index: int) -> None:
        hwnd = self._window_combo.itemData(index)
        self._selected_hwnd = hwnd

    def _start_region_selection(self) -> None:
        # 로컬 변수로 두면 함수 종료 즉시 GC가 소멸 → self에 저장해야 함
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.selection_cancelled.connect(
            lambda: self._set_status("Region selection cancelled.")
        )
        self._selector.showFullScreen()   # show() 대신 showFullScreen()으로 확실히 전체화면 확보
        self._selector.raise_()
        self._selector.activateWindow()

    def _on_region_selected(self, rect: QRect) -> None:
        self._capture_region = rect
        self._region_label.setText(
            f"({rect.left()}, {rect.top()})  {rect.width()} × {rect.height()} px"
        )
        self._set_status("Region set. Ready to start.")

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_value_label.setText(f"{value}%")
        if self._overlay:
            self._overlay.set_opacity(value / 100.0)

    def _on_click_through_changed(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        if self._overlay:
            self._overlay.set_click_through(enabled)

    def _start_overlay(self) -> None:
        if self._capture_region is None:
            self._set_status("⚠  Please select a region first.")
            return

        # Stop any existing session cleanly
        self._stop_overlay()

        opacity = self._opacity_slider.value() / 100.0
        click_through = self._click_through_cb.isChecked()
        fps = int(self._fps_combo.currentText())

        self._overlay = OverlayWindow(opacity=opacity, click_through=click_through)
        self._overlay.move(100, 100)
        self._overlay.show()

        self._engine = CaptureEngine(region=self._capture_region, target_fps=fps)
        self._engine.frame_ready.connect(self._on_frame_ready)
        self._engine.error_occurred.connect(self._on_capture_error)
        self._engine.start()

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._set_status("Capturing…")

    def _stop_overlay(self) -> None:
        if self._engine:
            self._engine.stop()
            self._engine = None
        if self._overlay:
            self._overlay.close()
            self._overlay = None
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._fps_label.setText("FPS: —")
        self._set_status("Stopped.")

    def _on_frame_ready(self, image) -> None:
        self._frame_count += 1
        if self._overlay:
            self._overlay.update_frame(image)

    def _on_capture_error(self, msg: str) -> None:
        self._set_status(f"Capture error: {msg}")

    def _update_fps_label(self) -> None:
        if self._engine and self._engine.isRunning():
            self._fps_label.setText(f"FPS: {self._frame_count}")
        self._frame_count = 0

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def closeEvent(self, event) -> None:
        self._stop_overlay()
        QApplication.quit()
        event.accept()

    # ------------------------------------------------------------------ #
    #  Stylesheet                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _stylesheet() -> str:
        return """
        QWidget {
            background-color: #1a1a2e;
            color: #e0e0f0;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }
        QGroupBox {
            border: 1px solid #30305a;
            border-radius: 6px;
            margin-top: 8px;
            padding: 8px;
            color: #8888bb;
            font-size: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }
        QLabel#title {
            font-size: 20px;
            font-weight: bold;
            color: #a0a0ff;
            padding-bottom: 4px;
        }
        QLabel#dimLabel {
            color: #666688;
            font-size: 11px;
        }
        QComboBox, QSlider, QCheckBox {
            background-color: #16213e;
            border: 1px solid #30305a;
            border-radius: 4px;
            padding: 3px 6px;
            color: #e0e0f0;
        }
        QComboBox::drop-down { border: none; }
        QPushButton {
            background-color: #16213e;
            border: 1px solid #4444aa;
            border-radius: 5px;
            padding: 6px 14px;
            color: #c0c0ff;
        }
        QPushButton:hover { background-color: #22226e; border-color: #8888ff; }
        QPushButton:disabled { color: #444466; border-color: #222244; }
        QPushButton#startBtn {
            background-color: #1a3a1a;
            border-color: #44aa44;
            color: #88ff88;
        }
        QPushButton#startBtn:hover { background-color: #225522; }
        QPushButton#stopBtn {
            background-color: #3a1a1a;
            border-color: #aa4444;
            color: #ff8888;
        }
        QPushButton#stopBtn:hover { background-color: #552222; }
        QSlider::groove:horizontal {
            height: 4px;
            background: #30305a;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #8888ff;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        """
