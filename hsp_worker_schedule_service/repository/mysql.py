from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from hsp_worker_schedule_service.infrastructure.orm import EchoRecordORM, ScheduleTaskORM, WorkerORM
from hsp_worker_schedule_service.repository.interfaces import (
    EchoRepository,
    WorkerScheduleRepository,
)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class SQLAlchemyEchoRepository(EchoRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, message: str, source: SourceType) -> EchoRecord:
        row = EchoRecordORM(
            id=str(uuid4()),
            message=message,
            source=source.value,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _to_domain(row)

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        async with self._session_factory() as session:
            stmt = select(EchoRecordORM).where(EchoRecordORM.id == record_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)


def _to_domain(row: EchoRecordORM) -> EchoRecord:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return EchoRecord(
        id=row.id,
        message=row.message,
        source=SourceType(row.source),
        created_at=created_at,
    )


class SQLAlchemyWorkerScheduleRepository(WorkerScheduleRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_worker(self, worker_id: str, worker_name: str) -> Worker:
        async with self._session_factory() as session:
            stmt = select(WorkerORM).where(WorkerORM.id == worker_id)
            worker = (await session.execute(stmt)).scalar_one_or_none()
            now = datetime.now(UTC)
            if worker is None:
                worker = WorkerORM(
                    id=worker_id,
                    name=worker_name,
                    status=WorkerStatus.AVAILABLE.value,
                    updated_at=now,
                )
                session.add(worker)
            else:
                worker.name = worker_name
                worker.updated_at = now

            await session.commit()
            await session.refresh(worker)
            return _to_worker(worker)

    async def list_workers(self) -> list[Worker]:
        async with self._session_factory() as session:
            stmt = select(WorkerORM).order_by(WorkerORM.id.asc())
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_worker(row) for row in rows]

    async def get_worker(self, worker_id: str) -> Worker | None:
        async with self._session_factory() as session:
            stmt = select(WorkerORM).where(WorkerORM.id == worker_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _to_worker(row)

    async def update_worker_status(
        self,
        worker_id: str,
        status: WorkerStatus,
    ) -> Worker:
        async with self._session_factory() as session:
            stmt = select(WorkerORM).where(WorkerORM.id == worker_id)
            worker = (await session.execute(stmt)).scalar_one_or_none()
            if worker is None:
                raise NotFoundError(f"worker '{worker_id}' not found")

            worker.status = status.value
            worker.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(worker)
            return _to_worker(worker)

    async def find_conflicting_tasks(
        self,
        worker_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[ScheduleTask]:
        async with self._session_factory() as session:
            stmt = (
                select(ScheduleTaskORM)
                .where(ScheduleTaskORM.worker_id == worker_id)
                .where(
                    ScheduleTaskORM.status.in_(
                        [
                            ScheduleTaskStatus.ASSIGNED.value,
                            ScheduleTaskStatus.IN_SERVICE.value,
                        ],
                    ),
                )
                .where(ScheduleTaskORM.start_time < end_time)
                .where(ScheduleTaskORM.end_time > start_time)
                .order_by(ScheduleTaskORM.start_time.asc())
            )
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_schedule_task(row) for row in rows]

    async def apply_order_event(self, event: OrderEvent) -> Worker:
        async with self._session_factory() as session:
            now = datetime.now(UTC)
            worker_stmt = select(WorkerORM).where(WorkerORM.id == event.worker_id)
            worker = (await session.execute(worker_stmt)).scalar_one_or_none()
            if worker is None:
                worker = WorkerORM(
                    id=event.worker_id,
                    name=event.worker_name,
                    status=WorkerStatus.AVAILABLE.value,
                    updated_at=now,
                )
                session.add(worker)
                await session.flush()
            else:
                worker.name = event.worker_name

            task_stmt = select(ScheduleTaskORM).where(ScheduleTaskORM.order_id == event.order_id)
            task = (await session.execute(task_stmt)).scalar_one_or_none()

            if event.event_type == OrderEventType.ASSIGNED:
                if task is None:
                    task = ScheduleTaskORM(
                        id=str(uuid4()),
                        order_id=event.order_id,
                        worker_id=event.worker_id,
                        title=event.title,
                        start_time=event.start_time,
                        end_time=event.end_time,
                        status=ScheduleTaskStatus.ASSIGNED.value,
                        updated_at=now,
                    )
                    session.add(task)
                else:
                    task.worker_id = event.worker_id
                    task.title = event.title
                    task.start_time = event.start_time
                    task.end_time = event.end_time
                    task.status = ScheduleTaskStatus.ASSIGNED.value
                    task.updated_at = now
            else:
                if task is None:
                    raise NotFoundError(f"order '{event.order_id}' not found")
                task.title = event.title
                task.start_time = event.start_time
                task.end_time = event.end_time
                task.status = {
                    OrderEventType.SERVICE_STARTED: ScheduleTaskStatus.IN_SERVICE.value,
                    OrderEventType.COMPLETED: ScheduleTaskStatus.COMPLETED.value,
                    OrderEventType.CANCELED: ScheduleTaskStatus.CANCELED.value,
                }[event.event_type]
                task.updated_at = now

            await session.flush()
            worker.status = await self._derive_worker_status(session, event.worker_id)
            worker.updated_at = now
            await session.commit()
            await session.refresh(worker)
            return _to_worker(worker)

    async def list_schedule_by_date(self, local_date: str) -> list[ScheduleTask]:
        async with self._session_factory() as session:
            stmt = select(ScheduleTaskORM).order_by(ScheduleTaskORM.start_time.asc())
            rows = (await session.execute(stmt)).scalars().all()
        tasks = []
        for row in rows:
            start_time = _normalize_datetime(row.start_time)
            if start_time.astimezone(SHANGHAI_TZ).date().isoformat() == local_date:
                tasks.append(_to_schedule_task(row))
        return tasks

    async def get_order_detail(self, order_id: str) -> OrderDetail | None:
        async with self._session_factory() as session:
            task_stmt = select(ScheduleTaskORM).where(ScheduleTaskORM.order_id == order_id)
            task = (await session.execute(task_stmt)).scalar_one_or_none()
            if task is None:
                return None

            worker_stmt = select(WorkerORM).where(WorkerORM.id == task.worker_id)
            worker = (await session.execute(worker_stmt)).scalar_one_or_none()
            worker_name = worker.name if worker is not None else ""
            return _to_order_detail(task, worker_name)

    async def _derive_worker_status(
        self,
        session: AsyncSession,
        worker_id: str,
    ) -> str:
        in_service_stmt = (
            select(ScheduleTaskORM.id)
            .where(ScheduleTaskORM.worker_id == worker_id)
            .where(ScheduleTaskORM.status == ScheduleTaskStatus.IN_SERVICE.value)
            .limit(1)
        )
        in_service_task = (await session.execute(in_service_stmt)).scalar_one_or_none()
        if in_service_task is not None:
            return WorkerStatus.IN_SERVICE.value

        assigned_stmt = (
            select(ScheduleTaskORM.id)
            .where(ScheduleTaskORM.worker_id == worker_id)
            .where(ScheduleTaskORM.status == ScheduleTaskStatus.ASSIGNED.value)
            .limit(1)
        )
        assigned_task = (await session.execute(assigned_stmt)).scalar_one_or_none()
        if assigned_task is not None:
            return WorkerStatus.ASSIGNED.value

        return WorkerStatus.AVAILABLE.value


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_worker(row: WorkerORM) -> Worker:
    return Worker(
        id=row.id,
        name=row.name,
        status=WorkerStatus(row.status),
        updated_at=_normalize_datetime(row.updated_at),
    )


def _to_schedule_task(row: ScheduleTaskORM) -> ScheduleTask:
    return ScheduleTask(
        id=row.id,
        order_id=row.order_id,
        worker_id=row.worker_id,
        title=row.title,
        start_time=_normalize_datetime(row.start_time),
        end_time=_normalize_datetime(row.end_time),
        status=ScheduleTaskStatus(row.status),
        updated_at=_normalize_datetime(row.updated_at),
    )


def _to_order_detail(row: ScheduleTaskORM, worker_name: str) -> OrderDetail:
    return OrderDetail(
        order_id=row.order_id,
        worker_id=row.worker_id,
        worker_name=worker_name,
        title=row.title,
        start_time=_normalize_datetime(row.start_time),
        end_time=_normalize_datetime(row.end_time),
        status=ScheduleTaskStatus(row.status),
        updated_at=_normalize_datetime(row.updated_at),
    )
