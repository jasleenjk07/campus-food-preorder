#Central configuration manager for the backend.
from pydantic_settings import BaseSettings #BaseSettings automatically: Reads values from .env, Converts types automatically, Validates them, Throws error if something is missing
from pydantic import field_validator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ENVIRONMENT: str

    LOG_LEVEL: str = "INFO"

    # Email Configuration
    EMAIL_HOST: str = "smtp@gmail.com" #which SMTP server to use, Gmail’s mail server
    EMAIL_PORT: int = 587 #which port to connect to, Port 587 = TLS secure email port
    EMAIL_USER: str #login email
    EMAIL_PASSWORD: str #login password
    EMAIL_FROM: str #sender name shown in email

    #This allows you to validate specific fields.
    @field_validator("SECRET_KEY")
    def validate_secret_key(cls, v, info): #v = the actual SECRET_KEY value from .env, values = other already loaded environment variables
        env = info.data.get("ENVIRONMENT")
        if env == "production" and len(v) < 32:
            raise ValueError("SECRET_KEY too weak for production")
        return v

    class Config:
        env_file = BASE_DIR / ".env" #Load environment variables from .env automatically.
        env_file_encoding = "utf-8"

settings = Settings()
