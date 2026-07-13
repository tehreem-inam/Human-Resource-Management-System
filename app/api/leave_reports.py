from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select , func
from app.database import get_db
from sqlalchemy.orm import selectinload
from app.models import Employee , LeaveRequest 
from app.auth.dependencies import require_employee ,require_hr_or_company_owner
from app.dto.leave_management import  LeaveReportFilterDTO , LeaveRequestResponseDTO , PaginationDTO
router = APIRouter(
    prefix="/companies/leave-reports",
    tags =["Company • Leave Reporting"]
)
@router.get("/hr", response_model=dict)
async def hr_leave_report(
    filters: LeaveReportFilterDTO = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    company_id = current_user.company_id

  
    base_query = (
        select(LeaveRequest)
        .join(Employee, LeaveRequest.employee_id == Employee.id)
        .where(
            Employee.company_id == company_id,      
        )
    )


    if filters.employee_id:
        base_query = base_query.where(
            LeaveRequest.employee_id == filters.employee_id
        )

    if filters.leave_type_id:
        base_query = base_query.where(
            LeaveRequest.leave_type_id == filters.leave_type_id
        )

    if filters.status:
        base_query = base_query.where(
            LeaveRequest.status == filters.status
        )

    if filters.start_date_from:
        base_query = base_query.where(
            LeaveRequest.start_date >= filters.start_date_from
        )

    if filters.start_date_to:
        base_query = base_query.where(
            LeaveRequest.start_date <= filters.start_date_to
        )


    count_stmt = select(func.count()).select_from(
        base_query.order_by(None).subquery()
    )
    total = await db.scalar(count_stmt)

    #  Pagination
    offset = (filters.page - 1) * filters.page_size

    result = await db.execute(
        base_query
        .options(
            selectinload(LeaveRequest.employee),    
            selectinload(LeaveRequest.leave_type),  
        )
        .order_by(
            LeaveRequest.applied_at.desc(),
            LeaveRequest.id.desc(), 
        )
        .offset(offset)
        .limit(filters.page_size)
    )

    records = result.scalars().all()

    return {
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "data": [
            LeaveRequestResponseDTO.model_validate(r)
            for r in records
        ],
    }
    
   
@router.get("/employee/history", response_model=dict)
async def employee_leave_history(
    pagination: PaginationDTO = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_employee),
):
    employee_id = current_user.employee_id

    # Base query
    base_stmt = select(LeaveRequest).where(
        LeaveRequest.employee_id == employee_id
    )

    #  Count query 
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = await db.scalar(count_stmt) or 0

    #  Safe pagination
    offset = max(pagination.page - 1, 0) * pagination.page_size

    data_stmt = (
        base_stmt
        .order_by(LeaveRequest.applied_at.desc(), LeaveRequest.id.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )

    result = await db.execute(data_stmt)
    records = result.scalars().all()

    return {
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "data": [
            LeaveRequestResponseDTO.model_validate(
                r, from_attributes=True
            )
            for r in records
        ],
    }