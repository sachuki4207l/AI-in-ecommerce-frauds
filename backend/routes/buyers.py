"""
routes/buyers.py — Buyer CRUD endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Buyer

router = APIRouter(prefix="/buyers", tags=["Buyers"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class BuyerCreate(BaseModel):
    name: str


class BuyerOut(BaseModel):
    id: int
    name: str
    credibility_score: int
    spam_flag_count: int

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/add", response_model=BuyerOut)
def add_buyer(payload: BuyerCreate, db: Session = Depends(get_db)):
    buyer = Buyer(name=payload.name)
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


@router.get("/all", response_model=list[BuyerOut])
def get_all_buyers(db: Session = Depends(get_db)):
    return db.query(Buyer).all()
