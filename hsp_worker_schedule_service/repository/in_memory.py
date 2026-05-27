from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from hsp_worker_schedule_service.domain.errors import NotFoundError
from hsp_worker_schedule_service.domain.models import (
    EchoRecord,
    OrderDetail,
    OrderEvent,
    OrderEventType,
    ScheduleTask,
    ScheduleTaskStatus,
    SourceType,
    Worker,
    WorkerStatus,
)
from hsp_worker_schedule_service.repository.interfaces import (
    EchoRepository,
    WorkerScheduleRepository,
)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class InMemoryEchoRepository(EchoRepository):
    def __init__(self) -> None:
        self._store: dict[str, EchoRecord] = {}

    async def create(self, message: str, source: SourceType) -> EchoRecord:
        record = EchoRecord(
            id=str(uuid4()),
            message=message,
            source=source,
            created_at=datetime.now(UTC),
        )
        self._store[record.id] = record
        return record

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        return self._store.get(record_id)


class InMemoryWorkerScheduleRepository(WorkerScheduleRepository):
    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}
        self._tasks_by_order: dict[str, ScheduleTask] = {}

    async def upsert_worker(self, worker_id: str, worker_name: str) -> Worker:
        now = datetime.now(UTC)
        existing = self._workers.get(worker_id)
        if existing is None:
            worker = Worker(
                id=worker_id,
                name=worker_name,
                status=WorkerStatus.AVAILABLE,
                updated_at=now,
            )
            self._workers[worker_id] = worker
            return worker

        worker = Worker(
            id=existing.id,
            name=worker_name,
            status=existing.status,
            updated_at=now,
        )
        self._workers[worker_id] = worker
        return worker

    async def list_workers(self) -> list[Worker]:
        return sorted(self._workers.values(), key=lambda worker: worker.id)

    async def get_worker(self, worker_id: str) -> Worker | None:
        return self._workers.get(worker_id)

    async def update_worker_status(
        self,
        worker_id: str,
        status: WorkerStatus,
    ) -> Worker:
        worker = self._workers.get(worker_id)
        if worker is None:
            raise NotFoundError(f"worker '{worker_id}' not found")

        updated = Worker(
            id=worker.id,
            name=worker.name,
            status=status,
            updated_at=datetime.now(UTC),
        )
        self._workers[worker_id] = updated
        return updated

    async def find_conflicting_tasks(
        self,
        worker_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[ScheduleTask]:
        tasks = []
        for task in self._tasks_by_order.values():
            if task.worker_id != worker_id:
                continue
            if task.status not in {ScheduleTaskStatus.ASSIGNED, ScheduleTaskStatus.IN_SERVICE}:
                continue
            if task.start_time < end_time and task.end_time > start_time:
                tasks.append(task)
        return sorted(tasks, key=lambda task: task.start_time)

    async def apply_order_event(self, event: OrderEvent) -> Worker:
        now = datetime.now(UTC)
        if event.event_type == OrderEventType.ASSIGNED:
            task = ScheduleTask(
                id=str(uuid4()),
                order_id=event.order_id,
                worker_id=event.worker_id,
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                status=ScheduleTaskStatus.ASSIGNED,
                updated_at=now,
            )
            self._tasks_by_order[event.order_id] = task
        else:
            existing_task = self._tasks_by_order.get(event.order_id)
            if existing_task is None:
                raise NotFoundError(f"order '{event.order_id}' not found")

            next_status = {
                OrderEventType.SERVICE_STARTED: ScheduleTaskStatus.IN_SERVICE,
                OrderEventType.COMPLETED: ScheduleTaskStatus.COMPLETED,
                OrderEventType.CANCELED: ScheduleTaskStatus.CANCELED,
            }[event.event_type]
            task = ScheduleTask(
                id=existing_task.id,
                order_id=existing_task.order_id,
                worker_id=existing_task.worker_id,
                title=event.title or existing_task.title,
                start_time=event.start_time,
                end_time=event.end_time,
                status=next_status,
                updated_at=now,
            )
            self._tasks_by_order[event.order_id] = task

        worker = self._workers.get(event.worker_id)
        if worker is None:
            worker = Worker(
                id=event.worker_id,
                name=event.worker_name,
                status=WorkerStatus.AVAILABLE,
                updated_at=now,
            )
        next_worker_status = self._derive_worker_status(event.worker_id)
        updated_worker = Worker(
            id=worker.id,
            name=event.worker_name or worker.name,
            status=next_worker_status,
            updated_at=now,
        )
        self._workers[event.worker_id] = updated_worker
        return updated_worker

    async def list_schedule_by_date(self, local_date: str) -> list[ScheduleTask]:
        tasks = [
            task
            for task in self._tasks_by_order.values()
            if task.start_time.astimezone(SHANGHAI_TZ).date().isoformat() == local_date
        ]
        return sorted(tasks, key=lambda task: task.start_time)

    async def get_order_detail(self, order_id: str) -> OrderDetail | None:
        task = self._tasks_by_order.get(order_id)
        if task is None:
            return None
        worker = self._workers.get(task.worker_id)
        return OrderDetail(
            order_id=task.order_id,
            worker_id=task.worker_id,
            worker_name=worker.name if worker is not None else "",
            title=task.title,
            start_time=task.start_time,
            end_time=task.end_time,
            status=task.status,
            updated_at=task.updated_at,
        )

    def _derive_worker_status(self, worker_id: str) -> WorkerStatus:
        has_in_service = any(
            task.worker_id == worker_id and task.status == ScheduleTaskStatus.IN_SERVICE
            for task in self._tasks_by_order.values()
        )
        if has_in_service:
            return WorkerStatus.IN_SERVICE

        has_assigned = any(
            task.worker_id == worker_id and task.status == ScheduleTaskStatus.ASSIGNED
            for task in self._tasks_by_order.values()
        )
        if has_assigned:
            return WorkerStatus.ASSIGNED

        return WorkerStatus.AVAILABLE
