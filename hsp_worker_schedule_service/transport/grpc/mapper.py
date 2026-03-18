from hsp_worker_schedule_service.domain.models import EchoRecord
from rpc.echo.v1 import echo_pb2


def to_grpc_record(record: EchoRecord) -> echo_pb2.EchoRecord:
    return echo_pb2.EchoRecord(
        id=record.id,
        message=record.message,
        source=record.source.value,
        created_at=record.created_at.isoformat(),
    )
