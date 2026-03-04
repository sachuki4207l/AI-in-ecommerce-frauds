"""
routes/sellers.py — Seller CRUD endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Seller

router = APIRouter(prefix="/sellers", tags=["Sellers"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SellerCreate(BaseModel):
    name: str
    account_age_days: int = 0


class SellerOut(BaseModel):
    id: int
    name: str
    account_age_days: int
    trust_score: int

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/add", response_model=SellerOut)
def add_seller(payload: SellerCreate, db: Session = Depends(get_db)):
    seller = Seller(name=payload.name, account_age_days=payload.account_age_days)
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


@router.get("/all", response_model=list[SellerOut])
def get_all_sellers(db: Session = Depends(get_db)):
    return db.query(Seller).all()
