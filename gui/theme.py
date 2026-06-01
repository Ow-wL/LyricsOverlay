"""테마 설정: UIConfig, Theme, ThemeManager."""


class UIConfig:
    # ----- Sidebar Icons -----
    ICON_COLOR_DASHBOARD = "#F17979"
    ICON_COLOR_MUSIC = "#7EEFA4"
    ICON_COLOR_STATS = "#FFB74D"
    ICON_COLOR_SETTINGS = "#75EDF1"

    # ----- Common Styles -----
    COLOR_SECONDARY_TEXT = "#828282"
    COLOR_SHADOW = (0, 0, 0, 20)  # RGBA tuple

    # ----- Light Theme (Apple Minimalist) -----
    LIGHT_BG_MAIN = "#F5F5F7"
    LIGHT_BG_SIDEBAR = "#FFFFFF"
    LIGHT_BG_CARD = "#FFFFFF"
    LIGHT_BORDER = "#E5E5EA"
    LIGHT_TEXT_PRIMARY = "#1D1D1F"
    LIGHT_TEXT_SECONDARY = "#86868B"
    LIGHT_ACCENT = "#0066CC"
    LIGHT_ACCENT_HOVER = "#0050A1"

    LIGHT_SB_NORMAL_TEXT = "#86868B"
    LIGHT_SB_ACTIVE_BG = "#F5F5F7"
    LIGHT_SB_ACTIVE_TEXT = "#1D1D1F"
    LIGHT_SB_HOVER_BG = "#F2F2F7"
    LIGHT_BTN_BG = "#FFFFFF"
    LIGHT_BTN_TEXT = "#1D1D1F"
    LIGHT_BTN_BORDER = "#E5E5EA"

    LIGHT_LIST_SEL_BG = "#E5F1FF"
    LIGHT_LIST_SEL_TEXT = "#0066CC"

    LIGHT_FONT_BTN_BG = "#0066CC"
    LIGHT_FONT_BTN_TEXT = "#FFFFFF"

    # ----- Dark Theme (VS Code / Discord Style) -----
    DARK_BG_MAIN = "#1E1E1E"
    DARK_BG_SIDEBAR = "#252526"
    DARK_BG_CARD = "#252526"
    DARK_BORDER = "#333333"
    DARK_TEXT_PRIMARY = "#E1E1E1"
    DARK_TEXT_SECONDARY = "#969696"
    DARK_ACCENT = "#007ACC"
    DARK_ACCENT_HOVER = "#005A9E"

    DARK_SB_NORMAL_TEXT = "#969696"
    DARK_SB_ACTIVE_BG = "#37373D"
    DARK_SB_ACTIVE_TEXT = "#FFFFFF"
    DARK_SB_HOVER_BG = "#2D2D30"
    DARK_BTN_BG = "#252526"
    DARK_BTN_TEXT = "#E1E1E1"
    DARK_BTN_BORDER = "#333333"

    DARK_LIST_SEL_BG = "#04395E"
    DARK_LIST_SEL_TEXT = "#FFFFFF"

    DARK_FONT_BTN_BG = "#007ACC"
    DARK_FONT_BTN_TEXT = "#FFFFFF"

    # ----- Font Sizes -----
    FS_HEADER_MAIN = "36px"
    FS_SIDEBAR_TITLE = "26px"
    FS_TITLE_L = "22px"
    FS_TITLE_M = "20px"
    FS_TITLE_S = "18px"
    FS_DESC = "15px"
    FS_BODY = "16px"
    FS_LIST = "15px"
    FS_BUTTON = "14px"
    FS_THEME_BUTTON = "15px"
    FS_SIDEBAR_BTN = "17px"
    FS_CHECKBOX = "15px"


class Theme:
    LIGHT = {
        "bg_main": UIConfig.LIGHT_BG_MAIN,
        "bg_sidebar": UIConfig.LIGHT_BG_SIDEBAR,
        "bg_card": UIConfig.LIGHT_BG_CARD,
        "border": UIConfig.LIGHT_BORDER,
        "text_primary": UIConfig.LIGHT_TEXT_PRIMARY,
        "text_secondary": UIConfig.LIGHT_TEXT_SECONDARY,
        "accent": UIConfig.LIGHT_ACCENT,
        "accent_hover": UIConfig.LIGHT_ACCENT_HOVER,
        "sb_normal_text": UIConfig.LIGHT_SB_NORMAL_TEXT,
        "sb_active_bg": UIConfig.LIGHT_SB_ACTIVE_BG,
        "sb_active_text": UIConfig.LIGHT_SB_ACTIVE_TEXT,
        "sb_hover_bg": UIConfig.LIGHT_SB_HOVER_BG,
        "btn_bg": UIConfig.LIGHT_BTN_BG,
        "btn_text": UIConfig.LIGHT_BTN_TEXT,
        "btn_border": UIConfig.LIGHT_BTN_BORDER,
        "btn_font_bg": UIConfig.LIGHT_FONT_BTN_BG,
        "btn_font_text": UIConfig.LIGHT_FONT_BTN_TEXT,
        "list_sel_bg": UIConfig.LIGHT_LIST_SEL_BG,
        "list_sel_text": UIConfig.LIGHT_LIST_SEL_TEXT,
    }
    DARK = {
        "bg_main": UIConfig.DARK_BG_MAIN,
        "bg_sidebar": UIConfig.DARK_BG_SIDEBAR,
        "bg_card": UIConfig.DARK_BG_CARD,
        "border": UIConfig.DARK_BORDER,
        "text_primary": UIConfig.DARK_TEXT_PRIMARY,
        "text_secondary": UIConfig.DARK_TEXT_SECONDARY,
        "accent": UIConfig.DARK_ACCENT,
        "accent_hover": UIConfig.DARK_ACCENT_HOVER,
        "sb_normal_text": UIConfig.DARK_SB_NORMAL_TEXT,
        "sb_active_bg": UIConfig.DARK_SB_ACTIVE_BG,
        "sb_active_text": UIConfig.DARK_SB_ACTIVE_TEXT,
        "sb_hover_bg": UIConfig.DARK_SB_HOVER_BG,
        "btn_bg": UIConfig.DARK_BTN_BG,
        "btn_text": UIConfig.DARK_BTN_TEXT,
        "btn_border": UIConfig.DARK_BTN_BORDER,
        "btn_font_bg": UIConfig.DARK_FONT_BTN_BG,
        "btn_font_text": UIConfig.DARK_FONT_BTN_TEXT,
        "list_sel_bg": UIConfig.DARK_LIST_SEL_BG,
        "list_sel_text": UIConfig.DARK_LIST_SEL_TEXT,
    }


class ThemeManager:
    def __init__(self):
        self.current_theme: dict = Theme.LIGHT

    def toggle_theme(self) -> dict:
        self.current_theme = (
            Theme.DARK if self.current_theme == Theme.LIGHT else Theme.LIGHT
        )
        return self.current_theme
