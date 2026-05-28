import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SyncLog(Base):
    """Запись о сессии синхронизации."""
    __tablename__ = "sync_logs"

    id               = Column(Integer, primary_key=True, index=True)
    session_id       = Column(String(36), unique=True, nullable=False, index=True)
    component        = Column(String(64), nullable=False, default="alstyle",
                              comment="alstyle | wb | manual")
    mode             = Column(String(32), nullable=False, default="all",
                              comment="all | categories | products | images")
    status           = Column(String(16), nullable=False, default="running",
                              comment="running | done | error")
    started_at       = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at      = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    stats            = Column(JSON, nullable=True,
                              comment="SyncStatsOut как JSON")
    error_message    = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SyncLog session={self.session_id!r} "
            f"status={self.status!r} mode={self.mode!r}>"
        )
