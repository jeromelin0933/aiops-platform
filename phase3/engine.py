# phase3/engine.py

import logging

from phase3.retriever.loki_retriever import LokiRetriever
from phase3.prompt.builder import PromptBuilder
from phase3.llm.gemini_caller import GeminiCaller
from phase3.store.report_store import ReportStore
from phase3.watcher.alert_watcher import AlertWatcher
from phase3.config import LOG_RETRIEVAL_WINDOW_MINUTES

logger = logging.getLogger("Phase3Engine")


class Phase3Engine:
    """
    Phase 3 主引擎：串接 Watcher → Retriever → Prompt → LLM → Store
    """

    def __init__(self):
        self.retriever = LokiRetriever()
        self.builder   = PromptBuilder()
        self.llm       = GeminiCaller()
        self.store     = ReportStore()
        self.watcher   = AlertWatcher(on_new_alert=self.process_alert)

    def process_alert(self, alert: dict) -> None:
        """
        完整 RCA Pipeline：接收一筆 Alert → 產出 RcaReport → 儲存
        由 AlertWatcher 的背景執行緒呼叫，需要 thread-safe。
        """
        alert_id = alert.get("alert_id", "unknown")
        logger.info(f"Processing alert: {alert_id}")

        # Step 1：RAG — 從 Loki 撈 log context
        log_context = self.retriever.retrieve(
            alert_triggered_at = alert.get("triggered_at", ""),
            window_minutes     = LOG_RETRIEVAL_WINDOW_MINUTES,
        )
        log_context["window_minutes"] = LOG_RETRIEVAL_WINDOW_MINUTES

        # Step 2：組裝 Prompt
        system_prompt, user_prompt = self.builder.build(alert, log_context)

        # Step 3：呼叫 LLM
        report = self.llm.call(
            system_prompt = system_prompt,
            user_prompt   = user_prompt,
            alert_id      = alert_id,
        )

        # Step 4：儲存報告
        record = self.store.save_report(report, log_context)
        logger.info(
            f"RCA complete: {record['report_id']} | "
            f"severity={report.severity_assessment} | "
            f"confidence={report.confidence_overall}"
        )

    def start(self) -> None:
        """啟動背景監看（non-blocking，主執行緒繼續跑 Web Server）"""
        self.watcher.start()
        logger.info("Phase 3 Engine started — watching for new alerts")