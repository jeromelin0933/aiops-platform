### 1.2.3 Metrics 模擬腳本


# simulator/metrics_exporter.py
# Exposes a /metrics endpoint for Prometheus to scrape

from prometheus_client import start_http_server, Histogram, Counter, Gauge
import time, random, threading

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["service", "endpoint"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
)
REQUEST_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "status_code"]
)
ACTIVE_CONNECTIONS = Gauge(
    "db_connection_pool_active",
    "Active DB connections",
    ["service"]
)

is_anomaly_mode = False

def simulate_traffic():
    services = ["account-service", "transfer-service", "credit-service"]
    while True:
        for svc in services:
            latency = (
                random.uniform(2.0, 8.0) if is_anomaly_mode
                else random.uniform(0.08, 0.3)
            )
            REQUEST_LATENCY.labels(service=svc, endpoint="/api/v1/query").observe(latency)
            status = "500" if is_anomaly_mode and random.random() < 0.1 else "200"
            REQUEST_TOTAL.labels(service=svc, status_code=status).inc()
            pool_size = (
                random.randint(90, 100) if is_anomaly_mode
                else random.randint(10, 40)
            )
            ACTIVE_CONNECTIONS.labels(service=svc).set(pool_size)
        time.sleep(1)

if __name__ == "__main__":
    start_http_server(8000)  # Prometheus scrapes :8000/metrics
    threading.Thread(target=simulate_traffic, daemon=True).start()
    # Anomaly trigger: toggle is_anomaly_mode externally via API
    while True:
        time.sleep(1)