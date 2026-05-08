import time
import random
from prometheus_client import start_http_server, Counter

# 定義 Prometheus 指標
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status_code'])

def generate_metrics():
    print("啟動 Metrics 模擬器 (Port 8000)...")
    start_time = time.time()
    
    while True:
        # 計算目前程式已經執行了幾分鐘
        elapsed_minutes = (time.time() - start_time) / 60
        
        # 核心改動：設定第 1 到 4 分鐘為「系統崩潰期」
        is_anomaly = 1 <= elapsed_minutes <= 4
        
        if is_anomaly:
            # 異常狀態：大幅提升 500 錯誤的機率 (70%)
            status = random.choices(['200', '500'], weights=[0.3, 0.7])[0]
        else:
            # 正常狀態：99% 都是 200 正常流量，偶爾有極少數的 500 錯誤
            status = random.choices(['200', '500'], weights=[0.99, 0.01])[0]
        
        # 寫入指標
        REQUEST_COUNT.labels(method='GET', endpoint='/api/transaction', status_code=status).inc()
        
        # 模擬請求間隔 (異常時稍微卡頓，正常時順暢)
        sleep_time = random.uniform(0.1, 0.5) if not is_anomaly else random.uniform(0.01, 0.1)
        time.sleep(sleep_time)

if __name__ == '__main__':
    # 在 8000 port 啟動 Prometheus 伺服器
    start_http_server(8000)
    generate_metrics()