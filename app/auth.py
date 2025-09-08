from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from fastapi.responses import Response
import jwt

from .config import SECRET_KEY, ACCESS_TOKEN_EXPIRE_MIN, COOKIE_NAME, COOKIE_SECURE

ALGO = "HS256"

def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MIN)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)

def set_token_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MIN * 60,
    )

def clear_token_cookie(resp: Response):
    resp.delete_cookie(COOKIE_NAME, path="/")

def current_user_id(request: Request) -> int:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        return int(payload.get("sub", "0"))
    except Exception:
        raise HTTPException(401, "Invalid token")
