# codeeditor/main_window.py
# Main application window — three-column layout with GIF engine, AI panel,
# multi-tab editing, find/replace, minimap, config persistence, and shortcuts.

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMainWindow,
    QFileDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QToolBar,
    QToolButton,
    QLabel,
    QStatusBar,
)

from codeeditor.config import (
    WINDOW_TITLE,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    SNAPSHOT_DIR_NAME,
    GIF_TYPING_DEBOUNCE_MS,
    GIF_SAVING_DURATION_MS,
    AI_RESPONSE_GIF_DURATION_MS,
    AUTO_SAVE_INTERVAL_MS,
    REACTION_DEBOUNCE_MS,
    SESSION_LOG_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    GEMINI_API_KEY_ENV,
    OPENAI_API_KEY_ENV,
    ANTHROPIC_API_KEY_ENV,
)
from codeeditor.themes import Theme, apply_theme
from codeeditor.editor import CodeEditor, EditorPaneManager, TabManager
from codeeditor.editor.shortcut_dialog import ShortcutCheatSheet
from codeeditor.syntax import (
    PythonHighlighter,
    get_highlighter_for_file,
    detect_language,
)
from codeeditor.filetree import FileTreePanel
from codeeditor.gifengine import GifPlayer, GifStateManager
from codeeditor.ai import AIPanel
from codeeditor.ai.session_logger import SessionLogger
from codeeditor.settings import Settings


