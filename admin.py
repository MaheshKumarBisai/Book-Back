from fastapi import APIRouter, Depends, UploadFile, File, Form
import shutil, os
from database import SessionLocal, get_db
from models import Book, User, Order, Rental
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from admin_dependency import admin_only
from s3_utils import upload_file_to_s3, delete_file_from_s3
import uuid

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db), admin = Depends(admin_only)):
    query_users = db.query(User)
    query_books = db.query(Book)
    query_orders = db.query(Order)
    query_rentals = db.query(Rental)

    if admin.role == "merchant":
        query_books = query_books.filter(Book.merchant_id == admin.id)
        query_orders = query_orders.join(Book).filter(Book.merchant_id == admin.id)
        query_rentals = query_rentals.join(Book).filter(Book.merchant_id == admin.id)
        # For merchants, total_users might not be relevant or could be filtered by customers who bought their books
        # For now, let's keep it simple as per user request (starting at zero)
        total_users = 0 
    else:
        total_users = query_users.count()

    total_books = query_books.count()
    total_orders = query_orders.count()
    total_rentals = query_rentals.count()
    
    # Calculate revenue
    revenue_orders = query_orders.with_entities(func.sum(Order.amount)).scalar() or 0
    revenue_rentals = query_rentals.with_entities(func.sum(Rental.rent_price)).scalar() or 0
    total_revenue = float(revenue_orders + revenue_rentals)

    return {
        "total_users": total_users,
        "total_books": total_books,
        "total_orders": total_orders,
        "total_rentals": total_rentals,
        "total_revenue": total_revenue
    }

@router.get("/users")
def get_all_users(db: Session = Depends(get_db), admin = Depends(admin_only)):
    if admin.role == "merchant":
        return []
    return db.query(User).all()

@router.get("/books")
def get_admin_books(db: Session = Depends(get_db), admin = Depends(admin_only)):
    query = db.query(Book)
    if admin.role == "merchant":
        query = query.filter(Book.merchant_id == admin.id)
    return query.all()

@router.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db), admin = Depends(admin_only)):
    book_query = db.query(Book).filter(Book.id == book_id)
    if admin.role == "merchant":
        book_query = book_query.filter(Book.merchant_id == admin.id)
    
    book = book_query.first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found or access denied")
    
    # Optional: Delete PDF file
    # Delete PDF file
    if book.pdf_path:
        if book.pdf_path.startswith("s3://"):
            delete_file_from_s3(book.pdf_path)
        elif os.path.exists(book.pdf_path):
            os.remove(book.pdf_path)
            
    # Delete Cover
    if book.cover_image:
        if book.cover_image.startswith("s3://"):
             delete_file_from_s3(book.cover_image)
    
    # Delete related records to prevent foreign key violations
    from models import ReadingProgress, Review, Bookmark
    db.query(Order).filter(Order.book_id == book_id).delete()
    db.query(Rental).filter(Rental.book_id == book_id).delete()
    db.query(ReadingProgress).filter(ReadingProgress.book_id == book_id).delete()
    db.query(Review).filter(Review.book_id == book_id).delete()
    db.query(Bookmark).filter(Bookmark.book_id == book_id).delete()
    
    db.delete(book)
    db.commit()
    return {"message": "Book deleted successfully"}

@router.post("/books/upload")
def upload_book(
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(None),
    category: str = Form(None),
    price: float = Form(0),
    rent_price: float = Form(0),
    is_free: bool = Form(False),
    pdf: UploadFile = File(...),
    cover_image: UploadFile = File(None),
    db = Depends(get_db),
    admin = Depends(admin_only)
):
    # PDF Upload
    pdf_filename = f"profiles/merchant/books/{uuid.uuid4()}_{pdf.filename}"
    pdf_path = upload_file_to_s3(pdf.file, pdf_filename, pdf.content_type)
    
    if not pdf_path:
        raise HTTPException(status_code=500, detail="S3 Upload Failed for Document. Please check S3 credentials.")

    # Cover Upload
    cover_image_path = None
    if cover_image:
        cover_filename = f"profiles/merchant/covers/{uuid.uuid4()}_{cover_image.filename}"
        cover_image_path = upload_file_to_s3(cover_image.file, cover_filename, cover_image.content_type)
        
        if not cover_image_path:
            raise HTTPException(status_code=500, detail="S3 Upload Failed for Cover Image. Please check S3 credentials.")

    book = Book(
        title=title,
        author=author,
        description=description,
        category=category,
        price=price,
        rent_price=rent_price,
        is_free=is_free,
        pdf_path=pdf_path,
        cover_image=cover_image_path,
        merchant_id=admin.id
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    return {"message": "Book uploaded successfully", "book_id": book.id}
