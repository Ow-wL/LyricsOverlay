"""설정 페이지 — 카테고리 사이드바 방식.

카테고리:
  0 🎨 외관   — 미리보기 / 활성화 / 프리셋 / 스타일 세부
  1 ⚙️ 동작   — 고스트 / 이동 / 크기 / 곡정보 / ROI
  2 ⌨️ 단축키 — 앱 제어 / 미디어 컨트롤
  3 💾 시스템 — 데이터 경로
"""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtGui import QFont  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QFontDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.theme import UIConfig
from gui.widgets.card import Card, PresetItem, StylePreview
from gui.widgets.hotkey_edit import HotkeyEdit
from overlay.config_manager import OverlayConfigManager

_ACCENT = "#7C4DFF"
_ACCENT_BG = "rgba(124,77,255,0.12)"

_CATEGORIES = [
    ("🎨", "외관"),
    ("⚙️", "동작"),
    ("⌨️", "단축키"),
    ("💾", "시스템"),
]


# ------------------------------------------------------------------ #
# 사이드바 네비게이션 버튼
# ------------------------------------------------------------------ #


class _NavBtn(QPushButton):
    """사이드바 카테고리 버튼."""

    _SS_ACTIVE = f"""
        QPushButton {{
            background-color: {_ACCENT_BG};
            color: {_ACCENT};
            border: none;
            border-left: 3px solid {_ACCENT};
            border-radius: 0px;
            text-align: left;
            padding: 0 0 0 16px;
            font-size: 15px;
            font-weight: 700;
        }}
    """
    _SS_IDLE = """
        QPushButton {
            background-color: transparent;
            color: #828282;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 0px;
            text-align: left;
            padding: 0 0 0 16px;
            font-size: 15px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: rgba(0,0,0,0.05);
            color: #333;
        }
    """

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}   {label}")
        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)
        self.setActive(False)

    def setActive(self, active: bool) -> None:
        self.setStyleSheet(self._SS_ACTIVE if active else self._SS_IDLE)


# ------------------------------------------------------------------ #
# 메인 설정 페이지
# ------------------------------------------------------------------ #


