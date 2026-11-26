"""테마 설정: UIConfig(글꼴 크기 등 공통 값), Theme(라이트/다크 색상 토큰), ThemeManager.

디자인 방향: 시안 A '아트워크 중심 플랫' (Spotify·YouTube Music 계열). 단색 바탕, 장식 대신 앨범 커버.
색상은 모두 이 파일의 토큰에서 가져오고, 위젯에는 색을 직접 적지 않습니다.
"""


class UIConfig:
    # ----- Font Sizes -----
    FS_HEADER_MAIN = "30px"
    FS_SIDEBAR_TITLE = "18px"
    FS_TITLE_L = "20px"
    FS_TITLE_M = "18px"
    FS_TITLE_S = "15px"
    FS_DESC = "13px"
    FS_BODY = "14px"
    FS_LIST = "14px"
    FS_BUTTON = "13px"
    FS_THEME_BUTTON = "13px"
    FS_SIDEBAR_BTN = "14px"
    FS_CHECKBOX = "14px"

    # ----- 이전 코드 호환용 -----
    COLOR_SECONDARY_TEXT = "#6B7090"
    LIGHT_BORDER = "#E3E5F0"

    # ----- 레이아웃 -----
    RADIUS_CARD = 12
    RADIUS_CONTROL = 10


def _rgba(r: int, g: int, b: int, a: float) -> str:
    """QSS용 rgba 문자열 (알파는 0~1 → 0~255 정수)."""
    return f"rgba({r}, {g}, {b}, {round(a * 255)})"


class Theme:
    """시안 A '아트워크 중심 플랫': 단색 바탕과 카드, 색은 앨범 커버가 만들고 강조색은 재생·주요 버튼에만."""

    LIGHT = {
        "name": "light",
        "bg_top": "#F6F6F8",
        "bg_bottom": "#F6F6F8",
        "blobs": [],
        "side": "#EFEFF3",
        "card": "#FFFFFF",
        # 버튼·입력 등 (이름은 예전 그대로 둡니다)
        "glass": "#FFFFFF",
        "glass_strong": "#F1F1F5",
        "glass_border": "#E4E4EA",
        "glass_hover": "#EBEBF1",
        "glass_pressed": "#E2E2EA",
        "hairline": "#E9E9EE",
        "track": "#E1E1E8",
        "shadow": (20, 20, 50, 14),
        "nav_on": "#E6E4FA",
        "nav_on_fg": "#2B1B78",
        "text_primary": "#121318",
        "text_secondary": "#34384F",
        "text_tertiary": "#474B66",
        "text_on_accent": "#FFFFFF",
        "accent": "#5B4BE0",
        "accent_2": "#5B4BE0",
        "accent_hover": "#4A3BCC",
        "fill_1": "#5B4BE0",
        "fill_2": "#5B4BE0",
        "fill_hover": "#4A3BCC",
        "accent_soft": _rgba(91, 75, 224, 0.10),
        "accent_soft_strong": _rgba(91, 75, 224, 0.22),
        "input_bg": "#FFFFFF",
        "solid_bg": "#F6F6F8",
        "solid_card": "#FFFFFF",
        "selection": _rgba(91, 75, 224, 0.12),
        "danger": "#E5484D",
        "status_ok": "#167A47",
        "status_warn": "#965A00",
        "status_error": "#C42B30",
    }
    DARK = {
        "name": "dark",
        "bg_top": "#0F1016",
        "bg_bottom": "#0F1016",
        "blobs": [],
        "side": "#0B0C11",
        "card": "#171821",
        "glass": "#171821",
        "glass_strong": "#22242F",
        "glass_border": "#262834",
        "glass_hover": "#20222D",
        "glass_pressed": "#2A2C3A",
        "hairline": "#23252F",
        "track": "#2C2E3A",
        "shadow": (0, 0, 0, 0),
        "nav_on": "#1F2131",
        "nav_on_fg": "#FFFFFF",
        "text_primary": "#F2F3F8",
        "text_secondary": "#BEC2DC",
        "text_tertiary": "#A3A8C6",
        "text_on_accent": "#FFFFFF",
        "accent": "#9D90FF",
        "accent_2": "#9D90FF",
        "accent_hover": "#B1A6FF",
        "fill_1": "#6E5BFF",
        "fill_2": "#6E5BFF",
        "fill_hover": "#7D6CFF",
        "accent_soft": _rgba(157, 144, 255, 0.14),
        "accent_soft_strong": _rgba(157, 144, 255, 0.28),
        "input_bg": "#1C1D27",
        "solid_bg": "#14151D",
        "solid_card": "#1C1D27",
        "selection": _rgba(157, 144, 255, 0.20),
        "danger": "#FF6B70",
        "status_ok": "#4ADE80",
        "status_warn": "#FBBF24",
        "status_error": "#FF7A7F",
    }


# 직접 그리는 위젯(차트, 프리셋 타일 등)이 현재 테마 색을 읽을 수 있게 보관합니다.
_active_theme: dict = Theme.LIGHT


def active() -> dict:
    return _active_theme


def set_active(theme: dict) -> None:
    global _active_theme
    _active_theme = theme


class ThemeManager:
    def __init__(self):
        self.current_theme: dict = Theme.LIGHT

    def toggle_theme(self) -> dict:
        self.current_theme = (
            Theme.DARK if self.current_theme is Theme.LIGHT else Theme.LIGHT
        )
        return self.current_theme
