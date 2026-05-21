from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.user_service import UserService


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    db = SessionLocal()
    try:
        UserService(db).ensure_default_admin()
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

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
