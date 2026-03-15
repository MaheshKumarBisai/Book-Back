import os
import dotenv
import random
from datetime import datetime, timedelta
from jose import jwt

dotenv.load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", 24))
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", 5))

def generate_otp():
    return str(random.randint(100000, 999999))

def otp_expiry():
    return datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

def create_access_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload["type"] = "access"
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload["type"] = "refresh"
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
