import grpc
import pytest
import pytest_asyncio

from hsp_worker_schedule_service.repository.in_memory import InMemoryEchoRepository
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.transport.grpc.service import EchoGrpcService
from rpc.echo.v1 import echo_pb2, echo_pb2_grpc


@pytest_asyncio.fixture
async def grpc_stub() -> echo_pb2_grpc.EchoServiceStub:
    service = EchoService(InMemoryEchoRepository())

    server = grpc.aio.server()
    echo_pb2_grpc.add_EchoServiceServicer_to_server(EchoGrpcService(service), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = echo_pb2_grpc.EchoServiceStub(channel)

    try:
        yield stub
    finally:
        await channel.close()
        await server.stop(0)


@pytest.mark.asyncio
async def test_health_success(grpc_stub: echo_pb2_grpc.EchoServiceStub) -> None:
    response = await grpc_stub.Health(echo_pb2.HealthRequest())

    assert response.status == "ok"


@pytest.mark.asyncio
async def test_create_and_get_echo_success(grpc_stub: echo_pb2_grpc.EchoServiceStub) -> None:
    created = await grpc_stub.CreateEcho(echo_pb2.CreateEchoRequest(message="hello grpc"))
    fetched = await grpc_stub.GetEcho(echo_pb2.GetEchoRequest(id=created.record.id))

    assert created.record.message == "hello grpc"
    assert created.record.source == "GRPC"
    assert fetched.record.id == created.record.id


@pytest.mark.asyncio
async def test_create_echo_invalid_argument(grpc_stub: echo_pb2_grpc.EchoServiceStub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.CreateEcho(echo_pb2.CreateEchoRequest(message="   "))

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_get_echo_not_found(grpc_stub: echo_pb2_grpc.EchoServiceStub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.GetEcho(echo_pb2.GetEchoRequest(id="missing"))

    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND
