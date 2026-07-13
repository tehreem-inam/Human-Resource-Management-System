from fastapi import APIRouter

from app.api.company import router as company_router
from app.api.auth import router as auth_router
from app.api.company_owner import router as company_owner_router
from app.api.company_hr import router as company_hr_router
from app.api.department import router as department_router
from app.api.designation import router as designation_router
from app.api.employee import router as employee_router
from app.api.leave_type import router as leave_type_router
from app.api.leave_balance import router as leave_balance_router
from app.api.leave_request import router as leave_request_router
from app.api.leave_reports import router as leave_report_router
from app.api.attendance import router as attendance_router
from app.api.salary_structure import router as salary_structure_router
from app.api.payroll import router as payroll_router
# from app.api.systempreferences import router as system_preferences_router
 
class APIRouterRegistry:
    """
    Central registry for all API routers.
    """
    def __init__(self):
        self.router = APIRouter()
        self.include_all()

    def include_all(self):
        self.router.include_router(auth_router)
     
        self.router.include_router(company_router)
        self.router.include_router(company_owner_router)
        self.router.include_router(company_hr_router)
        self.router.include_router(department_router)
        self.router.include_router(designation_router)
        self.router.include_router(employee_router)
        self.router.include_router(leave_type_router)
        self.router.include_router(leave_balance_router)
        self.router.include_router(leave_request_router)
        self.router.include_router(leave_report_router)
        self.router.include_router(attendance_router)
        self.router.include_router(salary_structure_router)
        self.router.include_router(payroll_router)
api_router_registry = APIRouterRegistry() 
  