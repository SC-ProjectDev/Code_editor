# codeeditor/themes.py
# Complete QSS-based theme system — independent of OS theme.
# Each theme defines palette colors + a full stylesheet.

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class Theme:
    LIGHT = "light"
    DARK = "dark"


# ---------------------------------------------------------------------------
# Color palettes (used both for QPalette and QSS variable substitution)
# ---------------------------------------------------------------------------
PALETTES = {
    Theme.LIGHT: {
        "window":           "#F5F5F5",
        "window_text":      "#1E1E1E",
        "base":             "#FFFFFF",
        "alternate_base":   "#EBF0F4",
        "text":             "#1E1E1E",
        "button":           "#E0E0E0",
        "button_text":      "#1E1E1E",
        "highlight":        "#4A90D9",
        "highlight_text":   "#FFFFFF",
        "tooltip_bg":       "#FFFFDC",
        "tooltip_text":     "#1E1E1E",
        "placeholder":      "#888888",
        "border":           "#C0C0C0",
        "border_light":     "#D8D8D8",
        "toolbar_bg":       "#EAEAEA",
        "toolbar_border":   "#D0D0D0",
        "statusbar_bg":     "#EAEAEA",
        "splitter":         "#C8C8C8",
        "tree_hover":       "#E3EDFA",
        "scrollbar_bg":     "#F0F0F0",
        "scrollbar_handle": "#C0C0C0",
        "tab_active":       "#FFFFFF",
        "tab_inactive":     "#E0E0E0",
        "gutter_bg":        "#F0F0F0",
        "gutter_text":      "#999999",
        "line_highlight":   "#FFF9E0",
        "selection_bg":     "#ADD6FF",
        "find_match_bg":    "#FFEB3B66",
        "find_current_bg":  "#FF980077",
        "bracket_match_bg": "#D0D0D0",
        "bracket_border":   "#B8860B",
    },
    Theme.DARK: {
        "window":           "#1E1E1E",
        "window_text":      "#D4D4D4",
        "base":             "#181818",
        "alternate_base":   "#2A2A2A",
        "text":             "#D4D4D4",
        "button":           "#333333",
        "button_text":      "#D4D4D4",
        "highlight":        "#264F78",
        "highlight_text":   "#FFFFFF",
        "tooltip_bg":       "#2D2D2D",
        "tooltip_text":     "#D4D4D4",
        "placeholder":      "#6E6E6E",
        "border":           "#3E3E3E",
        "border_light":     "#2E2E2E",
        "toolbar_bg":       "#252526",
        "toolbar_border":   "#1A1A1A",
        "statusbar_bg":     "#007ACC",
        "splitter":         "#3E3E3E",
        "tree_hover":       "#2A2D2E",
        "scrollbar_bg":     "#1E1E1E",
        "scrollbar_handle": "#424242",
        "tab_active":       "#1E1E1E",
        "tab_inactive":     "#2D2D2D",
        "gutter_bg":        "#1E1E1E",
        "gutter_text":      "#5A5A5A",
        "line_highlight":   "#2A2D2E",
        "selection_bg":     "#264F78",
        "find_match_bg":    "#FFD70044",
        "find_current_bg":  "#FF8C0077",
        "bracket_match_bg": "#3A3D41",
        "bracket_border":   "#FFD700",
    },
}


