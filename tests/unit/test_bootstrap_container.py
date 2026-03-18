from pathlib import Path

import pytest

from hsp_worker_schedule_service.bootstrap.container import build_container
from hsp_worker_schedule_service.config import get_settings
from hsp_worker_schedule_service.domain.models import SourceType
from hsp_worker_schedule_service.repository.in_memory import InMemoryEchoRepository
from hsp_worker_schedule_service.repository.mysql import SQLAlchemyEchoRepository


@pytest.mark.asyncio
async def test_build_container_with_mock_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MOCK_REPOSITORY", "true")
    monkeypatch.setenv("MYSQL_DSN", "mysql+aiomysql://not-used")
    monkeypatch.setenv("GRPC_PORT", "0")
    get_settings.cache_clear()

    container = await build_container()

    assert isinstance(container.echo_repository, InMemoryEchoRepository)
    assert container.engine is None
    assert container.session_factory is None

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_build_container_with_sqlalchemy_repository(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "container.db"
    monkeypatch.setenv("USE_MOCK_REPOSITORY", "false")
    monkeypatch.setenv("MYSQL_DSN", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("GRPC_PORT", "0")
    get_settings.cache_clear()

    container = await build_container()

    assert isinstance(container.echo_repository, SQLAlchemyEchoRepository)
    assert container.engine is not None
    assert container.session_factory is not None

    created = await container.echo_service.create_echo("from-container", SourceType.HTTP)
    fetched = await container.echo_service.get_echo(created.id)
    assert fetched.id == created.id

    if container.engine is not None:
        await container.engine.dispose()
    get_settings.cache_clear()
