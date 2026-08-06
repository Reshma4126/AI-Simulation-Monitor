"""JWT + bcrypt authentication logic."""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from database import get_db_pool
import aiomysql

JWT_SECRET = os.getenv("JWT_SECRET", "mysecret123")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and return payload. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency that returns the current user dict."""
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = await cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # ensure returned dict behaves like MongoDB document (with id)
    user["_id"] = user["id"]
    return user


async def require_instructor(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "instructor":
        raise HTTPException(status_code=403, detail="Instructor role required")
    return user
