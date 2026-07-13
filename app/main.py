from fastapi import FastAPI, Request
import logging
import socket
import os
import asyncio
import sys

from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from app.router.routes import api_router_registry

from app.settings import settings
from app.exceptions.handlers import (
    sqlalchemy_integrity_error_handler,
    generic_exception_handler,
    validation_error_handler,
)
from app.middleware.cors import get_cors_middleware
from app.database import init_db ,async_session_factory
from app.bootstrap.super_admin import create_super_admin




if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


app = FastAPI(
    title="HUMAN RESOURCE Management SYSTEM Backend API",
    version="0.0.2",
)

# ======================
# CORS
# ======================

cors_config = get_cors_middleware()
app.add_middleware(
    cors_config["middleware_class"],
    **cors_config["options"],
)

# ======================
# GLOBAL EXCEPTION HANDLERS
# ======================

app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(IntegrityError, sqlalchemy_integrity_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ======================
# ROOT (HEALTH CHECK)
# ======================

@app.get("/")
def root(request: Request):
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    return {
        "status": "OK",
        "message": "Backend is running",
        "available_routes": routes,
    }

#Attach all API routers
app.include_router(api_router_registry.router)
# ======================
# LOCAL IP DISCOVERY
# ======================

def _get_local_ips() -> list[str]:
    ips: set[str] = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            ips.add(ip)
    except Exception:
        pass

    if not ips:
        return ["127.0.0.1"]

    non_loop = [ip for ip in ips if not ip.startswith("127.")]
    return non_loop or list(ips)


# ======================
# STARTUP EVENT (FINAL)
# ======================

@app.on_event("startup")
async def startup_event() -> None:
    """
    - Create DB tables
    - Bootstrap SUPER_ADMIN (idempotent)
    - Log accessible URLs
    """
    logger = logging.getLogger("uvicorn.error")

    try:
        #  Initialize database (tables, etc.)
        await init_db()

        #  Bootstrap SUPER_ADMIN safely
        async with async_session_factory() as db:
            await create_super_admin(db)

        #  Log network access URLs
        ips = _get_local_ips()
        port = os.getenv("PORT") or getattr(settings, "app_port", None) or 8000

        for ip in ips:
            logger.info(
                "Server reachable on local network: http://%s:%s/",
                ip,
                port,
            )

        logger.info("Local access: http://127.0.0.1:%s/", port)

    except Exception:
        logger.exception("Startup initialization failed")

