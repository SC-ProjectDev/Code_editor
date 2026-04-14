# codeeditor/editor/shortcut_dialog.py
# Keyboard shortcut cheat sheet dialog.

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

# (Category, Action, Shortcut)
SHORTCUTS: list[tuple[str, str, str]] = [
    ("File", "Open Folder", "Ctrl+Shift+O"),
    ("File", "New Tab", "Ctrl+N"),
    ("File", "Save", "Ctrl+S"),
    ("File", "Save As", "Ctrl+Shift+Alt+S"),
    ("File", "Snapshot", "Ctrl+Shift+S"),
    ("Editor", "Find", "Ctrl+F"),
    ("Editor", "Find & Replace", "Ctrl+H"),
    ("Editor", "Copy Preview \u2192 Work", "Ctrl+Shift+C"),
    ("Editor", "Indent Selection", "Tab"),
    ("Editor", "Dedent Selection", "Shift+Tab"),
    ("View", "Toggle Preview Pane", "Ctrl+Shift+P"),
    ("View", "Toggle AI Panel", "Ctrl+Shift+A"),
    ("View", "Toggle Word Wrap", "(toolbar)"),
    ("View", "Toggle Theme", "(toolbar)"),
    ("View", "Shortcut Cheat Sheet", "Ctrl+/"),
    ("AI", "Send Prompt", "Enter (in AI input)"),
    ("AI", "Send Code", "(Send Code button)"),
    ("AI", "Insert AI Code", "(Insert button)"),
    ("AI", "Configure API Keys", "(API Keys button)"),
]


class ShortcutCheatSheet(QDialog):
    """Themed dialog listing all keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(480, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        table = QTableWidget(len(SHORTCUTS), 3)
        table.setHorizontalHeaderLabels(["Category", "Action", "Shortcut"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        prev_category = ""
        for row, (cat, action, shortcut) in enumerate(SHORTCUTS):
            # Only show category name on first row of each group
            cat_item = QTableWidgetItem(cat if cat != prev_category else "")
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if cat != prev_category:
                font = cat_item.font()
                font.setBold(True)
                cat_item.setFont(font)
            table.setItem(row, 0, cat_item)

            action_item = QTableWidgetItem(action)
            action_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 1, action_item)

            shortcut_item = QTableWidgetItem(shortcut)
            shortcut_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = shortcut_item.font()
            font.setBold(True)
            shortcut_item.setFont(font)
            table.setItem(row, 2, shortcut_item)

            prev_category = cat

        layout.addWidget(table)
