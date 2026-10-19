"""Legacy pact URLs use the same session and membership rules as the workspace."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Pact, PactParticipant, User
from app.routers.auth import get_current_user
from app.routers.workspace import member_pact, pact_view

router = APIRouter(prefix="/pacts", tags=["pacts"])

@router.get("")
def list_pacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pacts = db.scalars(select(Pact).join(PactParticipant).where(PactParticipant.user_id == user.id)).all()
    return [pact_view(db, pact, user) for pact in pacts]

@router.get("/{pact_id}")
def get_pact(pact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return pact_view(db, member_pact(db, pact_id, user), user)

@router.post("")
def create_pact(user: User = Depends(get_current_user)):
    raise HTTPException(422, "Создайте свой пакт через /my/pacts или отправьте совместный запрос")

@router.patch("/{pact_id}")
def update_pact(pact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member_pact(db, pact_id, user)
    raise HTTPException(409, "Условия заключённого пакта зафиксированы")

