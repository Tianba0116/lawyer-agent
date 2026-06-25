import json
import os
import copy

PROVIDERS_FILE = os.path.join(os.path.dirname(__file__), "providers.json")


def _load() -> dict:
    with open(PROVIDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(PROVIDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_providers() -> list[dict]:
    return _load()["providers"]


def get_active() -> str:
    return _load()["active"]


def set_active(provider_id: str):
    data = _load()
    data["active"] = provider_id
    _save(data)


def get_provider(provider_id: str) -> dict | None:
    for p in _load()["providers"]:
        if p["id"] == provider_id:
            return p
    return None


def add_provider(provider: dict) -> dict:
    data = _load()
    data["providers"].append(provider)
    _save(data)
    return provider


def update_provider(provider_id: str, updates: dict) -> dict | None:
    data = _load()
    for i, p in enumerate(data["providers"]):
        if p["id"] == provider_id:
            # For builtin providers, only allow editing certain fields
            p.update(updates)
            _save(data)
            return p
    return None


def delete_provider(provider_id: str) -> bool:
    data = _load()
    for i, p in enumerate(data["providers"]):
        if p["id"] == provider_id:
            if p.get("builtin"):
                return False
            data["providers"].pop(i)
            if data["active"] == provider_id:
                data["active"] = "deepseek"
            _save(data)
            return True
    return False
