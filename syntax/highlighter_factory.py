# codeeditor/syntax/highlighter_factory.py
# Auto-assign the correct syntax highlighter based on file extension.

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtWidgets import QPlainTextEdit

from codeeditor.config import PYTHON_EXTENSIONS, JAVASCRIPT_EXTENSIONS
from codeeditor.syntax.python_highlighter import PythonHighlighter
from codeeditor.syntax.javascript_highlighter import JavaScriptHighlighter


def get_highlighter_for_file(
    file_path: str | Path | None,
    editor: QPlainTextEdit,
) -> Optional[QSyntaxHighlighter]:
    """
    Given a file path and an editor, return the appropriate syntax highlighter.
    Returns None if no highlighter matches the file extension.
    """
    if file_path is None:
        return None

    ext = Path(file_path).suffix.lower()

    if ext in PYTHON_EXTENSIONS:
        return PythonHighlighter(editor.document())
    elif ext in JAVASCRIPT_EXTENSIONS:
        return JavaScriptHighlighter(editor.document())

    # No highlighting for unrecognized files
    return None


def detect_language(file_path: str | Path | None) -> str:
    """Return a language identifier string for the given file extension."""
    if file_path is None:
        return "plain"
    ext = Path(file_path).suffix.lower()
    if ext in PYTHON_EXTENSIONS:
        return "python"
    elif ext in JAVASCRIPT_EXTENSIONS:
        return "javascript"
    return "plain"
