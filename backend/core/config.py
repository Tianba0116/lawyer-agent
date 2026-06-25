import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # --- Embedding ---
    embed_provider: str = "huggingface"
    hf_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ollama_embed_model: str = "nomic-embed-text"

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # --- Retrieval ---
    top_k: int = 5

    # --- Paths ---
    pdfs_dir: str = "pdfs"
    faiss_db_path: str = "vectorstore/db_faiss"
    report_path: str = "AI_Lawyer_Report.pdf"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            embed_provider=os.getenv("EMBED_PROVIDER", "huggingface"),
            hf_embed_model=os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
            top_k=int(os.getenv("TOP_K", "5")),
        )


config = Config.from_env()
