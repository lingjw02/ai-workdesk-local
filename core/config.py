import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
PORT = int(os.getenv("PORT", "3787"))
APP_URL = os.getenv("APP_URL", f"http://localhost:{PORT}")
APP_NAME = os.getenv("APP_NAME", "AI WorkDesk OS")

# Model routing defaults
INSTANT_MODEL = os.getenv("INSTANT_MODEL", "openai/gpt-4o-mini")
EXPERT_MODEL = os.getenv("EXPERT_MODEL", "anthropic/claude-sonnet-4.5")
WORKER_MODEL = os.getenv("WORKER_MODEL", "anthropic/claude-sonnet-4.5")
LOCAL_ENDPOINT = os.getenv("LOCAL_ENDPOINT", "")  # e.g., http://localhost:11434/v1 for future Ollama
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "")        # actual local model name, e.g. qwen2.5:7b

# ChatAnywhere free GPT/DeepSeek relay (OpenAI-compatible, https://chatanywhere.tech)
# Free key: register at https://chatanywhere.tech and bind a GitHub account.
CHATANYWHERE_API_KEY = os.getenv("CHATANYWHERE_API_KEY", "")
CHATANYWHERE_ENDPOINT = os.getenv(
    "CHATANYWHERE_ENDPOINT", "https://api.chatanywhere.tech/v1")  # .org for outside CN
CHATANYWHERE_MODEL = os.getenv("CHATANYWHERE_MODEL", "gpt-4o-mini")

DATA_DIR = BASE_DIR / "data"
CONV_DIR = DATA_DIR / "conversations"
PROJ_DIR = DATA_DIR / "projects"
WORKER_DIR = DATA_DIR / "workers"
AUDIT_DIR = DATA_DIR / "audit"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
MEMORY_FILE = DATA_DIR / "memory.json"

for d in [DATA_DIR, CONV_DIR, PROJ_DIR, WORKER_DIR, AUDIT_DIR, CHECKPOINT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
