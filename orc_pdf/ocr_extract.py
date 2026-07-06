"""
扫描PDF OCR提取工具
使用 PaddleOCR 将扫描件PDF转为 Markdown
"""
import fitz
import numpy as np
from PIL import Image
import io
import sys
from paddleocr import PaddleOCR
from pathlib import Path
import time

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = "input.pdf"
OUTPUT_PATH = "output_ocr.md"
DPI = 200

print("=" * 50)
print("Initializing PaddleOCR ...")
start = time.time()

ocr = PaddleOCR(lang="ch")
print(f"Init done: {time.time() - start:.1f}s")

print(f"Opening PDF: {PDF_PATH}")
doc = fitz.open(PDF_PATH)
total = doc.page_count
print(f"Total pages: {total}")

results = []
for i in range(total):
    page_start = time.time()
    print(f"[{i+1}/{total}] Processing page {i+1}...", end=" ", flush=True)

    page = doc[i]
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat)

    img_bytes = pix.tobytes("png")
    img_pil = Image.open(io.BytesIO(img_bytes))
    img_array = np.array(img_pil)[:, :, ::-1]

    ocr_result = ocr.predict(img_array)
    page_text_lines = []

    if ocr_result:
        page_data = ocr_result[0]
        rec_texts = page_data.get("rec_texts", [])
        rec_scores = page_data.get("rec_scores", [])
        for text, score in zip(rec_texts, rec_scores):
            if score > 0.5:
                page_text_lines.append(text)

    page_text = "\n".join(page_text_lines)
    results.append(f"## Page {i+1}\n\n{page_text}\n")
    print(f"OK ({len(page_text_lines)} lines, {time.time() - page_start:.1f}s)")

doc.close()

md_content = f"# OCR提取结果\n\nSource: {PDF_PATH}\nPages: {total}\n\n---\n\n"
md_content += "\n---\n\n".join(results)

Path(OUTPUT_PATH).write_text(md_content, encoding="utf-8")
print(f"\nDone! Output: {OUTPUT_PATH}")
print(f"Total time: {time.time() - start:.1f}s")
print("=" * 50)
