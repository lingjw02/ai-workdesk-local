# -*- coding: utf-8 -*-
"""Skill Based Routing (SBR) — routes task components to workers by SKILL.

Replaces type/keyword-based worker selection with a skill-indexed pipeline:

    component (skill / capability)
        -> skills registry match (exact -> prefix -> alias token)
        -> worker candidates (reverse index over workers.skills_json)
        -> scoring  (skill fidelity + primary + QA stats + experience + tool fit)
        -> best worker OR capability gap (with suggested skill)
        -> audit route record (component, skill, worker, score, reason)

The routing table never depends on worker *names* or hard-coded types: a worker
is selected because it owns the required skill. Installing a new skill on a
worker automatically extends the tasks it can be routed to.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger("SkillRouter")

# Skill aliases: user/task vocabulary -> canonical skill names in the skills table.
# Used only as a fallback when exact / prefix matching finds nothing.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "research.search": ("research", "search", "browse", "investigate", "web", "survey", "source", "调研", "研究"),
    "coding.python": ("coding", "python", "script", "code", "program", "terminal", "shell", "bash", "编程", "脚本"),
    "writer.markdown": ("writer", "writing", "markdown", "document", "report", "article", "draft", "写作", "报告"),
    "data.summarize": ("data", "analys", "analyze", "dataset", "statistic", "metrics", "csv", "pandas", "数据", "分析"),
    "slides.create": ("slides", "present", "ppt", "deck", "pitch", "演示", "幻灯片"),
    "docx.create": ("docx", "word", "document", "letter", "memo", "文档"),
    "file.organize": ("file", "folder", "organize", "rename", "tree", "cleanup", "文件", "整理"),
}


def _tokens(text: str) -> set[str]:
    """Lowercased alphanumeric tokens for overlap matching."""
    out: set[str] = set()
    for tok in str(text).lower().replace("-", " ").replace(".", " ").replace("_", " ").split():
        tok = tok.strip()
        if len(tok) >= 2:
            out.add(tok)
    return out


class SkillRouter:
    """Pure-python skill router bound to a WorkDesk engine."""

    def __init__(self, engine) -> None:
        self.engine = engine

    # ------------------------------------------------------------------ #
    # public API                                                          #
    # ------------------------------------------------------------------ #
    def route(self, spec: dict) -> dict:
        """Route every component of a task spec.

        Returns:
            {
              "team":  {component_id: worker_id},
              "routes": [ {component, skill, worker, score, reason} ... ],
              "gaps":   [ {component, skill, reason, suggested_skill} ... ],
            }
        """
        team: dict[str, str] = {}
        routes: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        for comp in spec.get("components", []):
            skill = comp.get("skill") or comp.get("capability") or ""
            cap = comp.get("capability") or skill
            if not skill:
                continue
            res = self._route_component(skill, cap)
            if res.get("worker"):
                team[comp["id"]] = res["worker"]
                routes.append(res)
            else:
                gaps.append(res)
        return {"team": team, "routes": routes, "gaps": gaps}

    def route_text(self, text: str) -> dict:
        """Direct text entry point (used by diagnostics / UI preview)."""
        spec = {"components": [{"id": "auto", "skill": s, "capability": s.split(".")[0]}
                               for s in self._skills_for_text(text)]}
        return self.route(spec)

    # ------------------------------------------------------------------ #
    # internals                                                           #
    # ------------------------------------------------------------------ #
    def _route_component(self, skill: str, cap: str) -> dict[str, Any]:
        """Match one component against the worker pool."""
        workers = self._candidates(skill, cap)
        if not workers:
            return {
                "component": None, "skill": skill, "worker": None, "score": 0.0,
                "reason": "capability gap",
                "suggested_skill": self._suggest_skill(skill, cap),
            }
        best = None
        for w in workers:
            w["_score"], w["_match"] = self._score(w, skill, cap)
            if w["_score"] <= 0:
                continue  # worker does not own this skill -> not routable
            if best is None or w["_score"] > best["_score"]:
                best = w
        if best is None:
            return {
                "component": None, "skill": skill, "worker": None, "score": 0.0,
                "reason": "capability gap",
                "suggested_skill": self._suggest_skill(skill, cap),
            }
        return {
            "component": None, "skill": skill, "worker": best["worker_id"],
            "score": round(best["_score"], 3),
            "reason": (f"skill {skill} matched '{best['_match']}' "
                       f"(QA {best.get('qa_pass_rate', 0):.0%} · {best.get('tasks_completed', 0)} tasks)"),
        }

    def _candidates(self, skill: str, cap: str) -> list[dict]:
        """Reverse index over workers.skills_json, ranked-candidate list."""
        out: list[dict] = []
        conn = self.engine.db
        for row in conn.execute("SELECT * FROM workers").fetchall():
            if row["status"] not in ("AVAILABLE", "ACTIVE"):
                continue
            skills = json.loads(row["skills_json"] or "[]")
            if not skills:
                continue
            d = dict(row)
            d["_skills"] = skills
            out.append(d)
        return out

    @staticmethod
    def _score(w: dict, skill: str, cap: str) -> tuple[float, str]:
        """Score a candidate worker for this component.

        Components:
          +0.45  exact skill name match (worker.skills_json.capability == skill)
          +0.25  prefix match (skill "coding.python" vs capability "coding")
          +0.15  alias token overlap (SKILL_ALIASES)
          +0.10  skill flagged primary
          +0.30 * qa_pass_rate
          +0.20 * (1 - failure_rate)
          +0.05 * min(times_triggered, 10) / 10
        """
        score = 0.0
        match_kind = "none"
        caps = {s.get("capability", "") for s in w["_skills"]}
        if skill in caps or skill.split(".")[0] in caps:
            score += 0.45
            match_kind = "exact" if skill in caps else "prefix"
        else:
            sk = _tokens(skill)
            if sk:
                for cand in caps:
                    if sk & _tokens(cand):
                        score += 0.15
                        match_kind = "token"
                        break
        if match_kind == "none":
            # The worker does NOT own this skill: not routable (SBR gate).
            return 0.0, "none"
        if any(s.get("primary") for s in w["_skills"]):
            score += 0.10
        total = (w.get("qa_passed") or 0) + (w.get("qa_failed") or 0)
        rate = (w.get("qa_passed") or 0) / total if total else 0.0
        fail = w.get("failure_rate") or 0.0
        trig = min(w.get("times_triggered") or 0, 10) / 10.0
        score += 0.30 * rate + 0.20 * (1 - fail) + 0.05 * trig
        return score, match_kind

    @staticmethod
    def _suggest_skill(skill: str, cap: str) -> str:
        """When no worker owns the required skill, suggest the canonical skill name."""
        if skill in SKILL_ALIASES:
            return skill
        root = skill.split(".")[0]
        for canonical in SKILL_ALIASES:
            if canonical.startswith(root + ".") or root in SKILL_ALIASES.get(canonical, ()):
                return canonical
        return skill or cap or "custom"

    @staticmethod
    def _skills_for_text(text: str) -> list[str]:
        """Map a raw text to candidate canonical skills (diagnostics only)."""
        low = text.lower()
        hits = []
        for canonical, words in SKILL_ALIASES.items():
            if any(w in low for w in words):
                hits.append(canonical)
        return hits[:4]


def audit_skill_route(engine, task_id: str, routes: list[dict], gaps: list[dict]) -> None:
    """Persist the SBR decision as audit events (decision/event metadata)."""
    try:
        for r in routes:
            engine.permissions.audit(
                "MB", "mb", "skill_route",
                reason=f"SBR: {r['skill']} -> {r['worker']} (score {r['score']}; {r['reason']})",
                task_id=task_id)
        for g in gaps:
            engine.permissions.audit(
                "MB", "mb", "skill_gap",
                reason=f"SBR gap: {g['skill']} -> suggested {g.get('suggested_skill')}",
                task_id=task_id)
    except Exception:  # noqa: BLE001
        logger.debug("skill route audit failed", exc_info=True)


def route_id() -> str:
    return "sbr-" + uuid.uuid4().hex[:10]
