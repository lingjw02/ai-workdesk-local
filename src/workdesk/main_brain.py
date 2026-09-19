"""Phase-2 Main Brain intelligence layer (Spec §16 Phase 2).

Upgrades the Phase-1 rule stub into a structured requirement pipeline. Still
deterministic (the LLM lands in Phase 8 via the Model Router), but now covers the
full Phase-2 Main Brain responsibilities:

  - requirement understanding      -> structured RequirementSpec
  - requirement specification      -> typed spec (goal/intent/output/data/risk/...)
  - QA-1 gate                      -> completeness + ambiguity + contradiction + feasibility
  - clarification                  -> which items blocked the gate (consumed by runtime.MainBrain)
  - simple/complex classification  -> direct work vs Task Group
  - worker selection               -> ranked by performance statistics, capability-gap detection
  - Task Group planning            -> team_plan: only the selected workers
  - permission decision            -> risk level + expected approvals (audited)
  - global memory                  -> preference consultation + evidence-gated learning

Everything here is pure logic over the engine interfaces; orchestration and state
transitions stay in runtime.MainBrain.
"""
import json

from . import config, db

# --------------------------------------------------------------------------- #
# keyword tables (deterministic stand-ins for NLU)                             #
# --------------------------------------------------------------------------- #
GREET = ("hello", "hi ", "hey", "good morning", "good afternoon", "你好", "您好", "早上好", "嗨", "哈喽")
THANKS = ("thank", "thanks", "谢谢", "感谢")
ASK_MARKERS = ("what is", "what are", "how do", "how does", "how to", "why", "when is",
               "where is", "explain", "define", "meaning of", "是什么", "怎么", "如何",
               "为什么", "什么意思", "区别", "解释")
VAGUE_REF = ("这个", "那个", "this thing", "that thing")
VAGUE_AMOUNT = ("a few", "some", "several", "couple of", "一些", "若干", "几个", "少量", "一点")
CONFLICT_PAIRS = {("python", "slides"), ("python", "excel"), ("excel", "slides")}
NEGATION_MARKERS = ("not a report", "no report", "不要报告", "不是报告", "don't make a report",
                    "don't write a report", "不用报告")
DELETE_VERBS = ("delete", "remove", "uninstall", "format", "wipe", "clear out",
                "删除", "移除", "卸载", "格式化", "清空")
KEEP_WORDS = ("backup", "keep", "preserve", "retain", "备份", "保留", "留档")
RISK_HIGH = DELETE_VERBS + ("install", "send", "email", "post", "publish", "pay", "transfer",
                            "汇款", "支付", "转账", "发布", "发送", "安装")
RISK_MEDIUM = ("modify", "edit", "change", "update", "configure", "配置", "修改", "更改", "更新")
SENSITIVE = ("password", "passwd", "token", "secret", "credential", "api key", "apikey",
             "private key", "privatekey", "salary", "ssn", "health record", "medical record",
             "密码", "密钥", "令牌", "凭据", "工资", "薪酬", "病历", "体检", "身份证", "银行卡")
LANG_ZH = ("中文", "汉语", "用中文", "简体")
LANG_EN = ("english", "英文", "英语")
DEADLINE = ("today", "tonight", "tomorrow", "this week", "asap", "尽快",
            "今天", "今晚", "明天", "本周", "周内")
STYLE = ("concise", "brief", "detailed", "简洁", "简要", "详细")

# output_type inference priority: first matching hint wins
OUTPUT_HINTS = (
    ("python", ("python", "script", ".py", "code", "program", "runnable", "脚本", "程序", "可运行")),
    ("research", ("research", "investigate", "survey", "study", "调研", "研究", "查一下", "资料")),
    ("slides", ("slide", "slides", "ppt", "presentation", "deck", "幻灯片", "演示文稿", "讲稿")),
    ("excel", ("excel", "csv", "spreadsheet", "sheet", "表格", "电子表格", "数据表")),
    ("email", ("email", "mail", "邮件", "发一封")),
    ("markdown", ("markdown", "md file", ".md")),
    ("report", ("report", "summary", "summarize", "纪要", "总结", "报告", "汇报", "摘要")),
    ("plan", ("plan", "schedule", "roadmap", "outline", "计划", "方案", "日程", "规划")),
)

