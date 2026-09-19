"""Phase 8 — task-based hybrid model routing (Spec 01 §12, Phase 8).

The router is a pure decision function plus a persisted decision record. It
answers "which model should run this piece of work" from task attributes:

  privacy    -> sensitive work goes LOCAL first (fallback: cloud if no local
                endpoint is configured, with the limitation audited);
  complexity -> simple/classification -> instant model (local when available),
                complex/deep reasoning -> expert cloud model;
  capability -> vision/other specializations pin a model;
  default    -> worker model.

Workers never care whether their model is local or cloud — they ask for
"a capable coding model" and the routing layer decides (Spec 01 §12).
Every decision is persisted (task_routes) and audit-logged as decision
metadata (model_routed), so the UI can show why a model was chosen.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

from . import db, ids
from .model_providers import OpenAICompatProvider, OpenRouterProvider


@dataclass
class RouteRequest:
    """Everything the router needs to decide. `capability` is the worker's
    primary capability (e.g. coding, research, writer, slides, data)."""
    task_id: str
    worker_id: str
    capability: str = "default"
    complexity: str = "normal"      # simple | normal | complex
    privacy: str = "public"         # public | sensitive
    task_type: str = "default"      # classification | reasoning | generation | analysis | default
    model_hint: str = "auto"        # local | auto (user/MB preference)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RouteDecision:
    provider: str                    # local | cloud | api
    model: str
    fallbacks: list[str] = field(default_factory=list)
    reason: str = ""
    privacy_sensitive: bool = False
    ts: str = field(default_factory=ids.now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


def _or(values: list[str]) -> str:
    return " or ".join(f"'{v}'" for v in values)


@dataclass
class CallResult:
    """Outcome of actually invoking a routed model (Phase 8.2).

    `attempts` records every step of the chain (primary + fallbacks) so the
    UI can show what was tried and why it fell through."""
    ok: bool
    text: str = ""
    provider: str = ""           # provider that produced the text ('' on total failure)
    model: str = ""              # model that produced the text ('' on total failure)
    duration_ms: int = 0
    fallback_used: bool = False
    attempts: list[dict] = field(default_factory=list)
    ts: str = field(default_factory=ids.now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


def _find_api_key(config) -> str:
    """OpenRouter key comes from the config object if present, else the
    process environment (loaded from .env by core/config)."""
    if hasattr(config, "OPENROUTER_API_KEY"):
        val = getattr(config, "OPENROUTER_API_KEY")
        if val is not None:
            return str(val).strip()
    return (os.environ.get("OPENROUTER_API_KEY", "") or "").strip()


def _find_chatanywhere_key(config) -> str:
    """ChatAnywhere free relay key (https://chatanywhere.tech)."""
    if hasattr(config, "CHATANYWHERE_API_KEY"):
        val = getattr(config, "CHATANYWHERE_API_KEY")
        if val is not None:
            return str(val).strip()
    return (os.environ.get("CHATANYWHERE_API_KEY", "") or "").strip()


class ModelRouter:
    """Deterministic routing policy. Order matters — privacy wins, then
    complexity, then capability, then the worker default."""

    def __init__(self, config, audit: Callable | None = None,
                 local_provider: Any | None = None,
                 cloud_provider: Any | None = None):
        self.config = config
        self.audit = audit  # permissions.audit(actor_role, actor_id, action, ...)
        self._local_provider = local_provider   # injected (tests) or built lazily
        self._cloud_provider = cloud_provider

    # ---- decision ----
    def route(self, req: RouteRequest) -> RouteDecision:
        c = self.config
        local_endpoint = (c.LOCAL_ENDPOINT or "").strip()
        has_local = bool(local_endpoint)

        privacy_sensitive = req.privacy == "sensitive"
        model_hint = (req.model_hint or "auto").lower()

        # 1) privacy first (Spec §12: private file analysis -> local)
        if privacy_sensitive or model_hint == "local":
            if has_local:
                return RouteDecision(
                    provider="local", model=local_endpoint,
                    fallbacks=[c.INSTANT_MODEL],
                    reason="privacy=sensitive -> local endpoint (data never leaves the machine)",
                    privacy_sensitive=True)
            return RouteDecision(
                provider="cloud", model=c.INSTANT_MODEL,
                fallbacks=[c.WORKER_MODEL],
                reason=("privacy=sensitive but no LOCAL_ENDPOINT configured -> "
                        "cloud instant fallback (limitation: data leaves the machine)"),
                privacy_sensitive=True)

        # 2) capability pins (vision etc.)
        cap = (req.capability or "").lower()
        if cap in ("vision", "image"):
            return RouteDecision(
                provider="cloud", model=c.EXPERT_MODEL,
                fallbacks=[c.WORKER_MODEL, c.INSTANT_MODEL],
                reason=f"capability='{cap}' -> multimodal expert model",
                privacy_sensitive=False)

        # 3) complexity: simple/classification -> instant (local when available)
        simple = req.complexity == "simple" or req.task_type in ("classification", "summary")
        if simple:
            if has_local:
                return RouteDecision(
                    provider="local", model=local_endpoint,
                    fallbacks=[c.INSTANT_MODEL],
                    reason="complexity=simple -> local instant model",
                    privacy_sensitive=False)
            return RouteDecision(
                provider="cloud", model=c.INSTANT_MODEL,
                fallbacks=[c.WORKER_MODEL],
                reason="complexity=simple -> cloud instant model (no local endpoint)",
                privacy_sensitive=False)

        # 4) complex / deep reasoning -> expert cloud
        if req.complexity == "complex" or req.task_type in ("reasoning", "code", "analysis"):
            return RouteDecision(
                provider="cloud", model=c.EXPERT_MODEL,
                fallbacks=[c.WORKER_MODEL, c.INSTANT_MODEL],
                reason=f"complexity={req.complexity} -> expert cloud model",
                privacy_sensitive=False)

        # 5) default worker model
        return RouteDecision(
            provider="cloud", model=c.WORKER_MODEL,
            fallbacks=[c.INSTANT_MODEL],
            reason="default worker model",
            privacy_sensitive=False)

    # ---- persistence + audit ----
    def record(self, req: RouteRequest, decision: RouteDecision) -> None:
        db.execute(
            "INSERT INTO task_routes(task_id,worker_id,capability,provider,model,fallbacks_json,"
            "reason,privacy_sensitive,ts) VALUES(?,?,?,?,?,?,?,?,?)",
            (req.task_id, req.worker_id, req.capability, decision.provider, decision.model,
             json.dumps(decision.fallbacks), decision.reason,
             1 if decision.privacy_sensitive else 0, decision.ts))
        if self.audit is not None:
            try:
                self.audit("MB", "model_router", "model_routed",
                           reason=(f"worker={req.worker_id} capability={req.capability} "
                                   f"complexity={req.complexity} privacy={req.privacy} -> "
                                   f"{decision.provider}:{decision.model} ({decision.reason})"),
                           task_id=req.task_id)
            except Exception:  # noqa: BLE001 - audit must never break routing
                pass

    # ---- read models ----
    def stats(self) -> dict:
        by_provider: dict[str, int] = {}
        by_model: dict[str, int] = {}
        for r in db.query("SELECT provider, model FROM task_routes"):
            by_provider[r["provider"]] = by_provider.get(r["provider"], 0) + 1
            by_model[r["model"]] = by_model.get(r["model"], 0) + 1
        return {"by_provider": by_provider, "by_model": by_model,
                "total": sum(by_provider.values())}

    def recent(self, limit: int = 8) -> list[dict]:
        rows = db.query(
            "SELECT task_id, worker_id, capability, provider, model, reason, "
            "privacy_sensitive, ts FROM task_routes ORDER BY route_id DESC LIMIT ?",
            (limit,))
        return [dict(r) for r in rows]

    def for_task(self, task_id: str) -> list[dict]:
        rows = db.query(
            "SELECT worker_id, capability, provider, model, fallbacks_json, reason, "
            "privacy_sensitive, ts FROM task_routes WHERE task_id=? ORDER BY route_id",
            (task_id,))
        out = []
        for r in rows:
            d = dict(r)
            d["fallbacks"] = json.loads(d.pop("fallbacks_json") or "[]")
            d["privacy_sensitive"] = bool(d["privacy_sensitive"])
            out.append(d)
        return out

    # ---- Phase 8.2: provider adapters + actual model calls ----
    def _providers(self) -> tuple[Any | None, Any | None]:
        c = self.config
        lp = self._local_provider
        if lp is None:
            ep = (c.LOCAL_ENDPOINT or "").strip()
            if ep:
                lp = OpenAICompatProvider(ep, name="local")
        cp = self._cloud_provider
        if cp is None:
            # ChatAnywhere free relay preferred (OpenAI-compatible, free key);
            # OpenRouter remains the fallback cloud provider.
            cak = _find_chatanywhere_key(c)
            if cak:
                ep = (getattr(c, "CHATANYWHERE_ENDPOINT", "") or "").strip() or "https://api.chatanywhere.tech/v1"
                cp = OpenAICompatProvider(ep, api_key=cak, name="chatanywhere")
            else:
                key = _find_api_key(c)
                if key:
                    cp = OpenRouterProvider(api_key=key)
        return lp, cp

    def provider_status(self) -> dict:
        lp, cp = self._providers()
        c = self.config
        chatanywhere = bool(_find_chatanywhere_key(c))
        return {
            "local_configured": bool(lp),
            "local_endpoint": (c.LOCAL_ENDPOINT or "").strip() or None,
            "local_model": (getattr(c, "LOCAL_MODEL", "") or "").strip() or None,
            "openrouter_configured": bool(_find_api_key(c)) or self._cloud_provider is not None,
            "chatanywhere_configured": chatanywhere,
            "chatanywhere_endpoint": (getattr(c, "CHATANYWHERE_ENDPOINT", "") or "").strip() or None,
            "chatanywhere_model": (getattr(c, "CHATANYWHERE_MODEL", "") or "").strip() or None,
        }

    def _effective_model(self, kind: str, model: str, provider: Any) -> str:
        """Map a routed model name to what the actual provider expects.
        ChatAnywhere (free relay) only serves its own model list, so route
        names like anthropic/* are rewritten to CHATANYWHERE_MODEL."""
        if provider is not None and getattr(provider, "name", "") == "chatanywhere":
            return (getattr(self.config, "CHATANYWHERE_MODEL", "") or "").strip() or model
        return model

    def call(self, decision: RouteDecision, messages: list[dict],
             temperature: float = 0.7, max_tokens: int | None = None,
             timeout_s: int = 90) -> CallResult:
        """Invoke the routed model; on failure walk the decision's fallback
        chain. Local primary calls use config.LOCAL_MODEL as the model name
        (LOCAL_ENDPOINT is a base URL, not a model). Returns a CallResult and
        audit-logs model_called / model_call_failed."""
        lp, cp = self._providers()
        t0 = time.time()
        attempts: list[dict] = []

        def _attempt(kind: str, model: str, provider: Any, note: str = "") -> str | None:
            if provider is None:
                attempts.append({"provider": kind, "model": model, "ok": False,
                                 "error": note or f"{kind} provider not configured"})
                return None
            try:
                text = provider.call(model, messages, temperature=temperature,
                                     max_tokens=max_tokens)
                attempts.append({"provider": kind, "model": model, "ok": True})
                return text
            except Exception as e:  # noqa: BLE001 - any provider failure -> fallback
                attempts.append({"provider": kind, "model": model, "ok": False,
                                 "error": str(e)})
                return None

        # primary
        text: str | None = None
        used_provider = ""
        used_model = ""
        used_fallback = False
        cm = decision.model
        if decision.provider == "local":
            local_model = (getattr(self.config, "LOCAL_MODEL", "") or "").strip()
            if not local_model:
                attempts.append({"provider": "local", "model": decision.model,
                                 "ok": False,
                                 "error": "LOCAL_MODEL not configured (local endpoint is a base URL)"})
            else:
                text = _attempt("local", local_model, lp)
                if text is not None:
                    used_provider, used_model = "local", local_model
        else:
            cm = self._effective_model("cloud", decision.model, cp)
            text = _attempt("cloud", cm, cp)
            if text is not None:
                used_provider, used_model = "cloud", cm

        # fallbacks (skip the model already tried)
        if text is None:
            for m in decision.fallbacks:
                fm = self._effective_model("cloud", m, cp)
                if fm in (decision.model, cm, used_model):
                    continue
                t2 = _attempt("cloud", fm, cp)
                if t2 is not None:
                    text, used_provider, used_model = t2, "cloud", fm
                    used_fallback = True
                    break

        duration_ms = int((time.time() - t0) * 1000)
        ok = text is not None
        result = CallResult(ok=ok, text=text or "", provider=used_provider,
                            model=used_model, duration_ms=duration_ms,
                            fallback_used=used_fallback, attempts=attempts)
        if self.audit is not None:
            try:
                self.audit("MB", "model_provider",
                           "model_called" if ok else "model_call_failed",
                           reason=(f"provider={used_provider} model={used_model} "
                                   f"attempts={len(attempts)} fallback={result.fallback_used} "
                                   f"duration_ms={duration_ms}"))
            except Exception:  # noqa: BLE001 - audit must never break a call
                pass
        return result
