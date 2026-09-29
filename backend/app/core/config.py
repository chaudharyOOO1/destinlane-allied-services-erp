import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Fortellus Security & Facility Management ERP"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    SECRET_KEY: str = "your-super-secret-jwt-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "security_erp"
    DATABASE_URL: Union[str, None] = None
    ADMIN_SETUP_TOKEN: Union[str, None] = None
    SUPABASE_URL: Union[str, None] = None
    SUPABASE_SERVICE_ROLE_KEY: Union[str, None] = None
    EMPLOYEE_DOCUMENT_BUCKET: str = "employee-documents"

    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://frontend-fortellus.vercel.app",
        "https://frontend-nu-five-evlm3uvoo2.vercel.app",
        "https://frontend-git-main-fortellus.vercel.app",
        "https://frontend-6upexdcp8-fortellus.vercel.app",
        "https://frontend-ntbly181o-fortellus.vercel.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, str) and v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        if isinstance(v, list):
            return v
        return ["*"]

    @property
    def sync_database_url(self) -> str:
        url = self.DATABASE_URL
        if url:
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            if url.startswith("postgresql://"):
                return "postgresql+psycopg://" + url[len("postgresql://"):]
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
