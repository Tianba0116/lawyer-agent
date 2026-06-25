from rag.vector_db import retrieve_docs


def get_context_for_query(query: str, file_name: str) -> str:
    docs = retrieve_docs(query, file_name)
    if not docs:
        return ""
    return "\n\n".join(d.page_content for d in docs)
