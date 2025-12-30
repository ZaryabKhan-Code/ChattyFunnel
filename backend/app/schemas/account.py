from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ConnectedAccountBase(BaseModel):
    platform: str
    platform_username: Optional[str] = None


class ConnectedAccountResponse(ConnectedAccountBase):
    id: int
    platform_user_id: str
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None
