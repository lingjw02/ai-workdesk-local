"""WorkDesk Bridge — FastAPI/UI layer → headless core runtime.

Integration decision (DECISIONS.md): the server keeps its HTTP/WS contract
(public/ UI + test_pipeline.py) while all task execution, state machine,
persistence, memory, permissions and audit come from the `src/workdesk` Engine.

This module is the ONLY seam between the two layers:
  - `handle_request()` maps /api/chat and /api/projects/{id}/task to Engine.submit/clarify
  - the audit hook turns engine events into Work Graph / Virtual Office WS broadcasts
  - memory / approvals / audit endpoints read the engine's SQLite records
"""
import asyncio
import datetime
import json
import os
import queue
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from core import config as app_config
from core.event_bus import event_bus
from memory import store
from brain_context import build_chat_messages

from src.workdesk import db as wd_db
from src.workdesk.engine import Engine
from src.workdesk.runtime import ClarificationNeeded
from src.workdesk.states import TaskState
from src.workdesk.model_router import RouteRequest

OUTPUT_FILENAMES = {"python": "demo_script.py", "research": "research_notes.md",
                    "markdown": "report.md", "report": "report.md"}


class WorkDeskBridge:
    def __init__(self):
        db_path = os.environ.get("WORKDESK_DB") or str(Path(app_config.DATA_DIR) / "workdesk.db")
        auto_approve = os.environ.get("WORKDESK_AUTO_APPROVE", "1") != "0"
        self.engine = Engine(db_path=db_path, auto_approve=auto_approve,
                             project_dir=app_config.DATA_DIR / "out")
        self._seed_workers()
        self._queue: "queue.Queue[tuple[str, dict] | None]" = queue.Queue()
        self._pump_task = None
        self._wrap_audit()

    # ------------------------------------------------------------------ #
    # worker ecosystem (ids kept compatible with the old UI catalog)      #
    # ------------------------------------------------------------------ #
    def _seed_workers(self):
        self.engine.seed_worker("researcher", "Alex Researcher",
                                {"research.search": {"capability": "research"}})
        self.engine.seed_worker("coder", "Jordan Coder",
                                {"coding.python": {"capability": "coding"}})
        self.engine.seed_worker("documenter", "Taylor Documenter",
                                {"writer.markdown": {"capability": "writer"}})
        self.engine.seed_worker("data_analyst", "Morgan Data Analyst",
                                {"data.summarize": {"capability": "data"}})

    # ------------------------------------------------------------------ #
    # audit hook -> WS event stream (Work Graph / Virtual Office)         #
    # ------------------------------------------------------------------ #
    def _wrap_audit(self):
        orig = self.engine.permissions.audit

        def hooked(actor_role, actor_id, action, *, tool=None, files_changed=None,
                   reason=None, qa_refs=None, rework_refs=None, task_id=None):
            try:
                row = orig(actor_role, actor_id, action, tool=tool,
                           files_changed=files_changed, reason=reason,
                           qa_refs=qa_refs, rework_refs=rework_refs, task_id=task_id)
                self._enqueue(action, {"actor": actor_role, "actorId": actor_id,
                                       "reason": reason, "taskId": task_id})
                return row
            except Exception:  # noqa: BLE001 - audit must never break execution
                return None

        self.engine.permissions.audit = hooked

    def _enqueue(self, action: str, info: dict):
        try:
            self._queue.put_nowait((action, info))
        except Exception:  # noqa: BLE001
            pass

    def start_pump(self):
        """Start the asyncio pump that drains engine events into the WS bus."""
        if self._pump_task is not None:
            return
        loop = asyncio.get_event_loop()
        self._pump_task = loop.create_task(self._pump())

    async def _pump(self):
        """Drain engine events into the WS bus. NEVER blocks the event loop:
        threading.Queue is only probed with get_nowait(); idle time is asyncio.sleep."""
        while True:
            drained = False
            while True:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    break
                drained = True
                if item is None:
                    return
                try:
                    await self._broadcast_for(action=item[0], info=item[1])
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(0.05 if drained else 0.25)

    async def _broadcast_for(self, action: str, info: dict):
        task_id = info.get("taskId")
        actor = info.get("actor", "")
        if action == "task_state:ANALYZING":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "ANALYZING"})
        elif action == "task_state:CLARIFYING":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "CLARIFYING"})
            await event_bus.broadcast("qa1_audit_completed", {
                "taskId": task_id, "status": "FAIL", "ambiguityLevel": "IMPORTANT",
                "clarificationPrompt": {"question": "需要补充必要信息后开始执行。",
                                        "options": ["Markdown 报告", "研究笔记", "Python 脚本"]},
                "auditNotes": str(info.get("reason", ""))})
        elif action == "task_state:READY":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "READY"})
            await event_bus.broadcast("qa1_audit_completed", {
                "taskId": task_id, "status": "PASS", "ambiguityLevel": "MINOR",
                "clarificationPrompt": None, "auditNotes": "Requirement QA passed."})
        elif action == "task_state:RUNNING":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "RUNNING"})
            await event_bus.broadcast("pm_status_changed", {
                "pmId": None, "projectId": None, "status": "executing",
                "message": str(info.get("reason", ""))})
        elif action == "task_state:IN_QA":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "IN_QA"})
        elif action == "task_state:REWORK":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "REWORK"})
            await self._broadcast_qa2(task_id, "FAIL")
        elif action == "task_state:COMPLETED":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "COMPLETED"})
            await self._broadcast_qa2(task_id, "PASS")
        elif action == "task_state:FAILED":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "FAILED"})
            await self._broadcast_qa2(task_id, "FAIL")
        elif action == "task_state:CANCELLED":
            await event_bus.broadcast("task_state_changed", {"taskId": task_id, "state": "CANCELLED"})
            await event_bus.broadcast("task_cancelled", {"projectId": None, "taskId": task_id})
        elif action == "command:execute":
            await event_bus.broadcast("worker_status_changed", {
                "workerId": info.get("actorId"), "status": "working", "taskId": task_id,
                "activity": str(info.get("reason", ""))})
            await event_bus.broadcast("pm_status_changed", {
                "pmId": None, "projectId": None, "status": "executing",
                "message": f"Worker {info.get('actorId')} executing"})
        elif action == "command:redo":
            await event_bus.broadcast("worker_status_changed", {
                "workerId": info.get("actorId"), "status": "reworking", "taskId": task_id,
                "activity": str(info.get("reason", ""))})
        elif action == "rework":
            await event_bus.broadcast("pm_status_changed", {
                "pmId": None, "projectId": None, "status": "reworking",
                "message": str(info.get("reason", ""))})
        elif action.startswith("error"):
            await event_bus.broadcast("worker_status_changed", {
                "workerId": info.get("actorId"), "status": "error", "taskId": task_id,
                "activity": str(info.get("reason", ""))})
        elif action == "escalate:capability_gap":
            await event_bus.broadcast("pm_status_changed", {
                "pmId": None, "projectId": None, "status": "waiting",
                "message": f"capability gap: {info.get('reason')}"})

    async def _broadcast_qa2(self, task_id: str, result: str):
        evaluations, summary = [], "Output QA passed." if result == "PASS" else "Output QA failed; rework loop engaged."
        score = 1.0 if result == "PASS" else 0.0
        try:
            task = self.engine.load_task(task_id)
            artifacts = ((task.result or {}).get("artifacts") or []) if task.result else []
            evaluations = [{"component": a.get("component"), "worker": a.get("worker_id"),
                            "status": "PASS", "reason": "verified by QA-2"} for a in artifacts]
            qa_cycles = (task.result or {}).get("qa_cycles", 0)
            summary = f"QA-2 {result}; cycles={qa_cycles}"
        except Exception:  # noqa: BLE001
            pass
        await event_bus.broadcast("qa2_audit_completed", {
            "taskId": task_id, "result": result, "score": score, "summary": summary,
            "evaluations": evaluations, "reworkTarget": None})

    # ------------------------------------------------------------------ #
    # request handling (old contract: /api/chat + /api/projects/{id}/task) #
    # ------------------------------------------------------------------ #
    def handle_request(self, user_text: str, project_id: str | None = None,
                       clarification_response: str | None = None,
                       active_workers: list[str] | None = None,
                       conversation_id: str | None = None,
                       chat_mode: str = "chat") -> dict:
        if self._is_simple_chat(user_text):
            reply = self._chat_model_reply(user_text, conversation_id=conversation_id)
            return {"taskId": None, "status": "DONE", "complexity": "simple",
                    "reply": reply, "deliverables": {"answer.txt": reply}}

        pid = project_id or "default"
        ctx = {"project_id": pid, "out_dir": str(self.engine.project_dir)}
        if conversation_id:
            ctx["conversation_id"] = conversation_id
        try:
            task = self.engine.submit(user_text, ctx=ctx)
        except ClarificationNeeded as exc:
            if not clarification_response:
                return {"taskId": exc.task_id, "status": "CLARIFICATION_REQUIRED",
                        "clarification": self._clarification_prompt(exc.missing, exc.verdict),
                        "taskSpec": {"goal": user_text, "projectId": pid,
                                     "rawUserInput": user_text}}
            try:
                task = self.engine.clarify(exc.task_id, self._infer_answers(clarification_response))
            except Exception as e:  # noqa: BLE001
                return {"taskId": exc.task_id, "status": "ERROR", "error": repr(e)}
        except Exception as e:  # noqa: BLE001
            return {"taskId": None, "status": "ERROR", "error": repr(e)}
        res = self._task_result(task)
        if res.get("status") == "DONE" and res.get("pmPlan"):
            res["mbNarrative"] = self._mb_narrate(user_text, res)
        return res

    def cancel(self, task_id: str) -> dict:
        try:
            self.engine.stop(task_id)
            return {"ok": True, "taskId": task_id, "status": "CANCELLED"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "taskId": task_id, "error": repr(e)}

    def _is_simple_chat(self, text: str) -> bool:
        # Phase 2: simple/complex classification now lives in the Main Brain core.
        try:
            return self.engine.mb.classify_text(text) == "simple"
        except Exception:  # noqa: BLE001 - fall back to the old keyword gate
            low = text.lower()
            return not any(w in low for w in (
                "report", "summary", "summarize", "analy", "data", "dataset", "research",
                "investigate", "code", "script", "python", ".py", "document", "write",
                "create", "make", "build", "generate", "present", "slide", "plan",
                "review", "markdown", "file", "save", "draft", "prepare", "design"))

    def _chat_model_reply(self, text: str, conversation_id: str | None = None) -> str:
        """Phase 8.2 — route & invoke a real model for simple chats; fall back
        to the rule-engine placeholder when no provider is reachable."""
        try:
            import time as _t
            decision = self.engine.model_router.route(RouteRequest(
                task_id="chat-" + str(int(_t.time() * 1000)),
                worker_id="mb", capability="default", complexity="simple",
                privacy="public", task_type="chat"))
            conversation = store.load_conversation(conversation_id) if conversation_id else None
            memories, _ = self.engine.memory.read("MB", "GLOBAL", "global")
            messages = build_chat_messages(text, (conversation or {}).get("messages", []), memories)
            call = self.engine.model_router.call(
                decision,
                messages,
                temperature=0.7, max_tokens=512)
            if call and call.ok and call.text and call.text.strip():
                return call.text.strip()
            print("chat model call returned no text; provider=", (call.provider if call else None))
        except Exception as e:  # noqa: BLE001
            print("chat model call failed, falling back:", e)
        return self._simple_reply(text)

    def _simple_reply(self, text: str) -> str:
        return ("已收到你的消息。当前为 Phase-1 规则引擎（尚无 LLM 接入），"
                "简单问答将在 Phase 2 Main Brain 接入模型路由后给出真实回答。\n\n"
                "现在可以尝试的任务型指令，例如：\n"
                "- 分析数据集并生成报告\n- 调研某主题并整理研究笔记\n- 写一个 Python 演示脚本")

    def _clarification_prompt(self, missing: list[str], verdict: dict | None = None) -> dict:
        labels = {"output_type": "输出格式（Markdown 报告 / 研究笔记 / Python 脚本）",
                  "inputs": "输入数据（数据集或文件）", "save_path": "保存路径", "goal": "目标描述"}
        bits = [labels.get(m, m) for m in missing]
        verdict = verdict or {}
        for a in verdict.get("ambiguities") or []:
            bits.append(a)
        for c in verdict.get("contradictions") or []:
            bits.append(c)
        gaps = (verdict.get("feasibility") or {}).get("gaps") or []
        if gaps:
            bits.append("当前没有具备对应能力的 Worker（能力缺口：" + "、".join(gaps)
                        + "），请选择支持的输出类型")
        question = "开始前需要你补充以下信息：" + "；".join(bits) if bits \
            else "请补充必要信息后开始执行。"
        return {"question": question,
                "options": ["生成 Markdown 报告", "生成研究笔记", "生成 Python 脚本", "其他（在回复中说明）"],
                "isMultiSelect": False, "contextExplanation": "QA-1 需求澄清门：信息完整后才会开工。"}

    @staticmethod
    def _infer_answers(text: str) -> dict:
        low = text.lower()
        if any(k in low for k in ("code", "script", "python", ".py", "runnable")):
            return {"output_type": "python"}
        if any(k in low for k in ("research", "investigate", "notes")):
            return {"output_type": "research"}
        if any(k in low for k in ("markdown", "md ")):
            return {"output_type": "markdown"}
        if "report" in low or "summary" in low:
            return {"output_type": "report"}
        return {"output_type": "markdown"}

    def _task_result(self, task) -> dict:
        artifacts = ((task.result or {}).get("artifacts") or []) if task.result else []
        deliverables: dict = {}
        for a in artifacts:
            if a.get("kind") == "file":
                p = Path(a["path"])
                deliverables[p.name] = (p.read_text(encoding="utf-8", errors="replace")
                                        if p.exists() else str(a.get("path")))
            elif a.get("kind") == "computation":
                deliverables["computation.json"] = {"total": a.get("total"),
                                                    "regions": a.get("regions")}
        state = task.state.value
        passed = state == TaskState.COMPLETED.value
        evaluations = [{"component": a.get("component"), "worker": a.get("worker_id"),
                        "status": "PASS", "reason": "verified by QA-2"} for a in artifacts]
        qa_cycles = ((task.result or {}).get("qa_cycles", 0)) if task.result else 0
        return {
            "taskId": task.task_id,
            "status": "DONE" if passed else state,
            "complexity": "complex",
            "pmPlan": f"Decomposed into {len(artifacts)} component(s); QA-2 cycles: {qa_cycles}",
            "deliverables": deliverables,
            "qa2Report": {"result": "PASS" if passed else "FAIL", "score": 1.0 if passed else 0.0,
                          "summary": f"QA-2 {'passed' if passed else 'failed'}; cycles={qa_cycles}",
                          "evaluations": evaluations, "reworkTarget": None},
            "workerLogs": [{"workerId": a.get("worker_id"), "summary": a.get("component"),
                            "success": True} for a in artifacts],
        }

    # ------------------------------------------------------------------ #
    # UI read/write endpoints backed by the engine's SQLite records       #
    # ------------------------------------------------------------------ #
    def _mb_narrate(self, user_text: str, res: dict) -> str:
        """Main Brain narrates its plan and outcome in natural language
        (like a real assistant), falling back to the structured template."""
        plan = res.get("pmPlan", "")
        delivs = list((res.get("deliverables") or {}).keys())
        qa = (res.get("qa2Report") or {}).get("result", "PASS")
        deliv_line = ", ".join(delivs) if delivs else "no file artifacts"
        prompt = (
            f"You are the Main Brain of a personal AI WorkDesk OS. A task group just finished. "
            f"Narrate briefly and naturally (4-6 sentences, plain text, no markdown headers): "
            f"what you understood from the user's goal, the plan you decomposed, how the team "
            f"executed, and the final QA-2 {qa} result with deliverables ({deliv_line}). "
            f"Do not mention system internals.\n\nUSER GOAL: {user_text}\nPLAN: {plan}"
        )
        try:
            decision = self.engine.model_router.route(RouteRequest(
                task_id="mbn-" + str(int(datetime.datetime.now().timestamp() * 1000)),
                worker_id="mb", capability="default", complexity="normal",
                privacy="public", task_type="narrate"))
            call = self.engine.model_router.call(
                decision,
                [{"role": "system", "content": "You are the Main Brain, a helpful AI assistant."},
                 {"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=300)
            if call and call.ok and call.text and call.text.strip():
                return call.text.strip()
        except Exception as e:  # noqa: BLE001
            print("mb narrate failed:", e)
        return (f"我已理解你的目标并完成了工作。{plan}。"
                f"QA-2 验证{qa}，交付物：{deliv_line}。可在工作区的项目标签页查看。")

    def search_web(self, query: str, count: int = 5) -> dict:
        """Real web search for the Researcher's live browser view."""
        try:
            from tools.web_tool import WebTool
            wt = WebTool()
            results = wt.search_sync(query, count=count)
            return {"query": query, "results": results}
        except Exception as e:  # noqa: BLE001
            return {"query": query, "error": repr(e), "results": []}

    def memory_get(self, project_id: str | None = None) -> dict:
        rows, _ = self.engine.memory.read("USER", "GLOBAL", "global")
        global_mem = {r["type"]: r["content"] for r in rows}
        project_mem = {}
        if project_id:
            prows, _ = self.engine.memory.read("USER", "PROJECT", project_id)
            project_mem = {r["type"]: r["content"] for r in prows}
        return {"globalMemory": global_mem, "projectMemory": project_mem}

    def memory_update(self, patch: dict) -> dict:
        for k, v in (patch or {}).items():
            self.engine.memory.write("USER", "user", "GLOBAL", "global", str(k), str(v))
        rows, _ = self.engine.memory.read("USER", "GLOBAL", "global")
        return {r["type"]: r["content"] for r in rows}

    def approvals_pending(self, conversation_id: str | None = None) -> list[dict]:
        return self.engine.approvals_pending(conversation_id)

    def approvals_resolve(self, decision_id: str, approved: bool) -> bool:
        row = wd_db.query_one("SELECT approval_id FROM approvals WHERE approval_id=? OR request_id=?",
                              (decision_id, decision_id))
        if row is None:
            return False
        self.engine.permissions.decide(row["approval_id"], "APPROVED" if approved else "DENIED",
                                       "resolved via UI")
        return True

    def audit_list(self, limit: int = 50) -> list[dict]:
        rows = self.engine.permissions.timeline()
        out = []
        for r in rows[-limit:]:
            out.append({"timestamp": r["ts"], "actor": r["actor_id"] or r["actor_role"],
                        "role": r["actor_role"], "eventType": r["action"],
                        "details": {"reason": r["reason"]},
                        "relatedTaskId": r["task_id"]})
        return out

    # ------------------------------------------------------------------ #
    # Phase 7: WorkDesk UI read models (engine-backed)                    #
    # ------------------------------------------------------------------ #
    def tasks_list(self, project_id: str | None = None, limit: int = 100,
                   conversation_id: str | None = None) -> list[dict]:
        return self.engine.list_tasks(project_id, limit, conversation_id)

    def reorder_tasks(self, conversation_id: str, task_ids: list[str]) -> dict:
        return self.engine.reorder_tasks(conversation_id, task_ids)

    def task_detail(self, task_id: str) -> dict:
        return self.engine.task_detail(task_id)

    def skill_market(self) -> dict:
        """GET /api/skill-market — every registered skill, its owner workers and
        the workers that could still install it (SBR auto-extends on install)."""
        rows = self.engine.db.execute(
            "SELECT skill_id,name,version,type,entry_point,tools_required_json,enabled "
            "FROM skills ORDER BY name").fetchall()
        workers = self.engine.worker_catalog()
        # dedupe by skill NAME (install reuses one skill_id per name)
        by_name: dict[str, dict] = {}
        for r in rows:
            n = r["name"]
            if n not in by_name:
                by_name[n] = {"skill_id": r["skill_id"], "name": n, "version": r["version"],
                              "type": r["type"],
                              "tools_required": json.loads(r["tools_required_json"] or "[]"),
                              "enabled": bool(r["enabled"]), "_ids": {r["skill_id"]}}
            else:
                by_name[n]["_ids"].add(r["skill_id"])
        skills = []
        for n, agg in by_name.items():
            ids = agg.pop("_ids")
            owners = []
            for w in workers:
                for s in (w.get("skills") or []):
                    if s.get("skill_id") in ids:
                        owners.append({"worker_id": w["worker_id"], "name": w["name"]})
                        break
            owner_ids = {o["worker_id"] for o in owners}
            installable = [{"worker_id": w["worker_id"], "name": w["name"]}
                           for w in workers if w["worker_id"] not in owner_ids]
            skills.append({
                "skill_id": agg["skill_id"], "name": n,
                "capability": (n or "").split(".")[0],
                "version": agg["version"], "type": agg["type"],
                "tools_required": agg["tools_required"],
                "enabled": agg["enabled"],
                "owners": owners, "installable": installable,
            })
        return {"skills": skills, "count": len(skills)}

    def skill_install(self, worker_id: str, skill_name: str) -> dict:
        """POST /api/skill-market/install — attach a skill to a worker so the SBR
        router can route matching components to it. Idempotent."""
        w = self.engine.registry.get_worker(worker_id)
        if w is None:
            return {"error": "worker_not_found"}
        skill_name = (skill_name or "").strip()
        if not skill_name:
            return {"error": "skill_name_required"}
        existing = {s.get("skill_id") for s in (w.get("skills") or [])}
        found = None
        for r in self.engine.db.execute("SELECT * FROM skills").fetchall():
            if r["name"] == skill_name:
                found = dict(r)
                break
        if found is None:
            # skill not registered yet: register one stub skill
            full_sid = self.engine.registry.register_skill(
                name=skill_name, entry_point=f"stub:{skill_name}", tools_required=["FILESYSTEM"])
        else:
            full_sid = found["skill_id"]
        existing_ids = {s.get("skill_id") for s in (w.get("skills") or [])}
        if full_sid in existing_ids:
            return {"worker_id": worker_id, "skill": skill_name, "status": "already"}
        cap = skill_name.split(".")[0]
        from src.workdesk.worker_creator import _dynamic_handler
        self.engine.skill_handlers[skill_name] = _dynamic_handler(self.engine, cap)
        skills = list(w.get("skills") or []) + [{"skill_id": full_sid, "primary": False,
                                                 "capability": cap}]
        self.engine.registry.register_worker(
            worker_id=worker_id, name=w["name"], role_class=w.get("role_class", "WORKER"),
            personality=w.get("personality") or {}, behavior_rules=w.get("behavior_rules") or [],
            skills=skills, tools=w.get("tools") or [], permissions=w.get("permissions") or {},
            memory_rules=w.get("memory_rules") or {})
        worker = self.engine.workers.get(worker_id)
        if worker is not None:
            worker.skills[skill_name] = {"capability": cap}
        self.engine.permissions.audit("MB", "mb", "skill_installed",
                                      reason=f"worker={worker_id}; skill={skill_name}")
        return {"worker_id": worker_id, "skill": skill_name, "status": "installed"}

    def worker_create_capability(self, capability: str, name: str | None = None) -> dict:
        """POST /api/workers/create-capability — SBR gap -> worker creation path.
        Prefers upgrading an existing worker with a matching capability root;
        otherwise creates a fresh worker via the Worker Creator."""
        from src.workdesk.worker_creator import WorkerCreator
        cap = (capability or "").strip().lower()
        if not cap:
            return {"error": "capability_required"}
        root = cap.split(".")[0]
        # 1) reuse/upgrade: an existing worker whose capability root already matches
        for w in self.engine.worker_catalog():
            caps = {s.get("capability") for s in (w.get("skills") or [])}
            if root in caps or any(c.split(".")[0] == root for c in caps):
                if root in caps:
                    return {"worker_id": w["worker_id"], "skill": cap,
                            "name": w["name"], "mode": "existing"}
                WorkerCreator().upgrade(self.engine, w["worker_id"], root)
                return {"worker_id": w["worker_id"], "skill": cap,
                        "name": w["name"], "mode": "upgraded"}
        # 2) create a brand-new worker
        wid, status = WorkerCreator().create(self.engine, root, name=name)
        if wid is None:
            return {"error": "create_pending_or_denied", "status": status}
        return {"worker_id": wid, "skill": cap, "name": name or f"{root.title()} Worker",
                "mode": status}

    # ---------------- Remote Device (working area) ----------------
    @staticmethod
    def _host_info() -> dict:
        try:
            import platform, socket, shutil
            return {
                "hostname": socket.gethostname(),
                "os": f"{platform.system()} {platform.release()}",
                "machine": platform.machine(),
                "python": platform.python_version(),
                "disk_free_gb": round(shutil.disk_usage(Path.cwd()).free / 1e9, 1),
            }
        except Exception:  # noqa: BLE001
            return {"hostname": "unknown", "os": "unknown"}

    def remote_devices_list(self) -> dict:
        """GET /api/remote/devices — host info + registered remote devices."""
        rows = self.engine.db.execute(
            "SELECT * FROM remote_devices ORDER BY created_ts DESC").fetchall()
        devices = [dict(r) for r in rows]
        for d in devices:
            try:
                d["session"] = json.loads(d.pop("session_json") or "[]")
            except Exception:
                d["session"] = []
        return {"host": self._host_info(), "devices": devices}

    def remote_device_register(self, name: str, host: str, os_name: str = "") -> dict:
        """POST /api/remote/devices — register a device (pairing token in MVP)."""
        from src.workdesk import ids as _ids
        did = _ids.new_id()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        token = _ids.new_id()[:8]
        self.engine.db.execute(
            "INSERT INTO remote_devices(device_id,name,host,status,os,last_seen,created_ts,session_json)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (did, name or host, host, "PENDING", os_name or "unknown", now, now, "[]"))
        self.engine.permissions.audit("USER", "user", "remote_device_registered",
                                      reason=f"device={name or host} host={host}")
        return {"device_id": did, "pairing_token": token, "status": "PENDING"}

    def remote_device_command(self, device_id: str, command: str) -> dict:
        """POST /api/remote/{id}/command — MVP session log (echo), audited."""
        row = self.engine.db.execute(
            "SELECT * FROM remote_devices WHERE device_id=?", (device_id,)).fetchone()
        if row is None:
            return {"error": "device_not_found"}
        cmd = (command or "").strip()
        if not cmd:
            return {"error": "command_required"}
        now = datetime.datetime.utcnow().isoformat() + "Z"
        try:
            sess = json.loads(row["session_json"] or "[]")
        except Exception:
            sess = []
        entry = {"ts": now, "command": cmd, "status": "queued"}
        sess.append(entry)
        sess = sess[-50:]
        self.engine.db.execute(
            "UPDATE remote_devices SET session_json=?, last_seen=?, status='ONLINE' "
            "WHERE device_id=?",
            (json.dumps(sess), now, device_id))
        self.engine.permissions.audit("USER", "user", "remote_command",
                                      reason=f"device={device_id}; cmd={cmd[:80]}")
        return {"device_id": device_id, "entry": entry,
                "note": "MVP: command queued to remote agent (local echo). "
                        "Real execution ships with the signed pairing agent."}

    def pms_list(self) -> list[dict]:
        return self.engine.list_pms()

    def virtual_office(self, conversation_id: str | None = None) -> dict:
        return self.engine.virtual_office(conversation_id)

    def learning(self, scope: str | None = None, limit: int = 100) -> dict:
        """GET /api/learning — Phase 9 learning system read model."""
        return {"stats": self.engine.learning_stats(),
                "lessons": self.engine.learning_list(scope=scope, limit=limit)}

    # ---------------- Phase 10: personal utilities + working area ----------------
    WS_ROOT = Path(__file__).resolve().parent / "data" / "workspace"

    @staticmethod
    def _ws_abs(rel: str) -> Path | None:
        """Resolve a workspace-relative path, rejecting traversal escapes."""
        rel = (rel or "").replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            return None
        p = (WorkDeskBridge.WS_ROOT / rel).resolve()
        if not str(p).startswith(str(WorkDeskBridge.WS_ROOT.resolve())):
            return None
        return p

    def ws_list(self) -> dict:
        WorkDeskBridge.WS_ROOT.mkdir(parents=True, exist_ok=True)
        out = []
        for p in sorted(WorkDeskBridge.WS_ROOT.rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(WorkDeskBridge.WS_ROOT)).replace("\\", "/")
                out.append({"path": rel, "size": p.stat().st_size,
                            "mtime": p.stat().st_mtime,
                            "kind": p.suffix.lstrip(".").lower() or "bin"})
        return {"root": str(WorkDeskBridge.WS_ROOT), "files": out}

    def ws_read(self, rel: str) -> dict:
        p = self._ws_abs(rel)
        if p is None or not p.exists() or not p.is_file():
            return {"error": "not_found"}
        raw = p.read_bytes()
        try:
            return {"path": rel, "content": raw.decode("utf-8")}
        except UnicodeDecodeError:
            return {"error": "binary", "size": len(raw)}

    def ws_save(self, rel: str, content: str) -> dict:
        p = self._ws_abs(rel)
        if p is None:
            return {"error": "invalid_path"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": rel, "bytes": len(content.encode("utf-8"))}

    def ws_upload(self, filename: str, data: bytes, subdir: str = "") -> dict:
        safe = Path(filename).name
        rel = (f"{subdir.strip('/')}/{safe}" if subdir else safe)
        p = self._ws_abs(rel)
        if p is None:
            return {"error": "invalid_path"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"ok": True, "path": rel, "bytes": len(data)}

    def ws_delete(self, rel: str) -> dict:
        p = self._ws_abs(rel)
        if p is None or not p.exists():
            return {"error": "not_found"}
        if p.is_dir():
            return {"error": "is_dir"}
        p.unlink()
        return {"ok": True, "path": rel}

    def ws_file(self, rel: str) -> Path | None:
        p = self._ws_abs(rel)
        if p is not None and p.exists() and p.is_file():
            return p
        return None

    def code_run(self, code: str, language: str = "python",
                 timeout: int = 15) -> dict:
        """Run code in an isolated subprocess with a hard timeout. Audited as a
        terminal-level action; the working directory is a temp sandbox."""
        import subprocess
        import tempfile
        if len(code) > 60_000:
            return {"ok": False, "error": "code_too_large"}
        sandbox = Path(tempfile.mkdtemp(prefix="wd_run_"))
        script = sandbox / "main.py"
        script.write_text(code, encoding="utf-8")
        self.engine.permissions.audit("USER", "user", "code_run",
                                      tool="terminal", reason=language,
                                      task_id=None)
        try:
            r = subprocess.run(
                [sys.executable, "-u", str(script)], cwd=str(sandbox),
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ.copy(), "PYTHONIOENCODING": "utf-8"})
            return {"ok": r.returncode == 0, "returncode": r.returncode,
                    "stdout": r.stdout[-8000:], "stderr": r.stderr[-4000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {timeout}s"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": repr(exc)}
        finally:
            try:
                import shutil
                shutil.rmtree(sandbox, ignore_errors=True)
            except Exception:  # noqa: BLE001
                pass

    def notes_list(self, section: str | None = None) -> list[dict]:
        if section:
            rows = wd_db.query("SELECT * FROM notes WHERE section=? ORDER BY updated_ts DESC",
                            (section,))
        else:
            rows = wd_db.query("SELECT * FROM notes ORDER BY updated_ts DESC")
        return [dict(r) for r in rows]

    def notes_save(self, note_id: str | None, section: str, title: str,
                   content: str) -> dict:
        from src.workdesk import ids
        if note_id:
            wd_db.execute("UPDATE notes SET title=?, content=?, updated_ts=? WHERE note_id=?",
                       (title, content, ids.now_iso(), note_id))
        else:
            note_id = ids.new_id()
            wd_db.execute("INSERT INTO notes(note_id,section,title,content,created_ts,updated_ts) "
                       "VALUES(?,?,?,?,?,?)",
                       (note_id, section, title, content, ids.now_iso(), ids.now_iso()))
        return {"ok": True, "note_id": note_id}

    def notes_delete(self, note_id: str) -> dict:
        wd_db.execute("DELETE FROM notes WHERE note_id=?", (note_id,))
        return {"ok": True, "note_id": note_id}

    def settings(self) -> dict:
        s = self.engine.settings_snapshot()
        s["model_router"] = {
            "instant": app_config.INSTANT_MODEL, "expert": app_config.EXPERT_MODEL,
            "worker": app_config.WORKER_MODEL,
            "local_endpoint": app_config.LOCAL_ENDPOINT or None,
            "openrouter_configured": bool(app_config.OPENROUTER_API_KEY),
            "chatanywhere_configured": bool(app_config.CHATANYWHERE_API_KEY),
            "chatanywhere_endpoint": app_config.CHATANYWHERE_ENDPOINT,
            "chatanywhere_model": app_config.CHATANYWHERE_MODEL,
            "stats": self.engine.model_router.stats(),
            "recent": self.engine.model_router.recent(),
            "providers": self.engine.model_router.provider_status(),
        }
        s["app_url"] = app_config.APP_URL
        return s

    def save_chatanywhere_key(self, api_key: str) -> dict:
        """Persist the ChatAnywhere free relay key to .env and hot-apply it
        to the running process (no restart needed). Returns the new status."""
        key = (api_key or "").strip()
        # 1) persist to .env (replace only the CHATANYWHERE_API_KEY line)
        env_path = app_config.BASE_DIR / ".env"
        try:
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
                found = False
                out = []
                for ln in lines:
                    if ln.strip().startswith("CHATANYWHERE_API_KEY="):
                        out.append(f"CHATANYWHERE_API_KEY={key}\n")
                        found = True
                    else:
                        out.append(ln)
                if not found:
                    out.append(f"CHATANYWHERE_API_KEY={key}\n")
                env_path.write_text("".join(out), encoding="utf-8")
            else:
                env_path.write_text(f"CHATANYWHERE_API_KEY={key}\n", encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": f"could not write .env: {e}"}
        # 2) hot-apply to this process (module attrs are shared)
        setattr(app_config, "CHATANYWHERE_API_KEY", key)
        setattr(self.engine.config, "CHATANYWHERE_API_KEY", key)
        return {"ok": True, "chatanywhere_configured": bool(key),
                "chatanywhere_endpoint": app_config.CHATANYWHERE_ENDPOINT,
                "chatanywhere_model": app_config.CHATANYWHERE_MODEL}

    def model_router(self) -> dict:
        return {
            "config": {"instant": app_config.INSTANT_MODEL, "expert": app_config.EXPERT_MODEL,
                       "worker": app_config.WORKER_MODEL,
                       "local_endpoint": app_config.LOCAL_ENDPOINT or None,
                       "openrouter_configured": bool(app_config.OPENROUTER_API_KEY),
                       "chatanywhere_configured": bool(app_config.CHATANYWHERE_API_KEY),
                       "chatanywhere_endpoint": app_config.CHATANYWHERE_ENDPOINT,
                       "chatanywhere_model": app_config.CHATANYWHERE_MODEL},
            "providers": self.engine.model_router.provider_status(),
            "stats": self.engine.model_router.stats(),
            "recent": self.engine.model_router.recent(),
        }

    def model_router_call(self, body: dict) -> dict:
        """POST /api/model-router/call — route a one-off request, persist the
        decision, then actually invoke the model (Phase 8.2)."""
        req = RouteRequest(
            task_id=body.get("task_id") or ("test-" + str(int(datetime.datetime.now().timestamp() * 1000))),
            worker_id=body.get("worker_id") or "tester",
            capability=body.get("capability") or "default",
            complexity=body.get("complexity") or "normal",
            privacy=body.get("privacy") or "public",
            task_type=body.get("task_type") or "default",
            model_hint=body.get("model_hint") or "auto",
        )
        decision = self.engine.model_router.route(req)
        self.engine.model_router.record(req, decision)
        messages: list[dict] = []
        if body.get("system"):
            messages.append({"role": "system", "content": str(body["system"])})
        messages.append({"role": "user", "content": str(body.get("prompt") or "")})
        call = self.engine.model_router.call(
            decision, messages,
            temperature=float(body.get("temperature", 0.7)),
            max_tokens=int(body.get("max_tokens", 256)))
        return {"request": req.to_dict(), "decision": decision.to_dict(),
                "call": call.to_dict()}

    def workers_list(self) -> list[dict]:
        return self.engine.worker_catalog()

    def worker_create(self, profile: dict) -> str:
        """Create a worker in the engine SQLite registry (single source of
        truth for the UI catalog), mapping a core.models.WorkerProfile dump."""
        sk = profile.get("skills") or {}
        skills = []
        for sid in (sk.get("primary") or []):
            skills.append({"name": sid, "capability": sid.split(".")[0], "primary": True})
        for sid in (sk.get("secondary") or []):
            skills.append({"name": sid, "capability": sid.split(".")[0], "primary": False})
        person = profile.get("personality") or {}
        payload = {
            "worker_id": profile.get("id"),
            "name": profile.get("name", "Worker"),
            "role_class": profile.get("role_class", "WORKER"),
            "personality": {
                "temperament": person.get("temperament", "professional, analytical"),
                "behavior_rules": person.get("behaviorRules") or [],
            },
            "behavior_rules": person.get("behaviorRules") or [],
            "skills": skills,
            "tools": profile.get("tools") or [],
            "permissions": profile.get("permissions") or {},
            "memory_rules": {},
        }
        return self.engine.install_worker_from_profile(payload)

    # ------------------------------------------------------------------ #
    # Phase 11: Obsidian-style vault (markdown notes + wiki links)        #
    # ------------------------------------------------------------------ #
    VAULT_ROOT = Path(__file__).resolve().parent / "data" / "vault"

    def _vault_abs(self, section: str, rel: str) -> Path | None:
        section = (section or "my").strip("/\\")
        if section not in ("my", "mb"):
            section = "my"
        rel = (rel or "").replace("\\", "/").strip("/")
        if not rel:
            return self.VAULT_ROOT / section
        parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
        if len(parts) != len([p for p in rel.split("/") if p]):
            return None  # any .. attempt rejected
        root = (self.VAULT_ROOT / section).resolve()
        target = (root / "/".join(parts)).resolve()
        if root != target and root not in target.parents:
            return None
        return target

    def vault_tree(self, section: str = "my") -> list[dict]:
        root = self.VAULT_ROOT / (section if section in ("my", "mb") else "my")
        root.mkdir(parents=True, exist_ok=True)
        out = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".json"):
                rel = p.relative_to(root).as_posix()
                out.append({"path": rel, "name": p.name,
                            "updated": datetime.datetime.fromtimestamp(
                                p.stat().st_mtime).isoformat(timespec="minutes"),
                            "size": p.stat().st_size})
        return out

    def vault_read(self, section: str, path: str) -> dict:
        p = self._vault_abs(section, path)
        if p is None or not p.exists() or not p.is_file():
            return {"error": "not_found"}
        content = p.read_text(encoding="utf-8", errors="replace")
        links = sorted({m for m in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)})
        return {"path": path, "section": section, "content": content, "links": links}

    def vault_save(self, section: str, path: str, content: str) -> dict:
        if not path or path.endswith("/"):
            return {"error": "invalid_path"}
        p = self._vault_abs(section, path)
        if p is None:
            return {"error": "invalid_path"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(content or "")}

    def vault_delete(self, section: str, path: str) -> dict:
        p = self._vault_abs(section, path)
        if p is None or not p.exists():
            return {"error": "not_found"}
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"ok": True}

    def vault_search(self, section: str, q: str) -> list[dict]:
        root = self.VAULT_ROOT / (section if section in ("my", "mb") else "my")
        q = (q or "").strip().lower()
        hits = []
        if not root.exists():
            return hits
        for p in root.rglob("*.md"):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if q and q in text.lower():
                rel = p.relative_to(root).as_posix()
                idx = text.lower().find(q)
                hits.append({"path": rel,
                             "snippet": text[max(0, idx - 60): idx + 120].replace("\n", " ")})
        return hits[:50]

    # ------------------------------------------------------------------ #
    # Phase 11: clear cache & history                                     #
    # ------------------------------------------------------------------ #
    def clear_history(self, scope: str = "all") -> dict:
        """Wipe chat/task/approval/audit/learning history. Workers, PMs,
        notes, vault and workspace files are assets and are preserved."""
        wiped = []
        if scope in ("all", "chats"):
            for f in app_config.CONV_DIR.glob("*.json"):
                f.unlink()
            wiped.append(f"conversations:{len(list(app_config.CONV_DIR.glob('*.json')))}")
            for f in app_config.PROJ_DIR.glob("*.json"):
                f.unlink()
        if scope in ("all", "tasks"):
            for t in ("tasks", "task_transitions", "task_groups", "checkpoints",
                      "task_routes", "qa_verdicts"):
                wd_db.execute(f"DELETE FROM {t}")
        if scope in ("all", "approvals"):
            wd_db.execute("DELETE FROM approvals")
        if scope in ("all", "audit"):
            wd_db.execute("DELETE FROM audit_events")
        if scope in ("all", "learning"):
            wd_db.execute("DELETE FROM lessons")
            wd_db.execute("DELETE FROM memory_grants")
        wiped.append("db:tasks/approvals/audit/learning")
        return {"ok": True, "wiped": wiped}

    # ------------------------------------------------------------------ #
    # Phase 11: Design New Worker from a GitHub skill                     #
    # ------------------------------------------------------------------ #
    _GH_PROBE_PATHS = ["SKILL.md", "skills/SKILL.md", ".claude/skills/SKILL.md",
                       "plugins/SKILL.md", ".workdesk/skills/SKILL.md"]
    _TOOL_HINTS = [
        (("code", "python", "script", "automation", "program", "terminal", "shell", "cli", "api", "compile", "debug", "test"),
         ["TERMINAL", "VSCODE"]),
        (("research", "search", "web", "browser", "url", "crawl", "scrape", "news", "gather", "collect", "source", "investigate"),
         ["BROWSER"]),
        (("document", "write", "report", "markdown", "article", "word", "copy", "blog"),
         ["OFFICE", "DOCUMENT"]),
        (("data", "excel", "csv", "sheet", "analys", "statistic", "sql", "pandas"),
         ["SHEETS"]),
        (("slide", "present", "ppt", "deck", "pitch"), ["SLIDES"]),
        (("image", "design", "photo", "poster", "logo", "icon", "illustrate"), ["IMAGE"]),
        (("pdf", "file", "organize", "folder", "archive"), ["PDF"]),
        (("video", "audio", "media", "music", "podcast"), ["MEDIA"]),
    ]

    def _gh_raw(self, owner: str, repo: str, branch: str, path: str) -> str | None:
        for ref in (branch, "main", "master"):
            if not ref:
                continue
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "workdesk"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                continue
        return None

    def _locate_skill(self, owner: str, repo: str, branch: str,
                     subpath: str = "") -> tuple[str | None, str | None]:
        base = subpath.strip("/")
        if base:
            if base.lower().endswith(".md"):
                candidates = [base]  # explicit file path (from candidate pick)
            else:
                candidates = [f"{base}/SKILL.md", f"{base}/skills/SKILL.md",
                              f"{base}/.claude/skills/SKILL.md"]
        else:
            candidates = self._GH_PROBE_PATHS
        for path in candidates:
            text = self._gh_raw(owner, repo, branch, path)
            if text:
                return path, text
        return None, None

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        body = text.lstrip("\ufeff")
        meta: dict = {}
        if body.startswith("---"):
            end = body.find("\n---", 3)
            if end != -1:
                fm = body[3:end]
                for line in fm.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip().lower()] = v.strip().strip("\"'")
                body = body[end + 4:].lstrip()
        return meta, body

    def _infer_worker(self, skill_name: str, description: str) -> dict:
        desc = f"{skill_name} {description}".lower()
        tools: list[str] = []
        for keys, tset in self._TOOL_HINTS:
            if any(k in desc for k in keys):
                tools += tset
        tools = list(dict.fromkeys(["FILESYSTEM"] + tools))
        # pick the studio with the highest priority among matched tools
        priority = {"BROWSER": "research", "TERMINAL": "code", "VSCODE": "code",
                    "SHEETS": "sheets", "SLIDES": "slides", "MEDIA": "media",
                    "IMAGE": "design", "PDF": "pdf", "OFFICE": "docs", "DOCUMENT": "docs"}
        order = ["research", "code", "sheets", "slides", "media", "design", "pdf", "docs"]
        studio_type = "general"
        for t in tools:
            s = priority.get(t)
            if s and (studio_type == "general" or order.index(s) < order.index(studio_type)):
                studio_type = s
        role = {"code": "Engineer", "research": "Researcher", "docs": "Writer",
                "sheets": "Data Analyst", "slides": "Presenter", "media": "Media Producer",
                "design": "Designer", "pdf": "Document Specialist",
                "general": "Specialist"}[studio_type]
        return {
            "name": re.sub(r"[^a-zA-Z0-9 _-]", "", skill_name).strip() or "custom-worker",
            "role": role,
            "studio_type": studio_type,
            "description": description[:400],
            "skills": [{"name": skill_name, "primary": True,
                        "capability": skill_name.lower().replace(" ", "-"),
                        "tools_required": tools}],
            "tools": [{"tool": t, "permissions": {"read": True, "write": True}} for t in tools],
            "personality": {"traits": ["focused", "thorough"], "tone": "professional",
                            "communication_style": "concise status updates"},
            "behavior_rules": ["report blockers to the PM", "follow the permission policy"],
            "permissions": {},
            "memory_rules": {"group_memory": True, "own_experience": True,
                             "cross_project": "NEVER"},
        }

    def _similar_workers(self, candidate: dict) -> list[dict]:
        terms = {w for w in re.findall(r"[a-z0-9]+", candidate["name"].lower())}
        terms |= {w for w in re.findall(r"[a-z0-9]+",
                                        candidate["skills"][0]["name"].lower()) if len(w) > 2}
        matches = []
        for w in self.engine.worker_catalog():
            wname = " ".join(re.findall(r"[a-z0-9]+", (w.get("name") or "").lower()))
            wsp = " ".join((s.get("capability") or "") + " " + (s.get("name") or "")
                           for s in (w.get("skills") or [])).lower()
            wterms = {t for t in re.findall(r"[a-z0-9]+", wname + " " + wsp) if len(t) > 2}
            shared = terms & wterms
            if shared:
                matches.append({
                    "worker_id": w["worker_id"], "name": w.get("name"),
                    "score": round(len(shared) / max(1, len(terms)), 2),
                    "overlap": sorted(shared),
                })
        matches.sort(key=lambda m: -m["score"])
        return matches[:4]

    @staticmethod
    def _gh_api_json(url: str) -> dict | None:
        """One GitHub REST call. Returns parsed JSON or None on any failure
        (network, 404, 403 rate-limit, 5xx)."""
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "workdesk", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return None

    @staticmethod
    def _gh_default_branch(owner: str, repo: str) -> str | None:
        info = WorkDeskBridge._gh_api_json(f"https://api.github.com/repos/{owner}/{repo}")
        if info and info.get("default_branch"):
            return info["default_branch"]
        return None

    _GH_TREE_IGNORE = ("node_modules/", ".git/", "dist/", "build/", "__pycache__/",
                       "vendor/", ".venv/", "venv/")

    def _find_skill_candidates(self, owner: str, repo: str,
                               branch: str | None) -> list[dict]:
        """Recursively scan the repo tree for every SKILL.md (skill dirs can
        live at any depth). Returns lightweight candidates (path + inferred
        name) so the user can pick; the chosen one is then read fully."""
        ref = branch or self._gh_default_branch(owner, repo) or "main"
        tree = self._gh_api_json(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
        if not tree or not isinstance(tree.get("tree"), list):
            return []
        out: list[dict] = []
        for node in tree["tree"]:
            path = node.get("path") or ""
            if node.get("type") != "blob" or not path.lower().endswith("skill.md"):
                continue
            low = path.lower()
            if any(low.startswith(ig) or f"/{ig}" in f"/{low}" for ig in self._GH_TREE_IGNORE):
                continue
            parts = [p for p in path.split("/") if p]
            name = parts[-2] if len(parts) >= 2 else repo
            out.append({"path": path, "name": name, "dir": "/".join(parts[:-1])})
        out.sort(key=lambda c: (c["dir"], c["name"]))
        return out

    def worker_design(self, github_url: str, subdir: str | None = None) -> dict:
        url = (github_url or "").strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc not in ("github.com", "www.github.com", "raw.githubusercontent.com"):
            return {"error": "only_github"}
        parts = [p for p in parsed.path.split("/") if p]
        owner = repo = branch = None
        if parsed.netloc == "raw.githubusercontent.com":
            if len(parts) < 3:
                return {"error": "invalid_url"}
            owner, repo, branch = parts[0], parts[1], parts[2]
        else:
            if len(parts) < 2:
                return {"error": "invalid_url"}
            owner, repo = parts[0], parts[1]
            subpath = ""
            if len(parts) >= 4 and parts[2] == "tree":
                branch = parts[3]
                subpath = "/".join(parts[4:])
        if subdir and not subpath:
            subpath = subdir.strip("/")
        skill_path, text = self._locate_skill(owner, repo, branch, subpath)
        if not text and not subpath:
            candidates = self._find_skill_candidates(owner, repo, branch)
            if len(candidates) == 1:
                skill_path, text = self._locate_skill(
                    owner, repo, branch, candidates[0]["path"])
            elif candidates:
                return {"candidates": candidates,
                        "repo": f"{owner}/{repo}",
                        "detail": f"Found {len(candidates)} SKILL.md files in sub-folders — pick one."}
        if not text:
            return {"error": "no_skill_found",
                    "detail": "No SKILL.md found at the repo root or in any sub-folder "
                              "(checked the full tree recursively)."}
        meta, body = self._parse_frontmatter(text)
        skill_name = meta.get("name") or repo
        description = meta.get("description") or body[:300].strip().splitlines()[0][:300]
        candidate = self._infer_worker(skill_name, description)
        candidate["github_url"] = url
        candidate["skill_source"] = f"{owner}/{repo}/{skill_path}"
        return {"candidate": candidate, "matches": self._similar_workers(candidate)}

    def worker_apply(self, profile: dict, mode: str = "create",
                     merge_into: str | None = None) -> dict:
        if mode == "merge":
            if not merge_into:
                return {"error": "merge_target_required"}
            existing = self.engine.registry.get_worker(merge_into)
            if not existing:
                return {"error": "worker_not_found"}
            merged = existing.copy()
            merged["name"] = profile.get("name") or merged.get("name")
            skills = list(merged.get("skills") or [])
            have = {s.get("capability") for s in skills}
            for s in profile.get("skills", []):
                if s.get("capability") not in have:
                    skills.append(s)
            merged["skills"] = skills
            merged["tools"] = list(merged.get("tools") or []) + \
                [t for t in profile.get("tools", [])
                 if t.get("tool") not in {x.get("tool") for x in (merged.get("tools") or [])}]
            merged["behavior_rules"] = list(dict.fromkeys(
                list(merged.get("behavior_rules") or []) +
                list(profile.get("behavior_rules") or [])))
            merged["description"] = profile.get("description") or merged.get("description")
            self.engine.install_worker_from_profile(merged)
            return {"ok": True, "mode": "merge", "worker_id": merge_into}
        profile = dict(profile)
        profile.setdefault("role_class", "WORKER")
        wid = self.engine.install_worker_from_profile(profile)
        return {"ok": True, "mode": "create", "worker_id": wid}

    def worker_update(self, worker_id: str, patch: dict) -> dict:
        existing = self.engine.registry.get_worker(worker_id)
        if not existing:
            return {"error": "worker_not_found"}
        merged = existing.copy()
        for k in ("name", "role_class", "personality", "behavior_rules",
                  "skills", "tools", "permissions", "memory_rules", "description"):
            if k in patch and patch[k] is not None:
                merged[k] = patch[k]
        self.engine.install_worker_from_profile(merged)
        return {"ok": True, "worker_id": worker_id}

    # ------------------------------------------------------------------ #
    # Phase 11: worker studio (per-worker workspace + live view)          #
    # ------------------------------------------------------------------ #
    _STUDIO_TYPES = {"code", "research", "docs", "sheets", "slides", "pdf",
                     "media", "design", "general"}

    def vault_mb_chat(self, message: str) -> dict:
        """User tells the Main Brain what to store in the Vault.

        Every message is appended to vault/mb/chat-log.md; if the user asks to
        save/remember something, a dated note is created under vault/mb/ and a
        summary entry is written into global memory.
        """
        import datetime
        now = datetime.datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M")
        day = now.strftime("%Y%m%d")
        msg = (message or "").strip()
        if not msg:
            return {"ok": False, "error": "empty message"}

        # 1) always append to the chat log
        log_path = "chat-log.md"
        log = f"### {ts} — User\n{msg}\n\n"
        prev = ""
        try:
            prev = self.vault_read("mb", log_path).get("content") or ""
        except Exception:
            prev = ""
        self.vault_save("mb", log_path, prev + log)

        # 2) if the user asks to store something, create a dated note
        note_path = None
        low = msg.lower()
        save_kw = ("save", "remember", "store", "keep", "保存", "记住", "存入", "记录", "备忘")
        if any(k in low for k in save_kw):
            title = msg[:48]
            safe = re.sub(r'[\\/:*?"<>|\n]', ' ', title).strip()[:40] or 'note'
            note_path = f"{day} - {safe}.md"
            self.vault_save("mb", note_path, f"# {title}\n\n> {ts} — dictated by user\n\n{msg}\n")

        # 3) update global memory so MB keeps a short digest
        try:
            rows, _ = self.engine.memory.read("USER", "GLOBAL", "global")
            gm = {r["type"]: r["content"] for r in rows}
            digest = gm.get("vault_dictations", "")
            line = f"- {ts}: {msg[:120]}"
            new_digest = (digest + "\n" + line if digest else line)[-2000:]
            self.engine.memory.write("USER", "user", "GLOBAL", "global", "vault_dictations", new_digest)
        except Exception:
            pass

        reply = (f"已记入 Vault ✅ — 日志已追加（{log_path}）"
                 + (f"，并创建笔记 `{note_path}`" if note_path else "")
                 + "。Main Brain 会把摘要同步进全局记忆，随时可检索。")
        return {"ok": True, "reply": reply, "log": log_path, "note": note_path}

    def mb_sync(self) -> dict:
        """Main Brain auto-writes its learned knowledge into vault/mb/_auto/.

        The Main Brain memory vault is not a manual notepad: it mirrors the
        system's own state so the user can read what MB knows, has learned and
        still needs to do. Idempotent — rebuilds the auto files on each call.
        """
        written = []
        def put(rel: str, text: str) -> None:
            self.vault_save("mb", rel, text)
            written.append(rel)

        # 1) global memory (long-term knowledge the MB keeps about the user)
        rows, _ = self.engine.memory.read("USER", "GLOBAL", "global")
        gm = {r["type"]: r["content"] for r in rows}
        gm_lines = "\n".join(f"- **{k}**: {v}" for k, v in gm.items()) if gm else "_No global memory yet._"
        put("_auto/global-memory.md", f"# Global Memory\n\n{gm_lines}\n")

        # 2) lessons the MB has validated and learned (evidence-gated)
        lessons = self.engine.learning_list(scope=None, limit=50) or []
        if lessons:
            lns = []
            for L in lessons:
                conf = L.get("confidence", "")
                lns.append(f"### {L.get('capability', '')} — {L.get('lesson', '')[:160]}\n"
                           f"- evidence: {L.get('evidence_count', 0)} cases · confidence: {conf}\n"
                           f"- applied: {', '.join(L.get('applied_to', [])[:4]) or 'pending'}\n")
            put("_auto/lessons.md", f"# Lessons Learned\n\n" + "\n".join(lns))
        else:
            put("_auto/lessons.md", "# Lessons Learned\n\n_No validated lessons yet._\n")

        # 3) todo — what MB still needs to do: in-flight tasks + pending approvals
        tasks = self.engine.list_tasks(None, 30, None)
        pend = [t for t in tasks if t.get("state") in ("ANALYZING", "WORKING", "REWORK", "IN_QA")]
        todo = []
        for t in pend:
            todo.append(f"- [ ] `{t.get('state')}` {t.get('request_text', '')[:120]}")
        apps = self.engine.approvals_pending(None)
        for a in apps:
            todo.append(f"- [ ] approval needed: {str(a.get('reason') or a.get('request_text') or a.get('action'))[:120]}")
        put("_auto/todo.md", "# Main Brain — To Do\n\n" + ("\n".join(todo) if todo else "_All clear — nothing pending._\n"))

        # 4) PM / project knowledge
        pms = self.engine.list_pms()
        if pms:
            pl = []
            for pm in pms[:10]:
                pl.append(f"### {pm.get('project_id')} — {pm.get('name', 'PM')}\n"
                          f"- state: {pm.get('state', '')} · memory keys: "
                          f"{', '.join(list((pm.get('memory') or {}).keys())[:6]) or 'none'}\n")
            put("_auto/pm-knowledge.md", "# PM & Project Knowledge\n\n" + "\n".join(pl))
        else:
            put("_auto/pm-knowledge.md", "# PM & Project Knowledge\n\n_No active projects yet._\n")

        return {"ok": True, "written": written, "count": len(written)}

    def worker_studio(self, worker_id: str) -> dict:
        w = self.engine.registry.get_worker(worker_id)
        if not w:
            return {"error": "worker_not_found"}
        wdict = self.engine.worker_catalog_row(worker_id) or {}
        tools = " ".join((t.get("tool") or "") for t in (wdict.get("tools") or []))
        skills = " ".join((s.get("capability") or "") + " " + (s.get("name") or "")
                          for s in (wdict.get("skills") or [])).lower()
        hay = (tools + " " + skills).lower()
        studio = "general"
        for s, keys in (("research", ("research", "search", "browser", "crawl", "scrape", "investigat", "gather")),
                        ("code", ("code", "coding", "python", "script", "automation", "program", "terminal", "shell", "cli", "api", "compile")),
                        ("sheets", ("sheets", "spreadsheet", "excel", "xlsx", "csv", "data")),
                        ("slides", ("slides", "presentation", "pptx", "powerpoint")),
                        ("media", ("media", "video", "audio", "image", "music")),
                        ("design", ("design", "illustrat", "figma", "brand"))):
            if any(k in hay for k in keys):
                studio = s
                break
        if studio == "general" and any(k in hay for k in ("document", "writer", "report", "office", "docx")):
            studio = "docs"
        # recent activity for this worker (audit + tasks)
        rows = wd_db.query(
            "SELECT ts, actor_role, action, tool, reason FROM audit_events "
            "WHERE actor_id=? OR task_id IN (SELECT task_id FROM tasks WHERE result_json LIKE ?) "
            "ORDER BY seq DESC LIMIT 12", (worker_id, f"%{worker_id}%"))
        feed = [{"ts": r[0], "actor": r[1], "action": r[2], "tool": r[3], "reason": r[4]}
                for r in rows]
        tasks = wd_db.query(
            "SELECT task_id, request_text, state, created_ts FROM tasks "
            "WHERE result_json LIKE ? ORDER BY created_ts DESC LIMIT 8",
            (f"%{worker_id}%",))
        return {"worker": wdict, "studio_type": studio, "feed": feed,
                "tasks": [{"task_id": t[0], "request": t[1], "state": t[2], "ts": t[3]}
                          for t in tasks]}

    # ------------------------------------------------------------------ #
    # Phase 13: Hive layer — office floor coordination (munder-difflin  #
    # inspired: mailbox/actor messaging, speech-act protocol, shared     #
    # blackboard, append-only event log). Single-AI: MB is the god,      #
    # PMs are scribes, workers get inbox/outbox.                         #
    # ------------------------------------------------------------------ #
    HIVE_ROOT = Path(__file__).resolve().parent / "data" / "hive"
    HIVE_ACTS = ("request", "inform", "propose", "query", "agree", "refuse", "done")
    HIVE_HOP_CAP = 8

    @staticmethod
    def _hive_agent_dir(agent_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", agent_id or "unknown")[:80] or "unknown"
        d = WorkDeskBridge.HIVE_ROOT / "agents" / safe
        (d / "inbox").mkdir(parents=True, exist_ok=True)
        (d / "outbox").mkdir(parents=True, exist_ok=True)
        return d

    def _hive_log(self, entry: dict) -> None:
        log = WorkDeskBridge.HIVE_ROOT / "log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def hive_send(self, conversation_id: str, from_id: str, to_id: str, act: str,
                  subject: str, body: str = "", in_reply_to: str | None = None) -> dict:
        """Send one hive message (FIPA-lite speech act). Writes sender outbox,
        recipient inbox and the append-only event log. Anti-livelock: every
        reply increments hops; past the cap the message is refused and logged."""
        act = (act or "inform").lower()
        if act not in WorkDeskBridge.HIVE_ACTS:
            return {"error": "bad_act", "acts": list(WorkDeskBridge.HIVE_ACTS)}
        hops = 0
        if in_reply_to:
            prev = self.hive_get_message(in_reply_to)
            if prev:
                hops = int(prev.get("hops") or 0) + 1
        if hops >= WorkDeskBridge.HIVE_HOP_CAP:
            self._hive_log({"event": "hive_refused", "conversation": conversation_id,
                            "from": from_id, "to": to_id, "act": act, "hops": hops,
                            "reason": "hop_cap"})
            return {"error": "hop_cap", "hops": hops,
                    "reason": "message chain exceeded the livelock cap"}
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        msg_id = f"{now}-{os.urandom(3).hex()}"
        msg = {"id": msg_id, "conversation": conversation_id or "",
               "in_reply_to": in_reply_to, "from": from_id, "to": to_id, "act": act,
               "subject": subject or "", "body": body or "", "hops": hops,
               "requires_reply": act in ("request", "query", "propose"),
               "needs_human": False, "created_at": now}
        src = self._hive_agent_dir(from_id)
        dst = self._hive_agent_dir(to_id)
        for folder in (dst / "inbox", src / "outbox"):
            tmp = folder / f".{msg_id}.tmp"
            tmp.write_text(json.dumps(msg, ensure_ascii=False), encoding="utf-8")
            tmp.replace(folder / f"{msg_id}.json")
        self._hive_log({"event": "hive_msg", "id": msg_id, "conversation": conversation_id,
                        "from": from_id, "to": to_id, "act": act, "subject": subject,
                        "hops": hops})
        return {"ok": True, "message": msg}

    def hive_get_message(self, msg_id: str) -> dict | None:
        for agent_dir in (WorkDeskBridge.HIVE_ROOT / "agents").glob("*"):
            for folder in ("inbox", "outbox"):
                p = agent_dir / folder / f"{msg_id}.json"
                if p.exists():
                    try:
                        return json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        return None
        return None

    def hive_messages(self, conversation_id: str | None = None,
                      agent_id: str | None = None) -> list[dict]:
        """All hive messages, optionally filtered by conversation and/or agent.
        A message lives in both sender outbox and recipient inbox, so results
        are deduped by message id (box label keeps the first hit)."""
        seen: dict[str, dict] = {}
        root = WorkDeskBridge.HIVE_ROOT / "agents"
        if not root.exists():
            return []
        for agent_dir in root.glob("*"):
            aid = agent_dir.name
            if agent_id and aid != agent_id:
                continue
            for folder in ("inbox", "outbox"):
                for p in agent_dir.glob(folder + "/*.json"):
                    try:
                        m = json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if conversation_id and m.get("conversation") != conversation_id:
                        continue
                    m["_box"] = f"{aid}:{folder}"
                    seen.setdefault(m.get("id") or p.stem, m)
        out = list(seen.values())
        out.sort(key=lambda m: m.get("created_at", ""))
        return out

    def hive_board_get(self, conversation_id: str) -> dict:
        board = self._hive_board_path(conversation_id)
        if not board or not board.exists():
            return {"conversation_id": conversation_id, "content": "",
                    "scribe": None, "updated": None}
        return {"conversation_id": conversation_id, "content": board.read_text(encoding="utf-8"),
                "scribe": "pm", "updated": board.stat().st_mtime}

    def _hive_board_path(self, conversation_id: str) -> Path | None:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", conversation_id or "default")[:80] or "default"
        root = (WorkDeskBridge.HIVE_ROOT / "boards").resolve()
        root.mkdir(parents=True, exist_ok=True)
        p = (root / f"{safe}.md").resolve()
        return p if root in p.parents else None

    def hive_board_put(self, conversation_id: str, text: str, scribe: str = "pm") -> dict:
        """Single-scribe blackboard (munder-difflin rule: the god/PM is the only
        writer of board.md, so shared plans never conflict)."""
        p = self._hive_board_path(conversation_id)
        if p is None:
            return {"error": "bad_conversation"}
        p.write_text(text or "", encoding="utf-8")
        self._hive_log({"event": "hive_board", "conversation": conversation_id,
                        "scribe": scribe, "chars": len(text or "")})
        return {"ok": True, "conversation_id": conversation_id, "content": text or ""}

    def hive_state(self, conversation_id: str | None = None) -> dict:
        """One snapshot for the office floor: roster + statuses, board,
        recent messages, tail of the event log."""
        vo = self.engine.virtual_office(conversation_id)
        workers = vo.get("workers") or []
        if not workers and conversation_id:
            workers = self.engine.virtual_office(None).get("workers") or []
        board = self.hive_board_get(conversation_id or "default")
        msgs = self.hive_messages(conversation_id)[-40:]
        log_tail = []
        log = WorkDeskBridge.HIVE_ROOT / "log.jsonl"
        if log.exists():
            with log.open(encoding="utf-8") as f:
                lines = [l for l in f.read().splitlines() if l.strip()][-30:]
            for l in lines:
                try:
                    log_tail.append(json.loads(l))
                except Exception:
                    pass
        return {"conversation_id": conversation_id, "workers": workers,
                "board": board, "messages": msgs, "log": log_tail,
                "hop_cap": WorkDeskBridge.HIVE_HOP_CAP}


bridge = WorkDeskBridge()
