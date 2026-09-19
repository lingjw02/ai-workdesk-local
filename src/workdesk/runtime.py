"""Phase-1/2 runtime: MB / PM / Worker / QA orchestration.

Intelligence comes from the Phase-2 Main Brain layer (`main_brain.py`): structured
requirement understanding, enhanced QA-1 (completeness/ambiguity/contradiction/
feasibility), simple-complex classification, stats-ranked worker selection,
permission planning and global-memory learning. The real LLM still lands in Phase 8
(Model Router); everything here is deterministic so the orchestration skeleton is
verified end to end.
"""
import os
import threading
import time
from pathlib import Path

from . import config, db, ids
from .envelope import Envelope
from .main_brain import MainBrainIntelligence
from .states import TaskState
from .task import Task


class ClarificationNeeded(Exception):
    def __init__(self, task_id: str, missing: list[str], verdict: dict | None = None):
        super().__init__(f"clarification needed: {missing}")
        self.task_id = task_id
        self.missing = missing
        self.verdict = verdict or {}


def _jsonable(obj):
    """Coerce Path objects (and containers) into JSON-safe values for persistence."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


# --------------------------------------------------------------------------- #
# Intelligence layer (Phase 2): requirement understanding + component planning  #
# --------------------------------------------------------------------------- #
class StubUnderstanding:
    """DEPRECATED since Phase 2 — kept as a thin alias over MainBrainIntelligence
    for any code that still references the Phase-1 stub."""

    intelligence = MainBrainIntelligence()

    @classmethod
    def plan(cls, text: str, ctx: dict | None, answers: dict | None) -> dict:
        spec = cls.intelligence.analyze(text, ctx, answers, engine=None)
        return spec


# --------------------------------------------------------------------------- #
# QA role: QA-1 (requirement) + QA-2 (output) with structured verdicts        #
# --------------------------------------------------------------------------- #
# Phase 6: capability consumption map — which component kinds consume another
# capability's artifacts, so selective rework redone only the failed component
# and its direct downstream consumers (never the full project).
CONSUMES = {
    "writer": {"data"},
    "documenter": {"data", "research"},
}


class FailureReport:
    """One structured QA-2 failure: which component, which criterion, how bad,
    what evidence, and what to fix. Drives selective rework (Phase 6)."""

    def __init__(self, component: str, criterion: str, severity: str = "medium",
                 evidence: str = "", fix_hint: str = ""):
        self.component = component
        self.criterion = criterion
        self.severity = severity            # low | medium | high
        self.evidence = evidence
        self.fix_hint = fix_hint

    def to_dict(self) -> dict:
        return {"component": self.component, "criterion": self.criterion,
                "severity": self.severity, "evidence": self.evidence,
                "fix_hint": self.fix_hint}


class QA:
    def qa1(self, spec: dict) -> dict:
        missing = []
        if not spec.get("goal"):
            missing.append("goal")
        if not spec.get("output_type"):
            missing.append("output_type")
        if spec.get("output_type") in ("report", "markdown") and spec.get("_needs_data") and not spec.get("inputs"):
            missing.append("inputs")
        if spec.get("save_path") is not None and not str(spec["save_path"]).strip():
            missing.append("save_path")
        return {"pass": not missing, "missing": missing}

    # ---- Phase 6: deterministic format/structure checks by output kind ----
    @staticmethod
    def _format_check(artifact: dict, content: str, output_type: str | None) -> str | None:
        kind = (artifact.get("kind") or "").lower()
        if kind in ("", "file"):
            kind = (output_type or "").lower()
        if kind in ("markdown", "report", "slides", "plan", "md", "file", ""):
            s = content.lstrip()
            if s and not s.startswith("#"):
                return "markdown-style output should start with a heading (#)"
        if kind in ("csv", "excel"):
            lines = [l for l in content.splitlines() if l.strip()]
            if len(lines) < 2:
                return "tabular output needs a header row and at least one data row"
            if "," not in lines[0] and "\t" not in lines[0] and not lines[0].lstrip().startswith("#"):
                return "csv output should be comma-separated"
        if kind == "email":
            if "Subject:" not in content:
                return "email output should include a Subject: line"
        return None

    def _record(self, verdict_id: str, task_id: str, stage: str, cycle: int,
                component: str, criterion: str, passed: int, severity: str,
                evidence: str, fix_hint: str) -> None:
        db.execute(
            "INSERT INTO qa_verdicts(verdict_id,task_id,stage,cycle,component,criterion,"
            "passed,severity,evidence,fix_hint,ts) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (verdict_id, task_id, stage, cycle, component, criterion, passed,
             severity, evidence, fix_hint, ids.now_iso()))

    def qa2(self, task: Task, artifacts: list[dict], spec: dict, cycle: int = 0) -> dict:
        """Output QA: completeness + correctness + format, with a persisted
        validation history (Phase 6) and a score for the pipeline."""
        failures: list[FailureReport] = []
        dataset = (spec.get("inputs") or {}).get("dataset")
        expected = sum(dataset["q3"]) if dataset else None
        crit_ids = {c["id"] for c in spec.get("criteria", [])}
        # Phase 3: completeness — every planned component must have produced an
        # artifact, otherwise a silently-errored worker would pass QA-2 vacuously
        made = {a.get("component") for a in artifacts}
        for comp in spec.get("components", []):
            if comp["id"] not in made:
                failures.append(FailureReport(
                    component=comp["id"], criterion="artifact_missing", severity="high",
                    evidence=f"no artifact produced for {comp['id']}",
                    fix_hint="re-run the component and confirm it writes its artifact"))
        for art in artifacts:
            path = art.get("path")
            if path and "file_exists" in crit_ids and not os.path.exists(path):
                failures.append(FailureReport(
                    component=art.get("component", "?"), criterion="file_exists", severity="high",
                    evidence=f"missing file {path}",
                    fix_hint="make sure the skill writes the promised file path"))
            if path and os.path.exists(path):
                content = Path(path).read_text(encoding="utf-8", errors="replace")
                # totals_correct is scoped to the report-writing component, not to
                # every file artifact (research notes etc. legitimately have no Total)
                if (expected is not None and "totals_correct" in crit_ids
                        and art.get("component") == "writer.markdown"
                        and f"Total: {expected}" not in content):
                    failures.append(FailureReport(
                        component="data.summarize", criterion="totals_correct", severity="high",
                        evidence=f"expected total {expected}",
                        fix_hint="recompute the aggregation before formatting"))
                if "has_summary" in crit_ids and "Summary" not in content:
                    failures.append(FailureReport(
                        component="writer.markdown", criterion="has_summary", severity="medium",
                        evidence="no Summary section",
                        fix_hint="include a Summary section in the report"))
                # Phase 6: deterministic format/structure checks
                hint = self._format_check(art, content, spec.get("output_type"))
                if hint:
                    failures.append(FailureReport(
                        component=art.get("component", "?"), criterion="format_ok", severity="low",
                        evidence=str(path), fix_hint=hint))
        # Phase 6: persisted validation history (queryable, auditable, learnable)
        task_id = getattr(task, "task_id", None) or "unit"
        verdict_id = ids.new_id()
        if failures:
            for f in failures:
                self._record(verdict_id, task_id, "QA2", cycle, f.component, f.criterion,
                             0, f.severity, f.evidence, f.fix_hint)
        else:
            self._record(verdict_id, task_id, "QA2", cycle, "*", "all_pass",
                         1, "low", "", "")
        score = round(max(0.0, 1.0
                          - 0.25 * sum(1 for f in failures if f.severity == "high")
                          - 0.10 * sum(1 for f in failures if f.severity == "medium")
                          - 0.05 * sum(1 for f in failures if f.severity == "low")), 2)
        return {"pass": not failures, "score": score,
                "failures": [f.to_dict() for f in failures],
                "verdict_id": verdict_id}


# --------------------------------------------------------------------------- #
# Worker role: persistent AI employee (stub skills + permission + memory)      #
# --------------------------------------------------------------------------- #
class StubWorker:
    def __init__(self, engine, worker_id: str, name: str, skills: dict,
                 fail_once: list[str] | None = None, sleep_skill: dict | None = None):
        self.e = engine
        self.worker_id = worker_id
        self.name = name
        self.skills = skills                      # {skill_id: {"capability": ...}}
        self.fail_once = set(fail_once or [])     # skills that fail exactly once (rework demo)
        self.sleep_skill = dict(sleep_skill or {})
        self._started = threading.Event()

    def available(self) -> bool:
        return True

    def execute(self, task: Task, group, comp: dict) -> dict:
        self.e.registry.bump_triggered(self.worker_id)
        self._started.set()
        skill = comp.get("skill")
        delay = self.sleep_skill.get(skill)
        if delay:
            time.sleep(delay)
        inject = skill in self.fail_once
        if inject:
            self.fail_once.discard(skill)
        t0 = time.time()
        out = self._run_skill(task, group, comp, inject_error=inject)
        exec_ms = (time.time() - t0) * 1000
        artifact = {"artifact_id": ids.new_id(), "component": comp["id"], "skill": skill,
                    "worker_id": self.worker_id, **out}
        self.e.registry.record_result(self.worker_id, task.task_id, passed=not inject, exec_ms=exec_ms)
        # Spec 03: worker writes its own experience (allowed: own WORKER layer)
        try:
            self.e.memory.write("WORKER", self.worker_id, "WORKER", self.worker_id, "experience",
                                f"completed {comp['id']}", ctx={"own_worker_id": self.worker_id},
                                task_id=task.task_id)
        except PermissionError:
            pass
        return artifact

    def redo(self, task: Task, group, failure: dict) -> None:
        comp_id = failure["component"]
        # Phase 3: resolve the capability from this worker's own skills first
        cap = next((m.get("capability") for sid, m in self.skills.items() if sid == comp_id), None)
        if cap is None:
            cap = self._capability(comp_id)
        comp = {"id": comp_id, "skill": comp_id, "capability": cap}
        # Phase 6: a HIGH PM lesson injected by the PM steers the redo
        if failure.get("guidance"):
            comp["guidance"] = failure["guidance"]
        art = self.execute(task, group, comp)
        group.artifacts_manifest = [a for a in group.artifacts_manifest
                                    if a.get("component") != comp_id] + [art]

    @staticmethod
    def _capability(component_id: str) -> str:
        return {"data.summarize": "data", "writer.markdown": "writer",
                "research.search": "research", "coding.python": "coding"}.get(component_id, "writer")

    # ---- stub skills ----
    def _run_skill(self, task: Task, group, comp: dict, inject_error: bool = False) -> dict:
        skill = comp.get("skill")
        if skill == "data.summarize":
            ds = (task.spec.get("inputs") or {}).get("dataset") or {}
            total = sum(ds.get("q3") or [])
            if inject_error:
                total += 10
            return {"kind": "computation", "total": total, "regions": ds.get("region")}
        if skill == "research.search":
            path = Path(self.e.project_dir) / task.project_id / "research_notes.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                from tools.web_tool import web_tool  # lazy: tools/ is at project root
                results = web_tool.search_sync(task.request_text, count=5)
                if results:
                    lines = [f"# Research Notes\n\nSummary: live web search for: {task.request_text}\n"]
                    for i, r in enumerate(results, 1):
                        lines.append(f"{i}. **{r['title']}**\n   URL: {r['url']}\n   {r['snippet']}\n")
                    content = "\n".join(lines)
                else:
                    content = ("# Research Notes\n\n"
                               "Summary: live web search returned no results for "
                               f"'{task.request_text}'.\n")
            except Exception as e:  # noqa: BLE001 - search must never break the pipeline
                content = (f"# Research Notes\n\nSummary: web search unavailable ({e}).\n"
                           "No live results were captured.\n")
            path.write_text(content, encoding="utf-8")
            return {"kind": "file", "path": str(path)}
        if skill == "coding.python":
            path = Path(self.e.project_dir) / task.project_id / "demo_script.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                "# demo_script.py -- Summary: stub Python demo (Phase-1 stub worker).\n"
                "def main():\n"
                "    print('AI WorkDesk OS demo script (stub)')\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            )
            path.write_text(content, encoding="utf-8")
            return {"kind": "file", "path": str(path)}
        if skill == "writer.markdown":
            totals = None
            for a in group.artifacts_manifest:
                if a.get("kind") == "computation":
                    totals = a["total"]
            path = task.spec.get("save_path")
            if not path:
                # Phase 3: default to the project dir when no save_path was given
                path = Path(self.e.project_dir) / task.project_id / "report.md"
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            content = f"# Q3 Sales Summary\n\nSummary: quarterly regional sales totals.\n\nTotal: {totals}\n"
            # Phase 6: a HIGH PM lesson injected by the PM lands in the artifact,
            # so the rework is visibly steered by institutional memory
            if comp.get("guidance"):
                content += f"\nQA Note: {comp['guidance']}\n"
            Path(path).write_text(content, encoding="utf-8")
            self._exercise_delete(path)   # Spec 03: EXPLICIT approval on delete
            return {"kind": "file", "path": str(path)}
        # Phase 3: dynamically created skills (Worker Creator) are resolved here
        handler = (self.e.skill_handlers or {}).get(skill)
        if handler is not None:
            return handler(task, group, comp)
        raise RuntimeError(f"unknown skill {skill}")

    def _exercise_delete(self, path) -> None:
        tmp = Path(path).with_suffix(".tmp")
        try:
            tmp.write_text("temp", encoding="utf-8")
            level, _ = self.e.permissions.resolve("WORKER", "delete", f"project:{tmp}", "FILESYSTEM")
            if level in ("ASK", "EXPLICIT"):
                ap_id, _ = self.e.permissions.require_approval("WORKER", self.worker_id, "delete",
                                                               f"project:{tmp}", "FILESYSTEM")
                if ap_id:
                    self.e.permissions.decide(ap_id, "APPROVED", "demo auto-approve")
            tmp.unlink(missing_ok=True)
        except FileNotFoundError:
            pass


# --------------------------------------------------------------------------- #
# PM role: persistent project employee (institutional memory of the project)   #
# --------------------------------------------------------------------------- #
class ProjectManager:
    def __init__(self, pm_id: str, name: str, project_id: str, engine):
        self.pm_id = pm_id
        self.name = name
        self.project_id = project_id
        self.e = engine

    def _ctx(self) -> dict:
        """Memory access context: PM owns this project's memory (Spec 03 §4.3)."""
        return {"own_project_id": self.project_id}

    # ---- Phase 4: PM institutional memory ----
    def record_after_task(self, task: Task, group, outcome: str, *,
                          qa_cycles: int = 0, rework_count: int = 0,
                          failed_components: list[str] | None = None) -> None:
        """PM writes its project memory after every terminal task state:
        task/group history, worker performance snapshots, project knowledge,
        conventions, decisions, and evidence-gated lessons."""
        if task.group_id:
            self.e.registry.update_pm(self.pm_id, task_history=[task.task_id],
                                      group_history=[task.group_id])
        perf: dict[str, dict] = {}
        for a in (group.artifacts_manifest or []):
            wid = a.get("worker_id")
            if not wid:
                continue
            rec = self.e.registry.get_worker(wid)
            if rec:
                perf[wid] = {"tasks_completed": rec["tasks_completed"],
                             "qa_passed": rec["qa_passed"], "qa_failed": rec["qa_failed"],
                             "failure_rate": rec["failure_rate"],
                             "avg_execution_time_ms": rec["avg_execution_time_ms"],
                             "last_updated": rec["updated_ts"]}
        if perf:
            self.e.registry.update_pm(self.pm_id, worker_performance=perf)
        # project knowledge: result + artifacts (PROJECT memory layer)
        arts = [{"component": a.get("component"), "worker": a.get("worker_id"),
                 "kind": a.get("kind"), "path": a.get("path")}
                for a in (group.artifacts_manifest or [])]
        self.e.memory.write("PM", self.pm_id, "PROJECT", self.project_id, "task_result",
                            f"task {task.task_id} -> {outcome}", ctx=self._ctx(),
                            task_id=task.task_id)
        if arts:
            self.e.memory.write("PM", self.pm_id, "PROJECT", self.project_id, "artifact",
                                str(arts), ctx=self._ctx(), task_id=task.task_id)
        # conventions: recurring successful output types
        ot = (task.spec or {}).get("output_type")
        if outcome == "COMPLETED" and ot:
            self.e.registry.update_pm(self.pm_id, conventions=[f"output_type={ot}"])
        # decisions worth remembering
        if rework_count:
            self.e.registry.update_pm(self.pm_id, decisions=[{
                "decision": "rework",
                "context": f"task {task.task_id}",
                "ts": ids.now_iso(),
                "outcome": f"reworked {rework_count} cycle(s), final={outcome}"}])
        # evidence-gated lessons (Phase 4/9: PM + workers + global MB)
        self._learn_lessons(task, group, outcome, qa_cycles, rework_count,
                            failed_components)
        self.e.permissions.audit("PM", self.pm_id, "pm_recorded",
                                 reason=f"task={task.task_id}; outcome={outcome}",
                                 task_id=task.task_id)

    def _learn_lessons(self, task: Task, group, outcome: str, qa_cycles: int,
                       rework_count: int,
                       failed_components: list[str] | None = None) -> None:
        """Task -> Result -> QA -> Lesson candidate -> evidence/confidence ->
        stored (Spec 01 §8 / Phase 9). PM + participating workers + global MB
        each learn from the same evidence, in their own scope."""
        worker_ids = []
        for a in (group.artifacts_manifest or []):
            wid = a.get("worker_id")
            if wid and wid not in worker_ids:
                worker_ids.append(wid)
        if not worker_ids:
            # fall back to the team plan when no artifacts exist yet
            plan = (task.spec or {}).get("team_plan") or {}
            worker_ids = list(dict.fromkeys(v for v in plan.values() if v))
        self.e.learning.learn_from_task(
            task=task, outcome=outcome, qa_cycles=qa_cycles,
            rework_count=rework_count, worker_ids=worker_ids,
            pm_id=self.pm_id,
            team_plan=(task.spec or {}).get("team_plan") or {},
            failed_components=failed_components)

    def _pick_worker(self, task: Task, comp: dict) -> str | None:
        # Phase 2: honor the MB team plan (stats-ranked selection) first
        plan = (task.spec or {}).get("team_plan") or {}
        if comp["id"] in plan:
            wid = plan[comp["id"]]
            if wid in self.e.workers and self.e.workers[wid].available():
                return wid
        cap = comp.get("capability")
        for wid, w in self.e.workers.items():
            if not w.available():
                continue
            if any(s.get("capability") == cap for s in w.skills.values()):
                return wid
        return None

    def run_task(self, task: Task, group) -> None:
        for comp in task.spec.get("components", []):
            if self.e.cancel_requested(task.task_id):
                break
            worker_id = self._pick_worker(task, comp)
            if worker_id is None:
                # Phase 3: PM may request a new worker for a still-uncovered capability
                try:
                    self.e.maybe_create_workers(task.spec, task.task_id)
                    worker_id = self._pick_worker(task, comp)
                except Exception:  # noqa: BLE001
                    worker_id = None
            if worker_id is None:
                self.e.bus.send(Envelope(type="ESCALATION", from_role="PM", from_id=self.pm_id,
                                         to_role="MB", task_id=task.task_id, group_id=group.group_id,
                                         payload={"reason": "capability_gap", "component": comp["id"]}))
                self.e.permissions.audit("PM", self.pm_id, "escalate:capability_gap",
                                         reason=comp["id"], task_id=task.task_id)
                continue
            self.e.bus.send(Envelope(type="COMMAND", from_role="PM", from_id=self.pm_id,
                                     to_role="WORKER", to_id=worker_id, task_id=task.task_id,
                                     group_id=group.group_id, payload={"op": "execute", "component": comp}))
            try:
                artifact = self.e.workers[worker_id].execute(task, group, comp)
                if artifact:
                    group.artifacts_manifest.append(artifact)
                self.e.bus.send(Envelope(type="EVENT", from_role="WORKER", from_id=worker_id,
                                         to_role="PM", task_id=task.task_id, group_id=group.group_id,
                                         payload={"kind": "artifact_created", "artifact": artifact}))
            except Exception as exc:  # noqa: BLE001 - worker error escalates
                self.e.bus.send(Envelope(type="ESCALATION", from_role="WORKER", from_id=worker_id,
                                         to_role="PM", task_id=task.task_id, group_id=group.group_id,
                                         payload={"reason": "worker_error", "error": repr(exc),
                                                  "component": comp["id"]}))
                self.e.permissions.audit("WORKER", worker_id, "error", reason=repr(exc),
                                         task_id=task.task_id)

    def rework(self, task: Task, group, failures: list[dict]) -> None:
        """Phase 6 selective rework: only the failed component plus its direct
        downstream consumers are redone — never the full project, and never
        unrelated components. Failed components whose capability carries a HIGH
        PM lesson are handled FIRST and the lesson is injected into the redo as
        guidance (lessons now steer execution)."""
        comps_by_id = {c["id"]: c for c in task.spec.get("components", [])}
        failed_ids = {f["component"] for f in failures}

        def _consumes(consumer: dict, capability: str) -> bool:
            return capability in CONSUMES.get(consumer.get("capability") or "", set())

        todo: list[dict] = []
        seen: set[str] = set()
        for fid in sorted(failed_ids):                      # deterministic order
            comp = comps_by_id.get(fid)
            if comp is None or comp["id"] in seen:
                continue
            seen.add(comp["id"])
            todo.append(comp)
            cap = comp.get("capability") or ""
            for c in task.spec.get("components", []):
                if c["id"] in seen:
                    continue
                if _consumes(c, cap):
                    seen.add(c["id"])
                    todo.append(c)
        for comp in todo:
            worker_id = self._pick_worker(task, comp)
            if worker_id is None:
                continue
            guidance = ""
            if comp["id"] in failed_ids:
                lesson = self.e.registry.get_pm_lesson_key(self.pm_id,
                                                           comp.get("capability") or "")
                if lesson is not None and lesson["confidence"] == "HIGH":
                    guidance = lesson["content"]
                    self.e.permissions.audit("PM", self.pm_id, "rework_lesson_applied",
                                             reason=f"cap={comp.get('capability')}; "
                                                    f"lesson={lesson['lesson_id']}",
                                             qa_refs=failures, task_id=task.task_id)
            payload = {"op": "redo", "component": comp["id"], "failure": failures,
                       "guidance": guidance}
            self.e.bus.send(Envelope(type="COMMAND", from_role="PM", from_id=self.pm_id,
                                     to_role="WORKER", to_id=worker_id, task_id=task.task_id,
                                     group_id=group.group_id, payload=payload))
            self.e.workers[worker_id].redo(task, group, payload)
            self.e.permissions.audit("PM", self.pm_id, "rework", reason=f"component={comp['id']}",
                                     qa_refs=[f.get("criterion", f.get("criteria_violated", ""))
                                              for f in failures],
                                     task_id=task.task_id)


