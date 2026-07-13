from pydantic import BaseModel , Field
from datetime import date , datetime
from typing import Optional , Literal
from pydantic import validator

class LeaveTypeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=50)
    annual_quota: int = Field(ge=0)
    is_paid: bool = True
    requires_approval: bool = True
    
class LeaveTypeUpdate(BaseModel):
    name: Optional[str]
    annual_quota: Optional[int]
    is_paid: Optional[bool]
    requires_approval: Optional[bool]
    
class LeaveTypeStatus(BaseModel):
    is_active: bool
    
class LeaveBalanceAllocate(BaseModel):
    employee_id: int
    leave_type_id: int
    year: int
    allocated_days: Optional[int] = None

############ leave request ############
class LeaveRequestCreate(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: Optional[str] = Field(max_length=500)
    @validator("end_date")
    def validate_dates(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("End date cannot be before start date")
        return v
    
class LeaveApprove(BaseModel):
    action : Literal["approve", "reject"]
    remarks: Optional[str]  = None
    
    
############# leave report ############
class PaginationDTO(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    
class LeaveReportFilterDTO(PaginationDTO):
    employee_id: Optional[int] = None
    leave_type_id: Optional[int] = None
    status: Optional[Literal["pending", "approved", "rejected", "cancelled"]] = None
    start_date_from: Optional[date] = None
    start_date_to: Optional[date] = None
    page: int = 1
    page_size: int = 10
    
class LeaveRequestResponseDTO(BaseModel):
    id: int
    employee_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    status: str
    applied_at: datetime

    class Config:
        from_attributes = True