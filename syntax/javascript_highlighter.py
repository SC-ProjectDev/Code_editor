# codeeditor/syntax/javascript_highlighter.py
# JavaScript / TypeScript syntax highlighting for QPlainTextEdit / CodeEditor.

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


class JavaScriptHighlighter(QSyntaxHighlighter):
    """Regex-based JavaScript / TypeScript syntax highlighter."""

    def __init__(self, document):
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # ── Keywords ───────────────────────────────────────
        kw_fmt = _fmt("#4D7CFE", bold=True)
        keywords = (
            "abstract|arguments|async|await|break|case|catch|class|const|"
            "continue|debugger|default|delete|do|else|enum|export|extends|"
            "false|finally|for|from|function|get|if|implements|import|in|"
            "instanceof|interface|let|new|null|of|package|private|protected|"
            "public|return|set|static|super|switch|this|throw|true|try|"
            "typeof|undefined|var|void|while|with|yield"
        )
        self.rules.append((QRegularExpression(rf"\b(?:{keywords})\b"), kw_fmt))

        # ── TypeScript type keywords ──────────────────────
        ts_fmt = _fmt("#4EC9B0", bold=True)
        ts_keywords = (
            "any|boolean|number|string|symbol|never|unknown|void|"
            "type|namespace|declare|readonly|keyof|infer|as|is"
        )
        self.rules.append((QRegularExpression(rf"\b(?:{ts_keywords})\b"), ts_fmt))

        # ── Built-in objects / globals ────────────────────
        bi_fmt = _fmt("#8A2BE2")
        builtins = (
            "Array|Boolean|Date|Error|Function|JSON|Map|Math|Number|Object|"
            "Promise|Proxy|RegExp|Set|String|Symbol|WeakMap|WeakSet|"
            "console|document|globalThis|module|process|require|window|"
            "parseInt|parseFloat|isNaN|isFinite|decodeURI|encodeURI|"
            "decodeURIComponent|encodeURIComponent|setTimeout|setInterval|"
            "clearTimeout|clearInterval|fetch|alert|confirm|prompt"
        )
        self.rules.append((QRegularExpression(rf"\b(?:{builtins})\b"), bi_fmt))

        # ── Arrow functions ───────────────────────────────
        arrow_fmt = _fmt("#C586C0", bold=True)
        self.rules.append((QRegularExpression(r"=>"), arrow_fmt))

        # ── Numbers ───────────────────────────────────────
        num_fmt = _fmt("#E879F9")
        self.rules.append((
            QRegularExpression(
                r"\b(0[xXoObB][\da-fA-F_]+|[0-9][\d_]*(\.[0-9][\d_]*)?([eE][+-]?[\d_]+)?)\b"
            ),
            num_fmt,
        ))

        # ── Template literals (`...`) ─────────────────────
        tmpl_fmt = _fmt("#CE9178")
        self.rules.append((QRegularExpression(r"`[^`\\]*(\\.[^`\\]*)*`"), tmpl_fmt))

        # ── Strings (single & double) ─────────────────────
        str_fmt = _fmt("#16A34A")
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        # ── JSX tags (basic) ──────────────────────────────
        jsx_fmt = _fmt("#569CD6")
        self.rules.append((QRegularExpression(r"</?[A-Z][A-Za-z0-9.]*"), jsx_fmt))
        self.rules.append((QRegularExpression(r"/>"), jsx_fmt))

        # ── Regex literals ────────────────────────────────
        regex_fmt = _fmt("#D16969")
        self.rules.append((
            QRegularExpression(r"(?<=[=(:,;\[!&|?{])\s*/[^/\*][^/]*/[gimsuy]*"),
            regex_fmt,
        ))

        # ── Single-line comment (//) ──────────────────────
        cmt_fmt = _fmt("#6A9955", italic=True)
        self.rules.append((QRegularExpression(r"//.*"), cmt_fmt))

        # ── Multi-line comment (/* ... */ on a single line) ─
        block_cmt_fmt = _fmt("#6A9955", italic=True)
        self.rules.append((QRegularExpression(r"/\*.*?\*/"), block_cmt_fmt))

    def highlightBlock(self, text: str):
        for regex, fmt in self.rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
