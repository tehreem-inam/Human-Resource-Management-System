
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models import Designation, Department
from app.dto.designation import DesignationCreate , DesignationUpdateDTO
from app.auth.dependencies import require_hr

router = APIRouter(
    prefix="/companies/designations",
    tags=["Company | Designations"]
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_designation(
    payload: DesignationCreate,
    
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    """
    Create a new designation under a department.
    Company ownership is derived via department.
    """

    #  Fetch & validate department
    department = await db.scalar(
        select(Department).where(
            Department.id == payload.department_id,
            Department.is_active.is_(True)
        )
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found or inactive"
        )

    #Enforce company boundary
    if department.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to create designations for this department"
        )

    #  Check duplicate designation (department-scoped)
    existing_designation = await db.scalar(
        select(Designation).where(
            Designation.department_id == payload.department_id,
            Designation.title.ilike(payload.title.strip()),
            Designation.deleted_at.is_(None)
        )
    )

    if existing_designation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Designation with this title already exists in this department"
        )

    #  Create designation
    designation = Designation(
        department_id=payload.department_id,
        title=payload.title.strip(),
        description=payload.description,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )

    db.add(designation)
    await db.commit()
    await db.refresh(designation)

    return {
        "message": "Designation created successfully",
        "designation": {
            "id": designation.id,
            "title": designation.title,
            "department_id": designation.department_id,
            "is_active": designation.is_active
        }
    }


#------------- get designation------------#
@router.get("", status_code=status.HTTP_200_OK)
async def list_designations(
    department_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    """
    List all designations for the current company.
    Optional filter by department.
    """

    query = (
        select(Designation)
        .join(Department)
        .where(
            Department.company_id == current_user.company_id,
            Designation.deleted_at.is_(None)
        )
        .order_by(Designation.created_at.desc())
    )

    if department_id:
        query = query.where(Designation.department_id == department_id)

    result = await db.execute(query)
    designations = result.scalars().all()

    return {
        "total": len(designations),
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "department_id": d.department_id,
                "is_active": d.is_active,
                "created_at": d.created_at,
            }
            for d in designations
        ]
    }

#------------------update designation endpoint ------------------#
@router.patch("/{designation_id}", status_code=status.HTTP_200_OK)
async def update_designation(
    designation_id: int,
    payload: DesignationUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    """
    Update designation details.
    """

    designation = await db.scalar(
        select(Designation)
        .join(Department)
        .where(
            Designation.id == designation_id,
            Designation.deleted_at.is_(None),
            Department.company_id == current_user.company_id
        )
    )

    if not designation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Designation not found"
        )

    # Duplicate title check (if title is changing)
    if payload.title:
        duplicate = await db.scalar(
            select(Designation).where(
                Designation.department_id == designation.department_id,
                Designation.title.ilike(payload.title.strip()),
                Designation.id != designation.id,
                Designation.deleted_at.is_(None)
            )
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Designation with this title already exists in the department"
            )
        designation.title = payload.title.strip()



    await db.commit()
    await db.refresh(designation)

    return {
        "message": "Designation updated successfully",
        "designation_id": designation.id
    }
