from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./loom_dev.db"
    cors_origins: str = "http://localhost:5173"
    redis_url: str = "redis://localhost:16379/0"
    object_storage_endpoint: str = "http://localhost:19000"
    object_storage_access_key: str = "loom_dev"
    object_storage_secret_key: str = "loom_dev_password"
    object_storage_bucket: str = "loom-assets"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

