from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URL: str
    MONGO_DB: str
    MONGO_DB_RESERVATION: str
    MONGO_DB_MARKET: str
    SECRET_KEY:str
    ALGORITHM: str
    MARKET_SERVICE_URL:str
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()