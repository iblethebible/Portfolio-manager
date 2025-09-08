import os
from dotenv import load_dotenv

load_dotenv()  # loads values from .env into process env

def _to_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}

# --- Database / Core ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://pm_user:pm_pass_123@127.0.0.1:3306/portfolio",
)
BASE_CCY = os.getenv("BASE_CCY", "GBP").upper().strip()
PRICE_POLL_MINUTES = int(os.getenv("PRICE_POLL_MINUTES", "5"))

# --- Auth / Security ---
# Use a long random string in your real .env (e.g. secrets.token_hex(32))
SECRET_KEY = os.getenv("SECRET_KEY", "change_me_now")  # DO NOT commit real secrets
ACCESS_TOKEN_EXPIRE_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MIN", "10080"))  # 7 days
COOKIE_NAME = os.getenv("COOKIE_NAME", "opm_token").strip()
COOKIE_SECURE = _to_bool(os.getenv("COOKIE_SECURE"), False)  # set True behind HTTPS

# (optional) quick sanity print — comment out in production
# print(">>> Using DATABASE_URL:", DATABASE_URL)
# print(">>> BASE_CCY:", BASE_CCY, "| COOKIE_SECURE:", COOKIE_SECURE)
