from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb+srv://himan1406:r123saini@<cluster>.mongodb.net/?retryWrites=true&w=majority"
    DB_NAME: str = "student_management"

    class Config:
        env_file = ".env"

settings = Settings()