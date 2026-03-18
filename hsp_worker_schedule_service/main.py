import asyncio
from contextlib import suppress

import uvicorn

from hsp_worker_schedule_service.bootstrap.container import build_container


async def run() -> None:
    container = await build_container()
    await container.grpc_server.start()

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

    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            raise exc

    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    await container.grpc_server.stop(grace=5)
    if container.engine is not None:
        await container.engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
