from typing import Annotated
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_llm
from tools import ALL_TOOLS
from agent.prompts import SYSTEM_PROMPT


def create_lawyer_agent(provider: str = "deepseek"):
    llm = get_llm(provider)
    return create_agent(
        model=llm,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def build_initial_state(query: str, file_name: str) -> dict:
    if file_name:
        context_msg = SystemMessage(content=f"用户当前已上传的文档：{file_name}。如果用户的问题涉及该文档，请使用工具检索文档内容后回答。")
    else:
        context_msg = SystemMessage(content="用户当前尚未上传任何文档。请基于你的法律知识直接回答问题，并建议用户上传文档以获得更精准分析。")

    return {
        "messages": [context_msg, HumanMessage(content=query)],
    }
