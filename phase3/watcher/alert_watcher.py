# phase3/watcher/alert_watcher.py

import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable

from phase3.config import ALERT_STORE_PATH, WATCHER_POLL_INTERVAL

logger = logging.getLogger("AlertWatcher")


class AlertWatcher:
    """
    監看 alert_store.jsonl，偵測到新告警時觸發回調函式。

    ⚠️ Demo 妥協：用 polling（每 5 秒讀一次檔案末尾）實作。
    🚀 未來升級：改用 watchdog 的 FileSystemEventHandler 做即時 inotify 監聽，
       或訂閱 Kafka topic（Phase 2 直接 publish 到 Kafka，Phase 3 消費）。
    """

    def __init__(self, on_new_alert: Callable[[dict], None],
                 path: str = ALERT_STORE_PATH,
                 poll_interval: int = WATCHER_POLL_INTERVAL):
        self.on_new_alert  = on_new_alert
        self.path          = Path(path)
        self.poll_interval = poll_interval
        self._seen_ids:    set  = set()
        self._stop_event:  threading.Event = threading.Event()
        self._thread:      threading.Thread = None

    def start(self) -> None:
        """在背景執行緒啟動監看"""
        # 初始化：標記現有 alert 為「已見過」，避免重複處理
        self._init_seen_ids()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(
            f"AlertWatcher started (poll interval: {self.poll_interval}s) — "
            f"pre-loaded {len(self._seen_ids)} existing alerts"
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _init_seen_ids(self) -> None:
        """將檔案中現有的 alert_id 全部標記為已處理"""
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").strip().splitlines():
            try:
                alert = json.loads(line)
                if aid := alert.get("alert_id"):
                    self._seen_ids.add(aid)
            except json.JSONDecodeError:
                pass

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._check_new_alerts()
            time.sleep(self.poll_interval)

    def _check_new_alerts(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        except Exception as e:
            logger.warning(f"Read alert_store failed: {e}")
            return

        for line in lines:
            try:
                alert = json.loads(line)
                aid = alert.get("alert_id")
                # 只處理「尚未分析過的」告警（rca_result 為 None）
                if aid and aid not in self._seen_ids and alert.get("rca_result") is None:
                    self._seen_ids.add(aid)
                    logger.info(f"New alert detected: {aid}")
                    try:
                        self.on_new_alert(alert)
                    except Exception as e:
                        logger.error(f"on_new_alert callback failed: {e}", exc_info=True)
            except json.JSONDecodeError:
                pass