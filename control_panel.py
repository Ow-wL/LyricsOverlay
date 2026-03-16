"""
control_panel.py
메인 컨트롤 패널.
- 창 선택 드롭다운
- 듀얼 모니터 지원 RegionSelector
- 텍스트 색상 / 텍스트 불투명도
- 배경 색상 / 배경 불투명도
- 임계값 모드 & 오프셋 (글씨 인식 정확도 조절)
- 형태학 보정 크기 (글자 두께)
- 반전 모드 (밝은 배경/어두운 글씨)
- 창 불투명도 (전체 밝기)
- 클릭 통과 모드
- FPS 선택 & 실시간 FPS 표시
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSlider, QCheckBox, QGroupBox,
    QSizePolicy, QApplication, QColorDialog, QFrame,
)
from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QColor, QFont

from window_enumerator import WindowEnumerator, WindowInfo
from region_selector import RegionSelector
from capture_engine import CaptureEngine
from overlay_window import OverlayWindow
from text_processor import ProcessorSettings


# ─────────────────────────────────────────────────────────────────────────────
#  색상 선택 버튼
# ─────────────────────────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    """현재 색상을 배경으로 표시하고, 클릭 시 QColorDialog 를 여는 버튼."""

    def __init__(self, color: tuple[int, int, int] = (255, 255, 255)) -> None:
        super().__init__()
        self._color = color
        self.setFixedSize(36, 26)
        self._refresh_style()
        self.clicked.connect(self._pick)

    def get_color(self) -> tuple[int, int, int]:
        return self._color

    def set_color(self, rgb: tuple[int, int, int]) -> None:
        self._color = rgb
        self._refresh_style()

    def _pick(self) -> None:
        initial = QColor(*self._color)
        chosen  = QColorDialog.getColor(initial, self, "색상 선택")
        if chosen.isValid():
            self._color = (chosen.red(), chosen.green(), chosen.blue())
            self._refresh_style()

    def _refresh_style(self) -> None:
        r, g, b = self._color
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        text_col = "#000" if luma > 128 else "#fff"
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: {text_col};"
            f"border: 1px solid #555; border-radius: 4px;"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  슬라이더 + 레이블 묶음
# ─────────────────────────────────────────────────────────────────────────────

def _labeled_slider(
    label: str, lo: int, hi: int, val: int, suffix: str = ""
) -> tuple[QHBoxLayout, QSlider, QLabel]:
    row   = QHBoxLayout()
    lbl   = QLabel(label)
    lbl.setFixedWidth(110)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(lo, hi)
    slider.setValue(val)
    val_lbl = QLabel(f"{val}{suffix}")
    val_lbl.setFixedWidth(36)
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v}{suffix}"))
    row.addWidget(lbl)
    row.addWidget(slider)
    row.addWidget(val_lbl)
    return row, slider, val_lbl


# ─────────────────────────────────────────────────────────────────────────────
#  ControlPanel
# ─────────────────────────────────────────────────────────────────────────────

class ControlPanel(QWidget):

    def __init__(self) -> None:
        super().__init__()
        self._windows: list[WindowInfo] = []
        self._selected_hwnd: int | None = None
        self._capture_region: QRect | None = None
        self._engine:  CaptureEngine | None = None
        self._overlay: OverlayWindow | None = None
        self._selector: RegionSelector | None = None
        self._frame_count = 0
        self._fps_timer = QTimer(self)

        self._build_ui()
        self._refresh_windows()
        self._fps_timer.timeout.connect(self._update_fps_label)
        self._fps_timer.start(1000)

    # ═══════════════════════════════════════════════════════════════════
    #  UI 구성
    # ═══════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        self.setWindowTitle("🎵 Lyrics Overlay – 컨트롤 패널")
        self.setMinimumWidth(460)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 14, 16, 14)

        # 타이틀
        title = QLabel("🎵  Lyrics Overlay")
        title.setObjectName("title")
        root.addWidget(title)

        root.addWidget(self._build_source_group())
        root.addWidget(self._build_region_group())
        root.addWidget(self._build_text_group())
        root.addWidget(self._build_bg_group())
        root.addWidget(self._build_threshold_group())
        root.addWidget(self._build_display_group())
        root.addLayout(self._build_controls())
        root.addLayout(self._build_status_bar())

    # ── 1. 소스 선택 ────────────────────────────────────────────────────
    def _build_source_group(self) -> QGroupBox:
        box = QGroupBox("1. 음악 플레이어 창 선택")
        lay = QHBoxLayout(box)
        self._window_combo = QComboBox()
        self._window_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._window_combo.currentIndexChanged.connect(self._on_window_selected)
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(34)
        refresh_btn.setToolTip("창 목록 새로 고침")
        refresh_btn.clicked.connect(self._refresh_windows)
        lay.addWidget(self._window_combo)
        lay.addWidget(refresh_btn)
        return box

    # ── 2. 영역 선택 ────────────────────────────────────────────────────
    def _build_region_group(self) -> QGroupBox:
        box = QGroupBox("2. 가사 영역 선택  (듀얼 모니터 지원)")
        lay = QVBoxLayout(box)
        self._region_label = QLabel("영역이 선택되지 않았습니다.")
        self._region_label.setObjectName("dimLabel")
        btn = QPushButton("🔲  드래그로 영역 선택…")
        btn.clicked.connect(self._start_region_selection)
        lay.addWidget(self._region_label)
        lay.addWidget(btn)
        return box

    # ── 3. 텍스트 색상 ──────────────────────────────────────────────────
    def _build_text_group(self) -> QGroupBox:
        box = QGroupBox("3. 텍스트 색상 & 불투명도")
        lay = QVBoxLayout(box)

        # 색상 피커
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("텍스트 색상"))
        self._text_color_btn = ColorButton((255, 255, 255))
        self._text_color_btn.clicked.connect(self._on_settings_changed)  # 재연결은 ColorButton 내부에 있으나 변경 감지를 위해 추가
        # ColorButton.clicked → _pick → _refresh_style. 실시간 반영용 타이머 방식 사용
        color_row.addWidget(self._text_color_btn)
        color_row.addStretch()
        lay.addLayout(color_row)

        # 불투명도 슬라이더
        row, self._text_alpha_slider, _ = _labeled_slider("텍스트 불투명도", 0, 255, 255)
        self._text_alpha_slider.valueChanged.connect(self._on_settings_changed)
        lay.addLayout(row)
        return box

    # ── 4. 배경 색상 ────────────────────────────────────────────────────
    def _build_bg_group(self) -> QGroupBox:
        box = QGroupBox("4. 배경 색상 & 불투명도")
        lay = QVBoxLayout(box)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("배경 색상"))
        self._bg_color_btn = ColorButton((0, 0, 0))
        color_row.addWidget(self._bg_color_btn)
        color_row.addStretch()
        lay.addLayout(color_row)

        row, self._bg_alpha_slider, _ = _labeled_slider("배경 불투명도", 0, 255, 80)
        self._bg_alpha_slider.valueChanged.connect(self._on_settings_changed)
        lay.addLayout(row)
        return box

    # ── 5. 임계값 / 인식 설정 ────────────────────────────────────────────
    def _build_threshold_group(self) -> QGroupBox:
        box = QGroupBox("5. 글씨 인식 설정")
        lay = QVBoxLayout(box)

        # 임계값 모드
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("임계값 방식"))
        self._thresh_mode = QComboBox()
        self._thresh_mode.addItems(["adaptive (적응형)", "otsu (자동)"])
        self._thresh_mode.currentIndexChanged.connect(self._on_settings_changed)
        mode_row.addWidget(self._thresh_mode)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # 임계값 오프셋
        row, self._thresh_offset_slider, _ = _labeled_slider("민감도 오프셋", -50, 50, -10)
        self._thresh_offset_slider.valueChanged.connect(self._on_settings_changed)
        lay.addLayout(row)

        # 적응형 블록 크기
        row2, self._block_size_slider, _ = _labeled_slider("블록 크기", 3, 51, 15)
        self._block_size_slider.valueChanged.connect(self._on_settings_changed)
        lay.addLayout(row2)

        # 형태학 커널
        row3, self._morph_slider, _ = _labeled_slider("글자 두께 보정", 0, 5, 1)
        self._morph_slider.valueChanged.connect(self._on_settings_changed)
        lay.addLayout(row3)

        # 반전 모드
        self._invert_cb = QCheckBox("반전 모드  (밝은 배경 / 어두운 글씨)")
        self._invert_cb.stateChanged.connect(self._on_settings_changed)
        lay.addWidget(self._invert_cb)

        return box

    # ── 6. 표시 설정 ────────────────────────────────────────────────────
    def _build_display_group(self) -> QGroupBox:
        box = QGroupBox("6. 오버레이 표시 설정")
        lay = QVBoxLayout(box)

        row, self._win_opacity_slider, _ = _labeled_slider("창 불투명도", 10, 100, 100, "%")
        self._win_opacity_slider.valueChanged.connect(self._on_win_opacity_changed)
        lay.addLayout(row)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("목표 FPS"))
        self._fps_combo = QComboBox()
        for fps in ("15", "24", "30", "60"):
            self._fps_combo.addItem(fps)
        self._fps_combo.setCurrentText("30")
        fps_row.addWidget(self._fps_combo)
        fps_row.addStretch()
        lay.addLayout(fps_row)

        self._click_through_cb = QCheckBox("클릭 통과 모드  (게임 중 마우스 간섭 없음)")
        self._click_through_cb.stateChanged.connect(self._on_click_through_changed)
        lay.addWidget(self._click_through_cb)

        return box

    # ── 컨트롤 버튼 ─────────────────────────────────────────────────────
    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._start_btn = QPushButton("▶  오버레이 시작")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.clicked.connect(self._start_overlay)
        self._stop_btn = QPushButton("■  정지")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_overlay)
        row.addWidget(self._start_btn)
        row.addWidget(self._stop_btn)
        return row

    # ── 상태 바 ─────────────────────────────────────────────────────────
    def _build_status_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._status_lbl = QLabel("준비")
        self._status_lbl.setObjectName("dimLabel")
        self._fps_label = QLabel("FPS: —")
        self._fps_label.setObjectName("dimLabel")
        row.addWidget(self._status_lbl)
        row.addStretch()
        row.addWidget(self._fps_label)
        return row

    # ═══════════════════════════════════════════════════════════════════
    #  슬롯
    # ═══════════════════════════════════════════════════════════════════

    def _refresh_windows(self) -> None:
        self._windows = WindowEnumerator.get_all_windows()
        self._window_combo.clear()
        self._window_combo.addItem("— 창을 선택하세요 —", userData=None)
        for w in self._windows:
            self._window_combo.addItem(w.title[:80], userData=w.hwnd)

    def _on_window_selected(self, idx: int) -> None:
        self._selected_hwnd = self._window_combo.itemData(idx)

    # ── 영역 선택 ────────────────────────────────────────────────────────
    def _start_region_selection(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.selection_cancelled.connect(
            lambda: self._set_status("영역 선택이 취소되었습니다.")
        )
        self._selector.show()

    def _on_region_selected(self, rect: QRect) -> None:
        self._capture_region = rect
        self._region_label.setText(
            f"({rect.left()}, {rect.top()})  →  {rect.width()} × {rect.height()} px"
        )
        self._set_status("영역 설정 완료. 시작 버튼을 누르세요.")

    # ── 설정 변경 → 엔진에 즉시 반영 ───────────────────────────────────
    def _on_settings_changed(self, *_) -> None:
        if self._engine:
            self._engine.update_settings(self._build_processor_settings())

    def _on_win_opacity_changed(self, value: int) -> None:
        if self._overlay:
            self._overlay.set_opacity(value / 100.0)

    def _on_click_through_changed(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        if self._overlay:
            self._overlay.set_click_through(enabled)

    # ── 오버레이 시작 / 정지 ────────────────────────────────────────────
    def _start_overlay(self) -> None:
        if self._capture_region is None:
            self._set_status("⚠  먼저 영역을 선택해 주세요.")
            return

        self._stop_overlay()

        opacity     = self._win_opacity_slider.value() / 100.0
        click_through = self._click_through_cb.isChecked()
        fps         = int(self._fps_combo.currentText())
        settings    = self._build_processor_settings()

        self._overlay = OverlayWindow(opacity=opacity, click_through=click_through)
        self._overlay.move(100, 100)
        self._overlay.show()

        self._engine = CaptureEngine(
            region=self._capture_region,
            target_fps=fps,
            settings=settings,
        )
        self._engine.frame_ready.connect(self._on_frame_ready)
        self._engine.error_occurred.connect(self._on_capture_error)
        self._engine.start()

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._set_status("캡처 중…")

        # 색상 버튼 클릭 후 실시간 반영을 위해 주기적으로 settings 동기화
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._on_settings_changed)
        self._sync_timer.start(200)

    def _stop_overlay(self) -> None:
        if hasattr(self, "_sync_timer"):
            self._sync_timer.stop()
        if self._engine:
            self._engine.stop()
            self._engine = None
        if self._overlay:
            self._overlay.close()
            self._overlay = None
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._fps_label.setText("FPS: —")
        self._set_status("정지됨.")

    def _on_frame_ready(self, image) -> None:
        self._frame_count += 1
        if self._overlay:
            self._overlay.update_frame(image)

    def _on_capture_error(self, msg: str) -> None:
        self._set_status(f"캡처 오류: {msg}")

    def _update_fps_label(self) -> None:
        if self._engine and self._engine.isRunning():
            self._fps_label.setText(f"FPS: {self._frame_count}")
        self._frame_count = 0

    # ═══════════════════════════════════════════════════════════════════
    #  ProcessorSettings 빌더
    # ═══════════════════════════════════════════════════════════════════

    def _build_processor_settings(self) -> ProcessorSettings:
        mode_idx = self._thresh_mode.currentIndex()
        mode_str = "otsu" if mode_idx == 1 else "adaptive"

        # block_size 는 홀수여야 함
        bs = self._block_size_slider.value()
        bs = bs if bs % 2 == 1 else bs + 1

        return ProcessorSettings(
            text_color        = self._text_color_btn.get_color(),
            text_alpha        = self._text_alpha_slider.value(),
            bg_color          = self._bg_color_btn.get_color(),
            bg_alpha          = self._bg_alpha_slider.value(),
            threshold_mode    = mode_str,
            threshold_offset  = self._thresh_offset_slider.value(),
            block_size        = bs,
            morph_size        = self._morph_slider.value(),
            invert            = self._invert_cb.isChecked(),
        )

    # ═══════════════════════════════════════════════════════════════════
    #  헬퍼
    # ═══════════════════════════════════════════════════════════════════

    def _set_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)

    def closeEvent(self, event) -> None:
        self._stop_overlay()
        QApplication.quit()
        event.accept()

    # ═══════════════════════════════════════════════════════════════════
    #  스타일시트
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _stylesheet() -> str:
        return """
        QWidget {
            background-color: #12121f;
            color: #ddddf5;
            font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
            font-size: 13px;
        }
        QGroupBox {
            border: 1px solid #2a2a50;
            border-radius: 7px;
            margin-top: 10px;
            padding: 8px 10px 10px 10px;
            color: #7777bb;
            font-size: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QLabel#title {
            font-size: 18px;
            font-weight: bold;
            color: #9999ff;
            padding-bottom: 2px;
        }
        QLabel#dimLabel {
            color: #555577;
            font-size: 11px;
        }
        QComboBox {
            background-color: #1a1a30;
            border: 1px solid #2a2a55;
            border-radius: 4px;
            padding: 3px 8px;
            color: #ddddf5;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView {
            background: #1a1a30;
            selection-background-color: #3333aa;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: #2a2a50;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #7777ff;
            width: 14px; height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        QSlider::sub-page:horizontal {
            background: #5555dd;
            border-radius: 2px;
        }
        QCheckBox { spacing: 6px; }
        QCheckBox::indicator {
            width: 14px; height: 14px;
            border: 1px solid #4444aa;
            border-radius: 3px;
            background: #1a1a30;
        }
        QCheckBox::indicator:checked { background: #5555ff; }
        QPushButton {
            background-color: #1a1a35;
            border: 1px solid #3a3a88;
            border-radius: 5px;
            padding: 6px 14px;
            color: #aaaaff;
        }
        QPushButton:hover  { background-color: #252560; border-color: #7777ff; }
        QPushButton:disabled { color: #333355; border-color: #1e1e40; }
        QPushButton#startBtn {
            background-color: #0e2e0e; border-color: #33aa33; color: #66ff66;
        }
        QPushButton#startBtn:hover { background-color: #1a4a1a; }
        QPushButton#stopBtn {
            background-color: #2e0e0e; border-color: #aa3333; color: #ff6666;
        }
        QPushButton#stopBtn:hover { background-color: #4a1a1a; }
        """
