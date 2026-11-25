"""테마 설정: UIConfig(글꼴 크기 등 공통 값), Theme(라이트/다크 색상 토큰), ThemeManager.

디자인 방향: 오로라 그라데이션 배경 위에 반투명 '유리' 패널을 올리는 글래스모피즘.
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
    RADIUS_CARD = 18
    RADIUS_CONTROL = 10


def _rgba(r: int, g: int, b: int, a: float) -> str:
    """QSS용 rgba 문자열 (알파는 0~1 → 0~255 정수)."""
    return f"rgba({r}, {g}, {b}, {round(a * 255)})"


class Theme:
    LIGHT = {
        "name": "light",
        # 배경: 기본 그라데이션 + 은은한 색 번짐(blob)
        "bg_top": "#F1F2FA",
        "bg_bottom": "#E9ECF7",
        "blobs": [  # (x 비율, y 비율, 반지름 비율, 색, 알파)
            (0.12, 0.10, 0.55, "#B9A8FF", 0.55),
            (0.88, 0.18, 0.50, "#9CC7FF", 0.50),
            (0.70, 0.95, 0.60, "#FFC4E1", 0.45),
        ],
        # 유리 패널
        "glass": _rgba(255, 255, 255, 0.50),
        "glass_strong": _rgba(255, 255, 255, 0.74),
        "glass_border": _rgba(255, 255, 255, 0.90),
        "glass_hover": _rgba(255, 255, 255, 0.80),
        "glass_pressed": _rgba(255, 255, 255, 0.95),
        "hairline": _rgba(30, 34, 80, 0.08),
        "track": _rgba(30, 34, 80, 0.12),
        "shadow": (60, 60, 120, 30),
        # 글자
        "text_primary": "#16182C",
        "text_secondary": "#474B68",
        "text_tertiary": "#5F6382",  # 밝은 배경 대비 4.9:1 이상 (WCAG AA)
        "text_on_accent": "#FFFFFF",
        # 강조색 (보라 → 파랑 그라데이션)
        "accent": "#5B4BE0",
        "accent_2": "#3E8BFF",
        "accent_hover": "#4A3BCC",
        # 흰 글자를 올리는 채움 배경 (선택된 메뉴, 주요 버튼) — 흰 글자 대비 4.5:1 이상
        "fill_1": "#5B4BE0",
        "fill_2": "#2F6FE0",
        "fill_hover": "#4A3BCC",
        "accent_soft": _rgba(108, 92, 246, 0.13),
        "accent_soft_strong": _rgba(108, 92, 246, 0.22),
        # 입력칸·대화상자처럼 불투명해야 하는 곳
        "input_bg": _rgba(255, 255, 255, 0.78),
        "solid_bg": "#F5F6FC",
        "solid_card": "#FFFFFF",
        "selection": _rgba(108, 92, 246, 0.16),
        "danger": "#E5484D",
        # 상태 글자색 (밝은 배경에서도 4.5:1 이상)
        "status_ok": "#167A47",
        "status_warn": "#965A00",
        "status_error": "#C42B30",
    }
    DARK = {
        "name": "dark",
        "bg_top": "#0D0E1A",
        "bg_bottom": "#0A0B14",
        "blobs": [
            (0.10, 0.08, 0.55, "#6D3BFF", 0.42),
            (0.92, 0.22, 0.50, "#1F6FFF", 0.34),
            (0.65, 1.00, 0.60, "#C2307E", 0.26),
        ],
        "glass": _rgba(255, 255, 255, 0.055),
        "glass_strong": _rgba(255, 255, 255, 0.095),
        "glass_border": _rgba(255, 255, 255, 0.13),
        "glass_hover": _rgba(255, 255, 255, 0.11),
        "glass_pressed": _rgba(255, 255, 255, 0.16),
        "hairline": _rgba(255, 255, 255, 0.08),
        "track": _rgba(255, 255, 255, 0.14),
        "shadow": (0, 0, 0, 110),
        "text_primary": "#ECEDF8",
        "text_secondary": "#A4A8C4",
        "text_tertiary": "#8287A6",
        "text_on_accent": "#FFFFFF",
        "accent": "#8B7BFF",
        "accent_2": "#4D93FF",
        "accent_hover": "#9D8FFF",
        "fill_1": "#5B4BE0",
        "fill_2": "#2E6BD8",
        "fill_hover": "#4A3BCC",
        "accent_soft": _rgba(139, 123, 255, 0.16),
        "accent_soft_strong": _rgba(139, 123, 255, 0.28),
        "input_bg": _rgba(255, 255, 255, 0.07),
        "solid_bg": "#14152A",
        "solid_card": "#1C1D35",
        "selection": _rgba(139, 123, 255, 0.24),
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
