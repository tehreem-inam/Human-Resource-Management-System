from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Role
from app.auth.security import get_password_hash
from app.settings import settings


async def create_super_admin(db: AsyncSession):
    # 1. Check if SUPER_ADMIN role exists
    role_stmt = select(Role).where(Role.name == "SUPER_ADMIN")
    role_result = await db.execute(role_stmt)
    super_admin_role = role_result.scalar_one_or_none()

    if not super_admin_role:
        super_admin_role = Role(
            name="SUPER_ADMIN"        )
        db.add(super_admin_role)
        await db.commit()
        await db.refresh(super_admin_role)

    # 2. Check if SUPER_ADMIN user exists
    user_stmt = select(User).where(
        User.role_id == super_admin_role.id
    )
    user_result = await db.execute(user_stmt)
    existing_admin = user_result.scalar_one_or_none()

    if existing_admin:
        return

    # 3. Read credentials from ENV
    email = settings.SUPER_ADMIN_EMAIL
    password = settings.SUPER_ADMIN_PASSWORD

    if not email or not password:
        raise RuntimeError(
            "SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must be set"
        )

    # 4. Create SUPER_ADMIN user
    super_admin = User(
        email=email,
        password_hash=get_password_hash(password),
        role_id=super_admin_role.id,
        is_active=True,
        company_id=None  # 🔥 IMPORTANT
    )

    db.add(super_admin)
    await db.commit()

