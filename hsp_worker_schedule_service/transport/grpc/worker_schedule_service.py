from __future__ import annotations

import logging
from collections import defaultdict

import grpc

from hsp_worker_schedule_service.domain.errors import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from hsp_worker_schedule_service.domain.models import ScheduleTask, ScheduleTaskStatus
from hsp_worker_schedule_service.service.worker_schedule_service import WorkerScheduleService
from hsp_worker_schedule_service.transport.grpc.auth import Principal, require_principal
from hsp_worker_schedule_service.transport.grpc.worker_schedule_mapper import (
    parse_order_event,
    to_schedule_task_record,
    to_worker_record,
    worker_status_from_proto,
)
from rpc.worker_schedule.v1 import worker_schedule_pb2, worker_schedule_pb2_grpc

logger = logging.getLogger(__name__)


class WorkerScheduleGrpcService(worker_schedule_pb2_grpc.WorkerScheduleServiceServicer):
    def __init__(self, worker_schedule_service: WorkerScheduleService) -> None:
        self._service = worker_schedule_service

    async def RegisterWorker(
        self,
        request: worker_schedule_pb2.RegisterWorkerRequest,
        context: grpc.aio.ServicerContext,
    ) -> worker_schedule_pb2.RegisterWorkerResponse:
        principal = await self._authorize(context, "RegisterWorker")
        try:
            worker = await self._service.register_worker(
                worker_id=request.worker_id,
                worker_name=request.worker_name,
            )
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        logger.info(
            "grpc_register_worker_ok worker_id=%s user_id=%s user_role=%s",
            worker.id,
            principal.user_id,
            principal.user_role,
        )
        return worker_schedule_pb2.RegisterWorkerResponse(worker=to_worker_record(worker))

    async def ListWorkers(
        self,
        request: worker_schedule_pb2.ListWorkersRequest,
        context: grpc.aio.ServicerContext,
    ) -> worker_schedule_pb2.ListWorkersResponse:
        del request
        principal = await self._authorize(context, "ListWorkers")
        workers = await self._service.list_workers()
        logger.debug(
            "grpc_list_workers_ok count=%s user_id=%s user_role=%s",
            len(workers),
            principal.user_id,
            principal.user_role,
        )
        return worker_schedule_pb2.ListWorkersResponse(
            workers=[to_worker_record(worker) for worker in workers],
        )

    async def UpdateWorkerStatus(
        self,
        request: worker_schedule_pb2.UpdateWorkerStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> worker_schedule_pb2.UpdateWorkerStatusResponse:
        principal = await self._authorize(context, "UpdateWorkerStatus")
        try:
            worker = await self._service.update_worker_status(
                worker_id=request.worker_id,
                target_status=worker_status_from_proto(request.status),
                operator_id=principal.user_id,
            )
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))

        return worker_schedule_pb2.UpdateWorkerStatusResponse(worker=to_worker_record(worker))

    async def SyncOrderEvent(
        self,
        request: worker_schedule_pb2.SyncOrderEventRequest,
        context: grpc.aio.ServicerContext,
    ) -> worker_schedule_pb2.SyncOrderEventResponse:
        principal = await self._authorize(context, "SyncOrderEvent")
        try:
            event = parse_order_event(request)
            worker = await self._service.apply_order_event(event, operator_id=principal.user_id)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ConflictError as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))

        return worker_schedule_pb2.SyncOrderEventResponse(worker=to_worker_record(worker))

    async def ListDailySchedule(
        self,
        request: worker_schedule_pb2.ListDailyScheduleRequest,
        context: grpc.aio.ServicerContext,
    ) -> worker_schedule_pb2.ListDailyScheduleResponse:
        principal = await self._authorize(context, "ListDailySchedule")
        try:
            tasks = await self._service.list_schedule_by_date(request.date)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        worker_map = {worker.id: worker.name for worker in await self._service.list_workers()}
        conflict_order_ids = _detect_conflicts(tasks)
        records = [
            to_schedule_task_record(
                task=task,
                worker_name=worker_map.get(task.worker_id, ""),
                has_conflict=task.order_id in conflict_order_ids,
            )
            for task in tasks
        ]
        logger.debug(
            "grpc_list_daily_schedule_ok date=%s count=%s conflicts=%s user_id=%s user_role=%s",
            request.date,
            len(records),
            len(conflict_order_ids),
            principal.user_id,
            principal.user_role,
        )
        return worker_schedule_pb2.ListDailyScheduleResponse(tasks=records)

    async def GetOrderDetail(
        self,
        request: worker_schedule_pb2.GetOrderDetailRequest,
        context: grpc.aio.ServicerContext,
    ) -> worker_schedule_pb2.GetOrderDetailResponse:
        principal = await self._authorize(context, "GetOrderDetail")
        try:
            detail = await self._service.get_order_detail(request.order_id)
        except ValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except NotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))

        logger.debug(
            "grpc_get_order_detail_ok order_id=%s user_id=%s user_role=%s",
            request.order_id,
            principal.user_id,
            principal.user_role,
        )
        return worker_schedule_pb2.GetOrderDetailResponse(
            task=to_schedule_task_record(detail, detail.worker_name, has_conflict=False),
        )

    async def _authorize(
        self,
        context: grpc.aio.ServicerContext,
        method_name: str,
    ) -> Principal:
        try:
            return await require_principal(context, method_name)
        except UnauthorizedError as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
            raise AssertionError("unreachable") from exc


def _detect_conflicts(tasks: list[ScheduleTask]) -> set[str]:
    conflict_order_ids: set[str] = set()
    grouped: dict[str, list[ScheduleTask]] = defaultdict(list)
    for task in tasks:
        if task.status not in {ScheduleTaskStatus.ASSIGNED, ScheduleTaskStatus.IN_SERVICE}:
            continue
        grouped[task.worker_id].append(task)

    for worker_id in grouped:
        group = sorted(grouped[worker_id], key=lambda task: task.start_time)
        for index in range(1, len(group)):
            prev_task = group[index - 1]
            curr_task = group[index]
            if prev_task.end_time > curr_task.start_time:
                conflict_order_ids.add(prev_task.order_id)
                conflict_order_ids.add(curr_task.order_id)

    return conflict_order_ids
