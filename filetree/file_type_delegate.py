# codeeditor/filetree/file_type_delegate.py
# Custom delegate that draws colored file-type indicator dots in the tree.

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFileSystemModel, QStyle, QStyleOptionViewItem, QStyledItemDelegate

# Extension → (color_hex, label)
FILE_TYPE_MAP: dict[str, tuple[str, str]] = {
    ".py":   ("#3572A5", "PY"),
    ".pyw":  ("#3572A5", "PY"),
    ".pyi":  ("#3572A5", "PY"),
    ".js":   ("#F7DF1E", "JS"),
    ".jsx":  ("#61DAFB", "JX"),
    ".ts":   ("#3178C6", "TS"),
    ".tsx":  ("#3178C6", "TX"),
    ".mjs":  ("#F7DF1E", "JS"),
    ".cjs":  ("#F7DF1E", "JS"),
    ".json": ("#A0A0A0", "{}"),
    ".md":   ("#083FA1", "MD"),
    ".html": ("#E34F26", "HT"),
    ".css":  ("#1572B6", "CS"),
    ".yaml": ("#CB171E", "YM"),
    ".yml":  ("#CB171E", "YM"),
    ".toml": ("#9C4121", "TM"),
    ".txt":  ("#888888", "TX"),
}

DOT_SIZE = 8
DOT_MARGIN = 4


class FileTypeDelegate(QStyledItemDelegate):
    """Draws a colored dot indicator before the filename for known file types."""

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Only modify column 0 (filename column)
        model = index.model()
        if not isinstance(model, QFileSystemModel):
            super().paint(painter, option, index)
            return

        file_path = model.filePath(index)
        if model.isDir(index):
            super().paint(painter, option, index)
            return

        ext = Path(file_path).suffix.lower()
        type_info = FILE_TYPE_MAP.get(ext)

        if type_info is None:
            super().paint(painter, option, index)
            return

        color_hex, _label = type_info

        # Draw selection/hover background first
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        # Draw colored dot
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dot_y = option.rect.center().y() - DOT_SIZE // 2
        dot_x = option.rect.left() + DOT_MARGIN
        painter.setBrush(QColor(color_hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot_x, dot_y, DOT_SIZE, DOT_SIZE)
        painter.restore()

        # Draw text shifted right to make room for the dot
        text_rect = QRect(option.rect)
        text_rect.setLeft(dot_x + DOT_SIZE + DOT_MARGIN)
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            index.data(),
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        size = super().sizeHint(option, index)
        # Add space for the dot
        size.setWidth(size.width() + DOT_SIZE + DOT_MARGIN * 2)
        return size
