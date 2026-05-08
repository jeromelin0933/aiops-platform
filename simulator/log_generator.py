import time
import random
import json
import logging
import os
from datetime import datetime, timezone

# 確保 logs 資料夾存在
os.makedirs('logs', exist_ok=True)

# 設定 logging，輸出到 logs/app.log
logger = logging.getLogger('simulator')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('logs/app.log')
file_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(file_handler)

def generate_logs():
    print("啟動 Logs 模擬器... 寫入至 logs/app.log")
    start_time = time.time()
    
    endpoints = ['/api/login', '/api/transaction', '/api/balance']
    
    while True:
        # 計算目前程式已經執行了幾分鐘
        elapsed_minutes = (time.time() - start_time) / 60
        
        # 異常區間：第 1 到 4 分鐘
        is_anomaly = 1 <= elapsed_minutes <= 4
        
        timestamp = datetime.now(timezone.utc).isoformat()
        trace_id = f"trace-{random.randint(1000, 9999)}"
        endpoint = random.choice(endpoints)
        
        # 核心改動：狀態機率分配
        if is_anomaly:
            # 系統崩潰期：80% 都是 ERROR (大爆發)
            level = random.choices(['INFO', 'ERROR'], weights=[0.2, 0.8])[0]
        else:
            # 日常穩定狀態：95% INFO, 3% WARN, 2% ERROR (背景雜訊)
            level = random.choices(['INFO', 'WARN', 'ERROR'], weights=[0.95, 0.03, 0.02])[0]
            
        # 根據 Level 給予對應的狀態碼與假訊息
        if level == 'ERROR':
            status = 500
            msg = "database query timeout" if is_anomaly else "connection reset by peer (random noise)"
        elif level == 'WARN':
            status = 429
            msg = "rate limit exceeded"
        else:
            status = 200
            msg = "request processed successfully"

        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "trace_id": trace_id,
            "endpoint": endpoint,
            "status": status,
            "message": msg
        }
        
        # 寫入 JSON 日誌
        logger.info(json.dumps(log_entry))
        
        # 模擬請求間隔 (異常時日誌狂刷，正常時順暢)
        sleep_time = random.uniform(0.01, 0.05) if is_anomaly else random.uniform(0.1, 0.3)
        time.sleep(sleep_time)

if __name__ == '__main__':
    generate_logs()