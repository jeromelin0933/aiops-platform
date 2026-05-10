# phase2/publisher/alert_publisher.py

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from phase2.detector.isolation_forest import AnomalyResult
from phase2.config import ALERT_STORE_PATH

logger = logging.getLogger("AlertPublisher")

class AlertPublisher:
    def __init__(self, store_path: str = ALERT_STORE_PATH):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def publish(self, result: AnomalyResult) -> dict:
        alert = self._build_alert(result)
        self._write(alert)
        return alert

    def _build_alert(self, result: AnomalyResult) -> dict:
        fv = result.feature_vector
        severity_map = {"high": "critical", "medium": "warning", "low": "info"}
        severity = severity_map.get(result.confidence, "warning")

        # 自動生成事件摘要
        p95, err, corr = fv.get("p95_latency_ms", 0), fv.get("error_rate_pct", 0), fv.get("latency_error_corr", 0)
        if corr > 10000:
            summary = f"嚴重異常：p95 延遲 {p95:.0f}ms 且錯誤率 {err:.1f}%，疑似系統崩潰。"
        elif p95 > 1000:
            summary = f"延遲異常：p95 延遲 {p95:.0f}ms，超過正常值。"
        elif err > 5:
            summary = f"錯誤率異常：5xx 錯誤率達 {err:.1f}%。"
        else:
            summary = f"輕微異常：多項指標輕微偏離正常分佈。"

        return {
            "alert_id":           f"ALERT-{int(datetime.now(timezone.utc).timestamp())}",
            "triggered_at":       result.timestamp,
            "severity":           severity,
            "confidence":         result.confidence,
            "anomaly_score":      result.anomaly_score,
            "summary":            summary,
            "affected_service":   "financial-api",
            "metrics": {
                "p95_latency_ms": fv.get("p95_latency_ms"), "error_rate_pct": fv.get("error_rate_pct"),
            },
            "triggered_features": result.triggered_features,
            "rca_result":         None, # 給 Phase 3 留的位置
        }

    def _write(self, alert: dict) -> None:
        with open(self.store_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")

    def read_latest(self, n: int = 5) -> list:
        if not self.store_path.exists():
            return []
        lines = self.store_path.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(line) for line in lines[-n:]]