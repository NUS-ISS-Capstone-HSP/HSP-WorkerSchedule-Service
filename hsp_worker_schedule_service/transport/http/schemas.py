from pydantic import BaseModel, ConfigDict, Field


class CreateEchoRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "Hello from HTTP"}},
    )

    message: str = Field(
        min_length=1,
        max_length=2048,
        description="Message content to be stored as an echo record.",
    )


class EchoRecordResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6f88f9f2-65fd-4ef7-80de-2c96d8ab7b5b",
                "message": "Hello from HTTP",
                "source": "HTTP",
                "created_at": "2026-03-18T12:34:56+00:00",
            }
        },
    )

    id: str = Field(description="Echo record id (UUID).")
    message: str = Field(description="Stored message.")
    source: str = Field(description="Record source. HTTP or GRPC.")
    created_at: str = Field(description="Creation time in ISO-8601 format.")
