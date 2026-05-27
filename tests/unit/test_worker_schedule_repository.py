from datetime import datetime
from pathlib import Path

import pytest

from hsp_worker_schedule_service.domain.models import OrderEvent, OrderEventType, WorkerStatus
from hsp_worker_schedule_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_worker_schedule_service.repository.mysql import SQLAlchemyWorkerScheduleRepository


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.mark.asyncio
async def test_sqlalchemy_worker_schedule_repository_basic_flow(tmp_path: Path) -> None:
    db_file = tmp_path / "worker_schedule.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)
    repository = SQLAlchemyWorkerScheduleRepository(create_session_factory(engine))

    worker = await repository.upsert_worker("w-1", "张三")
    assert worker.status == WorkerStatus.AVAILABLE

    await repository.apply_order_event(
        OrderEvent(
            order_id="o-1",
            worker_id="w-1",
            worker_name="张三",
            event_type=OrderEventType.ASSIGNED,
            start_time=_dt("2026-04-07T09:00:00+08:00"),
            end_time=_dt("2026-04-07T10:00:00+08:00"),
            title="空调清洗",
        ),
    )

    conflicts = await repository.find_conflicting_tasks(
        worker_id="w-1",
        start_time=_dt("2026-04-07T09:30:00+08:00"),
        end_time=_dt("2026-04-07T10:30:00+08:00"),
    )
    assert len(conflicts) == 1
    assert conflicts[0].order_id == "o-1"

    await engine.dispose()
