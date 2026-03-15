# BookWorm Backend

A FastAPI-based backend for the BookWorm e-book marketplace — supporting user auth (OTP + password), book management, purchases, rentals, reviews, and merchant workflows.

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL (via SQLAlchemy)
- **Cache**: Redis (OTP storage with auto-expiry)
- **Storage**: AWS S3 (book covers, profile pictures)
- **Email**: Gmail SMTP (OTP delivery)
- **Auth**: JWT (access + refresh tokens)
- **Deploy**: Docker + Docker Compose

## Project Structure

```
backend/
├── auth/auth.py          # Authentication (OTP, login, register)
├── admin.py              # Admin endpoints
├── admin_dependency.py   # Admin role check
├── books.py              # Book CRUD, search, categories
├── library.py            # User library (purchases, rentals)
├── notifications.py      # Push notifications
├── models.py             # SQLAlchemy models
├── schemas.py            # Pydantic schemas
├── database.py           # DB connection
├── redis_client.py       # Redis connection
├── email_utils.py        # SMTP email sender
├── s3_utils.py           # S3 upload/presigned URLs
├── dependencies.py       # Auth dependencies
├── utils.py              # JWT, OTP helpers
├── main.py               # App entrypoint
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up .env (copy from .env.example)
cp .env.example .env
# Edit .env with your values

# Run
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/mobile

# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
OTP_EXPIRE_MINUTES=5

# Redis (optional, falls back to DB)
REDIS_URL=redis://localhost:6379/0

# AWS S3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-2
S3_BUCKET_NAME=book-covers-images

# SMTP (Gmail)
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_FROM=noreply@yourapp.com
```

## Docker Deployment

```bash
# Build and run backend + Redis
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/send-otp` | Send OTP to email |
| POST | `/auth/verify-otp` | Verify OTP & get tokens |
| POST | `/auth/login` | Login with email + password |
| POST | `/auth/set-password` | Set user password |
| GET | `/auth/me` | Get current user profile |
| PUT | `/auth/profile` | Update profile |
| POST | `/auth/profile/upload-photo` | Upload profile picture |
| POST | `/auth/register-merchant` | Register as merchant |
| GET | `/books/` | List/search books |
| POST | `/books/upload` | Upload a book (merchant) |
| GET | `/library/` | User's purchased/rented books |
| GET | `/notifications/` | User notifications |
| GET | `/health` | Health check |
