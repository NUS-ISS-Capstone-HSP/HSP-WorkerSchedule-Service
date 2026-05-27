from datetime import datetime

import grpc
import pytest
import pytest_asyncio

from hsp_worker_schedule_service.domain.models import ScheduleTask, ScheduleTaskStatus
from hsp_worker_schedule_service.repository.in_memory import InMemoryWorkerScheduleRepository
from hsp_worker_schedule_service.service.worker_schedule_service import WorkerScheduleService
from hsp_worker_schedule_service.transport.grpc.worker_schedule_service import (
    WorkerScheduleGrpcService,
    _detect_conflicts,
)
from rpc.worker_schedule.v1 import worker_schedule_pb2, worker_schedule_pb2_grpc


def _dt(value: str) -> str:
    return datetime.fromisoformat(value).isoformat()


@pytest_asyncio.fixture
async def grpc_stub() -> worker_schedule_pb2_grpc.WorkerScheduleServiceStub:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())

    server = grpc.aio.server()
    worker_schedule_pb2_grpc.add_WorkerScheduleServiceServicer_to_server(
        WorkerScheduleGrpcService(service),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = worker_schedule_pb2_grpc.WorkerScheduleServiceStub(channel)
    try:
        yield stub
    finally:
        await channel.close()
        await server.stop(0)


def _metadata() -> list[tuple[str, str]]:
    return [("x-user-id", "u-cs-1"), ("x-user-role", "csr")]


async def _register_worker(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
    worker_id: str,
    worker_name: str,
) -> None:
    await grpc_stub.RegisterWorker(
        worker_schedule_pb2.RegisterWorkerRequest(
            worker_id=worker_id,
            worker_name=worker_name,
        ),
        metadata=_metadata(),
    )


@pytest.mark.asyncio
async def test_worker_schedule_grpc_flow_success(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    registered = await grpc_stub.RegisterWorker(
        worker_schedule_pb2.RegisterWorkerRequest(worker_id="w-1", worker_name="张三"),
        metadata=_metadata(),
    )
    assert registered.worker.id == "w-1"
    assert registered.worker.status == worker_schedule_pb2.WORKER_STATUS_AVAILABLE

    assigned = await grpc_stub.SyncOrderEvent(
        worker_schedule_pb2.SyncOrderEventRequest(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_ASSIGNED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
        metadata=_metadata(),
    )
    assert assigned.worker.status == worker_schedule_pb2.WORKER_STATUS_ASSIGNED

    started = await grpc_stub.SyncOrderEvent(
        worker_schedule_pb2.SyncOrderEventRequest(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_SERVICE_STARTED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
        metadata=_metadata(),
    )
    assert started.worker.status == worker_schedule_pb2.WORKER_STATUS_IN_SERVICE

    completed = await grpc_stub.SyncOrderEvent(
        worker_schedule_pb2.SyncOrderEventRequest(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_COMPLETED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
        metadata=_metadata(),
    )
    assert completed.worker.status == worker_schedule_pb2.WORKER_STATUS_AVAILABLE

    schedule = await grpc_stub.ListDailySchedule(
        worker_schedule_pb2.ListDailyScheduleRequest(date="2026-04-07"),
        metadata=_metadata(),
    )
    assert len(schedule.tasks) == 1
    assert schedule.tasks[0].order_id == "o-1"

    detail = await grpc_stub.GetOrderDetail(
        worker_schedule_pb2.GetOrderDetailRequest(order_id="o-1"),
        metadata=_metadata(),
    )
    assert detail.task.order_id == "o-1"
    assert detail.task.worker_id == "w-1"


@pytest.mark.asyncio
async def test_list_workers_success(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    await _register_worker(grpc_stub, "w-a", "张三")
    await _register_worker(grpc_stub, "w-b", "李四")

    response = await grpc_stub.ListWorkers(
        worker_schedule_pb2.ListWorkersRequest(),
        metadata=_metadata(),
    )

    worker_ids = [worker.id for worker in response.workers]
    assert worker_ids == ["w-a", "w-b"]


@pytest.mark.asyncio
async def test_update_worker_status_success(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    await _register_worker(grpc_stub, "w-2", "王五")

    assigned = await grpc_stub.UpdateWorkerStatus(
        worker_schedule_pb2.UpdateWorkerStatusRequest(
            worker_id="w-2",
            status=worker_schedule_pb2.WORKER_STATUS_ASSIGNED,
        ),
        metadata=_metadata(),
    )
    assert assigned.worker.status == worker_schedule_pb2.WORKER_STATUS_ASSIGNED

    serving = await grpc_stub.UpdateWorkerStatus(
        worker_schedule_pb2.UpdateWorkerStatusRequest(
            worker_id="w-2",
            status=worker_schedule_pb2.WORKER_STATUS_IN_SERVICE,
        ),
        metadata=_metadata(),
    )
    assert serving.worker.status == worker_schedule_pb2.WORKER_STATUS_IN_SERVICE


@pytest.mark.asyncio
async def test_update_worker_status_invalid_argument(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    await _register_worker(grpc_stub, "w-3", "赵六")

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.UpdateWorkerStatus(
            worker_schedule_pb2.UpdateWorkerStatusRequest(
                worker_id="w-3",
                status=worker_schedule_pb2.WORKER_STATUS_IN_SERVICE,
            ),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_update_worker_status_not_found(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.UpdateWorkerStatus(
            worker_schedule_pb2.UpdateWorkerStatusRequest(
                worker_id="w-missing",
                status=worker_schedule_pb2.WORKER_STATUS_ASSIGNED,
            ),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_sync_order_event_conflict_failed_precondition(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    await _register_worker(grpc_stub, "w-4", "陈七")

    await grpc_stub.SyncOrderEvent(
        worker_schedule_pb2.SyncOrderEventRequest(
            order_id="o-10",
            worker_id="w-4",
            worker_name="陈七",
            event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_ASSIGNED,
            start_time=_dt("2026-04-07T11:00:00+08:00"),
            end_time=_dt("2026-04-07T12:00:00+08:00"),
            title="一次保洁",
        ),
        metadata=_metadata(),
    )

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.SyncOrderEvent(
            worker_schedule_pb2.SyncOrderEventRequest(
                order_id="o-11",
                worker_id="w-4",
                worker_name="陈七",
                event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_ASSIGNED,
                start_time=_dt("2026-04-07T11:30:00+08:00"),
                end_time=_dt("2026-04-07T12:30:00+08:00"),
                title="深度保洁",
            ),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.FAILED_PRECONDITION


@pytest.mark.asyncio
async def test_sync_order_event_canceled_back_to_available(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    await _register_worker(grpc_stub, "w-5", "周八")

    await grpc_stub.SyncOrderEvent(
        worker_schedule_pb2.SyncOrderEventRequest(
            order_id="o-20",
            worker_id="w-5",
            worker_name="周八",
            event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_ASSIGNED,
            start_time=_dt("2026-04-07T14:00:00+08:00"),
            end_time=_dt("2026-04-07T15:00:00+08:00"),
            title="油烟机清洗",
        ),
        metadata=_metadata(),
    )

    canceled = await grpc_stub.SyncOrderEvent(
        worker_schedule_pb2.SyncOrderEventRequest(
            order_id="o-20",
            worker_id="w-5",
            worker_name="周八",
            event_type=worker_schedule_pb2.ORDER_EVENT_TYPE_CANCELED,
            start_time=_dt("2026-04-07T14:00:00+08:00"),
            end_time=_dt("2026-04-07T15:00:00+08:00"),
            title="油烟机清洗",
        ),
        metadata=_metadata(),
    )
    assert canceled.worker.status == worker_schedule_pb2.WORKER_STATUS_AVAILABLE


@pytest.mark.asyncio
async def test_list_daily_schedule_invalid_date(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.ListDailySchedule(
            worker_schedule_pb2.ListDailyScheduleRequest(date="2026/04/07"),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_list_daily_schedule_empty_date(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.ListDailySchedule(
            worker_schedule_pb2.ListDailyScheduleRequest(date=""),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_get_order_detail_not_found(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.GetOrderDetail(
            worker_schedule_pb2.GetOrderDetailRequest(order_id="not-exists"),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_sync_order_event_invalid_event_type(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    await _register_worker(grpc_stub, "w-7", "吴九")

    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.SyncOrderEvent(
            worker_schedule_pb2.SyncOrderEventRequest(
                order_id="o-70",
                worker_id="w-7",
                worker_name="吴九",
                event_type=999,
                start_time=_dt("2026-04-07T09:00:00+08:00"),
                end_time=_dt("2026-04-07T10:00:00+08:00"),
                title="无效事件",
            ),
            metadata=_metadata(),
        )

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_worker_schedule_grpc_missing_metadata_unauthenticated(
    grpc_stub: worker_schedule_pb2_grpc.WorkerScheduleServiceStub,
) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await grpc_stub.ListWorkers(worker_schedule_pb2.ListWorkersRequest())

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_detect_conflicts_only_counts_active_tasks() -> None:
    tasks = [
        ScheduleTask(
            id="t-1",
            order_id="o-1",
            worker_id="w-1",
            title="任务1",
            start_time=datetime.fromisoformat("2026-04-07T09:00:00+08:00"),
            end_time=datetime.fromisoformat("2026-04-07T10:00:00+08:00"),
            status=ScheduleTaskStatus.COMPLETED,
            updated_at=datetime.fromisoformat("2026-04-07T10:00:00+08:00"),
        ),
        ScheduleTask(
            id="t-2",
            order_id="o-2",
            worker_id="w-1",
            title="任务2",
            start_time=datetime.fromisoformat("2026-04-07T09:30:00+08:00"),
            end_time=datetime.fromisoformat("2026-04-07T10:30:00+08:00"),
            status=ScheduleTaskStatus.CANCELED,
            updated_at=datetime.fromisoformat("2026-04-07T10:30:00+08:00"),
        ),
    ]

    assert _detect_conflicts(tasks) == set()
