from fastapi import APIRouter , Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User , Role , Company 
from app.auth.dependencies import require_super_admin
from app.auth.security import get_password_hash
from app.dto.auth_employee import UserCreate


router = APIRouter(prefix="/system/companies",
    tags=["System | Company Owners"])

@router.post("/{company_id}/owners", status_code=status.HTTP_201_CREATED)
async def create_company_owner(
    company_id: int,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_super_admin)
):
    #validate company
    company = await db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.is_deleted == False
        )
    )
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
        
    #ensure no existing owner
    existing_owner = await db.scalar(
        select(User).join(Role).where(
            User.company_id == company_id,
            Role.name == "COMPANY_OWNER",
        )
    )
    
    if existing_owner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company owner already exists"
        )
        
    #fetch company owner role
    role = await db.scalar(
        select(Role).where(Role.name == "COMPANY_OWNER",
                           Role.company_id == company_id)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400,
            detail="COMPANY_OWNER role not found for this company"
        )
        
    #create owner user
    owner = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role_id=role.id,
        is_active=True,
        company_id=company_id,
       
        # created_at=datetime.now(timezone.utc)
    )
    db.add(owner)
    await db.commit()
    return {
        "message": "Company owner created successfully",
        "company_id": company_id,
        "owner_user_id": owner.id
    }
