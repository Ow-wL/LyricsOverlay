"""설정 페이지."""

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
    QVBoxLayout,
    QWidget,
)

from gui.theme import UIConfig
from gui.widgets.card import Card, PresetItem, StylePreview
from gui.widgets.hotkey_edit import HotkeyEdit
from overlay.config_manager import OverlayConfigManager


class SettingPage(QWidget):
    """오버레이 스타일 및 동작을 설정하는 페이지."""

    settings_changed = Signal()
    hotkeys_changed = Signal()

    def __init__(self, config_manager: OverlayConfigManager):
        super().__init__()
        self.config = config_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(32)

        header = QLabel("오버레이 설정")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 20, 0, 0)
        scroll_layout.setSpacing(24)

        # ── 미리보기 ──────────────────────────────────────────────────
        preview_header = QLabel("오버레이 미리보기")
        preview_header.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; "
            f"color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        scroll_layout.addWidget(preview_header)
        self.preview_area = StylePreview()
        scroll_layout.addWidget(self.preview_area)
        scroll_layout.addSpacing(10)

        # ── 오버레이 활성화 ────────────────────────────────────────────
        control_card = Card()
        control_layout = QHBoxLayout(control_card)
        control_layout.setContentsMargins(24, 24, 24, 24)
        ctrl_vbox = QVBoxLayout()
        ctrl_vbox.addWidget(
            self._make_label("오버레이 활성화", UIConfig.FS_TITLE_M, bold=800)
        )
        ctrl_vbox.addWidget(
            self._make_label("가사 오버레이를 화면에 표시하거나 숨깁니다.", UIConfig.FS_DESC, secondary=True)
        )
        self.overlay_switch = QCheckBox()
        self.overlay_switch.setCursor(Qt.PointingHandCursor)
        self.overlay_switch.setChecked(self.config.visible)
        self.overlay_switch.toggled.connect(self._on_visible_toggled)
        control_layout.addLayout(ctrl_vbox)
        control_layout.addStretch()
        control_layout.addWidget(self.overlay_switch)
        scroll_layout.addWidget(control_card)

        # ── 스타일 프리셋 ──────────────────────────────────────────────
        preset_card = Card()
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(24, 24, 24, 24)
        preset_layout.setSpacing(20)

        preset_header = QHBoxLayout()
        preset_title = QLabel("스타일 프리셋")
        preset_title.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_L}; font-weight: 800; "
            f"color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        preset_header.addWidget(preset_title)
        preset_header.addStretch()

        self.btn_import_styles = QPushButton("가져오기  📥")
        self.btn_import_styles.setFixedHeight(40)
        self.btn_import_styles.clicked.connect(self._import_styles_dialog)

        self.btn_export_styles = QPushButton("내보내기  📤")
        self.btn_export_styles.setFixedHeight(40)
        self.btn_export_styles.clicked.connect(self._export_styles_dialog)

        self.btn_save_preset = QPushButton("현재 스타일 저장  💾")
        self.btn_save_preset.setFixedHeight(40)
        self.btn_save_preset.clicked.connect(self._save_current_as_preset)

        preset_header.addWidget(self.btn_import_styles)
        preset_header.addWidget(self.btn_export_styles)
        preset_header.addWidget(self.btn_save_preset)
        preset_layout.addLayout(preset_header)

        self.preset_container = QWidget()
        self.preset_grid = QGridLayout(self.preset_container)
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setSpacing(16)
        self._update_preset_list()
        preset_layout.addWidget(self.preset_container)
        scroll_layout.addWidget(preset_card)

        # ── 스타일 및 투명도 ───────────────────────────────────────────
        appearance_card = Card()
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(24, 24, 24, 24)
        appearance_layout.setSpacing(20)
        appearance_layout.addWidget(
            self._make_section_title("스타일 및 투명도")
        )

        # 글꼴
        font_hbox = QHBoxLayout()
        font_hbox.addWidget(
            self._make_label("오버레이 글꼴", UIConfig.FS_TITLE_S, bold=600)
        )
        self.btn_font = QPushButton("글꼴 변경  🔤")
        self.btn_font.setObjectName("AccentButton")
        self.btn_font.setFixedSize(140, 40)
        self.btn_font.clicked.connect(self._pick_font)
        font_hbox.addStretch()
        font_hbox.addWidget(self.btn_font)
        appearance_layout.addLayout(font_hbox)

        # 불투명도 슬라이더
        trans_vbox = QVBoxLayout()
        trans_vbox.setSpacing(12)
        trans_header = QHBoxLayout()
        trans_header.addWidget(self._make_label("오버레이 불투명도", UIConfig.FS_TITLE_S, bold=600))
        trans_header.addStretch()
        self.alpha_val_label = QLabel(str(self.config.bg_color.alpha()))
        self.alpha_val_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: #7C4DFF;"
        )
        trans_header.addWidget(self.alpha_val_label)
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(self.config.bg_color.alpha())
        self.alpha_slider.valueChanged.connect(self._on_alpha_changed)
        trans_vbox.addLayout(trans_header)
        trans_vbox.addWidget(self.alpha_slider)
        appearance_layout.addLayout(trans_vbox)

        # 색상 선택
        color_grid = QHBoxLayout()
        color_grid.setSpacing(30)
        color_text_vbox, self.btn_text_color = self._create_color_ctrl(
            "글씨 색상", self.config.text_color, "text"
        )
        color_bg_vbox, self.btn_bg_color = self._create_color_ctrl(
            "배경 색상", self.config.bg_color, "bg"
        )
        color_out_vbox, self.btn_out_color = self._create_color_ctrl(
            "아웃라인 색상", self.config.outline_color, "outline"
        )
        color_grid.addLayout(color_text_vbox)
        color_grid.addLayout(color_bg_vbox)
        color_grid.addLayout(color_out_vbox)
        color_grid.addStretch()
        appearance_layout.addLayout(color_grid)

        # 아웃라인 두께 슬라이더
        outline_vbox = QVBoxLayout()
        outline_vbox.setSpacing(12)
        outline_header = QHBoxLayout()
        outline_header.addWidget(self._make_label("아웃라인 두께", UIConfig.FS_TITLE_S, bold=600))
        outline_header.addStretch()
        self.outline_val_label = QLabel(str(self.config.outline_width))
        self.outline_val_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: #7C4DFF;"
        )
        outline_header.addWidget(self.outline_val_label)
        self.outline_slider = QSlider(Qt.Horizontal)
        self.outline_slider.setRange(0, 10)
        self.outline_slider.setValue(self.config.outline_width)
        self.outline_slider.valueChanged.connect(self._on_outline_changed)
        outline_vbox.addLayout(outline_header)
        outline_vbox.addWidget(self.outline_slider)
        appearance_layout.addLayout(outline_vbox)

        # 오버레이 크기 슬라이더
        size_vbox = QVBoxLayout()
        size_vbox.setSpacing(12)
        size_header = QHBoxLayout()
        size_header.addWidget(
            self._make_label("오버레이 크기 (너비 / 높이)", UIConfig.FS_TITLE_S, bold=600)
        )
        size_header.addStretch()
        self.size_val_label = QLabel(f"{self.config.width} x {self.config.height}")
        self.size_val_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: #7C4DFF;"
        )
        size_header.addWidget(self.size_val_label)
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
        size_vbox.addLayout(size_header)
        size_vbox.addLayout(size_sliders)
        appearance_layout.addLayout(size_vbox)
        scroll_layout.addWidget(appearance_card)

        # ── 인식 및 상호작용 ───────────────────────────────────────────
        interaction_card = Card()
        interaction_layout = QVBoxLayout(interaction_card)
        interaction_layout.setContentsMargins(24, 24, 24, 24)
        interaction_layout.setSpacing(20)
        interaction_layout.addWidget(self._make_section_title("인식 및 상호작용"))

        interaction_layout.addLayout(
            self._make_toggle_row(
                "고스트 모드",
                "오버레이가 마우스 클릭을 통과하도록 설정합니다.",
                self.config.ghost_mode,
                self._on_ghost_toggled,
                "ghost_check",
            )
        )
        interaction_layout.addWidget(self._make_hline())
        interaction_layout.addLayout(
            self._make_toggle_row(
                "오버레이 위치 이동",
                "오버레이를 드래그하여 위치를 변경할 수 있도록 합니다.",
                self.config.move_enabled,
                self._on_move_toggled,
                "move_check",
            )
        )
        interaction_layout.addLayout(
            self._make_toggle_row(
                "오버레이 크기 조절",
                "오버레이 우측 하단을 드래그하여 크기를 조절할 수 있도록 합니다.",
                self.config.resize_enabled,
                self._on_resize_toggled,
                "resize_check",
            )
        )
        interaction_layout.addWidget(self._make_hline())

        # ROI (비활성화됨)
        roi_vbox = QVBoxLayout()
        roi_vbox.setSpacing(12)
        roi_title = QLabel("영역 설정 (비활성화됨)")
        roi_title.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600; color: #AAAAAA;"
        )
        roi_desc = QLabel("가사가 출력되는 멜론 창의 영역을 직접 선택합니다.")
        roi_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: #AAAAAA;")
        self.roi_btn = QPushButton("가사 인식 영역 설정 (ROI)  🎯")
        self.roi_btn.setEnabled(False)
        self.roi_btn.setMinimumHeight(55)
        self.roi_btn.setStyleSheet(
            "background-color: #EEEEEE; color: #AAAAAA; border-radius: 10px;"
        )
        roi_vbox.addWidget(roi_title)
        roi_vbox.addWidget(roi_desc)
        roi_vbox.addWidget(self.roi_btn)
        interaction_layout.addLayout(roi_vbox)
        scroll_layout.addWidget(interaction_card)

        # ── 단축키 설정 ────────────────────────────────────────────────
        hotkey_card = Card()
        hotkey_layout = QVBoxLayout(hotkey_card)
        hotkey_layout.setContentsMargins(24, 24, 24, 24)
        hotkey_layout.setSpacing(20)
        hotkey_layout.addWidget(self._make_section_title("단축키 설정"))

        ghost_hk_hbox, self.ghost_hk_edit = self._make_hotkey_row(
            "고스트 모드 토글", self.config.hotkey_ghost, self._on_hotkey_ghost_changed
        )
        quit_hk_hbox, self.quit_hk_edit = self._make_hotkey_row(
            "프로그램 종료", self.config.hotkey_quit, self._on_hotkey_quit_changed
        )
        hotkey_layout.addLayout(ghost_hk_hbox)
        hotkey_layout.addLayout(quit_hk_hbox)
        scroll_layout.addWidget(hotkey_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.refresh_ui_from_config()

    # ------------------------------------------------------------------ #
    # 헬퍼 위젯 팩토리
    # ------------------------------------------------------------------ #

    def _make_label(
        self,
        text: str,
        font_size: str,
        bold: int = 400,
        secondary: bool = False,
    ) -> QLabel:
        lbl = QLabel(text)
        color_style = (
            f"color: {UIConfig.COLOR_SECONDARY_TEXT};" if secondary else ""
        )
        lbl.setStyleSheet(
            f"font-size: {font_size}; font-weight: {bold}; {color_style}"
        )
        return lbl

    def _make_section_title(self, text: str) -> QLabel:
        return self._make_label(text, UIConfig.FS_TITLE_L, bold=800, secondary=True)

    def _make_hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #E0E0E0;")
        return line

    def _make_toggle_row(
        self,
        title: str,
        desc: str,
        checked: bool,
        callback,
        attr_name: str,
    ) -> QHBoxLayout:
        hbox = QHBoxLayout()
        vbox = QVBoxLayout()
        vbox.addWidget(self._make_label(title, UIConfig.FS_TITLE_S, bold=600))
        vbox.addWidget(self._make_label(desc, UIConfig.FS_DESC, secondary=True))
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

    def _make_hotkey_row(
        self, label_text: str, current_val: str, callback
    ) -> tuple:
        hbox = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;"
        )
        edit = HotkeyEdit(current_val)
        edit.setFixedWidth(150)
        edit.changed.connect(callback)
        hbox.addWidget(lbl)
        hbox.addStretch()
        hbox.addWidget(edit)
        return hbox, edit

    def _create_color_ctrl(self, label_text: str, color_obj, target: str):
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
        """설정 변경 후 UI 요소 상태를 업데이트합니다."""
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

    def _on_hotkey_ghost_changed(self, text: str) -> None:
        self.config.update_hotkey_ghost(text.strip())
        self.settings_changed.emit()
        self.hotkeys_changed.emit()

    def _on_hotkey_quit_changed(self, text: str) -> None:
        self.config.update_hotkey_quit(text.strip())
        self.settings_changed.emit()
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
        ok, font = QFontDialog.getFont(current_font, self)
        if ok:
            self.config.update_font(family=font.family(), size=font.pointSize())
            self.settings_changed.emit()
