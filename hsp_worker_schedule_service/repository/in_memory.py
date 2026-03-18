from datetime import UTC, datetime
from uuid import uuid4

from hsp_worker_schedule_service.domain.models import EchoRecord, SourceType
from hsp_worker_schedule_service.repository.interfaces import EchoRepository


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
