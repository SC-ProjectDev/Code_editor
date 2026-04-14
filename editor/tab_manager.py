# codeeditor/editor/tab_manager.py
# Multi-tab editor manager — each tab holds a CodeEditor + Minimap + FindReplaceBar.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from codeeditor.editor.code_editor import CodeEditor
from codeeditor.editor.find_replace_bar import FindReplaceBar
from codeeditor.editor.minimap import Minimap
from codeeditor.syntax.highlighter_factory import get_highlighter_for_file, detect_language
from codeeditor.syntax.python_highlighter import PythonHighlighter


@dataclass
class TabInfo:
    """Metadata for a single editor tab."""

    editor: CodeEditor
    minimap: Minimap
    find_bar: FindReplaceBar
    file_path: Optional[Path] = None
    highlighter: object = None


class TabManager(QWidget):
    """QTabWidget wrapper that manages multiple editor tabs.

    Signals
    -------
    active_editor_changed(CodeEditor)
        Emitted when the user switches tabs (or a tab is added/removed).
    tab_content_changed()
        Emitted when any tab's text changes (for GIF engine typing trigger).
    """

    active_editor_changed = Signal(CodeEditor)
    tab_content_changed = Signal()

    # Aggregated reaction signals from all tabs
    editor_backspace = Signal()
    editor_paste = Signal()
    no_search_results = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: list[TabInfo] = []

        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.tabCloseRequested.connect(self._on_close_tab)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tab_widget)

        # Start with one empty tab
        self.new_tab()

    # ── Public API ────────────────────────────────────────

    def new_tab(self, file_path: Path | None = None, content: str = "") -> int:
        """Create a new tab. Returns the tab index."""
        editor = CodeEditor(read_only=False)
        find_bar = FindReplaceBar(editor)
        minimap = Minimap(editor)

        # Build the tab widget: [FindBar on top, [Editor | Minimap] below]
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(find_bar)

        editor_row = QWidget()
        row_layout = QHBoxLayout(editor_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(editor, stretch=1)
        row_layout.addWidget(minimap, stretch=0)
        outer.addWidget(editor_row, stretch=1)

        # Connect signals for GIF engine reactions
        editor.textChanged.connect(self.tab_content_changed.emit)
        editor.backspace_pressed.connect(self.editor_backspace.emit)
        editor.paste_performed.connect(self.editor_paste.emit)
        find_bar.no_results_found.connect(self.no_search_results.emit)

        # Apply syntax highlighter (default to Python for new/empty tabs)
        if file_path:
            highlighter = get_highlighter_for_file(file_path, editor)
            editor.set_language(detect_language(file_path))
        else:
            highlighter = PythonHighlighter(editor.document())
            editor.set_language("python")

        # Track info
        info = TabInfo(
            editor=editor,
            minimap=minimap,
            find_bar=find_bar,
            file_path=file_path,
            highlighter=highlighter,
        )
        self._tabs.append(info)

        # Set content
        if content:
            editor.setPlainText(content)
            editor.document().setModified(False)

        # Determine tab label
        label = file_path.name if file_path else "(unsaved)"
        idx = self._tab_widget.addTab(container, label)
        self._tab_widget.setCurrentIndex(idx)

        # Track modified state in tab title
        editor.modificationChanged.connect(
            lambda modified, i=idx: self._update_tab_title(i)
        )

        return idx

    def current_editor(self) -> CodeEditor | None:
        """Return the CodeEditor for the active tab."""
        info = self.current_tab_info()
        return info.editor if info else None

    def current_tab_info(self) -> TabInfo | None:
        """Return TabInfo for the active tab."""
        idx = self._tab_widget.currentIndex()
        if 0 <= idx < len(self._tabs):
            return self._tabs[idx]
        return None

    def current_file_path(self) -> Path | None:
        info = self.current_tab_info()
        return info.file_path if info else None

    def set_current_file_path(self, path: Path) -> None:
        info = self.current_tab_info()
        if info:
            info.file_path = path
            idx = self._tab_widget.currentIndex()
            self._tab_widget.setTabText(idx, path.name)

    def set_current_highlighter(self, highlighter) -> None:
        info = self.current_tab_info()
        if info:
            info.highlighter = highlighter

    def tab_count(self) -> int:
        return self._tab_widget.count()

    def all_tabs(self) -> list[TabInfo]:
        return list(self._tabs)

    def open_file_in_tab(self, file_path: Path, content: str) -> int:
        """Open a file — if it's already open in a tab, switch to it.
        Otherwise create a new tab (or reuse the current one if it's empty+unsaved)."""
        # Check if already open
        for i, info in enumerate(self._tabs):
            if info.file_path == file_path:
                self._tab_widget.setCurrentIndex(i)
                return i

        # Reuse current tab if it's empty and unsaved
        cur = self.current_tab_info()
        if (
            cur is not None
            and cur.file_path is None
            and not cur.editor.document().isModified()
            and cur.editor.toPlainText() == ""
        ):
            idx = self._tab_widget.currentIndex()
            cur.editor.setPlainText(content)
            cur.editor.document().setModified(False)
            cur.file_path = file_path
            self._tab_widget.setTabText(idx, file_path.name)
            return idx

        return self.new_tab(file_path=file_path, content=content)

    def show_find(self) -> None:
        info = self.current_tab_info()
        if info:
            info.find_bar.show_find()

    def show_replace(self) -> None:
        info = self.current_tab_info()
        if info:
            info.find_bar.show_find_replace()

    def ask_to_save_all(self) -> bool:
        """Ask to save all modified tabs. Returns False if user cancels."""
        for i, info in enumerate(self._tabs):
            if info.editor.document().isModified():
                self._tab_widget.setCurrentIndex(i)
                name = info.file_path.name if info.file_path else "(unsaved)"
                btn = QMessageBox.question(
                    self,
                    "Unsaved changes",
                    f"'{name}' has unsaved changes. Save?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if btn == QMessageBox.StandardButton.Cancel:
                    return False
                if btn == QMessageBox.StandardButton.Save:
                    # Caller will handle saving via current_tab_info
                    if info.file_path:
                        try:
                            info.file_path.write_text(
                                info.editor.toPlainText(), encoding="utf-8"
                            )
                            info.editor.document().setModified(False)
                        except Exception as e:
                            QMessageBox.critical(self, "Save failed", str(e))
                            return False
                    else:
                        # No path — can't auto-save; skip for now
                        pass
        return True

    # ── Internals ─────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < len(self._tabs):
            self.active_editor_changed.emit(self._tabs[index].editor)

    def _on_close_tab(self, index: int) -> None:
        if self._tab_widget.count() <= 1:
            # Don't close the last tab — just clear it
            info = self._tabs[0]
            if info.editor.document().isModified():
                btn = QMessageBox.question(
                    self,
                    "Unsaved changes",
                    "Discard unsaved changes?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if btn != QMessageBox.StandardButton.Yes:
                    return
            info.editor.clear()
            info.editor.document().setModified(False)
            info.file_path = None
            info.highlighter = PythonHighlighter(info.editor.document())
            info.editor.set_language("python")
            self._tab_widget.setTabText(0, "(unsaved)")
            return

        info = self._tabs[index]
        if info.editor.document().isModified():
            name = info.file_path.name if info.file_path else "(unsaved)"
            btn = QMessageBox.question(
                self,
                "Unsaved changes",
                f"'{name}' has unsaved changes. Discard?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if btn != QMessageBox.StandardButton.Yes:
                return

        self._tab_widget.removeTab(index)
        self._tabs.pop(index)

    def _update_tab_title(self, index: int) -> None:
        """Append/remove '*' indicator on modified tabs."""
        if index < 0 or index >= len(self._tabs):
            return
        info = self._tabs[index]
        name = info.file_path.name if info.file_path else "(unsaved)"
        if info.editor.document().isModified():
            name += " *"
        self._tab_widget.setTabText(index, name)

    def apply_wrap_mode(self, mode) -> None:
        """Apply wrap mode to all tabs."""
        for info in self._tabs:
            info.editor.setLineWrapMode(mode)

    def set_language_all(self, lang: str) -> None:
        """Set language for auto-indent on all tabs' editors (called on highlighter change)."""
        for info in self._tabs:
            info.editor.set_language(lang)
