"""
结构化PDF提取工具 - 知识库就绪输出
使用 PP-StructureV3 (layout + OCR + table) 一站式提取
输出: output_kb/metadata.json / document.md / tables/
"""
import fitz
import numpy as np
from PIL import Image
import io
import sys
import json
import re
import statistics
from pathlib import Path
from html.parser import HTMLParser
from paddleocr import PPStructureV3
import time

sys.stdout.reconfigure(encoding='utf-8')


# ═══════════════════════════════════ Helpers ═══════════════════════════════════

class _TableHTMLParser(HTMLParser):
    """Pull text from <td> elements inside <tr>, preserving row/col structure."""

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


def _html_table_to_md(html_str):
    """Convert a simple HTML <table> to a Markdown table string."""
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


# Labels that carry readable text content (not structural noise)
_TEXT_LABELS = frozenset({
    "title", "text", "paragraph", "figure_title", "header", "footer",
    "reference", "list", "abstract", "content", "formula",
})

# Labels to skip outright
_SKIP_LABELS = frozenset({
    "number", "seal", "figure", "chart", "equation", "footnote",
})


def _extract_metadata(sections):
    """Auto-detect structured metadata from document text.

    Uses generic patterns (key:value, Chinese dates, person records) that work
    across common Chinese formal documents without per-template configuration.
    """
    meta = {}
    combined = "\n".join([t for _, _, t in sections])

    # --- 1. Generic key:value detection ---
    kv_pattern = re.compile(
        r"(?:^|\n)\s*"
        r"([一-龥][一-龥A-Za-z0-9/\s]{0,18}[一-龥A-Za-z0-9/)]"  # key
        r")\s*[：:]\s*"
        r"([^\n]{1,120})"  # value (single line)
    )
    seen_keys = set()
    for match in kv_pattern.finditer(combined):
        key = match.group(1).strip()
        value = match.group(2).strip()
        if len(key) < 2 or key in seen_keys:
            continue
        if any(p in key for p in ("。", "，", "、", "；", "的", "是", "在", "和", "与")):
            continue
        seen_keys.add(key)
        meta[key] = value

    # --- 2. Document type detection ---
    doc_type_patterns = [
        (r"([一-龥]{2,10}(?:判决书|裁定书|决定书|起诉书|通知书|申报书|申请书|报告书|意见书|批复))", "doc_type"),
    ]
    for pattern, label in doc_type_patterns:
        m = re.search(pattern, combined)
        if m:
            meta[label] = m.group(1)
            break

    # --- 3. Generic date extraction ---
    date_pattern = re.compile(
        r"((?:20|19)\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)"
    )
    dates = date_pattern.findall(combined)
    if dates:
        meta["date"] = dates[0].replace(" ", "")

    # --- 4. Generic person extraction ---
    person_pattern = re.compile(
        r"([一-龥]{2,4})\s*[男女]\s*(\d{2,3})\s*(\d{4}级|博士|硕士|本科)?"
    )
    participants = []
    seen_names = set()
    for match in person_pattern.finditer(combined):
        name = match.group(1)
        if name in seen_names:
            continue
        if len(name) == 2 and name in ("男女", "性别", "年龄", "姓名", "年级", "联系电话"):
            continue
        seen_names.add(name)
        gender = "男" if "男" in match.group(0) else "女"
        info = {"name": name, "gender": gender}
        age_str = match.group(2)
        if age_str:
            info["age"] = int(age_str)
        grade = match.group(3)
        if grade:
            info["grade"] = grade
        participants.append(info)

    if participants:
        meta["participants"] = participants

    # --- 5. Rename generic keys to standard names for convenience ---
    KEY_ALIASES = {
        "申请项目名称": "title",
        "项目名称": "title",
        "申请者姓名": "applicant",
        "申请人": "applicant",
        "所在学院": "college",
        "学科代码及名称": "discipline_full",
        "拟申请经费额度": "funding",
        "项目起止年限": "duration",
        "案号": "case_number",
        "案由": "case_cause",
        "被告人": "defendant",
        "公诉机关": "prosecutor",
        "审判长": "judge",
        "法院": "court",
    }
    for raw_key, std_key in KEY_ALIASES.items():
        if raw_key in meta:
            meta[std_key] = meta.pop(raw_key)

    return meta


# ═══════════════════════════════════ Main ═════════════════════════════════════

PDF_PATH = "input.pdf"
OUTPUT_DIR = Path("output_kb")
DPI = 200


