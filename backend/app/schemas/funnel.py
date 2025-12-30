from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# Funnel Step Schemas
class FunnelStepBase(BaseModel):
    name: str
    step_order: int
    step_type: str  # send_message, delay, condition, tag, assign_human, ai_response
    step_config: Dict[str, Any] = {}
    is_active: bool = True


class FunnelStepCreate(FunnelStepBase):
    pass


class FunnelStepUpdate(BaseModel):
    name: Optional[str] = None
    step_order: Optional[int] = None
    step_type: Optional[str] = None
    step_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class FunnelStepResponse(FunnelStepBase):
    id: int
    funnel_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Funnel Schemas
class FunnelBase(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str  # keyword, new_conversation, tag, custom
    trigger_config: Dict[str, Any] = {}
    is_active: bool = True
    priority: int = 0


class FunnelCreate(FunnelBase):
    steps: List[FunnelStepCreate] = []


class FunnelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class FunnelResponse(FunnelBase):
    id: int
    workspace_id: int
    created_at: datetime
    updated_at: datetime
    steps: List[FunnelStepResponse] = []
    enrollment_count: Optional[int] = 0

    class Config:
        from_attributes = True


# Funnel Enrollment Schemas
class FunnelEnrollmentCreate(BaseModel):
    funnel_id: int
    conversation_id: str


class FunnelEnrollmentUpdate(BaseModel):
    status: Optional[str] = None  # active, completed, paused, exited
    current_step: Optional[int] = None


class FunnelEnrollmentResponse(BaseModel):
    id: int
    funnel_id: int
    conversation_id: str
    current_step: int
    status: str
    enrolled_at: datetime
    completed_at: Optional[datetime] = None
    next_step_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True
