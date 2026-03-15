from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Notification, User, Order, Rental, Book
from auth.auth import get_current_user
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from s3_utils import generate_presigned_url

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class NotificationSchema(BaseModel):
    id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime
    notification_type: Optional[str] = None
    reference_id: Optional[int] = None
    sender_id: Optional[int] = None
    
    # Extra fields for frontend rendering of requests
    sender_name: Optional[str] = None
    sender_phone: Optional[str] = None
    sender_address: Optional[str] = None
    book_title: Optional[str] = None
    sender_photo: Optional[str] = None
    book_cover: Optional[str] = None
    approval_status: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/", response_model=List[NotificationSchema])
def get_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()
    
    result = []
    for n in notifs:
        notif_dict = {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at,
            "notification_type": n.notification_type,
            "reference_id": n.reference_id,
            "sender_id": n.sender_id
        }
        
        # Populate extra metadata for purchase or rent requests
        if n.notification_type in ['buy_request', 'rent_request'] and n.sender_id and n.reference_id:
            sender = db.query(User).filter(User.id == n.sender_id).first()
            if sender:
                notif_dict["sender_name"] = sender.name or "Unknown User"
                notif_dict["sender_phone"] = sender.phone
                notif_dict["sender_address"] = sender.address
                if sender.profile_picture:
                    notif_dict["sender_photo"] = generate_presigned_url(sender.profile_picture) if sender.profile_picture.startswith("s3://") else sender.profile_picture

            # Find the linked order/rental to get the book and status
            if n.notification_type == 'buy_request':
                order = db.query(Order).filter(Order.id == n.reference_id).first()
                if order:
                    notif_dict["approval_status"] = order.approval_status
                    book = db.query(Book).filter(Book.id == order.book_id).first()
                    if book:
                        notif_dict["book_title"] = book.title
                        notif_dict["book_cover"] = book.cover_image
            elif n.notification_type == 'rent_request':
                rental = db.query(Rental).filter(Rental.id == n.reference_id).first()
                if rental:
                    notif_dict["approval_status"] = rental.approval_status
                    book = db.query(Book).filter(Book.id == rental.book_id).first()
                    if book:
                        notif_dict["book_title"] = book.title
                        notif_dict["book_cover"] = book.cover_image
                        
        result.append(notif_dict)

    return result

@router.post("/{notification_id}/read")
def mark_as_read(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Marked as read"}

@router.post("/clear-all")
def clear_all_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == current_user.id).delete()
    db.commit()
    return {"message": "All notifications cleared"}

class RespondRequest(BaseModel):
    action: str # "accept" or "reject"

@router.post("/{notification_id}/respond")
def respond_to_request(notification_id: int, req: RespondRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    if req.action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    new_status = "approved" if req.action == "accept" else "rejected"
    book_title = "Unknown Book"
    sender_name = "User"

    sender = db.query(User).filter(User.id == notif.sender_id).first()
    if sender and sender.name:
        sender_name = sender.name

    if notif.notification_type == 'buy_request':
        order = db.query(Order).filter(Order.id == notif.reference_id).first()
        if order:
            order.approval_status = new_status
            book = db.query(Book).filter(Book.id == order.book_id).first()
            if book: book_title = book.title

    elif notif.notification_type == 'rent_request':
        rental = db.query(Rental).filter(Rental.id == notif.reference_id).first()
        if rental:
            rental.approval_status = new_status
            book = db.query(Book).filter(Book.id == rental.book_id).first()
            if book: book_title = book.title

    db.commit()

    # Create an auto-reply notification back to the user
    if notif.sender_id:
        if req.action == "accept":
            reply_title = "Request Approved"
            reply_msg = f"Yeh {sender_name}, you succesfully bought {book_title}, Thank you."
        else:
            reply_title = "Request Rejected"
            reply_msg = f"We're Sorry {sender_name}, {book_title} couldn't be read."
            
        create_notification(
            db=db, user_id=notif.sender_id, title=reply_title, message=reply_msg,
            notification_type="info", reference_id=None, sender_id=current_user.id
        )

    return {"message": f"Request {new_status}"}

def create_notification(db: Session, user_id: int, title: str, message: str, notification_type: str = None, reference_id: int = None, sender_id: int = None):
    new_notif = Notification(
        user_id=user_id, 
        title=title, 
        message=message,
        notification_type=notification_type,
        reference_id=reference_id,
        sender_id=sender_id
    )
    db.add(new_notif)
    db.commit()
    db.refresh(new_notif)
    return new_notif
