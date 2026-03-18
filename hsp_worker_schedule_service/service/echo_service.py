from hsp_worker_schedule_service.domain.errors import NotFoundError, ValidationError
from hsp_worker_schedule_service.domain.models import EchoRecord, SourceType
from hsp_worker_schedule_service.repository.interfaces import EchoRepository


class EchoService:
    def __init__(self, repository: EchoRepository) -> None:
        self._repository = repository

    async def create_echo(self, message: str, source: SourceType) -> EchoRecord:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValidationError("message must not be empty")
        return await self._repository.create(normalized_message, source)

    async def get_echo(self, record_id: str) -> EchoRecord:
        normalized_id = record_id.strip()
        if not normalized_id:
            raise ValidationError("id must not be empty")

        record = await self._repository.get_by_id(normalized_id)
        if record is None:
            raise NotFoundError(f"echo record '{normalized_id}' not found")
        return record
