from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from jose import JWTError, ExpiredSignatureError


from app.database import get_db
from app.models import User
from app.auth.security import decode_token

security = HTTPBearer()


# ======================
# AUTH CONTEXT
# ======================

class AuthContext(BaseModel):
    user_id: int
    company_id: Optional[int]
    role: str
    employee_id: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


# ======================
# TOKEN VALIDATION
# ======================

def validate_token(token: str) -> dict:
    payload = decode_token(token)

    # ---- Token type check (important for refresh tokens later)
    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    exp = payload.get("exp")
    if not exp:
        raise HTTPException(401, "Token missing expiration")

    if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(401, "Token expired")

    if not payload.get("sub"):
        raise HTTPException(401, "Invalid token subject")

    return payload


# ======================
# CURRENT USER
# ======================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    token = credentials.credentials

    try:
        payload = validate_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token. Authentication failed.",
        )

    user_id = int(payload.get("sub"))
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user information."
        )

    stmt = select(User).options(
        selectinload(User.role),
        selectinload(User.employee)
    ).where(User.id == user_id)

    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account disabled")

    if not user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role is invalid")

    if user.role.name != "SUPER_ADMIN" and not user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a company"
        )

    return AuthContext(
        user_id=user.id,
        company_id=user.company_id,
        role=user.role.name,
        employee_id=user.employee.id if user.employee else None,
        is_active=user.is_active,
    )

# ======================
# ROLE GUARDS (GENERIC)
# ======================

def require_roles(allowed_roles: List[str]):
    def role_checker(user: AuthContext = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        return user
    return role_checker


# ======================
# COMMON ROLE DEPENDENCIES
# ======================

require_super_admin = require_roles(["SUPER_ADMIN"])
require_hr = require_roles(["HR"])
require_company_owner = require_roles(["COMPANY_OWNER"])
require_employee = require_roles(["EMPLOYEE"])
require_hr_or_company_owner = require_roles(["HR", "COMPANY_OWNER"])


import random, string

def generate_employee_code():
    return "EMP-" + "".join(random.choices(string.digits, k=4))
