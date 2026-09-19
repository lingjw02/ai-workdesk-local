"""Resolved Phase-1 configuration.

Open Decisions from Spec v0.1 §7 are locked here with MVP defaults;
the full rationale lives in DECISIONS.md. Override WORKDESK_DB to relocate the database.
"""
import os
from pathlib import Path

APP_NAME = "ai-workdesk-local"
SCHEMA_VERSION = "0.1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # ai-workdesk-local/
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = DATA_DIR / "out"
DB_PATH = Path(os.environ.get("WORKDESK_DB", str(DATA_DIR / "workdesk.db")))

# ---- Spec 01 §2.8: retry & failure policy ----
RETRY_TOOL = 3                 # tool call retries
RETRY_WORKER_STAGE = 2         # worker stage retries
RETRY_MESSAGE = 5              # message delivery retries
MAX_REWORK_CYCLES = 3          # QA-2 -> rework cycles before FAILED
BACKOFF_BASE_SEC = 1.0
GRACEFUL_CANCEL_S = 30         # Stop protocol graceful window
CHECKPOINT_KEEP = 3            # checkpoints retained per task

# ---- Spec 02 §3.6: timeouts & heartbeats ----
REQUEST_DEFAULT_TIMEOUT_S = 120
HEARTBEAT_WORKER_S = 30
HEARTBEAT_PM_S = 15

# ---- Spec 03: permission defaults ----
# Demo/tests default to auto-approve. Production MUST run with AUTO_APPROVE_DEFAULT = False.
AUTO_APPROVE_DEFAULT = True

# ---- Learning (Spec 03 §4.5) ----
LESSON_PROMOTE_MIN_EVIDENCE = 2   # corroborating cases required for promotion

# ---- Phase 8: hybrid model routing defaults (env overrides live in core/config) ----
INSTANT_MODEL = "openai/gpt-4o-mini"
EXPERT_MODEL = "anthropic/claude-sonnet-4.5"
WORKER_MODEL = "anthropic/claude-sonnet-4.5"
LOCAL_ENDPOINT = ""               # e.g. http://localhost:11434/v1 for Ollama
LOCAL_MODEL = ""                  # actual local model name, e.g. qwen2.5:7b
CHATANYWHERE_API_KEY = os.getenv("CHATANYWHERE_API_KEY", "")
CHATANYWHERE_ENDPOINT = os.getenv("CHATANYWHERE_ENDPOINT", "https://api.chatanywhere.tech/v1")
CHATANYWHERE_MODEL = os.getenv("CHATANYWHERE_MODEL", "gpt-4o-mini")

