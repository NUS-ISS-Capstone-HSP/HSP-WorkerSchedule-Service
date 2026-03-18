from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SourceType(StrEnum):
    HTTP = "HTTP"
    GRPC = "GRPC"


@dataclass(slots=True)
class EchoRecord:
    id: str
    message: str
    source: SourceType
    created_at: datetime