class MainWindow(QMainWindow):
    def __init__(self, start_path: Path | None = None):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)

        self._settings = Settings.instance()
        self._current_theme: str = self._settings.theme()
        self._session_logger: SessionLogger | None = None

        # Track active highlighter for preview pane
        self._preview_highlighter = None

        # ── Build UI ───────────────────────────────────────
        self._build_editors()
        self._build_gif_engine()
        self._build_file_tree(start_path)
        self._build_ai_panel()
        self._build_layout()
        self._build_toolbar()
        self._build_statusbar()
        self._wire_gif_events()
        self._init_session_logger()
        self._load_ai_keys()
        self._restore_settings()
        self._sync_titles()

        # ── Drag & drop ───────────────────────────────────
        self.setAcceptDrops(True)

        # ── Auto-save ─────────────────────────────────────
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setInterval(AUTO_SAVE_INTERVAL_MS)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._auto_save_timer.start()

        # ── Initial startup reaction ──────────────────────
        self._gif_state.trigger_reaction("initial")

    # ==================================================================
    # Convenience: active work editor
    # ==================================================================

    @property
    def work_editor(self) -> CodeEditor | None:
        """Return the CodeEditor for the currently active tab."""
        return self._tab_mgr.current_editor()

    @property
    def _work_path(self) -> Path | None:
        return self._tab_mgr.current_file_path()

    @_work_path.setter
    def _work_path(self, value: Path | None) -> None:
        if value is not None:
            self._tab_mgr.set_current_file_path(value)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_editors(self):
        """Preview (read-only) and tabbed Work editors."""
        self.preview_editor = CodeEditor(read_only=True)
        self._preview_highlighter = PythonHighlighter(self.preview_editor.document())

        # Multi-tab work area
        self._tab_mgr = TabManager()
        self._tab_mgr.active_editor_changed.connect(self._on_active_tab_changed)

        self._pane_mgr = EditorPaneManager(self.preview_editor, self._tab_mgr)

    def _build_gif_engine(self):
        self._gif_player = GifPlayer()
        self._gif_state = GifStateManager(self._gif_player, parent=self)

    def _build_file_tree(self, start_path: Path | None):
        self._file_tree = FileTreePanel(gif_player=self._gif_player)
        # Use last opened folder from settings if no explicit start path
        last_folder = self._settings.last_opened_folder()
        root = str(start_path or (last_folder if last_folder else Path.cwd()))
        self._file_tree.set_root_path(root)
        self._file_tree.file_selected.connect(self._on_file_selected)

    def _build_ai_panel(self):
        self._ai_panel = AIPanel()
        self._ai_panel.setVisible(False)
        self._ai_visible = False
        self._ai_saved_sizes: list[int] | None = None

        self._ai_panel.request_code_context.connect(self._send_code_context)
        self._ai_panel.ai_request_started.connect(
            lambda: self._gif_state.set_state("ai_waiting")
        )
        self._ai_panel.ai_request_finished.connect(self._on_ai_response_done)
        self._ai_panel.insert_code_requested.connect(self._insert_code_at_cursor)

        # Reaction triggers from AI panel
        self._ai_panel.ai_selector_changed.connect(self._on_ai_selector_changed)
        self._ai_panel.paste_in_prompt.connect(
            lambda: self._gif_state.trigger_reaction_debounced("pasting", REACTION_DEBOUNCE_MS)
        )

    def _build_layout(self):
        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.addWidget(self._file_tree)
        self._main_split.addWidget(self._pane_mgr.splitter)
        self._main_split.addWidget(self._ai_panel)
        self._main_split.setStretchFactor(0, 0)
        self._main_split.setStretchFactor(1, 1)
        self._main_split.setStretchFactor(2, 0)
        self.setCentralWidget(self._main_split)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(tb)

        # ── File actions ──────────────────────────────────
        self.act_open_folder = QAction("Open Folder\u2026", self)
        self.act_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_open_folder.setToolTip("Open a folder in the file tree")
        self.act_open_folder.triggered.connect(self._open_folder)

        self.act_new_work = QAction("New Tab", self)
        self.act_new_work.setShortcut(QKeySequence.StandardKey.New)
        self.act_new_work.setToolTip("Open a new editor tab")
        self.act_new_work.triggered.connect(self._new_work_doc)

        self.act_save_work = QAction("Save", self)
        self.act_save_work.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save_work.setToolTip("Save the active tab")
        self.act_save_work.triggered.connect(self._save_work)

        self.act_save_work_as = QAction("Save As\u2026", self)
        self.act_save_work_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_work_as.triggered.connect(self._save_work_as)

        self.act_snapshot = QAction("Snapshot", self)
        self.act_snapshot.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_snapshot.setToolTip("Save a timestamped snapshot")
        self.act_snapshot.triggered.connect(self._snapshot_work)

        # ── Editor actions ────────────────────────────────
        self.act_copy_to_work = QAction("Preview \u2192 Work", self)
        self.act_copy_to_work.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.act_copy_to_work.setToolTip("Copy preview contents into active tab")
        self.act_copy_to_work.triggered.connect(self._copy_preview_to_work)

        self.act_find = QAction("Find", self)
        self.act_find.setShortcut(QKeySequence("Ctrl+F"))
        self.act_find.setToolTip("Find in active tab")
        self.act_find.triggered.connect(lambda: self._pane_mgr.show_find())

        self.act_replace = QAction("Replace", self)
        self.act_replace.setShortcut(QKeySequence("Ctrl+H"))
        self.act_replace.setToolTip("Find & replace in active tab")
        self.act_replace.triggered.connect(lambda: self._pane_mgr.show_replace())

        self.act_toggle_preview = QAction("Toggle Preview", self)
        self.act_toggle_preview.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_toggle_preview.setCheckable(True)
        self.act_toggle_preview.setChecked(True)
        self.act_toggle_preview.setToolTip("Show / hide the read-only preview pane")
        self.act_toggle_preview.triggered.connect(self._toggle_preview)

        self.act_toggle_ai = QAction("Toggle AI Panel", self)
        self.act_toggle_ai.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.act_toggle_ai.setCheckable(True)
        self.act_toggle_ai.setChecked(False)
        self.act_toggle_ai.setToolTip("Show / hide the AI context panel")
        self.act_toggle_ai.triggered.connect(self._toggle_ai_panel)

        self.act_toggle_wrap = QAction("Word Wrap", self)
        self.act_toggle_wrap.setCheckable(True)
        self.act_toggle_wrap.setChecked(self._settings.wrap_mode())
        self.act_toggle_wrap.triggered.connect(self._toggle_wrap)

        # ── Theme ─────────────────────────────────────────
        is_light = self._current_theme == Theme.LIGHT
        self.act_theme = QAction("Dark Mode" if is_light else "Light Mode", self)
        self.act_theme.setCheckable(True)
        self.act_theme.setChecked(is_light)
        self.act_theme.setToolTip("Switch between light and dark themes")
        self.act_theme.triggered.connect(self._toggle_theme)

        # ── Media sound ───────────────────────────────────
        self.act_mute = QAction("Mute \U0001F50A", self)
        self.act_mute.setCheckable(True)
        self.act_mute.setChecked(False)
        self.act_mute.setToolTip("Mute / unmute MP4 clip audio")
        self.act_mute.triggered.connect(self._toggle_mute)

        # ── Settings / Utility ────────────────────────────
        self.act_api_keys = QAction("API Keys", self)
        self.act_api_keys.setToolTip("Configure Gemini / GPT / Claude API keys")
        self.act_api_keys.triggered.connect(self._show_api_key_dialog)

        self.act_shortcuts = QAction("Shortcuts", self)
        self.act_shortcuts.setShortcut(QKeySequence("Ctrl+/"))
        self.act_shortcuts.setToolTip("Show keyboard shortcut cheat sheet")
        self.act_shortcuts.triggered.connect(self._show_shortcuts_dialog)

        # ── Recent files button ───────────────────────────
        self._recent_menu = QMenu("Recent Files", self)
        self._recent_btn = QToolButton()
        self._recent_btn.setText("Recent")
        self._recent_btn.setToolTip("Recently opened files")
        self._recent_btn.setMenu(self._recent_menu)
        self._recent_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._recent_menu.aboutToShow.connect(self._populate_recent_menu)

        # ── Add to toolbar ────────────────────────────────
        for a in (
            self.act_open_folder,
            self.act_new_work,
            self.act_save_work,
            self.act_save_work_as,
            self.act_snapshot,
        ):
            tb.addAction(a)
        tb.addWidget(self._recent_btn)

        tb.addSeparator()

        for a in (
            self.act_copy_to_work,
            self.act_find,
            self.act_replace,
            self.act_toggle_preview,
            self.act_toggle_ai,
            self.act_toggle_wrap,
        ):
            tb.addAction(a)

        tb.addSeparator()
        tb.addAction(self.act_theme)
        tb.addAction(self.act_mute)
        tb.addAction(self.act_api_keys)
        tb.addAction(self.act_shortcuts)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._cursor_label = QLabel("")
        self._lang_label = QLabel("Python")
        self._encoding_label = QLabel("UTF-8")
        self._line_ending_label = QLabel("")
        self._file_size_label = QLabel("")
        self.status.addPermanentWidget(self._file_size_label)
        self.status.addPermanentWidget(self._encoding_label)
        self.status.addPermanentWidget(self._line_ending_label)
        self.status.addPermanentWidget(self._lang_label)
        self.status.addPermanentWidget(self._cursor_label)

        self.preview_editor.cursorPositionChanged.connect(
            lambda: self._update_cursor_status(self.preview_editor)
        )
        # Active tab cursor tracking is wired via _on_active_tab_changed
        if self.work_editor:
            self._wire_cursor_tracking(self.work_editor)
            self._update_cursor_status(self.work_editor)

    def _wire_cursor_tracking(self, editor: CodeEditor) -> None:
        """Connect cursor position tracking for an editor."""
        editor.cursorPositionChanged.connect(
            lambda: self._update_cursor_status(editor)
        )

    def _wire_gif_events(self):
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.setInterval(GIF_TYPING_DEBOUNCE_MS)
        self._typing_timer.timeout.connect(
            lambda: self._gif_state.clear_state("typing")
        )
        # Connect to the tab manager's content-changed signal (fires from any tab)
        self._tab_mgr.tab_content_changed.connect(self._on_text_changed)

        # Reaction triggers from editor tabs
        self._tab_mgr.editor_backspace.connect(
            lambda: self._gif_state.trigger_reaction_debounced(
                "pressing_backspace", REACTION_DEBOUNCE_MS
            )
        )
        self._tab_mgr.editor_paste.connect(
            lambda: self._gif_state.trigger_reaction_debounced(
                "pasting", REACTION_DEBOUNCE_MS
            )
        )
        self._tab_mgr.no_search_results.connect(
            lambda: self._gif_state.trigger_reaction("no_search_results")
        )

        self._saving_timer = QTimer(self)
        self._saving_timer.setSingleShot(True)
        self._saving_timer.setInterval(GIF_SAVING_DURATION_MS)
        self._saving_timer.timeout.connect(
            lambda: self._gif_state.clear_state("saving")
        )

    def _init_session_logger(self):
        self._session_logger = SessionLogger(SESSION_LOG_DIR)
        self._ai_panel.set_session_logger(self._session_logger)

    def _load_ai_keys(self):
        gemini_key = os.environ.get(GEMINI_API_KEY_ENV, "")
        gpt_key = os.environ.get(OPENAI_API_KEY_ENV, "")
        claude_key = os.environ.get(ANTHROPIC_API_KEY_ENV, "")

        if not gemini_key or not gpt_key or not claude_key:
            env_file = Path.cwd() / ".env"
            if env_file.is_file():
                env_vars = _parse_dotenv(env_file)
                gemini_key = gemini_key or env_vars.get(GEMINI_API_KEY_ENV, "")
                gpt_key = gpt_key or env_vars.get(OPENAI_API_KEY_ENV, "")
                claude_key = claude_key or env_vars.get(ANTHROPIC_API_KEY_ENV, "")

        if not gemini_key or not gpt_key or not claude_key:
            try:
                cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                gemini_key = gemini_key or cfg.get("gemini_api_key", "")
                gpt_key = gpt_key or cfg.get("openai_api_key", "")
                claude_key = claude_key or cfg.get("anthropic_api_key", "")
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        if gemini_key or gpt_key or claude_key:
            self._ai_panel.set_api_keys(gemini_key, gpt_key, claude_key)
        else:
            self.status.showMessage(
                "AI keys not found. Use API Keys button or set env vars.", 5000
            )

    def _restore_settings(self):
        """Restore window state from persisted settings."""
        s = self._settings

        # Window geometry
        geo = s.window_geometry()
        self.resize(geo.get("width", DEFAULT_WIDTH), geo.get("height", DEFAULT_HEIGHT))
        x, y = geo.get("x", 100), geo.get("y", 100)
        self.move(x, y)

        # Splitter sizes
        saved = s.splitter_sizes()
        if "main" in saved:
            self._main_split.setSizes(saved["main"])
        if "editor" in saved:
            self._pane_mgr.splitter.setSizes(saved["editor"])

        # Wrap mode
        if s.wrap_mode():
            self._toggle_wrap(True)

    def _on_text_changed(self):
        self._gif_state.set_state("typing")
        self._typing_timer.start()

    def _on_active_tab_changed(self, editor: CodeEditor):
        """Called when the user switches tabs — update status bar and title."""
        self._wire_cursor_tracking(editor)
        self._update_cursor_status(editor)
        self._sync_titles()

        # Update language label for the active tab
        info = self._tab_mgr.current_tab_info()
        if info and info.file_path:
            lang = detect_language(info.file_path)
            self._lang_label.setText(lang.capitalize())

    # ==================================================================
    # AI Integration
    # ==================================================================

    def _send_code_context(self):
        """Send code from the ACTIVE tab to the AI panel."""
        editor = self.work_editor
        if editor is None:
            self._ai_panel.set_code_context("")
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            code = cursor.selectedText().replace("\u2029", "\n")
        else:
            code = editor.toPlainText()
        self._ai_panel.set_code_context(code)

    def _on_ai_selector_changed(self, name: str):
        """Trigger a reaction clip when the user picks a different AI."""
        mapping = {
            "Claude": "selected_claude",
            "GPT": "selected_gpt",
            "Gemini": "selected_gemini",
        }
        reaction = mapping.get(name)
        if reaction:
            self._gif_state.trigger_reaction(reaction)

    def _on_ai_response_done(self):
        self._gif_state.clear_state("ai_waiting")
        self._gif_state.set_state("ai_response")
        QTimer.singleShot(
            AI_RESPONSE_GIF_DURATION_MS,
            lambda: self._gif_state.clear_state("ai_response"),
        )

    def _insert_code_at_cursor(self, code: str):
        """Insert code from AI response at the ACTIVE tab's cursor."""
        editor = self.work_editor
        if editor is None:
            return
        cursor = editor.textCursor()
        cursor.insertText(code)
        editor.setTextCursor(cursor)
        self.status.showMessage("Code inserted from AI response.", 3000)

    def _show_api_key_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("API Keys")
        dialog.setMinimumWidth(400)

        form = QFormLayout(dialog)

        gemini_input = QLineEdit()
        gemini_input.setPlaceholderText("Enter Gemini API key")
        gemini_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Gemini API Key:", gemini_input)

        gpt_input = QLineEdit()
        gpt_input.setPlaceholderText("Enter GPT API key")
        gpt_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("GPT API Key:", gpt_input)

        claude_input = QLineEdit()
        claude_input.setPlaceholderText("Enter Claude API key")
        claude_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Claude API Key:", claude_input)

        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            gemini_input.setText(cfg.get("gemini_api_key", ""))
            gpt_input.setText(cfg.get("openai_api_key", ""))
            claude_input.setText(cfg.get("anthropic_api_key", ""))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            gemini_key = gemini_input.text().strip()
            gpt_key = gpt_input.text().strip()
            claude_key = claude_input.text().strip()

            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            try:
                cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                cfg = {}

            if gemini_key:
                cfg["gemini_api_key"] = gemini_key
            if gpt_key:
                cfg["openai_api_key"] = gpt_key
            if claude_key:
                cfg["anthropic_api_key"] = claude_key

            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            self._ai_panel.set_api_keys(gemini_key, gpt_key, claude_key)
            self.status.showMessage("API keys saved.", 3000)

    def _show_shortcuts_dialog(self):
        dialog = ShortcutCheatSheet(parent=self)
        dialog.exec()

    # ==================================================================
    # Actions
    # ==================================================================

    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose folder", str(Path.cwd()))
        if not path:
            return
        self._file_tree.set_root_path(path)
        self._settings.set_last_opened_folder(path)
        self.status.showMessage(f"Opened folder: {path}", 3000)
        self._gif_state.trigger_reaction("opening")

    def _on_file_selected(self, file_path: Path):
        try:
            raw = file_path.read_bytes()
            text = raw.decode("utf-8")
        except Exception as e:
            QMessageBox.warning(
                self, "Preview failed",
                f"Could not preview file:\n{file_path}\n\n{e}",
            )
            return

        self.preview_editor.setPlainText(text)
        self._apply_preview_highlighter(file_path)
        self._settings.add_recent_file(str(file_path))
        self._update_file_info(file_path, raw)
        self.status.showMessage(f"Preview: {file_path}", 3000)
        self._gif_state.trigger_reaction("opening")

    def _apply_preview_highlighter(self, file_path: Path):
        """Apply highlighter to the preview pane only."""
        lang = detect_language(file_path)
        self._lang_label.setText(lang.capitalize())
        self.preview_editor.set_language(lang)

        hl = get_highlighter_for_file(file_path, self.preview_editor)
        if hl is not None:
            self._preview_highlighter = hl

    def _apply_work_highlighter(self, file_path: Path):
        """Apply highlighter to the active work tab."""
        editor = self.work_editor
        if editor is None:
            return
        lang = detect_language(file_path)
        editor.set_language(lang)
        hl = get_highlighter_for_file(file_path, editor)
        if hl is not None:
            self._tab_mgr.set_current_highlighter(hl)

    def _copy_preview_to_work(self):
        """Copy preview text into the active work tab."""
        editor = self.work_editor
        if editor is None:
            return
        editor.setPlainText(self.preview_editor.toPlainText())
        editor.document().setModified(True)
        # Clear the tab's file path since this is now unsaved content
        info = self._tab_mgr.current_tab_info()
        if info:
            info.file_path = None
        self._sync_titles()
        self.status.showMessage("Copied preview to active tab (unsaved)", 3000)

    def _new_work_doc(self):
        """Create a new editor tab."""
        self._tab_mgr.new_tab()
        self._sync_titles()
        self._gif_state.trigger_reaction("opening")

    def _save_work(self) -> bool:
        """Save the active tab."""
        editor = self.work_editor
        if editor is None:
            return False
        work_path = self._work_path
        if work_path is None:
            return self._save_work_as()
        try:
            work_path.write_text(editor.toPlainText(), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", f"Could not save:\n{e}")
            return False
        editor.document().setModified(False)
        self.status.showMessage(f"Saved: {work_path}", 2000)
        self._sync_titles()

        self._gif_state.set_state("saving")
        self._saving_timer.start()
        return True

    def _save_work_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Work As",
            str(self._work_path or Path.cwd()),
            "Python (*.py);;JavaScript (*.js);;All files (*)",
        )
        if not path:
            return False
        self._work_path = Path(path)
        self._apply_work_highlighter(Path(path))
        return self._save_work()

    def _snapshot_work(self):
        editor = self.work_editor
        if editor is None:
            return
        text = editor.toPlainText()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        work_path = self._work_path
        if work_path is not None:
            base_dir = work_path.parent / SNAPSHOT_DIR_NAME
            base_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{work_path.stem}-{timestamp}{work_path.suffix}"
            snap_path = base_dir / fname
        else:
            base_dir = Path.cwd() / "snapshots"
            base_dir.mkdir(parents=True, exist_ok=True)
            snap_path = base_dir / f"unsaved-{timestamp}.txt"
        try:
            snap_path.write_text(text, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Snapshot failed", str(e))
            return
        self.status.showMessage(f"Snapshot saved: {snap_path}", 3000)

    def _toggle_preview(self, checked: bool):
        self._pane_mgr.toggle_preview(checked)

    def _toggle_ai_panel(self, checked: bool):
        if checked and not self._ai_visible:
            self._ai_panel.setVisible(True)
            if self._ai_saved_sizes:
                self._main_split.setSizes(self._ai_saved_sizes)
            else:
                sizes = self._main_split.sizes()
                ai_width = 300
                sizes[1] = max(sizes[1] - ai_width, 200)
                if len(sizes) >= 3:
                    sizes[2] = ai_width
                self._main_split.setSizes(sizes)
            self._ai_visible = True
        elif not checked and self._ai_visible:
            self._ai_saved_sizes = self._main_split.sizes()
            self._ai_panel.setVisible(False)
            self._ai_visible = False

    def _toggle_wrap(self, checked: bool):
        mode = (
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if checked
            else QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.preview_editor.setLineWrapMode(mode)
        # Apply to all tabs
        self._tab_mgr.apply_wrap_mode(mode)
        self._settings.set_wrap_mode(checked)

    def _toggle_mute(self, checked: bool):
        self._gif_player.set_muted(checked)
        self.act_mute.setText("Unmute \U0001F507" if checked else "Mute \U0001F50A")
        self._gif_state.trigger_reaction("mute")

    def _toggle_theme(self, checked: bool):
        app = QApplication.instance()
        if checked:
            self._current_theme = Theme.LIGHT
            self.act_theme.setText("Dark Mode")
        else:
            self._current_theme = Theme.DARK
            self.act_theme.setText("Light Mode")
        apply_theme(app, self._current_theme)
        self._settings.set_theme(self._current_theme)
        self.preview_editor.highlight_current_line()
        # Highlight current line on all open tabs
        for info in self._tab_mgr.all_tabs():
            info.editor.highlight_current_line()
        self._gif_state.trigger_reaction(
            "light_mode_enabled" if checked else "dark_mode_enabled"
        )

    # ==================================================================
    # Helpers
    # ==================================================================

    def _ask_to_save_if_dirty(self) -> bool:
        """Check all tabs for unsaved changes."""
        return self._tab_mgr.ask_to_save_all()

    def _sync_titles(self):
        info = self._tab_mgr.current_tab_info()
        if info is None:
            self.setWindowTitle(WINDOW_TITLE)
            return
        work_name = info.file_path.name if info.file_path else "(unsaved)"
        mod = "*" if info.editor.document().isModified() else ""
        self.setWindowTitle(f"{WINDOW_TITLE} \u2014 {work_name}{mod}")

    def _update_cursor_status(self, editor: CodeEditor):
        c = editor.textCursor()
        line = c.blockNumber() + 1
        col = c.positionInBlock() + 1
        role = "Work" if editor is not self.preview_editor else "Preview"
        self._cursor_label.setText(f"  {role}  Ln {line}, Col {col}  ")

    def _update_file_info(self, file_path: Path, raw: bytes) -> None:
        """Update status bar file-info labels."""
        size = len(raw)
        if size < 1024:
            self._file_size_label.setText(f"  {size} B  ")
        elif size < 1024 * 1024:
            self._file_size_label.setText(f"  {size / 1024:.1f} KB  ")
        else:
            self._file_size_label.setText(f"  {size / (1024 * 1024):.1f} MB  ")

        self._line_ending_label.setText("  CRLF  " if b"\r\n" in raw else "  LF  ")
        self._encoding_label.setText("  UTF-8  ")

    def _populate_recent_menu(self) -> None:
        """Rebuild the Recent Files menu each time it's about to show."""
        self._recent_menu.clear()
        recent = self._settings.recent_files()
        found_any = False
        for p in recent:
            path = Path(p)
            if path.exists():
                found_any = True
                action = self._recent_menu.addAction(path.name)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked, fp=path: self._on_file_selected(fp))
        if not found_any:
            empty = self._recent_menu.addAction("(no recent files)")
            empty.setEnabled(False)

    def _auto_save(self) -> None:
        """Auto-save all modified tabs that have a file path."""
        saved_any = False
        for info in self._tab_mgr.all_tabs():
            if info.file_path is not None and info.editor.document().isModified():
                try:
                    info.file_path.write_text(
                        info.editor.toPlainText(), encoding="utf-8"
                    )
                    info.editor.document().setModified(False)
                    saved_any = True
                except Exception:
                    pass  # silent — don't interrupt the user
        if saved_any:
            self._sync_titles()
            self._gif_state.trigger_reaction("auto_save")

    # ── Drag & Drop ───────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file():
                self._on_file_selected(path)
                break
            elif path.is_dir():
                self._file_tree.set_root_path(str(path))
                self._settings.set_last_opened_folder(str(path))
                self.status.showMessage(f"Opened folder: {path}", 3000)
                break

    def closeEvent(self, event):
        if self._ask_to_save_if_dirty():
            # Save settings
            geo = self.geometry()
            self._settings.set_window_geometry(geo.x(), geo.y(), geo.width(), geo.height())
            self._settings.set_splitter_sizes("main", self._main_split.sizes())
            self._settings.set_splitter_sizes("editor", self._pane_mgr.splitter.sizes())

            if self._session_logger:
                self._session_logger.close()
            event.accept()
        else:
            event.ignore()


def _parse_dotenv(env_path: Path) -> dict[str, str]:
    """Parse a simple .env file into a dict."""
    result: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            result[key] = value
    return result
