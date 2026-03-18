from typing import Protocol

from hsp_worker_schedule_service.domain.models import EchoRecord, SourceType


class EchoRepository(Protocol):
    async def create(self, message: str, source: SourceType) -> EchoRecord:
        ...

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        ...
