from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from schemas import EmailRequest, VerifyOTPRequest, RefreshTokenRequest, UserProfileUpdate, SetPasswordRequest, LoginRequest, MerchantRegisterRequest
from datetime import datetime
from database import SessionLocal, get_db
from models import User, EmailOTP, MerchantProfile
from utils import generate_otp, otp_expiry, create_access_token, create_refresh_token
from dependencies import get_current_user
import shutil
import os
import uuid
from s3_utils import upload_file_to_s3, generate_presigned_url
from passlib.context import CryptContext

from email_utils import send_otp_email
from redis_client import redis_client

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

router = APIRouter(prefix="/auth")


@router.post("/send-otp")
def send_otp(request: EmailRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()

    otp = generate_otp()

    if redis_client:
        # Store in Redis with 5-minute TTL (auto-expires)
        redis_client.setex(f"otp:{email}", 300, otp)
    else:
        # Fallback: store in PostgreSQL
        db_otp = EmailOTP(
            email=email,
            otp=otp,
            expires_at=otp_expiry()
        )
        db.add(db_otp)
        db.commit()

    send_otp_email(email, otp)
    return {"message": "OTP sent to email"}


@router.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    otp = request.otp.strip()

    valid = False

    if redis_client:
        # Check Redis
        stored_otp = redis_client.get(f"otp:{email}")
        if stored_otp and stored_otp == otp:
            redis_client.delete(f"otp:{email}")  # One-time use
            valid = True
    else:
        # Fallback: check PostgreSQL
        record = db.query(EmailOTP).filter(
            EmailOTP.email == email,
            EmailOTP.otp == otp,
            EmailOTP.is_used == False,
            EmailOTP.expires_at > datetime.utcnow()
        ).first()
        if record:
            record.is_used = True
            db.commit()
            valid = True

    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.is_verified = True
    db.commit()

    access_token = create_access_token({"user_id": user.id, "email": user.email})
    refresh_token = create_refresh_token({"user_id": user.id, "email": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role,
        "has_password": user.password_hash is not None
    }

def process_refresh_token(refresh_token: str, db: Session):
    from jose import jwt, JWTError
    from utils import SECRET_KEY, ALGORITHM

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
             raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("user_id")
        email = payload.get("email")
        if user_id is None or email is None:
             raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = create_access_token({"user_id": user.id, "email": email})
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    return process_refresh_token(request.refresh_token, db)

@router.post("/refresh/{refresh_token}")
def refresh_token_path(refresh_token: str, db: Session = Depends(get_db)):
    return process_refresh_token(refresh_token, db)


@router.post("/set-password")
def set_password(request: SetPasswordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import traceback
    try:
        if len(request.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.password_hash = pwd_context.hash(request.password[:72])
        db.commit()
        
        return {"message": "Password set successfully"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="No password set. Please use OTP to sign in and set your password.",
                            headers={"X-Has-Password": "false"})
    
    if not pwd_context.verify(request.password[:72], user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token({"user_id": user.id, "email": user.email})
    refresh_token = create_refresh_token({"user_id": user.id, "email": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role
    }


@router.post("/refresh_path/{refresh_token}")
def refresh_token_path_alt(refresh_token: str, db: Session = Depends(get_db)):
    return process_refresh_token(refresh_token, db)

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "phone": current_user.phone,
        "address": current_user.address,
        "is_verified": current_user.is_verified,
        "role": current_user.role,
        "profile_picture": generate_presigned_url(current_user.profile_picture) if current_user.profile_picture and current_user.profile_picture.startswith("s3://") else current_user.profile_picture
    }

@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return {
        "name": user.name,
        "phone": user.phone,
        "address": user.address,
        "address": user.address,
        "profile_picture": generate_presigned_url(user.profile_picture) if user.profile_picture and user.profile_picture.startswith("s3://") else user.profile_picture
    }

@router.put("/profile")
def update_profile(profile: UserProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.name = profile.name
    user.phone = profile.phone
    user.address = profile.address
    db.commit()
    user.address = profile.address
    db.commit()
    return {"message": "Profile updated successfully"}


@router.post("/profile/upload-photo")
def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validate file type
    if not file.content_type.startswith("image/"):
         raise HTTPException(status_code=400, detail="File must be an image")

    # Generate unique filename with role-based prefix
    file_extension = os.path.splitext(file.filename)[1]
    
    if current_user.role == "merchant":
        unique_filename = f"profiles/merchant/{uuid.uuid4()}{file_extension}"
    else:
        unique_filename = f"profiles/users/{uuid.uuid4()}{file_extension}"
    
    # Try S3 Upload
    s3_url = upload_file_to_s3(file.file, unique_filename, file.content_type)
    
    if not s3_url:
        raise HTTPException(status_code=500, detail="S3 Upload Failed. Please check .env configuration.")

    # Update user profile
    user = db.query(User).filter(User.id == current_user.id).first()
    
    user.profile_picture = s3_url
    db.commit()

    return {
        "message": "Profile picture uploaded", 
        "file_path": generate_presigned_url(s3_url) if s3_url.startswith("s3://") else s3_url
    }


@router.post("/register-merchant")
def register_merchant(
    request: MerchantRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Removed num_books < 20 constraint to allow new merchants to start from zero.

    # Check if already a merchant
    existing = db.query(MerchantProfile).filter(MerchantProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Merchant profile already exists")

    merchant = MerchantProfile(
        user_id=current_user.id,
        merchant_name=request.merchant_name,
        library_name=request.library_name,
        num_books=request.num_books
    )
    db.add(merchant)

    # Update user role and name
    user = db.query(User).filter(User.id == current_user.id).first()
    user.role = "merchant"
    user.name = request.merchant_name
    db.commit()

    # Return new tokens with updated role
    access_token = create_access_token({"user_id": user.id, "email": user.email})
    refresh_token = create_refresh_token({"user_id": user.id, "email": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": "merchant"
    }
