from datetime import datetime, timezone , date
from pydantic import BaseModel, EmailStr , Field
from typing import Optional,List , Literal


class BaseResponse(BaseModel):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        
        
class RoleResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
        
        
# ------------------ auth schemas ------------------ #

class UserCreate(BaseModel):
    #used by hr/admin to create users#
    email: EmailStr
    password: str = Field(min_length=6)
    role_id: Optional[int] = None
    is_active: Optional[bool] = True
    
class HRCreate(BaseModel):
    email: EmailStr
    password: str
    # first_name: str
    # employee_code: str
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    
class UserResponse(BaseResponse):
    email: EmailStr
    is_active: bool
    role: RoleResponse
    last_login: Optional[datetime] = None
    
class TokenResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    
class AuthUserContext(BaseModel):
    user_id: int
    role: str
    employee_id: Optional[int] = None
    
# ------------------ company schemas ------------------ #


class CompanyResonse(BaseResponse):
    name : str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    
class DepartmentCreate(BaseModel):
    name: str
    is_active: Optional[bool] = True
    
class DepartmentResponse(BaseResponse):
    name: str
    is_active: bool
    
class DesignationCreate(BaseModel):
    department_id: int
    title: str
    level: Optional[str] = None  # Junior, Mid, Senior
    
class DesignationResponse(BaseResponse):
    department_id: int
    title: str
    level: Optional[str] = None  # Junior, Mid, Senior
    
# ------------------ employee schemas ------------------ #

class EmployeeStatusUpdate(BaseModel):
    status: Literal["active", "inactive", "on_leave", "terminated"]
class EmployeeCreate(BaseModel):
    #hr creates employee profiles#
    employee_code: str
    first_name: str
    last_name: Optional[str] = None
    gender: Optional[str]
    date_of_birth: Optional[date] = None
    
    department_id: int
    designation_id: int
    manager_id: Optional[int] = None
    
    joining_date: date
    employment_type: str  # full_time, part_time, contract, internship
    
    user_id: int  # link to user account
    
class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    manager_id: Optional[int] = None
    employment_type: Optional[str] = None  # full_time, part_time, contract,
    status: Optional[str] = None  # active, inactive, on_leave, terminated
    
class EmployeeResponse(BaseResponse):
    employee_code: str
    first_name: str
    last_name: Optional[str] = None
    gender: Optional[str]
    date_of_birth: Optional[date] = None
    
    joining_date: date
    employment_type: str  # full_time, part_time, contract, internship
    status: str  # active, inactive, on_leave, terminated
    
    department: Optional[DepartmentResponse]
    designation: Optional[DesignationResponse]
    user: Optional[UserResponse]
    manager_id: Optional[int] = None
    
class EmployeeMinimalResponse(BaseModel):
    id: int
    employee_code: str
    first_name: str
    last_name: Optional[str] = None
    
    class Config:
        from_attributes = True
        
class EmployeeListResponse(BaseModel):
    total: int
    items: List[EmployeeResponse]




# SECURITY / PASSWORD


class ChangePasswordRequest(BaseModel):
  old_password: str
  new_password: str = Field(min_length=8)




class ResetPasswordRequest(BaseModel):
  email: EmailStr




# ERROR RESPONSE (OPTIONAL)


class ErrorResponse(BaseModel):
  detail: str
  

class RoleResponse(BaseModel):
    id: int
    name: str


class CompanyResponse(BaseModel):
    id: int
    name: str


class UserDataResponse(BaseModel):
    id: int
   
    email: EmailStr
    role: RoleResponse
    company: Optional[CompanyResponse] = None


class UserProfileResponse(BaseModel):
    success: bool
    message: str
    data: UserDataResponse