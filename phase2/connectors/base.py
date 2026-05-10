# phase2/connectors/base.py

from abc import ABC, abstractmethod
from datetime import datetime
from phase2.features.schema import RawWindow

class BaseConnector(ABC):
    """
    所有資料連接器的抽象基底。
    未來替換 Kafka / Flink 時，只需實作此介面即可。
    """

    @abstractmethod
    def fetch_metrics(self, start: datetime, end: datetime) -> dict:
        ...

    @abstractmethod
    def fetch_logs(self, start: datetime, end: datetime) -> dict:
        ...

    def fetch(self, start: datetime, end: datetime) -> RawWindow:
        """組裝 RawWindow（不需要子類別覆寫）"""
        metrics_data = self.fetch_metrics(start, end)
        logs_data    = self.fetch_logs(start, end)

        return RawWindow(
            window_start=start,
            window_end=end,
            **metrics_data,
            **logs_data,
        )