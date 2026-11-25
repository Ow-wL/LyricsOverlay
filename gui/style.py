"""테마 토큰으로 앱 전체 스타일시트(QSS)를 만듭니다.

위젯은 색을 직접 지정하지 않고 objectName만 붙입니다:
  Card, Sidebar, PageHeader, PageSubtitle, SectionLabel, CardTitle, Secondary, Tertiary,
  StatValue, Divider, SegmentGroup/Segment, PrimaryButton, LinkButton, ColorSwatch,
  HotkeyEdit, MutedCard, LogList, IconGlyph
"""

from gui.icons import ICON_FONT_CSS
from gui.theme import UIConfig


def build_stylesheet(t: dict) -> str:
    accent_grad = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t['accent']}, stop:1 {t['accent_2']})"
    )
    glass_grad = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t['glass_strong']}, stop:1 {t['glass']})"
    )
    r = UIConfig.RADIUS_CARD
    rc = UIConfig.RADIUS_CONTROL
    return f"""
    QWidget {{
        color: {t['text_primary']};
        font-family: 'Pretendard';
    }}
    QDialog, QMessageBox, QInputDialog, QFontDialog, QColorDialog, QFileDialog {{
        background-color: {t['solid_bg']};
    }}
    QToolTip {{
        background-color: {t['solid_card']};
        color: {t['text_primary']};
        border: 1px solid {t['hairline']};
        border-radius: 6px;
        padding: 6px 8px;
    }}

    /* ---------- 유리 패널 ---------- */
    QFrame#Card, QFrame#Sidebar {{
        background: {glass_grad};
        border: 1px solid {t['glass_border']};
        border-radius: {r}px;
    }}
    QFrame#Sidebar {{ border-radius: 22px; }}
    QFrame#MutedCard {{
        background: transparent;
        border: 1px dashed {t['track']};
        border-radius: {r}px;
    }}
    QFrame#Divider {{
        background-color: {t['hairline']};
        border: none;
        min-height: 1px; max-height: 1px;
    }}
    QFrame#VDivider {{
        background-color: {t['hairline']};
        border: none;
        min-width: 1px; max-width: 1px;
    }}

    /* ---------- 글자 ---------- */
    QLabel {{ background: transparent; }}
    QLabel#PageHeader {{
        font-size: {UIConfig.FS_HEADER_MAIN};
        font-weight: 800;
        letter-spacing: -0.8px;
    }}
    QLabel#PageSubtitle {{ color: {t['text_secondary']}; font-size: 14px; }}
    QLabel#SectionLabel {{
        color: {t['text_tertiary']};
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.6px;
    }}
    QLabel#CardTitle {{ font-size: {UIConfig.FS_TITLE_S}; font-weight: 700; }}
    QLabel#Secondary {{ color: {t['text_secondary']}; }}
    QLabel#Tertiary, QLabel#StatSub {{ color: {t['text_tertiary']}; }}
    QLabel#StatValue {{ font-size: 34px; font-weight: 800; letter-spacing: -0.8px; }}
    QLabel#StatusTitle {{ font-size: 13px; font-weight: 700; color: {t['text_secondary']}; }}
    QLabel#StatusTitle[level="ok"] {{ color: {t['status_ok']}; }}
    QLabel#StatusTitle[level="warn"] {{ color: {t['status_warn']}; }}
    QLabel#StatusTitle[level="error"] {{ color: {t['status_error']}; }}
    QLabel#AccentValue {{ color: {t['accent']}; font-weight: 800; }}
    QLabel#BrandName {{ font-size: 17px; font-weight: 800; letter-spacing: -0.3px; }}
    QLabel#IconGlyph {{ font-family: {ICON_FONT_CSS}; color: {t['accent']}; }}
    QLabel#IconChip {{
        font-family: {ICON_FONT_CSS};
        font-size: 16px;
        color: {t['accent']};
        background-color: {t['accent_soft']};
        border-radius: 12px;
    }}

    /* ---------- 버튼 ---------- */
    QPushButton {{
        background-color: {t['glass_strong']};
        color: {t['text_primary']};
        border: 1px solid {t['glass_border']};
        border-radius: {rc}px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: {UIConfig.FS_BUTTON};
    }}
    QPushButton:hover {{ background-color: {t['glass_hover']}; border-color: {t['accent_soft_strong']}; }}
    QPushButton:pressed {{ background-color: {t['glass_pressed']}; }}
    QPushButton:disabled {{ color: {t['text_tertiary']}; background-color: transparent; border: 1px dashed {t['track']}; }}
    QPushButton#PrimaryButton {{
        background: {accent_grad};
        color: {t['text_on_accent']};
        border: none;
    }}
    QPushButton#PrimaryButton:hover {{ background: {t['accent_hover']}; }}
    QPushButton#LinkButton {{
        background: transparent;
        border: none;
        color: {t['accent']};
        padding: 4px 6px;
        font-size: 12px;
    }}
    QPushButton#LinkButton:hover {{ text-decoration: underline; }}
    QPushButton#ColorSwatch {{
        border: 3px solid {t['glass_strong']};
        border-radius: 16px;
        padding: 0px;
    }}
    QPushButton#ColorSwatch:hover {{ border: 3px solid {t['accent_soft_strong']}; }}

    /* 세그먼트 컨트롤 (세션/오늘/이번 주…) */
    QFrame#SegmentGroup {{
        background-color: {t['glass']};
        border: 1px solid {t['glass_border']};
        border-radius: 12px;
    }}
    QPushButton#Segment {{
        background: transparent;
        border: none;
        border-radius: 9px;
        color: {t['text_secondary']};
        padding: 6px 14px;
        font-weight: 600;
    }}
    QPushButton#Segment:hover {{ color: {t['text_primary']}; }}
    QPushButton#Segment:checked {{
        background-color: {t['solid_card']};
        color: {t['accent']};
    }}

    /* 미디어 버튼 */
    QPushButton#MediaButton {{
        font-family: {ICON_FONT_CSS};
        font-size: 14px;
        border-radius: 20px;
        padding: 0px;
    }}
    QPushButton#MediaButtonMain {{
        font-family: {ICON_FONT_CSS};
        font-size: 14px;
        border-radius: 24px;
        padding: 0px;
        border: none;
        background: {accent_grad};
        color: {t['text_on_accent']};
    }}
    QPushButton#MediaButtonMain:hover {{ background: {t['accent_hover']}; }}

    /* ---------- 입력 ---------- */
    QLineEdit, QSpinBox, QComboBox {{
        background-color: {t['input_bg']};
        border: 1px solid {t['hairline']};
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: {t['accent']};
        selection-color: {t['text_on_accent']};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
    QComboBox QAbstractItemView {{
        background-color: {t['solid_card']};
        border: 1px solid {t['hairline']};
        selection-background-color: {t['selection']};
        selection-color: {t['text_primary']};
    }}
    QLineEdit#HotkeyEdit {{
        background-color: {t['input_bg']};
        border: 1px solid {t['glass_border']};
        border-radius: 10px;
        padding: 8px;
        font-weight: 700;
        color: {t['text_primary']};
    }}
    QLineEdit#HotkeyEdit:focus {{
        border: 1px solid {t['accent']};
        background-color: {t['accent_soft']};
        color: {t['accent']};
    }}

    /* ---------- 목록 ---------- */
    QListWidget, QListView, QTreeView {{
        background: transparent;
        border: none;
        outline: none;
        font-size: {UIConfig.FS_LIST};
    }}
    QListWidget::item {{
        padding: 10px 12px;
        border-radius: 10px;
        margin: 1px 0px;
    }}
    QListWidget::item:hover {{ background-color: {t['glass_hover']}; }}
    QListWidget::item:selected {{
        background-color: {t['selection']};
        color: {t['text_primary']};
    }}
    QListWidget#LogList {{ font-size: 12px; color: {t['text_secondary']}; }}
    QListWidget#LogList::item {{ padding: 6px 8px; }}
    QDialog QListView, QDialog QTreeView, QFontDialog QListView {{
        background-color: {t['solid_card']};
        border: 1px solid {t['hairline']};
        border-radius: 8px;
    }}

    /* ---------- 슬라이더 ---------- */
    QSlider::horizontal {{ min-height: 24px; }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: {t['track']};
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {accent_grad};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: #FFFFFF;
        border: 2px solid {t['accent']};
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{ border: 2px solid {t['accent_hover']}; }}

    /* ---------- 스크롤 ---------- */
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t['track']}; min-height: 40px; border-radius: 3px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['text_tertiary']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {t['track']}; min-width: 40px; border-radius: 3px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; border: none; background: none; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    /* ---------- 체크박스 (토글 스위치가 아닌 곳) ---------- */
    QCheckBox {{ spacing: 10px; font-size: {UIConfig.FS_CHECKBOX}; background: transparent; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 5px;
        border: 1px solid {t['track']};
        background-color: {t['input_bg']};
    }}
    QCheckBox::indicator:checked {{ background-color: {t['accent']}; border: 1px solid {t['accent']}; }}
    """
