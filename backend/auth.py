"""JWT + bcrypt authentication logic."""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from database import get_db_pool
import aiomysql

JWT_SECRET = os.getenv("JWT_SECRET", "mysecret123")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)


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
    clean_token = token.strip("'\" \t\r\n")
    try:
        payload = jwt.decode(clean_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """FastAPI dependency that returns the current authenticated user dict."""
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials.strip("'\" \t\r\n")
    
    if not raw_token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            raw_token = cookie_token.strip("'\" \t\r\n")

    if not raw_token or raw_token in ("demo-token", "", "null", "undefined"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_token(raw_token)
    except HTTPException as e:
        raise e

    username = payload.get("sub") or payload.get("username") or payload.get("user")
    user_id = payload.get("id")
    token_role = payload.get("role")

    user = None
    try:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    if username:
                        await cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                        user = await cur.fetchone()
                    elif user_id:
                        await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                        user = await cur.fetchone()
    except Exception:
        pass

    if not user:
        if not username or not token_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session identity",
            )
        user = {
            "id": user_id or 1,
            "username": username,
            "role": token_role,
        }

    user["_id"] = user.get("id", 1)
    return user


async def require_authenticated_user(user: dict = Depends(get_current_user)) -> dict:
    return user


async def require_instructor(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("instructor", "operator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor role required",
        )
    return user


async def require_student(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("student", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student role required",
        )
    return user

