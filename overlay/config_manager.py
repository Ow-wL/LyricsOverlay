import json
import os

from PySide6.QtGui import QColor, QFont  # type: ignore


class OverlayConfigManager:
    """오버레이 스타일 및 설정을 관리하는 매니저 클래스."""

    def __init__(
        self,
        data_dir: str
    ):
        self.data_dir = data_dir
        self.config_path = os.path.join(data_dir, "overlay_settings.json")
        self.styles_path = os.path.join(data_dir, "overlay_styles.json")
        self.PRESET_STYLES: dict = {}
        self.custom_presets: dict = {}

        self.load_styles()

        # 기본값
        self.bg_color = QColor(0, 0, 0, 100)
        self.text_color = QColor(255, 255, 255)
        self.outline_color = QColor(0, 0, 0)
        self.outline_width = 2
        self.font_family = "Pretendard"
        self.font_size = 22
        self.ghost_mode = True
        self.visible = True
        self.move_enabled = False
        self.resize_enabled = False
        self.hotkey_ghost = "F9"
        self.hotkey_quit = "Shift+Q"
        self.x = 460
        self.y = 800
        self.width = 800
        self.height = 150
        self.dashboard_view_mode = "session"
        self.show_song_info = True

        self.load_from_file()

    # ------------------------------------------------------------------ #
    # 스타일 프리셋 관련
    # ------------------------------------------------------------------ #

    def load_styles(self) -> None:
        """별도의 파일에서 프리셋 스타일을 로드합니다."""
        if os.path.exists(self.styles_path):
            try:
                with open(self.styles_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and (
                    "system_presets" in data or "custom_presets" in data
                ):
                    self.PRESET_STYLES = data.get("system_presets", {})
                    self.custom_presets = data.get("custom_presets", {})
                else:
                    self.PRESET_STYLES = data
                    self.custom_presets = {}
            except Exception as e:
                print(f"Failed to load styles from {self.styles_path}: {e}")
                self.PRESET_STYLES = {}
                self.custom_presets = {}
        else:
            self.PRESET_STYLES = {
                "기본 (반투명 검정)": {
                    "bg_color": "#000000",
                    "bg_alpha": 100,
                    "text_color": "#FFFFFF",
                    "outline_color": "#000000",
                    "outline_width": 2,
                    "font_family": "Pretendard",
                    "font_size": 22
                },
                "모던 다크 (Modern Dark)": {
                    "bg_color": "#1e1e1e",
                    "bg_alpha": 220,
                    "text_color": "#FFFFFF",
                    "outline_color": "#000000",
                    "outline_width": 1,
                    "font_family": "Pretendard",
                    "font_size": 20
                },
                "네온 핑크 (Neon Pink)": {
                    "bg_color": "#0f0f15",
                    "bg_alpha": 200,
                    "text_color": "#ff2a75",
                    "outline_color": "#4a0018",
                    "outline_width": 2,
                    "font_family": "Pretendard",
                    "font_size": 24
                },
                "애플 라이트 (Apple Light)": {
                    "bg_color": "#F5F5F7",
                    "bg_alpha": 230,
                    "text_color": "#1D1D1F",
                    "outline_color": "#FFFFFF",
                    "outline_width": 1,
                    "font_family": "Pretendard",
                    "font_size": 22
                }
            }
            self.custom_presets = {}
            self.save_styles()

    def save_styles(self) -> None:
        """현재 프리셋 스타일을 파일에 저장합니다."""
        try:
            data = {
                "system_presets": self.PRESET_STYLES,
                "custom_presets": self.custom_presets,
            }
            with open(self.styles_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save styles to {self.styles_path}: {e}")

    def export_styles(self, export_path: str) -> bool:
        """프리셋 스타일을 외부 파일로 내보냅니다."""
        try:
            export_data = {
                "system_presets": self.PRESET_STYLES,
                "custom_presets": self.custom_presets,
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to export styles: {e}")
            return False

    def import_styles(self, import_path: str) -> bool:
        """외부 파일에서 프리셋 스타일을 가져옵니다."""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
            if "system_presets" in import_data or "custom_presets" in import_data:
                if "system_presets" in import_data:
                    self.PRESET_STYLES.update(import_data["system_presets"])
                if "custom_presets" in import_data:
                    self.custom_presets.update(import_data["custom_presets"])
            else:
                self.PRESET_STYLES.update(import_data)
            self.save_styles()
            self.save_to_file()
            return True
        except Exception as e:
            print(f"Failed to import styles: {e}")
            return False

    def apply_preset(self, preset_data: dict) -> None:
        """프리셋 데이터를 현재 설정에 적용합니다."""
        if "bg_color" in preset_data:
            self.bg_color = QColor(preset_data["bg_color"])
            if "bg_alpha" in preset_data:
                self.bg_color.setAlpha(preset_data["bg_alpha"])
        if "text_color" in preset_data:
            self.text_color = QColor(preset_data["text_color"])
        if "outline_color" in preset_data:
            self.outline_color = QColor(preset_data["outline_color"])
        if "outline_width" in preset_data:
            self.outline_width = preset_data["outline_width"]
        if "font_family" in preset_data:
            self.font_family = preset_data["font_family"]
        if "font_size" in preset_data:
            self.font_size = preset_data["font_size"]
        self.save_to_file()

    def save_custom_preset(self, name: str) -> None:
        """현재 스타일을 사용자 프리셋으로 저장합니다."""
        self.custom_presets[name] = {
            "bg_color": self.bg_color.name(),
            "bg_alpha": self.bg_color.alpha(),
            "text_color": self.text_color.name(),
            "outline_color": self.outline_color.name(),
            "outline_width": self.outline_width,
            "font_family": self.font_family,
            "font_size": self.font_size,
        }
        self.save_styles()

    def delete_custom_preset(self, name: str) -> None:
        """사용자 프리셋을 삭제합니다."""
        if name in self.custom_presets:
            del self.custom_presets[name]
            self.save_styles()

    # ------------------------------------------------------------------ #
    # 설정 조회/갱신
    # ------------------------------------------------------------------ #

    def get_settings(self) -> dict:
        """현재 설정을 dict로 반환합니다 (LyricsOverlay.apply_settings 호환)."""
        return {
            "bg_color": self.bg_color,
            "text_color": self.text_color,
            "out_color": self.outline_color,
            "out_width": self.outline_width,
            "font": QFont(self.font_family, self.font_size),
            "ghost": self.ghost_mode,
            "visible": self.visible,
            "move_enabled": self.move_enabled,
            "resize_enabled": self.resize_enabled,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "show_song_info": self.show_song_info,
        }

    def update_background(self, color=None, opacity: int | None = None) -> None:
        """배경색 및 투명도 업데이트 (opacity: 0~255)."""
        if color:
            new_color = QColor(color)
            new_color.setAlpha(
                opacity if opacity is not None else self.bg_color.alpha()
            )
            self.bg_color = new_color
        elif opacity is not None:
            self.bg_color.setAlpha(opacity)
        self.save_to_file()

    def update_text_style(
        self,
        color=None,
        outline_color=None,
        outline_width: int | None = None,
    ) -> None:
        """글자 스타일 업데이트."""
        if color:
            self.text_color = QColor(color)
        if outline_color:
            self.outline_color = QColor(outline_color)
        if outline_width is not None:
            self.outline_width = outline_width
        self.save_to_file()

    def update_font(self, family: str | None = None, size: int | None = None) -> None:
        """폰트 업데이트."""
        if family:
            self.font_family = family
        if size is not None:
            self.font_size = size
        self.save_to_file()

    def update_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.save_to_file()

    def update_size(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.save_to_file()

    def set_visible(self, visible: bool) -> None:
        self.visible = visible
        self.save_to_file()

    def set_ghost_mode(self, ghost: bool) -> None:
        self.ghost_mode = ghost
        self.save_to_file()

    def set_move_enabled(self, enabled: bool) -> None:
        self.move_enabled = enabled
        self.save_to_file()

    def set_resize_enabled(self, enabled: bool) -> None:
        self.resize_enabled = enabled
        self.save_to_file()

    def update_hotkey_ghost(self, hotkey: str) -> None:
        self.hotkey_ghost = hotkey
        self.save_to_file()

    def update_hotkey_quit(self, hotkey: str) -> None:
        self.hotkey_quit = hotkey
        self.save_to_file()

    # ------------------------------------------------------------------ #
    # 파일 I/O
    # ------------------------------------------------------------------ #

    def save_to_file(self) -> None:
        """설정을 JSON 파일로 저장합니다."""
        try:
            data = {
                "bg_color": self.bg_color.name(),
                "bg_alpha": self.bg_color.alpha(),
                "text_color": self.text_color.name(),
                "outline_color": self.outline_color.name(),
                "outline_width": self.outline_width,
                "font_family": self.font_family,
                "font_size": self.font_size,
                "ghost_mode": self.ghost_mode,
                "visible": self.visible,
                "move_enabled": self.move_enabled,
                "resize_enabled": self.resize_enabled,
                "hotkey_ghost": self.hotkey_ghost,
                "hotkey_quit": self.hotkey_quit,
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
                "dashboard_view_mode": self.dashboard_view_mode,
                "show_song_info": self.show_song_info,
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_from_file(self) -> None:
        """JSON 파일에서 설정을 로드합니다."""
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "bg_color" in data:
                self.bg_color = QColor(data["bg_color"])
                if "bg_alpha" in data:
                    self.bg_color.setAlpha(data["bg_alpha"])
            if "text_color" in data:
                self.text_color = QColor(data["text_color"])
            if "outline_color" in data:
                self.outline_color = QColor(data["outline_color"])

            self.outline_width = data.get("outline_width", self.outline_width)
            self.font_family = data.get("font_family", self.font_family)
            self.font_size = data.get("font_size", self.font_size)
            self.ghost_mode = data.get("ghost_mode", self.ghost_mode)
            self.visible = data.get("visible", self.visible)
            self.move_enabled = data.get("move_enabled", self.move_enabled)
            self.resize_enabled = data.get("resize_enabled", self.resize_enabled)
            self.hotkey_ghost = data.get("hotkey_ghost", self.hotkey_ghost)
            self.hotkey_quit = data.get("hotkey_quit", self.hotkey_quit)
            self.x = data.get("x", self.x)
            self.y = data.get("y", self.y)
            self.width = data.get("width", self.width)
            self.height = data.get("height", self.height)
            self.dashboard_view_mode = data.get("dashboard_view_mode", self.dashboard_view_mode)
            self.show_song_info = data.get("show_song_info", self.show_song_info)
        except Exception as e:
            print(f"Failed to load settings: {e}")
