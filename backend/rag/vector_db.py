import os
import json
from datetime import datetime
from langchain_ollama import OllamaEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from core.config import config
from rag.chunker import load_pdf, chunk_documents


_faiss_db = None
_embedding_model = None

DOCS_REGISTRY = "vectorstore/docs.json"


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        if config.embed_provider == "ollama":
            _embedding_model = OllamaEmbeddings(model=config.ollama_embed_model)
        else:
            try:
                _embedding_model = HuggingFaceEmbeddings(
                    model_name=config.hf_embed_model,
                    model_kwargs={"local_files_only": True},  # 离线模式，国内网络不连 HuggingFace
                )
            except Exception as e:
                raise RuntimeError(
                    f"无法加载嵌入模型 '{config.hf_embed_model}'。\n"
                    f"请确保模型已下载到本地缓存，或设置 HF_ENDPOINT 环境变量。\n"
                    f"原始错误: {e}"
                )
    return _embedding_model


def _load_registry() -> dict:
    if os.path.exists(DOCS_REGISTRY):
        with open(DOCS_REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_registry(reg: dict):
    os.makedirs(os.path.dirname(DOCS_REGISTRY), exist_ok=True)
    with open(DOCS_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def index_pdf(file_path: str):
    global _faiss_db
    file_name = os.path.basename(file_path)
    documents, ocr_meta = load_pdf(file_path)
    chunks = chunk_documents(documents, file_name)
    embedding = _get_embedding_model()

    new_db = FAISS.from_documents(chunks, embedding)

    if _faiss_db is None:
        try:
            _faiss_db = FAISS.load_local(config.faiss_db_path, embedding, allow_dangerous_deserialization=True)
        except Exception:
            _faiss_db = None

    if _faiss_db is not None:
        _faiss_db.merge_from(new_db)
    else:
        _faiss_db = new_db

    _faiss_db.save_local(config.faiss_db_path)

    reg = _load_registry()
    reg[file_name] = {
        "chunks": len(chunks),
        "size": os.path.getsize(file_path),
        "uploaded_at": datetime.now().isoformat(),
        "pdf_type": ocr_meta["pdf_type"] if ocr_meta else "text",
    }
    _save_registry(reg)


def remove_document(file_name: str):
    global _faiss_db
    reg = _load_registry()
    if file_name not in reg:
        return False

    del reg[file_name]
    _save_registry(reg)

    pdf_path = os.path.join(config.pdfs_dir, file_name)
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    # Rebuild index from remaining documents
    _faiss_db = None
    if os.path.exists(config.faiss_db_path):
        import shutil
        shutil.rmtree(config.faiss_db_path, ignore_errors=True)

    embedding = _get_embedding_model()
    for fname in reg:
        fpath = os.path.join(config.pdfs_dir, fname)
        if os.path.exists(fpath):
            docs, _ = load_pdf(fpath)  # 解包 tuple
            chunks = chunk_documents(docs, fname)
            new_db = FAISS.from_documents(chunks, embedding)
            if _faiss_db is None:
                _faiss_db = new_db
            else:
                _faiss_db.merge_from(new_db)

    if _faiss_db is not None:
        _faiss_db.save_local(config.faiss_db_path)

    return True


def list_documents() -> list[dict]:
    reg = _load_registry()
    result = []
    for name, info in reg.items():
        exists = os.path.exists(os.path.join(config.pdfs_dir, name))
        result.append({
            "name": name,
            "chunks": info["chunks"],
            "size": info["size"],
            "uploaded_at": info.get("uploaded_at", ""),
            "exists": exists,
            "pdf_type": info.get("pdf_type", "text"),
        })
    return result


def retrieve_docs(query: str, file_name: str):
    global _faiss_db
    if _faiss_db is None:
        embedding = _get_embedding_model()
        try:
            _faiss_db = FAISS.load_local(config.faiss_db_path, embedding, allow_dangerous_deserialization=True)
        except Exception:
            return []
    docs = _faiss_db.similarity_search(query, k=config.top_k)
    if file_name:
        docs = [d for d in docs if d.metadata.get("source") == file_name]
    return docs
