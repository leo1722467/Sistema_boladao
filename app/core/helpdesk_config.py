import json
import os
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "helpdesk")

def _ensure_dir() -> None:
    os.makedirs(BASE_DIR, exist_ok=True)

def _load_json(name: str, default: Any) -> Any:
    _ensure_dir()
    path = os.path.join(BASE_DIR, f"{name}.json")
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(name: str, data: Any) -> None:
    _ensure_dir()
    path = os.path.join(BASE_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_routing_rules() -> Dict[str, Any]:
    return _load_json("routing_rules", {"by_category": {}, "by_priority": {}, "default_agent_id": None})

def save_routing_rules(data: Dict[str, Any]) -> None:
    _save_json("routing_rules", data)

def load_macros() -> List[Dict[str, Any]]:
    return _load_json("macros", [])

def save_macros(data: List[Dict[str, Any]]) -> None:
    _save_json("macros", data)

def load_sla_overrides() -> Dict[str, Any]:
    return _load_json("sla_overrides", {"low": {}, "normal": {}, "high": {}, "urgent": {}, "critical": {}})

def save_sla_overrides(data: Dict[str, Any]) -> None:
    _save_json("sla_overrides", data)

def load_auto_close_policy() -> Dict[str, Any]:
    return _load_json("auto_close_policy", {"pending_customer_days": 14, "resolved_days": 7, "enabled": False})

def save_auto_close_policy(data: Dict[str, Any]) -> None:
    _save_json("auto_close_policy", data)

