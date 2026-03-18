import grpc

from hsp_worker_schedule_service.domain.errors import NotFoundError, ValidationError
from hsp_worker_schedule_service.domain.models import SourceType
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.transport.grpc.mapper import to_grpc_record
from rpc.echo.v1 import echo_pb2, echo_pb2_grpc


class EchoGrpcService(echo_pb2_grpc.EchoServiceServicer):
    def __init__(self, echo_service: EchoService) -> None:
        self._echo_service = echo_service

    async def CreateEcho(
        self,
        request: echo_pb2.CreateEchoRequest,
        context: grpc.aio.ServicerContext,
    ) -> echo_pb2.CreateEchoResponse:
        try:
            record = await self._echo_service.create_echo(request.message, SourceType.GRPC)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return echo_pb2.CreateEchoResponse(record=to_grpc_record(record))

    async def GetEcho(
        self,
        request: echo_pb2.GetEchoRequest,
        context: grpc.aio.ServicerContext,
    ) -> echo_pb2.GetEchoResponse:
        try:
            record = await self._echo_service.get_echo(request.id)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        return echo_pb2.GetEchoResponse(record=to_grpc_record(record))

    async def Health(
        self,
        request: echo_pb2.HealthRequest,
        context: grpc.aio.ServicerContext,
    ) -> echo_pb2.HealthResponse:
        del request, context
        return echo_pb2.HealthResponse(status="ok")
