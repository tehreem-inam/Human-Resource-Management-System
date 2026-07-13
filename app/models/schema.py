from app.database import Base
from sqlalchemy import Column,Date, Integer,JSON,Time,  Numeric,String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func, text, CheckConstraint
from sqlalchemy import ( Column, Enum,Integer, String, Boolean, DateTime, ForeignKey, Text)
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
 


def utcnow():
 return datetime.utcnow()

class Company(Base):
  __tablename__ = "companies"
  id = Column(Integer, primary_key= True)  
  name = Column(String(100), nullable=False, unique=True)
  email = Column(String(120), nullable=False, unique=True)
  phone =  Column(String(20))
  address = Column(String(255))
  is_active = Column(Boolean, default=True)
  is_deleted = Column(Boolean, default=False)
  
  created_at = Column(DateTime(timezone=True), default=utcnow)
  updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
  
  departments = relationship("Department",back_populates="company")
  employees = relationship("Employee",back_populates="company")
  users = relationship("User", back_populates="company")
  roles = relationship("Role", back_populates="company")
  
  
class Department(Base):
  __tablename__ = "departments"
  id = Column(Integer, primary_key=True)
  company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"),nullable=False)
  name = Column(String(100), nullable=False)
  description = Column(Text)
  is_active = Column(Boolean, default=True)
  head_employee_id = Column(
        Integer,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True
    )
  
  
  employees = relationship(
        "Employee",
        back_populates="department",
        foreign_keys="Employee.department_id"
    )
  head = relationship(
        "Employee",
        foreign_keys=[head_employee_id],
        post_update=True
    )

  company = relationship("Company",back_populates="departments")
  designation = relationship("Designation",back_populates="department")   
  
  __table_args__ = (
    UniqueConstraint("company_id","name", name="uq_department_company"),
  ) 
  

class Designation(Base):
  __tablename__ = "designations"
  id = Column(Integer, primary_key=True)
  department_id = Column(Integer,ForeignKey("departments.id", ondelete="CASCADE"),nullable=False)
  title = Column(String(100), nullable=False)
  description = Column(Text)
  is_active = Column(Boolean, default=True)
  created_at = Column(DateTime(timezone=True), default=utcnow)
  deleted_at = Column(DateTime(timezone=True), nullable=True)
  # level = Column(String(50))  # Junior, Mid, Senior
  
  department = relationship("Department", back_populates="designation")  





class Role(Base):
   __tablename__ = "roles"


   id = Column(Integer, primary_key=True)
   company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
   name = Column(String(50), nullable=False) # admin, hr, employee
   created_at = Column(DateTime(timezone=True), default=utcnow)


   users = relationship("User", back_populates="role")
   company = relationship("Company", back_populates="roles")
   __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_company_role"),
    )

class User(Base):
   __tablename__ = "users"


   id = Column(Integer, primary_key=True)
   company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
   email = Column(String(120),unique=True, nullable=False)
   password_hash = Column(String(255), nullable=False)
   role_id = Column(Integer, ForeignKey("roles.id"))
   is_active = Column(Boolean, default=True)
   last_login = Column(DateTime)
   created_at = Column(DateTime, default=utcnow)

   company = relationship("Company", back_populates="users")
   role = relationship("Role", back_populates="users")
   employee = relationship("Employee", back_populates="user", uselist=False)
   __table_args__ = (
        UniqueConstraint(
            "company_id",
            "email",
            name="uq_company_email"
        ),
    )
class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"

class Employee(Base):
  __tablename__ = "employees"
  id = Column(Integer, primary_key=True)
  company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"),nullable=False)
  user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),unique=True)
  
  employee_code = Column(String(50), unique=True, nullable=False)
  first_name = Column(String(100), nullable=False)
  last_name = Column(String(100))
  gender = Column(Enum("male","female","other",name="gender_enum"))
  date_of_birth = Column(Date)
  
  
  department_id = Column(Integer, ForeignKey("departments.id"))
  designation_id = Column(Integer, ForeignKey("designations.id"))
  manager_id = Column(Integer, ForeignKey("employees.id"))
  
  joining_date = Column(Date)
  employment_type = Column(Enum("full_time","part_time","contract","internship",name="employment_type_enum"))
  status = Column(Enum("active","inactive","on_leave","terminated",name="employee_status_enum"), default="active")
  
  company = relationship("Company", back_populates="employees")
  user = relationship("User", back_populates="employee")
  manager = relationship("Employee", remote_side=[id])
  department = relationship(
        "Department",
        back_populates="employees",
        foreign_keys=[department_id]
    )
  __table_args__ = (
    UniqueConstraint(
        "company_id",
        "employee_code",
        name="uq_company_employee_code"
    ),)
