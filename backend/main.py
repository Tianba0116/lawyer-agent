import os
import json
import asyncio
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from core.config import config
from core.llm import get_llm
from rag.vector_db import index_pdf, list_documents, remove_document
from agent.agent import create_lawyer_agent, build_initial_state
from providers import (
    list_providers, get_active, set_active,
    add_provider, update_provider, delete_provider,
)

app = FastAPI(title="AI 法律助手 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conversations: dict[str, list] = {"default": []}


class QueryRequest(BaseModel):
    query: str
    file_name: str
    provider: str = "deepseek"


class SummarizeRequest(BaseModel):
    file_name: str
    provider: str = "deepseek"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        return {"error": "仅支持 PDF 格式文件"}, 400

    os.makedirs(config.pdfs_dir, exist_ok=True)
    file_path = os.path.join(config.pdfs_dir, file.filename)
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    index_pdf(file_path)
    return {"file_name": file.filename, "status": "indexed"}


@app.post("/api/query")
def query(req: QueryRequest):
    provider = get_active()
    agent = create_lawyer_agent(provider)
    history = conversations["default"]
    state = build_initial_state(req.query, req.file_name)
    state["messages"] = history + state["messages"]

    result = agent.invoke(state)

    final_answer = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            final_answer = msg.content
            break

    conversations["default"] = result["messages"]
    return {"answer": final_answer or "未能生成回答，请重试。"}


@app.post("/api/query/stream")
async def query_stream(req: QueryRequest):
    provider = get_active()
    agent = create_lawyer_agent(provider)
    history = conversations["default"]
    state = build_initial_state(req.query, req.file_name)
    state["messages"] = history + state["messages"]

    async def generate():
        collected_content = ""
        try:
            async for event in agent.astream_events(state, version="v2"):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", None)
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        collected_content += chunk.content
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"

                elif kind == "on_tool_start":
                    name = event.get("name", "unknown")
                    yield f"data: {json.dumps({'tool_start': name})}\n\n"

                elif kind == "on_tool_end":
                    yield f"data: {json.dumps({'tool_end': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # Save the final conversation
        full_messages = state["messages"]
        full_messages.append(AIMessage(content=collected_content))
        conversations["default"] = full_messages
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.post("/api/summarize")
def summarize(req: SummarizeRequest):
    provider = get_active()
    agent = create_lawyer_agent(provider)
    state = build_initial_state(
        "请对已上传的法律文档进行结构化摘要，突出关键要点和法律结论。",
        req.file_name,
    )
    result = agent.invoke(state)

    summary_text = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            summary_text = msg.content
            break

    return {"summary": summary_text or "未提取到可摘要的内容。"}


@app.get("/api/documents")
def get_documents():
    """列出知识库中所有已索引的文档"""
    docs = list_documents()
    return {"documents": docs, "count": len(docs)}


@app.delete("/api/documents/{file_name}")
def delete_document(file_name: str):
    """从知识库中删除指定文档"""
    success = remove_document(file_name)
    if not success:
        return {"error": "文档不存在"}, 404
    if file_name in conversations:
        del conversations[file_name]
    return {"status": "deleted", "file_name": file_name}


# ── Provider Management ──

class ProviderUpdate(BaseModel):
    name: str = ""
    icon: str = ""
    model: str = ""
    type: str = "openai"
    api_key_env: str = ""
    base_url: str = ""


@app.get("/api/providers")
def get_providers():
    return {"providers": list_providers(), "active": get_active()}


@app.put("/api/providers/{provider_id}/activate")
def activate_provider(provider_id: str):
    set_active(provider_id)
    return {"active": provider_id}


@app.put("/api/providers/{provider_id}")
def edit_provider(provider_id: str, updates: ProviderUpdate):
    result = update_provider(provider_id, updates.model_dump(exclude_unset=True))
    if result is None:
        return {"error": "供应商不存在"}, 404
    return {"provider": result}


@app.post("/api/providers")
def create_provider(provider: ProviderUpdate):
    import uuid
    pid = "custom-" + uuid.uuid4().hex[:8]
    data = provider.model_dump()
    data["id"] = pid
    data["builtin"] = False
    add_provider(data)
    return {"provider": data}


@app.delete("/api/providers/{provider_id}")
def remove_provider(provider_id: str):
    if not delete_provider(provider_id):
        return {"error": "无法删除内置供应商或供应商不存在"}, 400
    return {"status": "deleted"}


@app.get("/api/report/{file_name}")
def download_report(file_name: str):
    conv = conversations.get("default", [])
    if not conv:
        return {"error": "未找到对话记录"}, 404
    qa_lines = []
    for msg in conv:
        if isinstance(msg, HumanMessage):
            qa_lines.append(f"Q: {msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            qa_lines.append(f"A: {msg.content}")
            qa_lines.append("---")

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit

    c = canvas.Canvas(config.report_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "AI 法律助手 - 对话报告")
    c.setFont("Helvetica", 12)
    c.drawString(100, 730, f"文档：{file_name}")
    c.drawString(100, 715, "以下为您与 AI 法律助手的对话记录：")

    y = 685
    for line in qa_lines:
        wrapped = simpleSplit(line, "Helvetica", 12, 450)
        for w in wrapped:
            if y < 50:
                c.showPage()
                c.setFont("Helvetica", 12)
                y = 750
            c.drawString(100, y, w)
            y -= 15
        y -= 5

    c.save()
    return FileResponse(config.report_path, media_type="application/pdf", filename="AI_Lawyer_Report.pdf")
