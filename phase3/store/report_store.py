# phase3/store/report_store.py

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from phase3.config import ALERT_STORE_PATH, REPORT_STORE_PATH
from phase3.llm.gemini_caller import RcaReport

logger = logging.getLogger("ReportStore")


class ReportStore:
    """
    負責讀寫 RCA 報告，並將結果回寫至原始 alert 紀錄。

    檔案格式：JSONL（每行一個完整 JSON）
    - report_store.jsonl：完整 RCA 報告
    - alert_store.jsonl：原始告警（rca_result 欄位由此更新）
    """

    def __init__(self,
                 report_path: str = REPORT_STORE_PATH,
                 alert_path:  str = ALERT_STORE_PATH):
        self.report_path = Path(report_path)
        self.alert_path  = Path(alert_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 寫入 ──────────────────────────────────────────────────────────────────

    def save_report(self, report: RcaReport, log_context: dict) -> dict:
        """儲存完整 RCA 報告並回寫 alert 的 rca_result 欄位"""
        record = {
            "report_id":   f"RCA-{report.alert_id}",
            "alert_id":    report.alert_id,
            "generated_at": report.generated_at,
            "rca":         report.to_dict(),
            "log_context": {
                "window_start":  log_context.get("window_start"),
                "window_end":    log_context.get("window_end"),
                "total_fetched": log_context.get("total_fetched"),
            },
        }

        # 寫入 report_store.jsonl
        with open(self.report_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 回寫 alert_store.jsonl（重寫整個檔案，Demo 規模下可接受）
        self._update_alert_rca(report.alert_id, record["report_id"])

        logger.info(f"Report saved: {record['report_id']}")
        return record

    def _update_alert_rca(self, alert_id: str, report_id: str):
        """將 report_id 寫回 alert_store.jsonl 的 rca_result 欄位"""
        if not self.alert_path.exists():
            return
        lines = self.alert_path.read_text(encoding="utf-8").strip().splitlines()
        updated = []
        for line in lines:
            try:
                alert = json.loads(line)
                if alert.get("alert_id") == alert_id:
                    alert["rca_result"] = report_id
                updated.append(json.dumps(alert, ensure_ascii=False))
            except json.JSONDecodeError:
                updated.append(line)
        self.alert_path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    # ── 讀取 ──────────────────────────────────────────────────────────────────

    def read_all_reports(self) -> list[dict]:
        """讀取所有 RCA 報告，按時間倒序"""
        if not self.report_path.exists():
            return []
        lines = self.report_path.read_text(encoding="utf-8").strip().splitlines()
        reports = []
        for line in lines:
            try:
                reports.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return list(reversed(reports))   # 最新的排前面

    def read_report(self, report_id: str) -> Optional[dict]:
        """讀取指定 report_id 的單一報告"""
        for report in self.read_all_reports():
            if report.get("report_id") == report_id:
                return report
        return None

    def read_all_alerts(self) -> list[dict]:
        """讀取所有 alert（含 rca_result 狀態）"""
        if not self.alert_path.exists():
            return []
        lines = self.alert_path.read_text(encoding="utf-8").strip().splitlines()
        alerts = []
        for line in lines:
            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return list(reversed(alerts))