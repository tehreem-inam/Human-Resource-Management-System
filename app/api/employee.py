from fastapi import APIRouter, Depends, HTTPException, status 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload , aliased
from sqlalchemy import select , update
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.database import get_db
from app.models import User, Employee, Role , Department , Designation
from app.auth.dependencies import require_hr_or_company_owner , get_current_user
from app.auth.security import get_password_hash
from app.dto.employee import EmployeeCreate , EmployeeSelfProfileUpdate , EmployeeHRProfileUpdate , AssignDepartmentDTO , AssignDesignationDTO , AssignManagerDTO , EmployeeStatusUpdate
from app.auth.dependencies import generate_employee_code

router = APIRouter(
    prefix="/companies/employees",
    tags=["Company • Employees"]
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    Create a new employee under the authenticated user's company.
    """

    company_id = current_user.company_id

    #  Ensure EMPLOYEE role exists for company
    role = await db.scalar(
        select(Role).where(
            Role.name == "EMPLOYEE",
            Role.company_id == company_id
        )
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMPLOYEE role not configured for this company"
        )

    # Check email uniqueness
    existing_user = await db.scalar(
        select(User).where(User.email == payload.email)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists"
        )

    try:
        #  Create user
        user = User(
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            role_id=role.id,
            company_id=company_id,
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(user)
        await db.flush()  # get user.id

        # Create employee shell
        employee = Employee(
            user_id=user.id,
            company_id=company_id,
            employee_code=generate_employee_code(),
            first_name=payload.first_name,
            last_name=payload.last_name,
            status="active",
            joining_date=datetime.now(timezone.utc).date()
        )
        db.add(employee)

        await db.commit()
        await db.refresh(employee)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee creation failed due to data conflict"
        )

    return {
        "message": "Employee created successfully",
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "email": user.email
    }

@router.patch("/me/profile",)
async def update_my_profile(
    payload: EmployeeSelfProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Employee updates their own profile (self-service).
    """

    if not current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee profile not found"
        )

    employee = await db.get(Employee, current_user.employee_id)

    if not employee or employee.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive employee"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)

    return {"message": "Profile updated successfully"}

