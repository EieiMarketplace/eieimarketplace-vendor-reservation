from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URL: str
    MONGO_DB: str
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()