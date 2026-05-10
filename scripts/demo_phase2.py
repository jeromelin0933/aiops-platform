# scripts/demo_phase2.py

import sys, os, time, threading, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.ERROR) # 隱藏普通日誌，只留警報

from phase2.engine import AIOpsEngine
from phase2.publisher.alert_publisher import AlertPublisher
import schedule
from phase2.config import INFERENCE_INTERVAL_SECONDS

def watch_alerts(publisher, stop_event):
    seen_ids = set()
    while not stop_event.is_set():
        for alert in publisher.read_latest(n=10):
            if alert["alert_id"] not in seen_ids:
                seen_ids.add(alert["alert_id"])
                print("\n" + "🚨" * 20)
                print(f"  ANOMALY DETECTED: {alert['severity'].upper()}")
                print(f"  Summary : {alert['summary']}")
                print(f"  Score   : {alert['anomaly_score']:.4f}")
                print("🚨" * 20 + "\n")
        time.sleep(5)

def main():
    print("=" * 50)
    print(" AIOps Phase 2: 異常偵測引擎啟動")
    print("=" * 50)
    print("\n👉 請回到你的 VS Code 終端機，將 Phase 1 的兩個水龍頭 (metrics/log) 重新啟動。")
    print("引擎將在 1~4 分鐘內自動捕捉到系統崩潰！\n等待中...\n")

    engine, publisher = AIOpsEngine(), AlertPublisher()
    stop_event = threading.Event()
    threading.Thread(target=watch_alerts, args=(publisher, stop_event), daemon=True).start()

    schedule.every(INFERENCE_INTERVAL_SECONDS).seconds.do(engine.run_once)
    engine.run_once()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        print("\nDemo 結束。")

if __name__ == "__main__":
    main()