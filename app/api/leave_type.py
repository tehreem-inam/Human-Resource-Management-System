from fastapi import APIRouter, Depends, HTTPException, status 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from datetime import datetime
from app.database import get_db
from app.models import LeaveType , Employee , LeaveBalance
from app.auth.dependencies import require_hr_or_company_owner 
from app.dto.leave_management import LeaveTypeCreate , LeaveTypeUpdate , LeaveTypeStatus 

router = APIRouter(
    prefix="/companies/leave-types",
    tags=["Company • Leave types"]
)



async def generate_balances_for_leave_type(
    db,
    company_id: int,
    leave_type
):
    current_year = datetime.now().year

    result = await db.execute(
        select(Employee.id).where(Employee.company_id == company_id)
    )
    employee_ids = result.scalars().all()

  
    if not employee_ids:
        return

   
    balances = []

    for emp_id in employee_ids:
        exists = await db.scalar(
            select(LeaveBalance.id).where(
                LeaveBalance.employee_id == emp_id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.year == current_year,
            )
        )

        if not exists:
            balances.append(
                LeaveBalance(
                    company_id=company_id,
                    employee_id=emp_id,
                    leave_type_id=leave_type.id,
                    year=current_year,
                    allocated_days=leave_type.annual_quota,
                    used_days=0,
                )
            )

    if balances:
        db.add_all(balances)
        
########## Leave Types ##########
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    payload: LeaveTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user =  Depends(require_hr_or_company_owner),
):
    company_id = current_user.company_id
    
      # Normalize code (enterprise standard)
    code_normalized = payload.code.strip().upper()
    
    # Prevent duplicate code
    existing = await db.scalar(
        select(LeaveType).where(
        LeaveType.company_id == company_id,
        LeaveType.code == code_normalized
    )
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave type code already exists for this company"
        )
        
    leave_type = LeaveType(
        company_id=company_id,
        name=payload.name.strip(),
        code = code_normalized,
        annual_quota=payload.annual_quota,
        is_paid=payload.is_paid,
        requires_approval=payload.requires_approval
    )
    
    db.add(leave_type)
    await db.flush()
   
    
    await generate_balances_for_leave_type(
    db,
    company_id=company_id,
    leave_type=leave_type
)
    await db.commit()
    await db.refresh(leave_type)

    return {
        "message":"Leave type created successfully",
         "data": {
            "id": leave_type.id,
            "name": leave_type.name,
            "code": leave_type.code,
            "annual_quota": leave_type.annual_quota,
            "is_paid": leave_type.is_paid,
            "requires_approval": leave_type.requires_approval,
        }
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_leave_types(
    is_active: bool = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner)
):
    query = select(LeaveType).where(
        LeaveType.company_id == current_user.company_id
    )
    
    if is_active is not None:
        query = query.where(LeaveType.is_active == is_active)
        
    result = await db.execute(query)
    leave_types = result.scalars().all()
    
    
    return{
        "total" : len(leave_types),
        "items" : leave_types
    }
    
@router.patch("/{leave_type_id}", status_code=status.HTTP_200_OK)
async def update_leave_type(
    leave_type_id: int,
    payload: LeaveTypeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    company_id = current_user.company_id

    leave_type = await db.scalar(
        select(LeaveType).where(
            LeaveType.id == leave_type_id,
            LeaveType.company_id == company_id
        )
    )

    if not leave_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave type not found"
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "code" in update_data:
        new_code = update_data["code"].strip().upper()

        raise HTTPException(400, "Leave type code cannot be updated")

    # Validate annual quota
    if "annual_quota" in update_data:
        quota = update_data["annual_quota"]
        if quota is not None and quota < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Annual quota must be zero or positive"
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(leave_type, field, value)

    await db.commit()
    await db.refresh(leave_type)

    return {
        "message": "Leave type updated successfully",
        "leave_type_id": leave_type.id
    }

@router.patch("/{leave_type_id}/status", status_code=200)
async def toggle_leave_type_status(
    leave_type_id: int,
    payload: LeaveTypeStatus,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    leave_type = await db.scalar(
        select(LeaveType).where(
            LeaveType.id == leave_type_id,
            LeaveType.company_id == current_user.company_id
        )
    )

    if not leave_type:
        raise HTTPException(404, "Leave type not found")

    leave_type.is_active = payload.is_active

    await db.commit()

    return {
        "message": "Leave type status updated successfully",
        "is_active": leave_type.is_active
    }
 