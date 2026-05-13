# phase3/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API ────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── Loki ──────────────────────────────────────────────────────────────────────
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")

# RAG：往前撈幾分鐘的 log
LOG_RETRIEVAL_WINDOW_MINUTES = int(os.getenv("LOG_RETRIEVAL_WINDOW_MINUTES", "3"))

# 撈取的 log 上限（避免 prompt 過長）
LOG_MAX_LINES = int(os.getenv("LOG_MAX_LINES", "50"))

# ── 路徑 ──────────────────────────────────────────────────────────────────────
ALERT_STORE_PATH  = os.getenv("ALERT_STORE_PATH",  "alerts/alert_store.jsonl")
REPORT_STORE_PATH = os.getenv("REPORT_STORE_PATH", "reports/report_store.jsonl")

# ── Web Server ────────────────────────────────────────────────────────────────
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

# ── File Watcher ──────────────────────────────────────────────────────────────
# 多久 poll 一次 alert_store.jsonl（秒）
WATCHER_POLL_INTERVAL = int(os.getenv("WATCHER_POLL_INTERVAL", "5"))