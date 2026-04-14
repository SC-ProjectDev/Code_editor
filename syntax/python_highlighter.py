# codeeditor/syntax/python_highlighter.py
# Python syntax highlighting for QPlainTextEdit / CodeEditor.

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    """Regex-based Python syntax highlighter."""

    def __init__(self, document):
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # ── Keywords ───────────────────────────────────────
        kw_fmt = _fmt("#4D7CFE", bold=True)
        keywords = (
            "and|as|assert|async|await|break|class|continue|def|del|elif|else|"
            "except|False|finally|for|from|global|if|import|in|is|lambda|None|"
            "nonlocal|not|or|pass|raise|return|True|try|while|with|yield"
        )
        self.rules.append((QRegularExpression(rf"\b(?:{keywords})\b"), kw_fmt))

        # ── Builtins ──────────────────────────────────────
        bi_fmt = _fmt("#8A2BE2")
        builtins = (
            "abs|all|any|bin|bool|bytes|callable|chr|classmethod|complex|"
            "delattr|dict|dir|divmod|enumerate|eval|exec|filter|float|format|"
            "frozenset|getattr|globals|hasattr|hash|help|hex|id|input|int|"
            "isinstance|issubclass|iter|len|list|locals|map|max|memoryview|"
            "min|next|object|oct|open|ord|pow|print|property|range|repr|"
            "reversed|round|set|setattr|slice|sorted|staticmethod|str|sum|"
            "super|tuple|type|vars|zip"
        )
        self.rules.append((QRegularExpression(rf"\b(?:{builtins})\b"), bi_fmt))

        # ── Decorators ────────────────────────────────────
        dec_fmt = _fmt("#D19A66", italic=True)
        self.rules.append((QRegularExpression(r"@\w+"), dec_fmt))

        # ── Self / cls ────────────────────────────────────
        self_fmt = _fmt("#E06C75", italic=True)
        self.rules.append((QRegularExpression(r"\bself\b"), self_fmt))
        self.rules.append((QRegularExpression(r"\bcls\b"), self_fmt))

        # ── Numbers ───────────────────────────────────────
        num_fmt = _fmt("#E879F9")
        self.rules.append((
            QRegularExpression(r"\b(0[xXoObB])?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\b"),
            num_fmt,
        ))

        # ── Strings (single & double quotes) ─────────────
        str_fmt = _fmt("#16A34A")
        # Triple-quoted strings (must come before single-quote rules)
        self.rules.append((QRegularExpression(r'""".*?"""'), str_fmt))
        self.rules.append((QRegularExpression(r"'''.*?'''"), str_fmt))
        # Single/double quoted strings
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        # ── f-string prefix ───────────────────────────────
        fstr_fmt = _fmt("#16A34A", bold=True)
        self.rules.append((QRegularExpression(r'\bf"[^"\\]*(\\.[^"\\]*)*"'), fstr_fmt))
        self.rules.append((QRegularExpression(r"\bf'[^'\\]*(\\.[^'\\]*)*'"), fstr_fmt))

        # ── Comments (must be last — overrides everything) ─
        cmt_fmt = _fmt("#6A9955", italic=True)
        self.rules.append((QRegularExpression(r"#.*"), cmt_fmt))

    def highlightBlock(self, text: str):
        for regex, fmt in self.rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
