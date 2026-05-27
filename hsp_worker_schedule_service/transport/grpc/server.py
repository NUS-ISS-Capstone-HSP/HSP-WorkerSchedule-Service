import grpc

from hsp_worker_schedule_service.config import Settings
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.service.worker_schedule_service import WorkerScheduleService
from hsp_worker_schedule_service.transport.grpc.service import EchoGrpcService
from hsp_worker_schedule_service.transport.grpc.worker_schedule_service import (
    WorkerScheduleGrpcService,
)
from rpc.echo.v1 import echo_pb2_grpc
from rpc.worker_schedule.v1 import worker_schedule_pb2_grpc


def build_grpc_server(
    settings: Settings,
    echo_service: EchoService,
    worker_schedule_service: WorkerScheduleService,
) -> grpc.aio.Server:
    server = grpc.aio.server()
    echo_pb2_grpc.add_EchoServiceServicer_to_server(EchoGrpcService(echo_service), server)
    worker_schedule_pb2_grpc.add_WorkerScheduleServiceServicer_to_server(
        WorkerScheduleGrpcService(worker_schedule_service),
        server,
    )
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    return server
