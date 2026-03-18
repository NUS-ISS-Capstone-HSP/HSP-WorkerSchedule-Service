from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# 看似是写死，其实是读取了环境变量，这些写死的值只是默认值。
class Settings(BaseSettings):
    service_name: str = "hsp-execution-record-service"
    env: str = "dev"
    log_level: str = "INFO"

    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051

    http_host: str = "0.0.0.0"
    http_port: int = 8080

    use_mock_repository: bool = False
    mysql_dsn: str = "mysql+aiomysql://app:app@mysql:3306/schedule_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
