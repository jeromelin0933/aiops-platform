# phase2/connectors/loki.py

import logging
from datetime import datetime
import requests

from phase2.connectors.base import BaseConnector
from phase2.config import LOKI_URL

logger = logging.getLogger("LokiConnector")

class LokiConnector(BaseConnector):
    def __init__(self, url: str = LOKI_URL):
        self.url = url

    def _count_logs(self, start: datetime, end: datetime, query: str, limit: int = 2000) -> int:
        start_ns = int(start.timestamp() * 1e9)
        end_ns   = int(end.timestamp() * 1e9)
        try:
            r = requests.get(
                f"{self.url}/loki/api/v1/query_range",
                params={"query": query, "start": start_ns, "end": end_ns, "limit": limit, "direction": "forward"},
                timeout=10,
            )
            r.raise_for_status()
            streams = r.json().get("data", {}).get("result", [])
            return sum(len(s.get("values", [])) for s in streams)
        except Exception as e:
            logger.warning(f"Loki query failed: {e}")
            return 0

    def fetch_metrics(self, start: datetime, end: datetime) -> dict:
        return {}

    def fetch_logs(self, start: datetime, end: datetime) -> dict:
        total = self._count_logs(start, end, '{job="aiops_simulator"}')
        error = self._count_logs(start, end, '{job="aiops_simulator"} | json | level="ERROR"')
        warn  = self._count_logs(start, end, '{job="aiops_simulator"} | json | level="WARN"')
        return {
            "log_total_count": total,
            "log_error_count": error,
            "log_warn_count":  warn,
        }

    def fetch(self, start: datetime, end: datetime):
        return self.fetch_logs(start, end)