from __future__ import annotations

import logging
from dataclasses import dataclass

import grpc

from hsp_worker_schedule_service.domain.errors import UnauthorizedError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Principal:
    user_id: str
    user_role: str


async def require_principal(
    context: grpc.aio.ServicerContext,
    method_name: str,
) -> Principal:
    metadata = {item.key.lower(): item.value for item in context.invocation_metadata()}
    user_id = metadata.get("x-user-id", "").strip()
    user_role = metadata.get("x-user-role", "").strip()

    if not user_id or not user_role:
        logger.warning(
            "grpc_auth_failed method=%s user_id=%s user_role=%s",
            method_name,
            user_id,
            user_role,
        )
        raise UnauthorizedError("missing metadata: x-user-id or x-user-role")

    logger.debug(
        "grpc_auth_ok method=%s user_id=%s user_role=%s",
        method_name,
        user_id,
        user_role,
    )
    return Principal(user_id=user_id, user_role=user_role)
