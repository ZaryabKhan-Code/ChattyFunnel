from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import User, ConnectedAccount

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("/db-status")
async def check_database_status(db: Session = Depends(get_db)):
    """Check if database is initialized and working"""
    try:
        # Test database connection
        user_count = db.query(User).count()
        account_count = db.query(ConnectedAccount).count()

        # Get all users
        users = db.query(User).all()
        user_list = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "created_at": str(u.created_at),
            }
            for u in users
        ]

        # Get all connected accounts
        accounts = db.query(ConnectedAccount).all()
        account_list = [
            {
                "id": a.id,
                "user_id": a.user_id,
                "platform": a.platform,
                "platform_username": a.platform_username,
                "page_name": a.page_name,
                "is_active": a.is_active,
            }
            for a in accounts
        ]

        return {
            "status": "Database is working",
            "user_count": user_count,
            "account_count": account_count,
            "users": user_list,
            "accounts": account_list,
        }
    except Exception as e:
        return {
            "status": "Database error",
            "error": str(e),
        }


@router.get("/test-insert")
async def test_database_insert(db: Session = Depends(get_db)):
    """Test inserting data into database"""
    try:
        # Create test user
        test_user = User(
            username=f"test_user_{datetime.now().timestamp()}",
            email="test@example.com",
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        return {
            "status": "Insert successful",
            "user_id": test_user.id,
            "username": test_user.username,
        }
    except Exception as e:
        db.rollback()
        return {
            "status": "Insert failed",
            "error": str(e),
        }