def _build_stylesheet(colors: dict) -> str:
    """Build a full QSS stylesheet from a color dictionary."""
    c = colors
    return f"""
    /* ── Global ────────────────────────────────────────── */
    QMainWindow {{
        background-color: {c['window']};
    }}

    /* ── Toolbar ───────────────────────────────────────── */
    QToolBar {{
        background-color: {c['toolbar_bg']};
        border-bottom: 1px solid {c['toolbar_border']};
        spacing: 4px;
        padding: 3px 6px;
    }}
    QToolBar QToolButton {{
        background-color: transparent;
        color: {c['window_text']};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    QToolBar QToolButton:hover {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
        border: 1px solid {c['highlight']};
    }}
    QToolBar QToolButton:checked {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
    }}

    /* ── Status Bar ────────────────────────────────────── */
    QStatusBar {{
        background-color: {c['statusbar_bg']};
        color: {c['highlight_text'] if c is PALETTES[Theme.DARK] else c['window_text']};
        font-size: 12px;
        padding: 2px 8px;
    }}
    QStatusBar QLabel {{
        color: {c['highlight_text'] if c is PALETTES[Theme.DARK] else c['window_text']};
    }}

    /* ── Splitters ─────────────────────────────────────── */
    QSplitter::handle {{
        background-color: {c['splitter']};
    }}
    QSplitter::handle:horizontal {{
        width: 3px;
    }}
    QSplitter::handle:vertical {{
        height: 3px;
    }}

    /* ── Tree View ─────────────────────────────────────── */
    QTreeView {{
        background-color: {c['base']};
        color: {c['text']};
        border: none;
        font-size: 12px;
    }}
    QTreeView::item {{
        padding: 3px 4px;
    }}
    QTreeView::item:hover {{
        background-color: {c['tree_hover']};
    }}
    QTreeView::item:selected {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
    }}
    QHeaderView::section {{
        background-color: {c['toolbar_bg']};
        color: {c['window_text']};
        border: 1px solid {c['border']};
        padding: 4px 6px;
        font-size: 11px;
    }}

    /* ── Code Editor (QPlainTextEdit) ──────────────────── */
    QPlainTextEdit {{
        background-color: {c['base']};
        color: {c['text']};
        selection-background-color: {c['selection_bg']};
        border: none;
    }}

    /* ── Scrollbars ────────────────────────────────────── */
    QScrollBar:vertical {{
        background: {c['scrollbar_bg']};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c['scrollbar_handle']};
        min-height: 30px;
        border-radius: 4px;
        margin: 2px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {c['scrollbar_bg']};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['scrollbar_handle']};
        min-width: 30px;
        border-radius: 4px;
        margin: 2px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ── Tooltips ──────────────────────────────────────── */
    QToolTip {{
        background-color: {c['tooltip_bg']};
        color: {c['tooltip_text']};
        border: 1px solid {c['border']};
        padding: 4px;
        font-size: 12px;
    }}

    /* ── GIF Player ────────────────────────────────────── */
    #gif_player {{
        background-color: {c['base']};
        border: none;
        border-top: 1px solid {c['border']};
    }}

    /* ── AI Panel ──────────────────────────────────────── */
    #ai_placeholder {{
        background-color: {c['base']};
        border: none;
    }}
    #ai_placeholder QLabel {{
        color: {c['placeholder']};
        font-size: 14px;
    }}
    #ai_placeholder QTextEdit {{
        background-color: {c['base']};
        color: {c['text']};
        border: none;
        font-size: 13px;
    }}
    #ai_placeholder QLineEdit {{
        background-color: {c['base']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 6px 8px;
        font-size: 12px;
    }}
    #ai_placeholder QComboBox {{
        background-color: {c['button']};
        color: {c['button_text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 12px;
    }}
    #ai_placeholder QComboBox::drop-down {{
        border: none;
    }}
    #ai_placeholder QComboBox QAbstractItemView {{
        background-color: {c['base']};
        color: {c['text']};
        selection-background-color: {c['highlight']};
    }}
    .attachment-chip {{
        background-color: {c['alternate_base']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 2px 8px;
        font-size: 11px;
    }}

    /* ── Find / Replace Bar ───────────────────────────── */
    #find_replace_bar {{
        background-color: {c['toolbar_bg']};
        border-bottom: 1px solid {c['border']};
        padding: 4px 6px;
    }}
    #find_replace_bar QLineEdit {{
        background-color: {c['base']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 3px 6px;
        font-size: 12px;
    }}
    #find_replace_bar QPushButton {{
        background-color: {c['button']};
        color: {c['button_text']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 3px 8px;
        font-size: 11px;
        min-width: 24px;
    }}
    #find_replace_bar QPushButton:hover {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
    }}
    #find_replace_bar QPushButton:checked {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
    }}
    #find_replace_bar QLabel {{
        color: {c['window_text']};
        font-size: 11px;
    }}

    /* ── Dialogs / Message Boxes ───────────────────────── */
    QMessageBox {{
        background-color: {c['window']};
    }}
    QMessageBox QLabel {{
        color: {c['text']};
    }}
    QPushButton {{
        background-color: {c['button']};
        color: {c['button_text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 5px 16px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
    }}
    QPushButton:pressed {{
        background-color: {c['highlight']};
    }}
    """


def _build_qpalette(colors: dict) -> QPalette:
    """Build a QPalette from a color dictionary (needed for native widgets)."""
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(colors["window_text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(colors["base"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alternate_base"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(colors["button"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(colors["button_text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(colors["highlight"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["highlight_text"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["tooltip_bg"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["tooltip_text"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["placeholder"]))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#FF0000"))
    return pal


def apply_theme(app: QApplication, theme: str):
    """Apply the given theme to the entire application."""
    colors = PALETTES.get(theme, PALETTES[Theme.LIGHT])
    app.setPalette(_build_qpalette(colors))
    app.setStyleSheet(_build_stylesheet(colors))


def get_theme_colors(theme: str) -> dict:
    """Return the color dict for a given theme (used by editor gutter, etc.)."""
    return PALETTES.get(theme, PALETTES[Theme.LIGHT])
