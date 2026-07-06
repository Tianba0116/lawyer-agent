"""HTML 表格 → Markdown 转换工具"""
from html.parser import HTMLParser


class _TableHTMLParser(HTMLParser):
    """从 <td>/<th> 元素中提取文本，保持行列结构。"""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._current_row = []
        self._in_td = False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_td = True

    def handle_endtag(self, tag):
        if tag == "tr" and self._current_row:
            self.rows.append(self._current_row)
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_td = False

    def handle_data(self, data):
        if self._in_td:
            self._current_row.append(data.strip())


def html_table_to_md(html_str: str) -> str:
    """将简单 HTML <table> 转为 Markdown 表格字符串。"""
    parser = _TableHTMLParser()
    parser.feed(html_str)
    if not parser.rows:
        return ""

    max_cols = max(len(r) for r in parser.rows)
    norm = []
    for r in parser.rows:
        if len(r) < max_cols:
            r += [""] * (max_cols - len(r))
        norm.append(r)

    lines = []
    for row in norm:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
