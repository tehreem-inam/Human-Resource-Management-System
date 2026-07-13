from fastapi import APIRouter, Depends, HTTPException, status 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from typing import  Optional
from app.database import get_db
from app.models import LeaveType , Employee , LeaveBalance
from app.auth.dependencies import require_hr_or_company_owner 
from app.dto.leave_management import  LeaveBalanceAllocate


    
router = APIRouter(
    prefix="/companies/leave-balances",
    tags=["Company • Leave Balances"]
)

@router.post("/allocate", status_code=status.HTTP_200_OK)
async def allocate_leave_balance(
    payload: LeaveBalanceAllocate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    company_id = current_user.company_id
    
    # Validate employee belongs to company
    employee = await db.scalar(
        select(Employee).where(
            Employee.id == payload.employee_id,
            Employee.company_id == company_id
        )
    )
    
    if not employee:
        raise HTTPException(404, "Employee not found in your company")
    
    # Validate leave type belongs to company
    leave_type = await db.scalar(
        select(LeaveType).where(    
            LeaveType.id == payload.leave_type_id,
            LeaveType.company_id == company_id
        )
    )
    
    if not leave_type:
        raise HTTPException(404, "Leave type not found in your company")
    
    #check if balance record already exists for employee, leave type and year
    
    existing = await db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == payload.employee_id,
            LeaveBalance.leave_type_id == payload.leave_type_id,
            LeaveBalance.year == payload.year
        )
    )
    
    if existing:
          raise HTTPException(
            status_code=409,
            detail="Leave balance already exists for this year"
        )
          
    balance = LeaveBalance(
        company_id=company_id,
        employee_id=payload.employee_id,
        leave_type_id=payload.leave_type_id,
        year=payload.year,
        allocated_days =   leave_type.annual_quota,
        used_days=0
    )
    
    
    db.add(balance)
    await db.commit()
    await db.refresh(balance)

    return {"message": "Leave balance allocated successfully"}

@router.get("/employee/{employee_id}", status_code=200)
async def get_employee_leave_balances(
    employee_id: int,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    query = select(LeaveBalance).where(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.company_id == current_user.company_id
    )

    if year:
        query = query.where(LeaveBalance.year == year)

    result = await db.execute(query)
    balances = result.scalars().all()

    response = []
    for b in balances:
        response.append({
            "employee_id": b.employee_id,
            "leave_type_id": b.leave_type_id,
            "year": b.year,
            "allocated_days": b.allocated_days,
            "used_days": b.used_days,
            "remaining_days": b.allocated_days - b.used_days
        })

    return {
        "total": len(response),
        "balances": response
    }
