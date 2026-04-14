# codeeditor/editor/minimap.py
# Narrow document minimap that sits beside the work editor.

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from codeeditor.config import DEFAULT_MINIMAP_WIDTH, MINIMAP_RENDER_DEBOUNCE_MS
from codeeditor.editor.code_editor import CodeEditor


class Minimap(QWidget):
    """Narrow scrollable minimap that renders a compressed overview of the editor."""

    def __init__(self, editor: CodeEditor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setFixedWidth(DEFAULT_MINIMAP_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._cache: QPixmap | None = None
        self._dragging = False

        # Debounced re-render
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(MINIMAP_RENDER_DEBOUNCE_MS)
        self._render_timer.timeout.connect(self._invalidate_cache)

        # Connect to editor changes
        self._editor.document().contentsChanged.connect(self._render_timer.start)
        self._editor.verticalScrollBar().valueChanged.connect(self.update)

    # ── Rendering ─────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        # Background
        win_color = QApplication.instance().palette().color(QPalette.ColorRole.Window)
        is_dark = win_color.lightness() <= 128
        bg = QColor("#1E1E1E") if is_dark else QColor("#F5F5F5")
        painter.fillRect(0, 0, w, h, bg)

        doc = self._editor.document()
        total_lines = doc.blockCount()
        if total_lines == 0:
            return

        # Render document lines as colored bars
        if self._cache is None or self._cache.height() != h or self._cache.width() != w:
            self._render_cache(w, h, total_lines, is_dark)

        if self._cache is not None:
            painter.drawPixmap(0, 0, self._cache)

        # Draw viewport rectangle
        self._draw_viewport_rect(painter, h, total_lines, is_dark)

    def _render_cache(self, w: int, h: int, total_lines: int, is_dark: bool) -> None:
        """Render the document overview into a cached QPixmap."""
        self._cache = QPixmap(w, h)
        bg = QColor("#1E1E1E") if is_dark else QColor("#F5F5F5")
        self._cache.fill(bg)

        cache_painter = QPainter(self._cache)
        text_color = QColor("#D4D4D4") if is_dark else QColor("#1E1E1E")
        text_color.setAlpha(80)

        # Pixels per line
        line_height = max(1, h / max(total_lines, 1))
        max_chars = 120  # assume ~120 char max line width

        block = self._editor.document().begin()
        y = 0.0
        while block.isValid() and y < h:
            text = block.text()
            line_len = min(len(text), max_chars)
            bar_width = max(1, int((line_len / max_chars) * (w - 4)))

            if line_len > 0:
                cache_painter.fillRect(
                    2, int(y), bar_width, max(1, int(line_height)),
                    text_color,
                )

            y += line_height
            block = block.next()

        cache_painter.end()

    def _draw_viewport_rect(
        self, painter: QPainter, h: int, total_lines: int, is_dark: bool
    ) -> None:
        """Draw a semi-transparent rectangle showing the visible region."""
        scrollbar = self._editor.verticalScrollBar()
        first_visible = scrollbar.value()
        visible_lines = self._editor.viewport().height() / self._editor.fontMetrics().lineSpacing()

        line_height = h / max(total_lines, 1)
        rect_y = int(first_visible * line_height)
        rect_h = max(10, int(visible_lines * line_height))

        overlay = QColor("#FFFFFF" if is_dark else "#000000")
        overlay.setAlpha(30)
        painter.fillRect(0, rect_y, self.width(), rect_h, overlay)

        # Border
        border = QColor("#FFFFFF" if is_dark else "#000000")
        border.setAlpha(60)
        painter.setPen(border)
        painter.drawRect(0, rect_y, self.width() - 1, rect_h)

    def _invalidate_cache(self) -> None:
        self._cache = None
        self.update()

    # ── Navigation ────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._dragging = True
        self._scroll_to_y(event.position().y())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._scroll_to_y(event.position().y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def _scroll_to_y(self, y: float) -> None:
        """Compute proportional document position and scroll the editor."""
        h = self.height()
        if h <= 0:
            return
        ratio = y / h
        total_lines = self._editor.document().blockCount()
        target_line = int(ratio * total_lines)
        scrollbar = self._editor.verticalScrollBar()
        scrollbar.setValue(target_line)