# --------------------------------------------------------------------------- #
# Main Brain: orchestrator + final authority (below USER)                      #
# --------------------------------------------------------------------------- #
class MainBrain:
    def __init__(self, engine):
        self.e = engine
        self.intelligence = MainBrainIntelligence()

    def classify_text(self, text: str) -> str:
        """Phase-2 simple/complex classification (used by the server bridge)."""
        spec = self.intelligence.analyze(text, None, None, self.e)
        return self.intelligence.classify(text, spec, self.e)

    def accept_request(self, text: str, ctx: dict | None = None, answers: dict | None = None) -> Task:
        ctx = dict(ctx or {})
        task = Task(task_id=ids.new_id(), request_text=text,
                    project_id=ctx.get("project_id", "default"),
                    conversation_id=ctx.get("conversation_id"))
        task.spec = {"_ctx": _jsonable(ctx)}     # persist context for later clarification
        self._persist_task(task)
        self._t(task, TaskState.ANALYZING, None, "MB")
        spec, v1 = self._plan(task, text, task.spec["_ctx"], None)
        if not v1["pass"]:
            # Phase 3: capability gaps trigger the Worker Creator (permission-gated);
            # if a worker is created, re-plan and re-run QA-1 before clarifying.
            gaps = (v1.get("feasibility") or {}).get("gaps") or []
            if gaps and not answers:
                try:
                    self.e.maybe_create_workers(spec, task.task_id)
                    spec, v1 = self._plan(task, text, task.spec["_ctx"], None)
                except Exception:  # noqa: BLE001 - creation must never break the flow
                    pass
            if not v1["pass"]:
                self._t(task, TaskState.CLARIFYING, "QA1_FAIL", "QA")
                if not answers:
                    raise ClarificationNeeded(task.task_id, v1["missing"], verdict=v1)
                spec, v1 = self._plan(task, text, task.spec["_ctx"], answers)
                if not v1["pass"]:
                    self._t(task, TaskState.FAILED, "QA1_FAIL_FINAL", "QA")
                    task.spec = spec
                    self._save_task(task)
                    return task
                self._t(task, TaskState.ANALYZING, "CLARIFY_RESOLVED", "MB")
        task.spec = spec
        self._finalize_spec(task, text, spec, answers)
        self._t(task, TaskState.READY, "QA1_PASS", "QA")
        self._save_task(task)
        return task

    def _finalize_spec(self, task: Task, text: str, spec: dict, answers: dict | None) -> None:
        """Post-QA1: classification + team plan + permission plan + preference learning."""
        spec["complexity"] = self.intelligence.classify(text, spec, self.e)
        team, gaps = self.intelligence.select_workers(spec, self.e)
        spec["team_plan"] = team
        spec["capability_gaps"] = gaps
        spec["approvals_expected"] = self.intelligence.plan_permissions(self.e, task.task_id, spec)
        if answers and answers.get("output_type"):
            try:
                self.intelligence.learn_preference(self.e, task.task_id, answers["output_type"])
            except Exception:  # noqa: BLE001 - learning must never break the flow
                pass
        task.spec = spec

    def _reinforce_preference(self, task: Task) -> None:
        """Evidence-gated learning (Spec 03 §4.5): a COMPLETED task that USED a
        global-memory preference corroborates it (promotes MEDIUM -> HIGH at >= N)."""
        prov = (task.spec or {}).get("provenance") or {}
        if prov.get("output_type") != "global_memory:default_output_format":
            return
        ot = task.spec.get("output_type")
        if not ot:
            return
        try:
            self.intelligence.learn_preference(self.e, task.task_id, ot)
        except Exception:  # noqa: BLE001
            pass

    def _plan(self, task: Task, text: str, ctx: dict, answers: dict | None):
        spec = self.intelligence.analyze(text, ctx, answers, self.e)
        v1 = self.intelligence.qa1(spec, self.e)
        self.e.bus.send(Envelope(type="QA_VERDICT", from_role="QA", from_id="qa.1", to_role="MB",
                                 task_id=task.task_id, payload={"stage": "QA1", "verdict": v1}))
        # Phase 6: persist the requirement-QA verdict into the validation history
        try:
            if v1["pass"]:
                self.e.qa._record(ids.new_id(), task.task_id, "QA1", 0, "*", "qa1_pass",
                                  1, "low", "", "")
            else:
                for m in v1.get("missing", []):
                    self.e.qa._record(ids.new_id(), task.task_id, "QA1", 0, "*",
                                      f"missing:{m}", 0, "high", "", "ask the user to supply it")
                for g in (v1.get("feasibility") or {}).get("gaps", []):
                    self.e.qa._record(ids.new_id(), task.task_id, "QA1", 0, g,
                                      "capability_gap", 0, "medium", "", "create or upgrade a worker")
        except Exception:  # noqa: BLE001 - history must never break the flow
            pass
        return spec, v1

    def run_ready_task(self, task: Task) -> Task:
        """Execute a READY task end to end: group -> QA-2 -> selective rework -> done."""
        if task.state != TaskState.READY:
            return task
        if self.e.cancel_requested(task.task_id):
            self._t(task, TaskState.CANCELLED, "STOP", "USER")
            self._save_task(task)
            self.e._finalize(task, manifest=group.artifacts_manifest)
            return task
        self._t(task, TaskState.RUNNING, "PM_START", "PM")
        pm = self.e.get_pm(task.project_id)
        group = self.e._make_group(task, pm)
        task.group_id = group.group_id
        self._save_task(task)
        self.e.checkpoint(task)
        self.e.route_group(task, group)        # Phase 8: task-based model routing
        pm.run_task(task, group)
        if self.e.cancel_requested(task.task_id):
            self._t(task, TaskState.CANCELLED, "STOP", "USER")
            self._save_task(task)
            self.e._finalize(task, manifest=group.artifacts_manifest)
            pm.record_after_task(task, group, "CANCELLED")   # Phase 4: PM memory
            return task
        self._t(task, TaskState.IN_QA, "OUTPUT_READY", "PM")
        failed_comps: set[str] = set()
        for cycle in range(self.e.config.MAX_REWORK_CYCLES + 1):
            if self.e.cancel_requested(task.task_id):
                self._t(task, TaskState.CANCELLED, "STOP", "USER")
                self._save_task(task)
                self.e._finalize(task, manifest=group.artifacts_manifest)
                pm.record_after_task(task, group, "CANCELLED", qa_cycles=cycle,
                                     rework_count=task.rework_count)
                return task
            verdict = self.e.qa.qa2(task, group.artifacts_manifest, task.spec, cycle=cycle)
            # Phase 9: apply HIGH-confidence lessons as QA hints for this task
            cap = ((task.spec or {}).get("components") or [{}])[0].get("capability", "default")
            hints = self.e.learning.hints_for(cap)
            if hints:
                applied = []
                for h in hints:
                    self.e.learning.record_applied(h["lesson_id"])
                    self.e.permissions.audit(
                        "MB", "learning", "lesson_applied",
                        reason=f"lesson={h['lesson_id']} scope={h['scope']} "
                               f"key={h['lesson_key']} capability={cap}",
                        task_id=task.task_id)
                    applied.append({"lesson_id": h["lesson_id"], "scope": h["scope"],
                                    "content": h["content"],
                                    "evidence_count": h["evidence_count"]})
                verdict["applied_lessons"] = applied
            self.e.bus.send(Envelope(type="QA_VERDICT", from_role="QA", from_id="qa.1", to_role="MB",
                                     task_id=task.task_id,
                                     payload={"stage": "QA2", "cycle": cycle, "verdict": verdict}))
            if not verdict["pass"]:
                for f in verdict["failures"]:
                    if f.get("component"):
                        failed_comps.add(f["component"])
            if verdict["pass"]:
                self._t(task, TaskState.COMPLETED, "QA2_PASS", "QA")
                task.result = {"artifacts": group.artifacts_manifest, "qa_cycles": cycle,
                               "qa_score": verdict["score"], "rework_count": task.rework_count}
                self._save_task(task)
                self.e._finalize(task, manifest=group.artifacts_manifest)
                self._reinforce_preference(task)   # successful outcome corroborates memory
                pm.record_after_task(task, group, "COMPLETED", qa_cycles=cycle,
                                     rework_count=task.rework_count,
                                     failed_components=list(failed_comps))
                return task
            task.rework_count = cycle + 1
            if task.rework_count > self.e.config.MAX_REWORK_CYCLES:
                self._t(task, TaskState.FAILED, "QA2_RETRY_LIMIT", "MB")
                task.result = {"artifacts": group.artifacts_manifest, "qa_cycles": cycle,
                               "qa_score": verdict["score"], "rework_count": task.rework_count}
                self._save_task(task)
                self.e._finalize(task, manifest=group.artifacts_manifest)
                pm.record_after_task(task, group, "FAILED", qa_cycles=cycle,
                                     rework_count=task.rework_count,
                                     failed_components=list(failed_comps))
                return task
            self._t(task, TaskState.REWORK, "QA2_FAIL", "QA")
            self.e.checkpoint(task)
            pm.rework(task, group, verdict["failures"])
            self._t(task, TaskState.RUNNING, "REWORK_ASSIGNED", "PM")
            self._t(task, TaskState.IN_QA, "OUTPUT_READY", "PM")
            self._save_task(task)
        return task

    # ---- state transitions: single writer, event-sourced, audited ----
    def _t(self, task: Task, to: TaskState, trigger: str | None, actor: str) -> None:
        ev = task.sm.transition(to, trigger, actor)
        # Persistence sequence comes from the DB (source of truth), not the in-memory
        # copy, so concurrent stop()/resume() cannot collide on (task_id, seq).
        n = db.query_one("SELECT COALESCE(MAX(seq),0) AS m FROM task_transitions WHERE task_id=?",
                         (task.task_id,))["m"]
        seq = int(n) + 1
        try:
            db.execute(
                "INSERT INTO task_transitions(task_id,seq,from_state,to_state,trigger,actor,ts,payload_json) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (task.task_id, seq, ev["from"], ev["to"], ev["trigger"], ev["actor"], ev["ts"],
                 __import__("json").dumps(ev["payload"])))
        except Exception:  # noqa: BLE001 - idempotent re-transition, keep going
            return
        task.state = to
        task.updated_ts = ev["ts"]
        db.execute("UPDATE tasks SET state=?, updated_ts=? WHERE task_id=?",
                   (to.value, task.updated_ts, task.task_id))
        self.e.permissions.audit(actor, "", f"task_state:{to.value}", reason=f"trigger={ev['trigger']}",
                                 task_id=task.task_id)

    def _persist_task(self, task: Task) -> None:
        db.execute(
            "INSERT INTO tasks(task_id,request_text,spec_json,state,project_id,group_id,rework_count,created_ts,updated_ts,result_json,conversation_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (task.task_id, task.request_text, __import__("json").dumps(task.spec), task.state.value,
             task.project_id, task.group_id, task.rework_count, task.created_ts, task.updated_ts,
             None, task.conversation_id))

    def _save_task(self, task: Task) -> None:
        db.execute(
            "UPDATE tasks SET spec_json=?,state=?,group_id=?,rework_count=?,updated_ts=?,result_json=? WHERE task_id=?",
            (__import__("json").dumps(task.spec), task.state.value, task.group_id, task.rework_count,
             task.updated_ts, __import__("json").dumps(task.result) if task.result else None, task.task_id))
