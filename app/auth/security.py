
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
import os

from app.settings import settings

SECRET_KEY = settings.JWT_SECRET_KEY or os.getenv("JWT_SECRET_KEY", "change-me-in-prod")
ALGORITHM = settings.JWT_ALGORITHM or "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES or 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)



def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "typ": "access",
    })

    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise
