from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hsp_worker_schedule_service.domain.errors import NotFoundError, ValidationError
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.transport.http.router import build_router


def create_http_app(echo_service: EchoService) -> FastAPI:
    app = FastAPI(title="HSP Worker Schedule Service")
    app.include_router(build_router(echo_service))

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(ValidationError)
    async def validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    return app
