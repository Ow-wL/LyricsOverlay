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
from gui.widgets.card import Card, PresetFlow, PresetItem, StylePreview
from gui.widgets.glass import SegmentedControl, ToggleSwitch, divider, label, page_header
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
    overlay_edit_requested = Signal()
    overlay_reset_requested = Signal()

    def __init__(self, config_manager: OverlayConfigManager, app_config=None):
        super().__init__()
        self.config = config_manager
        self.app_config = app_config
        self._hotkey_edits: dict = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 14, 12, 0)
        root.setSpacing(20)

        # ── 헤더 + 카테고리 탭 (예전의 두 번째 사이드바 대신 가로 탭으로 공간 확보)
        header_row = QHBoxLayout()
        header_row.addWidget(page_header("설정", "오버레이의 모양과 동작, 단축키를 조정하세요"))
        header_row.addStretch()
        self.tabs = SegmentedControl([(str(i), text) for i, (_, text) in enumerate(_CATEGORIES)], "0")
        self.tabs.changed.connect(lambda key: self._switch_page(int(key)))
        header_row.addWidget(self.tabs, 0, Qt.AlignBottom)
        root.addLayout(header_row)

        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)

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

    def _switch_page(self, idx: int) -> None:
        self.tabs.set_current(str(idx))
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

    def _build_appearance_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # ── 미리보기: 스크롤 밖에 두어, 아래 값을 바꾸는 동안 계속 보이게 합니다.
        preview_wrap = QVBoxLayout()
        preview_wrap.setContentsMargins(16, 4, 20, 0)
        preview_wrap.setSpacing(6)
        preview_wrap.addWidget(self._section_lbl("미리보기"))
        self.preview_area = StylePreview()
        preview_wrap.addWidget(self.preview_area)
        outer.addLayout(preview_wrap)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 4, 20, 28)
        lay.setSpacing(14)

        # ── 스타일 프리셋
        lay.addWidget(self._section_lbl("스타일 프리셋 · 클릭하면 바로 적용돼요"))
        preset_card = Card()
        pl = QVBoxLayout(preset_card)
        pl.setContentsMargins(22, 16, 22, 16)
        pl.setSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
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

        self.preset_container = PresetFlow()
        self._update_preset_list()
        pl.addWidget(self.preset_container)
        lay.addWidget(preset_card)

        # ── 스타일 세부 설정
        lay.addWidget(self._section_lbl("직접 조정"))
        style_card = Card()
        sl = QVBoxLayout(style_card)
        sl.setContentsMargins(22, 16, 22, 16)
        sl.setSpacing(18)

        # 글꼴 (현재 글꼴 이름과 크기를 보여 줌)
        font_row = QHBoxLayout()
        font_text = QVBoxLayout()
        font_text.setSpacing(2)
        font_text.addWidget(self._lbl("글꼴", UIConfig.FS_TITLE_S, bold=600))
        self.font_val_label = self._lbl("", UIConfig.FS_DESC, secondary=True)
        font_text.addWidget(self.font_val_label)
        font_row.addLayout(font_text)
        font_row.addStretch()
        self.btn_font = QPushButton("글꼴 변경")
        self.btn_font.setFixedHeight(36)
        self.btn_font.clicked.connect(self._pick_font)
        font_row.addWidget(self.btn_font)
        sl.addLayout(font_row)
        sl.addWidget(self._hline())

        # 색상 버튼 3개
        color_row = QHBoxLayout()
        color_row.setSpacing(24)
        tv, self.btn_text_color = self._color_ctrl("글씨", self.config.text_color, "text")
        ov, self.btn_out_color = self._color_ctrl("외곽선", self.config.outline_color, "outline")
        bv, self.btn_bg_color = self._color_ctrl("배경", self.config.bg_color, "bg")
        color_row.addLayout(tv)
        color_row.addLayout(ov)
        color_row.addLayout(bv)
        color_row.addStretch()
        sl.addLayout(color_row)
        sl.addWidget(self._hline())

        # 슬라이더들: (제목, 범위, 핸들러) — 값은 오른쪽에 읽기 쉬운 단위로 표시
        self.alpha_slider, self.alpha_val_label = self._slider_row(
            sl, "배경 불투명도", 0, 255, self._on_alpha_changed
        )
        self.outline_slider, self.outline_val_label = self._slider_row(
            sl, "외곽선 두께", 0, 10, self._on_outline_changed
        )
        sl.addWidget(self._hline())
        self.width_slider, self.width_val_label = self._slider_row(
            sl, "오버레이 너비", 200, 4000, self._on_width_changed
        )
        self.height_slider, self.height_val_label = self._slider_row(
            sl, "오버레이 높이", 80, 1000, self._on_height_changed
        )
        # 예전 코드 호환용 (크기 요약)
        self.size_val_label = QLabel()

        lay.addWidget(style_card)
        lay.addStretch()
        outer.addWidget(self._wrap_scroll(inner), 1)

        # 어떤 경로로 값이 바뀌어도 미리보기와 값 표시를 함께 갱신
        self.settings_changed.connect(self._refresh_style_widgets)
        return page

    def _slider_row(self, parent_layout, title: str, lo: int, hi: int, handler):
        row = QVBoxLayout()
        row.setSpacing(6)
        hdr = QHBoxLayout()
        hdr.addWidget(self._lbl(title, UIConfig.FS_TITLE_S, bold=600))
        hdr.addStretch()
        val = QLabel()
        val.setObjectName("AccentValue")
        hdr.addWidget(val)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setAccessibleName(title)
        slider.valueChanged.connect(handler)
        row.addLayout(hdr)
        row.addWidget(slider)
        parent_layout.addLayout(row)
        return slider, val

    def _refresh_style_widgets(self) -> None:
        """미리보기·값 표시·색 견본을 현재 설정에 맞춥니다."""
        c = self.config
        self.preview_area.update_preview(c)
        self.alpha_val_label.setText(f"{round(c.bg_color.alpha() / 255 * 100)}%")
        self.outline_val_label.setText(f"{c.outline_width}px")
        self.width_val_label.setText(f"{c.width}px")
        self.height_val_label.setText(f"{c.height}px")
        self.size_val_label.setText(f"{c.width} x {c.height}")
        self.font_val_label.setText(f"{c.font_family} · {c.font_size}pt")
        for btn, color in ((self.btn_text_color, c.text_color),
                           (self.btn_bg_color, c.bg_color),
                           (self.btn_out_color, c.outline_color)):
            btn.setStyleSheet(f"background-color: {color.name()};")
            btn.setToolTip(color.name().upper())

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
            "오버레이 표시",
            "가사 오버레이를 화면에 띄웁니다.",
            self.config.visible, self._on_visible_toggled, "overlay_switch",
        ))
        bl.addLayout(self._toggle_row(
            "클릭 통과 (고스트 모드)",
            "켜면 오버레이 위를 클릭해도 뒤에 있는 창이 눌립니다. 게임·작업 중에 켜 두세요.",
            self.config.ghost_mode, self._on_ghost_toggled, "ghost_check",
        ))
        bl.addWidget(self._hline())
        pos_row = QHBoxLayout()
        pos_text = QVBoxLayout()
        pos_text.setSpacing(2)
        pos_text.addWidget(self._lbl("위치·크기", UIConfig.FS_TITLE_S, bold=600))
        pos_desc = self._lbl(
            "누르면 오버레이를 드래그해서 옮기고 오른쪽 아래 모서리로 크기를 바꿀 수 있어요. "
            "끝나면 오버레이의 '완료'를 누르세요.",
            UIConfig.FS_DESC, secondary=True,
        )
        pos_desc.setWordWrap(True)
        pos_text.addWidget(pos_desc)
        pos_row.addLayout(pos_text, 1)
        pos_row.addSpacing(12)
        reset_pos = QPushButton("위치 초기화")
        reset_pos.clicked.connect(self.overlay_reset_requested.emit)
        edit_pos = QPushButton("위치·크기 조정")
        edit_pos.setObjectName("PrimaryButton")
        edit_pos.clicked.connect(self.overlay_edit_requested.emit)
        pos_row.addWidget(reset_pos, 0, Qt.AlignVCenter)
        pos_row.addWidget(edit_pos, 0, Qt.AlignVCenter)
        bl.addLayout(pos_row)
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
            "고스트 모드 토글", self.config.hotkey_ghost, "hotkey_ghost"
        )
        quit_row, self.quit_hk_edit = self._hotkey_row(
            "프로그램 종료", self.config.hotkey_quit, "hotkey_quit"
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
            "키보드의 미디어 키처럼 동작해, 지금 재생 중인 미디어 앱(멜론 등)을 제어합니다. "
            "브라우저에서 영상을 재생 중이면 그쪽이 반응할 수 있어요.\n"
            "입력 칸을 클릭한 뒤 키 조합을 누르세요. Esc는 취소, Backspace는 단축키 해제입니다."
        )
        info.setObjectName("Secondary")
        info.setStyleSheet(f"font-size: {UIConfig.FS_DESC};")
        info.setWordWrap(True)
        ml.addWidget(info)
        ml.addWidget(self._hline())

        next_row, self.next_hk_edit = self._hotkey_row(
            "다음 곡", self.config.hotkey_next, "hotkey_next"
        )
        prev_row, self.prev_hk_edit = self._hotkey_row(
            "이전 곡", self.config.hotkey_prev, "hotkey_prev"
        )
        pause_row, self.pause_hk_edit = self._hotkey_row(
            "재생 / 일시정지", self.config.hotkey_pause, "hotkey_pause"
        )
        ml.addLayout(next_row)
        ml.addLayout(prev_row)
        ml.addLayout(pause_row)
        lay.addWidget(media_card)

        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("단축키 기본값으로")
        reset_btn.clicked.connect(self._reset_hotkeys)
        reset_row.addWidget(reset_btn)
        lay.addLayout(reset_row)

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
        sys_l.addWidget(self._hline())

        # 감상 기록 저장 여부와 개인정보 안내
        sys_l.addLayout(self._toggle_row(
            "감상 기록 저장",
            "들은 곡의 제목·가수·시각·감상 시간을 데이터 폴더의 lyrics_stats.json에 남깁니다. "
            "끄면 오버레이와 가사는 그대로 동작하고, 새 기록과 누적 감상 시간을 저장하지 않습니다. "
            "(대시보드의 '세션' 통계는 이번 실행 동안만 셉니다)",
            getattr(self.app_config, "record_history", True),
            self._on_record_history_toggled, "record_history_check",
        ))
        privacy = self._lbl(
            "감상 기록은 암호화되지 않은 파일로 저장돼요. 데이터 폴더가 '문서' 안에 있고 OneDrive의 "
            "문서 폴더 백업이 켜져 있으면 클라우드에도 동기화될 수 있어요. 원하지 않으면 데이터 경로를 "
            "OneDrive 밖으로 바꾸거나 기록 저장을 끄세요. 이미 쌓인 기록은 '감상 기록' 메뉴에서 지우거나 내보낼 수 있어요.",
            UIConfig.FS_DESC, secondary=True,
        )
        privacy.setWordWrap(True)
        sys_l.addWidget(privacy)
        lay.addWidget(sys_card)

        lay.addWidget(self._section_lbl("창"))
        win_card = Card()
        wl = QVBoxLayout(win_card)
        wl.setContentsMargins(22, 16, 22, 16)
        wl.addLayout(self._toggle_row(
            "창을 닫으면 트레이로 최소화",
            "켜면 창의 X 버튼을 눌러도 가사 오버레이가 계속 실행됩니다. "
            "완전히 끄려면 트레이 아이콘 메뉴의 '종료'나 종료 단축키를 쓰세요.",
            self.config.close_to_tray, self._on_close_to_tray_toggled, "close_to_tray_check",
        ))
        lay.addWidget(win_card)

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
        chk.setAccessibleName(title)
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
        edit.setFixedWidth(190)
        attr = callback  # 설정 속성 이름 (예: "hotkey_ghost")
        self._hotkey_edits[attr] = (edit, label_text)
        edit.changed.connect(lambda text, a=attr: self._on_hotkey_changed(a, text))
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
        items = []
        for name, data in self.config.PRESET_STYLES.items():
            preset = PresetItem(name, data, is_custom=False)
            preset.clicked.connect(self._on_preset_selected)
            items.append(preset)
        for name, data in self.config.custom_presets.items():
            preset = PresetItem(name, data, is_custom=True)
            preset.clicked.connect(self._on_preset_selected)
            preset.delete_requested.connect(self._on_delete_preset)
            items.append(preset)
        self.preset_container.set_items(items)

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
        # 화면 값만 맞추고 변경 핸들러는 다시 부르지 않습니다 (불필요한 저장·재귀 방지).
        widgets = [
            (self.overlay_switch, self.config.visible),
            (self.ghost_check, self.config.ghost_mode),
            (self.song_info_check, self.config.show_song_info),
            (self.media_controls_check, self.config.show_media_controls),
            (self.hide_melon_check, self.config.hide_melon_window),
            (self.alpha_slider, self.config.bg_color.alpha()),
            (self.outline_slider, self.config.outline_width),
            (self.width_slider, self.config.width),
            (self.height_slider, self.config.height),
        ]
        for widget, value in widgets:
            widget.blockSignals(True)
            if isinstance(value, bool):
                widget.setChecked(value)
            else:
                widget.setValue(value)
            widget.blockSignals(False)
        self._refresh_style_widgets()

    # ------------------------------------------------------------------ #
    # 이벤트 핸들러
    # ------------------------------------------------------------------ #

    def _on_visible_toggled(self, checked: bool) -> None:
        self.config.set_visible(checked)
        self.settings_changed.emit()

    def _on_ghost_toggled(self, checked: bool) -> None:
        self.config.set_ghost_mode(checked)
        self.settings_changed.emit()

    def _on_show_song_info_toggled(self, checked: bool) -> None:
        self.config.show_song_info = checked
        self.config.save_to_file()
        self.settings_changed.emit()

    def _on_show_media_controls_toggled(self, checked: bool) -> None:
        self.config.show_media_controls = checked
        self.config.save_to_file()
        self.settings_changed.emit()

    def _on_record_history_toggled(self, checked: bool) -> None:
        if self.app_config:
            self.app_config.record_history = checked

    def _on_close_to_tray_toggled(self, checked: bool) -> None:
        self.config.close_to_tray = checked
        self.config.save_to_file()

    def _on_hide_melon_toggled(self, checked: bool) -> None:
        self.config.hide_melon_window = checked
        self.config.save_to_file()
        self.settings_changed.emit()

    def _on_hotkey_changed(self, attr: str, text: str) -> None:
        """단축키 검증: 글자 하나짜리 조합이나 다른 기능과 겹치는 조합은 되돌립니다."""
        from core.hotkey_manager import is_typing_hotkey

        edit, name = self._hotkey_edits[attr]
        old = getattr(self.config, attr)
        text = text.strip()
        if text and is_typing_hotkey(text):
            edit.set_value(old)
            QMessageBox.warning(
                self, "쓸 수 없는 단축키",
                "글자 하나(또는 Shift+글자)는 다른 프로그램에서 타이핑할 때도 눌려서 쓸 수 없어요.\n"
                "Ctrl이나 Alt를 함께 눌러 주세요.",
            )
            return
        norm = text.replace(" ", "").lower()
        for other, (_, other_name) in self._hotkey_edits.items():
            if other != attr and norm and getattr(self.config, other).replace(" ", "").lower() == norm:
                edit.set_value(old)
                QMessageBox.warning(
                    self, "이미 쓰는 단축키",
                    f"이 조합은 '{other_name}'에 이미 지정돼 있어요. 다른 조합을 골라 주세요.",
                )
                return
        setattr(self.config, attr, text)
        self.config.save_to_file()
        self.hotkeys_changed.emit()

    def _reset_hotkeys(self) -> None:
        from overlay.config_manager import DEFAULT_HOTKEYS

        for attr, value in DEFAULT_HOTKEYS.items():
            setattr(self.config, attr, value)
            self._hotkey_edits[attr][0].set_value(value)
        self.config.save_to_file()
        self.hotkeys_changed.emit()

    def _on_alpha_changed(self, value: int) -> None:
        self.config.update_background(opacity=value)
        self.settings_changed.emit()

    def _on_outline_changed(self, value: int) -> None:
        self.config.update_text_style(outline_width=value)
        self.settings_changed.emit()

    def _on_width_changed(self, value: int) -> None:
        # 움직인 축만 바꿉니다 (다른 축이 슬라이더 범위로 잘리지 않게)
        self.config.update_size(value, self.config.height)
        self.settings_changed.emit()

    def _on_height_changed(self, value: int) -> None:
        self.config.update_size(self.config.width, value)
        self.settings_changed.emit()

    def _pick_color(self, target: str, btn: QPushButton) -> None:
        current_color = getattr(self.config, f"{target}_color")
        color = QColorDialog.getColor(current_color)
        if color.isValid():
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
