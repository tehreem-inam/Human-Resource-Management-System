from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Role, Employee 
from app.auth.dependencies import require_company_owner, generate_employee_code
from app.auth.security import get_password_hash
from app.dto.auth_employee import HRCreate , EmployeeStatusUpdate

router = APIRouter(
    prefix="/companies/hr-managers",
    tags=["Company • HR Managers"]
)




@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_hr_manager(
    payload: HRCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_company_owner),
):
    """
    Create a new HR Manager for the company of the authenticated Company Owner.
    """

    company_id = current_user.company_id

  
    role = await db.scalar(
        select(Role).where(Role.name == "HR", Role.company_id == company_id)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HR role is not configured for this company"
        )

    existing_user = await db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists"
        )
        
    try:
        # create user
        user = User(
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            role_id=role.id,
            company_id=company_id,
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(user)
        await db.flush()  # flush to get user.id

        # create employee profile
        employee = Employee(
            user_id=user.id,
            company_id=company_id,
            employee_code=generate_employee_code(),  # auto-generate
            first_name="HR Manager",                  # default name
            joining_date=datetime.now(timezone.utc).date(),
            status="active"
        )
        db.add(employee)

        await db.commit()
        await db.refresh(user)

    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Database integrity error: {str(e.orig)}"
        )

    return {
        "message": "HR Manager created successfully",
        "hr_manager_id": user.id,
        "email": user.email
    }

#-----------------list all hr managers-----------------#
@router.get("/", status_code=status.HTTP_200_OK)
async def list_hr_managers(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_company_owner),
):
    company_id = current_user.company_id

    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.user))  #  eager load

        .join(User, Employee.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .where(
            Employee.company_id == company_id,
            Role.name == "HR",
            # User.is_deleted == False
        )
        .order_by(Employee.joining_date.desc())
    )

    hr_employees = result.scalars().all()

    return {
        "count": len(hr_employees),
        "items": [
            {
                "employee_id": e.id,
                "user_id": e.user_id,
                "employee_code": e.employee_code,
                "email": e.user.email,
                "first_name": e.first_name,
                "status": e.status,
                "joining_date": e.joining_date
            }
            for e in hr_employees
        ]
    }


#------------------get hr manager by id-----------------#
@router.get("/{employee_id}", status_code=status.HTTP_200_OK)
async def get_hr_manager(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_company_owner),
):
    company_id = current_user.company_id

    employee = await db.scalar(
        select(Employee)
        .options(selectinload(Employee.user)) 
        .join(User)
        .join(Role)
        .where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Role.name == "HR",
            # User.is_deleted == False
        )
    )

    if not employee:
        raise HTTPException(404, "HR Manager not found")

    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "email": employee.user.email,
        "first_name": employee.first_name,
        "status": employee.status,
        "joining_date": employee.joining_date
    }

#------------------update hr manager status-----------------#


@router.patch(
    "/{employee_id}/status",
    status_code=status.HTTP_200_OK
)
async def update_hr_manager_status(
    employee_id: int,
    payload: EmployeeStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_company_owner),
):
    """
    Update HR Manager lifecycle status.
    This is the ONLY API controlling HR enable/disable/soft-delete.
    """

    company_id = current_user.company_id

    # Fetch employee with company isolation
    employee = await db.scalar(
    select(Employee)
    .join(User, Employee.user_id == User.id)
    .join(Role, User.role_id == Role.id)
    .options(
        selectinload(Employee.user).selectinload(User.role)
    )
    .where(
        Employee.id == employee_id,
        Employee.company_id == company_id,
        Role.name == "HR"
    )
)

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HR Manager not found"
        )

    if employee.user.role.name != "HR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target employee is not an HR Manager"
        )

    # Prevent invalid state transitions
    if employee.status == "terminated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminated HR Manager cannot be modified"
        )

    if employee.status == payload.status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"HR Manager is already '{payload.status}'"
        )

    #  Update status
    employee.status = payload.status
    employee.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()
    await db.refresh(employee)

    return {
        "message": "HR Manager status updated successfully",
        "employee_id": employee.id,
        "new_status": employee.status
    }
