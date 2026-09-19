"""SQLite persistence (Open Decision #1).

Single connection + threading.Lock, WAL journal. All managers share this module-level
connection so records (tasks, transitions, memory, audit, registry) live in one file
and survive restart -- the foundation of Spec 01 §2.7 resume.
"""
import sqlite3
import threading
from pathlib import Path

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  task_id TEXT PRIMARY KEY, request_text TEXT, spec_json TEXT, state TEXT,
  project_id TEXT, group_id TEXT, rework_count INTEGER DEFAULT 0,
  created_ts TEXT, updated_ts TEXT, result_json TEXT);

CREATE TABLE IF NOT EXISTS task_transitions(
  task_id TEXT, seq INTEGER, from_state TEXT, to_state TEXT, trigger TEXT,
  actor TEXT, ts TEXT, payload_json TEXT, PRIMARY KEY(task_id, seq));

CREATE TABLE IF NOT EXISTS task_groups(
  group_id TEXT PRIMARY KEY, task_id TEXT, pm_id TEXT, member_ids_json TEXT,
  requirements_ref TEXT, artifacts_json TEXT, memory_scope_id TEXT,
  created_ts TEXT, closed_ts TEXT);

CREATE TABLE IF NOT EXISTS checkpoints(
  cp_id TEXT PRIMARY KEY, task_id TEXT, snapshot_json TEXT, created_ts TEXT);

CREATE TABLE IF NOT EXISTS memory_records(
  mem_id TEXT PRIMARY KEY, layer TEXT, scope_id TEXT, type TEXT, content TEXT,
  source_role TEXT, source_id TEXT, ts TEXT, confidence TEXT,
  evidence_refs_json TEXT, ttl TEXT, access_scope TEXT, immutable INTEGER, tags_json TEXT);

CREATE TABLE IF NOT EXISTS memory_grants(
  actor_role TEXT, actor_id TEXT, scope_key TEXT, granted_by TEXT, ts TEXT);

CREATE TABLE IF NOT EXISTS policies(
  id INTEGER PRIMARY KEY AUTOINCREMENT, actor_role TEXT, action TEXT,
  resource_pattern TEXT, tool TEXT, condition TEXT, level TEXT, scope TEXT);

CREATE TABLE IF NOT EXISTS approvals(
  approval_id TEXT PRIMARY KEY, request_id TEXT, requester_role TEXT, requester_id TEXT,
  action TEXT, resource TEXT, tool TEXT, level TEXT, status TEXT,
  decision_ts TEXT, decision_context TEXT);

CREATE TABLE IF NOT EXISTS audit_events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, task_id TEXT,
  actor_role TEXT, actor_id TEXT, action TEXT, tool TEXT,
  files_changed_json TEXT, reason TEXT, qa_refs_json TEXT, rework_refs_json TEXT);

CREATE TABLE IF NOT EXISTS workers(
  worker_id TEXT PRIMARY KEY, name TEXT, role_class TEXT, personality_json TEXT,
  behavior_rules_json TEXT, skills_json TEXT, tools_json TEXT, permissions_json TEXT,
  memory_rules_json TEXT, status TEXT, times_triggered INTEGER, tasks_completed INTEGER,
  qa_passed INTEGER, qa_failed INTEGER, failure_rate REAL, avg_execution_time_ms REAL,
  created_ts TEXT, updated_ts TEXT);

CREATE TABLE IF NOT EXISTS pms(
  pm_id TEXT PRIMARY KEY, name TEXT, project_id TEXT, status TEXT,
  knowledge_json TEXT, decisions_json TEXT, lessons_json TEXT, conventions_json TEXT,
  worker_performance_json TEXT, task_history_json TEXT, group_history_json TEXT,
  schema_version INTEGER DEFAULT 1,
  created_ts TEXT, updated_ts TEXT);

