from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# Workspace Schemas
class WorkspaceBase(BaseModel):
    name: str
    description: Optional[str] = None


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WorkspaceResponse(WorkspaceBase):
    id: int
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = 0
    account_count: Optional[int] = 0

    class Config:
        from_attributes = True


# Workspace Member Schemas
class WorkspaceMemberBase(BaseModel):
    user_id: int
    role: str = "member"  # owner, admin, member
    permissions: Dict[str, Any] = {}


class WorkspaceMemberCreate(WorkspaceMemberBase):
    pass


class WorkspaceMemberUpdate(BaseModel):
    role: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None


class WorkspaceMemberResponse(WorkspaceMemberBase):
    id: int
    workspace_id: int
    created_at: datetime
    username: Optional[str] = None  # Populated from user relationship

    class Config:
        from_attributes = True


# Conversation Tag Schemas
class ConversationTagCreate(BaseModel):
    conversation_id: str
    tag: str


class ConversationTagResponse(BaseModel):
    id: int
    workspace_id: int
    conversation_id: str
    tag: str
    created_at: datetime

    class Config:
        from_attributes = True
