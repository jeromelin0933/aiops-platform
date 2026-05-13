# phase3/llm/gemini_caller.py

import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict, field
from typing import Optional

from google import genai
from google.genai import types

from phase3.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("GeminiCaller")


@dataclass
class RcaReport:
    """LLM 輸出的結構化 RCA 報告"""
    incident_summary:       str   = ""
    root_causes:            list  = field(default_factory=list)
    timeline:               list  = field(default_factory=list)
    remediation_steps:      list  = field(default_factory=list)
    prevention_measures:    list  = field(default_factory=list)
    estimated_mttr_minutes: int   = 0
    severity_assessment:    str   = "unknown"
    confidence_overall:     str   = "low"

    # 元資料（非 LLM 輸出，由呼叫端填入）
    alert_id:               str   = ""
    model_used:             str   = ""
    generated_at:           str   = ""
    prompt_tokens:          int   = 0
    completion_tokens:      int   = 0
    parse_error:            Optional[str] = None   # 若解析失敗記錄原因
    feature_vector:         dict  = field(default_factory=dict)
    def to_dict(self) -> dict:
        return asdict(self)


class GeminiCaller:
    """
    呼叫 Gemini API 並解析結構化 RCA 報告。

    ⚠️ Demo 妥協：使用 Free Tier，有 RPM（requests per minute）限制。
       若連續偵測到多個告警，呼叫間隔至少等待 10 秒。
    🚀 未來升級：
       - 切換至 Vertex AI endpoint，無 RPM 限制，支援企業 SLA
       - 導入 LangSmith 或 Langfuse 追蹤每次 prompt/response，方便 prompt 迭代優化
       - Fine-tune 一個金融領域專用的小型 LLM，降低對外部 API 的依賴
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 未設定，請在 .env 中填入")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self._last_call_time = 0.0
        # 👇 修改：智慧冷卻期設定 (絕對防護版)
        self._last_attempt_time = 0.0  # 改為記錄最後一次「嘗試」的時間
        self.cooldown_seconds = 60.0  # 冷卻時間設為 60 秒

    def _respect_rate_limit(self, min_interval: float = 10.0):
        """Free Tier 保護：確保兩次呼叫間隔至少 min_interval 秒"""
        elapsed = time.time() - self._last_call_time
        if elapsed < min_interval:
            wait = min_interval - elapsed
            logger.info(f"Rate limit: waiting {wait:.1f}s before next API call")
            time.sleep(wait)

    def call(self, system_prompt: str, user_prompt: str,
             alert: dict = None, alert_id: str = "") -> RcaReport:
        """
        呼叫 Gemini API，回傳解析後的 RcaReport。
        若 API 失敗或 JSON 解析失敗，回傳帶有 parse_error 的 RcaReport。
        """
        if alert is None:
            alert = {}
            
        # 👇 修改：【絕對防護版】檢查冷卻期 (只要最近有嘗試過就擋)
        current_time = time.time()
        if self._last_attempt_time != 0.0:
            time_since_last = current_time - self._last_attempt_time
            if time_since_last < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - time_since_last)
                logger.info(f"Cooldown Active: 略過告警 {alert_id} (冷卻期剩餘 {remaining} 秒)")
                from datetime import datetime, timezone
                return RcaReport(
                    alert_id    = alert_id,
                    model_used  = GEMINI_MODEL,
                    generated_at = datetime.now(timezone.utc).isoformat(),
                    incident_summary = f"🔒 系統告警收斂中（同事件餘波，保護算力，{remaining}秒後恢復分析）",
                    feature_vector = alert.get("metrics", {})
                )

        # 👇 關鍵防護！！！在進入 try 打 API 之前，立刻把門「鎖上」！
        self._last_attempt_time = time.time()

        self._respect_rate_limit()

        try:
            logger.info(f"Calling Gemini [{GEMINI_MODEL}] for alert: {alert_id}")

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.1,          # 低溫確保輸出穩定、可重現
                    max_output_tokens=8192,
                    # 告知 Gemini 輸出 JSON 格式（非強制 schema，用 prompt 控制）
                    response_mime_type="application/json",
                ),
            )

            self._last_call_time = time.time()
            

            raw_text = response.text
            logger.info(
                f"Gemini response received — "
                f"length: {len(raw_text)} chars"
            )

            report = self._parse_response(raw_text, alert_id)

            # 填入元資料
            from datetime import datetime, timezone
            report.alert_id   = alert_id
            report.model_used = GEMINI_MODEL
            report.generated_at = datetime.now(timezone.utc).isoformat()
            report.feature_vector = alert.get("metrics", {}) if alert else {}
            # 取得 token 使用量（若 API 有回傳）
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                report.prompt_tokens     = getattr(
                    response.usage_metadata, "prompt_token_count", 0)
                report.completion_tokens = getattr(
                    response.usage_metadata, "candidates_token_count", 0)

            return report

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}", exc_info=True)
            from datetime import datetime, timezone
            return RcaReport(
                alert_id    = alert_id,
                model_used  = GEMINI_MODEL,
                generated_at = datetime.now(timezone.utc).isoformat(),
                incident_summary = "⚠️ LLM 分析失敗，請手動排查",
                parse_error = str(e),
                feature_vector = alert.get("metrics", {}) if alert else {}
            )

    def _parse_response(self, raw_text: str, alert_id: str) -> RcaReport:
        """解析 LLM 輸出的 JSON 字串為 RcaReport"""
        # 嘗試直接解析
        text = raw_text.strip()

        # 移除可能的 markdown code fence（以防 LLM 沒遵守 response_mime_type）
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$",          "", text, flags=re.MULTILINE)
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed for {alert_id}: {e}")
            logger.debug(f"Raw text: {raw_text[:500]}")
            return RcaReport(
                alert_id    = alert_id,
                parse_error = f"JSON decode error: {e}",
                incident_summary = "JSON 解析失敗，原始回應已記錄",
            )

        return RcaReport(
            incident_summary       = data.get("incident_summary", ""),
            root_causes            = data.get("root_causes", []),
            timeline               = data.get("timeline", []),
            remediation_steps      = data.get("remediation_steps", []),
            prevention_measures    = data.get("prevention_measures", []),
            estimated_mttr_minutes = int(data.get("estimated_mttr_minutes", 0)),
            severity_assessment    = data.get("severity_assessment", "unknown"),
            confidence_overall     = data.get("confidence_overall", "low"),
        )