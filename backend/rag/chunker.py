from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.config import config


def load_pdf(file_path: str):
    loader = PDFPlumberLoader(file_path)
    return loader.load()


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
