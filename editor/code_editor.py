# codeeditor/editor/code_editor.py
# CodeEditor widget with line numbers, current-line highlight, auto-indent,
# bracket matching, and merged extra-selection support.

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QPainter,
    QPen,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QFont,
    QFontDatabase,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QPlainTextEdit,
    QWidget,
    QTextEdit,
)

from codeeditor.config import DEFAULT_FONT_SIZE, DEFAULT_TAB_WIDTH

# Bracket pairs
_OPEN_BRACKETS = {"(": ")", "[": "]", "{": "}"}
_CLOSE_BRACKETS = {")": "(", "]": "[", "}": "{"}
_ALL_BRACKETS = set(_OPEN_BRACKETS) | set(_CLOSE_BRACKETS)

# Python indent/dedent triggers
_PY_DEDENT_KEYWORDS = {"return", "break", "continue", "pass", "raise"}


class LineNumberArea(QWidget):
    """Gutter widget that renders line numbers alongside a CodeEditor."""

    def __init__(self, editor: CodeEditor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """
    Enhanced plain-text editor with:
      - Line number gutter
      - Current-line highlight
      - Bracket matching highlight
      - Smart auto-indent (Python / JavaScript)
      - Merged extra-selection support (line + brackets + search)
    """

    # Reaction signals for the GIF engine
    backspace_pressed = Signal()
    paste_performed = Signal()

    def __init__(self, parent=None, *, read_only: bool = False):
        super().__init__(parent)
        self.setReadOnly(read_only)

        # Language for auto-indent (set by MainWindow on highlighter swap)
        self._language: str = "python"

        # Extra-selection layers (merged in _apply_extra_selections)
        self._current_line_selections: list[QTextEdit.ExtraSelection] = []
        self._bracket_selections: list[QTextEdit.ExtraSelection] = []
        self._search_selections: list[QTextEdit.ExtraSelection] = []

        # Monospace font — cross-platform
        try:
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        except Exception:
            font = QFont("Courier New")
        font.setPointSize(DEFAULT_FONT_SIZE)
        self.setFont(font)

        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * DEFAULT_TAB_WIDTH
        )
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Gutter
        self._line_number_area = LineNumberArea(self)

        # Signals
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._on_cursor_moved)

        self._update_line_number_area_width(0)
        self._on_cursor_moved()

    # ── Public API ────────────────────────────────────────

    def set_language(self, lang: str) -> None:
        """Set the language for auto-indent behaviour."""
        self._language = lang

    def set_search_selections(self, selections: list[QTextEdit.ExtraSelection]) -> None:
        """Set search-highlight extra selections (called by FindReplaceBar)."""
        self._search_selections = selections
        self._apply_extra_selections()

    def clear_search_selections(self) -> None:
        self._search_selections = []
        self._apply_extra_selections()

    # ── Extra-selection merge ─────────────────────────────

    def _apply_extra_selections(self) -> None:
        """Merge all extra-selection layers and apply."""
        merged: list[QTextEdit.ExtraSelection] = []
        merged.extend(self._current_line_selections)
        merged.extend(self._bracket_selections)
        merged.extend(self._search_selections)
        self.setExtraSelections(merged)

    def _on_cursor_moved(self) -> None:
        """Combined handler for cursor position changes."""
        self.highlight_current_line()
        self._update_bracket_match()
        self._apply_extra_selections()

    # ── Line-number gutter ────────────────────────────────

    def line_number_area_width(self) -> int:
        digits = 1
        max_block = max(1, self.blockCount())
        while max_block >= 10:
            max_block //= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._line_number_area)
        bg = self.palette().alternateBase().color()
        painter.fillRect(event.rect(), bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        win_color = QApplication.instance().palette().color(QPalette.ColorRole.Window)
        if win_color.lightness() > 128:
            painter.setPen(QColor("#999999"))
        else:
            painter.setPen(QColor("#5A5A5A"))

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    # ── Current-line highlight ────────────────────────────

    def highlight_current_line(self):
        sel = QTextEdit.ExtraSelection()
        if self.isReadOnly():
            line_color = self.palette().alternateBase().color()
            line_color.setAlpha(50)
        else:
            line_color = self.palette().alternateBase().color()
            line_color.setAlpha(80)
        sel.format.setBackground(line_color)
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self._current_line_selections = [sel]

    # ── Bracket matching ──────────────────────────────────

    def _update_bracket_match(self) -> None:
        """Highlight matching bracket pair if cursor is on/adjacent to a bracket."""
        self._bracket_selections = []
        cursor = self.textCursor()
        doc = self.document()
        pos = cursor.position()

        # Check character at cursor and one before
        char_at = doc.characterAt(pos)
        char_before = doc.characterAt(pos - 1) if pos > 0 else ""

        bracket_pos = -1
        bracket_char = ""

        if char_at in _ALL_BRACKETS:
            bracket_pos = pos
            bracket_char = char_at
        elif char_before in _ALL_BRACKETS:
            bracket_pos = pos - 1
            bracket_char = char_before

        if bracket_pos < 0:
            return

        match_pos = self._find_matching_bracket(bracket_pos, bracket_char)
        if match_pos is None:
            return

        # Create highlight selections for both brackets
        for bpos in (bracket_pos, match_pos):
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#3A3D41"))  # will be overridden by theme
            # Use a gold border to make it visible in both themes
            win_color = QApplication.instance().palette().color(QPalette.ColorRole.Window)
            if win_color.lightness() > 128:
                fmt.setBackground(QColor("#D0D0D0"))
                fmt.setForeground(QColor("#000000"))
            else:
                fmt.setBackground(QColor("#3A3D41"))
                fmt.setForeground(QColor("#FFD700"))
            sel.format = fmt
            c = QTextCursor(doc)
            c.setPosition(bpos)
            c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = c
            self._bracket_selections.append(sel)

    def _find_matching_bracket(self, pos: int, char: str) -> int | None:
        """Scan forward or backward for the matching bracket, respecting nesting."""
        doc = self.document()
        total = doc.characterCount()

        if char in _OPEN_BRACKETS:
            target = _OPEN_BRACKETS[char]
            direction = 1
            start = pos + 1
            end = total
        elif char in _CLOSE_BRACKETS:
            target = _CLOSE_BRACKETS[char]
            direction = -1
            start = pos - 1
            end = -1
        else:
            return None

        depth = 1
        i = start
        while i != end:
            c = doc.characterAt(i)
            if c == char:
                depth += 1
            elif c == target:
                depth -= 1
                if depth == 0:
                    return i
            i += direction

        return None

    # ── Auto-indent ───────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.isReadOnly():
            super().keyPressEvent(event)
            return

        key = event.key()
        mods = event.modifiers()

        # Enter / Return → smart indent
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_auto_indent()
            return

        # Tab with selection → indent block
        if key == Qt.Key.Key_Tab and not (mods & Qt.KeyboardModifier.ShiftModifier):
            if self.textCursor().hasSelection():
                self._indent_selection()
                return

        # Shift+Tab → dedent block
        if key == Qt.Key.Key_Backtab or (
            key == Qt.Key.Key_Tab and (mods & Qt.KeyboardModifier.ShiftModifier)
        ):
            if self.textCursor().hasSelection():
                self._dedent_selection()
                return

        # Backspace → emit signal for GIF reactions
        if key == Qt.Key.Key_Backspace:
            self.backspace_pressed.emit()

        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        """Detect paste events and emit signal for GIF reactions."""
        super().insertFromMimeData(source)
        self.paste_performed.emit()

    def _handle_auto_indent(self) -> None:
        """Insert newline with smart indentation."""
        cursor = self.textCursor()
        block_text = cursor.block().text()
        indent = self._get_leading_whitespace(block_text)
        stripped = block_text.strip()

        action = self._detect_indent_action(stripped)

        cursor.insertText("\n")
        if action == "indent":
            cursor.insertText(indent + "    ")
        elif action == "dedent":
            # Remove one level of indent
            if indent.endswith("    "):
                cursor.insertText(indent[:-4])
            elif indent.endswith("\t"):
                cursor.insertText(indent[:-1])
            else:
                cursor.insertText(indent)
        else:
            cursor.insertText(indent)

        self.setTextCursor(cursor)

    def _detect_indent_action(self, stripped: str) -> str:
        """Return 'indent', 'dedent', or 'maintain'."""
        if not stripped:
            return "maintain"

        if self._language == "python":
            # Strip trailing comments for colon detection
            code = stripped.split("#")[0].rstrip()
            if code.endswith(":"):
                return "indent"
            first_word = stripped.split()[0] if stripped.split() else ""
            if first_word in _PY_DEDENT_KEYWORDS:
                return "dedent"

        elif self._language == "javascript":
            if stripped.endswith("{"):
                return "indent"
            if stripped == "}" or stripped.startswith("}"):
                return "dedent"

        return "maintain"

    def _indent_selection(self) -> None:
        """Indent all selected lines by one tab level."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )

        text = cursor.selectedText()
        # QTextCursor uses \u2029 as paragraph separator
        lines = text.split("\u2029")
        indented = ["    " + line for line in lines]
        cursor.insertText("\u2029".join(indented))

    def _dedent_selection(self) -> None:
        """Dedent all selected lines by one tab level."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )

        text = cursor.selectedText()
        lines = text.split("\u2029")
        dedented = []
        for line in lines:
            if line.startswith("    "):
                dedented.append(line[4:])
            elif line.startswith("\t"):
                dedented.append(line[1:])
            else:
                dedented.append(line)
        cursor.insertText("\u2029".join(dedented))

    @staticmethod
    def _get_leading_whitespace(text: str) -> str:
        """Return the leading whitespace from a text line."""
        return text[: len(text) - len(text.lstrip())]
