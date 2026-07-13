from fastapi import APIRouter, Depends, HTTPException, status , Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select , func
from typing import Optional
from app.database import get_db
from app.models import Department , Employee
from app.dto.department import DepartmentCreate , DepartmentUpdate , DepartmentStatusUpdate , DepartmentHeadAssign
from app.auth.dependencies import require_hr , require_hr_or_company_owner

router = APIRouter(
    prefix="/companies/departments",
    tags=["Company • Departments"]
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    """
    Create a department for the authenticated HR's company.
    """

    company_id = current_user.company_id

    # Check for duplicate department name (company-scoped)
    existing = await db.scalar(
        select(Department).where(
            Department.company_id == company_id,
            Department.name.ilike(payload.name),
            # Department.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department with this name already exists"
        )

    #  Create department
    department = Department(
        company_id=company_id,
        name=payload.name.strip(),
        description=payload.description,
        is_active=True,
    )

    db.add(department)
    await db.commit()
    await db.refresh(department)

    return {
        "message": "Department created successfully",
        "department": {
            "id": department.id,
            "name": department.name,
            "description": department.description,
            "is_active": department.is_active,
        }
    }
    
    
#------------------list departments endpoint ------------------#


@router.get("")
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),

    search: Optional[str] = Query(None, min_length=1),
    is_active: Optional[bool] = Query(None, regex="^(active|inactive)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    """
    List all departments of the authenticated user's company.
    Supports pagination, search, and status filtering.
    """

    company_id = current_user.company_id
    offset = (page - 1) * limit

    #  Base filters (company + not deleted)
    filters = [
        Department.company_id == company_id,
        # Department.deleted_at.is_(None)
    ]

    if is_active:
        filters.append(Department.is_active == is_active)

    if search:
        filters.append(Department.name.ilike(f"%{search.strip()}%"))

    # Total count (for pagination)
    total = await db.scalar(
        select(func.count(Department.id)).where(*filters)
    )

    #  Fetch paginated data
    result = await db.execute(
        select(Department)
        .where(*filters)
        .offset(offset)
        .limit(limit)
    )
    departments = result.scalars().all()

    return {
        "data": [
            {
                "id": dept.id,
                "name": dept.name,
                "description": dept.description,
                "is_active": dept.is_active,
            }
            for dept in departments
        ],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "has_next": offset + limit < total,
            "has_prev": page > 1
        }
    }
    
#------------------get department by id endpoint ------------------#
@router.get("/{department_id}")
async def get_department_details(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),
):
    company_id = current_user.company_id

    department = await db.scalar(
        select(Department)
        .where(
            Department.id == department_id,
            Department.company_id == company_id,
        )
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    return {
        "id": department.id,
        "name": department.name,
        "description": department.description,
        "is_active": department.is_active,
        "head_employee_id": department.head_employee_id,
    }


#---------------------- update department endpoint --------------------#
@router.patch("/{department_id}")
async def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    company_id = current_user.company_id

    department = await db.scalar(
        select(Department)
        .where(
            Department.id == department_id,
            Department.company_id == company_id,
        )
    )

    if not department:
        raise HTTPException(404, "Department not found")

    # Name uniqueness check (if name is changing)
    if payload.name and payload.name.strip().lower() != department.name.lower():
        exists = await db.scalar(
            select(Department).where(
                Department.company_id == company_id,
                Department.name.ilike(payload.name.strip()),
                Department.id != department_id
            )
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Department with this name already exists"
            )
        department.name = payload.name.strip()

    if payload.description is not None:
        department.description = payload.description

    await db.commit()
    await db.refresh(department)

    return {
        "message": "Department updated successfully",
        "department_id": department.id
    }

#---------------------- update department status endpoint --------------------#
@router.patch("/{department_id}/status")
async def change_department_active_state(
    department_id: int,
    payload: DepartmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    department = await db.scalar(
        select(Department).where(
            Department.id == department_id,
            Department.company_id == current_user.company_id,
        )
    )

    if not department:
        raise HTTPException(404, "Department not found")

    department.is_active = payload.is_active

    await db.commit()

    return {
        "message": "Department state updated successfully",
        "is_active": department.is_active
    }

#---------------------- assign department head endpoint --------------------#
@router.patch("/{department_id}/head")
async def assign_department_head(
    department_id: int,
    payload: DepartmentHeadAssign,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr),
):
    company_id = current_user.company_id

    department = await db.scalar(
        select(Department)
        .where(
            Department.id == department_id,
            Department.company_id == company_id,
        )
    )
    if not department:
        raise HTTPException(404, "Department not found")

    employee = await db.scalar(
        select(Employee)
        .where(
            Employee.id == payload.employee_id,
            Employee.company_id == company_id,
            Employee.status == "active"
        )
    )
    if not employee:
        raise HTTPException(
            status_code=400,
            detail="Employee not found or inactive"
        )

    department.head_employee_id = employee.id

    await db.commit()

    return {
        "message": "Department head assigned successfully",
        "department_id": department.id,
        "head_employee_id": employee.id
    }
