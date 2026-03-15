from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, get_db
from models import Order, Rental, Book
from dependencies import get_current_user
from datetime import datetime

router = APIRouter(prefix="/library")


@router.get("/")
def my_library(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    bought = db.query(Book).join(Order, Book.id == Order.book_id).filter(
        Order.user_id == user.id,
        Order.approval_status == "approved"
    ).all()

    rented = db.query(Book).join(Rental, Book.id == Rental.book_id).filter(
        Rental.user_id == user.id,
        Rental.expires_at > datetime.utcnow(),
        Rental.approval_status == "approved"
    ).all()

    return {
        "bought_books": bought,
        "rented_books": rented
    }
