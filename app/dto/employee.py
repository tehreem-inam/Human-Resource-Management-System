from pydantic import BaseModel, EmailStr, Field
from typing import Optional , Literal
from datetime import date

class EmployeeCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: str
    last_name: Optional[str] = None
    
class EmployeeStatusUpdate(BaseModel):
    status: Literal["active", "inactive", "on_leave", "terminated"]
    
class EmployeeSelfProfileUpdate(BaseModel):
    gender: Literal["male", "female", "other"] | None
    date_of_birth: Optional[date]
    
class EmployeeHRProfileUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[date]
    employment_type: Literal["full_time","part_time","contract","internship"] | None
    
    
    
#--------------assign department------------------#
class AssignDepartmentDTO(BaseModel):
    department_id: int


#--------------assign designation------------------#

class AssignDesignationDTO(BaseModel):
    designation_id: int



#--------------assign manager------------------#

class AssignManagerDTO(BaseModel):
    manager_id: int
