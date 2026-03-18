import json
from pathlib import Path

from hsp_worker_schedule_service.repository.in_memory import InMemoryEchoRepository
from hsp_worker_schedule_service.service.echo_service import EchoService
from hsp_worker_schedule_service.transport.http.app import create_http_app

OUTPUT_PATH = Path("docs/openapi.json")


def main() -> None:
    app = create_http_app(EchoService(InMemoryEchoRepository()))
    schema = app.openapi()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"OpenAPI schema generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
