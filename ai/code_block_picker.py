# codeeditor/ai/code_block_picker.py
# Dialog for choosing which code block(s) to insert from an AI response.

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class CodeBlockPicker(QDialog):
    """Lets the user pick which code blocks to insert from an AI response."""

    def __init__(self, blocks: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Code Block")
        self.setMinimumSize(500, 350)

        self._blocks = blocks
        self._selected_code = ""

        layout = QVBoxLayout(self)

        label = QLabel(f"Found {len(blocks)} code blocks. Select which to insert:")
        layout.addWidget(label)

        self._list = QListWidget()
        for i, block in enumerate(blocks):
            # Show first 3 lines as preview
            preview = "\n".join(block.strip().splitlines()[:3])
            if len(block.strip().splitlines()) > 3:
                preview += "\n..."
            item = QListWidgetItem(f"Block {i + 1}:\n{preview}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(item)
        self._list.setCurrentRow(0)
        layout.addWidget(self._list, stretch=1)

        # Buttons
        btn_layout = QVBoxLayout()

        insert_selected = QPushButton("Insert Selected")
        insert_selected.clicked.connect(self._insert_selected)
        btn_layout.addWidget(insert_selected)

        insert_all = QPushButton("Insert All")
        insert_all.clicked.connect(self._insert_all)
        btn_layout.addWidget(insert_all)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)

        layout.addLayout(btn_layout)

    def selected_code(self) -> str:
        return self._selected_code

    def _insert_selected(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            idx = item.data(Qt.ItemDataRole.UserRole)
            self._selected_code = self._blocks[idx]
        self.accept()

    def _insert_all(self) -> None:
        self._selected_code = "\n\n".join(self._blocks)
        self.accept()
