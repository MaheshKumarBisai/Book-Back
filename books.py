import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, get_db
from models import Book, Bookmark
from dependencies import get_current_user
from datetime import datetime, timedelta
from models import Order, Rental
from fastapi.responses import FileResponse, RedirectResponse
from s3_utils import generate_presigned_url




router = APIRouter(prefix="/books", tags=["Books"])


# --- Categories ---
@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    cats = db.query(Book.category).filter(Book.category != None, Book.category != '').distinct().all()
    return [c[0] for c in cats]


# --- Bookmarks ---
@router.get("/bookmarks")
def get_bookmarks(db: Session = Depends(get_db), user=Depends(get_current_user)):
    bookmarks = db.query(Bookmark).filter(Bookmark.user_id == user.id).order_by(Bookmark.created_at.desc()).all()
    result = []
    for bm in bookmarks:
        book = db.query(Book).filter(Book.id == bm.book_id).first()
        if book:
            avg = db.query(func.avg(Review.rating)).filter(Review.book_id == book.id).scalar()
            result.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "cover_image": f"/books/{book.id}/cover" if book.cover_image else None,
                "average_rating": float(round(avg, 1)) if avg else None,
                "bookmarked_at": bm.created_at
            })
    return result


# --- Books by category ---
@router.get("/by-category/{category}")
def books_by_category(category: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    books = db.query(Book).filter(Book.category == category).all()
    return [
        {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "price": book.price,
            "is_free": book.is_free,
            "cover_image": f"/books/{book.id}/cover" if book.cover_image else None,
            "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == book.id).scalar() or 0, 1)) or None
        }
        for book in books
    ]


# PROTECTED – list books
@router.get("/")
def list_books(db: Session = Depends(get_db), user=Depends(get_current_user)):
    books = db.query(Book).all()
    user_bookmarks = db.query(Bookmark.book_id).filter(Bookmark.user_id == user.id).all()
    bookmark_ids = {b[0] for b in user_bookmarks}
    
    return [
        {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "description": book.description,
            "category": book.category,
            "price": book.price,
            "is_free": book.is_free,
            "rent_price": book.rent_price,
            "pdf_path": book.pdf_path,
            "cover_image": f"/books/{book.id}/cover" if book.cover_image else None,
            "created_at": book.created_at,
            "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == book.id).scalar() or 0, 1)) or None,
            "is_bookmarked": book.id in bookmark_ids
        }
        for book in books
    ]

@router.get("/mine")
def my_books(db: Session = Depends(get_db), user=Depends(get_current_user)):
    # 1. Bought Books (only approved)
    bought_query = db.query(Order).filter(Order.user_id == user.id, Order.approval_status == "approved").all()
    bought_data = [
        {
            **order.book.__dict__,
            "cover_image": f"/books/{order.book.id}/cover" if order.book.cover_image else None,
            "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == order.book.id).scalar() or 0, 1)) or None,
            "created_at": order.created_at
        }
        for order in bought_query if order.book
    ]
    
    # 2. Rented Books (only approved, with expiration)
    rentals = db.query(Rental).filter(Rental.user_id == user.id, Rental.approval_status == "approved").all()
    rented_data = []
    
    for r in rentals:
        book = r.book
        if book:
            rented_data.append({
                "book": {
                     **book.__dict__,
                     "cover_image": f"/books/{book.id}/cover" if book.cover_image else None,
                     "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == book.id).scalar() or 0, 1)) or None
                },
                "expires_at": r.expires_at,
                "is_expired": r.expires_at < datetime.utcnow(),
                "created_at": r.created_at
            })
            
    return {
        "bought": bought_data,
        "rented": rented_data
    }

@router.get("/progress")
def get_all_reading_progress(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    from models import ReadingProgress
    progress_list = db.query(ReadingProgress).filter(
        ReadingProgress.user_id == user.id
    ).all()

    result = []
    for p in progress_list:
        book = db.query(Book).filter(Book.id == p.book_id).first()
        if book:
            result.append({
                "book_id": book.id,
                "category": book.category,
                "progress": float(p.progress),
                "last_read_at": p.last_read_at
            })
    return result

# PROTECTED – book details
@router.get("/{book_id}")
@router.get("/{book_id}")
def book_detail(book_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check status
    order = db.query(Order).filter(
        Order.user_id == user.id,
        Order.book_id == book.id
    ).first()

    rental = db.query(Rental).filter(
        Rental.user_id == user.id,
        Rental.book_id == book.id,
        Rental.expires_at > datetime.utcnow()
    ).first()

    # Calculate Average Rating
    avg_rating = db.query(func.avg(Review.rating)).filter(Review.book_id == book_id).scalar()
    
    # Check bookmark
    is_bookmarked = db.query(Bookmark).filter(
        Bookmark.user_id == user.id,
        Bookmark.book_id == book.id
    ).first() is not None
    
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "description": book.description,
        "category": book.category,
        "price": book.price,
        "rent_price": book.rent_price,
        "is_free": book.is_free,
        "pdf_path": book.pdf_path,
        "cover_image": f"/books/{book.id}/cover" if book.cover_image else None,
        "is_bought": order is not None and getattr(order, 'approval_status', 'approved') == 'approved',
        "is_rented": rental is not None and getattr(rental, 'approval_status', 'approved') == 'approved',
        "rental_expiry": rental.expires_at if rental else None,
        "buy_approval_status": getattr(order, 'approval_status', None) if order else None,
        "rent_approval_status": getattr(rental, 'approval_status', None) if rental else None,
        "average_rating": float(round(avg_rating, 1)) if avg_rating else None,
        "is_bookmarked": is_bookmarked
    }


# PROTECTED – add book (admin later)
@router.post("/")
def add_book(book: dict,
             db: Session = Depends(get_db),
             user=Depends(get_current_user)):
    new_book = Book(**book)
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book

@router.post("/{book_id}/buy")
def buy_book(
    book_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not user.name or not user.phone or not user.address:
        raise HTTPException(status_code=400, detail="Profile incomplete. Please update your profile.")

    order = Order(
        user_id=user.id,
        book_id=book.id,
        amount=book.price,
        approval_status="pending"
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Try to notify the merchant and user
    try:
        from notifications import create_notification
        if book.merchant_id:
            # Notify merchant
            create_notification(
                db=db, user_id=book.merchant_id, title="New Purchase Request",
                message=f"{user.name} wants to buy {book.title}",
                notification_type="buy_request", reference_id=order.id, sender_id=user.id
            )
        # Notify user
        create_notification(
            db=db, user_id=user.id, title="Request Sent",
            message="approval sent to merchant, Thank You",
            notification_type="info", reference_id=order.id, sender_id=None
        )
    except Exception as e:
        print("Notification error:", e)

    return {"message": "approval sent to merchant, Thank You"}

from pydantic import BaseModel

class RentRequest(BaseModel):
    days: int = 7

@router.post("/{book_id}/rent")
def rent_book(
    book_id: int,
    rent_request: RentRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    days = rent_request.days
    if days < 1:
        raise HTTPException(status_code=400, detail="Rental period must be at least 1 day")

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not user.name or not user.phone or not user.address:
        raise HTTPException(status_code=400, detail="Profile incomplete. Please update your profile.")

    # Calculate pro-rated price
    # Default rent_price is for 7 days
    rent_price_per_day = float(book.rent_price) / 7.0
    final_rent_price = rent_price_per_day * days

    rental = Rental(
        user_id=user.id,
        book_id=book.id,
        rent_price=final_rent_price,
        expires_at=datetime.utcnow() + timedelta(days=days),
        approval_status="pending"
    )
    db.add(rental)
    db.commit()
    db.refresh(rental)

    # Try to notify the merchant and user
    try:
        from notifications import create_notification
        if book.merchant_id:
            create_notification(
                db=db, user_id=book.merchant_id, title="New Rent Request",
                message=f"{user.name} wants to rent {book.title}",
                notification_type="rent_request", reference_id=rental.id, sender_id=user.id
            )
        create_notification(
            db=db, user_id=user.id, title="Request Sent",
            message="approval sent to merchant, Thank You",
            notification_type="info", reference_id=rental.id, sender_id=None
        )
    except Exception as e:
        print("Notification error:", e)

    return {"message": "approval sent to merchant, Thank You", "price": final_rent_price}


@router.get("/{book_id}/pdf")
def stream_pdf(
    book_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Access rules
    has_full_access = False
    
    if book.is_free:
        has_full_access = True
    else:
        bought = db.query(Order).filter(
            Order.user_id == user.id,
            Order.book_id == book.id,
            Order.approval_status == 'approved'
        ).first()

        rented = db.query(Rental).filter(
            Rental.user_id == user.id,
            Rental.book_id == book.id,
            Rental.expires_at > datetime.utcnow(),
            Rental.approval_status == 'approved'
        ).first()
        
        if bought or rented:
             has_full_access = True

    print(f"DEBUG: Streaming PDF for book {book_id}, Access: {has_full_access}")
    
    if not book.pdf_path or not os.path.exists(book.pdf_path):
        raise HTTPException(status_code=404, detail="PDF file missing")

    if has_full_access:
        if book.pdf_path.startswith("s3://"):
             # Generate Presigned URL and Redirect
             url = generate_presigned_url(book.pdf_path)
             if url:
                 return RedirectResponse(url=url)
             else:
                 raise HTTPException(status_code=500, detail="Could not generate PDF link")
        
        if not os.path.exists(book.pdf_path):
             raise HTTPException(status_code=404, detail="PDF file missing")
             
        return FileResponse(
            path=book.pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(book.pdf_path)
        )
    else:
        # SAMPLE MODE: First 2 pages
        try:
            import io
            from pypdf import PdfReader, PdfWriter
            
            reader = PdfReader(book.pdf_path)
            writer = PdfWriter()
            
            # Add up to 2 pages
            pages_to_add = min(2, len(reader.pages))
            for i in range(pages_to_add):
                writer.add_page(reader.pages[i])
                
            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)
            
            # Save to a temporary file is safer for FileResponse usually, 
            # but StreamingResponse is better for memory buffers.
            # Using StreamingResponse for sample.
            from fastapi.responses import StreamingResponse
            
            return StreamingResponse(
                output_stream, 
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=sample_{book_id}.pdf"}
            )
            
        except Exception as e:
            print(f"Error creating sample: {e}")
            raise HTTPException(status_code=500, detail="Could not generate sample")


@router.get("/{book_id}/cover")
def get_book_cover(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book.cover_image:
        if book.cover_image.startswith("s3://"):
             url = generate_presigned_url(book.cover_image)
             if url:
                 return RedirectResponse(url)
                 
        if os.path.exists(book.cover_image):
             return FileResponse(book.cover_image)
             
    raise HTTPException(status_code=404, detail="Cover image not found")



@router.get("/{book_id}/read")
def read_book(
    book_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Rule 1: Free book
    if book.is_free:
        return {"message": f"You can read '{book.title}'"}

    # Rule 2: Bought
    bought = db.query(Order).filter(
        Order.user_id == user.id,
        Order.book_id == book.id
    ).first()

    if bought:
        return {"message": f"You can read '{book.title}'"}

    # Rule 3: Rented & valid
    rented = db.query(Rental).filter(
        Rental.user_id == user.id,
        Rental.book_id == book.id,
        Rental.expires_at > datetime.utcnow()
    ).first()

    if rented:
        return {"message": f"You can read '{book.title}'"}

    raise HTTPException(status_code=403, detail="Access denied")

@router.get("/library/bought")
def bought_books(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    orders = (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .all()
    )

    return [
        {
            "id": o.book.id,
            "title": o.book.title,
            "author": o.book.author,
            "cover_image": f"/books/{o.book.id}/cover" if o.book.cover_image else None,
            "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == o.book.id).scalar() or 0, 1)) or None,
            "expires_at": None
        }
        for o in orders
    ]

@router.get("/library/rented")
def rented_books(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    rentals = (
        db.query(Rental)
        .filter(Rental.user_id == user.id)
        .all()
    )

    return [
        {
            "id": r.book.id,
            "title": r.book.title,
            "author": r.book.author,
            "cover_image": f"/books/{r.book.id}/cover" if r.book.cover_image else None,
            "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == r.book.id).scalar() or 0, 1)) or None,
            "expires_at": r.expires_at
        }
        for r in rentals
    ]

from models import ReadingProgress

@router.post("/{book_id}/start-reading")
def start_reading(
    book_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Verify book existence and access rights first (logic already in other endpoints, simplified here)
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if entry exists
    progress = db.query(ReadingProgress).filter(
        ReadingProgress.user_id == user.id,
        ReadingProgress.book_id == book_id
    ).first()

    if progress:
        progress.last_read_at = datetime.utcnow()
    else:
        progress = ReadingProgress(
            user_id=user.id,
            book_id=book_id,
            progress=0.0, # Start at 0%
            last_read_at=datetime.utcnow()
        )
        db.add(progress)
    
    db.commit()
    return {"message": "Reading started"}

@router.get("/current/reading")
def get_current_reading(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Get the MOST recenlty read book
    progress = db.query(ReadingProgress).filter(
        ReadingProgress.user_id == user.id
    ).order_by(ReadingProgress.last_read_at.desc()).first()

    if not progress:
        return None

    book = db.query(Book).filter(Book.id == progress.book_id).first()
    return {
        "book": {
            **book.__dict__,
            "cover_image": f"/books/{book.id}/cover" if book.cover_image else None,
            "average_rating": float(round(db.query(func.avg(Review.rating)).filter(Review.book_id == book.id).scalar() or 0, 1)) or None
        },
        "progress": progress.progress,
        "last_read_at": progress.last_read_at
    }



class ProgressUpdate(BaseModel):
    progress: float

@router.post("/{book_id}/progress")
def update_progress(
    book_id: int,
    update: ProgressUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Ensure 0-100
    if update.progress < 0 or update.progress > 100:
        raise HTTPException(status_code=400, detail="Progress must be between 0 and 100")

    progress_entry = db.query(ReadingProgress).filter(
        ReadingProgress.user_id == user.id,
        ReadingProgress.book_id == book_id
    ).first()

    if not progress_entry:
        raise HTTPException(status_code=404, detail="Reading progress not found. Start reading first.")

    progress_entry.progress = update.progress
    progress_entry.last_read_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Progress updated", "progress": progress_entry.progress}


# Reviews
from models import Review

class ReviewCreate(BaseModel):
    rating: int
    comment: str | None = None

@router.post("/{book_id}/reviews")
def add_review(
    book_id: int,
    review: ReviewCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if review.rating < 1 or review.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if user already reviewed? Optional. Let's allow multiple for now or unique?
    # Usually 1 per user per book.
    existing = db.query(Review).filter(Review.user_id == user.id, Review.book_id == book_id).first()
    if existing:
        existing.rating = review.rating
        existing.comment = review.comment
        existing.created_at = datetime.utcnow()
        message = "Review updated"
    else:
        new_review = Review(
            user_id=user.id,
            book_id=book_id,
            rating=review.rating,
            comment=review.comment
        )
        db.add(new_review)
        message = "Review added"
    
    db.commit()
    return {"message": message}

@router.get("/{book_id}/reviews")
def get_reviews(
    book_id: int,
    db: Session = Depends(get_db)
):
    reviews = db.query(Review).filter(Review.book_id == book_id).order_by(Review.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at,
            "user": {
                "name": r.user.name if r.user.name else "Anonymous",
                # "avatar": r.user.avatar ... add if User has avatar
            }
        }
        for r in reviews
    ]


# --- Bookmark toggle ---
@router.post("/{book_id}/bookmark")
def toggle_bookmark(
    book_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    existing = db.query(Bookmark).filter(
        Bookmark.user_id == user.id,
        Bookmark.book_id == book_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"bookmarked": False, "message": "Bookmark removed"}
    else:
        bm = Bookmark(user_id=user.id, book_id=book_id)
        db.add(bm)
        db.commit()
        return {"bookmarked": True, "message": "Book bookmarked"}


# --- PDF page text extraction ---
from fastapi import Query as QueryParam

@router.get("/{book_id}/pages")
def get_book_page(
    book_id: int,
    page: int = QueryParam(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not book.pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")

    # Handle S3 paths
    if book.pdf_path.startswith("s3://"):
        raise HTTPException(status_code=400, detail="In-app reading not yet supported for cloud-stored books")

    # Resolve relative path
    pdf_path = book.pdf_path
    if not os.path.isabs(pdf_path):
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), pdf_path)
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    # Check access
    has_access = book.is_free
    if not has_access:
        bought = db.query(Order).filter(Order.user_id == user.id, Order.book_id == book.id).first()
        rented = db.query(Rental).filter(
            Rental.user_id == user.id, Rental.book_id == book.id,
            Rental.expires_at > datetime.utcnow()
        ).first()
        has_access = bought is not None or rented is not None

    try:
        from pypdf import PdfReader
        from models import ReadingProgress

        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        target_page = page
        if target_page == 0:
            progress_entry = db.query(ReadingProgress).filter(
                ReadingProgress.user_id == user.id, ReadingProgress.book_id == book_id
            ).first()
            if progress_entry and progress_entry.progress > 0:
                target_page = int((float(progress_entry.progress) / 100.0) * total_pages)
                # Ensure it's bounded correctly
                if target_page < 1:
                    target_page = 1
                elif target_page > total_pages:
                    target_page = total_pages
            else:
                target_page = 1

        # Non-owners can only read first 2 pages (sample)
        if not has_access and target_page > 2:
            raise HTTPException(status_code=403, detail="Purchase or rent to read beyond sample pages")

        if target_page > total_pages:
            raise HTTPException(status_code=404, detail=f"Page {target_page} does not exist. Total pages: {total_pages}")

        text = reader.pages[target_page - 1].extract_text() or ""
        
        return {
            "text": text,
            "page": target_page,
            "total_pages": total_pages,
            "has_full_access": has_access
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error extracting page text: {e}")
        raise HTTPException(status_code=500, detail="Could not extract page text")
