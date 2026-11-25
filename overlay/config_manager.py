import json
import os

from PySide6.QtCore import QTimer  # type: ignore
from PySide6.QtGui import QColor, QFont  # type: ignore

from core.utils import atomic_write_json

# 예전 기본값. 전역 단축키라 다른 프로그램에서 대문자 Q만 쳐도 종료돼서 바꿨습니다.
_LEGACY_QUIT_HOTKEY = "shift+q"
DEFAULT_QUIT_HOTKEY = "ctrl+alt+q"
DEFAULT_HOTKEYS = {
    "hotkey_ghost": "F9",
    "hotkey_quit": DEFAULT_QUIT_HOTKEY,
    "hotkey_next": "ctrl+shift+right",
    "hotkey_prev": "ctrl+shift+left",
    "hotkey_pause": "F8",
}
# 멜론 창 캡처 이미지에서 가사(현재·다음 줄)가 있는 영역 [x, y, w, h] (100% 배율 기본 레이아웃 기준)
DEFAULT_ROI = [28, 216, 251, 46]


# ------------------------------------------------------------------ #
# 값 검증: 잘못된 JSON 하나 때문에 앱이 매번 시작하다 죽지 않도록,
# 형식이 틀린 값은 버리고 기본값을 씁니다.
# ------------------------------------------------------------------ #

