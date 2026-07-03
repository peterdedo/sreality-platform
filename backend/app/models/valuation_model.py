from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.common import PortableJSON


class ValuationModel(SQLModel, table=True):
    """Registry of fitted hedonic-regression models (see docs/METHODOLOGY.md
    §3). Coefficients are stored as plain JSON rather than a pickled object so
    the model stays inspectable and reproducible, not a black box."""

    id: Optional[int] = Field(default=None, primary_key=True)
    version: str = Field(index=True, description="e.g. 2026-07-02T12:00:00 (trained_at as string, unique per fit)")
    segment_key: str = Field(index=True, description="'{category_main_cb}_{category_type_cb}', e.g. '1_1' for Byty-Prodej")
    target: str = Field(default="log_price_czk")

    feature_list: list = Field(sa_column=Column(PortableJSON))
    coefficients: dict = Field(sa_column=Column(PortableJSON), description="feature_name -> coefficient")
    intercept: float

    r2: Optional[float] = None
    n_samples: int = 0
    trained_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    notes: Optional[str] = None