# capability that produces each output type (worker must exist or it is a gap)
COMPONENT_BY_OUTPUT = {
    "python": ("coding.python", "coding"),
    "research": ("research.search", "research"),
    "markdown": ("writer.markdown", "writer"),
    "report": ("writer.markdown", "writer"),
    "slides": ("slides.build", "slides"),
    "excel": ("excel.build", "excel"),
    "email": ("email.draft", "email"),
    "plan": ("plan.write", "plan"),
}
_FNAME = {"python": "demo_script.py", "research": "research_notes.md", "markdown": "report.md",
          "report": "report.md", "slides": "slides.pptx", "excel": "report.xlsx",
          "email": "email.txt", "plan": "plan.md"}


def _has_any(low: str, words) -> bool:
    return any(w in low for w in words)


# --------------------------------------------------------------------------- #
# RequirementSpec: the structured requirement (Spec §16 Phase 2)               #
# --------------------------------------------------------------------------- #
class RequirementSpec:
    """Structured requirement produced by Main Brain understanding.

    Serialized into the task's `spec_json` (all fields JSON-safe) so QA-1, the PM,
    workers and the audit trail share one frozen requirement definition.
    """

    FIELDS = (
        "goal", "intent", "complexity", "output_type", "needs_data", "_needs_data",
        "inputs", "save_path", "criteria", "components", "privacy", "risk_level",
        "constraints", "model_hint", "team_plan", "capability_gaps",
        "approvals_expected", "provenance", "_qa", "_ctx",
    )

    def __init__(self, **kw):
        for f in self.FIELDS:
            setattr(self, f, kw.get(f))

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> "RequirementSpec":
        return cls(**{f: d.get(f) for f in cls.FIELDS})


