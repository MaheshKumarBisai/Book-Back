from fastapi import Depends, HTTPException
from dependencies import get_current_user

def admin_only(user = Depends(get_current_user)):
    if user.role not in ["admin", "merchant"]:
        raise HTTPException(status_code=403, detail="Admin or Merchant access required")
    return user
