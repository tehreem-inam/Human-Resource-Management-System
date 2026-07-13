from fastapi import APIRouter , Depends , HTTPException , status 
from sqlalchemy.ext.asyncio import AsyncSession   

from sqlalchemy import select  
from app.database import get_db

from app.models import Payroll, Employee, SalaryStructure, Payslip , Company
from sqlalchemy.exc import IntegrityError 
from app.auth.dependencies import require_hr_or_company_owner , get_current_user

from sqlalchemy.orm import selectinload
from decimal import Decimal, ROUND_HALF_UP
from app.services.attendance import get_absent_days, get_unpaid_leave_days

from fastapi.responses import StreamingResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

router = APIRouter(
    prefix="/companies/payrolls",
    tags=["Company • Payrolls"]
)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    Create a payroll run for a specific month/year.
    Only HR/Admin allowed.
    One payroll per company per month.
    """

    #  Validate month
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12",
        )

    #  Check existing payroll (company isolation)
    result = await db.execute(
        select(Payroll).where(
            Payroll.company_id == current_user.company_id,
            Payroll.year == year,
            Payroll.month == month,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Payroll already exists for this month",
        )

    #  Create payroll 
    payroll = Payroll(
        company_id=current_user.company_id,
        year=year,
        month=month,
        status="draft",
    )

    try:
        db.add(payroll)
        await db.commit()
        await db.refresh(payroll)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Payroll already exists",
        )

    return payroll
@router.post("/{payroll_id}/generate", status_code=status.HTTP_200_OK)
async def generate_payroll(
    payroll_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    Process payroll for a given payroll run.

    Steps:
    1. Lock payroll row to avoid concurrent processing
    2. Fetch active employees
    3. Calculate salaries, deductions and net pay
    4. Create payslips
    5. Update payroll totals
    """

    # ---- Fetch payroll with row lock ----
    result = await db.execute(
        select(Payroll)
        .where(
            Payroll.id == payroll_id,
            Payroll.company_id == current_user.company_id,
        )
        .with_for_update()
    )
    payroll = result.scalar_one_or_none()

    if not payroll:
        raise HTTPException(
            status_code=404,
            detail="Payroll not found",
        )

    if payroll.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Payroll already processed",
        )

    try:
        payroll.status = "processing"

        # ---- Fetch active employees ----
        result = await db.execute(
            select(Employee).where(
                Employee.company_id == current_user.company_id,
                Employee.status == "active",
            )
        )
        employees = result.scalars().all()

        total_gross = Decimal("0.00")
        total_deductions = Decimal("0.00")
        total_net = Decimal("0.00")
        processed_employees = 0

        for employee in employees:

            # ---- Fetch employee salary structure ----
            salary_result = await db.execute(
                select(SalaryStructure).where(
                    SalaryStructure.employee_id == employee.id
                )
            )
            salary = salary_result.scalar_one_or_none()

            if not salary:
                continue

            gross_salary = (
                salary.basic_salary + salary.allowances
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            per_day_salary = (
                gross_salary
                / Decimal(salary.working_days_per_month)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # ---- Attendance deduction ----
            absent_days = await get_absent_days(
                db, employee.id, payroll.year, payroll.month
            )

            attendance_deduction = (
                per_day_salary * Decimal(absent_days)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # ---- Leave deduction ----
            unpaid_leave_days = await get_unpaid_leave_days(
                db, employee.id, payroll.year, payroll.month
            )

            leave_deduction = (
                per_day_salary * Decimal(unpaid_leave_days)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            total_emp_deductions = (
                salary.fixed_deductions
                + attendance_deduction
                + leave_deduction
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            net_salary = (
                gross_salary - total_emp_deductions
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # ---- Create payslip ----
            payslip = Payslip(
                payroll_id=payroll.id,
                employee_id=employee.id,
                basic_salary=salary.basic_salary,
                allowances=salary.allowances,
                fixed_deductions=salary.fixed_deductions,
                attendance_deduction=attendance_deduction,
                leave_deduction=leave_deduction,
                gross_salary=gross_salary,
                total_deductions=total_emp_deductions,
                net_salary=net_salary,
            )

            db.add(payslip)

            total_gross += gross_salary
            total_deductions += total_emp_deductions
            total_net += net_salary

            processed_employees += 1

        # ---- Update payroll totals ----
        payroll.total_employees = processed_employees
        payroll.total_gross = total_gross
        payroll.total_deductions = total_deductions
        payroll.total_net = total_net
        payroll.status = "processing"

        await db.commit()
        await db.refresh(payroll)

        return {
            "message": "Payroll processed successfully",
            "payroll_id": payroll.id,
            "total_employees": processed_employees,
        }

    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Payroll generation failed: {str(e)}"
        )
        


@router.post("/{payroll_id}/finalize", status_code=status.HTTP_200_OK)
async def finalize_payroll(
    payroll_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_hr_or_company_owner),
):
    """
    Finalize a payroll after processing.
    Locks the payroll for the month.
    """

    result = await db.execute(
        select(Payroll).where(
            Payroll.id == payroll_id,
            Payroll.company_id == current_user.company_id
        )
    )
    payroll = result.scalar_one_or_none()

    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")

    if payroll.status != "processing":
        raise HTTPException(status_code=400, detail="Payroll must be processed before finalization")

    payroll.status = "finalized"

    await db.commit()
    await db.refresh(payroll)

    return {"payroll_id": payroll.id, "status": payroll.status}





@router.get("/{payslip_id}/download")
async def download_payslip(
    payslip_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Download official payroll payslip PDF.
    Payslip can only be downloaded if payroll is finalized.
    """

    #  Fetch payslip with payroll eagerly loaded
    result = await db.execute(
        select(Payslip)
        .options(selectinload(Payslip.payroll))  
        .where(Payslip.id == payslip_id)
    )
    payslip = result.scalar_one_or_none()

    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")

    #  Check payroll status
    if payslip.payroll.status != "finalized":
        raise HTTPException(
            status_code=400,
            detail="Payslip not available until payroll is finalized"
        )

    #  Fetch employee
    result = await db.execute(
        select(Employee).where(Employee.id == payslip.employee_id)
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if current_user.role == "EMPLOYEE" and current_user.employee_id != employee.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role in ["HR", "COMPANY_OWNER"] and current_user.company_id != employee.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Company).where(Company.id == employee.company_id)
    )
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Generate PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, height - 50, "PAYSLIP")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, height - 100, f"Company: {company.name}")
    pdf.drawString(50, height - 120, f"Employee: {employee.first_name} {employee.last_name}")
    pdf.drawString(50, height - 140, f"Employee Code: {employee.employee_code}")

    pdf.drawString(50, height - 180, "Salary Details")
    pdf.drawString(50, height - 210, f"Basic Salary: {payslip.basic_salary}")
    pdf.drawString(50, height - 230, f"Allowances: {payslip.allowances}")
    pdf.drawString(50, height - 250, f"Gross Salary: {payslip.gross_salary}")

    pdf.drawString(50, height - 290, "Deductions")
    pdf.drawString(50, height - 320, f"Attendance Deduction: {payslip.attendance_deduction}")
    pdf.drawString(50, height - 340, f"Leave Deduction: {payslip.leave_deduction}")
    pdf.drawString(50, height - 360, f"Fixed Deductions: {payslip.fixed_deductions}")
    pdf.drawString(50, height - 400, f"Total Deductions: {payslip.total_deductions}")

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height - 450, f"Net Salary: {payslip.net_salary}")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    filename = f"payslip_{employee.employee_code}_{payslip.id}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )