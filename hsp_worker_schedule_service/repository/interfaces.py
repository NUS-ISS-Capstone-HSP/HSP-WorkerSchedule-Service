from datetime import datetime
from typing import Protocol

from hsp_worker_schedule_service.domain.models import (
    EchoRecord,
    OrderDetail,
    OrderEvent,
    ScheduleTask,
    SourceType,
    Worker,
    WorkerStatus,
)


class EchoRepository(Protocol):
    async def create(self, message: str, source: SourceType) -> EchoRecord:
        ...

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        ...


class WorkerScheduleRepository(Protocol):
    async def upsert_worker(self, worker_id: str, worker_name: str) -> Worker:
        ...

    async def list_workers(self) -> list[Worker]:
        ...

    async def get_worker(self, worker_id: str) -> Worker | None:
        ...

    async def update_worker_status(
        self,
        worker_id: str,
        status: WorkerStatus,
    ) -> Worker:
        ...

    async def find_conflicting_tasks(
        self,
        worker_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[ScheduleTask]:
        ...

    async def apply_order_event(self, event: OrderEvent) -> Worker:
        ...

    async def list_schedule_by_date(self, local_date: str) -> list[ScheduleTask]:
        ...

    async def get_order_detail(self, order_id: str) -> OrderDetail | None:
        ...
