"""AI WorkDesk OS — FastAPI/UI layer.

All task execution, state machine, persistence, memory, permissions and audit
are delegated to the headless core runtime via `bridge.WorkDeskBridge`
(Engine in src/workdesk). This file only keeps the HTTP/WS contract of the UI
layer: chat, projects, workers catalog, memory, approvals, audit + static UI.
"""
import datetime
import logging
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import config
from core.event_bus import event_bus
from core.models import WorkerProfile
from memory import store
from agents.registry import registry
from bridge import bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AIWorkDeskOS")

app = FastAPI(title="AI WorkDesk OS", version="0.8.0")
from companion_vision import router as companion_vision_router
app.include_router(companion_vision_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    """Start the WS pump that streams core engine events to Work Graph / Virtual Office."""
    bridge.start_pump()
    logger.info("WorkDeskBridge connected to headless core runtime.")


# --- WebSocket for Real-time Streaming & Work Graph / Virtual Office ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await event_bus.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Can handle incoming client heartbeats or interactive workspace controls
    except WebSocketDisconnect:
        event_bus.disconnect(websocket)


# --- REST Endpoints ---

class ChatRequest(BaseModel):
    conversationId: Optional[str] = None
    text: str
    mode: str = "instant"  # instant, expert, vision
    chatMode: str = "chat"  # chat | project
    deepthink: str = "normal"
    search: bool = False
    clarificationResponse: Optional[str] = None
    projectId: Optional[str] = None


@app.post("/api/chat")
def chat_handler(req: ChatRequest):
    """Main Brain conversation endpoint with automatic Ambiguity Gate and Task Group dispatch."""
    conv_id = req.conversationId or f"conv-{uuid.uuid4().hex[:8]}"
    conv = store.load_conversation(conv_id) or {
        "id": conv_id,
        "title": req.text[:40] or "New Chat",
        "chatMode": req.chatMode,
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "messages": [],
    }
    if req.chatMode:
        conv["chatMode"] = req.chatMode

    conv["messages"].append({
        "role": "user",
        "text": req.text,
        "timestamp": datetime.datetime.now().isoformat(),
    })

    result = bridge.handle_request(
        user_text=req.text,
        project_id=req.projectId,
        clarification_response=req.clarificationResponse,
        conversation_id=conv_id,
        chat_mode=req.chatMode,
    )

    reply_text = ""
    if result.get("status") == "CLARIFICATION_REQUIRED":
        cp = result["clarification"]
        opts = "\n".join(f"- {o}" for o in cp.get("options", []))
        reply_text = f"**Clarification Required (QA-1 Ambiguity Gate):**\n\n{cp.get('question')}\n\n*Options:*\n{opts}\n\n*{cp.get('contextExplanation', '')}*"
    elif result.get("complexity") == "simple":
        reply_text = result.get("reply", "Task completed.")
    elif result.get("mbNarrative"):
        reply_text = result["mbNarrative"]
    else:
        pm_plan = result.get("pmPlan", "")
        delivs = result.get("deliverables", {})
        deliv_list = ", ".join(delivs.keys()) if delivs else "None"
        qa2_status = result.get("qa2Report", {}).get("result", "PASS")
        reply_text = f"**Task Group Execution Completed (QA-2 Verified: {qa2_status})**\n\n**PM Plan:** {pm_plan}\n\n**Generated Deliverables:** {deliv_list}\n\n*View deliverables in the Workspace Project tabs.*"

    conv["messages"].append({
        "role": "assistant",
        "text": reply_text,
        "taskResult": result,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    conv["updatedAt"] = datetime.datetime.now().isoformat()
    store.save_conversation(conv)

    return {
        "conversationId": conv_id,
        "reply": reply_text,
        "taskResult": result,
    }


@app.get("/api/search")
def search_web(q: str = "", count: int = 5):
    """Real web search (keyless Bing / Brave) — powers the Researcher's live browser view."""
    if not q:
        return {"query": q, "results": []}
    try:
        from tools.web_tool import WebTool
        wt = WebTool()
        results = wt.search_sync(q, count=count)
        return {"query": q, "results": results}
    except Exception as e:  # noqa: BLE001
        return {"query": q, "error": repr(e), "results": []}


@app.get("/api/conversations")
def get_conversations():
    return store.list_conversations()


@app.get("/api/conversations/{id}")
def get_conversation(id: str):
    conv = store.load_conversation(id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{id}")
def delete_conversation(id: str):
    p = config.CONV_DIR / f"{id}.json"
    if p.exists():
        p.unlink()
    return {"ok": True}


# --- Projects & Lifetime PM ---

class CreateProjectRequest(BaseModel):
    name: str
    workers: List[str] = ["researcher", "coder", "documenter"]


@app.get("/api/projects")
def get_projects():
    return store.list_projects()


@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    project_id = f"proj-{uuid.uuid4().hex[:6]}"
    pm = registry.get_or_create_pm(project_id, req.name)
    nodes = {w: {"status": "idle", "files": {}, "notes": [], "doc": ""} for w in req.workers}
    project = {
        "id": project_id,
        "name": req.name,
        "workers": req.workers,
        "pm": pm.model_dump(),
        "nodes": nodes,
        "messages": [],
        "terminal": [],
        "deliverables": {},
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "status": "active",
    }
    store.save_project(project)
    return project


@app.get("/api/projects/{id}")
def get_project(id: str):
    proj = store.load_project(id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.delete("/api/projects/{id}")
def delete_project(id: str):
    store.delete_project(id)
    return {"ok": True}


class TaskGroupRequest(BaseModel):
    text: str
    clarificationResponse: Optional[str] = None


@app.post("/api/projects/{id}/task")
def dispatch_project_task(id: str, req: TaskGroupRequest):
    proj = store.load_project(id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    result = bridge.handle_request(
        user_text=req.text,
        project_id=id,
        active_workers=proj.get("workers", []),
        clarification_response=req.clarificationResponse,
    )

    proj = store.load_project(id)
    if proj:
        if "deliverables" not in proj:
            proj["deliverables"] = {}
        proj["deliverables"].update(result.get("deliverables", {}))
        proj["terminal"].append({
            "ts": datetime.datetime.now().isoformat(),
            "who": "pm",
            "text": f"Task completed: {result.get('pmPlan', '')}",
        })
        store.save_project(proj)

    return result


@app.post("/api/projects/{id}/cancel")
def cancel_project_task(id: str, task_id: str = Body(..., embed=True)):
    """Emergency Stop / Cancellation (USER > MB, Spec 01 Stop protocol)."""
    out = bridge.cancel(task_id)
    return out


# --- Workers Registry & Worker Creator ---

@app.get("/api/workers")
def list_workers():
    """Real engine worker pool (persistent profiles + statistics)."""
    return bridge.workers_list()


@app.post("/api/workers")
def create_worker(worker: WorkerProfile):
    """Create a worker in the engine SQLite registry (body JSON matches WorkerProfile)."""
    wid = bridge.worker_create(worker.model_dump())
    return {"ok": True, "worker_id": wid, "worker": worker.model_dump()}


# --- Memory Hierarchy Inspection (backed by engine SQLite) ---

@app.get("/api/memory")
def get_memory(projectId: Optional[str] = None):
    return bridge.memory_get(projectId)


@app.post("/api/memory")
def update_global_memory(patch: Dict[str, Any] = Body(...)):
    return bridge.memory_update(patch)


# --- Permission & Approvals (Level 2 & 3 Gates) ---

@app.get("/api/approvals")
def get_approvals(conversation_id: Optional[str] = None):
    return bridge.approvals_pending(conversation_id)


class ApprovalResolveRequest(BaseModel):
    requestId: str
    approved: bool
    userComment: Optional[str] = None


@app.post("/api/approvals/resolve")
def resolve_approval(req: ApprovalResolveRequest):
    """Resolve a pending approval (body JSON: requestId + approved)."""
    return {"ok": bridge.approvals_resolve(req.requestId, req.approved)}


# --- Audit Logs (engine event-sourced audit) ---

@app.get("/api/audit")
def get_audit(limit: int = 50):
    return bridge.audit_list(limit=limit)


# --- Phase 7: WorkDesk UI read models ---

@app.get("/api/tasks")
def get_tasks(projectId: Optional[str] = None, limit: int = 100,
              conversation_id: Optional[str] = None):
    return bridge.tasks_list(projectId, limit, conversation_id)


class ReorderRequest(BaseModel):
    conversation_id: str
    task_ids: list[str]


@app.post("/api/tasks/reorder")
def reorder_tasks(req: ReorderRequest):
    try:
        return bridge.reorder_tasks(req.conversation_id, req.task_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/tasks/{task_id}")
def get_task_detail(task_id: str):
    try:
        return bridge.task_detail(task_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/pms")
def get_pms():
    return bridge.pms_list()


@app.get("/api/virtual-office")
def get_virtual_office(conversation_id: Optional[str] = None):
    return bridge.virtual_office(conversation_id)


@app.get("/api/model-router")
def get_model_router():
    return bridge.model_router()


@app.get("/api/learning")
def get_learning(scope: Optional[str] = None, limit: int = 100):
    """Phase 9 — learning system stats + lessons (scope: pm|worker|global)."""
    return bridge.learning(scope=scope, limit=limit)


# ---------------- Phase 10: personal utilities + working area ----------------
@app.get("/api/workspace/files")
def ws_files():
    return bridge.ws_list()


@app.get("/api/workspace/read")
def ws_read(path: str):
    return bridge.ws_read(path)


@app.post("/api/workspace/save")
def ws_save(body: dict):
    return bridge.ws_save(body.get("path", ""), body.get("content", ""))


@app.post("/api/workspace/upload")
async def ws_upload(request: Request):
    form = await request.form()
    subdir = str(form.get("subdir", "") or "")
    saved = []
    for f in form.getlist("files"):
        data = await f.read()
        saved.append(bridge.ws_upload(f.filename or "upload.bin", data, subdir))
    return {"saved": saved}


@app.delete("/api/workspace/file")
def ws_delete(path: str):
    return bridge.ws_delete(path)


@app.get("/api/workspace/file")
def ws_file(path: str):
    p = bridge.ws_file(path)
    if p is None:
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(str(p), filename=Path(p).name)


@app.post("/api/code/run")
def code_run(body: dict):
    """Phase 10 — run code in a timed sandbox (audited terminal action)."""
    return bridge.code_run(body.get("code", ""), body.get("language", "python"),
                           timeout=int(body.get("timeout", 15)))


@app.get("/api/notes")
def notes_list(section: Optional[str] = None):
    return {"notes": bridge.notes_list(section)}


@app.post("/api/notes/save")
def notes_save(body: dict):
    return bridge.notes_save(body.get("note_id"), body.get("section", "user"),
                             body.get("title", "untitled"), body.get("content", ""))


@app.post("/api/notes/delete")
def notes_delete(body: dict):
    return bridge.notes_delete(body.get("note_id", ""))


class ModelCallRequest(BaseModel):
    prompt: str
    system: str | None = None
    capability: str = "default"
    complexity: str = "normal"
    privacy: str = "public"
    task_type: str = "default"
    model_hint: str = "auto"
    task_id: str | None = None
    worker_id: str | None = None
    temperature: float = 0.7


@app.post("/api/model-router/call")
def call_model_router(body: ModelCallRequest):
    """Phase 8.2 — route a one-off request, persist the decision, invoke the
    model (OpenRouter/local OpenAI-compatible endpoint) with fallback chain."""
    return bridge.model_router_call(body.model_dump())


@app.post("/api/settings/chatanywhere")
def save_chatanywhere(body: dict):
    """Persist the ChatAnywhere free relay key (.env) and hot-apply it."""
    return bridge.save_chatanywhere_key((body or {}).get("api_key", ""))


@app.get("/api/settings")
def get_settings():
    return bridge.settings()


@app.post("/api/tasks/{task_id}/resume")
def resume_task(task_id: str):
    try:
        task = bridge.engine.resume(task_id)
        return {"taskId": task.task_id, "state": task.state.value}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=repr(e))


# ---------------- Phase 11: vault, worker design, studio, clear history ----------------

@app.get("/api/vault/tree")
def vault_tree(section: Optional[str] = "my"):
    return {"files": bridge.vault_tree(section)}


@app.get("/api/vault/read")
def vault_read(section: str = "my", path: str = ""):
    return bridge.vault_read(section, path)


@app.post("/api/vault/save")
def vault_save(body: dict):
    return bridge.vault_save(body.get("section", "my"), body.get("path", ""),
                             body.get("content", ""))


@app.delete("/api/vault/file")
def vault_delete(section: str = "my", path: str = ""):
    return bridge.vault_delete(section, path)


@app.post("/api/vault/mb-chat")
def vault_mb_chat(body: dict):
    """User dictates what the Main Brain should store in the Vault."""
    return bridge.vault_mb_chat(body.get("message", ""))


@app.post("/api/vault/mb-sync")
def vault_mb_sync():
    """Main Brain auto-writes learned knowledge into vault/mb/_auto/."""
    return bridge.mb_sync()


@app.get("/api/vault/search")
def vault_search(section: str = "my", q: str = ""):
    return {"hits": bridge.vault_search(section, q)}


# ---------------- Phase 13: Hive (office floor coordination) ----------------
@app.post("/api/hive/messages")
def hive_send(body: dict):
    return bridge.hive_send(body.get("conversation_id"), body.get("from", "mb"),
                            body.get("to", "mb"), body.get("act", "inform"),
                            body.get("subject", ""), body.get("body", ""),
                            body.get("in_reply_to"))


@app.get("/api/hive/messages")
def hive_messages(conversation_id: str | None = None, agent_id: str | None = None):
    return {"messages": bridge.hive_messages(conversation_id, agent_id)}


@app.get("/api/hive/board")
def hive_board(conversation_id: str | None = None):
    return bridge.hive_board_get(conversation_id)


@app.post("/api/hive/board")
def hive_board_update(body: dict):
    return bridge.hive_board_put(body.get("conversation_id"), body.get("text", ""),
                                 body.get("scribe", "pm"))


@app.get("/api/hive/state")
def hive_state(conversation_id: str | None = None):
    return bridge.hive_state(conversation_id)


@app.post("/api/clear-history")
def clear_history(body: dict):
    return bridge.clear_history(body.get("scope", "all"))


class DesignRequest(BaseModel):
    github_url: str
    subdir: Optional[str] = None


class ApplyWorkerRequest(BaseModel):
    profile: dict
    mode: str = "create"
    merge_into: Optional[str] = None


@app.post("/api/workers/design")
def design_worker(req: DesignRequest):
    return bridge.worker_design(req.github_url, req.subdir)


@app.post("/api/workers/apply")
def apply_worker(req: ApplyWorkerRequest):
    return bridge.worker_apply(req.profile, req.mode, req.merge_into)


class CreateCapabilityRequest(BaseModel):
    capability: str
    name: Optional[str] = None


class SkillInstallRequest(BaseModel):
    worker_id: str
    skill_name: str


@app.post("/api/workers/create-capability")
def create_capability_worker(req: CreateCapabilityRequest):
    return bridge.worker_create_capability(req.capability, req.name)


@app.get("/api/skill-market")
def skill_market():
    return bridge.skill_market()


@app.post("/api/skill-market/install")
def skill_install(req: SkillInstallRequest):
    return bridge.skill_install(req.worker_id, req.skill_name)


class RemoteRegisterRequest(BaseModel):
    name: str
    host: str
    os: Optional[str] = ""


class RemoteCommandRequest(BaseModel):
    command: str


@app.get("/api/remote/devices")
def remote_devices():
    return bridge.remote_devices_list()


@app.post("/api/remote/devices")
def remote_device_register(req: RemoteRegisterRequest):
    return bridge.remote_device_register(req.name, req.host, req.os)


@app.post("/api/remote/{device_id}/command")
def remote_device_command(device_id: str, req: RemoteCommandRequest):
    return bridge.remote_device_command(device_id, req.command)


@app.put("/api/workers/{worker_id}")
def update_worker(worker_id: str, body: dict):
    return bridge.worker_update(worker_id, body)


@app.get("/api/workers/{worker_id}/studio")
def worker_studio(worker_id: str):
    return bridge.worker_studio(worker_id)




# ---------------- Local filesystem browse (read-only, user-authorized) ----------------
import os as _os

TEXT_EXTS = {".txt",".md",".markdown",".py",".js",".mjs",".ts",".tsx",".jsx",".html",".htm",".css",".json",".csv",".tsv",".xml",".yml",".yaml",".ini",".cfg",".conf",".log",".sql",".sh",".bat",".cmd",".ps1",".java",".c",".cpp",".h",".hpp",".go",".rs",".rb",".php",".vue",".svelte",".toml",".env",".gitignore",".dockerfile",".rst",".tex",".ipynb"}

@app.post("/api/local/scan")
def local_scan(body: Dict[str, Any]):
    raw = str(body.get("path") or "").strip() or str(config.BASE_DIR)
    path = _os.path.abspath(_os.path.expanduser(raw))
    if not _os.path.exists(path):
        raise HTTPException(400, f"Path does not exist: {path}")
    if not _os.path.isdir(path):
        raise HTTPException(400, "Not a directory")
    entries = []
    try:
        names = sorted(_os.listdir(path), key=lambda n: (not _os.path.isdir(_os.path.join(path, n)), n.lower()))
    except PermissionError:
        raise HTTPException(403, f"Access denied: {path}")
    except OSError as e:
        raise HTTPException(500, f"Cannot read folder: {e}")
    for name in names:
        if name.startswith("$") :
            continue
        fp = _os.path.join(path, name)
        try:
            st = _os.stat(fp)
            entries.append({
                "name": name,
                "path": fp,
                "is_dir": _os.path.isdir(fp),
                "size": st.st_size if not _os.path.isdir(fp) else 0,
                "mtime": st.st_mtime,
            })
        except OSError:
            continue
    return {"path": path, "parent": _os.path.dirname(path), "entries": entries}


@app.get("/api/local/read")
def local_read(path: str):
    path = _os.path.abspath(_os.path.expanduser(path))
    if not _os.path.isfile(path):
        raise HTTPException(400, "Not a file")
    try:
        size = _os.path.getsize(path)
    except OSError:
        raise HTTPException(403, "Cannot access file")
    if size > 4 * 1024 * 1024:
        raise HTTPException(413, f"File too large to preview ({size // 1024 // 1024} MB, limit 4 MB)")
    ext = _os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS or ext == "":
        try:
            data = io_open_text(path)
        except Exception:
            raise HTTPException(500, "Cannot decode file as text")
        return {"path": path, "kind": "text", "size": size, "content": data}
    return {"path": path, "kind": "binary", "size": size, "ext": ext or "unknown"}


def io_open_text(path):
    import io as _io
    try:
        return _io.open(path, "r", encoding="utf-8", errors="replace").read()
    except Exception:
        return _io.open(path, "r", encoding="latin-1", errors="replace").read()


@app.get("/api/local/file")
def local_file(path: str):
    path = _os.path.abspath(_os.path.expanduser(path))
    if not _os.path.isfile(path):
        raise HTTPException(400, "Not a file")
    try:
        size = _os.path.getsize(path)
        if size > 300 * 1024 * 1024:
            raise HTTPException(413, "File too large to stream")
    except OSError:
        raise HTTPException(403, "Cannot access file")
    return FileResponse(path)


@app.get("/api/font/simhei")
def font_simhei():
    cands = [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]
    for p in cands:
        if _os.path.exists(p):
            return FileResponse(p, media_type="font/ttf", filename=_os.path.basename(p))
    raise HTTPException(404, "No CJK font available")



# Mount static files at the root
app.mount("/", StaticFiles(directory=str(config.BASE_DIR / "public"), html=True), name="public")


if __name__ == "__main__":
    import uvicorn
    print(f"\n  [OK] AI WorkDesk OS running -> http://localhost:{config.PORT}\n")
    uvicorn.run(app, host="0.0.0.0", port=config.PORT,
                timeout_keep_alive=600)  # keep-alive 10 min; long-lived sessions stay connected
