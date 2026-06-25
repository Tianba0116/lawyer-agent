from langchain_core.tools import tool
from rag.retriever import get_context_for_query


@tool
def search_legal_document(query: str, file_name: str = "") -> str:
    """搜索已上传的法律文档，查找与查询相关的段落。

    Args:
        query: 要在法律文档中搜索的查询内容。
        file_name: 已上传的 PDF 文件名。如果用户未上传文档，传空字符串。

    Returns:
        相关段落，或未找到内容的提示。
    """
    if not file_name:
        return "当前未上传任何文档。请告知用户先上传一份法律 PDF 文档，以便进行检索。"
    context = get_context_for_query(query, file_name)
    if not context:
        return f"在文档 {file_name} 中未找到与 '{query}' 相关的内容。"
    return f"文档 {file_name} 中的相关段落：\n\n{context}"
