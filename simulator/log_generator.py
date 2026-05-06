### 1.2.2 Log 模擬腳本


# simulator/log_generator.py

import json
import time
import random
from datetime import datetime, timezone
from faker import Faker

fake = Faker()

SERVICES = ["account-service", "transfer-service", "credit-service"]
ENDPOINTS = {
    "account-service":  ["/api/v1/account/balance", "/api/v1/account/history"],
    "transfer-service": ["/api/v1/transfer/domestic", "/api/v1/transfer/status"],
    "credit-service":   ["/api/v1/credit/score", "/api/v1/credit/limit"],
}
STATUS_CODES_NORMAL   = [200, 200, 200, 200, 201, 204]
STATUS_CODES_DEGRADED = [200, 500, 503, 504, 408]

def generate_log_entry(is_anomaly: bool = False) -> dict:
    service  = random.choice(SERVICES)
    endpoint = random.choice(ENDPOINTS[service])

    if is_anomaly:
        response_time = random.randint(2000, 8000)
        status_code   = random.choice(STATUS_CODES_DEGRADED)
        error_msg     = random.choice([
            "upstream timeout", "connection pool exhausted",
            "database query timeout", None
        ])
    else:
        response_time = random.randint(80, 300)
        status_code   = random.choice(STATUS_CODES_NORMAL)
        error_msg     = None

    return {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "level":         "ERROR" if status_code >= 500 else "INFO",
        "service":       service,
        "trace_id":      fake.uuid4(),
        "span_id":       fake.uuid4()[:16],
        "endpoint":      endpoint,
        "method":        "GET" if "balance" in endpoint or "score" in endpoint else "POST",
        "status_code":   status_code,
        "response_time_ms": response_time,
        "user_id":       fake.uuid4()[:8],
        "error_message": error_msg,
    }

def stream_logs(output_file: str = "logs/app.log",
                anomaly_windows: list = None):
    """
    anomaly_windows: list of (start_minute, end_minute) tuples
    e.g. [(10, 15), (45, 50)]
    """
    anomaly_windows = anomaly_windows or [(10, 15), (45, 50)]
    start_time = time.time()

    with open(output_file, "a") as f:
        while True:
            elapsed_minutes = (time.time() - start_time) / 60
            is_anomaly = any(s <= elapsed_minutes <= e
                             for s, e in anomaly_windows)
            entry = generate_log_entry(is_anomaly)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            time.sleep(random.uniform(0.1, 0.5))  # ~3–10 req/sec

if __name__ == "__main__":
    print("啟動 Log 模擬器...")
    stream_logs(output_file="logs/app.log")
