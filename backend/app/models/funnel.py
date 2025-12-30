from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Funnel(Base):
    __tablename__ = "funnels"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(50), nullable=False)  # keyword, new_conversation, tag, custom
    trigger_config = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority funnels run first
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace = relationship("Workspace", back_populates="funnels")
    steps = relationship("FunnelStep", back_populates="funnel", cascade="all, delete-orphan", order_by="FunnelStep.step_order")
    enrollments = relationship("FunnelEnrollment", back_populates="funnel", cascade="all, delete-orphan")


class FunnelStep(Base):
    __tablename__ = "funnel_steps"

    id = Column(Integer, primary_key=True, index=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_type = Column(String(50), nullable=False)  # send_message, delay, condition, tag, assign_human, ai_response
    step_config = Column(JSON, nullable=False, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    funnel = relationship("Funnel", back_populates="steps")


class FunnelEnrollment(Base):
    __tablename__ = "funnel_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(String(255), nullable=False)
    current_step = Column(Integer, default=1)
    status = Column(String(50), default="active")  # active, completed, paused, exited
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    next_step_at = Column(DateTime, nullable=True)  # When to execute next step
    enrollment_data = Column(JSON, default={})  # Renamed from 'metadata' (SQLAlchemy reserved word)

    # Relationships
    funnel = relationship("Funnel", back_populates="enrollments")
