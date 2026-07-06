"""PDF 类型检测 + PP-StructureV3 扫描件 OCR 处理。

使用 PaddleOCR PP-StructureV3 进行布局分析、文字识别、表格抽取，
输出结构化 Markdown + 元数据 + 表格文件。

注意：重型依赖（fitz/numpy/PIL/paddleocr）均为函数内延迟导入，
确保不安装 OCR 依赖时项目其余功能正常运行。
"""
import io
import json
import time
from pathlib import Path

from core.config import config
from ocr.metadata import _TEXT_LABELS, _SKIP_LABELS, extract_metadata
from ocr.utils import html_table_to_md

# ── 模块级 OCR 引擎懒加载 ──────────────────────────────────────────
_ocr_engine = None
_device = None  # "mps" | "cuda" | "cpu"


def _detect_device() -> str:
    """自动检测最佳计算设备（跨平台：Apple MPS → NVIDIA CUDA → CPU）。"""
    try:
        import paddle
        try:
            if paddle.device.is_compiled_with_mps():
                paddle.set_device("mps")
                return "mps"
        except Exception:
            pass
        try:
            if paddle.device.is_compiled_with_cuda():
                paddle.set_device("gpu")
                return "cuda"
        except Exception:
            pass
    except Exception:
        pass
    return "cpu"


