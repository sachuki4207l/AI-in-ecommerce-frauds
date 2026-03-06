"""
routes/advisory.py — Phase 4: Real-Time Seller Advisory Engine.

Uses a dual-layer trust model:
  Layer 1 (historical) — persisted trust_score from fraud_engine.recalculate_trust_score
  Layer 2 (real-time)  — fresh score via fraud_engine.evaluate_current_risk (read-only)

This module only uses Layer 2 for advisory responses.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Seller, Complaint
from fraud_engine import evaluate_current_risk

router = APIRouter(prefix="/advisory", tags=["Advisory"])


# ── Risk-level thresholds (immutable) ────────────────────────────────────────

def _risk_level(trust_score: int) -> str:
    if trust_score >= 70:
        return "Safe"
    if trust_score >= 40:
        return "Caution"
    return "High Risk"


# ── Static recommendation text ───────────────────────────────────────────────

_STATIC_RECOMMENDATIONS: dict[str, str] = {
    "Safe": "Safe to purchase from this seller",
    "Caution": "Proceed with caution when purchasing",
    "High Risk": "Avoid purchase from this seller",
}

_ANOMALY_SAFE_RECOMMENDATION = "Safe to purchase, but review pricing carefully"


# ── Reason builder (ordered by importance) ───────────────────────────────────

# Importance rank constants (lower = more important)
_RANK_HIGH_SEVERITY = 0
_RANK_SUSPICIOUS_PRICING = 1
_RANK_NEW_ACCOUNT = 2
_RANK_HAS_COMPLAINTS = 3
_RANK_VISUAL_MISMATCH = 1


def _build_reasons(
    seller: Seller,
    open_complaints: list[Complaint],
    price_anomaly: bool,
    is_anomaly_safe_override: bool,
) -> list[str]:
    """Dynamically generate reasons sorted by importance hierarchy."""
    ranked: list[tuple[int, str]] = []

    # High severity unresolved complaints
    has_high_sev = any(c.severity_level >= 4 for c in open_complaints)
    if has_high_sev:
        ranked.append((_RANK_HIGH_SEVERITY, "High severity unresolved complaints detected"))

    # Suspicious / unusual pricing
    if price_anomaly:
        if is_anomaly_safe_override:
            ranked.append((_RANK_SUSPICIOUS_PRICING, "Seller exhibits unusual pricing patterns"))
        else:
            ranked.append((_RANK_SUSPICIOUS_PRICING, "Seller exhibits suspicious pricing behavior"))

    # Visual mismatch evidence from complaints (AI)
    has_visual_mismatch = any((getattr(c, "visual_mismatch_score", 0) or 0) > 0.6 for c in open_complaints)
    if has_visual_mismatch:
        ranked.append((_RANK_VISUAL_MISMATCH, "Significant visual discrepancy detected between listed and delivered product"))

    # New account
    if seller.account_age_days < 30:
        ranked.append((_RANK_NEW_ACCOUNT, "Seller account is relatively new"))

    # Active complaints
    if len(open_complaints) > 0:
        ranked.append((_RANK_HAS_COMPLAINTS, "Seller has active customer complaints"))

    ranked.sort(key=lambda r: r[0])
    return [text for _, text in ranked]


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/seller/{seller_id}")
def get_seller_advisory(seller_id: int, db: Session = Depends(get_db)):
    # Real-time read-only evaluation (Layer 2)
    result = evaluate_current_risk(db, seller_id)

    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Seller not found", "seller_id": seller_id},
        )

    seller = result["seller"]
    fresh_score = result["fresh_trust_score"]
    open_complaints = result["open_complaints"]
    price_anomaly = result["price_anomaly"]

    risk = _risk_level(fresh_score)

    # Anomaly-safe special case
    is_anomaly_safe = (risk == "Safe" and len(open_complaints) == 0 and price_anomaly)

    if is_anomaly_safe:
        recommendation = _ANOMALY_SAFE_RECOMMENDATION
    else:
        recommendation = _STATIC_RECOMMENDATIONS[risk]

    reasons = _build_reasons(seller, open_complaints, price_anomaly, is_anomaly_safe)

    return {
        "seller_id": seller.id,
        "trust_score": fresh_score,
        "risk_level": risk,
        "recommendation": recommendation,
        "reasons": reasons,
    }
