from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.routers.workspace import public_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [public_user(person) for person in db.scalars(select(User).order_by(User.created_at.desc()).limit(100)).all()]

