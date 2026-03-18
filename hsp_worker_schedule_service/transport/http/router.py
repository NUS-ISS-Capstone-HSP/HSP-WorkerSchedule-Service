from fastapi import APIRouter, Path

from hsp_worker_schedule_service.domain.models import SourceType
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.transport.http.mapper import to_http_response
from hsp_worker_schedule_service.transport.http.schemas import (
    CreateEchoRequest,
    EchoRecordResponse,
)


def build_router(echo_service: EchoService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["echo"])

    @router.post(
        "/echo",
        response_model=EchoRecordResponse,
        status_code=201,
        summary="Create echo record",
        description="Store an echo message and return the created record.",
        response_description="Created echo record.",
        responses={
            400: {"description": "Business validation failed."},
            422: {"description": "Request payload validation failed."},
        },
    )
    async def create_echo(payload: CreateEchoRequest) -> EchoRecordResponse:
        """Create an echo record using shared service logic."""
        record = await echo_service.create_echo(payload.message, SourceType.HTTP)
        return to_http_response(record)

    @router.get(
        "/echo/{echo_id}",
        response_model=EchoRecordResponse,
        summary="Get echo record by id",
        description="Query a previously created echo record.",
        response_description="Echo record details.",
        responses={
            400: {"description": "Business validation failed."},
            404: {"description": "Echo record was not found."},
        },
    )
    async def get_echo(
        echo_id: str = Path(..., description="Echo record id (UUID)."),
    ) -> EchoRecordResponse:
        """Get one echo record by its id."""
        record = await echo_service.get_echo(echo_id)
        return to_http_response(record)

    return router
