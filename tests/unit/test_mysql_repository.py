from pathlib import Path

import pytest

from hsp_worker_schedule_service.domain.models import SourceType
from hsp_worker_schedule_service.infrastructure.db import (
    create_engine,
    create_session_factory,
    init_db,
)
from hsp_worker_schedule_service.repository.mysql import SQLAlchemyEchoRepository


@pytest.mark.asyncio
async def test_sqlalchemy_repository_create_and_get(tmp_path: Path) -> None:
    db_file = tmp_path / "echo.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyEchoRepository(create_session_factory(engine))

    created = await repository.create("repo-message", SourceType.GRPC)
    fetched = await repository.get_by_id(created.id)

    assert created.message == "repo-message"
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.source == SourceType.GRPC

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlalchemy_repository_get_missing_returns_none(tmp_path: Path) -> None:
    db_file = tmp_path / "echo.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(engine)

    repository = SQLAlchemyEchoRepository(create_session_factory(engine))

    fetched = await repository.get_by_id("missing-id")
    assert fetched is None

    await engine.dispose()
