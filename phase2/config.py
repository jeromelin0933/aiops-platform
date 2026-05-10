# phase2/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ── 資料來源 ──────────────────────────────────────────────────────────────────
PROMETHEUS_URL  = os.getenv("PROMETHEUS_URL",  "http://localhost:9090")
LOKI_URL        = os.getenv("LOKI_URL",        "http://localhost:3100")

# ── 特徵視窗 ──────────────────────────────────────────────────────────────────
# 每次取「過去 2 分鐘」的資料來計算特徵
FEATURE_WINDOW_MINUTES = int(os.getenv("FEATURE_WINDOW_MINUTES", "2"))

# ── 推論排程 ──────────────────────────────────────────────────────────────────
INFERENCE_INTERVAL_SECONDS = int(os.getenv("INFERENCE_INTERVAL_SECONDS", "15"))

# ── 模型 ──────────────────────────────────────────────────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "models/isolation_forest.pkl")

# Isolation Forest 超參數
IF_N_ESTIMATORS  = 200
IF_CONTAMINATION = 0.05   # 預期約 5% 為異常（1-4 分崩潰 / 總時間）
IF_RANDOM_STATE  = 42

# ── 告警 ──────────────────────────────────────────────────────────────────────
ALERT_STORE_PATH = os.getenv("ALERT_STORE_PATH", "alerts/alert_store.jsonl")

# 異常分數低於此值才發出告警
ANOMALY_SCORE_THRESHOLD = float(os.getenv("ANOMALY_SCORE_THRESHOLD", "-0.05"))

# ── Phase 1 劇本時間軸設定 ────────────────────────────────────────────────────
# 訓練時跳過崩潰期；讓訓練腳本知道要等多久才開始收資料
CRASH_PERIOD_MINUTES = 4