
from pydantic import BaseModel, Field 
from typing import Optional , Literal 

class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
class DepartmentStatusUpdate(BaseModel):
   is_active: bool
   
class DepartmentHeadAssign(BaseModel):
    employee_id: int

