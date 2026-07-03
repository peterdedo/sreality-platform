from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ScrapingRunRead(BaseModel):
    id: int
    run_type: str
    category: Optional[str]
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    pages_fetched: int
    items_seen: int
    items_new: int
    items_updated: int
    items_removed: int
    error_count: int
    error_message: Optional[str]

    class Config:
        from_attributes = True


class TriggerRunResponse(BaseModel):
    message: str
    run_id: Optional[int] = None


class ReconcileOrphansResponse(BaseModel):
    reconciled_count: int
    run_ids: list[int]


class RunItemLogRead(BaseModel):
    id: int
    run_id: int
    hash_id: Optional[str]
    stage: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
