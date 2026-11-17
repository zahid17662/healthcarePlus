from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Domain error carrying the HTTP status the API should answer with."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def not_found(what: str) -> AppError:
    return AppError(404, f"{what} not found.")


def conflict(message: str) -> AppError:
    return AppError(409, message)


def unprocessable(message: str) -> AppError:
    return AppError(422, message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
