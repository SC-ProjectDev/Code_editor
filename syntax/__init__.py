# codeeditor/syntax/__init__.py
from codeeditor.syntax.python_highlighter import PythonHighlighter
from codeeditor.syntax.javascript_highlighter import JavaScriptHighlighter
from codeeditor.syntax.highlighter_factory import get_highlighter_for_file, detect_language

__all__ = [
    "PythonHighlighter",
    "JavaScriptHighlighter",
    "get_highlighter_for_file",
    "detect_language",
]
