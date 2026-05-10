# phase2/features/extractor.py

import logging
from phase2.features.schema import RawWindow, FeatureVector

logger = logging.getLogger("FeatureExtractor")

class FeatureExtractor:
    """從 RawWindow 計算標準化的 8 維 FeatureVector"""

    def extract(self, raw: RawWindow) -> FeatureVector:
        window_seconds = max((raw.window_end - raw.window_start).total_seconds(), 1.0)

        # ── Metrics 特徵 ──
        p95_ms = raw.p95_latency_seconds * 1000.0
        total_req = max(raw.total_request_count, 1.0)
        error_rate_pct = (raw.error_count_5xx / total_req) * 100.0
        db_pool_pct = (raw.db_pool_active / max(raw.db_pool_max, 1.0)) * 100.0
        throughput_rps = raw.total_request_count / window_seconds

        # ── Log 特徵 ──
        total_logs = max(raw.log_total_count, 1)
        log_error_rate_pct = (raw.log_error_count / total_logs) * 100.0
        log_warn_rate_pct  = (raw.log_warn_count  / total_logs) * 100.0

        # ── 融合特徵 (區分災難與雜訊的關鍵) ──
        # 崩潰時：錯誤率飆升，比值穩定。雜訊時：Metrics 沒事但 Log 偶發 ERROR，比值異常高。
        log_error_spike_ratio = log_error_rate_pct / max(error_rate_pct, 0.1)
        
        # 延遲與錯誤同時惡化，乘積會爆發性成長
        latency_error_corr = p95_ms * error_rate_pct

        fv = FeatureVector(
            timestamp             = raw.window_end.isoformat(),
            p95_latency_ms        = round(p95_ms,                 2),
            error_rate_pct        = round(error_rate_pct,         4),
            db_pool_usage_pct     = round(db_pool_pct,            2),
            throughput_rps        = round(throughput_rps,         2),
            log_error_rate_pct    = round(log_error_rate_pct,     4),
            log_warn_rate_pct     = round(log_warn_rate_pct,      4),
            log_error_spike_ratio = round(log_error_spike_ratio,  4),
            latency_error_corr    = round(latency_error_corr,     2),
        )

        return fv