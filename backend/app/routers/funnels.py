from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.models import (
    Funnel,
    FunnelStep,
    FunnelEnrollment,
    WorkspaceMember,
)
from app.schemas.funnel import (
    FunnelCreate,
    FunnelUpdate,
    FunnelResponse,
    FunnelStepCreate,
    FunnelStepUpdate,
    FunnelStepResponse,
    FunnelEnrollmentCreate,
    FunnelEnrollmentUpdate,
    FunnelEnrollmentResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/funnels", tags=["Funnels"])


def verify_workspace_access(db: Session, workspace_id: int, user_id: int):
    """Verify user has access to workspace"""
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
    return member


@router.post("", response_model=FunnelResponse)
async def create_funnel(
    funnel: FunnelCreate,
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Create a new funnel in a workspace"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    try:
        # Create funnel
        db_funnel = Funnel(
            workspace_id=workspace_id,
            name=funnel.name,
            description=funnel.description,
            trigger_type=funnel.trigger_type,
            trigger_config=funnel.trigger_config,
            is_active=funnel.is_active,
            priority=funnel.priority,
        )
        db.add(db_funnel)
        db.flush()

        # Create funnel steps
        for step_data in funnel.steps:
            db_step = FunnelStep(
                funnel_id=db_funnel.id,
                name=step_data.name,
                step_order=step_data.step_order,
                step_type=step_data.step_type,
                step_config=step_data.step_config,
                is_active=step_data.is_active,
            )
            db.add(db_step)

        db.commit()
        db.refresh(db_funnel)

        # Get enrollment count
        enrollment_count = db.query(FunnelEnrollment).filter(
            FunnelEnrollment.funnel_id == db_funnel.id
        ).count()

        response = FunnelResponse.model_validate(db_funnel)
        response.enrollment_count = enrollment_count

        return response

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating funnel: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create funnel: {str(e)}")


@router.get("", response_model=List[FunnelResponse])
async def list_funnels(
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List all funnels in a workspace"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    query = db.query(Funnel).filter(Funnel.workspace_id == workspace_id)

    if not include_inactive:
        query = query.filter(Funnel.is_active == True)

    funnels = query.order_by(Funnel.priority.desc(), Funnel.created_at.desc()).all()

    response_list = []
    for funnel in funnels:
        # Get enrollment count
        enrollment_count = db.query(FunnelEnrollment).filter(
            FunnelEnrollment.funnel_id == funnel.id
        ).count()

        resp = FunnelResponse.model_validate(funnel)
        resp.enrollment_count = enrollment_count
        response_list.append(resp)

    return response_list


@router.get("/{funnel_id}", response_model=FunnelResponse)
async def get_funnel(
    funnel_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get a specific funnel"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    # Get enrollment count
    enrollment_count = db.query(FunnelEnrollment).filter(
        FunnelEnrollment.funnel_id == funnel_id
    ).count()

    response = FunnelResponse.model_validate(funnel)
    response.enrollment_count = enrollment_count

    return response


@router.patch("/{funnel_id}", response_model=FunnelResponse)
async def update_funnel(
    funnel_id: int,
    funnel_update: FunnelUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update a funnel"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    # Update fields
    if funnel_update.name is not None:
        funnel.name = funnel_update.name
    if funnel_update.description is not None:
        funnel.description = funnel_update.description
    if funnel_update.trigger_type is not None:
        funnel.trigger_type = funnel_update.trigger_type
    if funnel_update.trigger_config is not None:
        funnel.trigger_config = funnel_update.trigger_config
    if funnel_update.is_active is not None:
        funnel.is_active = funnel_update.is_active
    if funnel_update.priority is not None:
        funnel.priority = funnel_update.priority

    db.commit()
    db.refresh(funnel)

    # Get enrollment count
    enrollment_count = db.query(FunnelEnrollment).filter(
        FunnelEnrollment.funnel_id == funnel_id
    ).count()

    response = FunnelResponse.model_validate(funnel)
    response.enrollment_count = enrollment_count

    return response


@router.delete("/{funnel_id}")
async def delete_funnel(
    funnel_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete a funnel"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    db.delete(funnel)
    db.commit()

    return {"message": "Funnel deleted successfully"}


# Funnel Steps Endpoints

@router.post("/{funnel_id}/steps", response_model=FunnelStepResponse)
async def create_funnel_step(
    funnel_id: int,
    step: FunnelStepCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Add a step to a funnel"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    # Check if step_order already exists
    existing = (
        db.query(FunnelStep)
        .filter(
            FunnelStep.funnel_id == funnel_id,
            FunnelStep.step_order == step.step_order,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Step with order {step.step_order} already exists"
        )

    # Create step
    db_step = FunnelStep(
        funnel_id=funnel_id,
        name=step.name,
        step_order=step.step_order,
        step_type=step.step_type,
        step_config=step.step_config,
        is_active=step.is_active,
    )
    db.add(db_step)
    db.commit()
    db.refresh(db_step)

    return FunnelStepResponse.model_validate(db_step)


@router.get("/{funnel_id}/steps", response_model=List[FunnelStepResponse])
async def list_funnel_steps(
    funnel_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """List all steps in a funnel"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    steps = (
        db.query(FunnelStep)
        .filter(FunnelStep.funnel_id == funnel_id)
        .order_by(FunnelStep.step_order)
        .all()
    )

    return [FunnelStepResponse.model_validate(step) for step in steps]


@router.patch("/{funnel_id}/steps/{step_id}", response_model=FunnelStepResponse)
async def update_funnel_step(
    funnel_id: int,
    step_id: int,
    step_update: FunnelStepUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update a funnel step"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    step = (
        db.query(FunnelStep)
        .filter(
            FunnelStep.id == step_id,
            FunnelStep.funnel_id == funnel_id,
        )
        .first()
    )

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    # Update fields
    if step_update.name is not None:
        step.name = step_update.name
    if step_update.step_order is not None:
        # Check if new order conflicts with existing step
        existing = (
            db.query(FunnelStep)
            .filter(
                FunnelStep.funnel_id == funnel_id,
                FunnelStep.step_order == step_update.step_order,
                FunnelStep.id != step_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Step with order {step_update.step_order} already exists"
            )
        step.step_order = step_update.step_order
    if step_update.step_type is not None:
        step.step_type = step_update.step_type
    if step_update.step_config is not None:
        step.step_config = step_update.step_config
    if step_update.is_active is not None:
        step.is_active = step_update.is_active

    db.commit()
    db.refresh(step)

    return FunnelStepResponse.model_validate(step)


@router.delete("/{funnel_id}/steps/{step_id}")
async def delete_funnel_step(
    funnel_id: int,
    step_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete a funnel step"""
    funnel = db.query(Funnel).filter(Funnel.id == funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    step = (
        db.query(FunnelStep)
        .filter(
            FunnelStep.id == step_id,
            FunnelStep.funnel_id == funnel_id,
        )
        .first()
    )

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    db.delete(step)
    db.commit()

    return {"message": "Step deleted successfully"}


# Funnel Enrollments Endpoints

@router.post("/enrollments", response_model=FunnelEnrollmentResponse)
async def enroll_conversation(
    enrollment: FunnelEnrollmentCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Enroll a conversation in a funnel"""
    funnel = db.query(Funnel).filter(Funnel.id == enrollment.funnel_id).first()
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Verify access
    verify_workspace_access(db, funnel.workspace_id, user_id)

    # Check if already enrolled
    existing = (
        db.query(FunnelEnrollment)
        .filter(
            FunnelEnrollment.funnel_id == enrollment.funnel_id,
            FunnelEnrollment.conversation_id == enrollment.conversation_id,
            FunnelEnrollment.status == "active",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Conversation is already enrolled in this funnel"
        )

    # Create enrollment
    db_enrollment = FunnelEnrollment(
        funnel_id=enrollment.funnel_id,
        conversation_id=enrollment.conversation_id,
        current_step=1,
        status="active",
    )
    db.add(db_enrollment)
    db.commit()
    db.refresh(db_enrollment)

    return FunnelEnrollmentResponse.model_validate(db_enrollment)


@router.get("/enrollments/{conversation_id}", response_model=List[FunnelEnrollmentResponse])
async def get_conversation_enrollments(
    conversation_id: str,
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get all funnel enrollments for a conversation"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    enrollments = (
        db.query(FunnelEnrollment)
        .join(Funnel, FunnelEnrollment.funnel_id == Funnel.id)
        .filter(
            FunnelEnrollment.conversation_id == conversation_id,
            Funnel.workspace_id == workspace_id,
        )
        .all()
    )

    return [FunnelEnrollmentResponse.model_validate(e) for e in enrollments]


@router.patch("/enrollments/{enrollment_id}", response_model=FunnelEnrollmentResponse)
async def update_enrollment(
    enrollment_id: int,
    enrollment_update: FunnelEnrollmentUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update a funnel enrollment"""
    enrollment = db.query(FunnelEnrollment).filter(
        FunnelEnrollment.id == enrollment_id
    ).first()

    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    # Get funnel to verify access
    funnel = db.query(Funnel).filter(Funnel.id == enrollment.funnel_id).first()
    verify_workspace_access(db, funnel.workspace_id, user_id)

    # Update fields
    if enrollment_update.status is not None:
        enrollment.status = enrollment_update.status
        if enrollment_update.status == "completed":
            from datetime import datetime
            enrollment.completed_at = datetime.utcnow()
    if enrollment_update.current_step is not None:
        enrollment.current_step = enrollment_update.current_step

    db.commit()
    db.refresh(enrollment)

    return FunnelEnrollmentResponse.model_validate(enrollment)


@router.delete("/enrollments/{enrollment_id}")
async def delete_enrollment(
    enrollment_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete/exit a funnel enrollment"""
    enrollment = db.query(FunnelEnrollment).filter(
        FunnelEnrollment.id == enrollment_id
    ).first()

    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    # Get funnel to verify access
    funnel = db.query(Funnel).filter(Funnel.id == enrollment.funnel_id).first()
    verify_workspace_access(db, funnel.workspace_id, user_id)

    db.delete(enrollment)
    db.commit()

    return {"message": "Enrollment deleted successfully"}

