from dataclasses import dataclass

import grpc
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from hsp_worker_schedule_service.config import Settings, get_settings
from hsp_worker_schedule_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_worker_schedule_service.repository.in_memory import (
    InMemoryEchoRepository,
    InMemoryWorkerScheduleRepository,
)
from hsp_worker_schedule_service.repository.interfaces import (
    EchoRepository,
    WorkerScheduleRepository,
)
from hsp_worker_schedule_service.repository.mysql import (
    SQLAlchemyEchoRepository,
    SQLAlchemyWorkerScheduleRepository,
)
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.service.worker_schedule_service import WorkerScheduleService
from hsp_worker_schedule_service.transport.grpc.server import build_grpc_server
from hsp_worker_schedule_service.transport.http.app import create_http_app


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine | None
    session_factory: async_sessionmaker[AsyncSession] | None
    echo_repository: EchoRepository
    worker_schedule_repository: WorkerScheduleRepository
    echo_service: EchoService
    worker_schedule_service: WorkerScheduleService
    http_app: FastAPI
    grpc_server: grpc.aio.Server


async def build_container() -> AppContainer:
    settings = get_settings()
    repository: EchoRepository
    worker_schedule_repository: WorkerScheduleRepository

    if settings.use_mock_repository:
        engine = None
        session_factory = None
        repository = InMemoryEchoRepository()
        worker_schedule_repository = InMemoryWorkerScheduleRepository()
    else:
        engine = create_engine(settings.mysql_dsn)
        await init_db(engine)
        session_factory = create_session_factory(engine)
        repository = SQLAlchemyEchoRepository(session_factory)
        worker_schedule_repository = SQLAlchemyWorkerScheduleRepository(session_factory)

    echo_service = EchoService(repository)
    worker_schedule_service = WorkerScheduleService(worker_schedule_repository)
    http_app = create_http_app(echo_service)
    grpc_server = build_grpc_server(settings, echo_service, worker_schedule_service)

    return AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        echo_repository=repository,
        worker_schedule_repository=worker_schedule_repository,
        echo_service=echo_service,
        worker_schedule_service=worker_schedule_service,
        http_app=http_app,
        grpc_server=grpc_server,
    )
