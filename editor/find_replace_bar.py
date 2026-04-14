# codeeditor/editor/find_replace_bar.py
# Inline find/replace bar, docked above a CodeEditor.

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from codeeditor.editor.code_editor import CodeEditor


class FindReplaceBar(QWidget):
    """Inline find/replace bar that sits above a CodeEditor."""

    closed = Signal()
    no_results_found = Signal()

    def __init__(self, editor: CodeEditor, parent=None):
        super().__init__(parent)
        self.setObjectName("find_replace_bar")
        self._editor = editor
        self._matches: list[tuple[int, int]] = []  # (start, length)
        self._current_match_idx: int = -1

        self._build_ui()
        self.setVisible(False)

    # ==================================================================
    # UI
    # ==================================================================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # ── Find row ──────────────────────────────────────
        find_row = QHBoxLayout()
        find_row.setSpacing(4)

        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Find...")
        self._find_input.textChanged.connect(self._do_search)
        self._find_input.returnPressed.connect(self.find_next)
        find_row.addWidget(self._find_input, stretch=1)

        self._prev_btn = QPushButton("\u25b2")  # ▲
        self._prev_btn.setToolTip("Previous match (Shift+Enter)")
        self._prev_btn.setFixedWidth(28)
        self._prev_btn.clicked.connect(self.find_prev)
        find_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("\u25bc")  # ▼
        self._next_btn.setToolTip("Next match (Enter)")
        self._next_btn.setFixedWidth(28)
        self._next_btn.clicked.connect(self.find_next)
        find_row.addWidget(self._next_btn)

        self._count_label = QLabel("")
        self._count_label.setFixedWidth(60)
        find_row.addWidget(self._count_label)

        # Option toggles
        self._case_btn = QPushButton("Aa")
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.setCheckable(True)
        self._case_btn.setFixedWidth(28)
        self._case_btn.toggled.connect(lambda: self._do_search())
        find_row.addWidget(self._case_btn)

        self._regex_btn = QPushButton(".*")
        self._regex_btn.setToolTip("Regular expression")
        self._regex_btn.setCheckable(True)
        self._regex_btn.setFixedWidth(28)
        self._regex_btn.toggled.connect(lambda: self._do_search())
        find_row.addWidget(self._regex_btn)

        self._word_btn = QPushButton("W")
        self._word_btn.setToolTip("Whole word")
        self._word_btn.setCheckable(True)
        self._word_btn.setFixedWidth(28)
        self._word_btn.toggled.connect(lambda: self._do_search())
        find_row.addWidget(self._word_btn)

        self._close_btn = QPushButton("\u00d7")  # ×
        self._close_btn.setFixedWidth(24)
        self._close_btn.clicked.connect(self.dismiss)
        find_row.addWidget(self._close_btn)

        layout.addLayout(find_row)

        # ── Replace row (hidden by default) ───────────────
        self._replace_row = QWidget()
        replace_layout = QHBoxLayout(self._replace_row)
        replace_layout.setContentsMargins(0, 0, 0, 0)
        replace_layout.setSpacing(4)

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace with...")
        replace_layout.addWidget(self._replace_input, stretch=1)

        self._replace_btn = QPushButton("Replace")
        self._replace_btn.clicked.connect(self.replace_current)
        replace_layout.addWidget(self._replace_btn)

        self._replace_all_btn = QPushButton("Replace All")
        self._replace_all_btn.clicked.connect(self.replace_all)
        replace_layout.addWidget(self._replace_all_btn)

        self._replace_row.setVisible(False)
        layout.addWidget(self._replace_row)

    # ==================================================================
    # Public API
    # ==================================================================

    def show_find(self) -> None:
        """Open in find-only mode."""
        self._replace_row.setVisible(False)
        self.setVisible(True)
        self._find_input.setFocus()
        self._find_input.selectAll()
        self._do_search()

    def show_find_replace(self) -> None:
        """Open in find+replace mode."""
        self._replace_row.setVisible(True)
        self.setVisible(True)
        self._find_input.setFocus()
        self._find_input.selectAll()
        self._do_search()

    def dismiss(self) -> None:
        """Close the bar and clear highlights."""
        self.setVisible(False)
        self._editor.clear_search_selections()
        self._matches.clear()
        self._current_match_idx = -1
        self._count_label.setText("")
        self.closed.emit()

    def find_next(self) -> None:
        if not self._matches:
            return
        self._current_match_idx = (self._current_match_idx + 1) % len(self._matches)
        self._go_to_match()

    def find_prev(self) -> None:
        if not self._matches:
            return
        self._current_match_idx = (self._current_match_idx - 1) % len(self._matches)
        self._go_to_match()

    def replace_current(self) -> None:
        if not self._matches or self._current_match_idx < 0:
            return
        start, length = self._matches[self._current_match_idx]
        cursor = self._editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(self._replace_input.text())
        self._do_search()

    def replace_all(self) -> None:
        if not self._matches:
            return
        replacement = self._replace_input.text()
        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        # Replace from end to start so positions stay valid
        for start, length in reversed(self._matches):
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(replacement)
        cursor.endEditBlock()
        self._do_search()

    # ==================================================================
    # Key handling
    # ==================================================================

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            return
        super().keyPressEvent(event)

    # ==================================================================
    # Search logic
    # ==================================================================

    def _do_search(self) -> None:
        """Run the search and update highlights + count."""
        query = self._find_input.text()
        self._matches.clear()
        self._current_match_idx = -1

        if not query:
            self._editor.clear_search_selections()
            self._count_label.setText("")
            self._find_input.setStyleSheet("")
            return

        text = self._editor.toPlainText()
        case_sensitive = self._case_btn.isChecked()
        use_regex = self._regex_btn.isChecked()
        whole_word = self._word_btn.isChecked()

        try:
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = re.compile(query, flags)
            else:
                escaped = re.escape(query)
                if whole_word:
                    escaped = rf"\b{escaped}\b"
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = re.compile(escaped, flags)
            self._find_input.setStyleSheet("")
        except re.error:
            # Invalid regex — show red border
            self._find_input.setStyleSheet("border: 2px solid #CC4444;")
            self._editor.clear_search_selections()
            self._count_label.setText("!")
            return

        for match in pattern.finditer(text):
            self._matches.append((match.start(), match.end() - match.start()))

        self._count_label.setText(f"{len(self._matches)}")

        if self._matches:
            self._current_match_idx = 0
            self._highlight_matches()
            self._go_to_match()
        else:
            self._editor.clear_search_selections()
            if self._find_input.text().strip():
                self.no_results_found.emit()

    def _highlight_matches(self) -> None:
        """Create extra selections for all matches."""
        selections: list[QTextEdit.ExtraSelection] = []
        doc = self._editor.document()

        for i, (start, length) in enumerate(self._matches):
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            if i == self._current_match_idx:
                fmt.setBackground(QColor("#FF8C00"))
            else:
                fmt.setBackground(QColor("#FFD700"))
                fmt.setForeground(QColor("#000000"))
            sel.format = fmt
            cursor = QTextCursor(doc)
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cursor
            selections.append(sel)

        self._editor.set_search_selections(selections)

    def _go_to_match(self) -> None:
        """Navigate editor to the current match."""
        if self._current_match_idx < 0 or not self._matches:
            return
        start, length = self._matches[self._current_match_idx]
        cursor = self._editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        self._editor.setTextCursor(cursor)
        self._editor.centerCursor()
        self._highlight_matches()
        self._count_label.setText(
            f"{self._current_match_idx + 1}/{len(self._matches)}"
        )
