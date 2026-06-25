import os
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from providers import get_provider


def _resolve_api_key(raw: str) -> str:
    """如果 raw 是环境变量名则从 env 读取，如果是 key 本身则直接返回"""
    if not raw:
        return ""
    # 如果以 sk- 开头或长度 > 30 且不含空格，视为 API Key 本身
    if raw.startswith("sk-") or (len(raw) > 30 and " " not in raw):
        return raw
    return os.getenv(raw, "")


def get_llm(provider_id: str = "deepseek"):
    p = get_provider(provider_id)
    if p is None:
        p = get_provider("deepseek")

    ptype = p.get("type", "deepseek")
    model = p.get("model", "deepseek-chat")
    api_key = _resolve_api_key(p.get("api_key_env", ""))
    base_url = p.get("base_url", "")

    if ptype == "openai":
        kwargs = {"model": model}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    else:  # deepseek
        kwargs = {"model": model}
        if api_key:
            kwargs["api_key"] = api_key
        return ChatDeepSeek(**kwargs)
