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
    QDialog,
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

from gui import icons
from gui.theme import UIConfig
from gui.widgets.card import Card, PresetItem, StylePreview
from gui.widgets.glass import NavButton, ToggleSwitch, divider, label, page_header
from gui.widgets.hotkey_edit import HotkeyEdit
from overlay.config_manager import OverlayConfigManager

_CATEGORIES = [
    (icons.PALETTE, "외관"),
    (icons.SLIDERS, "동작"),
    (icons.KEYBOARD, "단축키"),
    (icons.SYSTEM, "시스템"),
]


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
        root.setContentsMargins(28, 14, 12, 0)
        root.setSpacing(20)

        # ── 헤더
        header = page_header("설정", "오버레이의 모양과 동작, 단축키를 조정하세요")
        root.addWidget(header)

        # ── 본문 = 카테고리 | 콘텐츠 스택
        body = QHBoxLayout()
        body.setSpacing(6)
        body.setContentsMargins(0, 0, 0, 0)

        body.addWidget(self._build_sidebar(), 0, Qt.AlignTop)

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
        w = Card()
        w.setFixedWidth(176)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(4)

        self._nav_btns: list[NavButton] = []
        for i, (glyph, text) in enumerate(_CATEGORIES):
            btn = NavButton(glyph, text, height=40)
            btn.clicked.connect(lambda _=False, idx=i: self._switch_page(idx))
            self._nav_btns.append(btn)
            lay.addWidget(btn)
        return w

    def _switch_page(self, idx: int) -> None:
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------ #
    # 공통 스크롤 래퍼
    # ------------------------------------------------------------------ #

    def _wrap_scroll(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return scroll

    # ================================================================== #
    # 페이지 0 — 🎨 외관
    # ================================================================== #

    def _build_appearance_page(self) -> QScrollArea:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 4, 20, 28)
        lay.setSpacing(14)

        # ── 미리보기
        lay.addWidget(self._section_lbl("오버레이 미리보기"))
        self.preview_area = StylePreview()
        lay.addWidget(self.preview_area)

        # ── 오버레이 활성화
        enable_card = Card()
        el = QHBoxLayout(enable_card)
        el.setContentsMargins(22, 16, 22, 16)
        ev = QVBoxLayout()
        ev.setSpacing(2)
        ev.addWidget(self._lbl("오버레이 표시", UIConfig.FS_TITLE_S, bold=700))
        ev.addWidget(self._lbl("가사 오버레이를 화면에 표시하거나 숨깁니다.", UIConfig.FS_DESC, secondary=True))
        self.overlay_switch = ToggleSwitch()
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
        pl.setContentsMargins(22, 16, 22, 16)
        pl.setSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self._lbl("클릭해서 적용 · 직접 만든 프리셋은 우클릭으로 삭제", UIConfig.FS_DESC, secondary=True))
        btn_row.addStretch()
        self.btn_import_styles = QPushButton("가져오기")
        self.btn_import_styles.setFixedHeight(36)
        self.btn_import_styles.clicked.connect(self._import_styles_dialog)
        self.btn_export_styles = QPushButton("내보내기")
        self.btn_export_styles.setFixedHeight(36)
        self.btn_export_styles.clicked.connect(self._export_styles_dialog)
        self.btn_save_preset = QPushButton("현재 스타일 저장")
        self.btn_save_preset.setObjectName("PrimaryButton")
        self.btn_save_preset.setFixedHeight(36)
        self.btn_save_preset.clicked.connect(self._save_current_as_preset)
        btn_row.addWidget(self.btn_import_styles)
        btn_row.addWidget(self.btn_export_styles)
        btn_row.addWidget(self.btn_save_preset)
        pl.addLayout(btn_row)

        self.preset_container = QWidget()
        self.preset_grid = QGridLayout(self.preset_container)
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setSpacing(12)
        self.preset_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._update_preset_list()
        pl.addWidget(self.preset_container)
        lay.addWidget(preset_card)

        # ── 스타일 세부 설정
        lay.addWidget(self._section_lbl("스타일 세부 설정"))
        style_card = Card()
        sl = QVBoxLayout(style_card)
        sl.setContentsMargins(22, 16, 22, 16)
        sl.setSpacing(18)

        # 글꼴
        font_row = QHBoxLayout()
        font_row.addWidget(self._lbl("오버레이 글꼴", UIConfig.FS_TITLE_S, bold=600))
        self.btn_font = QPushButton("글꼴 변경")
        self.btn_font.setFixedHeight(36)
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
        self.alpha_val_label.setObjectName("AccentValue")
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
        self.outline_val_label.setObjectName("AccentValue")
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
        self.size_val_label.setObjectName("AccentValue")
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
        lay.setContentsMargins(16, 4, 20, 28)
        lay.setSpacing(14)

        lay.addWidget(self._section_lbl("오버레이 동작"))
        beh_card = Card()
        bl = QVBoxLayout(beh_card)
        bl.setContentsMargins(22, 16, 22, 16)
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
        bl.addLayout(self._toggle_row(
            "오버레이 재생 버튼",
            "고스트 모드가 꺼져 있을 때 오버레이에 마우스를 올리면 이전 곡·재생/일시정지·다음 곡 버튼을 표시합니다.",
            self.config.show_media_controls, self._on_show_media_controls_toggled, "media_controls_check",
        ))
        lay.addWidget(beh_card)

        lay.addWidget(self._section_lbl("멜론 창"))
        melon_card = Card()
        ml = QVBoxLayout(melon_card)
        ml.setContentsMargins(22, 16, 22, 16)
        ml.setSpacing(14)
        ml.addLayout(self._toggle_row(
            "고스트 모드에서 멜론 창 숨기기",
            "켜면 고스트 모드일 때 멜론 창을 투명하게 숨기고 클릭이 통과되게 합니다. "
            "듀얼 모니터처럼 멜론 창과 오버레이를 함께 쓰려면 끄세요.",
            self.config.hide_melon_window, self._on_hide_melon_toggled, "hide_melon_check",
        ))
        lay.addWidget(melon_card)

        # 가사 인식 영역
        lay.addWidget(self._section_lbl("가사 인식"))
        roi_card = Card()
        rl = QHBoxLayout(roi_card)
        rl.setContentsMargins(22, 16, 22, 16)
        rl.setSpacing(12)
        roi_text = QVBoxLayout()
        roi_text.setSpacing(4)
        roi_text.addWidget(self._lbl("가사 인식 영역", UIConfig.FS_TITLE_S, bold=600))
        roi_desc = self._lbl(
            "가사가 안 읽히거나 엉뚱한 글자가 나오면, 멜론 창에서 가사가 보이는 곳을 직접 지정하세요. "
            "화면 배율이 100%가 아니면 꼭 필요할 수 있어요.",
            UIConfig.FS_DESC, secondary=True,
        )
        roi_desc.setWordWrap(True)
        roi_text.addWidget(roi_desc)
        self.roi_value_label = self._lbl("", UIConfig.FS_DESC, secondary=True)
        roi_text.addWidget(self.roi_value_label)
        rl.addLayout(roi_text, 1)
        self.roi_btn = QPushButton("영역 지정하기")
        self.roi_btn.setObjectName("PrimaryButton")
        self.roi_btn.setMinimumHeight(40)
        self.roi_btn.clicked.connect(self._on_pick_roi)
        rl.addWidget(self.roi_btn, 0, Qt.AlignVCenter)
        lay.addWidget(roi_card)
        self._update_roi_label()

        lay.addStretch()
        return self._wrap_scroll(inner)

    # ================================================================== #
    # 페이지 2 — ⌨️ 단축키
    # ================================================================== #

    def _build_hotkeys_page(self) -> QScrollArea:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 4, 20, 28)
        lay.setSpacing(14)

        # 앱 제어
        lay.addWidget(self._section_lbl("앱 제어"))
        app_card = Card()
        al = QVBoxLayout(app_card)
        al.setContentsMargins(22, 16, 22, 16)
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
        ml.setContentsMargins(22, 16, 22, 16)
        ml.setSpacing(14)

        info = QLabel(
            "단축키를 누르면 멜론 등 미디어 앱에 재생 제어 명령이 전달됩니다.\n"
            "단축키 입력 칸을 클릭한 뒤 원하는 키 조합을 누르세요."
        )
        info.setObjectName("Secondary")
        info.setStyleSheet(f"font-size: {UIConfig.FS_DESC};")
        info.setWordWrap(True)
        ml.addWidget(info)
        ml.addWidget(self._hline())

        next_row, self.next_hk_edit = self._hotkey_row(
            "다음 곡", self.config.hotkey_next, self._on_hotkey_next_changed
        )
        prev_row, self.prev_hk_edit = self._hotkey_row(
            "이전 곡", self.config.hotkey_prev, self._on_hotkey_prev_changed
        )
        pause_row, self.pause_hk_edit = self._hotkey_row(
            "재생 / 일시정지", self.config.hotkey_pause, self._on_hotkey_pause_changed
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
        lay.setContentsMargins(16, 4, 20, 28)
        lay.setSpacing(14)

        lay.addWidget(self._section_lbl("데이터 관리"))
        sys_card = Card()
        sys_l = QVBoxLayout(sys_card)
        sys_l.setContentsMargins(22, 16, 22, 16)
        sys_l.setSpacing(12)

        path_row = QHBoxLayout()
        path_info = QVBoxLayout()
        path_info.addWidget(self._lbl("데이터 저장 경로", UIConfig.FS_TITLE_S, bold=600))
        current_path = self.app_config.data_dir if self.app_config else "알 수 없음"
        self.lbl_data_path = self._lbl(current_path, UIConfig.FS_DESC, secondary=True)
        path_info.addWidget(self.lbl_data_path)
        self.btn_change_path = QPushButton("경로 변경")
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
        lbl.setObjectName("SectionLabel")
        lbl.setContentsMargins(4, 8, 0, 0)
        return lbl

    def _lbl(
        self, text: str, font_size: str, bold: int = 400, secondary: bool = False
    ) -> QLabel:
        lbl = QLabel(text)
        if secondary:
            lbl.setObjectName("Secondary")
        lbl.setStyleSheet(f"font-size: {font_size}; font-weight: {bold};")
        return lbl

    # kept for legacy compatibility (some callers use _make_label)
    def _make_label(
        self, text: str, font_size: str, bold: int = 400, secondary: bool = False
    ) -> QLabel:
        return self._lbl(text, font_size, bold, secondary)

    def _make_section_title(self, text: str) -> QLabel:
        return self._lbl(text, UIConfig.FS_TITLE_L, bold=800, secondary=True)

    def _hline(self) -> QFrame:
        return divider()

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
        vbox.setSpacing(2)
        vbox.addWidget(self._lbl(title, UIConfig.FS_TITLE_S, bold=600))
        desc_lbl = self._lbl(desc, UIConfig.FS_DESC, secondary=True)
        desc_lbl.setWordWrap(True)  # 긴 설명이 페이지를 가로로 늘리지 않도록
        vbox.addWidget(desc_lbl)
        chk = ToggleSwitch()
        chk.setChecked(checked)
        chk.toggled.connect(callback)
        setattr(self, attr_name, chk)
        hbox.addLayout(vbox, 1)
        hbox.addSpacing(16)
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
        lbl = self._lbl(label_text, UIConfig.FS_TITLE_S, bold=600)
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
        lbl = self._lbl(label_text, UIConfig.FS_DESC, bold=600, secondary=True)
        btn = QPushButton()
        btn.setObjectName("ColorSwatch")
        btn.setFixedSize(72, 32)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"background-color: {color_obj.name()};"
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
            if col > 3:
                col = 0
                row += 1

        for name, data in self.config.custom_presets.items():
            preset = PresetItem(name, data, is_custom=True)
            preset.clicked.connect(self._on_preset_selected)
            preset.delete_requested.connect(self._on_delete_preset)
            self.preset_grid.addWidget(preset, row, col)
            col += 1
            if col > 3:
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
            count = self.config.import_styles(file_path)
            if count:
                QMessageBox.information(self, "가져오기 완료", f"프리셋 {count}개를 '내 프리셋'으로 가져왔습니다.")
                self._update_preset_list()
                self.refresh_ui_from_config()
                self.settings_changed.emit()
            else:
                QMessageBox.critical(self, "가져오기 실패", "올바른 프리셋 파일이 아니거나, 쓸 수 있는 프리셋이 없습니다.")

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
        self.media_controls_check.setChecked(self.config.show_media_controls)
        self.hide_melon_check.setChecked(self.config.hide_melon_window)

        self.btn_text_color.setStyleSheet(
            f"background-color: {self.config.text_color.name()};"
        )
        self.btn_bg_color.setStyleSheet(
            f"background-color: {self.config.bg_color.name()};"
        )
        self.btn_out_color.setStyleSheet(
            f"background-color: {self.config.outline_color.name()};"
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

    def _on_show_media_controls_toggled(self, checked: bool) -> None:
        self.config.show_media_controls = checked
        self.config.save_to_file()
        self.settings_changed.emit()

    def _on_hide_melon_toggled(self, checked: bool) -> None:
        self.config.hide_melon_window = checked
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
                f"background-color: {color.name()};"
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

    def _update_roi_label(self) -> None:
        from overlay.config_manager import DEFAULT_ROI

        x, y, w, h = self.config.roi
        suffix = " (기본값)" if list(self.config.roi) == DEFAULT_ROI else ""
        self.roi_value_label.setText(f"현재: 위치 ({x}, {y}) · 크기 {w} × {h}{suffix}")

    def _on_pick_roi(self) -> None:
        from core.window_capture import capture_covered_window, find_melon_window
        from gui.roi_selector import RoiSelectDialog

        target = find_melon_window()
        img = capture_covered_window(target.hwnd) if target else None
        if img is None:
            QMessageBox.information(
                self, "멜론 창을 찾을 수 없어요",
                "멜론 PC 플레이어를 실행하고, 가사가 보이는 상태로 띄워 주세요.\n"
                "창이 최소화돼 있으면 캡처할 수 없어요.",
            )
            return
        dlg = RoiSelectDialog(img, self.config.roi, self)
        result = dlg.exec()
        if result == RoiSelectDialog.RESET:
            self.config.set_roi(None)
        elif result == QDialog.Accepted and dlg.selected_roi:
            self.config.set_roi(dlg.selected_roi)
        else:
            return
        self._update_roi_label()
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
        if not new_dir:
            return
        if not self.app_config.is_writable(new_dir):
            QMessageBox.critical(self, "경로 변경 실패", "선택한 폴더에 파일을 쓸 수 없습니다.\n다른 폴더를 골라 주세요.")
            return

        overwrite = False
        existing = self.app_config.existing_data_files(new_dir)
        if existing:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle("이 폴더에 기존 데이터가 있어요")
            box.setText(
                "선택한 폴더에 이미 LyricsOverlay 데이터가 있습니다.\n"
                "어느 데이터를 사용할까요?"
            )
            box.setInformativeText("· " + "\n· ".join(existing))
            use_current = box.addButton("지금 데이터로 덮어쓰기 (기존 파일은 백업)", QMessageBox.AcceptRole)
            use_existing = box.addButton("그 폴더의 데이터 사용 (재시작 후 적용)", QMessageBox.ActionRole)
            box.addButton("취소", QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is use_existing:
                self.app_config.set_data_dir_on_next_start(new_dir)
                QMessageBox.information(
                    self, "다음 실행부터 적용",
                    "프로그램을 다시 시작하면 선택한 폴더의 데이터를 사용합니다.\n"
                    "그때까지는 지금 폴더에 계속 저장합니다.",
                )
                return
            if clicked is not use_current:
                return
            overwrite = True

        if self.app_config.set_data_dir(new_dir, overwrite_existing=overwrite):
            self.lbl_data_path.setText(self.app_config.data_dir)
            QMessageBox.information(
                self,
                "경로 변경 완료",
                "이제부터 새 폴더에 설정과 감상 기록을 저장합니다.\n이전 폴더의 파일은 지우지 않고 그대로 둡니다.",
            )
        else:
            QMessageBox.critical(self, "오류", "데이터 저장 경로를 변경하는데 실패했습니다.")
