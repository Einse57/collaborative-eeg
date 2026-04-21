"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "EEG/MEG Annotation Platform"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # File storage
    UPLOAD_DIR: str = "../datasets"
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    
    # Database (for future use)
    DATABASE_URL: str = "sqlite:///./eeg_annotations.db"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
