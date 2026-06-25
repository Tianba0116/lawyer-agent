from langchain_core.tools import tool
from rag.retriever import get_context_for_query


@tool
def summarize_document(file_name: str = "") -> str:
    """对已上传的法律文档进行摘要，突出关键要点和法律结论。

    Args:
        file_name: 要摘要的 PDF 文件名。如果用户未上传文档，传空字符串。

    Returns:
        文档的结构化摘要所需的内容，LLM 将据此生成摘要。
    """
    if not file_name:
        return "当前未上传任何文档，无法进行摘要。请告知用户先上传一份法律 PDF 文档。"
    context = get_context_for_query(
        "摘要 主要要点 法律结论 重要条款 核心内容", file_name
    )
    if not context:
        return f"无法摘要 {file_name}：文档中未提取到内容。"
    return f"文档 {file_name} 中提取的关键内容：\n\n{context}"
