"""
test_phase4.py — Dual-layer trust model integration test.
Validates that advisory uses real-time open-only evaluation (Layer 2),
while the persisted trust_score reflects historical data (Layer 1).
"""

import json
import urllib.request
import urllib.error


def api(method, path, data=None):
    url = f"http://127.0.0.1:8000{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read())
            print(f"{method} {path}")
            print(json.dumps(resp, indent=2))
            print()
            return resp
    except urllib.error.HTTPError as e:
        resp = e.read().decode()
        print(f"{method} {path} => HTTP {e.code}:")
        print(resp)
        print()
        return json.loads(resp)


def section(title):
    print("=" * 60)
    print(title)
    print("=" * 60)


def main():
    section("SETUP")

    # Scenario 1: Old seller, no complaints, normal pricing
    s1 = api("POST", "/sellers/add", {"name": "VeteranShop", "account_age_days": 500})
    api("POST", "/products/add", {"title": "Case", "price": 20, "market_price": 25, "seller_id": s1["id"]})

    # Scenario 2: Old seller, no complaints, strong price anomaly
    s2 = api("POST", "/sellers/add", {"name": "CheapButOld", "account_age_days": 200})
    api("POST", "/products/add", {"title": "TV", "price": 100, "market_price": 1000, "seller_id": s2["id"]})
    api("POST", "/products/add", {"title": "Phone", "price": 50, "market_price": 800, "seller_id": s2["id"]})

    # Scenario 3: Old seller, moderate open complaints
    s3 = api("POST", "/sellers/add", {"name": "MidRiskStore", "account_age_days": 120})
    b1 = api("POST", "/buyers/add", {"name": "Carol"})
    b2 = api("POST", "/buyers/add", {"name": "Dave"})
    api("POST", "/complaints/add", {"buyer_id": b1["id"], "seller_id": s3["id"], "complaint_text": "Wrong color", "severity_level": 3})
    api("POST", "/complaints/add", {"buyer_id": b2["id"], "seller_id": s3["id"], "complaint_text": "Late delivery", "severity_level": 2})

    # Scenario 4: New seller + high severity unresolved complaint
    s4 = api("POST", "/sellers/add", {"name": "ScamNewbie", "account_age_days": 7})
    b3 = api("POST", "/buyers/add", {"name": "Eve"})
    c4 = api("POST", "/complaints/add", {"buyer_id": b3["id"], "seller_id": s4["id"], "complaint_text": "Fake product", "severity_level": 5})

    # ── Advisory scenarios ──
    section("SCENARIO 1: Old, no complaints, normal pricing -> Safe")
    api("GET", f"/advisory/seller/{s1['id']}")

    section("SCENARIO 2: Old, no complaints, price anomaly -> Safe + pricing caution")
    api("GET", f"/advisory/seller/{s2['id']}")

    section("SCENARIO 3: Moderate open complaints -> Caution")
    api("GET", f"/advisory/seller/{s3['id']}")

    section("SCENARIO 4: New + sev-5 open -> High Risk")
    api("GET", f"/advisory/seller/{s4['id']}")

    section("ERROR: Non-existent seller -> 404 JSON")
    api("GET", "/advisory/seller/999")

    # ── DUAL-LAYER PROOF: Resolve Scenario 4's complaint ──
    section("DUAL-LAYER TEST: Resolve the sev-5 complaint on ScamNewbie")
    api("PUT", "/complaints/update", {"complaint_id": c4["id"], "status": "resolved"})

    section("Historical trust_score (Layer 1) -- still penalized by resolved complaint")
    sellers = api("GET", "/sellers/all")
    s4_stored = [s for s in sellers if s["id"] == s4["id"]][0]
    print(f"  ScamNewbie stored trust_score = {s4_stored['trust_score']}")
    print(f"  (Resolved sev-5 still contributes 20% decay = 7 risk)")
    print()

    section("Real-time advisory (Layer 2) -- ignores resolved, only open complaints")
    adv = api("GET", f"/advisory/seller/{s4['id']}")
    print(f"  Advisory fresh trust_score = {adv['trust_score']}")
    print(f"  (No open complaints -> only behavioral risk from account age)")
    print(f"  Expected: trust_score=70, risk_level=Safe")
    print()


if __name__ == "__main__":
    main()
