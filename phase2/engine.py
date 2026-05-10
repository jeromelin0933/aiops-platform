# phase2/engine.py

import logging
import time
from datetime import datetime, timedelta, timezone
import schedule

from phase2.config import FEATURE_WINDOW_MINUTES, INFERENCE_INTERVAL_SECONDS, MODEL_PATH
from phase2.connectors.prometheus import PrometheusConnector
from phase2.connectors.loki import LokiConnector
from phase2.features.schema import RawWindow
from phase2.features.extractor import FeatureExtractor
from phase2.detector.isolation_forest import AnomalyDetector
from phase2.publisher.alert_publisher import AlertPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AIOpsEngine")

class AIOpsEngine:
    def __init__(self):
        self.prom_conn = PrometheusConnector()
        self.loki_conn = LokiConnector()
        self.extractor  = FeatureExtractor()
        self.detector   = AnomalyDetector()
        self.publisher  = AlertPublisher()
        self.detector.load_model(MODEL_PATH)

    def _fetch_raw_window(self) -> RawWindow:
        now   = datetime.now(timezone.utc)
        start = now - timedelta(minutes=FEATURE_WINDOW_MINUTES)
        metrics_data = self.prom_conn.fetch_metrics(start, now)
        logs_data    = self.loki_conn.fetch_logs(start, now)
        return RawWindow(window_start=start, window_end=now, **metrics_data, **logs_data)

    def run_once(self) -> None:
        try:
            raw = self._fetch_raw_window()
            fv  = self.extractor.extract(raw)
            result = self.detector.predict(fv)

            if result.is_anomaly:
                self.publisher.publish(result)
            else:
                logger.info(f"Normal | score={result.anomaly_score:.4f} | p95={fv.p95_latency_ms}ms")
        except Exception as e:
            logger.error(f"Pipeline error: {e}")

    def start(self) -> None:
        logger.info(f"Starting AIOps Engine — interval={INFERENCE_INTERVAL_SECONDS}s")
        schedule.every(INFERENCE_INTERVAL_SECONDS).seconds.do(self.run_once)
        self.run_once()
        while True:
            schedule.run_pending()
            time.sleep(1)