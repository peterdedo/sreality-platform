from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AnalyticsRunRead(BaseModel):
    id: int
    run_type: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    items_processed: int
    error_count: int
    error_message: Optional[str]

    class Config:
        from_attributes = True


class TriggerRecomputeResponse(BaseModel):
    message: str
