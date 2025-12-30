from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(50), nullable=False)  # 'facebook' or 'instagram'
    connection_type = Column(String(50), nullable=True)  # 'facebook_page' or 'instagram_business_login'
    platform_user_id = Column(String(255), nullable=False)
    platform_username = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=True)
    page_id = Column(String(255), nullable=True)  # For Facebook pages or Instagram-scoped User ID
    page_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_workspace_exclusive = Column(Boolean, default=False)  # If True, account can only be in ONE workspace globally
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="connected_accounts")
    workspace = relationship("Workspace", back_populates="connected_accounts")

    @property
    def instagram_connection_type(self):
        """
        Detect Instagram connection type based on connection_type field or access token.
        Returns: 'facebook_page' or 'instagram_business_login'
        """
        if self.platform != "instagram":
            return None

        # Use connection_type if set
        if self.connection_type:
            return self.connection_type

        # Fallback: detect from access token
        if self.access_token and self.access_token.startswith("IGAAL"):
            return "instagram_business_login"
        else:
            return "facebook_page"

    @property
    def instagram_api_base_url(self):
        """Get the correct Instagram API base URL based on connection type"""
        if self.platform != "instagram":
            return None

        conn_type = self.instagram_connection_type
        if conn_type == "instagram_business_login":
            return "https://graph.instagram.com"
        else:  # facebook_page
            return "https://graph.facebook.com/v18.0"

    def __repr__(self):
        return f"<ConnectedAccount(platform={self.platform}, username={self.platform_username})>"