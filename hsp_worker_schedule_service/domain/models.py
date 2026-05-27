from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SourceType(StrEnum):
    HTTP = "HTTP"
    GRPC = "GRPC"


@dataclass(slots=True)
class EchoRecord:
    id: str
    message: str
    source: SourceType
    created_at: datetime


class WorkerStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    IN_SERVICE = "IN_SERVICE"


class ScheduleTaskStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class OrderEventType(StrEnum):
    ASSIGNED = "ASSIGNED"
    SERVICE_STARTED = "SERVICE_STARTED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


@dataclass(slots=True)
class Worker:
    id: str
    name: str
    status: WorkerStatus
    updated_at: datetime


@dataclass(slots=True)
class ScheduleTask:
    id: str
    order_id: str
    worker_id: str
    title: str
    start_time: datetime
    end_time: datetime
    status: ScheduleTaskStatus
    updated_at: datetime


@dataclass(slots=True)
class OrderEvent:
    order_id: str
    worker_id: str
    worker_name: str
    event_type: OrderEventType
    start_time: datetime
    end_time: datetime
    title: str


@dataclass(slots=True)
class OrderDetail:
    order_id: str
    worker_id: str
    worker_name: str
    title: str
    start_time: datetime
    end_time: datetime
    status: ScheduleTaskStatus
    updated_at: datetime