CREATE TABLE IF NOT EXISTS lessons(
  lesson_id TEXT PRIMARY KEY, pm_id TEXT, lesson_key TEXT, content TEXT,
  evidence_count INTEGER DEFAULT 1, confidence TEXT, refs_json TEXT,
  status TEXT DEFAULT 'candidate', created_ts TEXT, updated_ts TEXT);

CREATE TABLE IF NOT EXISTS notes(
  note_id TEXT PRIMARY KEY, section TEXT, title TEXT, content TEXT,
  created_ts TEXT, updated_ts TEXT);

CREATE TABLE IF NOT EXISTS qa_verdicts(
  verdict_id TEXT, task_id TEXT, stage TEXT, cycle INTEGER DEFAULT 0,
  component TEXT, criterion TEXT, passed INTEGER, severity TEXT,
  evidence TEXT, fix_hint TEXT, ts TEXT);

CREATE TABLE IF NOT EXISTS skills(
  skill_id TEXT PRIMARY KEY, name TEXT, version TEXT, type TEXT, entry_point TEXT,
  params_json TEXT, tools_required_json TEXT, permissions_required_json TEXT,
  enabled INTEGER, installed_ts TEXT);

CREATE TABLE IF NOT EXISTS task_routes(
  route_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, worker_id TEXT,
  capability TEXT, provider TEXT, model TEXT, fallbacks_json TEXT,
  reason TEXT, privacy_sensitive INTEGER, ts TEXT);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS remote_devices(
      device_id TEXT PRIMARY KEY, name TEXT, host TEXT, status TEXT DEFAULT 'OFFLINE',
      os TEXT, last_seen TEXT, created_ts TEXT, session_json TEXT)""")
    """Additive migrations for databases created before a schema change."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(pms)")}
    for col, ddl in (
        ("worker_performance_json", "ALTER TABLE pms ADD COLUMN worker_performance_json TEXT"),
        ("task_history_json", "ALTER TABLE pms ADD COLUMN task_history_json TEXT"),
        ("group_history_json", "ALTER TABLE pms ADD COLUMN group_history_json TEXT"),
        ("schema_version", "ALTER TABLE pms ADD COLUMN schema_version INTEGER DEFAULT 1"),
    ):
        if col not in cols:
            conn.execute(ddl)
    tcols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}
    if "conversation_id" not in tcols:
        conn.execute("ALTER TABLE tasks ADD COLUMN conversation_id TEXT")
    if "priority" not in tcols:
        conn.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
    acols = {r["name"] for r in conn.execute("PRAGMA table_info(approvals)")}
    if "task_id" not in acols:
        conn.execute("ALTER TABLE approvals ADD COLUMN task_id TEXT")
    # Phase 9: lessons gain a scope (pm|worker|global) + owner + application stats
    lcols = {r["name"] for r in conn.execute("PRAGMA table_info(lessons)")}
    if "scope" not in lcols:
        conn.execute("ALTER TABLE lessons ADD COLUMN scope TEXT DEFAULT 'pm'")
    if "owner_id" not in lcols:
        conn.execute("ALTER TABLE lessons ADD COLUMN owner_id TEXT DEFAULT ''")
    if "applied_count" not in lcols:
        conn.execute("ALTER TABLE lessons ADD COLUMN applied_count INTEGER DEFAULT 0")
    if "last_applied_ts" not in lcols:
        conn.execute("ALTER TABLE lessons ADD COLUMN last_applied_ts TEXT")
    conn.execute("UPDATE lessons SET scope='pm', owner_id=pm_id "
                 "WHERE scope='pm' AND (owner_id IS NULL OR owner_id='')")
    conn.commit()


def init(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open (once) the shared connection. `None` -> in-memory (tests)."""
    global _conn
    if _conn is not None:
        return _conn
    path = Path(db_path) if db_path is not None else None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with _lock:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    _conn = conn
    return conn


def execute(sql: str, params: tuple = ()) -> int:
    with _lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        return cur.lastrowid


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return _conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def reset() -> None:
    """Close the shared connection (tests only)."""
    global _conn
    if _conn is not None:
        with _lock:
            _conn.close()
            _conn = None
