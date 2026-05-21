import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.exc import OperationalError
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.user_service import UserService

logger = logging.getLogger("uvicorn.error")


def _mysql_auth_hint(exc: BaseException) -> str | None:
    message = str(getattr(exc, "orig", exc)).lower()
    if "mysql_native_password" in message or "1524" in message:
        return (
            "MySQL rechazó la conexión: el usuario usa mysql_native_password y el "
            "servidor no carga ese plugin (común en MySQL 8.4+). En MySQL ejecute:\n"
            "  ALTER USER 'su_usuario'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'su_password';\n"
            "  FLUSH PRIVILEGES;\n"
            "Luego reinicie la API. Asegúrese de tener `cryptography` instalado (requirements.txt)."
        )
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    db = SessionLocal()
    try:
        UserService(db).ensure_default_admin()
    except OperationalError as exc:
        hint = _mysql_auth_hint(exc)
        if hint:
            logger.error(hint)
        raise
    finally:
        db.close()
    yield


def _error_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict) and "msg" in first:
            return str(first["msg"])
    return "Error en la solicitud"


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": _error_message(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": _error_message(exc.errors())},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=r"https://([a-z0-9-]+\.)?carwashdg\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": settings.app_name, "docs": "/docs", "login": "/login"}

    @app.get("/login", include_in_schema=False)
    def login_redirect() -> RedirectResponse:
        return RedirectResponse(url=f"{settings.api_prefix}/auth/login", status_code=302)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8050, reload=True)
