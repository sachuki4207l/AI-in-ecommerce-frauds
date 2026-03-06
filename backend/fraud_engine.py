"""
fraud_engine.py — Hybrid risk calculation and trust-score recalculation.
(Phase 6: Credibility-weighted bidirectional model, transactional-safe)
"""

from sqlalchemy.orm import Session

from models import Seller, Product, Complaint

# ── Severity weight mapping ─────────────────────────────────────────────────

SEVERITY_WEIGHTS: dict[int, int] = {
    1: 2,
    2: 5,
    3: 10,
    4: 20,
    5: 35,
}

RESOLVED_DECAY_FACTOR = 0.2  # resolved complaints contribute 20 % of full weight


# ── Helpers ──────────────────────────────────────────────────────────────────

def _count_risk(complaint_count: int) -> int:
    """Capped linear risk from raw complaint count."""
    return min(40, complaint_count * 10)


def _credibility_multiplier(credibility_score: int) -> float:
    """
    Scale complaint impact based on buyer credibility.
    Ensures influence is reduced but never zero.
    """
    return 0.5 + (credibility_score / 200)


def _severity_risk(complaints: list[Complaint], include_resolved: bool) -> float:
    """
    Severity-weighted risk with buyer credibility weighting.
    If include_resolved=True → apply 20% decay for resolved complaints.
    If False → ignore resolved complaints (for advisory layer).
    """
    total = 0.0

    for c in complaints:
        # Skip resolved complaints entirely in real-time advisory layer
        if not include_resolved and c.status == "resolved":
            continue

        base_weight = SEVERITY_WEIGHTS.get(c.severity_level, 0)

        # Apply resolved decay only in historical layer
        if include_resolved and c.status == "resolved":
            base_weight *= RESOLVED_DECAY_FACTOR

        # Credibility-weighted multiplier
        buyer_cred = c.buyer.credibility_score if c.buyer else 100
        multiplier = _credibility_multiplier(buyer_cred)

        total += base_weight * multiplier

    return total


def _has_price_anomaly(products: list[Product]) -> bool:
    """
    Aggregated price anomaly:
    If more than half of a seller's products are priced below 60 % of market
    price, flag as anomalous.
    """
    if not products:
        return False
    anomalous = sum(1 for p in products if p.price < 0.6 * p.market_price)
    return anomalous > len(products) / 2


def _behavioral_risk(seller: Seller, products: list[Product]) -> int:
    """Account-age and price-anomaly risk components (0–60 max)."""
    risk = 0
    if seller.account_age_days < 30:
        risk += 30
    if _has_price_anomaly(products):
        risk += 30
    return risk


# ── Public helpers ───────────────────────────────────────────────────────────

def has_price_anomaly(products: list[Product]) -> bool:
    """Public wrapper so advisory module can reuse anomaly check."""
    return _has_price_anomaly(products)


# ── Public API ───────────────────────────────────────────────────────────────

def recalculate_trust_score(db: Session, seller_id: int) -> int:
    """
    Layer 1 — Historical Trust Score.
    Recompute and persist the trust_score for a given seller.
    Uses ALL complaints (open + resolved with decay) AND credibility weighting.
    NOTE: Does NOT commit. Caller must manage transaction.
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if seller is None:
        return -1

    complaints = (
        db.query(Complaint)
        .filter(Complaint.seller_id == seller_id)
        .all()
    )
    products = (
        db.query(Product)
        .filter(Product.seller_id == seller_id)
        .all()
    )

    count_r = _count_risk(len(complaints))
    severity_r = _severity_risk(complaints, include_resolved=True)
    behavioral_r = _behavioral_risk(seller, products)

    total_risk = count_r + severity_r + behavioral_r
    new_score = max(0, int(100 - total_risk))

    seller.trust_score = new_score
    return new_score


def evaluate_current_risk(db: Session, seller_id: int) -> dict | None:
    """
    Layer 2 — Real-Time Advisory Trust Score (read-only).
    Uses ONLY open complaints + credibility weighting.
    Does NOT write anything to the database.
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if seller is None:
        return None

    complaints = (
        db.query(Complaint)
        .filter(Complaint.seller_id == seller_id)
        .all()
    )
    products = (
        db.query(Product)
        .filter(Product.seller_id == seller_id)
        .all()
    )

    count_r = _count_risk(len([c for c in complaints if c.status == "open"]))
    severity_r = _severity_risk(complaints, include_resolved=False)
    behavioral_r = _behavioral_risk(seller, products)

    total_risk = count_r + severity_r + behavioral_r
    fresh_score = max(0, int(100 - total_risk))

    return {
        "seller": seller,
        "fresh_trust_score": fresh_score,
        "open_complaints": [c for c in complaints if c.status == "open"],
        "products": products,
        "price_anomaly": _has_price_anomaly(products),
    }