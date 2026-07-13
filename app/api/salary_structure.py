from fastapi import APIRouter , Depends , HTTPException , status 
from sqlalchemy.ext.asyncio import AsyncSession   
from sqlalchemy.orm import Session 


from sqlalchemy import select  , func
from app.database import get_db



from app.models import SalaryStructure , Employee , Payslip
from sqlalchemy.exc import IntegrityError 
from app.auth.dependencies import require_hr_or_company_owner , get_current_user
from app.dto.salary_structure import SalaryCreateRequest , SalaryResponse , SalaryUpdateRequest , SalaryListResponse
router = APIRouter(
    prefix="/companies/salary-structures",
    tags=["Company • Salary Structures"]
)

@router.post(
    "/",
    response_model=SalaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_salary_structure(
    payload: SalaryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),
):
    """
    Create salary structure for an employee.

   
    """

    #  Validate employee (company isolation)
    result = await db.execute(
        select(Employee).where(
            Employee.id == payload.employee_id,
            Employee.company_id == current_user.company_id,
        )
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found in your company",
        )

    #  Pre-check to avoid obvious duplicates
    result = await db.execute(
        select(SalaryStructure.id).where(
            SalaryStructure.employee_id == payload.employee_id,
            SalaryStructure.company_id == current_user.company_id,
            SalaryStructure.effective_from == payload.effective_from,
        )
    )
    exists = result.scalar_one_or_none()

    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Salary structure already exists for this effective date",
        )

    #  Create salary structure (NO gross/net here)
    salary = SalaryStructure(
        company_id=current_user.company_id,
        employee_id=payload.employee_id,
        basic_salary=payload.basic_salary,
        allowances=payload.allowances,
        fixed_deductions=payload.fixed_deductions,
        working_days_per_month=payload.working_days_per_month,
        effective_from=payload.effective_from,
    )

    #  Save with race-condition safety
    try:
        db.add(salary)
        await db.commit()
        await db.refresh(salary)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Salary structure already exists (unique constraint)",
        )

    return salary

@router.put(
    "/{salary_id}",
    response_model=SalaryResponse,
    status_code=status.HTTP_200_OK,
)
async def update_salary_structure(
    salary_id: int,
    payload: SalaryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),
):
    """
    Update salary structure.

    """

    #  1. Fetch with row-level lock (race-condition safe)
    result = await db.execute(
        select(SalaryStructure)
        .where(
            SalaryStructure.id == salary_id,
            SalaryStructure.company_id == current_user.company_id,
        )
        .with_for_update()
    )
    salary = result.scalar_one_or_none()

    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary structure not found",
        )

    #  2. Apply updates (ONLY fields that exist in model)
    salary.basic_salary = payload.basic_salary
    salary.allowances = payload.allowances
    salary.fixed_deductions = payload.fixed_deductions
    salary.working_days_per_month = payload.working_days_per_month


    #  3. Commit safely
    try:
        await db.commit()
        await db.refresh(salary)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update violates database constraints",
        )

    return salary

@router.get(
    "/{employee_id}",
    response_model=SalaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_salary_structure(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),
):
    """
    Fetch the latest salary structure for a given employee.

    """

    # Fetch the latest effective salary for the employee
    result = await db.execute(
        select(SalaryStructure)
        .where(
            SalaryStructure.employee_id == employee_id,
            SalaryStructure.company_id == current_user.company_id,
        )
        .order_by(SalaryStructure.effective_from.desc())
    )
    salary = result.scalars().first()

    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary structure not found for this employee",
        )

    return salary

@router.get(
    "/",
    response_model=SalaryListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_salary_structures(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_hr_or_company_owner),
):
    """
    List salary structures for the company with pagination.

    """

    # Ensure page and size are positive
    if page < 1:
        page = 1
    if size < 1:
        size = 20

    # Build query for company's salaries
    query = select(SalaryStructure).where(
        SalaryStructure.company_id == current_user.company_id
    ).order_by(SalaryStructure.effective_from.desc())

    # Get total count
    total_result = await db.execute(
        select(func.count()).select_from(SalaryStructure).where(
            SalaryStructure.company_id == current_user.company_id
        )
    )
    total = total_result.scalar_one()

    # Apply pagination
    result = await db.execute(
        query.offset((page - 1) * size).limit(size)
    )
    salaries = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "data": salaries
    }
    

@router.delete("/{salary_id}")
async def delete_salary_structure(
    salary_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):

    # Fetch the salary structure
    result = await db.execute(
        select(SalaryStructure).where(
            SalaryStructure.id == salary_id,
            SalaryStructure.company_id == current_user.company_id,
        )
    )
    salary = result.scalar_one_or_none()

    if not salary:
        raise HTTPException(status_code=404, detail="Salary not found")

    # Check if any payslip already exists for this employee
    result = await db.execute(
        select(Payslip).where(Payslip.employee_id == salary.employee_id)
    )
    existing_payslip = result.scalar_one_or_none()

    if existing_payslip:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete salary. Payslip already exists."
        )

    # Delete the salary
    try:
        await db.delete(salary)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error occurred while deleting salary"
        )

    return {"message": "Salary structure deleted successfully"}