"""Phase 8 — hybrid model router tests.

Covers the routing policy (privacy -> local first, simple -> instant,
complex -> expert, vision -> multimodal, default -> worker model), the
fallback chains, the persisted decision record (task_routes), the audit
trace (model_routed), engine integration (a submitted task records routes
for each planned worker), and the session-scoped UI read models
(conversation_id filtering for tasks / office / approvals).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workdesk import db
from workdesk.engine import Engine
from workdesk.model_router import ModelRouter, RouteRequest, RouteDecision


class _StubConfig:
    """A config stand-in so unit tests can control LOCAL_ENDPOINT presence."""
    INSTANT_MODEL = "openai/gpt-4o-mini"
    EXPERT_MODEL = "anthropic/claude-sonnet-4.5"
    WORKER_MODEL = "anthropic/claude-sonnet-4.5"
    LOCAL_ENDPOINT = ""          # no local endpoint by default
    OPENROUTER_API_KEY = ""
    CHATANYWHERE_API_KEY = ""
    __slots__ = ()


class _LocalConfig(_StubConfig):
    LOCAL_ENDPOINT = "http://localhost:11434/v1"


class TestRouterPolicy(unittest.TestCase):
    def setUp(self):
        self.no_local = ModelRouter(_StubConfig())
        self.local = ModelRouter(_LocalConfig())

    def test_privacy_without_local_falls_back_to_cloud_with_limitation(self):
        d = self.no_local.route(RouteRequest("t1", "w1", capability="data",
                                             complexity="complex", privacy="sensitive"))
        self.assertTrue(d.privacy_sensitive)
        self.assertEqual(d.provider, "cloud")
        self.assertIn("no LOCAL_ENDPOINT", d.reason)
        self.assertTrue(d.fallbacks)

    def test_privacy_with_local_stays_on_machine(self):
        d = self.local.route(RouteRequest("t1", "w1", capability="data",
                                          complexity="complex", privacy="sensitive"))
        self.assertTrue(d.privacy_sensitive)
        self.assertEqual(d.provider, "local")
        self.assertEqual(d.model, "http://localhost:11434/v1")

    def test_simple_with_local_uses_instant_local(self):
        d = self.local.route(RouteRequest("t1", "w1", capability="classifier",
                                          complexity="simple", privacy="public",
                                          task_type="classification"))
        self.assertEqual(d.provider, "local")

    def test_simple_without_local_uses_cloud_instant(self):
        d = self.no_local.route(RouteRequest("t1", "w1", capability="classifier",
                                             complexity="simple", privacy="public",
                                             task_type="classification"))
        self.assertEqual(d.provider, "cloud")
        self.assertEqual(d.model, "openai/gpt-4o-mini")

    def test_complex_routes_to_expert_cloud(self):
        d = self.no_local.route(RouteRequest("t1", "w1", capability="coding",
                                             complexity="complex", privacy="public",
                                             task_type="code"))
        self.assertEqual(d.provider, "cloud")
        self.assertEqual(d.model, "anthropic/claude-sonnet-4.5")

    def test_vision_capability_pins_multimodal(self):
        d = self.no_local.route(RouteRequest("t1", "w1", capability="vision",
                                             complexity="normal", privacy="public"))
        self.assertEqual(d.provider, "cloud")
        self.assertIn("vision", d.reason)

    def test_default_worker_model(self):
        d = self.no_local.route(RouteRequest("t1", "w1", capability="writer",
                                             complexity="normal", privacy="public",
                                             task_type="default"))
        self.assertEqual(d.model, "anthropic/claude-sonnet-4.5")

    def test_model_hint_local_forces_local_when_available(self):
        d = self.local.route(RouteRequest("t1", "w1", capability="coder",
                                          complexity="complex", privacy="public",
                                          model_hint="local"))
        self.assertEqual(d.provider, "local")


class TestRouterPersistence(unittest.TestCase):
    def test_record_persists_and_audits(self):
        db.reset()
        engine = Engine()   # in-memory db
        self.assertEqual(engine.model_router.stats()["total"], 0)
        req = RouteRequest("task-1", "coder", capability="coding",
                           complexity="complex", privacy="public", task_type="code")
        d = engine.model_router.route(req)
        engine.model_router.record(req, d)
        st = engine.model_router.stats()
        self.assertEqual(st["total"], 1)
        self.assertEqual(st["by_provider"].get("cloud"), 1)
        rows = engine.model_router.recent(5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["worker_id"], "coder")
        audited = [r for r in engine.permissions.timeline()
                   if r["action"] == "model_routed" and r["task_id"] == "task-1"]
        self.assertEqual(len(audited), 1)
        self.assertIn("coder", audited[0]["reason"])


class TestEngineIntegration(unittest.TestCase):
    def test_task_execution_records_routes(self):
        db.reset()
        engine = Engine()
        engine.seed_worker("researcher", "Alex Researcher", {"research": {"capability": "research"}})
        engine.seed_worker("documenter", "Taylor Documenter", {"writer": {"capability": "writer"}})
        task = engine.submit("Research Python 3.13 features and write a markdown report about it.")
        self.assertEqual(task.state.value, "COMPLETED")
        routes = engine.model_router.for_task(task.task_id)
        self.assertTrue(routes, "a completed task should have recorded model routes")
        comps = (task.spec or {}).get("components") or []
        self.assertGreaterEqual(len(routes), len(comps) and 1)
        for r in routes:
            self.assertTrue(r["provider"])
            self.assertTrue(r["model"])
            self.assertIn("fallbacks", r)

    def test_sensitive_task_routes_flagged(self):
        db.reset()
        engine = Engine()
        engine.seed_worker("data_analyst", "Morgan", {"data": {"capability": "data"}})
        engine.seed_worker("researcher", "Alex", {"research": {"capability": "research"}})
        # "salary" keyword marks the spec sensitive (main_brain SENSITIVE list)
        task = engine.submit("Analyze my salary dataset and summarize the numbers.",
                             ctx={"inputs": {"dataset": {"region": ["E"], "q3": [5]}},
                                  "output_type": "report"})
        self.assertEqual(task.state.value, "COMPLETED")
        routes = engine.model_router.for_task(task.task_id)
        self.assertTrue(routes)
        self.assertTrue(any(r["privacy_sensitive"] for r in routes),
                        "sensitive tasks must be routed with the privacy flag on")


class TestSessionScoping(unittest.TestCase):
    def test_conversation_scoped_read_models(self):
        db.reset()
        engine = Engine()
        engine.seed_worker("coder", "Jordan", {"coding": {"capability": "coding"}})
        engine.seed_worker("writer", "Taylor", {"writer": {"capability": "writer"}})
        t1 = engine.submit("Write a python demo script.", ctx={"conversation_id": "conv-a"})
        t2 = engine.submit("Write a document about the project.",
                           ctx={"conversation_id": "conv-b", "output_type": "document"})
        self.assertEqual(t1.state.value, "COMPLETED")
        self.assertEqual(t2.state.value, "COMPLETED")
        # tasks scoped per conversation
        a = engine.list_tasks(conversation_id="conv-a")
        b = engine.list_tasks(conversation_id="conv-b")
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)
        self.assertEqual(a[0]["task_id"], t1.task_id)
        self.assertEqual(a[0]["conversation_id"], "conv-a")
        # office snapshot scoped per conversation
        vo_a = engine.virtual_office("conv-a")
        vo_b = engine.virtual_office("conv-b")
        self.assertEqual(sum(vo_a["task_states"].values()), 1)
        self.assertEqual(sum(vo_b["task_states"].values()), 1)
        self.assertTrue(all(w["id"] in ("coder",) for w in vo_a["workers"]),
                        "conv-a used only the coding worker")
        # approvals scoped per conversation
        self.assertEqual(len(engine.approvals_pending("conv-a")), 0)
        self.assertEqual(len(engine.approvals_pending()), 0)

    def test_approval_scoped_to_conversation(self):
        db.reset()
        engine = Engine(auto_approve=False)
        engine.seed_worker("coder", "Jordan", {"coding": {"capability": "coding"}})
        task = engine.submit("Write a python demo script.", ctx={"conversation_id": "conv-x"})
        self.assertEqual(task.state.value, "COMPLETED")
        # with auto_approve off and a coder that uses tools, PENDING approvals
        # may exist for the tool actions; verify the scoped query returns the
        # same rows as the unscoped one (all belong to conv-x tasks)
        pending_all = engine.approvals_pending()
        pending_x = engine.approvals_pending("conv-x")
        pending_other = engine.approvals_pending("conv-none")
        self.assertEqual(len(pending_all), len(pending_x))
        self.assertEqual(len(pending_other), 0)


class TestEngineSettingsRouter(unittest.TestCase):
    def test_settings_includes_router_stats(self):
        db.reset()
        engine = Engine()
        engine.seed_worker("coder", "Jordan", {"coding": {"capability": "coding"}})
        engine.submit("Write a python demo script.")
        s = engine.settings_snapshot()
        self.assertIn("counts", s)
        self.assertGreaterEqual(s["counts"].get("tasks", 0), 1)



class _FakeProvider:
    """Injected provider stand-in: fails the first `fail` calls, then returns
    a fixed text suffixed with the model name (no network in tests)."""
    def __init__(self, fail=0, text="hello from model", name="fake"):
        self.calls = []
        self.fail = fail
        self.text = text
        self.name = name

    def call(self, model, messages, temperature=0.7, max_tokens=None):
        self.calls.append(model)
        if len(self.calls) <= self.fail:
            raise ProviderError(f"{self.name} boom on call {len(self.calls)}",
                                kind="http")
        return f"{self.text} [{model}]"


class _LocalWithModel(_LocalConfig):
    LOCAL_MODEL = "qwen2.5:7b"


class TestModelCall(unittest.TestCase):
    """Phase 8.2 — the router actually invokes a model and walks fallbacks."""

    def _router(self, local=None, cloud=None, config=None):
        return ModelRouter(config or _StubConfig(),
                           local_provider=local, cloud_provider=cloud)

    def test_call_primary_cloud_success(self):
        cloud = _FakeProvider(text="hi")
        r = self._router(cloud=cloud).call(
            RouteDecision(provider="cloud", model="openai/gpt-4o-mini",
                          fallbacks=["anthropic/claude-sonnet-4.5"]),
            [{"role": "user", "content": "hi"}])
        self.assertTrue(r.ok)
        self.assertEqual(r.provider, "cloud")
        self.assertEqual(r.model, "openai/gpt-4o-mini")
        self.assertIn("openai/gpt-4o-mini", r.text)
        self.assertFalse(r.fallback_used)
        self.assertEqual(len(r.attempts), 1)

    def test_call_falls_back_after_primary_failure(self):
        cloud = _FakeProvider(fail=1, text="ok")
        r = self._router(cloud=cloud).call(
            RouteDecision(provider="cloud", model="m1", fallbacks=["m2"]),
            [{"role": "user", "content": "hi"}])
        self.assertTrue(r.ok)
        self.assertEqual(r.model, "m2")
        self.assertTrue(r.fallback_used)
        self.assertEqual(cloud.calls, ["m1", "m2"])
        self.assertEqual(len(r.attempts), 2)

    def test_call_all_fail(self):
        cloud = _FakeProvider(fail=99)
        r = self._router(cloud=cloud).call(
            RouteDecision(provider="cloud", model="m1",
                          fallbacks=["m2", "m3"]),
            [{"role": "user", "content": "hi"}])
        self.assertFalse(r.ok)
        self.assertEqual(len(r.attempts), 3)
        self.assertFalse(any(a["ok"] for a in r.attempts))

    def test_call_local_primary_falls_back_to_cloud(self):
        local = _FakeProvider(fail=1, text="local")
        cloud = _FakeProvider(text="cloud")
        r = self._router(local=local, cloud=cloud, config=_LocalWithModel()).call(
            RouteDecision(provider="local", model="http://localhost:11434/v1",
                          fallbacks=["openai/gpt-4o-mini"]),
            [{"role": "user", "content": "hi"}])
        self.assertTrue(r.ok)
        self.assertEqual(r.provider, "cloud")
        self.assertEqual(r.model, "openai/gpt-4o-mini")
        self.assertTrue(r.fallback_used)
        self.assertEqual(local.calls, ["qwen2.5:7b"])
        self.assertEqual(len(r.attempts), 2)

    def test_call_local_without_model_name_skips_to_cloud(self):
        local = _FakeProvider()
        cloud = _FakeProvider(text="cloud")
        r = self._router(local=local, cloud=cloud, config=_LocalConfig()).call(
            RouteDecision(provider="local", model="http://localhost:11434/v1",
                          fallbacks=["openai/gpt-4o-mini"]),
            [{"role": "user", "content": "hi"}])
        self.assertTrue(r.ok)
        self.assertEqual(r.model, "openai/gpt-4o-mini")
        self.assertEqual(len(r.attempts), 2)
        self.assertIn("LOCAL_MODEL not configured", r.attempts[0]["error"])
        self.assertEqual(local.calls, [])  # never invoked without a model name

    def test_call_audits_and_provider_status(self):
        events = []
        cfg = _LocalWithModel()
        router = ModelRouter(
            cfg, audit=lambda *a, **k: events.append((a, k)),
            local_provider=_FakeProvider(), cloud_provider=_FakeProvider())
        r = router.call(
            RouteDecision(provider="cloud", model="m1", fallbacks=["m2"]),
            [{"role": "user", "content": "hi"}])
        self.assertTrue(r.ok)
        self.assertTrue(any("model_called" in a[0] for a in events))
        st = router.provider_status()
        self.assertTrue(st["local_configured"])
        self.assertEqual(st["local_endpoint"], "http://localhost:11434/v1")
        self.assertEqual(st["local_model"], "qwen2.5:7b")
        self.assertTrue(st["openrouter_configured"])

    def test_chatanywhere_maps_routed_models(self):
        class _CAConfig(_LocalWithModel):
            CHATANYWHERE_MODEL = "gpt-4o-mini"

        calls: list[str] = []

        class _CA:
            name = "chatanywhere"

            def call(self, model, messages, temperature=0.7, max_tokens=None):
                calls.append(model)
                return "ok"

        r = ModelRouter(_CAConfig(), cloud_provider=_CA()).call(
            RouteDecision(provider="cloud", model="anthropic/claude-sonnet-4.5",
                          fallbacks=["openai/gpt-4o-mini"]),
            [{"role": "user", "content": "hi"}])
        self.assertTrue(r.ok)
        self.assertEqual(calls, ["gpt-4o-mini"],
                         "chatanywhere must rewrite routed model names")

    def test_provider_status_unconfigured(self):
        st = self._router().provider_status()
        self.assertFalse(st["local_configured"])
        self.assertFalse(st["openrouter_configured"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
