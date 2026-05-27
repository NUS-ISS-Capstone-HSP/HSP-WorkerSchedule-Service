from __future__ import annotations

import logging
from datetime import datetime

from hsp_worker_schedule_service.domain.errors import ConflictError, NotFoundError, ValidationError
from hsp_worker_schedule_service.domain.models import (
    OrderDetail,
    OrderEvent,
    OrderEventType,
    ScheduleTask,
    Worker,
    WorkerStatus,
)
from hsp_worker_schedule_service.repository.interfaces import WorkerScheduleRepository

logger = logging.getLogger(__name__)

ALLOWED_MANUAL_TRANSITIONS: dict[WorkerStatus, set[WorkerStatus]] = {
    WorkerStatus.AVAILABLE: {WorkerStatus.ASSIGNED},
    WorkerStatus.ASSIGNED: {WorkerStatus.IN_SERVICE, WorkerStatus.AVAILABLE},
    WorkerStatus.IN_SERVICE: {WorkerStatus.AVAILABLE},
}


class WorkerScheduleService:
    def __init__(self, repository: WorkerScheduleRepository) -> None:
        self._repository = repository

    async def register_worker(self, worker_id: str, worker_name: str) -> Worker:
        normalized_id = worker_id.strip()
        normalized_name = worker_name.strip()
        if not normalized_id:
            raise ValidationError("worker_id must not be empty")
        if not normalized_name:
            raise ValidationError("worker_name must not be empty")
        worker = await self._repository.upsert_worker(normalized_id, normalized_name)
        logger.info("worker_upserted worker_id=%s status=%s", worker.id, worker.status.value)
        return worker

    async def list_workers(self) -> list[Worker]:
        workers = await self._repository.list_workers()
        logger.debug("workers_listed count=%s", len(workers))
        return workers

    async def update_worker_status(
        self,
        worker_id: str,
        target_status: WorkerStatus,
        operator_id: str,
    ) -> Worker:
        worker = await self._repository.get_worker(worker_id)
        if worker is None:
            raise NotFoundError(f"worker '{worker_id}' not found")

        if worker.status == target_status:
            raise ValidationError(
                f"invalid status transition: {worker.status.value} -> {target_status.value}",
            )

        allowed = ALLOWED_MANUAL_TRANSITIONS.get(worker.status, set())
        if target_status not in allowed:
            raise ValidationError(
                f"invalid status transition: {worker.status.value} -> {target_status.value}",
            )

        updated = await self._repository.update_worker_status(worker_id, target_status)
        logger.info(
            "worker_status_updated worker_id=%s from=%s to=%s operator_id=%s",
            worker_id,
            worker.status.value,
            target_status.value,
            operator_id,
        )
        return updated

    async def apply_order_event(
        self,
        event: OrderEvent,
        operator_id: str,
    ) -> Worker:
        self._validate_order_event(event)
        worker = await self._repository.upsert_worker(event.worker_id, event.worker_name)

        if event.event_type == OrderEventType.ASSIGNED:
            conflicts = await self._repository.find_conflicting_tasks(
                worker_id=event.worker_id,
                start_time=event.start_time,
                end_time=event.end_time,
            )
            if conflicts:
                conflict_order_ids = ",".join(task.order_id for task in conflicts)
                logger.warning(
                    (
                        "schedule_conflict_rejected worker_id=%s order_id=%s "
                        "conflicts=%s operator_id=%s"
                    ),
                    event.worker_id,
                    event.order_id,
                    conflict_order_ids,
                    operator_id,
                )
                raise ConflictError(
                    f"schedule conflict detected for worker '{event.worker_id}', "
                    f"order_ids={conflict_order_ids}",
                )

        self._validate_status_transition_by_event(worker.status, event.event_type)
        updated_worker = await self._repository.apply_order_event(event)
        logger.info(
            "order_event_applied order_id=%s worker_id=%s event=%s new_status=%s operator_id=%s",
            event.order_id,
            event.worker_id,
            event.event_type.value,
            updated_worker.status.value,
            operator_id,
        )
        # TODO: integrate Order service RPC to enrich order payload consistency checks.
        return updated_worker

    async def list_schedule_by_date(self, local_date: str) -> list[ScheduleTask]:
        date_value = local_date.strip()
        if not date_value:
            raise ValidationError("date must not be empty")
        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValidationError("date must follow YYYY-MM-DD") from exc

        tasks = await self._repository.list_schedule_by_date(date_value)
        logger.debug("schedule_listed date=%s count=%s", date_value, len(tasks))
        return tasks

    async def get_order_detail(self, order_id: str) -> OrderDetail:
        normalized_order_id = order_id.strip()
        if not normalized_order_id:
            raise ValidationError("order_id must not be empty")

        detail = await self._repository.get_order_detail(normalized_order_id)
        if detail is None:
            raise NotFoundError(f"order '{normalized_order_id}' not found")
        logger.debug("order_detail_fetched order_id=%s", normalized_order_id)
        return detail

    def _validate_order_event(self, event: OrderEvent) -> None:
        if not event.order_id.strip():
            raise ValidationError("order_id must not be empty")
        if not event.worker_id.strip():
            raise ValidationError("worker_id must not be empty")
        if not event.worker_name.strip():
            raise ValidationError("worker_name must not be empty")
        if not event.title.strip():
            raise ValidationError("title must not be empty")
        if event.start_time.tzinfo is None or event.end_time.tzinfo is None:
            raise ValidationError("start_time and end_time must include timezone")
        if event.start_time >= event.end_time:
            raise ValidationError("start_time must be earlier than end_time")

    def _validate_status_transition_by_event(
        self,
        current_status: WorkerStatus,
        event_type: OrderEventType,
    ) -> None:
        expected_next = {
            OrderEventType.ASSIGNED: WorkerStatus.ASSIGNED,
            OrderEventType.SERVICE_STARTED: WorkerStatus.IN_SERVICE,
            OrderEventType.COMPLETED: WorkerStatus.AVAILABLE,
            OrderEventType.CANCELED: WorkerStatus.AVAILABLE,
        }[event_type]

        if current_status == expected_next and event_type != OrderEventType.ASSIGNED:
            raise ValidationError(
                f"invalid repeated event: worker already in status {current_status.value}",
            )

        if event_type == OrderEventType.SERVICE_STARTED and current_status != WorkerStatus.ASSIGNED:
            raise ValidationError(
                f"invalid status transition by event: {current_status.value} -> IN_SERVICE",
            )

        if event_type == OrderEventType.COMPLETED and current_status != WorkerStatus.IN_SERVICE:
            raise ValidationError(
                f"invalid status transition by event: {current_status.value} -> AVAILABLE",
            )
