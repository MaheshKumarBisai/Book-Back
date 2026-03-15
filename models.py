from sqlalchemy import Column, String, Boolean, Text, Integer, Numeric, TIMESTAMP, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import BIGINT
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BIGINT, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, default="user")
    name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)
    password_hash = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class EmailOTP(Base):
    __tablename__ = "email_otp"

    id = Column(BIGINT, primary_key=True, index=True)
    email = Column(String, nullable=False)
    otp = Column(Integer, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Book(Base):
    __tablename__ = "books"

    id = Column(BIGINT, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))

    price = Column(Numeric(10,2))
    rent_price = Column(Numeric(10,2))
    is_free = Column(Boolean, default=False)

    pdf_path = Column(String, nullable=False)
    cover_image = Column(String, nullable=True)
    merchant_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    merchant = relationship("User", foreign_keys=[merchant_id])

class Order(Base):
    __tablename__ = "orders"

    id = Column(BIGINT, primary_key=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    book_id = Column(BIGINT, ForeignKey("books.id"))
    amount = Column(Numeric(10,2))
    approval_status = Column(String, default="approved") # "pending", "approved", "rejected"
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    book = relationship("Book")


class Rental(Base):
    __tablename__ = "rentals"

    id = Column(BIGINT, primary_key=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    book_id = Column(BIGINT, ForeignKey("books.id"))
    rent_price = Column(Numeric(10,2))
    expires_at = Column(TIMESTAMP)
    approval_status = Column(String, default="approved") # "pending", "approved", "rejected"
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    book = relationship("Book")
    created_at = Column(TIMESTAMP, server_default=func.now())

class ReadingProgress(Base):
    __tablename__ = "reading_progress"

    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    book_id = Column(BIGINT, ForeignKey("books.id"))
    progress = Column(Numeric(5, 2), default=0.0) # Percentage 0-100
    last_read_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    book = relationship("Book")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    book_id = Column(BIGINT, ForeignKey("books.id"))
    rating = Column(Integer, nullable=False) # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    book = relationship("Book")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    book_id = Column(BIGINT, ForeignKey("books.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    book = relationship("Book")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    notification_type = Column(String, nullable=True) # buy_request, rent_request, accepted, rejected, info
    reference_id = Column(BIGINT, nullable=True) # ID of the Order or Rental
    sender_id = Column(BIGINT, ForeignKey("users.id"), nullable=True) # User who sent the request
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    sender = relationship("User", foreign_keys=[sender_id])

class MerchantProfile(Base):
    __tablename__ = "merchant_profiles"

    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"), unique=True)
    merchant_name = Column(String(255), nullable=False)
    library_name = Column(String(255), nullable=False)
    num_books = Column(Integer, nullable=False)
    is_approved = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
