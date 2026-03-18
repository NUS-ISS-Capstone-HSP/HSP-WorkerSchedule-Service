from hsp_worker_schedule_service.domain.models import EchoRecord
from hsp_worker_schedule_service.transport.http.schemas import EchoRecordResponse


def to_http_response(record: EchoRecord) -> EchoRecordResponse:
    return EchoRecordResponse(
        id=record.id,
        message=record.message,
        source=record.source.value,
        created_at=record.created_at.isoformat(),
    )
