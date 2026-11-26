"""앱 글꼴과 글자 크기를 한곳에서 정합니다.

- 앱 글꼴은 설정 → 시스템에서 고를 수 있습니다 (가사 오버레이 글꼴과는 따로).
- SIZE_BOOST만큼 앱 전체 글자를 키웁니다. 스타일시트의 'font-size: Npx'와
  직접 그리는 위젯(px())이 모두 이 값을 따릅니다.
"""

import os
import re

from PySide6.QtGui import QFont, QFontDatabase  # type: ignore

SIZE_BOOST = 1

# 굵기 파일이 Regular·Bold·ExtraBold뿐인 글꼴은 600(SemiBold)을 Bold로 올려야 제목이 얇아지지 않습니다.
_NO_SEMIBOLD = {"NanumSquare Neo TTF"}

# (설정에 저장하는 값, 화면에 보이는 이름, Qt 글꼴 이름)
UI_FONTS = [
    ("pretendard", "Pretendard", "Pretendard"),
    ("nanum_square_neo", "나눔스퀘어 네오", "NanumSquare Neo TTF"),
    ("wanted_sans", "Wanted Sans", "Wanted Sans"),
]
DEFAULT_KEY = "pretendard"

_family = "Pretendard"
_loaded = False


def load_fonts(font_dir: str) -> None:
    """asset/Font 아래 글꼴 파일(.ttf/.otf, 하위 폴더 포함)을 앱에 등록합니다."""
    global _loaded
    if _loaded or not os.path.isdir(font_dir):
        return
    for root, _dirs, files in os.walk(font_dir):
        for name in sorted(files):
            if name.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(root, name))
    _loaded = True


def font_key_valid(key) -> bool:
    return any(k == key for k, _, _ in UI_FONTS)


def set_font_key(key: str) -> None:
    global _family
    for k, _label, family in UI_FONTS:
        if k == key:
            _family = family
            return
    _family = UI_FONTS[0][2]


def family() -> str:
    return _family


def px(size: int) -> int:
    return size + SIZE_BOOST


def font(size: int, weight=QFont.Normal) -> QFont:
    """직접 그리는 위젯용 글꼴 (앱 글꼴 + 키운 크기)."""
    f = QFont(_family)
    f.setPixelSize(px(size))
    if _family in _NO_SEMIBOLD and QFont.Medium < weight < QFont.Bold:
        weight = QFont.Bold
    f.setWeight(weight)
    return f


def app_font() -> QFont:
    f = QFont(_family)
    f.setPixelSize(px(14))
    f.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality | QFont.NoSubpixelAntialias)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


_FS = re.compile(r"font-size:\s*(\d+)px")
_SEMIBOLD = re.compile(r"font-weight:\s*600\b")


def css(style: str) -> str:
    """스타일시트 문자열의 글자 크기를 SIZE_BOOST만큼 키우고 앱 글꼴 이름을 넣습니다."""
    if not style:
        return style
    style = _FS.sub(lambda m: f"font-size: {int(m.group(1)) + SIZE_BOOST}px", style)
    if _family in _NO_SEMIBOLD:
        style = _SEMIBOLD.sub("font-weight: 700", style)
    return style.replace("'Pretendard'", f"'{_family}'")


def apply_css(widget, style: str) -> None:
    """위젯에 개별 스타일을 입히고 원본을 기억해 둡니다 (앱 글꼴을 바꾸면 refresh로 다시 계산)."""
    widget.setProperty("_raw_css", style)
    widget.setStyleSheet(css(style))


def refresh(root) -> None:
    """root 아래에서 apply_css로 스타일을 받은 위젯을 지금 글꼴 설정으로 다시 계산합니다."""
    from PySide6.QtWidgets import QWidget  # type: ignore

    for w in [root, *root.findChildren(QWidget)]:
        raw = w.property("_raw_css")
        if raw:
            w.setStyleSheet(css(raw))