@router.patch("/{employee_id}/profile",)
async def update_employee_profile_by_hr(
    employee_id: int,
    payload: EmployeeHRProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    HR or Company Owner updates employee profile.
    """

    employee = await db.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == current_user.company_id
        )
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)

    return {"message": "Employee profile updated successfully"}

@router.get("/me",)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get authenticated employee profile.
    """

    if not current_user.employee_id:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    employee = await db.get(Employee, current_user.employee_id)

    return employee



@router.get("/", status_code=200)
async def get_all_employees(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    Manager = aliased(Employee)

    stmt = (
        select(
            Employee,
            Department,
            Designation,
            Manager
        )
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .outerjoin(Manager, Manager.id == Employee.manager_id)
        .where(Employee.company_id == current_user.company_id)
        .order_by(Employee.id.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    employees = []

    for employee, department, designation, manager in rows:
        employees.append({
            "id": employee.id,
            "employee_code": employee.employee_code,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "status": employee.status,

            "department": {
                "id": department.id,
                "name": department.name
            } if department else None,

            "designation": {
                "id": designation.id,
                "title": designation.title
            } if designation else None,

            "manager": {
                "id": manager.id,
                "employee_code": manager.employee_code,
                "first_name": manager.first_name,
                "last_name": manager.last_name
            } if manager else None,
        })

    return {
        "count": len(employees),
        "employees": employees
    }


@router.patch("/{employee_id}/status", status_code=status.HTTP_200_OK)
async def update_employee_status(
    employee_id: int,
    payload: EmployeeStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    Change employee employment status (enterprise lifecycle control).
    """

    company_id = current_user.company_id
    new_status = payload.status

    #  Fetch employee
    employee = await db.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == company_id
        )
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    current_status = employee.status

    #  Prevent invalid transitions
    if current_status == "terminated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terminated employee status cannot be changed"
        )

    # No-op protection
    if current_status == new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee already has this status"
        )

    #  Handle TERMINATION (critical)
    if new_status == "terminated":
        # Remove this employee as manager from others
        await db.execute(
            update(Employee)
            .where(
                Employee.manager_id == employee.id,
                Employee.company_id == company_id
            )
            .values(manager_id=None)
        )

        # Disable user login
        await db.execute(
            update(User)
            .where(User.id == employee.user_id)
            .values(is_active=False)
        )

    #  Handle INACTIVE
    elif new_status == "inactive":
        await db.execute(
            update(User)
            .where(User.id == employee.user_id)
            .values(is_active=False)
        )

    #  Handle ACTIVE
    elif new_status == "active":
        await db.execute(
            update(User)
            .where(User.id == employee.user_id)
            .values(is_active=True)
        )

    employee.status = new_status

    await db.commit()
    await db.refresh(employee)

    return {
        "message": "Employee status updated successfully",
        "employee_id": employee.id,
        "previous_status": current_status,
        "current_status": employee.status
    }
    
@router.post("/{employee_id}/assign-department", response_model=dict)
async def assign_department(
    employee_id: int,
    payload: AssignDepartmentDTO,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    Assign a department to an employee.
    Only HR/Admin/SUPER_ADMIN can perform this.
    """



    # Fetch employee
    stmt = select(Employee).where(Employee.id == employee_id)
    result = await db.execute(stmt)
    employee: Employee | None = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    # Optional: Check if employee belongs to same company
    if current_user.role != "SUPER_ADMIN" and employee.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee does not belong to your company"
        )

    # Fetch department
    stmt = select(Department).where(Department.id == payload.department_id)
    result = await db.execute(stmt)
    department: Department | None = result.scalar_one_or_none()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )


    # Assign department
    employee.department_id = department.id
    db.add(employee)
    await db.commit()
    await db.refresh(employee)

    return {
        "employee_id": employee.id,
        "department_id": department.id,
        "department_name": department.name,
        "message": "Department assigned successfully."
    }
    


@router.post(
    "/{employee_id}/assign-designation",
    status_code=status.HTTP_200_OK
)
async def assign_designation(
    employee_id: int,
    payload: AssignDesignationDTO,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner)
):
    # Fetch employee
    result = await db.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    # Optional: Check if employee belongs to same company
    if current_user.role != "SUPER_ADMIN" and employee.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee does not belong to your company"
        )
    #  Employee must have department first
    if not employee.department_id:
        raise HTTPException(
            status_code=400,
            detail="Assign department before assigning designation"
        )

    # Fetch designation and validate company + department
    result = await db.execute(
        select(Designation).join(Department).where(
            Designation.id == payload.designation_id,
            Department.company_id == employee.company_id,
            Designation.department_id == employee.department_id
        )
    )
    designation = result.scalar_one_or_none()

    if not designation:
        raise HTTPException(
            status_code=404,
            detail="Designation does not belong to employee's department"
        )

    #  Assign designation
    employee.designation_id = designation.id

    await db.commit()
    await db.refresh(employee)

    return {
         "message": "Designation assigned successfully",
        "employee_id": employee.id,
        "department_id": employee.department_id,
        "designation_id": designation.id,
        "designation_title": designation.title,
    }


async def is_circular_manager(
    db: AsyncSession,
    employee_id: int,
    manager_id: int
) -> bool:
    """
    Returns True if assigning manager creates circular hierarchy
    """
    current_manager_id = manager_id

    while current_manager_id:
        if current_manager_id == employee_id:
            return True

        result = await db.execute(
            select(Employee.manager_id)
            .where(Employee.id == current_manager_id)
        )
        current_manager_id = result.scalar_one_or_none()

    return False

@router.post(
    "/{employee_id}/assign-manager",
    status_code=status.HTTP_200_OK,
)
async def assign_manager(
    employee_id: int,
    payload: AssignManagerDTO,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),
):
    #  Fetch employee
    employee = (
        await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
    ).scalar_one_or_none()

    if not employee:
        raise HTTPException(404, "Employee not found")
    if current_user.role != "SUPER_ADMIN" and employee.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee does not belong to your company"
        )
    manager = (
        await db.execute(
            select(Employee).where(Employee.id == payload.manager_id)
        )
    ).scalar_one_or_none()

    if not manager:
        raise HTTPException(404, "Manager not found")

    if employee.company_id != manager.company_id:
        raise HTTPException(
            403,
            "Manager must belong to the same company"
        )

    if not manager.status == "active":
        raise HTTPException(
            400,
            "Inactive employee cannot be assigned as manager"
        )

    if employee.id == manager.id:
        raise HTTPException(
            400,
            "Employee cannot be their own manager"
        )

    if employee.department_id and manager.department_id:
        if employee.department_id != manager.department_id:
            raise HTTPException(
                400,
                "Manager must be from the same department"
            )

    if await is_circular_manager(db, employee.id, manager.id):
        raise HTTPException(
            400,
            "Circular manager hierarchy detected"
        )

    #  Assign manager
    employee.manager_id = manager.id

    await db.commit()
    await db.refresh(employee)

    return {
        "message": "Manager assigned successfully",
        "employee_id": employee.id,
        "manager_id": manager.id,
        "manager_name": manager.first_name,
    }


@router.get("/{employee_id}/manager", status_code=200)
async def get_employee_manager(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.manager))
        .where(
            Employee.id == employee_id,
            Employee.company_id == current_user.company_id
        )
    )

    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(404, "Employee not found")

    if not employee.manager:
        return {"manager": None}

    manager = employee.manager

    return {
        "manager": {
            "id": manager.id,
            "employee_code": manager.employee_code,
            "first_name": manager.first_name,
            "last_name": manager.last_name,
        }
    }
    
    
@router.get("/{manager_id}/subordinates", status_code=200)
async def get_direct_subordinates(
    manager_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    manager = await db.scalar(
        select(Employee).where(
            Employee.id == manager_id,
            Employee.company_id == current_user.company_id
        )
    )
    if not manager:
        raise HTTPException(404, "Manager not found")

    result = await db.execute(
        select(Employee).where(Employee.manager_id == manager_id)
    )
    subordinates = result.scalars().all()

    return {
        "manager_id": manager_id,
        "total_subordinates": len(subordinates),
        "subordinates": [
            {
                "id": e.id,
                "employee_code": e.employee_code,
                "first_name": e.first_name,
                "last_name": e.last_name,
                "status": e.status
            }
            for e in subordinates
        ]
    }
