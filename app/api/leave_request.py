from fastapi import APIRouter, Depends, HTTPException, status 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from app.database import get_db
from app.models import LeaveType , LeaveRequest , LeaveBalance
from app.auth.dependencies import require_employee ,require_hr_or_company_owner
from app.dto.leave_management import  LeaveApprove , LeaveRequestCreate

router = APIRouter(
    prefix="/companies/leave-requests",
    tags =["Company • Leave Requests"]
)

@router.post("/apply" , status_code=status.HTTP_201_CREATED)
async def apply_leave(
    payload: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_employee),
):
    company_id = current_user.company_id
    employee_id = current_user.employee_id
    
    leave_type = await db.scalar(
        select(LeaveType).where(
            LeaveType.id == payload.leave_type_id,
            LeaveType.company_id == company_id 
        )
    )
    
    if not leave_type:
        raise HTTPException(404, "Leave type not found in your company")
    if not leave_type.is_active:
        raise HTTPException(400, "Leave type is inactive")
    if payload.end_date < payload.start_date:
     raise HTTPException(
        status_code=400,
        detail="End date cannot be before start date"
    )
     
    overlapping = await db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.company_id == company_id,
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date
        )
    )

    if overlapping:
        raise HTTPException(400, "You have an overlapping leave request during this period")
    
    leave_request = LeaveRequest(
         company_id=company_id,
        employee_id = employee_id,
        leave_type_id = payload.leave_type_id,
        start_date = payload.start_date,
        end_date = payload.end_date,
        reason = payload.reason,
        status = "pending"
        
    )
    db.add(leave_request)
    await db.commit()
    await db.refresh(leave_request)
   
    return {"message": "Leave request submitted successfully", "leave_request_id": leave_request.id}


def calculate_leave_days(start_date: date, end_date: date) -> int:
    return (end_date - start_date).days + 1
@router.post("/{leave_request_id}/action", status_code=status.HTTP_200_OK)
async def take_leave_action(
    leave_request_id: int,
    payload: LeaveApprove,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):

    # Lock leave request
    leave_request = await db.scalar(
        select(LeaveRequest)
        .where(
            LeaveRequest.id == leave_request_id,
            LeaveRequest.company_id == current_user.company_id,
        )
        .with_for_update()
    )

    if not leave_request:
        raise HTTPException(404, "Leave request not found in your company")

    if leave_request.status != "pending":
        raise HTTPException(400, "Leave request has already been processed")

    # Self approval guard
    if current_user.employee_id and (
        leave_request.employee_id == current_user.employee_id
    ):
        raise HTTPException(403, "You cannot approve your own leave")

    #  Reject flow
    if payload.action == "reject":
        leave_request.status = "rejected"
        await db.commit()
        return {"message": "Leave request rejected"}

    #  Calculate leave days
    leave_days = calculate_leave_days(
        leave_request.start_date,
        leave_request.end_date,
    )

    if leave_days <= 0:
        raise HTTPException(400, "Invalid leave duration")

    year = leave_request.start_date.year

    #  Fetch leave type
    leave_type = await db.scalar(
        select(LeaveType).where(
            LeaveType.id == leave_request.leave_type_id,
            LeaveType.company_id == current_user.company_id,
        )
    )

    if not leave_type:
        raise HTTPException(400, "Leave type not found")

    #  Lock balance
    leave_balance = await db.scalar(
        select(LeaveBalance)
        .where(
            LeaveBalance.company_id == current_user.company_id,
            LeaveBalance.employee_id == leave_request.employee_id,
            LeaveBalance.leave_type_id == leave_request.leave_type_id,
            LeaveBalance.year == year,
        )
        .with_for_update()
    )

    #  Auto create
    if not leave_balance:
        leave_balance = LeaveBalance(
            company_id=current_user.company_id,
            employee_id=leave_request.employee_id,
            leave_type_id=leave_request.leave_type_id,
            year=year,
            allocated_days=leave_type.annual_quota,
            used_days=0,
        )
        db.add(leave_balance)
        await db.flush()

    remaining_balance = (
        leave_balance.allocated_days - leave_balance.used_days
    )

    if leave_days > remaining_balance:
        raise HTTPException(400, "Insufficient leave balance")

    #  Deduct
    leave_balance.used_days += leave_days
    leave_request.status = "approved"

    await db.commit()
    await db.refresh(leave_request)

    return {"message": "Leave request approved"}
@router.post("/{leave_request_id}/cancel", status_code=200)
async def cancel_leave(
    leave_request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_employee),
):

    #  Lock leave request for update
    leave_request = await db.scalar(
        select(LeaveRequest)
        .where(
            LeaveRequest.id == leave_request_id,
            LeaveRequest.employee_id == current_user.employee_id,
        )
        .with_for_update()
    )

    if not leave_request:
        raise HTTPException(404, "Leave request not found")

    if leave_request.status != "approved":
        raise HTTPException(400, "Only approved leave can be cancelled")

    leave_days = calculate_leave_days(
        leave_request.start_date,
        leave_request.end_date,
    )

    year = leave_request.start_date.year

    #  Lock leave balance for update
    leave_balance = await db.scalar(
        select(LeaveBalance)
        .where(
            LeaveBalance.employee_id == leave_request.employee_id,
            LeaveBalance.leave_type_id == leave_request.leave_type_id,
            LeaveBalance.year == year,
        )
        .with_for_update()
    )

    if not leave_balance:
        raise HTTPException(400, "Leave balance not found")

    if leave_balance.used_days < leave_days:
        raise HTTPException(400, "Invalid balance state")

    #  Deduct used days and cancel leave
    leave_balance.used_days -= leave_days
    leave_request.status = "cancelled"

    await db.commit()
    await db.refresh(leave_request)

    return {"message": "Leave cancelled successfully"}