def _int_in(value, lo: int, hi: int):
    """정수이고 범위 안이면 그 값, 아니면 None (bool은 정수로 치지 않음)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = int(value)
    return value if lo <= value <= hi else None


def _color(value):
    if not isinstance(value, str):
        return None
    c = QColor(value)
    return c if c.isValid() else None


def _font_family(value):
    if isinstance(value, str) and 0 < len(value) <= 100:
        return value
    return None


def sanitize_preset(data) -> dict | None:
    """프리셋 dict에서 올바른 값만 남깁니다. 쓸 값이 하나도 없으면 None."""
    if not isinstance(data, dict):
        return None
    clean: dict = {}
    for key in ("bg_color", "text_color", "outline_color"):
        c = _color(data.get(key))
        if c is not None:
            clean[key] = c.name()
    for key, lo, hi in (("bg_alpha", 0, 255), ("outline_width", 0, 10), ("font_size", 6, 120)):
        v = _int_in(data.get(key), lo, hi)
        if v is not None:
            clean[key] = v
    fam = _font_family(data.get("font_family"))
    if fam:
        clean["font_family"] = fam
    return clean or None


def _sanitize_presets(data) -> dict:
    if not isinstance(data, dict):
        return {}
    out = {}
    for name, preset in data.items():
        if isinstance(name, str) and name.strip() and len(name) <= 60:
            clean = sanitize_preset(preset)
            if clean:
                out[name.strip()] = clean
    return out


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
        self.hotkey_quit = DEFAULT_QUIT_HOTKEY
        self.hotkey_next = "ctrl+shift+right"
        self.hotkey_prev = "ctrl+shift+left"
        self.hotkey_pause = "F8"
        self.x = 460
        self.y = 800
        self.width = 800
        self.height = 150
        self.dashboard_view_mode = "session"
        self.show_song_info = True
        # 고스트 모드일 때 멜론 창을 투명하게 숨길지 (끄면 멜론 창과 오버레이를 함께 사용)
        self.hide_melon_window = True
        # 오버레이에 마우스를 올리면 재생 버튼 표시 (고스트 모드가 꺼져 있을 때만 동작)
        self.show_media_controls = True
        # 창 닫기(X)를 누르면 종료하지 않고 트레이로 숨김
        self.close_to_tray = True
        # 대시보드 시작 안내를 다 봤는지. 설정 파일이 이미 있던 기존 사용자는 보지 않습니다.
        self.onboarding_done = False
        self.roi = list(DEFAULT_ROI)

        self.load_from_file()

    def set_data_dir(self, data_dir: str) -> None:
        """데이터 경로가 바뀌면 파일 경로를 바꾸고 현재 설정과 프리셋을 새 경로에 저장합니다."""
        self.data_dir = data_dir
        self.config_path = os.path.join(data_dir, "overlay_settings.json")
        self.styles_path = os.path.join(data_dir, "overlay_styles.json")
        self.save_styles()
        self.save_now()

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
                    self.PRESET_STYLES = _sanitize_presets(data.get("system_presets", {}))
                    self.custom_presets = _sanitize_presets(data.get("custom_presets", {}))
                else:
                    self.PRESET_STYLES = _sanitize_presets(data)
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
            atomic_write_json(self.styles_path, data)
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

    def import_styles(self, import_path: str) -> int:
        """외부 파일의 프리셋을 '내 프리셋'으로 가져옵니다. 가져온 개수를 반환 (0 = 실패).

        기본 프리셋은 덮어쓰지 않고, 형식이 틀린 값은 버립니다.
        """
        try:
            if os.path.getsize(import_path) > 1_000_000:
                return 0
            with open(import_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
            if not isinstance(import_data, dict):
                return 0
            if "system_presets" in import_data or "custom_presets" in import_data:
                incoming = {
                    **_sanitize_presets(import_data.get("system_presets", {})),
                    **_sanitize_presets(import_data.get("custom_presets", {})),
                }
            else:
                incoming = _sanitize_presets(import_data)
            if not incoming:
                return 0
            self.custom_presets.update(incoming)
            self.save_styles()
            return len(incoming)
        except Exception as e:
            print(f"Failed to import styles: {e}")
            return 0

    def apply_preset(self, preset_data: dict) -> None:
        """프리셋 데이터를 현재 설정에 적용합니다."""
        preset_data = sanitize_preset(preset_data) or {}
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
            "show_media_controls": self.show_media_controls,
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

    def set_roi(self, roi: list[int] | None) -> None:
        """가사 인식 영역을 바꿉니다. None이면 기본값으로."""
        self.roi = list(roi) if roi else list(DEFAULT_ROI)
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

    def update_hotkey_next(self, hotkey: str) -> None:
        self.hotkey_next = hotkey
        self.save_to_file()

    def update_hotkey_prev(self, hotkey: str) -> None:
        self.hotkey_prev = hotkey
        self.save_to_file()

    def update_hotkey_pause(self, hotkey: str) -> None:
        self.hotkey_pause = hotkey
        self.save_to_file()

    # ------------------------------------------------------------------ #
    # 파일 I/O
    # ------------------------------------------------------------------ #

    def save_to_file(self) -> None:
        """설정 저장을 예약합니다.

        드래그나 슬라이더처럼 값이 연달아 바뀔 때 매번 디스크에 쓰지 않도록,
        마지막 변경 후 0.4초 뒤에 한 번만 저장합니다. 종료할 때는 save_now()로 마무리합니다.
        """
        if not hasattr(self, "_save_timer"):
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.setInterval(400)
            self._save_timer.timeout.connect(self.save_now)
        self._save_timer.start()

    def save_now(self) -> None:
        """설정을 JSON 파일로 바로 저장합니다."""
        if hasattr(self, "_save_timer"):
            self._save_timer.stop()
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
                "hotkey_next": self.hotkey_next,
                "hotkey_prev": self.hotkey_prev,
                "hotkey_pause": self.hotkey_pause,
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
                "dashboard_view_mode": self.dashboard_view_mode,
                "show_song_info": self.show_song_info,
                "hide_melon_window": self.hide_melon_window,
                "show_media_controls": self.show_media_controls,
                "close_to_tray": self.close_to_tray,
                "onboarding_done": self.onboarding_done,
                "roi": self.roi,
            }
            atomic_write_json(self.config_path, data)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_from_file(self) -> None:
        """JSON 파일에서 설정을 로드합니다."""
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("설정 파일 형식이 올바르지 않습니다")
        except Exception as e:
            print(f"Failed to load settings: {e}")
            return

        # 예전 버전부터 쓰던 사람(키가 없는 설정 파일)은 시작 안내가 필요 없습니다.
        if "onboarding_done" not in data:
            self.onboarding_done = True

        # 값마다 형식을 확인하고, 틀린 값은 버리고 기본값을 유지합니다.
        style = sanitize_preset(data) or {}
        if "bg_color" in style:
            self.bg_color = QColor(style["bg_color"])
        if "bg_alpha" in style:
            self.bg_color.setAlpha(style["bg_alpha"])
        if "text_color" in style:
            self.text_color = QColor(style["text_color"])
        if "outline_color" in style:
            self.outline_color = QColor(style["outline_color"])
        self.outline_width = style.get("outline_width", self.outline_width)
        self.font_family = style.get("font_family", self.font_family)
        self.font_size = style.get("font_size", self.font_size)

        for key in ("ghost_mode", "visible", "move_enabled", "resize_enabled",
                    "show_song_info", "hide_melon_window", "show_media_controls",
                    "close_to_tray", "onboarding_done"):
            if isinstance(data.get(key), bool):
                setattr(self, key, data[key])
        for key in ("hotkey_ghost", "hotkey_quit", "hotkey_next", "hotkey_prev", "hotkey_pause"):
            value = data.get(key)
            if isinstance(value, str) and len(value) <= 60:
                setattr(self, key, value)
        for key, lo, hi in (("x", -20000, 20000), ("y", -20000, 20000),
                            ("width", 200, 4000), ("height", 80, 2000)):
            v = _int_in(data.get(key), lo, hi)
            if v is not None:
                setattr(self, key, v)
        roi = data.get("roi")
        if isinstance(roi, list) and len(roi) == 4:
            vals = [_int_in(v, 0, 10000) for v in roi]
            if None not in vals and vals[2] >= 10 and vals[3] >= 10:
                self.roi = vals
        if data.get("dashboard_view_mode") in ("session", "daily", "weekly", "monthly"):
            self.dashboard_view_mode = data["dashboard_view_mode"]

        if self.hotkey_quit.replace(" ", "").lower() in (
            _LEGACY_QUIT_HOTKEY, "leftshift+q", "rightshift+q"
        ):
            print(f"[⌨️] 종료 단축키를 {self.hotkey_quit} → {DEFAULT_QUIT_HOTKEY}로 변경합니다.")
            self.hotkey_quit = DEFAULT_QUIT_HOTKEY
            self.save_to_file()