# --------------------------------------------------------------------------- #
# MainBrainIntelligence: understanding + QA-1 + selection + permissions + memory#
# --------------------------------------------------------------------------- #
class MainBrainIntelligence:
    def analyze(self, text: str, ctx: dict | None, answers: dict | None,
                engine) -> dict:
        """Full Phase-2 understanding pass -> RequirementSpec dict (with `_qa`)."""
        ctx = dict(ctx or {})
        ctx.update(answers or {})
        low = text.lower()

        spec: dict = {
            "goal": self._clean_goal(text),
            "intent": self._intent(low, text),
            "complexity": "complex",            # classified after QA-1 passes
            "output_type": ctx.get("output_type"),
            "needs_data": False, "_needs_data": False,
            "inputs": ctx.get("inputs"),
            "save_path": ctx.get("save_path"),
            "criteria": [],
            "components": [],
            "privacy": "public", "risk_level": "low",
            "constraints": {}, "model_hint": "auto",
            "team_plan": {}, "capability_gaps": [],
            "approvals_expected": [], "provenance": {},
            "_qa": {}, "_ctx": _jsonable(ctx),
        }

        hints = self._output_hints(low)
        spec["needs_data"] = bool(ctx.get("inputs")) or _has_any(
            low, ("analyze", "analys", "dataset", "sales", "metrics", "numbers", "data ",
                  "统计", "数据", "指标", "汇总"))
        spec["_needs_data"] = spec["needs_data"]
        if spec["output_type"] is None and hints:
            spec["output_type"] = hints[0]      # first matching hint wins
        spec["save_path"] = self._default_save_path(spec, ctx)
        spec["privacy"] = "sensitive" if _has_any(low, SENSITIVE) else "public"
        spec["risk_level"] = self._risk(low)
        spec["constraints"] = self._constraints(low)
        spec["model_hint"] = "local" if spec["privacy"] == "sensitive" else "auto"
        spec["criteria"] = ctx.get("criteria") or self._default_criteria(spec)
        spec["components"] = self._components_for(spec, low)

        # global memory consultation: only when the text itself is not explicit
        if spec["output_type"] is None and not hints:
            self.consult_global_memory(engine, spec)
            # the learned preference may have set output_type: rebuild the
            # components (and default criteria) that were derived from it
            spec["criteria"] = ctx.get("criteria") or self._default_criteria(spec)
            spec["components"] = self._components_for(spec, low)

        # QA-1 audit info: ambiguity + contradiction + feasibility
        spec["_qa"] = {
            "ambiguities": self._ambiguities(low, spec),
            "contradictions": self._contradictions(low, hints, spec),
            "feasibility": self._feasibility(engine, spec),
        }
        return spec

    # ---- understanding primitives ----
    @staticmethod
    def _clean_goal(text: str) -> str:
        goal = text.strip()
        for prefix in ("please ", "pls ", "can you ", "could you ", "help me ", "i want ",
                       "i need ", "make me ", "would you ", "帮我", "请", "麻烦你", "你能不能"):
            if goal.lower().startswith(prefix):
                goal = goal[len(prefix):].strip()
                break
        return goal.rstrip("?？.。") or text.strip()

    @staticmethod
    def _intent(low: str, text: str) -> str:
        if _has_any(low, GREET):
            return "greet"
        if _has_any(low, THANKS):
            return "thanks"
        if _has_any(low, ASK_MARKERS) or text.rstrip().endswith(("?", "？")):
            return "ask"
        return "execute"

    @staticmethod
    def _output_hints(low: str) -> list[str]:
        return [kind for kind, words in OUTPUT_HINTS if _has_any(low, words)]

    @staticmethod
    def _risk(low: str) -> str:
        if _has_any(low, RISK_HIGH):
            return "high"
        if _has_any(low, RISK_MEDIUM):
            return "medium"
        return "low"

    @staticmethod
    def _constraints(low: str) -> dict:
        c: dict = {}
        if _has_any(low, LANG_ZH):
            c["language"] = "zh"
        elif _has_any(low, LANG_EN):
            c["language"] = "en"
        if _has_any(low, DEADLINE):
            c["deadline"] = "urgent"
        if _has_any(low, STYLE):
            c["style"] = "concise" if _has_any(low, ("concise", "brief", "简洁", "简要")) else "detailed"
        return c

    @staticmethod
    def _default_save_path(spec: dict, ctx: dict) -> str | None:
        if spec["save_path"] is None and ctx.get("out_dir") and spec["output_type"]:
            fname = _FNAME.get(spec["output_type"], "output.md")
            return str(Path(str(ctx["out_dir"])) / str(ctx.get("project_id") or "default") / fname)
        return spec["save_path"]

    @staticmethod
    def _default_criteria(spec: dict) -> list[dict]:
        c: list[dict] = []
        if spec.get("output_type") in ("report", "markdown", "research", "python"):
            c.append({"id": "file_exists", "check": "file"})
        if spec.get("inputs"):
            c.append({"id": "totals_correct", "check": "totals"})
        c.append({"id": "has_summary", "check": "content"})
        return c

    def _components_for(self, spec: dict, low: str) -> list[dict]:
        comps: list[dict] = []
        seen: set[str] = set()

        def add(cid: str, skill: str, cap: str) -> None:
            if cid not in seen:
                seen.add(cid)
                comps.append({"id": cid, "skill": skill, "capability": cap})

        if spec.get("inputs") or spec.get("needs_data"):
            add("data.summarize", "data.summarize", "data")
        if spec.get("output_type") == "python" or _has_any(
                low, ("code", "script", "python", ".py", "program", "runnable")):
            add("coding.python", "coding.python", "coding")
        if spec.get("output_type") == "research" or _has_any(
                low, ("research", "investigate", "survey", "study", "调研", "研究")):
            add("research.search", "research.search", "research")
        ot = spec.get("output_type")
        if ot in COMPONENT_BY_OUTPUT:
            cid, cap = COMPONENT_BY_OUTPUT[ot]
            add(cid, cid, cap)
        return comps

    # ---- QA-1: ambiguity + contradiction + feasibility ----
    @staticmethod
    def _ambiguities(low: str, spec: dict) -> list[str]:
        out = []
        if _has_any(low, VAGUE_REF) and not spec.get("output_type"):
            out.append("vague_reference: 目标指代不明确，请说明具体对象")
        if spec.get("needs_data") and _has_any(low, VAGUE_AMOUNT):
            out.append("vague_amount: 数据范围/数量描述模糊（如“一些/几个”）")
        return out

    @staticmethod
    def _contradictions(low: str, hints: list[str], spec: dict) -> list[str]:
        out = []
        for a, b in CONFLICT_PAIRS:
            if a in hints and b in hints:
                out.append(f"output_conflict: 同时要求 {a} 与 {b}，产出类型互相矛盾")
        if ("report" in hints or spec.get("output_type") == "report") and _has_any(low, NEGATION_MARKERS):
            out.append("negation_conflict: 明确说“不要报告”但又要求报告类产出")
        if _has_any(low, DELETE_VERBS) and _has_any(low, KEEP_WORDS):
            out.append("destructive_conflict: 同时要求删除与保留/备份同一类对象")
        return out

    @staticmethod
    def _feasibility(engine, spec: dict) -> dict:
        """Capability-gap detection: every component needs an available worker."""
        if engine is None:      # compat path (deprecated StubUnderstanding)
            return {"gaps": [], "ok": True}
        gaps: list[str] = []
        for comp in spec.get("components", []):
            cap = comp.get("capability")
            if not cap:
                continue
            found = any(
                any(s.get("capability") == cap for s in w.skills.values())
                for w in engine.workers.values() if w.available())
            if not found:
                gaps.append(f"{comp['id']} (capability={cap})")
        return {"gaps": gaps, "ok": not gaps}

    def qa1(self, spec: dict, engine) -> dict:
        """Requirement gate: completeness + ambiguity + contradiction + feasibility."""
        missing: list[str] = []
        if not spec.get("goal"):
            missing.append("goal")
        if spec.get("intent") == "execute" and not spec.get("output_type"):
            missing.append("output_type")
        if spec.get("output_type") in ("report", "markdown", "excel", "slides") \
                and spec.get("needs_data") and not spec.get("inputs"):
            missing.append("inputs")
        if spec.get("save_path") is not None and not str(spec["save_path"]).strip():
            missing.append("save_path")
        qa = spec.get("_qa") or {}
        amb = qa.get("ambiguities") or []
        contra = qa.get("contradictions") or []
        gaps = (qa.get("feasibility") or {}).get("gaps") or []
        passed = not (missing or amb or contra or gaps)
        return {"pass": passed, "missing": missing, "ambiguities": amb,
                "contradictions": contra,
                "feasibility": {"gaps": gaps, "ok": not gaps}}

    # ---- simple / complex classification (Spec §16: direct work vs group) ----
    def classify(self, text: str, spec: dict, engine) -> str:
        if spec.get("intent") in ("greet", "thanks"):
            return "simple"
        # questions are answered by the MB directly, never executed as tasks
        if spec.get("intent") == "ask" and not spec.get("needs_data"):
            return "simple"
        # Phase 3: every execute intent goes through the task pipeline (QA-1 gate
        # → group → QA-2); the bridge's simple fast-path is for MB-answerable
        # interactions only. An incomplete execute (missing output, etc.) must
        # still reach the clarification gate, so it is never "simple".
        if spec.get("intent") == "execute":
            return "complex"
        if (spec.get("_qa") or {}).get("feasibility", {}).get("gaps"):
            return "complex"          # capability gap -> MB must intervene/upgrade
        score = len(spec.get("components") or []) \
            + (1 if spec.get("needs_data") else 0) \
            + (1 if spec.get("risk_level") == "high" else 0)
        return "complex" if score >= 2 else "simple"

    # ---- worker selection: SKILL BASED ROUTING (SBR) ----
    # Route each component by the *skill* it requires. A worker is chosen because
    # it owns the required skill (exact -> prefix -> alias), scored with QA stats
    # and experience. No worker owns the skill -> capability gap (Worker Creator).
    def select_workers(self, spec: dict, engine) -> tuple[dict[str, str], list[str]]:
        from .skill_router import SkillRouter, audit_skill_route
        router = SkillRouter(engine)
        res = router.route(spec)
        spec["team_routes"] = res["routes"]
        spec["capability_gaps_detail"] = res["gaps"]
        audit_skill_route(engine, spec.get("taskId") or (spec.get("_ctx") or {}).get("task_id"),
                          res["routes"], res["gaps"])
        team = {comp["id"]: res["team"][comp["id"]] for comp in spec.get("components", [])
                if comp["id"] in res["team"]}
        gaps = [g.get("component") or g.get("skill") for g in res["gaps"]]
        return team, gaps

    @staticmethod
    def _score(wrow: dict, cap: str) -> float:
        skills = wrow.get("skills") or []
        if cap not in {s.get("capability") for s in skills}:
            return 0.0
        rate = wrow.get("qa_pass_rate") or 0.0
        fail = wrow.get("failure_rate") or 0.0
        trig = min(wrow.get("times_triggered") or 0, 10) / 10.0
        return 0.5 + 0.3 * rate + 0.2 * (1 - fail) + 0.05 * trig

    # ---- permission decision: risk -> expected approvals (audited) ----
    def plan_permissions(self, engine, task_id: str | None, spec: dict) -> list[dict]:
        probes = [
            ("read", "project:/x/file", "FILESYSTEM"),
            ("create", "project:/x/new", "FILESYSTEM"),
            ("modify", "project:config:settings.json", "FILESYSTEM"),
            ("delete", "project:/x/draft", "FILESYSTEM"),
            ("install", "system:app", "SYSTEM"),
            ("send", "external:email", "NETWORK"),
        ]
        plan = []
        for action, resource, tool in probes:
            level, _ = engine.permissions.resolve("WORKER", action, resource, tool)
            # ASK/EXPLICIT = will require approval; DENY = worker is blocked outright
            if level in ("ASK", "EXPLICIT", "DENY"):
                plan.append({"action": action, "resource": resource, "tool": tool, "level": level})
        try:
            engine.permissions.audit("MB", "mb", "permission_plan",
                                     reason=f"risk={spec.get('risk_level')}; approvals={[p['action'] for p in plan]}",
                                     task_id=task_id)
        except Exception:  # noqa: BLE001
            pass
        return plan

    # ---- global memory: consultation + evidence-gated learning ----
    @staticmethod
    def consult_global_memory(engine, spec: dict) -> None:
        if engine is None:      # compat path (deprecated StubUnderstanding)
            return
        rows, _ = engine.memory.read("MB", "GLOBAL", "global")
        prefs: dict[str, str] = {}
        for r in rows:
            key, value = r["type"], (r["content"] or "").strip()
            if key == "preference" and "=" in value:
                k, _, v = value.partition("=")
                prefs[k.strip()] = v.strip()
            elif key in ("default_output_format", "language", "report_style") and value:
                prefs[key] = value
        prov = {}
        if spec.get("output_type") is None and prefs.get("default_output_format"):
            spec["output_type"] = prefs["default_output_format"]
            prov["output_type"] = "global_memory:default_output_format"
        if not spec.get("constraints", {}).get("language") and prefs.get("language"):
            spec.setdefault("constraints", {})["language"] = prefs["language"]
            prov["language"] = "global_memory:language"
        spec["provenance"] = prov

    @staticmethod
    def learn_preference(engine, task_id: str, output_type: str) -> str | None:
        """Evidence-gated preference learning (Spec 03 §4.5): promotion needs >= N cases."""
        value = f"default_output_format={output_type}"
        rows, _ = engine.memory.read("MB", "GLOBAL", "global")
        for r in rows:
            content = (r["content"] or "").strip()
            if content == value or (r["type"] == "preference" and content.partition("=")[2] == output_type):
                refs = json.loads(r["evidence_refs_json"] or "[]")
                if task_id in refs:
                    return r["mem_id"]
                refs.append(task_id)
                conf = "HIGH" if len(refs) >= config.LESSON_PROMOTE_MIN_EVIDENCE else "MEDIUM"
                db.execute("UPDATE memory_records SET evidence_refs_json=?, confidence=? WHERE mem_id=?",
                           (json.dumps(refs), conf, r["mem_id"]))
                return r["mem_id"]
        mem_id = engine.memory.write("MB", "mb", "GLOBAL", "global", "preference", value,
                                     confidence="MEDIUM", evidence_refs=[task_id],
                                     tags=["learned", "output_format"])
        return mem_id


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _jsonable(obj):
    from pathlib import Path
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


from pathlib import Path  # noqa: E402  (used by _default_save_path)
