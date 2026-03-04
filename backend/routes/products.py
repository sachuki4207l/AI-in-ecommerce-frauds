"""
routes/products.py — Product CRUD endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

import uuid
import os

from database import get_db
from models import Product, Seller

# ensure upload directory exists
UPLOAD_DIR = "uploads/products"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/products", tags=["Products"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    title: str
    price: int
    market_price: int
    seller_id: int


class ProductOut(BaseModel):
    id: int
    title: str
    price: int
    market_price: int
    seller_id: int
    image_path: str

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/add", response_model=ProductOut)
def add_product(
    title: str = Form(...),
    price: int = Form(...),
    market_price: int = Form(...),
    seller_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # validate seller
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    # save image to disk
    file_ext = image.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(image.file.read())

    product = Product(
        title=title,
        price=price,
        market_price=market_price,
        seller_id=seller_id,
        image_path=file_path,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/all", response_model=list[ProductOut])
def get_all_products(db: Session = Depends(get_db)):
    return db.query(Product).all()
