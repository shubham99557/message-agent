from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class BackgroundTaskBase(BaseModel):
    category: str
    campaign_id: Optional[int] = None
    company_id: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class BackgroundTaskTriggerRequest(BaseModel):
    category: str
    payload: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    campaign_id: Optional[int] = None
    company_id: Optional[int] = None
    execute_sync: bool = False


class BackgroundTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    category: str
    idempotency_key: Optional[str] = None
    status: str
    payload_json: Optional[str] = None
    result_json: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    max_retries: int
    campaign_id: Optional[int] = None
    company_id: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DeadLetterTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    category: str
    idempotency_key: Optional[str] = None
    payload_json: Optional[str] = None
    final_error: str
    retries_exhausted: int
    failed_at: datetime
    requeued: bool


class QueueHealthResponse(BaseModel):
    status: str
    timestamp: str
    timezone: str
    redis: Dict[str, Any]
    celery: Dict[str, Any]
    tasks: Dict[str, Any]
