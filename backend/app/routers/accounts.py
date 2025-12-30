from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import ConnectedAccount, User
from app.schemas import ConnectedAccountResponse

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/{user_id}", response_model=List[ConnectedAccountResponse])
async def get_connected_accounts(user_id: int, db: Session = Depends(get_db)):
    """Get all connected accounts for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    accounts = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == user_id, ConnectedAccount.is_active == True)
        .all()
    )

    return accounts


@router.delete("/{account_id}")
async def disconnect_account(account_id: int, db: Session = Depends(get_db)):
    """Disconnect a social media account"""
    account = db.query(ConnectedAccount).filter(ConnectedAccount.id == account_id).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = False
    db.commit()

    return {"message": "Account disconnected successfully"}


@router.post("/{account_id}/reactivate")
async def reactivate_account(account_id: int, db: Session = Depends(get_db)):
    """Reactivate a disconnected account"""
    account = db.query(ConnectedAccount).filter(ConnectedAccount.id == account_id).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = True
    db.commit()

    return {"message": "Account reactivated successfully"}
