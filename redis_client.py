import os
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "")

redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print("[REDIS] Connected successfully")
    except Exception as e:
        print(f"[REDIS] Failed: {e}. Falling back to DB.")
        redis_client = None
else:
    print("[REDIS] No REDIS_URL configured. Using DB for OTP storage.")
