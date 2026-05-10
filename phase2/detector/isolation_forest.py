# phase2/detector/isolation_forest.py

import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from phase2.features.schema import FeatureVector
from phase2.config import MODEL_PATH, IF_N_ESTIMATORS, IF_CONTAMINATION, IF_RANDOM_STATE, ANOMALY_SCORE_THRESHOLD

logger = logging.getLogger("AnomalyDetector")

@dataclass
class AnomalyResult:
    timestamp:          str
    is_anomaly:         bool
    anomaly_score:      float
    confidence:         str
    triggered_features: list
    feature_vector:     dict
    model_version:      str = "isolation_forest_v1"

class AnomalyDetector:
    def __init__(self):
        self.model:   Optional[IsolationForest] = None
        self.scaler:  Optional[StandardScaler]  = None
        self.columns: list = []
        self._loaded = False

    def train(self, feature_vectors: list[FeatureVector], save_path: str = MODEL_PATH) -> None:
        if len(feature_vectors) < 30:
            raise ValueError(f"訓練資料不足（{len(feature_vectors)} 筆），至少需要 30 筆。")

        X_raw = np.array([fv.to_numpy() for fv in feature_vectors])
        self.columns = feature_vectors[0].feature_names

        self.scaler = StandardScaler()
        X = self.scaler.fit_transform(X_raw)

        self.model = IsolationForest(
            n_estimators=IF_N_ESTIMATORS, contamination=IF_CONTAMINATION,
            max_samples="auto", random_state=IF_RANDOM_STATE, n_jobs=-1
        )
        self.model.fit(X)
        self._loaded = True

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        joblib.dump({"model": self.model, "scaler": self.scaler, "columns": self.columns}, save_path)
        logger.info(f"Model saved to {save_path}")

    def load_model(self, path: str = MODEL_PATH) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"找不到模型：{path}，請先執行訓練腳本")
        artifact     = joblib.load(path)
        self.model   = artifact["model"]
        self.scaler  = artifact["scaler"]
        self.columns = artifact["columns"]
        self._loaded = True

    def predict(self, fv: FeatureVector) -> AnomalyResult:
        if not self._loaded:
            raise RuntimeError("模型尚未載入")

        X_raw    = np.array([fv.to_numpy()])
        X_scaled = self.scaler.transform(X_raw)

        score = float(self.model.decision_function(X_scaled)[0])
        pred  = int(self.model.predict(X_scaled)[0])

        is_anomaly = pred == -1 and score < ANOMALY_SCORE_THRESHOLD
        
        confidence = "high" if score < -0.3 else "medium" if score < -0.1 else "low"
        triggered = self._find_triggered_features(X_scaled[0])

        return AnomalyResult(
            timestamp=fv.timestamp, is_anomaly=is_anomaly, anomaly_score=round(score, 6),
            confidence=confidence, triggered_features=triggered, feature_vector=fv.to_dict()
        )

    def _find_triggered_features(self, x_scaled: np.ndarray, top_n: int = 3) -> list:
        abs_vals = np.abs(x_scaled)
        top_indices = abs_vals.argsort()[::-1][:top_n]
        return [{"feature": self.columns[i], "z_score": round(float(x_scaled[i]), 3), 
                 "direction": "above_normal" if x_scaled[i] > 0 else "below_normal"} for i in top_indices]