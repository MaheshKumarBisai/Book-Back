from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import Base, engine
from auth.auth import router as auth_router
from books import router as books_router
from library import router as library_router
from admin import router as admin_router
from notifications import router as notifications_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth_router)
app.include_router(books_router)
app.include_router(library_router)
app.include_router(admin_router)
app.include_router(notifications_router)

# Mount the profile directory
import os
if not os.path.exists("profile"):
    os.makedirs("profile")
app.mount("/profile", StaticFiles(directory="profile"), name="profile")
Base.metadata.create_all(bind=engine)