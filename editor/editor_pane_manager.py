# codeeditor/editor/editor_pane_manager.py
# Manages the vertical splitter containing preview + tabbed work editors.

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from codeeditor.editor.code_editor import CodeEditor
from codeeditor.editor.tab_manager import TabManager


class EditorPaneManager:
    """Toggles between split (preview + tabbed work) and single (work-only) views."""

    def __init__(
        self,
        preview_editor: CodeEditor,
        tab_manager: TabManager,
    ):
        self._preview = preview_editor
        self._tab_mgr = tab_manager

        # ── Preview container (just the editor, no extras) ──
        self._preview_container = QWidget()
        preview_layout = QVBoxLayout(self._preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.addWidget(self._preview)

        # ── Vertical splitter: preview on top, tabs on bottom ──
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self._preview_container)
        self.splitter.addWidget(self._tab_mgr)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        self._preview_visible = True
        self._saved_sizes: list[int] | None = None

    # ── Public API ────────────────────────────────────────

    @property
    def tab_manager(self) -> TabManager:
        return self._tab_mgr

    def toggle_preview(self, visible: bool) -> None:
        """Show or hide the preview pane, remembering splitter sizes."""
        if visible and not self._preview_visible:
            self._preview_container.setVisible(True)
            if self._saved_sizes:
                self.splitter.setSizes(self._saved_sizes)
            self._preview_visible = True
        elif not visible and self._preview_visible:
            self._saved_sizes = self.splitter.sizes()
            self._preview_container.setVisible(False)
            self._preview_visible = False

    def is_preview_visible(self) -> bool:
        return self._preview_visible

    def show_find(self) -> None:
        """Open find bar on the active tab (Ctrl+F)."""
        self._tab_mgr.show_find()

    def show_replace(self) -> None:
        """Open find+replace bar on the active tab (Ctrl+H)."""
        self._tab_mgr.show_replace()
