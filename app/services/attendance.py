from sqlalchemy import select, func , extract
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Attendance , LeaveRequest , LeaveType


async def get_absent_days(
    db: AsyncSession,
    employee_id: int,
    year: int,
    month: int,
) -> int:

    result = await db.execute(
        select(func.count())
        .where(
            Attendance.employee_id == employee_id,
            Attendance.status == "absent",
            func.extract("year", Attendance.attendance_date) == year,
            func.extract("month", Attendance.attendance_date) == month,
        )
    )

    return result.scalar() or 0




async def get_unpaid_leave_days(
    db: AsyncSession,
    employee_id: int,
    year: int,
    month: int,
) -> int:
    """
    Returns the total unpaid leave days for a given employee
    in a specific month/year.
    """

    # Join LeaveRequest with LeaveType to know if it's paid
    result = await db.execute(
        select(func.sum(LeaveRequest.end_date - LeaveRequest.start_date  + 1))
        .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
        .where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",  # Only approved leaves
            LeaveType.is_paid == False,         # Only unpaid leaves
            func.extract("year", LeaveRequest.start_date) == year,
            func.extract("month", LeaveRequest.start_date) == month,
        )
    )

    total_days = result.scalar()
    return int(total_days or 0)