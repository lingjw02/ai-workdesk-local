import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from core import config


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    # Atomic replace on Windows
    if os.name == "nt" and path.exists():
        os.replace(temp_path, path)
    else:
        temp_path.replace(path)


# --- Storage Functions ---

def get_project_path(project_id: str) -> Path:
    return config.PROJ_DIR / f"{project_id}.json"


def list_projects() -> List[Dict[str, Any]]:
    projects = []
    for f in config.PROJ_DIR.glob("*.json"):
        data = read_json(f)
        if data and "id" in data:
            projects.append({
                "id": data["id"],
                "name": data.get("name", "Untitled Project"),
                "workers": data.get("workers", []),
                "updatedAt": data.get("updatedAt"),
                "status": data.get("status", "active"),
                "pm": data.get("pm", {}),
            })
    return sorted(projects, key=lambda p: p.get("updatedAt", ""), reverse=True)


def load_project(project_id: str) -> Optional[Dict[str, Any]]:
    return read_json(get_project_path(project_id))


def save_project(project_data: Dict[str, Any]):
    write_json(get_project_path(project_data["id"]), project_data)


def delete_project(project_id: str) -> bool:
    p = get_project_path(project_id)
    if p.exists():
        p.unlink()
        return True
    return False


def get_conversation_path(conv_id: str) -> Path:
    return config.CONV_DIR / f"{conv_id}.json"


def list_conversations() -> List[Dict[str, Any]]:
    convs = []
    for f in config.CONV_DIR.glob("*.json"):
        data = read_json(f)
        if data and "id" in data:
            convs.append({
                "id": data["id"],
                "title": data.get("title", "New chat"),
                "updatedAt": data.get("updatedAt"),
            })
    return sorted(convs, key=lambda c: c.get("updatedAt", ""), reverse=True)


def load_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    return read_json(get_conversation_path(conv_id))


def save_conversation(conv_data: Dict[str, Any]):
    write_json(get_conversation_path(conv_data["id"]), conv_data)


def load_global_memory() -> Dict[str, Any]:
    return read_json(config.MEMORY_FILE, {})


def save_global_memory(patch: Dict[str, Any]) -> Dict[str, Any]:
    mem = load_global_memory()
    mem.update(patch)
    write_json(config.MEMORY_FILE, mem)
    return mem


def append_audit_log(entry: Dict[str, Any]):
    audit_file = config.AUDIT_DIR / "audit_log.jsonl"
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def get_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    audit_file = config.AUDIT_DIR / "audit_log.jsonl"
    if not audit_file.exists():
        return []
    lines = audit_file.read_text(encoding="utf-8").strip().split("\n")
    results = []
    for line in reversed(lines[-limit:]):
        if line:
            try:
                results.append(json.loads(line))
            except Exception:
                pass
    return results
