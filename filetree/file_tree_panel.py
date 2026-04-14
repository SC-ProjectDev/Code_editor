# codeeditor/filetree/file_tree_panel.py
# Left-column widget: file tree + GIF player slot.

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QFileSystemModel,
    QInputDialog,
    QMenu,
    QMessageBox,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from codeeditor.gifengine.gif_player import GifPlayer
from codeeditor.filetree.file_type_delegate import FileTypeDelegate


class FileTreePanel(QWidget):
    """File tree browser with an optional GIF player area below."""

    # Emitted when the user double-clicks a file (not a directory)
    file_selected = Signal(Path)

    def __init__(self, gif_player: GifPlayer | None = None, parent=None):
        super().__init__(parent)

        # ── File system model ─────────────────────────────
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setReadOnly(True)

        # ── Tree view ─────────────────────────────────────
        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setItemDelegateForColumn(0, FileTypeDelegate(self.tree))
        self.tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree.setHeaderHidden(False)
        self.tree.setAnimated(True)
        self.tree.setColumnWidth(0, 240)
        for col, w in [(1, 80), (2, 100), (3, 140)]:
            self.tree.setColumnWidth(col, w)
        self.tree.doubleClicked.connect(self._on_double_click)

        # ── Context menu ──────────────────────────────────
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        # ── Layout ────────────────────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self.tree)
        self._splitter.setStretchFactor(0, 1)

        if gif_player is not None:
            self._splitter.addWidget(gif_player)
            self._splitter.setStretchFactor(1, 0)
            self._splitter.setSizes([400, 160])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._splitter)

        self._gif_player = gif_player

    # ── Public API ────────────────────────────────────────

    def set_root_path(self, path: str) -> None:
        """Set the root directory shown in the tree."""
        root_index = self.fs_model.setRootPath(path)
        self.tree.setRootIndex(root_index)

    def set_gif_player(self, player: GifPlayer) -> None:
        """Attach a GIF player widget below the tree (if not set in constructor)."""
        if self._gif_player is not None:
            return
        self._gif_player = player
        self._splitter.addWidget(player)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([400, 160])

    # ── Context menu ──────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        index = self.tree.indexAt(pos)
        menu = QMenu(self)

        if index.isValid():
            file_path = Path(self.fs_model.filePath(index))
            is_dir = file_path.is_dir()

            if is_dir:
                menu.addAction("New File...", lambda: self._new_file(file_path))
                menu.addAction("New Folder...", lambda: self._new_folder(file_path))
                menu.addSeparator()
            else:
                menu.addAction("Open", lambda: self.file_selected.emit(file_path))
                menu.addSeparator()

            menu.addAction("Rename...", lambda: self._rename(file_path))
            menu.addAction("Delete", lambda: self._delete(file_path))
            menu.addSeparator()
            menu.addAction("Copy Path", lambda: QApplication.clipboard().setText(str(file_path)))

            if is_dir:
                menu.addAction(
                    "Open in Explorer",
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path))),
                )
            else:
                menu.addAction(
                    "Open in Explorer",
                    lambda: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(file_path.parent))
                    ),
                )
        else:
            # Right-click on empty space — use the current root
            root_path = Path(self.fs_model.rootPath())
            if root_path.is_dir():
                menu.addAction("New File...", lambda: self._new_file(root_path))
                menu.addAction("New Folder...", lambda: self._new_folder(root_path))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _new_file(self, parent_dir: Path) -> None:
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name.strip():
            target = parent_dir / name.strip()
            if target.exists():
                QMessageBox.warning(self, "Exists", f"{target.name} already exists.")
                return
            try:
                target.touch()
            except OSError as e:
                QMessageBox.critical(self, "Error", str(e))

    def _new_folder(self, parent_dir: Path) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            target = parent_dir / name.strip()
            if target.exists():
                QMessageBox.warning(self, "Exists", f"{target.name} already exists.")
                return
            try:
                target.mkdir(parents=False)
            except OSError as e:
                QMessageBox.critical(self, "Error", str(e))

    def _rename(self, path: Path) -> None:
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=path.name
        )
        if ok and new_name.strip() and new_name.strip() != path.name:
            target = path.parent / new_name.strip()
            if target.exists():
                QMessageBox.warning(self, "Exists", f"{target.name} already exists.")
                return
            try:
                path.rename(target)
            except OSError as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self, path: Path) -> None:
        kind = "folder" if path.is_dir() else "file"
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {kind} '{path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── Internals ─────────────────────────────────────────

    def _on_double_click(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        file_path = Path(self.fs_model.filePath(index))
        if file_path.is_dir():
            return
        self.file_selected.emit(file_path)
