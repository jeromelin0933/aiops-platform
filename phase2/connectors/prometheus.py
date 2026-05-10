# phase2/connectors/prometheus.py

import logging
from datetime import datetime
import requests

from phase2.connectors.base import BaseConnector
from phase2.config import PROMETHEUS_URL

logger = logging.getLogger("PrometheusConnector")

class PrometheusConnector(BaseConnector):
    def __init__(self, url: str = PROMETHEUS_URL):
        self.url = url

    def _instant_query(self, promql: str, at_time: int) -> float:
        try:
            r = requests.get(
                f"{self.url}/api/v1/query",
                params={"query": promql, "time": at_time},
                timeout=8,
            )
            r.raise_for_status()
            results = r.json().get("data", {}).get("result", [])
            if results:
                val = results[0]["value"][1]
                if val in ("NaN", "Inf", "-Inf"):
                    return 0.0
                return float(val)
        except Exception as e:
            logger.warning(f"Prometheus query failed [{promql[:50]}...]: {e}")
        return 0.0

    def fetch_metrics(self, start: datetime, end: datetime) -> dict:
        end_ts   = int(end.timestamp())
        window_seconds = (end - start).total_seconds()
        window_str = f"{int(window_seconds)}s"

        p95 = self._instant_query(
            f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[{window_str}]))', end_ts)
        p50 = self._instant_query(
            f'histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[{window_str}]))', end_ts)
        
        error_rate = self._instant_query(f'rate(http_requests_total{{status_code=~"5.."}}[{window_str}])', end_ts)
        total_rate = self._instant_query(f'rate(http_requests_total[{window_str}])', end_ts)

        db_pool = self._instant_query('db_connection_pool_active', end_ts)

        return {
            "p95_latency_seconds":   p95,
            "p50_latency_seconds":   p50,
            "error_count_5xx":       error_rate * window_seconds,
            "total_request_count":   total_rate * window_seconds,
            "db_pool_active":        db_pool,
            "db_pool_max":           100.0,
        }

    def fetch_logs(self, start: datetime, end: datetime) -> dict:
        return {} # Prometheus 不管 Log