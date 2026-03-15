import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import dotenv

dotenv.load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "BookWorm")


def send_otp_email(to_email: str, otp: str):
    """Send OTP verification email via Gmail SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[DEV MODE] SMTP not configured. OTP for {to_email}: {otp}")
        return False

    subject = "Your BookWorm Verification Code"
    
    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #FFFBF0; padding: 40px 30px; border-radius: 16px;">
        <h1 style="color: #2D3250; font-size: 28px; margin-bottom: 8px; text-align: center;">BookWorm</h1>
        <p style="color: #888; text-align: center; margin-bottom: 30px;">Verification Code</p>
        <div style="background: #2D3250; border-radius: 12px; padding: 30px; text-align: center; margin-bottom: 25px;">
            <p style="color: rgba(255,255,255,0.7); font-size: 14px; margin: 0 0 10px 0;">Your OTP is</p>
            <h2 style="color: #F5A623; font-size: 36px; letter-spacing: 8px; margin: 0; font-weight: 900;">{otp}</h2>
        </div>
        <p style="color: #666; font-size: 13px; text-align: center;">This code expires in 5 minutes. Do not share it with anyone.</p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email

    # Plain text fallback
    plain_body = f"Your BookWorm verification code is: {otp}\n\nThis code expires in 5 minutes."
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP to {to_email}: {e}")
        return False
