
from pydantic import BaseModel, Field
from typing import Optional

class DesignationCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    # description: Optional[str] = Field(None, max_length=500)
    department_id: Optional[int] = None
class DesignationUpdateDTO(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=100)
    # description: str | None = Field(None, max_length=500)
