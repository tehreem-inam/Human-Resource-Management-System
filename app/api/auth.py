from fastapi import APIRouter , Depends , HTTPException , status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime 


from app.database import get_db
from app.models import User 
from app.auth.dependencies import get_current_user 
from app.auth.security import  verify_password  , create_access_token 
from app.dto.auth_employee import TokenResponse , UserLogin , UserProfileResponse

router = APIRouter(prefix="/auth",
    tags=["Authentication"])

#------------------------login endpoint------------------------#
@router.post("/login",response_model=TokenResponse)
async def login_user(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Password too long"
    )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
        
    #update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    
    token = create_access_token(
    data={"sub": str(user.id)}
)
    
    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
       
    }
    
    # -------------------------me endpoint------------------------#
@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.company)
        )
        .where(User.id == current.user_id)
    )

    user = result.scalar_one_or_none()

    if not user:
        return {
            "success": False,
            "message": "User not found.",
            "data": None
        }

    company = None

    if user.company:
        company = {
            "id": user.company.id,
            "name": user.company.name
        }

    return {
        "success": True,
        "message": "User profile fetched successfully.",
        "data": {
            "id": user.id,
            "email": user.email,
            "role": {
                "id": user.role.id,
                "name": user.role.name
            },
            "company": company
        }
    }