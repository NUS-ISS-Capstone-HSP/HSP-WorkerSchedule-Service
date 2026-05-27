import asyncio
import logging
from contextlib import suppress

import uvicorn

from hsp_worker_schedule_service.bootstrap.container import build_container
from hsp_worker_schedule_service.config import get_settings
from hsp_worker_schedule_service.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "service_starting http=%s:%s grpc=%s:%s log_level=%s",
        settings.http_host,
        settings.http_port,
        settings.grpc_host,
        settings.grpc_port,
        settings.log_level,
    )

    container = await build_container()
    await container.grpc_server.start()
    logger.info(
        "grpc_server_started addr=%s:%s",
        container.settings.grpc_host,
        container.settings.grpc_port,
    )

    http_config = uvicorn.Config(
        container.http_app,
        host=container.settings.http_host,
        port=container.settings.http_port,
        log_level=container.settings.log_level.lower(),
    )
    http_server = uvicorn.Server(http_config)

    http_task = asyncio.create_task(http_server.serve(), name="http-server")
    grpc_task = asyncio.create_task(
        container.grpc_server.wait_for_termination(),
        name="grpc-server",
    )

    done, pending = await asyncio.wait(
        {http_task, grpc_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    server_exception: Exception | None = None
    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            logger.exception("server_task_failed task=%s", task.get_name())
            if isinstance(exc, Exception):
                server_exception = exc
            else:
                server_exception = RuntimeError(str(exc))

    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    await container.grpc_server.stop(grace=5)
    if container.engine is not None:
        await container.engine.dispose()
    logger.info("service_stopped")

    if server_exception is not None:
        raise server_exception


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
