from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import logging

from app.database import get_db
from app.models import (
    Workspace,
    WorkspaceMember,
    ConnectedAccount,
    ConversationTag,
    User,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceMemberResponse,
    ConversationTagCreate,
    ConversationTagResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    workspace: WorkspaceCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Create a new workspace"""
    try:
        # Create workspace
        db_workspace = Workspace(
            owner_id=user_id,
            name=workspace.name,
            description=workspace.description,
        )
        db.add(db_workspace)
        db.flush()

        # Add owner as workspace member
        db_member = WorkspaceMember(
            workspace_id=db_workspace.id,
            user_id=user_id,
            role="owner",
        )
        db.add(db_member)

        db.commit()
        db.refresh(db_workspace)

        # Get counts
        member_count = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == db_workspace.id
        ).count()
        account_count = db.query(ConnectedAccount).filter(
            ConnectedAccount.workspace_id == db_workspace.id
        ).count()

        response = WorkspaceResponse.model_validate(db_workspace)
        response.member_count = member_count
        response.account_count = account_count

        return response

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating workspace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create workspace: {str(e)}")


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get all workspaces for a user (owned + member of)"""
    try:
        # Get workspaces where user is owner or member
        workspaces = (
            db.query(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .filter(WorkspaceMember.user_id == user_id)
            .filter(Workspace.is_active == True)
            .all()
        )

        response_list = []
        for workspace in workspaces:
            # Get counts
            member_count = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == workspace.id
            ).count()
            account_count = db.query(ConnectedAccount).filter(
                ConnectedAccount.workspace_id == workspace.id
            ).count()

            resp = WorkspaceResponse.model_validate(workspace)
            resp.member_count = member_count
            resp.account_count = account_count
            response_list.append(resp)

        return response_list

    except Exception as e:
        logger.error(f"Error listing workspaces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list workspaces: {str(e)}")


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get a specific workspace"""
    # Verify user has access to workspace
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Get counts
    member_count = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id
    ).count()
    account_count = db.query(ConnectedAccount).filter(
        ConnectedAccount.workspace_id == workspace_id
    ).count()

    response = WorkspaceResponse.model_validate(workspace)
    response.member_count = member_count
    response.account_count = account_count

    return response


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: int,
    workspace_update: WorkspaceUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update a workspace (owner/admin only)"""
    # Verify user is owner or admin
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role.in_(["owner", "admin"]),
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Update fields
    if workspace_update.name is not None:
        workspace.name = workspace_update.name
    if workspace_update.description is not None:
        workspace.description = workspace_update.description
    if workspace_update.is_active is not None:
        workspace.is_active = workspace_update.is_active

    db.commit()
    db.refresh(workspace)

    # Get counts
    member_count = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id
    ).count()
    account_count = db.query(ConnectedAccount).filter(
        ConnectedAccount.workspace_id == workspace_id
    ).count()

    response = WorkspaceResponse.model_validate(workspace)
    response.member_count = member_count
    response.account_count = account_count

    return response


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete a workspace (owner only)"""
    # Verify user is owner
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role == "owner",
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Only workspace owner can delete")

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    db.delete(workspace)
    db.commit()

    return {"message": "Workspace deleted successfully"}


# Workspace Members Endpoints

@router.get("/{workspace_id}/members", response_model=List[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """List all members of a workspace"""
    # Verify user has access to workspace
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    members = (
        db.query(WorkspaceMember, User.username)
        .join(User, WorkspaceMember.user_id == User.id)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )

    response_list = []
    for member, username in members:
        resp = WorkspaceMemberResponse.model_validate(member)
        resp.username = username
        response_list.append(resp)

    return response_list


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse)
async def add_workspace_member(
    workspace_id: int,
    member_data: WorkspaceMemberCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Add a member to workspace (owner/admin only)"""
    # Verify user is owner or admin
    requester = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role.in_(["owner", "admin"]),
        )
        .first()
    )

    if not requester:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Check if member already exists
    existing = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_data.user_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")

    # Verify target user exists
    target_user = db.query(User).filter(User.id == member_data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Create member
    db_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=member_data.user_id,
        role=member_data.role,
        permissions=member_data.permissions,
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)

    response = WorkspaceMemberResponse.model_validate(db_member)
    response.username = target_user.username

    return response


@router.patch("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_workspace_member(
    workspace_id: int,
    member_id: int,
    member_update: WorkspaceMemberUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update a workspace member (owner/admin only)"""
    # Verify user is owner or admin
    requester = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role.in_(["owner", "admin"]),
        )
        .first()
    )

    if not requester:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get member to update
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Update fields
    if member_update.role is not None:
        member.role = member_update.role
    if member_update.permissions is not None:
        member.permissions = member_update.permissions

    db.commit()
    db.refresh(member)

    # Get username
    target_user = db.query(User).filter(User.id == member.user_id).first()
    response = WorkspaceMemberResponse.model_validate(member)
    response.username = target_user.username if target_user else None

    return response


@router.delete("/{workspace_id}/members/{member_id}")
async def remove_workspace_member(
    workspace_id: int,
    member_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Remove a member from workspace (owner/admin only)"""
    # Verify user is owner or admin
    requester = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role.in_(["owner", "admin"]),
        )
        .first()
    )

    if not requester:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get member to remove
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent removing the owner
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

    db.delete(member)
    db.commit()

    return {"message": "Member removed successfully"}


# Conversation Tags Endpoints

@router.post("/{workspace_id}/tags", response_model=ConversationTagResponse)
async def add_conversation_tag(
    workspace_id: int,
    tag_data: ConversationTagCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Add a tag to a conversation"""
    # Verify user has access to workspace
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    # Check if tag already exists
    existing = (
        db.query(ConversationTag)
        .filter(
            ConversationTag.workspace_id == workspace_id,
            ConversationTag.conversation_id == tag_data.conversation_id,
            ConversationTag.tag == tag_data.tag,
        )
        .first()
    )

    if existing:
        return ConversationTagResponse.model_validate(existing)

    # Create tag
    db_tag = ConversationTag(
        workspace_id=workspace_id,
        conversation_id=tag_data.conversation_id,
        tag=tag_data.tag,
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)

    return ConversationTagResponse.model_validate(db_tag)


@router.get("/{workspace_id}/tags/{conversation_id}", response_model=List[ConversationTagResponse])
async def get_conversation_tags(
    workspace_id: int,
    conversation_id: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get all tags for a conversation"""
    # Verify user has access to workspace
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    tags = (
        db.query(ConversationTag)
        .filter(
            ConversationTag.workspace_id == workspace_id,
            ConversationTag.conversation_id == conversation_id,
        )
        .all()
    )

    return [ConversationTagResponse.model_validate(tag) for tag in tags]


@router.delete("/{workspace_id}/tags/{tag_id}")
async def remove_conversation_tag(
    workspace_id: int,
    tag_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Remove a tag from a conversation"""
    # Verify user has access to workspace
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    tag = (
        db.query(ConversationTag)
        .filter(
            ConversationTag.id == tag_id,
            ConversationTag.workspace_id == workspace_id,
        )
        .first()
    )

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.delete(tag)
    db.commit()

    return {"message": "Tag removed successfully"}
