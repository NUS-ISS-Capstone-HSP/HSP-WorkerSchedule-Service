from datetime import datetime

import pytest

from hsp_worker_schedule_service.domain.errors import ConflictError, ValidationError
from hsp_worker_schedule_service.domain.models import OrderEvent, OrderEventType, WorkerStatus
from hsp_worker_schedule_service.repository.in_memory import InMemoryWorkerScheduleRepository
from hsp_worker_schedule_service.service.worker_schedule_service import WorkerScheduleService


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.mark.asyncio
async def test_order_event_drives_worker_status_success() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())
    await service.register_worker("w-1", "张三")

    assigned_worker = await service.apply_order_event(
        OrderEvent(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=OrderEventType.ASSIGNED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
        operator_id="u-cs-1",
    )
    assert assigned_worker.status == WorkerStatus.ASSIGNED

    serving_worker = await service.apply_order_event(
        OrderEvent(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=OrderEventType.SERVICE_STARTED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
        operator_id="u-cs-1",
    )
    assert serving_worker.status == WorkerStatus.IN_SERVICE

    done_worker = await service.apply_order_event(
        OrderEvent(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=OrderEventType.COMPLETED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
        operator_id="u-cs-1",
    )
    assert done_worker.status == WorkerStatus.AVAILABLE


@pytest.mark.asyncio
async def test_assign_conflict_raises_conflict_error() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())
    await service.register_worker("w-2", "李四")

    await service.apply_order_event(
        OrderEvent(
            order_id="o-2",
            worker_id="w-2",
            worker_name="李四",
            event_type=OrderEventType.ASSIGNED,
            start_time=_dt("2026-04-07T11:00:00+08:00"),
            end_time=_dt("2026-04-07T12:00:00+08:00"),
            title="保洁",
        ),
        operator_id="u-cs-1",
    )

    with pytest.raises(ConflictError):
        await service.apply_order_event(
            OrderEvent(
                order_id="o-3",
                worker_id="w-2",
                worker_name="李四",
                event_type=OrderEventType.ASSIGNED,
                start_time=_dt("2026-04-07T11:30:00+08:00"),
                end_time=_dt("2026-04-07T12:30:00+08:00"),
                title="深度保洁",
            ),
            operator_id="u-cs-1",
        )


@pytest.mark.asyncio
async def test_manual_invalid_status_transition_raises_validation_error() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())
    await service.register_worker("w-3", "王五")

    with pytest.raises(ValidationError):
        await service.update_worker_status(
            worker_id="w-3",
            target_status=WorkerStatus.IN_SERVICE,
            operator_id="u-cs-1",
        )


@pytest.mark.asyncio
async def test_service_started_without_assignment_raises_validation_error() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())
    await service.register_worker("w-4", "赵六")

    with pytest.raises(ValidationError):
        await service.apply_order_event(
            OrderEvent(
                order_id="o-4",
                worker_id="w-4",
                worker_name="赵六",
                event_type=OrderEventType.SERVICE_STARTED,
                start_time=_dt("2026-04-07T09:00:00+08:00"),
                end_time=_dt("2026-04-07T10:00:00+08:00"),
                title="上门维修",
            ),
            operator_id="u-cs-1",
        )


@pytest.mark.asyncio
async def test_completed_without_in_service_raises_validation_error() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())
    await service.register_worker("w-5", "孙七")

    await service.apply_order_event(
        OrderEvent(
            order_id="o-5",
            worker_id="w-5",
            worker_name="孙七",
            event_type=OrderEventType.ASSIGNED,
            start_time=_dt("2026-04-07T10:00:00+08:00"),
            end_time=_dt("2026-04-07T11:00:00+08:00"),
            title="电路检修",
        ),
        operator_id="u-cs-1",
    )

    with pytest.raises(ValidationError):
        await service.apply_order_event(
            OrderEvent(
                order_id="o-5",
                worker_id="w-5",
                worker_name="孙七",
                event_type=OrderEventType.COMPLETED,
                start_time=_dt("2026-04-07T10:00:00+08:00"),
                end_time=_dt("2026-04-07T11:00:00+08:00"),
                title="电路检修",
            ),
            operator_id="u-cs-1",
        )


@pytest.mark.asyncio
async def test_list_schedule_invalid_date_raises_validation_error() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())

    with pytest.raises(ValidationError):
        await service.list_schedule_by_date("2026/04/07")


@pytest.mark.asyncio
async def test_register_worker_empty_fields_raise_validation_error() -> None:
    service = WorkerScheduleService(InMemoryWorkerScheduleRepository())

    with pytest.raises(ValidationError):
        await service.register_worker("", "张三")

    with pytest.raises(ValidationError):
        await service.register_worker("w-6", "")
