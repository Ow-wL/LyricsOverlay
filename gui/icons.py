"""Windows 아이콘 글꼴(Segoe Fluent Icons / MDL2) 글리프.

이모지 대신 선 아이콘을 써서 화면 톤을 통일합니다.
Windows 11은 Segoe Fluent Icons, Windows 10은 Segoe MDL2 Assets가 같은 코드로 그려집니다.
"""

from PySide6.QtGui import QFont  # type: ignore

ICON_FAMILIES = ["Segoe Fluent Icons", "Segoe MDL2 Assets"]
ICON_FONT_CSS = "'Segoe Fluent Icons', 'Segoe MDL2 Assets'"

HOME = ""
PLAYLIST = ""
CHART = ""
SETTINGS = ""
INFO = ""
SUN = ""
MOON = ""

PREV = ""
NEXT = ""
PLAY = ""
PAUSE = ""
PLAY_PAUSE = PLAY + PAUSE

MUSIC_NOTE = ""
MUSIC = ""
CLOCK = ""
LINES = ""
LIST = ""
PALETTE = ""
SLIDERS = ""
KEYBOARD = ""
SYSTEM = ""
FOLDER = ""
IMPORT = ""
EXPORT = ""
FONT = ""
SAVE = ""
MONITOR = ""
DOWNLOAD = ""
OPEN_LINK = ""
HISTORY = ""


def icon_font(pixel_size: int = 16) -> QFont:
    font = QFont()
    font.setFamilies(ICON_FAMILIES)
    font.setPixelSize(pixel_size)
    return font
