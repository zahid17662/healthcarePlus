from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import engine
from .errors import register_error_handlers
from .routers import admin, appointments, auth, doctors

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def _first_validation_message(exc: RequestValidationError) -> str:
    """One readable line; never echoes the submitted value (could be a password)."""
    err = exc.errors()[0]
    field = next((str(p) for p in reversed(err["loc"]) if p not in ("body", "query", "path")), "request")
    return f"{field}: {err['msg']}"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MediBook API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_error_handlers(app)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": _first_validation_message(exc)})

    for module in (auth, doctors, appointments, admin):
        app.include_router(module.router, prefix=API_PREFIX)

    @app.get("/health", tags=["Meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
