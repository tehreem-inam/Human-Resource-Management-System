from pydantic import BaseModel, Field 

from datetime import date
from decimal import Decimal 

from typing import Annotated , List

# Numeric type with constraints using Annotated + Field
Decimal12_2 = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Decimal12_2_optional = Annotated[Decimal, Field(default=0, max_digits=12, decimal_places=2)]
WorkingDays = Annotated[int, Field(default=30, ge=20, le=31)]


class SalaryCreateRequest(BaseModel):
    employee_id: int
    basic_salary: Decimal12_2
    allowances: Decimal12_2_optional
    fixed_deductions: Decimal12_2_optional
    working_days_per_month: WorkingDays
    effective_from: date


class SalaryUpdateRequest(BaseModel):
    basic_salary: Decimal12_2
    allowances: Decimal12_2_optional
    fixed_deductions: Decimal12_2_optional
    working_days_per_month: WorkingDays


class SalaryResponse(BaseModel):
    id: int
    employee_id: int
    basic_salary: Decimal
    allowances: Decimal
    fixed_deductions: Decimal
    working_days_per_month: int
    effective_from: date
    
    
class SalaryListResponse(BaseModel):
      total: int
      page: int
      size: int
      data: List[SalaryResponse]  # Uses your existing SalaryResponse model

   
class Config:
        orm_mode = True