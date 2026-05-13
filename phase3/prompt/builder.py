# phase3/prompt/builder.py

import logging
from phase3.config import LOG_MAX_LINES

logger = logging.getLogger("PromptBuilder")

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """你是一位在台灣金融機構服務超過 10 年的資深 SRE（Site Reliability Engineer）。
你熟悉 Java Spring Boot 微服務、PostgreSQL、Redis、Kubernetes，以及金管會對核心系統 RTO/RPO 的要求。

你腦中有一份完整的「金融 API 系統排障 SOP 知識庫」，涵蓋以下常見根因場景：

【SOP-01：DB 連線池耗盡（Connection Pool Exhausted）】
症狀：p95 latency 急劇上升、error_message 出現 "connection pool exhausted"、db_pool_usage_pct 接近 100%
根因：① 慢查詢佔用連線未釋放 ② 連線洩漏（connection leak）③ 突發流量超過連線池上限
排障步驟：SHOW PROCESSLIST 查活躍查詢 → 找慢查詢並 KILL → 調高 pool size → 部署熱修復

【SOP-02：上游服務逾時（Upstream Timeout）】
症狀：出現 "upstream timeout" 或 504 錯誤、特定 endpoint 的 trace 顯示在某個 span 長時間等待
根因：① 依賴的下游微服務回應慢 ② 網路抖動 ③ DNS 解析異常
排障步驟：確認下游服務健康狀態 → 檢查 service mesh 的 circuit breaker 是否開啟 → 查 DNS 快取

【SOP-03：記憶體壓力導致 GC 停頓（JVM GC Pressure）】
症狀：latency 呈鋸齒狀週期性飆升、JVM heap 使用率接近上限、GC log 顯示 Full GC 頻繁
根因：① 記憶體洩漏 ② 大量物件短時間建立 ③ Heap 設定不當
排障步驟：jstack 確認 GC 停頓 → 分析 heap dump → 調整 -Xmx 與 GC 策略

【SOP-04：系統崩潰期（Cascading Failure）】
症狀：多項指標同時異常（latency 飆升 + error_rate 驟增 + log_error_rate 洗頻）
根因：通常為上述多個根因的連鎖反應，或是部署/設定變更引發
排障步驟：① 確認最近 30 分鐘是否有部署或設定變更 ② 先 rollback 再排查 ③ 啟動 Incident Response 流程

你的任務：閱讀系統異常快照與 Log 紀錄，進行根因分析，並輸出「結構化 JSON 格式」的 RCA 報告。
輸出必須嚴格符合後續指定的 JSON schema，不得輸出任何 JSON 以外的文字、markdown 或解釋。
"""

# ── User Prompt 模板 ──────────────────────────────────────────────────────────
USER_PROMPT_TEMPLATE = """請分析以下金融 API 系統異常事件，並輸出根因分析報告。

## 異常事件快照（來自自動化偵測系統）

- **告警 ID**：{alert_id}
- **觸發時間**：{triggered_at}
- **嚴重度**：{severity}
- **信心度**：{confidence}
- **異常分數**：{anomaly_score}

### Metrics 異常數值
| 指標 | 異常值 | 正常基準 |
|---|---|---|
| p95 延遲 | **{p95_latency_ms} ms** | ~200 ms |
| 5xx 錯誤率 | **{error_rate_pct}%** | ~1% |
| DB 連線池使用率 | **{db_pool_usage_pct}%** | ~30% |
| 每秒請求數 | {throughput_rps} req/s | 參考值 |
| Log ERROR 比率 | **{log_error_rate_pct}%** | ~2% |
| 延遲×錯誤複合分數 | {latency_error_corr} | 正常期接近 0 |

### ML 模型標記的最異常特徵
{triggered_features_text}

---

## Log 上下文（RAG 檢索：告警前 {log_window_minutes} 分鐘）

**時間範圍**：{log_window_start} → {log_window_end}
**撈取筆數**：ERROR {error_log_count} 筆 + WARN {warn_log_count} 筆

### ERROR Logs
```text
{error_logs_text}

{warn_logs_text}
---

請根據以上資訊，嚴格輸出符合以下 JSON schema 的根因分析報告，不得輸出任何 JSON 以外的文字：

```json
{{
  "incident_summary": "一句話描述事件核心現象",
  "root_causes": [
    {{
      "rank": 1,
      "confidence": "high | medium | low",
      "hypothesis": "根本原因假設",
      "evidence": "引用具體 log 訊息或 metrics 數值作為佐證",
      "sop_reference": "對應的 SOP 編號，如 SOP-01，若無對應則填 null"
    }}
  ],
  "timeline": [
    {{
      "time": "HH:MM:SS 格式，從 log 推斷",
      "event": "發生了什麼"
    }}
  ],
  "remediation_steps": [
    {{
      "order": 1,
      "priority": "immediate | short_term | long_term",
      "action": "具體可執行的指令或操作步驟",
      "expected_effect": "執行後預期改善效果"
    }}
  ],
  "prevention_measures": [
    "預防措施一",
    "預防措施二"
  ],
  "estimated_mttr_minutes": 數字（估算若有此分析輔助可縮短幾分鐘的 MTTR）,
  "severity_assessment": "critical | high | medium | low",
  "confidence_overall": "high | medium | low"
}}
```
"""


