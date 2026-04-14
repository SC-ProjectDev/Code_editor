# codeeditor/ai/file_attachment.py
# File picker with removable chip display for AI context attachments.

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)

from codeeditor.config import MAX_ATTACHMENT_SIZE_BYTES


class AttachmentChip(QWidget):
    """Small removable chip showing a filename."""

    removed = Signal(str)  # emits the filepath string

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setProperty("class", "attachment-chip")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        name_label = QLabel(Path(filepath).name)
        name_label.setStyleSheet("border: none; padding: 0;")
        layout.addWidget(name_label)

        remove_btn = QPushButton("\u00d7")  # × symbol
        remove_btn.setFixedSize(16, 16)
        remove_btn.setStyleSheet(
            "border: none; padding: 0; font-weight: bold; font-size: 12px;"
        )
        remove_btn.clicked.connect(lambda: self.removed.emit(self.filepath))
        layout.addWidget(remove_btn)


class FileAttachmentBar(QWidget):
    """Horizontal bar with attachment chips and an Attach button."""

    attachments_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: dict[str, dict] = {}  # filepath -> {filename, content, mime_type}

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(4)

        # Scrollable chip area
        self._chip_area = QWidget()
        self._chip_layout = QHBoxLayout(self._chip_area)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(4)
        self._chip_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._chip_area)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(32)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        main_layout.addWidget(scroll, stretch=1)

        # Attach button
        self._attach_btn = QPushButton("Attach")
        self._attach_btn.setToolTip("Attach a file to send with your prompt")
        self._attach_btn.clicked.connect(self.attach_file)
        main_layout.addWidget(self._attach_btn, stretch=0)

    def attach_file(self) -> None:
        """Open a file dialog and add the selected file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach File", "", "All files (*)"
        )
        if not path or path in self._attachments:
            return

        file_path = Path(path)
        if file_path.stat().st_size > MAX_ATTACHMENT_SIZE_BYTES:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "File too large",
                f"Max attachment size is {MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)} MB.",
            )
            return

        data = self._read_file(file_path)
        self._attachments[path] = data

        chip = AttachmentChip(path, parent=self._chip_area)
        chip.removed.connect(self._remove_attachment)
        # Insert before the stretch
        self._chip_layout.insertWidget(self._chip_layout.count() - 1, chip)

        self.attachments_changed.emit()

    def get_attachments(self) -> list[dict]:
        """Return list of {filename, content, mime_type} dicts."""
        return list(self._attachments.values())

    def get_filenames(self) -> list[str]:
        """Return list of attached filenames (for session logging)."""
        return [d["filename"] for d in self._attachments.values()]

    def clear(self) -> None:
        """Remove all chips and attachments."""
        self._attachments.clear()
        while self._chip_layout.count() > 1:  # keep the stretch
            item = self._chip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.attachments_changed.emit()

    def _remove_attachment(self, filepath: str) -> None:
        self._attachments.pop(filepath, None)
        for i in range(self._chip_layout.count()):
            item = self._chip_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, AttachmentChip) and widget.filepath == filepath:
                self._chip_layout.takeAt(i)
                widget.deleteLater()
                break
        self.attachments_changed.emit()

    @staticmethod
    def _read_file(file_path: Path) -> dict:
        """Read a file — text as UTF-8 string, binary as base64."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            raw = file_path.read_bytes()
            content = base64.b64encode(raw).decode("ascii")
            mime_type = mime_type or "application/octet-stream"

        return {
            "filename": file_path.name,
            "content": content,
            "mime_type": mime_type,
        }
