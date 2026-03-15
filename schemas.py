from pydantic import BaseModel, EmailStr

class EmailRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserProfileUpdate(BaseModel):
    name: str
    phone: str
    address: str

class SetPasswordRequest(BaseModel):
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MerchantRegisterRequest(BaseModel):
    merchant_name: str
    library_name: str
    num_books: int
