# BookWorm Backend

FastAPI backend for the BookWorm e-book marketplace — user auth (OTP + password), book management, purchases, rentals, reviews, and merchant workflows.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL (SQLAlchemy) |
| Cache | Redis (OTP storage) |
| Storage | AWS S3 |
| Email | Gmail SMTP |
| Auth | JWT (access + refresh tokens) |
| Deploy | Docker + Docker Compose |

## Project Structure

```
backend/
├── auth/auth.py          # Auth (OTP, login, register, merchant)
├── admin.py              # Admin endpoints
├── admin_dependency.py   # Admin role check
├── books.py              # Book CRUD, search, categories
├── library.py            # User library (purchases, rentals)
├── notifications.py      # Notifications
├── models.py             # SQLAlchemy models
├── schemas.py            # Pydantic schemas
├── database.py           # DB connection
├── redis_client.py       # Redis connection
├── email_utils.py        # SMTP email sender
├── s3_utils.py           # S3 upload / presigned URLs
├── dependencies.py       # Auth dependencies
├── utils.py              # JWT, OTP helpers
├── main.py               # App entrypoint
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/send-otp` | Send OTP to email |
| POST | `/auth/verify-otp` | Verify OTP & get tokens |
| POST | `/auth/login` | Login with email + password |
| POST | `/auth/set-password` | Set user password |
| GET | `/auth/me` | Get current user |
| PUT | `/auth/profile` | Update profile |
| POST | `/auth/profile/upload-photo` | Upload profile picture |
| POST | `/auth/register-merchant` | Register as merchant |
| GET | `/books/` | List / search books |
| POST | `/books/upload` | Upload a book (merchant) |
| GET | `/library/` | User's purchases & rentals |
| GET | `/notifications/` | User notifications |

---

## Local Development Setup

```bash
# 1. Clone
git clone https://github.com/MaheshKumarBisai/Book-Back.git
cd Book-Back

# 2. Virtual env
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# 3. Install deps
pip install -r requirements.txt

# 4. Configure env
cp .env.example .env
# Edit .env with your values

# 5. Run
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs → http://localhost:8000/docs

---

## AWS Production Deployment (from scratch)

### Architecture

```
Internet → ALB (public subnet, port 80/443)
              → EC2 (private subnet, SSM access)
                  → Docker Compose
                      ├── Backend container (:8000)
                      └── Redis container (:6379)
                  → RDS PostgreSQL (:5432)
                  → S3 (book-covers-images)
```

---

### Step 1 — VPC & Networking

**AWS Console → VPC → Create VPC → "VPC and more"**

| Setting | Value |
|---|---|
| Name | `bookworm-vpc` |
| CIDR | `10.0.0.0/16` |
| AZs | 2 |
| Public subnets | 2 (`10.0.1.0/24`, `10.0.2.0/24`) |
| Private subnets | 2 (`10.0.3.0/24`, `10.0.4.0/24`) |
| NAT Gateway | 1 in 1 AZ |
| VPC Endpoints | S3 Gateway |

**Security Groups:**

| SG Name | Port | Source |
|---|---|---|
| `bookworm-alb-sg` | 80, 443 in | `0.0.0.0/0` |
| `bookworm-ec2-sg` | 8000 in | `bookworm-alb-sg` |
| `bookworm-ec2-sg` | 443 in | VPC CIDR (SSM) |
| `bookworm-rds-sg` | 5432 in | `bookworm-ec2-sg` |

> Redis runs inside Docker on EC2, so no separate SG needed.

---

### Step 2 — RDS PostgreSQL

**AWS Console → RDS → Create database**

| Setting | Value |
|---|---|
| Engine | PostgreSQL 15 |
| Template | Free tier |
| Instance ID | `bookworm-db` |
| Username | `postgres` |
| Instance | `db.t3.micro` |
| Storage | 20 GB gp3 |
| VPC | `bookworm-vpc` |
| Subnet group | Private subnets |
| Public access | **No** |
| SG | `bookworm-rds-sg` |
| Initial DB | `mobile` |

> Tables are auto-created by SQLAlchemy on first start. Fresh, clean schema.

---

### Step 3 — EC2 Instance

**3a. IAM Role** → `bookworm-ec2-role` with:
- `AmazonSSMManagedInstanceCore`
- `AmazonS3FullAccess`

**3b. Launch Instance**

| Setting | Value |
|---|---|
| AMI | Amazon Linux 2023 |
| Type | `t3.micro` or `t3.small` |
| Key pair | None (using SSM) |
| Subnet | Private |
| Public IP | Disabled |
| SG | `bookworm-ec2-sg` |
| IAM profile | `bookworm-ec2-role` |
| Storage | 20 GB gp3 |

**3c. Connect via SSM (optional)**

```bash
aws ssm start-session --target i-0xxxxxxxxxxxx --region us-east-2
```

**3d. Install Docker & Git**

```bash
sudo yum update -y
sudo yum install -y docker git

sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ssm-user

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Re-login for docker group
exit
# Reconnect via SSM
```

---

### Step 4 — Deploy

```bash
# Clone repo
cd /home/ssm-user
git clone https://github.com/MaheshKumarBisai/Book-Back.git
cd Book-Back

# Create .env
cat > .env << 'EOF'
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@bookworm-db.xxxx.us-east-2.rds.amazonaws.com:5432/mobile
SECRET_KEY=CHANGE_THIS_TO_RANDOM_STRING
ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
OTP_EXPIRE_MINUTES=5
REDIS_URL=redis://redis:6379/0
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-2
S3_BUCKET_NAME=book-covers-images
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_FROM=noreply@yourapp.com
EOF

# Build & run
docker-compose up -d --build

# Verify
docker-compose ps
docker-compose logs -f backend
curl http://localhost:8000/health
```

> **Important:** In the `.env`, `REDIS_URL=redis://redis:6379/0` uses the Docker service name `redis`, not `localhost`.

---

### Step 5 — Application Load Balancer

**5a. Target Group** (`bookworm-tg`)

| Setting | Value |
|---|---|
| Type | Instances |
| Protocol/Port | HTTP / 8000 |
| Health check | `/health` |

Register your EC2 on port 8000.

**5b. Create ALB** (`bookworm-alb`)

| Setting | Value |
|---|---|
| Scheme | Internet-facing |
| Subnets | Both public subnets |
| SG | `bookworm-alb-sg` |
| Listener | HTTP:80 → `bookworm-tg` |

For HTTPS: Get a free cert from **ACM**, add HTTPS:443 listener, redirect HTTP:80 → HTTPS.

**5c. Update Frontend** `Config.js`:
```javascript
const API_URL = "http://bookworm-alb-xxxx.us-east-2.elb.amazonaws.com";
```

---

### Redeploy After Code Changes

```bash
cd /home/ssm-user/Book-Back
git pull origin main
docker-compose up -d --build
docker-compose logs -f backend
```

---

### Useful Commands

```bash
# Logs
docker-compose logs -f backend

# Restart
docker-compose restart backend

# Redis CLI
docker exec bookworm-redis redis-cli PING

# Connect to RDS
sudo yum install -y postgresql15
psql -h bookworm-db.xxxx.rds.amazonaws.com -U postgres -d mobile
```

---

