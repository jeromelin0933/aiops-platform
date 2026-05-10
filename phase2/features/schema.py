# phase2/features/schema.py

from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class RawWindow:
    """
    從資料來源（Prometheus / Loki）拉回的原始資料視窗。
    """
    window_start:    datetime
    window_end:      datetime

    # Prometheus 原始值
    p95_latency_seconds:    float = 0.0   
    p50_latency_seconds:    float = 0.0
    error_count_5xx:        float = 0.0   
    total_request_count:    float = 0.0
    db_pool_active:         float = 0.0
    db_pool_max:            float = 100.0

    # Loki 原始值
    log_total_count:        int   = 0
    log_error_count:        int   = 0
    log_warn_count:         int   = 0


@dataclass
class FeatureVector:
    """
    標準化特徵向量（8 維）。
    AnomalyDetector 只接受此結構，完全不感知原始資料來源。
    """
    timestamp:              str   = ""

    # ── Metrics 特徵（4 維）──
    p95_latency_ms:         float = 0.0   # p95 延遲（毫秒）
    error_rate_pct:         float = 0.0   # 5xx 錯誤率（%）
    db_pool_usage_pct:      float = 0.0   # DB 連線池使用率（%）
    throughput_rps:         float = 0.0   # 每秒請求數

    # ── Log 特徵（2 維）──
    log_error_rate_pct:     float = 0.0   # ERROR log 佔比（%）
    log_warn_rate_pct:      float = 0.0   # WARN log 佔比（%）

    # ── 融合特徵（2 維）── 這是區分「崩潰」與「雜訊」的關鍵
    log_error_spike_ratio:  float = 0.0
    latency_error_corr:     float = 0.0

    def to_numpy(self) -> list:
        """返回供 sklearn 使用的特徵列表（排除 timestamp）"""
        return [
            self.p95_latency_ms,
            self.error_rate_pct,
            self.db_pool_usage_pct,
            self.throughput_rps,
            self.log_error_rate_pct,
            self.log_warn_rate_pct,
            self.log_error_spike_ratio,
            self.latency_error_corr,
        ]

    @property
    def feature_names(self) -> list:
        return [
            "p95_latency_ms", "error_rate_pct", "db_pool_usage_pct",
            "throughput_rps", "log_error_rate_pct", "log_warn_rate_pct",
            "log_error_spike_ratio", "latency_error_corr",
        ]

    def to_dict(self) -> dict:
        return asdict(self)