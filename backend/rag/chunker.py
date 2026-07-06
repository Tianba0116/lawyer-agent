from pathlib import Path

from langchain_community.document_loaders import PDFPlumberLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.config import config
from ocr import detect_pdf_type, process_scanned_pdf


def load_pdf(file_path: str) -> tuple[list, dict | None]:
    """加载 PDF 并提取为 LangChain Documents。

    自动检测 PDF 类型：
    - 文本型 PDF：使用 pdfplumber 提取嵌入文字层
    - 扫描件 PDF：使用 PP-StructureV3 进行 OCR 结构化提取

    Args:
        file_path: PDF 文件路径

    Returns:
        (documents, ocr_meta) 元组：
        - 文本型 PDF: ocr_meta = None
        - 扫描件 PDF: ocr_meta = {"pdf_type": "scanned", "pages": N, ...}
    """
    pdf_type = detect_pdf_type(file_path)

    if pdf_type == "scanned":
        output_dir = Path(config.ocr_output_dir) / Path(file_path).stem
        ocr_result = process_scanned_pdf(file_path, output_dir)

        # 直接读 OCR 产出的 Markdown，避免 TextLoader 编码风险
        md_path = Path(ocr_result["md_path"])
        content = md_path.read_text(encoding="utf-8")
        doc = Document(
            page_content=content,
            metadata={"source": Path(file_path).name, "pdf_type": "scanned"}
        )
        return [doc], ocr_result

    # 文本型 PDF：走原有 pdfplumber 逻辑
    loader = PDFPlumberLoader(file_path)
    docs = loader.load()
    for d in docs:
        d.metadata["pdf_type"] = "text"
    return docs, None


def chunk_documents(documents, file_name: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        add_start_index=True,
    )
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["source"] = file_name
    return chunks