class PromptBuilder:
    """
    從 Alert JSON + Log Context 組裝完整的 Gemini Prompt。

    設計原則：
    - System Prompt 嵌入 SOP 隱含知識，減少 LLM 幻覺
    - User Prompt 使用 Markdown 表格讓 LLM 更易解析數值
    - 強制 JSON 輸出 schema，方便後端解析與前端渲染
    - Log 長度有上限控制，避免超出 context window
    """

    def build(self, alert: dict, log_context: dict) -> tuple[str, str]:
        """
        Returns:
            (system_prompt, user_prompt) — 兩個字串，分別傳給 Gemini API
        """
        metrics   = alert.get("metrics", {})
        log_stats = alert.get("log_stats", {})
        fusion    = alert.get("fusion_features", {})

        # 格式化觸發特徵
        triggered = alert.get("triggered_features", [])
        triggered_text = "\n".join(
            f"- `{tf['feature']}`: z-score={tf['z_score']} ({tf['direction']})"
            for tf in triggered
        ) or "（無）"

        # 格式化 Log（截斷至上限）
        error_logs = log_context.get("error_logs", [])
        warn_logs  = log_context.get("warn_logs",  [])

        error_logs_text = "\n".join(error_logs[:30]) or "（此時間窗口無 ERROR log）"
        warn_logs_text  = "\n".join(warn_logs[:20])  or "（此時間窗口無 WARN log）"

        user_prompt = USER_PROMPT_TEMPLATE.format(
            alert_id               = alert.get("alert_id", "N/A"),
            triggered_at           = alert.get("triggered_at", ""),
            severity               = alert.get("severity", ""),
            confidence             = alert.get("confidence", ""),
            anomaly_score          = alert.get("anomaly_score", ""),
            p95_latency_ms         = metrics.get("p95_latency_ms", "N/A"),
            error_rate_pct         = metrics.get("error_rate_pct", "N/A"),
            db_pool_usage_pct      = metrics.get("db_pool_usage_pct", "N/A"),
            throughput_rps         = metrics.get("throughput_rps", "N/A"),
            log_error_rate_pct     = log_stats.get("log_error_rate_pct", "N/A"),
            latency_error_corr     = fusion.get("latency_error_corr", "N/A"),
            triggered_features_text = triggered_text,
            log_window_minutes     = log_context.get("window_minutes", 3),
            log_window_start       = log_context.get("window_start", ""),
            log_window_end         = log_context.get("window_end", ""),
            error_log_count        = len(error_logs),
            warn_log_count         = len(warn_logs),
            error_logs_text        = error_logs_text,
            warn_logs_text         = warn_logs_text,
        )

        logger.debug(f"Prompt built — user_prompt length: {len(user_prompt)} chars")
        return SYSTEM_PROMPT, user_prompt