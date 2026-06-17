from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class JobOut(BaseModel):
    id: int
    filename: str
    status: str
    row_count_raw: int
    row_count_clean: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class JobStatusOut(BaseModel):
    id: int
    status: str
    summary: Optional[dict] = None


class TransactionOut(BaseModel):
    txn_id: Optional[str] = None
    date: Optional[str] = None
    merchant: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[str] = None
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None

    model_config = {"from_attributes": True}


class CategorySpend(BaseModel):
    category: str
    count: int
    total: float


class NarrativeSummary(BaseModel):
    total_spend_inr: float
    total_spend_usd: float
    top_merchants: list
    anomaly_count: int
    narrative: str
    risk_level: str


class JobResultsOut(BaseModel):
    transactions: list[TransactionOut]
    anomalies: list[TransactionOut]
    category_spend: list[CategorySpend]
    narrative_summary: Optional[NarrativeSummary] = None


class JobListOut(BaseModel):
    id: int
    filename: str
    status: str
    row_count_raw: int
    created_at: datetime

    model_config = {"from_attributes": True}
