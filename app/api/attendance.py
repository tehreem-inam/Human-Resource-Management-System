from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select , func

from datetime import datetime , timezone
from dateutil.relativedelta import relativedelta
from datetime import date , timedelta

from app.database import get_db
from app.models import  Attendance
from app.auth.dependencies import require_hr_or_company_owner  , require_employee
from app.dto.attendance import ManualAttendanceDTO



def to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

router = APIRouter(
    prefix="/companies/attendance",
    tags=["Company • Attendance"]
)
@router.post("/check-in", response_model=dict)
async def check_in(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_employee),
):
    employee_id = current_user.employee_id
    company_id = current_user.company_id
    today = datetime.utcnow().date()

    attendance = await db.scalar(
        select(Attendance)
        .where(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date == today
        )
        .with_for_update()
    )

    if attendance and attendance.check_in_time:
        raise HTTPException(
            status_code=400,
            detail="Already checked in today"
        )

    now = datetime.utcnow()

    if not attendance:
        attendance = Attendance(
            company_id=company_id,
            employee_id=employee_id,
            attendance_date=today,
            check_in_time=now,
            status="present"
        )
        db.add(attendance)
    else:
        attendance.check_in_time = now
        attendance.status = "present"
        db.add(attendance)

    await db.commit()  # commit manually

    return {"message": "Check-in successful"}

@router.post("/check-out", response_model=dict)
async def check_out(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_employee),
):
    employee_id = current_user.employee_id
    today = datetime.utcnow().date()

    # Fetch today's attendance record
    attendance = await db.scalar(
        select(Attendance)
        .where(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date == today
        )
        .with_for_update()
    )

    if not attendance or not attendance.check_in_time:
        raise HTTPException(
            status_code=400,
            detail="Check-in required before check-out"
        )

    if attendance.check_out_time:
        raise HTTPException(
            status_code=400,
            detail="Already checked out"
        )

    # Update check-out time and total work minutes
    checkout_time = datetime.utcnow()
    attendance.check_out_time = checkout_time

    # Calculate total work minutes
    delta = checkout_time - attendance.check_in_time
    attendance.total_work_minutes = int(delta.total_seconds() // 60)

    db.add(attendance)  # update the record
    await db.commit()   # commit manually

    return {"message": "Check-out successful"}

@router.post("/manual", status_code=200)
async def manual_attendance_entry(
    payload: ManualAttendanceDTO,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    company_id = current_user.company_id
    now_utc = datetime.utcnow()

    # Convert payload times to naive UTC
    check_in = to_naive_utc(payload.check_in_time)
    check_out = to_naive_utc(payload.check_out_time)

    # Validation
    if check_in and check_out and check_in > check_out:
        raise HTTPException(status_code=400, detail="Check-in cannot be after check-out")
    if (check_in and check_in > now_utc) or (check_out and check_out > now_utc):
        raise HTTPException(status_code=400, detail="Times cannot be in the future")

    # Fetch existing record
    attendance = await db.scalar(
        select(Attendance)
        .where(
            Attendance.employee_id == payload.employee_id,
            Attendance.attendance_date == payload.attendance_date
        )
        .with_for_update()
    )

    if not attendance:
        attendance = Attendance(
            company_id=company_id,
            employee_id=payload.employee_id,
            attendance_date=payload.attendance_date,
            is_manual=True
        )
        db.add(attendance)

    attendance.check_in_time = check_in
    attendance.check_out_time = check_out
    attendance.status = payload.status
    attendance.remarks = payload.remarks

    if check_in and check_out:
        delta = check_out - check_in
        attendance.total_work_minutes = int(delta.total_seconds() // 60)

    await db.flush()   # push changes
    await db.commit()  # commit transaction

    return {"message": "Attendance updated successfully"}


@router.get("/summary/monthly")
async def monthly_attendance_summary(
    employee_id: int,
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    # Compute month range
    start_date = date(year, month, 1)
    end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)

    # Aggregate total days & minutes
    result = await db.execute(
        select(
            func.count().label("total_days"),
            func.sum(Attendance.total_work_minutes).label("total_minutes")
        )
        .where(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date.between(start_date, end_date)
        )
    )

    row = result.fetchone()

    total_minutes = row.total_minutes or 0
    hours = total_minutes // 60
    minutes = total_minutes % 60

    return {
        "total_days": row.total_days or 0,
        "total_work_minutes": total_minutes,
        "total_work_hours": f"{hours}h {minutes}m"
    }