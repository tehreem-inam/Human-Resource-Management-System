from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from app.database import get_db
from app.models import Company , Role , User 
from app.auth.dependencies import AuthContext,  require_super_admin


router = APIRouter(prefix="/system/companies",
    tags=["System | Companies"])

class CompanyCreate(BaseModel):
    name: str
    email: EmailStr


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_active: bool
    is_deleted: bool
    has_owner: bool = False

    class Config:
        from_attributes = True

class CompanyStatusUpdate(BaseModel):
    is_active: bool
@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_super_admin)
):

        existing = await db.scalar(
            select(Company).where(
                Company.email == payload.email,
                Company.is_deleted == False
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company with this email already exists"
            )

        company = Company(
            name=payload.name,
            email=payload.email,
            is_active=True,
            is_deleted=False,
        )

        db.add(company)
        await db.flush() 

        roles = [
            Role(name="COMPANY_OWNER", company_id=company.id),
            Role(name="HR", company_id=company.id),
            Role(name="EMPLOYEE", company_id=company.id),
        ]
        db.add_all(roles)

    # commit happens automatically here
        await db.commit()
        await db.refresh(company)
        return company


#-------------------list companies endpoint-------------------#
@router.get("/", response_model=List[CompanyResponse])
async def list_companies(
    db : AsyncSession = Depends(get_db),
    _: AuthContext = Depends(require_super_admin),
):
    stmt = select(Company).where(Company.is_deleted == False)
    result = await db.execute(stmt)
    companies = result.scalars().all()
    return companies
#-------------------get company by id endpoint-------------------#
@router.get(
    "/{company_id}",
    response_model=CompanyResponse
)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    _: AuthContext = Depends(require_super_admin),
):
    stmt = select(Company).where(
        Company.id == company_id,
        Company.is_deleted == False
    )

    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    owner_exists = await db.scalar(
        select(User.id)
        .join(Role, User.role_id == Role.id)
        .where(
            User.company_id == company.id,
            Role.company_id == company.id,
            Role.name == "COMPANY_OWNER"
        )
    )

    return CompanyResponse(
        id=company.id,
        name=company.name,
        email=company.email,
        is_active=company.is_active,
        is_deleted=company.is_deleted,
        has_owner=owner_exists is not None
    )
#-------------------update company endpoint-------------------#
@router.patch(
    "/{company_id}",
    response_model=CompanyResponse
)
async def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    _: AuthContext = Depends(require_super_admin),
):
    stmt = select(Company).where(
        Company.id == company_id,
        Company.is_deleted == False
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if payload.name is not None:
        company.name = payload.name
    if payload.email is not None:
        company.email = payload.email

    await db.commit()
    await db.refresh(company)

    return company

#---------------enable/disable company endpoint---------------#
@router.patch(
    "/{company_id}/status",
    response_model=CompanyResponse
)
async def change_company_status(
    company_id: int,
    payload: CompanyStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: AuthContext = Depends(require_super_admin),
):
    stmt = select(Company).where(
        Company.id == company_id,
        Company.is_deleted == False
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.is_active = payload.is_active
    await db.commit()
    await db.refresh(company)

    return company


#-------------------soft delete company endpoint-------------------#
@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def soft_delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    _: AuthContext = Depends(require_super_admin),
):
    stmt = select(Company).where(
        Company.id == company_id,
        Company.is_deleted == False
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.is_deleted = True
    company.is_active = False

    await db.commit()
