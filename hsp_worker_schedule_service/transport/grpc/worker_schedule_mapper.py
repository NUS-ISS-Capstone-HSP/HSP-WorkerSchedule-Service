from __future__ import annotations

from datetime import datetime
from typing import cast

from hsp_worker_schedule_service.domain.errors import ValidationError
from hsp_worker_schedule_service.domain.models import (
    OrderDetail,
    OrderEvent,
    OrderEventType,
    ScheduleTask,
    ScheduleTaskStatus,
    Worker,
    WorkerStatus,
)
from rpc.worker_schedule.v1 import worker_schedule_pb2


def parse_order_event(request: worker_schedule_pb2.SyncOrderEventRequest) -> OrderEvent:
    return OrderEvent(
        order_id=request.order_id,
        worker_id=request.worker_id,
        worker_name=request.worker_name,
        event_type=order_event_type_from_proto(request.event_type),
        start_time=parse_iso_datetime(request.start_time, "start_time"),
        end_time=parse_iso_datetime(request.end_time, "end_time"),
        title=request.title,
    )


def parse_iso_datetime(raw: str, field_name: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must follow ISO-8601 format") from exc
    if value.tzinfo is None:
        raise ValidationError(f"{field_name} must include timezone")
    return value


def to_worker_record(worker: Worker) -> worker_schedule_pb2.WorkerRecord:
    return worker_schedule_pb2.WorkerRecord(
        id=worker.id,
        name=worker.name,
        status=worker_status_to_proto(worker.status),
        updated_at=worker.updated_at.isoformat(),
    )


def to_schedule_task_record(
    task: ScheduleTask | OrderDetail,
    worker_name: str,
    has_conflict: bool,
) -> worker_schedule_pb2.ScheduleTaskRecord:
    return worker_schedule_pb2.ScheduleTaskRecord(
        order_id=task.order_id,
        worker_id=task.worker_id,
        worker_name=worker_name,
        title=task.title,
        start_time=task.start_time.isoformat(),
        end_time=task.end_time.isoformat(),
        status=schedule_task_status_to_proto(task.status),
        updated_at=task.updated_at.isoformat(),
        has_conflict=has_conflict,
    )


def worker_status_from_proto(status: int) -> WorkerStatus:
    mapping = {
        worker_schedule_pb2.WORKER_STATUS_AVAILABLE: WorkerStatus.AVAILABLE,
        worker_schedule_pb2.WORKER_STATUS_ASSIGNED: WorkerStatus.ASSIGNED,
        worker_schedule_pb2.WORKER_STATUS_IN_SERVICE: WorkerStatus.IN_SERVICE,
    }
    if status not in mapping:
        raise ValidationError("invalid worker status")
    return mapping[status]


def worker_status_to_proto(status: WorkerStatus) -> int:
    value = {
        WorkerStatus.AVAILABLE: worker_schedule_pb2.WORKER_STATUS_AVAILABLE,
        WorkerStatus.ASSIGNED: worker_schedule_pb2.WORKER_STATUS_ASSIGNED,
        WorkerStatus.IN_SERVICE: worker_schedule_pb2.WORKER_STATUS_IN_SERVICE,
    }[status]
    return cast(int, value)


def order_event_type_from_proto(event_type: int) -> OrderEventType:
    mapping = {
        worker_schedule_pb2.ORDER_EVENT_TYPE_ASSIGNED: OrderEventType.ASSIGNED,
        worker_schedule_pb2.ORDER_EVENT_TYPE_SERVICE_STARTED: OrderEventType.SERVICE_STARTED,
        worker_schedule_pb2.ORDER_EVENT_TYPE_COMPLETED: OrderEventType.COMPLETED,
        worker_schedule_pb2.ORDER_EVENT_TYPE_CANCELED: OrderEventType.CANCELED,
    }
    if event_type not in mapping:
        raise ValidationError("invalid order event type")
    return mapping[event_type]


def schedule_task_status_to_proto(status: ScheduleTaskStatus) -> int:
    value = {
        ScheduleTaskStatus.ASSIGNED: worker_schedule_pb2.SCHEDULE_TASK_STATUS_ASSIGNED,
        ScheduleTaskStatus.IN_SERVICE: worker_schedule_pb2.SCHEDULE_TASK_STATUS_IN_SERVICE,
        ScheduleTaskStatus.COMPLETED: worker_schedule_pb2.SCHEDULE_TASK_STATUS_COMPLETED,
        ScheduleTaskStatus.CANCELED: worker_schedule_pb2.SCHEDULE_TASK_STATUS_CANCELED,
    }[status]
    return cast(int, value)
