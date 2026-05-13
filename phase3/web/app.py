# phase3/web/app.py

import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from phase3.engine import Phase3Engine
from phase3.store.report_store import ReportStore
from phase3.config import ALERT_STORE_PATH

logger = logging.getLogger("WebApp")



# ── 初始化 ─────────────────────────────────────────────────────────────────────
store     = ReportStore()
# Phase 3 引擎
engine    = Phase3Engine()

# 最新版的 FastAPI 生命週期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.start()  # 啟動背景大腦
    logger.info("Phase 3 Engine started with web server")
    yield

# 將 lifespan 綁定，宣告 app
app       = FastAPI(title="AIOps Incident Dashboard", docs_url=None, redoc_url=None, lifespan=lifespan)
templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates")
)
# ── 頁面路由 ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    reports = store.read_all_reports()
    alerts  = store.read_all_alerts()

    # 統計數據
    critical_count = sum(
        1 for r in reports
        if r.get("rca", {}).get("severity_assessment") == "critical"
    )
    analyzed_count = len(reports)
    pending_count  = sum(
        1 for a in alerts if a.get("rca_result") is None
    )

    return templates.TemplateResponse("index.html", {
        "request":        request,
        "reports":        reports[:20],   # 最新 20 筆
        "critical_count": critical_count,
        "analyzed_count": analyzed_count,
        "pending_count":  pending_count,
    })


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def report_detail(request: Request, report_id: str):
    report = store.read_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return templates.TemplateResponse("report.html", {
        "request": request,
        "report":  report,
        "rca":     report.get("rca", {}),
    })


# ── JSON API（供前端 polling） ──────────────────────────────────────────────────

@app.get("/api/reports")
async def api_reports():
    return store.read_all_reports()[:20]

@app.get("/api/alerts")
async def api_alerts():
    return store.read_all_alerts()[:20]

@app.post("/api/analyze/{alert_id}")
async def manual_analyze(alert_id: str, background_tasks: BackgroundTasks):
    """手動觸發重新分析（Demo 用）"""
    alerts = store.read_all_alerts()
    alert  = next((a for a in alerts if a.get("alert_id") == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    # 清除舊的 rca_result，讓 watcher 重新觸發
    alert["rca_result"] = None
    background_tasks.add_task(engine.process_alert, alert)
    return {"status": "processing", "alert_id": alert_id}

if __name__ == "__main__":
    import uvicorn
    # 這裡的 port 8080 必須對應你之前瀏覽器輸入的網址
    print("=" * 60)
    print("🚀 AIOps 儀表板正在啟動...")
    print("👉 請訪問: http://localhost:8080")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8080)