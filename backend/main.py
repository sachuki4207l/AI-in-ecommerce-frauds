"""
main.py — FastAPI application entrypoint for Phase 5 (Frontend Simulation Layer).
AI-Based Bidirectional Fraud & Trust Detection Backend.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import engine, Base
from routes import sellers, products, buyers, complaints, advisory

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Fraud & Trust Detection API — Phase 5",
    description=(
        "Bidirectional trust model with explainable seller advisory engine "
        "and frontend simulation layer."
    ),
    version="5.0.0",
)

# ── Register API routers ────────────────────────────────────────────────────
app.include_router(sellers.router)
app.include_router(products.router)
app.include_router(buyers.router)
app.include_router(complaints.router)
app.include_router(advisory.router)

# ── Frontend Setup (NEW) ────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Frontend Routes ─────────────────────────────────────────────────────────
@app.get("/", tags=["Frontend"])
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/seller/{seller_id}", tags=["Frontend"])
def seller_page(request: Request, seller_id: int):
    return templates.TemplateResponse(
        "seller.html",
        {"request": request, "seller_id": seller_id},
    )

# ── Optional: keep health-check under different path ────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "running",
        "phase": 5,
        "message": "Bidirectional Fraud & Trust Detection API is live.",
    }