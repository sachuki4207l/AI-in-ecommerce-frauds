"""
routes/complaints.py — Complaint lifecycle endpoints.
(Phase 6: Bidirectional credibility-aware transactional model)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

import uuid
import os

# ensure upload directory exists
UPLOAD_DIR = "uploads/complaints"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from database import get_db
from models import Buyer, Seller, Complaint, Product
from fraud_engine import recalculate_trust_score
from ai_vision import compare_images

router = APIRouter(prefix="/complaints", tags=["Complaints"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ComplaintCreate(BaseModel):
    buyer_id: int
    seller_id: int
    complaint_text: str
    severity_level: int  # 1–5

    @field_validator("severity_level")
    @classmethod
    def validate_severity(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("severity_level must be between 1 and 5")
        return v


class ComplaintUpdate(BaseModel):
    complaint_id: int
    complaint_text: Optional[str] = None
    severity_level: Optional[int] = None
    status: Optional[str] = None  # "open" | "resolved"

    @field_validator("severity_level")
    @classmethod
    def validate_severity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("severity_level must be between 1 and 5")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("open", "resolved"):
            raise ValueError("status must be 'open' or 'resolved'")
        return v


class ComplaintOut(BaseModel):
    id: int
    buyer_id: int
    seller_id: int
    complaint_text: str
    severity_level: int
    status: str
    received_image_path: Optional[str] = None
    visual_mismatch_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Helper: clamp credibility ────────────────────────────────────────────────

def _clamp_credibility(score: int) -> int:
    return max(20, min(100, score))


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/add", response_model=ComplaintOut)
def add_complaint(
    buyer_id: int = Form(...),
    seller_id: int = Form(...),
    complaint_text: str = Form(...),
    severity_level: int = Form(...),
    received_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    # verify buyer + seller
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")

    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    # enforce unique complaint rule
    existing = (
        db.query(Complaint)
        .filter(
            Complaint.buyer_id == buyer_id,
            Complaint.seller_id == seller_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Buyer already has a complaint for this seller. Use PUT /complaints/update to modify it.",
        )

    # handle optional image upload
    image_path = None
    if received_image is not None:
        file_ext = received_image.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{file_ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(received_image.file.read())

    try:
        complaint = Complaint(
            buyer_id=buyer_id,
            seller_id=seller_id,
            complaint_text=complaint_text,
            severity_level=severity_level,
            received_image_path=image_path,
        )
        db.add(complaint)

        # If a complaint image exists and a product image can be found, compute visual mismatch
        score = 0.0
        if image_path is not None:
            product = db.query(Product).filter(Product.seller_id == seller_id).first()
            if product and product.image_path:
                try:
                    score = compare_images(product.image_path, image_path)
                except Exception:
                    score = 0.0

        complaint.visual_mismatch_score = score

        # Adjust severity using AI evidence (amplifier, then clamp to 1..5)
        adjusted = round(severity_level * (1 + score))
        adjusted = min(5, max(1, adjusted))
        complaint.severity_level = adjusted

        # Recalculate seller trust score using the AI-adjusted severity
        recalculate_trust_score(db, seller_id)

        buyer.credibility_score -= 2
        buyer.credibility_score = _clamp_credibility(buyer.credibility_score)

        db.commit()
        db.refresh(complaint)
        return complaint
    except Exception:
        db.rollback()
        raise


@router.put("/update", response_model=ComplaintOut)
def update_complaint(payload: ComplaintUpdate, db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(Complaint.id == payload.complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    buyer = db.query(Buyer).filter(Buyer.id == complaint.buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")

    old_status = complaint.status

    try:
        # Apply updates
        if payload.complaint_text is not None:
            complaint.complaint_text = payload.complaint_text
        if payload.severity_level is not None:
            complaint.severity_level = payload.severity_level
        if payload.status is not None:
            complaint.status = payload.status

        complaint.updated_at = datetime.now(timezone.utc)

        # Recalculate seller trust score FIRST
        recalculate_trust_score(db, complaint.seller_id)

        # Credibility updates only if status changed open -> resolved
        if old_status == "open" and complaint.status == "resolved":
            buyer.credibility_score -= 3

            # Passive recovery for minor complaints
            if complaint.severity_level <= 2:
                buyer.credibility_score += 1

            buyer.credibility_score = _clamp_credibility(buyer.credibility_score)

        db.commit()
        db.refresh(complaint)
        return complaint

    except Exception:
        db.rollback()
        raise