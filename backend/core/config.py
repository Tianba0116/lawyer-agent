import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # --- Embedding ---
    embed_provider: str = "huggingface"
    hf_embed_model: str = "BAAI/bge-small-zh-v1.5"
    ollama_embed_model: str = "nomic-embed-text"

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # --- Retrieval ---
    top_k: int = 5

    # --- OCR ---
    ocr_output_dir: str = "ocr_output"
    ocr_dpi: int = 150                       # 扫描精度（150 通用性好，速度是 200 的 2x）
    ocr_sample_pages: int = 3
    ocr_table_recognition: bool = True        # 表格识别（关闭可提速 ~50%）
    ocr_mode: str = "accurate"               # "accurate" | "fast"（fast 模式关闭表格识别 + 低 DPI）

    # --- Paths ---
    pdfs_dir: str = "pdfs"
    faiss_db_path: str = "vectorstore/db_faiss"
    report_path: str = "AI_Lawyer_Report.pdf"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            embed_provider=os.getenv("EMBED_PROVIDER", "huggingface"),
            hf_embed_model=os.getenv("HF_EMBED_MODEL", "BAAI/bge-small-zh-v1.5"),
            ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
            top_k=int(os.getenv("TOP_K", "5")),
            ocr_output_dir=os.getenv("OCR_OUTPUT_DIR", "ocr_output"),
            ocr_dpi=int(os.getenv("OCR_DPI", "150")),
            ocr_sample_pages=int(os.getenv("OCR_SAMPLE_PAGES", "3")),
            ocr_table_recognition=os.getenv("OCR_TABLE_RECOGNITION", "1") not in ("0", "false", "no"),
            ocr_mode=os.getenv("OCR_MODE", "accurate"),
        )


config = Config.from_env()
