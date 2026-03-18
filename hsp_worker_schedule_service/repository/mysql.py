from datetime import UTC
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hsp_worker_schedule_service.domain.models import EchoRecord, SourceType
from hsp_worker_schedule_service.infrastructure.orm import EchoRecordORM
from hsp_worker_schedule_service.repository.interfaces import EchoRepository


class SQLAlchemyEchoRepository(EchoRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, message: str, source: SourceType) -> EchoRecord:
        row = EchoRecordORM(
            id=str(uuid4()),
            message=message,
            source=source.value,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _to_domain(row)

    async def get_by_id(self, record_id: str) -> EchoRecord | None:
        async with self._session_factory() as session:
            stmt = select(EchoRecordORM).where(EchoRecordORM.id == record_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)


def _to_domain(row: EchoRecordORM) -> EchoRecord:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return EchoRecord(
        id=row.id,
        message=row.message,
        source=SourceType(row.source),
        created_at=created_at,
    )
