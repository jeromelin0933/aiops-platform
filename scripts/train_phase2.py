# scripts/train_phase2.py

import sys, os, time, logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrainScript")

from phase2.connectors.prometheus import PrometheusConnector
from phase2.connectors.loki import LokiConnector
from phase2.features.schema import RawWindow
from phase2.features.extractor import FeatureExtractor
from phase2.detector.isolation_forest import AnomalyDetector
from phase2.config import FEATURE_WINDOW_MINUTES, CRASH_PERIOD_MINUTES

def collect_training_data() -> list:
    prom_conn, loki_conn, extractor = PrometheusConnector(), LokiConnector(), FeatureExtractor()
    now = datetime.now(timezone.utc)
    
    # 往回撈 20 分鐘的資料 (每 30 秒取樣一次)
    collect_end   = now - timedelta(seconds=30)
    collect_start = collect_end - timedelta(minutes=20)
    
    feature_vectors = []
    current = collect_start + timedelta(minutes=FEATURE_WINDOW_MINUTES)
    
    while current <= collect_end:
        start = current - timedelta(minutes=FEATURE_WINDOW_MINUTES)
        try:
            metrics = prom_conn.fetch_metrics(start, current)
            logs = loki_conn.fetch_logs(start, current)
            raw = RawWindow(window_start=start, window_end=current, **metrics, **logs)
            feature_vectors.append(extractor.extract(raw))
        except Exception:
            pass
        current += timedelta(seconds=30)
    return feature_vectors

def main():
    print(f"\n【重要】請確認系統已啟動超過 {CRASH_PERIOD_MINUTES + 1} 分鐘（已避開崩潰期）")
    input("按 Enter 開始收集正常資料並訓練模型...\n")
    
    fvs = collect_training_data()
    if not fvs:
        print("❌ 未收集到資料，請確認 Docker 和 Python 模擬器正在運行。")
        return
        
    print(f"✅ 成功收集 {len(fvs)} 筆特徵向量，開始訓練...")
    AnomalyDetector().train(fvs)
    print("🎉 訓練完成！模型已儲存至 models/isolation_forest.pkl")

if __name__ == "__main__":
    main()