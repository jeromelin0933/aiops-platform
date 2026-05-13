# phase3/retriever/loki_retriever.py

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from phase3.config import LOKI_URL, LOG_RETRIEVAL_WINDOW_MINUTES, LOG_MAX_LINES

logger = logging.getLogger("LokiRetriever")


class LogEntry:
    """單筆 Log 結構"""
    __slots__ = ("timestamp", "level", "service", "endpoint",
                 "status_code", "response_time_ms", "message", "raw")

    def __init__(self, ts: str, line: str):
        self.timestamp = ts
        self.raw = line
        try:
            d = json.loads(line)
            self.level           = d.get("level", "INFO")
            self.service         = d.get("service", "unknown")
            self.endpoint        = d.get("endpoint", "")
            self.status_code     = d.get("status_code", "")
            self.response_time_ms = d.get("response_time_ms", "")
            self.message         = d.get("error_message") or d.get("message") or ""
        except json.JSONDecodeError:
            self.level, self.service = "INFO", "unknown"
            self.endpoint = self.message = ""
            self.status_code = self.response_time_ms = ""

    def to_text(self) -> str:
        parts = [f"[{self.timestamp}]", f"[{self.level}]"]
        if self.service:
            parts.append(self.service)
        if self.endpoint:
            parts.append(self.endpoint)
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        if self.response_time_ms:
            parts.append(f"{self.response_time_ms}ms")
        if self.message:
            parts.append(f"| {self.message}")
        return " ".join(str(p) for p in parts)


class LokiRetriever:
    """
    RAG 層：根據 alert timestamp 往前撈取 Loki log。

    ⚠️ Demo 妥協：直接 HTTP query，無向量化，僅做關鍵字過濾（level=ERROR/WARN）。
    🚀 未來升級：
       - 對 log 做 embedding（如 nomic-embed-text），存入向量資料庫
       - 改為語意相似度檢索，召回與「告警症狀最相關」的 log，而非單純按時間
       - 結合 BM25 + 向量的 Hybrid Search 提升召回率
    """

    def __init__(self, url: str = LOKI_URL):
        self.url = url

    def retrieve(self, alert_triggered_at: str,
                 window_minutes: int = LOG_RETRIEVAL_WINDOW_MINUTES,
                 max_lines: int = LOG_MAX_LINES) -> dict:
        """
        以 alert_triggered_at 為結束時間，往前 window_minutes 分鐘撈 log。

        Returns:
            {
                "error_logs":  list[str],   # ERROR level log 文字列表
                "warn_logs":   list[str],   # WARN level log 文字列表
                "total_fetched": int,
                "window_start": str,
                "window_end":   str,
            }
        """
        try:
            end_dt   = datetime.fromisoformat(alert_triggered_at.replace("Z", "+00:00"))
        except ValueError:
            end_dt   = datetime.now(timezone.utc)

        start_dt = end_dt - timedelta(minutes=window_minutes)
        start_ns = int(start_dt.timestamp() * 1e9)
        end_ns   = int(end_dt.timestamp()   * 1e9)

        error_entries = self._query(start_ns, end_ns, "ERROR", max_lines // 2)
        warn_entries  = self._query(start_ns, end_ns, "WARN",  max_lines // 2)

        logger.info(
            f"Retrieved {len(error_entries)} ERROR + {len(warn_entries)} WARN logs "
            f"from {start_dt.strftime('%H:%M:%S')} to {end_dt.strftime('%H:%M:%S')}"
        )

        return {
            "error_logs":    [e.to_text() for e in error_entries],
            "warn_logs":     [e.to_text() for e in warn_entries],
            "total_fetched": len(error_entries) + len(warn_entries),
            "window_start":  start_dt.isoformat(),
            "window_end":    end_dt.isoformat(),
        }

    def _query(self, start_ns: int, end_ns: int,
               level: str, limit: int) -> list[LogEntry]:
        """向 Loki 查詢指定 level 的 log"""
        try:
            r = requests.get(
                f"{self.url}/loki/api/v1/query_range",
                params={
                    "query":     f'{{job="aiops_simulator"}} | json | level="{level}"',
                    "start":     start_ns,
                    "end":       end_ns,
                    "limit":     limit,
                    "direction": "forward",
                },
                timeout=10,
            )
            r.raise_for_status()
            streams = r.json().get("data", {}).get("result", [])
            entries = []
            for stream in streams:
                for ts_ns, line in stream.get("values", []):
                    # Loki 回傳的時間戳是奈秒字串，轉為可讀格式
                    ts_dt = datetime.fromtimestamp(
                        int(ts_ns) / 1e9, tz=timezone.utc
                    ).strftime("%H:%M:%S.%f")[:-3]
                    entries.append(LogEntry(ts_dt, line))
            # 按時間排序（Loki 多 stream 可能亂序）
            entries.sort(key=lambda e: e.timestamp)
            return entries

        except Exception as e:
            logger.warning(f"Loki query [{level}] failed: {e}")
            return []