class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    employee_id = Column(
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    attendance_date = Column(Date, nullable=False, index=True)

    check_in_time = Column(DateTime)
    check_out_time = Column(DateTime)

    total_work_minutes = Column(Integer)

    status = Column(
        Enum(
            "present",
            "absent",
            "half_day",
            "on_leave",
            "weekend",
            "holiday",
            name="attendance_status_enum"
        ),
        nullable=False,
        default="present"
    )

    is_manual = Column(Boolean, default=False)
    remarks = Column(Text)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "attendance_date",
            name="uq_employee_attendance_date"
        ),
    )
  
  
  
#leave management 
  
  
class LeaveType(Base):
  __tablename__ = "leave_types"
  
  id = Column(Integer, primary_key=True)
  name = Column(String(100), nullable=False)
  annual_quota = Column(Integer, nullable=False)
  company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

  is_paid = Column(Boolean, default=True)
  requires_approval = Column(Boolean, default=True)
  is_active = Column(Boolean, default=True)
  code = Column(String(50), nullable=False)

  __table_args__ = (
    UniqueConstraint("company_id", "code", name="uq_company_leave_code"),
)
  
class LeaveRequest(Base):
  __tablename__ = "leave_requests"
  
  id = Column(Integer, primary_key=True)
  employee_id = Column(Integer, ForeignKey("employees.id"),nullable=False)
  leave_type_id = Column(Integer, ForeignKey("leave_types.id"),nullable=False)
  company_id = Column(
    Integer,
    ForeignKey("companies.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
  start_date = Column(Date, nullable=False)
  end_date = Column(Date, nullable=False)
  reason = Column(Text)
  
  status = Column(Enum("pending","approved","rejected","cancelled",name="leave_request_status_enum"), default="pending")
  applied_at = Column(DateTime, default=utcnow)
  approved_by = Column(Integer, ForeignKey("employees.id"))
  approved_at = Column(DateTime)
  rejection_reason = Column(Text)

  
  employee = relationship("Employee", foreign_keys=[employee_id],
        backref="leave_requests")
  approver = relationship(
        "Employee",
        foreign_keys=[approved_by],
        backref="approved_leave_requests"
    )
  leave_type = relationship("LeaveType")
  
class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    employee_id = Column(
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    leave_type_id = Column(
        Integer,
        ForeignKey("leave_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    year = Column(Integer, nullable=False)

    allocated_days = Column(Integer, nullable=False, default=0)
    used_days = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "leave_type_id",
            "year",
            name="uq_employee_leave_year"
        ),
    )

#payroll management
class SalaryStructure(Base):
    __tablename__ = "salary_structures"
  
    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    employee_id = Column(Integer, ForeignKey("employees.id"),nullable=False,unique=True,index=True)
  
    # Core Salary Components (Minimal Model)
    basic_salary = Column(Numeric(12, 2), nullable=False)
    allowances = Column(Numeric(12, 2), nullable=False, default=0)
    fixed_deductions = Column(Numeric(12, 2), nullable=False, default=0)

    # Payroll Policy
    working_days_per_month = Column(Integer, nullable=False, default=30)

    # Effective Date
    effective_from = Column(Date, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

  
    employee = relationship("Employee")
    __table_args__ = (
    UniqueConstraint(
        "company_id",
        "employee_id",
        "effective_from",
        name="uq_salary_effective"
    ),
)
  
class Payroll(Base):
  __tablename__ = "payrolls"
  
  id = Column(Integer, primary_key=True)
  company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
  month = Column(Integer, nullable=False)
  year = Column(Integer, nullable=False)
  status = Column(
        Enum(
            "draft",
            "processing",
            "finalized",
            name="payroll_status_enum"
        ),
        nullable=False,
        default="draft"
    )
  total_employees = Column(Integer, default=0)
  total_gross = Column(Numeric(14, 2), default=0)
  total_deductions = Column(Numeric(14, 2), default=0)
  total_net = Column(Numeric(14, 2), default=0)

  created_at = Column(DateTime, default=utcnow, nullable=False)
  updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

  payslips = relationship(
        "Payslip",
        back_populates="payroll",
        cascade="all, delete-orphan"
    )
  
  __table_args__ = (
    UniqueConstraint( "company_id",
            "year",
            "month",
            name="uq_company_year_month"),
  )
  
class Payslip(Base):
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True)

    payroll_id = Column(
        Integer,
        ForeignKey("payrolls.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    employee_id = Column(
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Salary Snapshot
    basic_salary = Column(Numeric(12, 2), nullable=False)
    allowances = Column(Numeric(12, 2), nullable=False)
    fixed_deductions = Column(Numeric(12, 2), nullable=False)

    # Dynamic Deductions
    attendance_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    leave_deduction = Column(Numeric(12, 2), nullable=False, default=0)

    # Final Calculations
    gross_salary = Column(Numeric(14, 2), nullable=False)
    total_deductions = Column(Numeric(14, 2), nullable=False)
    net_salary = Column(Numeric(14, 2), nullable=False)

    generated_at = Column(DateTime, default=utcnow, nullable=False)

    payroll = relationship("Payroll", back_populates="payslips")
    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint(
            "payroll_id",
            "employee_id",
            name="uq_payroll_employee"
        ),
    )