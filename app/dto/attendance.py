
from pydantic import BaseModel
from typing import Optional  
from datetime import date, datetime


class ManualAttendanceDTO(BaseModel):
    employee_id: int
    attendance_date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime]  = None
    status: str
    remarks: Optional[str] = None