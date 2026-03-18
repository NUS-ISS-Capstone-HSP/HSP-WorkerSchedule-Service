import pytest

from hsp_worker_schedule_service.domain.errors import NotFoundError, ValidationError
from hsp_worker_schedule_service.domain.models import SourceType
from hsp_worker_schedule_service.repository.in_memory import InMemoryEchoRepository
from hsp_worker_schedule_service.service.echo_service import EchoService


@pytest.mark.asyncio
async def test_create_and_get_echo_success() -> None:
    service = EchoService(InMemoryEchoRepository())

    created = await service.create_echo(" hello ", SourceType.HTTP)
    fetched = await service.get_echo(created.id)

    assert created.message == "hello"
    assert fetched.id == created.id
    assert fetched.source == SourceType.HTTP


@pytest.mark.asyncio
async def test_create_echo_empty_message_raises_validation_error() -> None:
    service = EchoService(InMemoryEchoRepository())

    with pytest.raises(ValidationError):
        await service.create_echo("   ", SourceType.HTTP)


@pytest.mark.asyncio
async def test_get_echo_not_found_raises_not_found_error() -> None:
    service = EchoService(InMemoryEchoRepository())

    with pytest.raises(NotFoundError):
        await service.get_echo("missing-id")