def main():
    print("=" * 60)
    print("Loading PP-StructureV3 (layout + OCR + table) ...")
    start = time.time()

    engine = PPStructureV3(
        lang="ch",
        use_table_recognition=True,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    print(f"Init done: {time.time() - start:.1f}s")

    doc = fitz.open(PDF_PATH)
    total = doc.page_count
    print(f"PDF: {PDF_PATH} | Pages: {total}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    tables_dir = OUTPUT_DIR / "tables"
    tables_dir.mkdir(exist_ok=True)

    all_text_sections = []
    all_tables = []

    for i in range(total):
        page_start = time.time()
        print(f"[{i+1}/{total}] Page {i+1}...", end=" ", flush=True)

        page = doc[i]
        mat = fitz.Matrix(DPI / 72, DPI / 72)
        pix = page.get_pixmap(matrix=mat)
        img_pil = Image.open(io.BytesIO(pix.tobytes("png")))
        img_array = np.array(img_pil)[:, :, ::-1]

        page_result = engine.predict(img_array)[0]

        # --- Process layout blocks ---
        layout_blocks = page_result.get("parsing_res_list", [])
        table_idx = 0
        region_texts_seen = set()

        for block in layout_blocks:
            label = getattr(block, "label", "text")
            content = getattr(block, "content", "").strip()

            if not content:
                continue

            if label == "table":
                # PPStructureV3 already has HTML table in content
                md_table = _html_table_to_md(content)
                table_name = f"page{i+1}_table{table_idx}"

                (tables_dir / f"{table_name}.html").write_text(content, encoding="utf-8")
                if md_table:
                    (tables_dir / f"{table_name}.md").write_text(md_table, encoding="utf-8")

                all_tables.append((i + 1, table_name, md_table or content))
                all_text_sections.append((i + 1, "table", f"[Table: {table_name}]\n{md_table or content}"))
                table_idx += 1

            elif label in _TEXT_LABELS:
                if content in region_texts_seen:
                    continue
                region_texts_seen.add(content)
                if all_text_sections and all_text_sections[-1][2] == content:
                    continue
                all_text_sections.append((i + 1, label, content))

            elif label not in _SKIP_LABELS:
                # Unknown label – treat as text if it looks readable
                if content and len(content) > 2:
                    if all_text_sections and all_text_sections[-1][2] == content:
                        continue
                    all_text_sections.append((i + 1, label, content))

        elapsed = time.time() - page_start
        print(f"OK ({len(layout_blocks)} blocks, {table_idx} tables, {elapsed:.1f}s)")

    doc.close()

    # --- Merge cross-page text continuations ---
    SENTENCE_END = frozenset("。！？…）)]」』\"")
    merged = []
    skip_next = False
    for idx, (page_num, rtype, text) in enumerate(all_text_sections):
        if skip_next:
            skip_next = False
            continue
        if rtype == "text" and idx + 1 < len(all_text_sections):
            next_page, next_rtype, next_text = all_text_sections[idx + 1]
            if next_page == page_num + 1 and next_rtype == "text":
                if text and text[-1] not in SENTENCE_END:
                    merged.append((page_num, rtype, text.rstrip() + next_text))
                    skip_next = True
                    continue
        merged.append((page_num, rtype, text))
    all_text_sections = merged

    metadata = _extract_metadata(all_text_sections)

    # --- Build document.md ---
    title = metadata.pop("title", None) or metadata.pop("doc_type", None) or "OCR提取结果"
    doc_lines = [f"# {title}", ""]
    if metadata:
        doc_lines.append("## 基本信息")
        doc_lines.append("")
        for key, val in metadata.items():
            if key == "participants" and isinstance(val, list):
                if val:
                    all_fields = set()
                    for p in val:
                        all_fields.update(p.keys())
                    ordered_fields = [f for f in ("name", "gender", "age", "grade") if f in all_fields]
                    ordered_fields += sorted(all_fields - set(ordered_fields))
                    labels_map = {"name": "姓名", "gender": "性别", "age": "年龄", "grade": "年级"}
                    doc_lines.append("### 人员信息")
                    doc_lines.append("")
                    doc_lines.append("| " + " | ".join(labels_map.get(f, f) for f in ordered_fields) + " |")
                    doc_lines.append("| " + " | ".join(["---"] * len(ordered_fields)) + " |")
                    for p in val:
                        doc_lines.append("| " + " | ".join(str(p.get(f, "")) for f in ordered_fields) + " |")
                    doc_lines.append("")
            elif val:
                doc_lines.append(f"- **{key}**: {val}")
        doc_lines.append("")
        doc_lines.append("---")
        doc_lines.append("")

    current_page = 0
    for page_num, rtype, text in all_text_sections:
        if page_num != current_page:
            doc_lines.append(f"## Page {page_num}")
            doc_lines.append("")
            current_page = page_num
        if rtype == "title":
            doc_lines.append(f"### {text.strip()}")
            doc_lines.append("")
        elif rtype == "table":
            ref_name = text.replace("[Table: ", "").split("]")[0] if "[Table:" in text else "unknown"
            doc_lines.append(f"*（表格见 tables/{ref_name}.md）*")
            doc_lines.append("")
        else:
            doc_lines.append(text)
            doc_lines.append("")

    (OUTPUT_DIR / "document.md").write_text("\n".join(doc_lines), encoding="utf-8")
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{'=' * 60}")
    print("Done!")
    print(f"  {OUTPUT_DIR}/document.md   - main content")
    print(f"  {OUTPUT_DIR}/metadata.json - structured metadata")
    print(f"  {OUTPUT_DIR}/tables/       - {len(all_tables)} tables")
    print(f"  Time: {time.time() - start:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
