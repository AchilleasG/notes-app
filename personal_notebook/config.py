"""
Pydantic settings configuration for environment variables.
"""

from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Main settings class combining all configuration."""

    # Django App Settings
    debug: bool = Field(True, env="DEBUG", description="Debug mode")
    secret_key: str = Field(
        "django-insecure-ubu06b9u!la4iu&)v^#fn0bb856q5o^lrt_kqoy6pan$bg2*)f",
        env="SECRET_KEY",
        description="Django secret key",
    )

    # Database Settings
    db_name: str = Field(..., env="DB_NAME", description="Database name")
    db_user: str = Field(..., env="DB_USER", description="Database user")
    db_password: str = Field(..., env="DB_PASSWORD", description="Database password")
    db_host: str = Field(..., env="DB_HOST", description="Database host")
    db_port: int = Field(5432, env="DB_PORT", description="Database port")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v):
        """Parse debug value from string."""
        if isinstance(v, str):
            return v.lower() in ["true", "1", "yes", "on"]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create a global settings instance
settings = Settings()