class SettingPage(QWidget):
    """오버레이 스타일 및 동작을 설정하는 페이지."""

    settings_changed = Signal()
    hotkeys_changed = Signal()

    def __init__(self, config_manager: OverlayConfigManager, app_config=None):
        super().__init__()
        self.config = config_manager
        self.app_config = app_config

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 48, 48, 48)
        root.setSpacing(24)

        # ── 헤더
        header = QLabel("오버레이 설정")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        root.addWidget(header)

        # ── 본문 = 사이드바 | 구분선 | 콘텐츠 스택
        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)

        body.addWidget(self._build_sidebar())

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #E0E0E0;")
        body.addWidget(sep)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_appearance_page())   # 0
        self.stack.addWidget(self._build_behavior_page())     # 1
        self.stack.addWidget(self._build_hotkeys_page())      # 2
        self.stack.addWidget(self._build_system_page())       # 3
        body.addWidget(self.stack, 1)

        root.addLayout(body, 1)

        self._switch_page(0)
        self.refresh_ui_from_config()

    # ------------------------------------------------------------------ #
    # 사이드바
    # ------------------------------------------------------------------ #

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(148)
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(2)

        self._nav_btns: list[_NavBtn] = []
        for i, (icon, label) in enumerate(_CATEGORIES):
            btn = _NavBtn(icon, label)
            btn.clicked.connect(lambda _, idx=i: self._switch_page(idx))
            self._nav_btns.append(btn)
            lay.addWidget(btn)

        lay.addStretch()
        return w

    def _switch_page(self, idx: int) -> None:
        for i, btn in enumerate(self._nav_btns):
            btn.setActive(i == idx)
        self.stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------ #
    # 공통 스크롤 래퍼
    # ------------------------------------------------------------------ #

    def _wrap_scroll(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        return scroll

    # ================================================================== #
    # 페이지 0 — 🎨 외관
    # ================================================================== #

    def _build_appearance_page(self) -> QScrollArea:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 20, 24, 32)
        lay.setSpacing(20)

        # ── 미리보기
        lay.addWidget(self._section_lbl("오버레이 미리보기"))
        self.preview_area = StylePreview()
        lay.addWidget(self.preview_area)

        # ── 오버레이 활성화
        enable_card = Card()
        el = QHBoxLayout(enable_card)
        el.setContentsMargins(24, 18, 24, 18)
        ev = QVBoxLayout()
        ev.addWidget(self._lbl("오버레이 활성화", UIConfig.FS_TITLE_M, bold=800))
        ev.addWidget(self._lbl("가사 오버레이를 화면에 표시하거나 숨깁니다.", UIConfig.FS_DESC, secondary=True))
        self.overlay_switch = QCheckBox()
        self.overlay_switch.setCursor(Qt.PointingHandCursor)
        self.overlay_switch.setChecked(self.config.visible)
        self.overlay_switch.toggled.connect(self._on_visible_toggled)
        el.addLayout(ev)
        el.addStretch()
        el.addWidget(self.overlay_switch)
        lay.addWidget(enable_card)

        # ── 스타일 프리셋
        lay.addWidget(self._section_lbl("스타일 프리셋"))
        preset_card = Card()
        pl = QVBoxLayout(preset_card)
        pl.setContentsMargins(24, 18, 24, 18)
        pl.setSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_import_styles = QPushButton("가져오기  📥")
        self.btn_import_styles.setFixedHeight(36)
        self.btn_import_styles.clicked.connect(self._import_styles_dialog)
        self.btn_export_styles = QPushButton("내보내기  📤")
        self.btn_export_styles.setFixedHeight(36)
        self.btn_export_styles.clicked.connect(self._export_styles_dialog)
        self.btn_save_preset = QPushButton("현재 스타일 저장  💾")
        self.btn_save_preset.setFixedHeight(36)
        self.btn_save_preset.clicked.connect(self._save_current_as_preset)
        btn_row.addWidget(self.btn_import_styles)
        btn_row.addWidget(self.btn_export_styles)
        btn_row.addWidget(self.btn_save_preset)
        pl.addLayout(btn_row)

        self.preset_container = QWidget()
        self.preset_grid = QGridLayout(self.preset_container)
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setSpacing(14)
        self._update_preset_list()
        pl.addWidget(self.preset_container)
        lay.addWidget(preset_card)

        # ── 스타일 세부 설정
        lay.addWidget(self._section_lbl("스타일 세부 설정"))
        style_card = Card()
        sl = QVBoxLayout(style_card)
        sl.setContentsMargins(24, 18, 24, 18)
        sl.setSpacing(18)

        # 글꼴
        font_row = QHBoxLayout()
        font_row.addWidget(self._lbl("오버레이 글꼴", UIConfig.FS_TITLE_S, bold=600))
        self.btn_font = QPushButton("글꼴 변경  🔤")
        self.btn_font.setFixedSize(140, 36)
        self.btn_font.clicked.connect(self._pick_font)
        font_row.addStretch()
        font_row.addWidget(self.btn_font)
        sl.addLayout(font_row)
        sl.addWidget(self._hline())

        # 불투명도
        alpha_vbox = QVBoxLayout()
        alpha_vbox.setSpacing(8)
        alpha_hdr = QHBoxLayout()
        alpha_hdr.addWidget(self._lbl("배경 불투명도", UIConfig.FS_TITLE_S, bold=600))
        alpha_hdr.addStretch()
        self.alpha_val_label = QLabel(str(self.config.bg_color.alpha()))
        self.alpha_val_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: {_ACCENT};"
        )
        alpha_hdr.addWidget(self.alpha_val_label)
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(self.config.bg_color.alpha())
        self.alpha_slider.valueChanged.connect(self._on_alpha_changed)
        alpha_vbox.addLayout(alpha_hdr)
        alpha_vbox.addWidget(self.alpha_slider)
        sl.addLayout(alpha_vbox)
        sl.addWidget(self._hline())

        # 색상 버튼 3개
        color_row = QHBoxLayout()
        color_row.setSpacing(24)
        tv, self.btn_text_color = self._color_ctrl("글씨 색상", self.config.text_color, "text")
        bv, self.btn_bg_color   = self._color_ctrl("배경 색상", self.config.bg_color, "bg")
        ov, self.btn_out_color  = self._color_ctrl("아웃라인 색상", self.config.outline_color, "outline")
        color_row.addLayout(tv)
        color_row.addLayout(bv)
        color_row.addLayout(ov)
        color_row.addStretch()
        sl.addLayout(color_row)
        sl.addWidget(self._hline())

        # 아웃라인 두께
        out_vbox = QVBoxLayout()
        out_vbox.setSpacing(8)
        out_hdr = QHBoxLayout()
        out_hdr.addWidget(self._lbl("아웃라인 두께", UIConfig.FS_TITLE_S, bold=600))
        out_hdr.addStretch()
        self.outline_val_label = QLabel(str(self.config.outline_width))
        self.outline_val_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: {_ACCENT};"
        )
        out_hdr.addWidget(self.outline_val_label)
        self.outline_slider = QSlider(Qt.Horizontal)
        self.outline_slider.setRange(0, 10)
        self.outline_slider.setValue(self.config.outline_width)
        self.outline_slider.valueChanged.connect(self._on_outline_changed)
        out_vbox.addLayout(out_hdr)
        out_vbox.addWidget(self.outline_slider)
        sl.addLayout(out_vbox)
        sl.addWidget(self._hline())

        # 크기 슬라이더
        size_vbox = QVBoxLayout()
        size_vbox.setSpacing(8)
        size_hdr = QHBoxLayout()
        size_hdr.addWidget(self._lbl("오버레이 크기 (너비 / 높이)", UIConfig.FS_TITLE_S, bold=600))
        size_hdr.addStretch()
        self.size_val_label = QLabel(f"{self.config.width} x {self.config.height}")
        self.size_val_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: {_ACCENT};"
        )
        size_hdr.addWidget(self.size_val_label)
        size_sliders = QHBoxLayout()
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(200, 1500)
        self.width_slider.setValue(self.config.width)
        self.width_slider.valueChanged.connect(self._on_size_changed)
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(80, 500)
        self.height_slider.setValue(self.config.height)
        self.height_slider.valueChanged.connect(self._on_size_changed)
        size_sliders.addWidget(self.width_slider)
        size_sliders.addWidget(self.height_slider)
        size_vbox.addLayout(size_hdr)
        size_vbox.addLayout(size_sliders)
        sl.addLayout(size_vbox)

        lay.addWidget(style_card)
        lay.addStretch()
        return self._wrap_scroll(inner)

    # ================================================================== #
    # 페이지 1 — ⚙️ 동작
    # ================================================================== #

    def _build_behavior_page(self) -> QScrollArea:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 20, 24, 32)
        lay.setSpacing(20)

        lay.addWidget(self._section_lbl("오버레이 동작"))
        beh_card = Card()
        bl = QVBoxLayout(beh_card)
        bl.setContentsMargins(24, 18, 24, 18)
        bl.setSpacing(14)

        bl.addLayout(self._toggle_row(
            "고스트 모드",
            "오버레이가 마우스 클릭을 통과하도록 설정합니다.",
            self.config.ghost_mode, self._on_ghost_toggled, "ghost_check",
        ))
        bl.addWidget(self._hline())
        bl.addLayout(self._toggle_row(
            "오버레이 위치 이동",
            "오버레이를 드래그하여 위치를 변경할 수 있도록 합니다.",
            self.config.move_enabled, self._on_move_toggled, "move_check",
        ))
        bl.addLayout(self._toggle_row(
            "오버레이 크기 조절",
            "오버레이 우측 하단을 드래그하여 크기를 조절할 수 있도록 합니다.",
            self.config.resize_enabled, self._on_resize_toggled, "resize_check",
        ))
        bl.addWidget(self._hline())
        bl.addLayout(self._toggle_row(
            "곡 정보 표시",
            "오버레이에 현재 재생 중인 곡의 제목과 가수를 표시합니다.",
            self.config.show_song_info, self._on_show_song_info_toggled, "song_info_check",
        ))
        lay.addWidget(beh_card)

        # ROI (비활성화)
        lay.addWidget(self._section_lbl("영역 설정"))
        roi_card = Card()
        rl = QVBoxLayout(roi_card)
        rl.setContentsMargins(24, 18, 24, 18)
        rl.setSpacing(10)
        roi_title = QLabel("영역 설정 (비활성화됨)")
        roi_title.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600; color: #AAAAAA;"
        )
        roi_desc = QLabel("가사가 출력되는 멜론 창의 영역을 직접 선택합니다.")
        roi_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: #AAAAAA;")
        self.roi_btn = QPushButton("가사 인식 영역 설정 (ROI)  🎯")
        self.roi_btn.setEnabled(False)
        self.roi_btn.setMinimumHeight(50)
        self.roi_btn.setStyleSheet(
            "background-color: #EEEEEE; color: #AAAAAA; border-radius: 10px;"
        )
        rl.addWidget(roi_title)
        rl.addWidget(roi_desc)
        rl.addWidget(self.roi_btn)
        lay.addWidget(roi_card)

        lay.addStretch()
        return self._wrap_scroll(inner)

    # ================================================================== #
    # 페이지 2 — ⌨️ 단축키
    # ================================================================== #

    def _build_hotkeys_page(self) -> QScrollArea:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 20, 24, 32)
        lay.setSpacing(20)

        # 앱 제어
        lay.addWidget(self._section_lbl("앱 제어"))
        app_card = Card()
        al = QVBoxLayout(app_card)
        al.setContentsMargins(24, 18, 24, 18)
        al.setSpacing(14)

        ghost_row, self.ghost_hk_edit = self._hotkey_row(
            "고스트 모드 토글", self.config.hotkey_ghost, self._on_hotkey_ghost_changed
        )
        quit_row, self.quit_hk_edit = self._hotkey_row(
            "프로그램 종료", self.config.hotkey_quit, self._on_hotkey_quit_changed
        )
        al.addLayout(ghost_row)
        al.addLayout(quit_row)
        lay.addWidget(app_card)

        # 미디어 컨트롤
        lay.addWidget(self._section_lbl("미디어 컨트롤"))
        media_card = Card()
        ml = QVBoxLayout(media_card)
        ml.setContentsMargins(24, 18, 24, 18)
        ml.setSpacing(14)

        info = QLabel(
            "단축키를 누르면 멜론 등 미디어 앱에 재생 제어 명령이 전달됩니다.\n"
            "단축키 입력 칸을 클릭한 뒤 원하는 키 조합을 누르세요."
        )
        info.setStyleSheet(
            f"font-size: {UIConfig.FS_DESC}; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        info.setWordWrap(True)
        ml.addWidget(info)
        ml.addWidget(self._hline())

        next_row, self.next_hk_edit = self._hotkey_row(
            "다음 곡  ⏭", self.config.hotkey_next, self._on_hotkey_next_changed
        )
        prev_row, self.prev_hk_edit = self._hotkey_row(
            "이전 곡  ⏮", self.config.hotkey_prev, self._on_hotkey_prev_changed
        )
        pause_row, self.pause_hk_edit = self._hotkey_row(
            "일시정지 / 재생  ⏯", self.config.hotkey_pause, self._on_hotkey_pause_changed
        )
        ml.addLayout(next_row)
        ml.addLayout(prev_row)
        ml.addLayout(pause_row)
        lay.addWidget(media_card)

        lay.addStretch()
        return self._wrap_scroll(inner)

    # ================================================================== #
    # 페이지 3 — 💾 시스템
    # ================================================================== #

    def _build_system_page(self) -> QScrollArea:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 20, 24, 32)
        lay.setSpacing(20)

        lay.addWidget(self._section_lbl("데이터 관리"))
        sys_card = Card()
        sys_l = QVBoxLayout(sys_card)
        sys_l.setContentsMargins(24, 18, 24, 18)
        sys_l.setSpacing(12)

        path_row = QHBoxLayout()
        path_info = QVBoxLayout()
        path_info.addWidget(self._lbl("데이터 저장 경로", UIConfig.FS_TITLE_S, bold=600))
        current_path = self.app_config.data_dir if self.app_config else "알 수 없음"
        self.lbl_data_path = self._lbl(current_path, UIConfig.FS_DESC, secondary=True)
        path_info.addWidget(self.lbl_data_path)
        self.btn_change_path = QPushButton("경로 변경하기  📂")
        self.btn_change_path.setFixedHeight(40)
        self.btn_change_path.clicked.connect(self._on_change_data_path)
        path_row.addLayout(path_info)
        path_row.addStretch()
        path_row.addWidget(self.btn_change_path)
        sys_l.addLayout(path_row)
        lay.addWidget(sys_card)

        lay.addStretch()
        return self._wrap_scroll(inner)

    # ------------------------------------------------------------------ #
    # 헬퍼 위젯 팩토리
    # ------------------------------------------------------------------ #

    def _section_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; "
            f"color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        return lbl

    def _lbl(
        self, text: str, font_size: str, bold: int = 400, secondary: bool = False
    ) -> QLabel:
        lbl = QLabel(text)
        color = f"color: {UIConfig.COLOR_SECONDARY_TEXT};" if secondary else ""
        lbl.setStyleSheet(f"font-size: {font_size}; font-weight: {bold}; {color}")
        return lbl

    # kept for legacy compatibility (some callers use _make_label)
    def _make_label(
        self, text: str, font_size: str, bold: int = 400, secondary: bool = False
    ) -> QLabel:
        return self._lbl(text, font_size, bold, secondary)

    def _make_section_title(self, text: str) -> QLabel:
        return self._lbl(text, UIConfig.FS_TITLE_L, bold=800, secondary=True)

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #E0E0E0;")
        return line

    def _make_hline(self) -> QFrame:
        return self._hline()

    def _toggle_row(
        self,
        title: str,
        desc: str,
        checked: bool,
        callback,
        attr_name: str,
    ) -> QHBoxLayout:
        hbox = QHBoxLayout()
        vbox = QVBoxLayout()
        vbox.addWidget(self._lbl(title, UIConfig.FS_TITLE_S, bold=600))
        vbox.addWidget(self._lbl(desc, UIConfig.FS_DESC, secondary=True))
        chk = QCheckBox()
        chk.setCursor(Qt.PointingHandCursor)
        chk.setChecked(checked)
        chk.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
        chk.toggled.connect(callback)
        setattr(self, attr_name, chk)
        hbox.addLayout(vbox)
        hbox.addStretch()
        hbox.addWidget(chk)
        return hbox

    def _make_toggle_row(
        self, title, desc, checked, callback, attr_name
    ) -> QHBoxLayout:
        return self._toggle_row(title, desc, checked, callback, attr_name)

    def _hotkey_row(
        self, label_text: str, current_val: str, callback
    ) -> tuple:
        hbox = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        edit = HotkeyEdit(current_val)
        edit.setFixedWidth(165)
        edit.changed.connect(callback)
        hbox.addWidget(lbl)
        hbox.addStretch()
        hbox.addWidget(edit)
        return hbox, edit

    def _make_hotkey_row(self, label_text, current_val, callback) -> tuple:
        return self._hotkey_row(label_text, current_val, callback)

    def _color_ctrl(self, label_text: str, color_obj, target: str):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        btn = QPushButton()
        btn.setFixedSize(80, 36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"background-color: {color_obj.name()}; border-radius: 18px; border: 2px solid #E0E0E0;"
        )
        btn.clicked.connect(lambda: self._pick_color(target, btn))
        vbox.addWidget(lbl)
        vbox.addWidget(btn)
        return vbox, btn

    def _create_color_ctrl(self, label_text, color_obj, target):
        return self._color_ctrl(label_text, color_obj, target)

    # ------------------------------------------------------------------ #
    # 프리셋 관리
    # ------------------------------------------------------------------ #

    def _update_preset_list(self) -> None:
        while self.preset_grid.count():
            item = self.preset_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        row = col = 0
        for name, data in self.config.PRESET_STYLES.items():
            preset = PresetItem(name, data, is_custom=False)
            preset.clicked.connect(self._on_preset_selected)
            self.preset_grid.addWidget(preset, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        for name, data in self.config.custom_presets.items():
            preset = PresetItem(name, data, is_custom=True)
            preset.clicked.connect(self._on_preset_selected)
            preset.delete_requested.connect(self._on_delete_preset)
            self.preset_grid.addWidget(preset, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

    def _on_delete_preset(self, name: str) -> None:
        reply = QMessageBox.question(
            self,
            "프리셋 삭제",
            f"'{name}' 프리셋을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.config.delete_custom_preset(name)
            self._update_preset_list()

    def _on_preset_selected(self, preset_data: dict) -> None:
        self.config.apply_preset(preset_data)
        self.refresh_ui_from_config()
        self.settings_changed.emit()

    def _import_styles_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "스타일 가져오기", "", "JSON Files (*.json)"
        )
        if file_path:
            if self.config.import_styles(file_path):
                QMessageBox.information(self, "성공", "스타일을 성공적으로 가져왔습니다.")
                self._update_preset_list()
                self.refresh_ui_from_config()
                self.settings_changed.emit()
            else:
                QMessageBox.critical(self, "오류", "스타일 가져오기에 실패했습니다.")

    def _export_styles_dialog(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "스타일 내보내기", "my_styles.json", "JSON Files (*.json)"
        )
        if file_path:
            if self.config.export_styles(file_path):
                QMessageBox.information(self, "성공", "스타일을 성공적으로 내보냈습니다.")
            else:
                QMessageBox.critical(self, "오류", "스타일 내보내기에 실패했습니다.")

    def _save_current_as_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog  # type: ignore

        name, ok = QInputDialog.getText(self, "프리셋 저장", "프리셋 이름을 입력하세요:")
        if ok and name:
            self.config.save_custom_preset(name)
            self._update_preset_list()

    # ------------------------------------------------------------------ #
    # UI 동기화
    # ------------------------------------------------------------------ #

    def refresh_ui_from_config(self) -> None:
        """설정 변경 후 UI 요소 상태를 동기화합니다."""
        self.overlay_switch.blockSignals(True)
        self.overlay_switch.setChecked(self.config.visible)
        self.overlay_switch.blockSignals(False)

        self.alpha_slider.setValue(self.config.bg_color.alpha())
        self.alpha_val_label.setText(str(self.config.bg_color.alpha()))
        self.outline_slider.setValue(self.config.outline_width)
        self.outline_val_label.setText(str(self.config.outline_width))
        self.width_slider.setValue(self.config.width)
        self.height_slider.setValue(self.config.height)
        self.size_val_label.setText(f"{self.config.width} x {self.config.height}")

        self.ghost_check.setChecked(self.config.ghost_mode)
        self.move_check.setChecked(self.config.move_enabled)
        self.resize_check.setChecked(self.config.resize_enabled)
        self.song_info_check.setChecked(self.config.show_song_info)

        self.btn_text_color.setStyleSheet(
            f"background-color: {self.config.text_color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;"
        )
        self.btn_bg_color.setStyleSheet(
            f"background-color: {self.config.bg_color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;"
        )
        self.btn_out_color.setStyleSheet(
            f"background-color: {self.config.outline_color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;"
        )
        self.preview_area.update_preview(self.config)

    # ------------------------------------------------------------------ #
    # 이벤트 핸들러
    # ------------------------------------------------------------------ #

    def _on_visible_toggled(self, checked: bool) -> None:
        self.config.visible = checked
        self.settings_changed.emit()

    def _on_ghost_toggled(self, checked: bool) -> None:
        self.config.ghost_mode = checked
        self.settings_changed.emit()

    def _on_move_toggled(self, checked: bool) -> None:
        self.config.set_move_enabled(checked)
        self.settings_changed.emit()

    def _on_resize_toggled(self, checked: bool) -> None:
        self.config.set_resize_enabled(checked)
        self.settings_changed.emit()

    def _on_show_song_info_toggled(self, checked: bool) -> None:
        self.config.show_song_info = checked
        self.config.save_to_file()
        self.settings_changed.emit()

    def _on_hotkey_ghost_changed(self, text: str) -> None:
        self.config.update_hotkey_ghost(text.strip())
        self.settings_changed.emit()
        self.hotkeys_changed.emit()

    def _on_hotkey_quit_changed(self, text: str) -> None:
        self.config.update_hotkey_quit(text.strip())
        self.settings_changed.emit()
        self.hotkeys_changed.emit()

    def _on_hotkey_next_changed(self, text: str) -> None:
        self.config.update_hotkey_next(text.strip())
        self.hotkeys_changed.emit()

    def _on_hotkey_prev_changed(self, text: str) -> None:
        self.config.update_hotkey_prev(text.strip())
        self.hotkeys_changed.emit()

    def _on_hotkey_pause_changed(self, text: str) -> None:
        self.config.update_hotkey_pause(text.strip())
        self.hotkeys_changed.emit()

    def _on_alpha_changed(self, value: int) -> None:
        self.alpha_val_label.setText(str(value))
        self.config.update_background(opacity=value)
        self.settings_changed.emit()

    def _on_outline_changed(self, value: int) -> None:
        self.outline_val_label.setText(str(value))
        self.config.update_text_style(outline_width=value)
        self.settings_changed.emit()

    def _on_size_changed(self) -> None:
        w = self.width_slider.value()
        h = self.height_slider.value()
        self.size_val_label.setText(f"{w} x {h}")
        self.config.update_size(w, h)
        self.settings_changed.emit()

    def _pick_color(self, target: str, btn: QPushButton) -> None:
        current_color = getattr(self.config, f"{target}_color")
        color = QColorDialog.getColor(current_color)
        if color.isValid():
            btn.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;"
            )
            if target == "text":
                self.config.update_text_style(color=color)
            elif target == "bg":
                self.config.update_background(color=color)
            elif target == "outline":
                self.config.update_text_style(outline_color=color)
            self.settings_changed.emit()

    def _pick_font(self) -> None:
        current_font = QFont(self.config.font_family, self.config.font_size)
        ok, font = QFontDialog.getFont(current_font)
        if ok:
            self.config.update_font(family=font.family(), size=font.pointSize())
            self.settings_changed.emit()

    def _on_change_data_path(self) -> None:
        if not self.app_config:
            return
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "새 데이터 저장 경로 선택",
            self.app_config.data_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if new_dir:
            success = self.app_config.set_data_dir(new_dir)
            if success:
                self.lbl_data_path.setText(new_dir)
                QMessageBox.information(
                    self,
                    "경로 변경 완료",
                    "데이터 저장 경로가 성공적으로 변경되었습니다.\n새로운 경로에 설정 및 통계 파일이 저장됩니다.",
                )
            else:
                QMessageBox.critical(
                    self, "오류", "데이터 저장 경로를 변경하는데 실패했습니다."
                )