def _get_ocr_engine():
    """懒加载 PP-StructureV3，避免每次调用都重新初始化模型。

    自动检测可用 GPU（MPS/CUDA），不可用时回退 CPU。
    根据 config.ocr_mode 决定是否启用表格识别。
    """
    global _ocr_engine, _device
    if _ocr_engine is None:
        try:
            from paddleocr import PPStructureV3
        except ImportError:
            raise RuntimeError(
                "PaddleOCR 未安装。请运行: pip install paddlepaddle==3.2.2 paddleocr paddlex[ocr] pymupdf"
            )

        _device = _detect_device()

        use_table = config.ocr_table_recognition
        if config.ocr_mode == "fast":
            use_table = False

        print(f"Loading PP-StructureV3 (device={_device}, tables={use_table}, dpi={config.ocr_dpi}) ...")
        start = time.time()
        _ocr_engine = PPStructureV3(
            lang="ch",
            use_table_recognition=use_table,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        print(f"PP-StructureV3 ready ({time.time() - start:.1f}s)")
    return _ocr_engine


# ── PDF 类型检测 ────────────────────────────────────────────────────


def detect_pdf_type(pdf_path: str, sample_pages: int = None) -> str:
    """检测 PDF 是文本型还是扫描件。

    用 PyMuPDF 提取前 N 页的文字，三重判断：
    1. 字符数太少（< 50） → 扫描件（无文字层）
    2. 空白符比例过高（> 15%） → 扫描件（嵌入了碎片化的噪音文字层）
    3. 否则 → 文本型

    Args:
        pdf_path: PDF 文件路径
        sample_pages: 采样页数，默认使用 config.ocr_sample_pages

    Returns:
        "text" 或 "scanned"
    """
    import re
    import fitz  # 延迟导入

    if sample_pages is None:
        sample_pages = config.ocr_sample_pages

    # 防御：sample_pages 为 0 时取 1
    if sample_pages < 1:
        sample_pages = 1

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count

    if total_pages == 0:
        doc.close()
        return "text"

    pages_to_check = min(sample_pages, total_pages)
    total_chars = 0
    total_whitespace = 0

    for i in range(pages_to_check):
        text = doc[i].get_text()
        total_chars += len(text)
        total_whitespace += len(re.findall(r'\s', text))

    doc.close()

    avg_chars = total_chars / pages_to_check

    # 规则1: 几乎没文字 → 扫描件
    if avg_chars < 50:
        return "scanned"

    # 规则2: 文字不少但空白符比例过高 → 噪音文字层 → 扫描件
    if total_chars > 0:
        ws_ratio = total_whitespace / total_chars
        if ws_ratio > 0.15:
            return "scanned"

    return "text"


# ── 扫描件 OCR ──────────────────────────────────────────────────────


def process_scanned_pdf(pdf_path: str, output_dir: Path) -> dict:
    """对扫描件 PDF 执行完整的 OCR 结构化提取。

    Args:
        pdf_path: 扫描件 PDF 文件路径
        output_dir: 输出目录（如 ocr_output/判决书/）

    Returns:
        dict:
            - md_path: 生成的 document.md 路径
            - metadata: 自动抽取的结构化元数据
            - table_count: 发现的表格数量
            - pages: 总页数
            - pdf_type: "scanned"
    """
    import fitz  # 延迟导入
    import numpy as np
    from PIL import Image

    engine = _get_ocr_engine()
    doc = fitz.open(pdf_path)
    total = doc.page_count
    dpi = config.ocr_dpi

    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    all_text_sections = []
    all_tables = []

    print(f"OCR processing: {pdf_path} ({total} pages, {dpi} DPI)")

    for i in range(total):
        page_start = time.time()
        print(f"  [{i+1}/{total}] Page {i+1}...", end=" ", flush=True)

        page = doc[i]
        try:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            img_array = np.array(img_pil)[:, :, ::-1]  # RGB → BGR（确保3通道，防止RGBA导致通道错位）

            raw_result = engine.predict(img_array)
            if not raw_result:
                print(f"SKIP (empty result)")
                continue
            page_result = raw_result[0]
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # --- 处理布局区块 ---
        layout_blocks = page_result.get("parsing_res_list", [])
        table_idx = 0
        region_texts_seen = set()

        for block in layout_blocks:
            label = getattr(block, "label", "text")
            content = getattr(block, "content", "").strip()

            if not content:
                continue

            if label == "table":
                # PP-StructureV3 已在 content 中提供 HTML 表格
                md_table = html_table_to_md(content)
                table_name = f"page{i+1}_table{table_idx}"

                (tables_dir / f"{table_name}.html").write_text(content, encoding="utf-8")
                if md_table:
                    (tables_dir / f"{table_name}.md").write_text(md_table, encoding="utf-8")

                all_tables.append((i + 1, table_name, md_table or content))
                all_text_sections.append(
                    (i + 1, "table", f"[Table: {table_name}]\n{md_table or content}")
                )
                table_idx += 1

            elif label in _TEXT_LABELS:
                if content in region_texts_seen:
                    continue
                region_texts_seen.add(content)
                if all_text_sections and all_text_sections[-1][2] == content:
                    continue
                all_text_sections.append((i + 1, label, content))

            elif label not in _SKIP_LABELS:
                # 未知标签 — 看起来像文字就保留
                if content and len(content) > 2:
                    if all_text_sections and all_text_sections[-1][2] == content:
                        continue
                    all_text_sections.append((i + 1, label, content))

        elapsed = time.time() - page_start
        print(f"OK ({len(layout_blocks)} blocks, {table_idx} tables, {elapsed:.1f}s)")

    doc.close()

    # --- 跨页文本连续段落合并 ---
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

    # --- 抽取元数据 ---
    metadata = extract_metadata(all_text_sections)

    # --- 构建 document.md ---
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
                    doc_lines.append(
                        "| " + " | ".join(labels_map.get(f, f) for f in ordered_fields) + " |"
                    )
                    doc_lines.append(
                        "| " + " | ".join(["---"] * len(ordered_fields)) + " |"
                    )
                    for p in val:
                        doc_lines.append(
                            "| " + " | ".join(str(p.get(f, "")) for f in ordered_fields) + " |"
                        )
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
            # 将表格内容直接嵌入文档，而非仅引用外部文件
            # text 格式: "[Table: pageX_tableY]\n| col1 | col2 |\n| ... |"
            table_content = text
            if table_content.startswith("[Table:"):
                # 去掉 [Table: xxx] 引用前缀，保留纯 Markdown 表格
                table_content = table_content.split("]\n", 1)[-1] if "]\n" in table_content else table_content
            doc_lines.append(f"#### 表格")
            doc_lines.append("")
            doc_lines.append(table_content)
            doc_lines.append("")
        else:
            doc_lines.append(text)
            doc_lines.append("")

    md_path = output_dir / "document.md"
    md_path.write_text("\n".join(doc_lines), encoding="utf-8")

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OCR done: {md_path} | tables: {len(all_tables)} | pages: {total}")

    return {
        "md_path": str(md_path),
        "metadata": metadata,
        "table_count": len(all_tables),
        "pages": total,
        "pdf_type": "scanned",
    }
