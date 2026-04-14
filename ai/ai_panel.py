# codeeditor/ai/ai_panel.py
# Full AI chat panel — third column UI with conversation display,
# input controls, file attachments, and API client orchestration.

from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtWidgets import QDialog

from codeeditor.ai.claude_client import ClaudeClient
from codeeditor.ai.code_block_picker import CodeBlockPicker
from codeeditor.ai.file_attachment import FileAttachmentBar
from codeeditor.ai.gemini_client import GeminiClient
from codeeditor.ai.gpt_client import GPTClient
from codeeditor.ai.session_logger import SessionLogger
from codeeditor.ai.worker import AIWorker


# Persona colors (used as inline HTML styles in the chat area)
_PERSONA_COLORS = {
    "@Gemini": "#4A90D9",
    "@GPT": "#4CAF50",
    "@Claude": "#D97706",
}


class _PasteAwareTextEdit(QTextEdit):
    """QTextEdit that emits a signal on paste."""

    paste_performed = Signal()

    def insertFromMimeData(self, source):
        super().insertFromMimeData(source)
        self.paste_performed.emit()


class AIPanel(QWidget):
    """Third-column AI chat panel with conversation history and input controls."""

    # MainWindow connects these to supply editor text
    request_code_context = Signal()

    # MainWindow connects these to drive the GIF engine
    ai_request_started = Signal()
    ai_request_finished = Signal()

    # MainWindow connects this to insert code into work editor
    insert_code_requested = Signal(str)

    # Reaction triggers for GIF engine
    ai_selector_changed = Signal(str)   # "Claude", "GPT", "Gemini"
    paste_in_prompt = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ai_placeholder")

        self._gemini_client: GeminiClient | None = None
        self._gpt_client: GPTClient | None = None
        self._claude_client: ClaudeClient | None = None
        self._session_logger: SessionLogger | None = None
        self._current_worker: AIWorker | None = None
        self._pending_code: str = ""
        self._send_with_code: bool = False
        self._last_response_text: str = ""
        self._pending_persona: str = ""
        # Per-persona conversation history: list of {"role": "user"/"assistant", "content": str}
        self._history: dict[str, list[dict]] = {}

        self._build_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Chat display ──────────────────────────────────
        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setPlaceholderText("AI conversation will appear here...")
        layout.addWidget(self._chat, stretch=1)

        # ── Attachment bar ────────────────────────────────
        self._attachment_bar = FileAttachmentBar()
        layout.addWidget(self._attachment_bar, stretch=0)

        # ── Prompt input (multi-line, paste-aware) ─────────
        self._prompt_input = _PasteAwareTextEdit()
        self._prompt_input.setPlaceholderText("Ask the AI something...")
        self._prompt_input.setMinimumHeight(80)
        self._prompt_input.setMaximumHeight(150)
        self._prompt_input.setAcceptRichText(False)
        self._prompt_input.installEventFilter(self)
        self._prompt_input.paste_performed.connect(self.paste_in_prompt.emit)
        layout.addWidget(self._prompt_input, stretch=0)

        # ── Button row ────────────────────────────────────
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        self._ai_selector = QComboBox()
        self._ai_selector.addItems(["Gemini", "GPT", "Claude"])
        self._ai_selector.setFixedWidth(90)
        self._ai_selector.currentTextChanged.connect(self.ai_selector_changed.emit)
        btn_layout.addWidget(self._ai_selector)

        self._send_btn = QPushButton("Send")
        self._send_btn.setToolTip("Send prompt to selected AI")
        self._send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self._send_btn)

        self._send_code_btn = QPushButton("Send Code")
        self._send_code_btn.setToolTip(
            "Send prompt + code from work editor to selected AI"
        )
        self._send_code_btn.clicked.connect(self._on_send_code)
        btn_layout.addWidget(self._send_code_btn)

        self._insert_btn = QPushButton("Insert")
        self._insert_btn.setToolTip("Insert code from last AI response into editor")
        self._insert_btn.setEnabled(False)
        self._insert_btn.clicked.connect(self._on_insert_code)
        btn_layout.addWidget(self._insert_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear conversation history for the selected AI")
        self._clear_btn.clicked.connect(self._on_clear_history)
        btn_layout.addWidget(self._clear_btn)

        btn_layout.addStretch()
        layout.addWidget(btn_row, stretch=0)

    # ==================================================================
    # Event filter (Enter to send, Shift+Enter for newline)
    # ==================================================================

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._prompt_input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    # ==================================================================
    # Public API (called by MainWindow)
    # ==================================================================

    def set_api_keys(
        self, gemini_key: str, gpt_key: str, claude_key: str = ""
    ) -> None:
        """Initialize or update API clients."""
        if gemini_key:
            self._gemini_client = GeminiClient(gemini_key)
        if gpt_key:
            self._gpt_client = GPTClient(gpt_key)
        if claude_key:
            self._claude_client = ClaudeClient(claude_key)

    def set_session_logger(self, logger: SessionLogger) -> None:
        self._session_logger = logger

    def set_code_context(self, code: str) -> None:
        """Receive code from the work editor (called by MainWindow signal handler)."""
        self._pending_code = code
        if self._send_with_code:
            self._send_with_code = False
            self._dispatch()

    # ==================================================================
    # Actions
    # ==================================================================

    def _on_send(self) -> None:
        """Send prompt (no code context) to selected AI."""
        self._pending_code = ""
        self._send_with_code = False
        self._dispatch()

    def _on_send_code(self) -> None:
        """Request code context, then send once it arrives."""
        self._send_with_code = True
        self.request_code_context.emit()

    def _dispatch(self) -> None:
        """Gather inputs and dispatch to the selected API client."""
        prompt = self._prompt_input.toPlainText().strip()
        if not prompt:
            return

        persona = self._current_persona()
        client = self._current_client()

        if client is None:
            self._append_system_message(
                f"No API key set for {persona}. Use the API Keys dialog to configure it."
            )
            return

        attachments = self._attachment_bar.get_attachments()
        attachment_names = self._attachment_bar.get_filenames()
        code = self._pending_code

        # Show user message in chat
        display_parts = []
        if code:
            display_parts.append(f"[Code attached: {len(code)} chars]")
        if attachment_names:
            display_parts.append(f"[Files: {', '.join(attachment_names)}]")
        display_parts.append(prompt)
        self._append_user_message(persona, "\n".join(display_parts))

        # Log
        if self._session_logger:
            self._session_logger.log_message(
                persona, "user", prompt, attachment_names or None
            )

        # Build the assembled user content to store in history
        history_parts: list[str] = []
        if code:
            history_parts.append(f"Here is the code I'm working with:\n```\n{code}\n```")
        if attachments:
            for att in attachments:
                history_parts.append(
                    f"Attached file '{att['filename']}' ({att['mime_type']}):\n"
                    f"```\n{att['content']}\n```"
                )
        history_parts.append(prompt)
        user_content = "\n\n".join(history_parts)

        # Dispatch with prior history
        prior_history = self._history.get(persona, [])
        worker = client.send(
            prompt, code, attachments if attachments else None,
            history=list(prior_history),
        )
        worker.finished.connect(self._on_response)
        worker.errored.connect(self._on_error)
        self._current_worker = worker

        # Record user turn in history after dispatching
        self._history.setdefault(persona, []).append(
            {"role": "user", "content": user_content}
        )
        self._pending_persona = persona

        # UI state
        self._send_btn.setEnabled(False)
        self._send_code_btn.setEnabled(False)
        self._prompt_input.clear()
        self._pending_code = ""
        self.ai_request_started.emit()

    def _on_response(self, text: str) -> None:
        """Display AI response, log it, and record it in conversation history."""
        persona = self._pending_persona or self._current_persona()
        self._last_response_text = text
        self._append_ai_response(persona, text)

        if self._session_logger:
            self._session_logger.log_message(persona, "assistant", text)

        self._history.setdefault(persona, []).append(
            {"role": "assistant", "content": text}
        )
        self._pending_persona = ""

        self._send_btn.setEnabled(True)
        self._send_code_btn.setEnabled(True)
        self._insert_btn.setEnabled(True)
        self._current_worker = None
        self.ai_request_finished.emit()

    def _on_clear_history(self) -> None:
        """Clear the conversation history for the currently selected AI."""
        persona = self._current_persona()
        self._history.pop(persona, None)
        self._append_system_message(f"Conversation history cleared for {persona}.")

    def _on_insert_code(self) -> None:
        """Extract code blocks from last response and emit for insertion."""
        blocks = self._extract_code_blocks(self._last_response_text)
        if not blocks:
            self._append_system_message("No code blocks found in last response.")
            return
        if len(blocks) == 1:
            self.insert_code_requested.emit(blocks[0])
        else:
            picker = CodeBlockPicker(blocks, parent=self)
            if picker.exec() == QDialog.DialogCode.Accepted:
                code = picker.selected_code()
                if code:
                    self.insert_code_requested.emit(code)

    @staticmethod
    def _extract_code_blocks(text: str) -> list[str]:
        """Extract all fenced code blocks from markdown text."""
        return re.findall(r"```(?:\w+)?\n?(.*?)```", text, re.DOTALL)

    def _on_error(self, error_msg: str) -> None:
        """Display error in chat."""
        self._append_system_message(f"Error: {error_msg}")
        self._send_btn.setEnabled(True)
        self._send_code_btn.setEnabled(True)
        self._current_worker = None
        self.ai_request_finished.emit()

    # ==================================================================
    # Chat display helpers
    # ==================================================================

    def _current_persona(self) -> str:
        selected = self._ai_selector.currentText()
        return f"@{selected}"

    def _current_client(self) -> GeminiClient | GPTClient | ClaudeClient | None:
        selected = self._ai_selector.currentText()
        if selected == "Gemini":
            return self._gemini_client
        if selected == "Claude":
            return self._claude_client
        return self._gpt_client

    def _append_user_message(self, persona: str, text: str) -> None:
        color = _PERSONA_COLORS.get(persona, "#888888")
        ts = datetime.now().strftime("%H:%M:%S")
        html = (
            f'<div style="margin: 6px 0;">'
            f'<span style="color: gray; font-size: 11px;">{ts}</span> '
            f'<span style="color: {color}; font-weight: bold;">{persona}</span> '
            f'<span style="color: #888;">You:</span><br>'
            f'<span>{_escape_html(text)}</span>'
            f'</div>'
        )
        self._chat.append(html)

    def _append_ai_response(self, persona: str, text: str) -> None:
        color = _PERSONA_COLORS.get(persona, "#888888")
        ts = datetime.now().strftime("%H:%M:%S")
        formatted = self._format_code_blocks(text)
        html = (
            f'<div style="margin: 6px 0;">'
            f'<span style="color: gray; font-size: 11px;">{ts}</span> '
            f'<span style="color: {color}; font-weight: bold;">{persona}</span>:<br>'
            f'{formatted}'
            f'</div>'
        )
        self._chat.append(html)

    def _append_system_message(self, text: str) -> None:
        html = (
            f'<div style="margin: 6px 0; color: #CC6666; font-style: italic;">'
            f'{_escape_html(text)}'
            f'</div>'
        )
        self._chat.append(html)

    @staticmethod
    def _format_code_blocks(text: str) -> str:
        """Convert markdown ```...``` blocks to HTML <pre><code>."""
        def _replace_block(match: re.Match) -> str:
            code = _escape_html(match.group(1))
            return (
                f'<pre style="background-color: #1E1E1E; color: #D4D4D4; '
                f'padding: 8px; border-radius: 4px; font-family: monospace; '
                f'font-size: 12px; white-space: pre-wrap;">'
                f'<code>{code}</code></pre>'
            )

        # Replace fenced code blocks (with optional language tag)
        result = re.sub(
            r"```(?:\w+)?\n?(.*?)```",
            _replace_block,
            text,
            flags=re.DOTALL,
        )
        # Escape remaining text (outside code blocks is already handled)
        # Replace inline code `...`
        result = re.sub(
            r"`([^`]+)`",
            lambda m: (
                f'<code style="background-color: #2A2A2A; padding: 1px 4px; '
                f'border-radius: 3px; font-family: monospace;">'
                f'{_escape_html(m.group(1))}</code>'
            ),
            result,
        )
        # Convert newlines to <br> for non-code parts
        result = result.replace("\n", "<br>")
        return result


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
