from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
import jwt
from core.config import settings

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
import os
import aiohttp
import json
import asyncio
from schemas.reservations import UserInfo

security = HTTPBearer()

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:7001").rstrip("/")
# Optional internal/Docker DNS (e.g., http://user-management:7001)
AUTH_SERVICE_INTERNAL_URL = os.getenv("AUTH_SERVICE_INTERNAL_URL", "").rstrip("/")
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "false").lower() == "true"
# Add your docker-compose service DNS here if you have it:
DEFAULT_DOCKER_SERVICE = "http://user-management:7001"

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
# @dataclass
# class UserInfo:
#     user_id: str
#     role: str
#     token: str
#     firstName: str
#     lastName: str

# def get_db():
#     db = database.SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


def verify_token(token: str ):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        uuid: str = payload.get("sub")
        if uuid is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return uuid
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
# -----------------------------------------------------------------------------
# URL candidates
# -----------------------------------------------------------------------------
def _candidate_urls(path: str) -> List[str]:
    """Build a list of candidate base URLs with the given path appended."""
    bases = [
        AUTH_SERVICE_URL,
        AUTH_SERVICE_INTERNAL_URL,
        DEFAULT_DOCKER_SERVICE,
        "http://host.docker.internal:7001",  # Works on Docker Desktop
        "http://127.0.0.1:7001",             # Only works if service is on the same host namespace
        "http://localhost:7001",
    ]
    return [f"{b}{path}" for b in bases if b]

# -----------------------------------------------------------------------------
# HTTP helpers
# -----------------------------------------------------------------------------
async def _request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    timeout_sec: float = 10.0,
) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    """Make an HTTP request and return (status, text, json_or_none) without double-reading."""
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        req = session.post if method.upper() == "POST" else session.get
        async with req(url, headers=headers, json=payload) as resp:
            text = await resp.text()
            data: Optional[Dict[str, Any]] = None
            # Parse JSON leniently (even if server Content-Type is wrong)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = None
            return resp.status, text, data

    
# -----------------------------------------------------------------------------
# Auth service calls
# -----------------------------------------------------------------------------
async def fetch_user_info(path: str, token: str) -> UserInfo:
    headers = {"Authorization": f"Bearer {token}"}
    for url in _candidate_urls(path):
        try:
            status, _text, data = await _request_json("GET", url, headers=headers, timeout_sec=10)
            if status == 200 and isinstance(data, dict):
                user_id = str(data.get("id", "")).strip()
                role = str(data.get("role", "")).strip()
                if not user_id or not role:
                    raise HTTPException(status_code=502, detail="Malformed user info from auth service")
                return UserInfo(
                    user_id=user_id, 
                    role=role, 
                    token=token, 
                    first_name=data.get("first_name", "NaN"), 
                    last_name=data.get("last_name", "NaN"))

            if status == 401:
                raise HTTPException(status_code=401, detail="Invalid or expired token")

            # Non-200/401: try next candidate
            continue

        except (aiohttp.ClientError, asyncio.TimeoutError):
            continue
        except HTTPException:
            raise
        except Exception:
            continue

    if BYPASS_AUTH:
        return UserInfo(user_id="dev-user", role="organizer", token=token)


    raise HTTPException(status_code=503, detail="Authentication service is currently unavailable or request user not found")

async def get_user_from_id(id: str, token: str) -> UserInfo:
    userInfo = await fetch_user_info(f"/users/info/{id}", token)
    return userInfo

async def get_user_from_token(token: str) -> UserInfo:
    userInfo = await fetch_user_info("/users/info", token)
    return userInfo