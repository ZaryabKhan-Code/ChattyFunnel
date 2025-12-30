from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Facebook Settings
    FACEBOOK_APP_ID: str
    FACEBOOK_APP_SECRET: str
    FACEBOOK_REDIRECT_URI: str

    # Instagram Settings
    INSTAGRAM_APP_ID: str
    INSTAGRAM_APP_SECRET: str
    INSTAGRAM_REDIRECT_URI: str

    # Application Settings
    SECRET_KEY: str
    DATABASE_URL: str = "mysql+pymysql://admin_auto:KWhPA6HJ75zW@database-automation.csl246qas9qs.us-east-1.rds.amazonaws.com:3306/faceandinsta"
    FRONTEND_URL: str = "http://localhost:3000"
    API_V1_STR: str = "/api"  # Changed from "/api" to match frontend calls
    WEBHOOK_VERIFY_TOKEN: str = "my_secure_verify_token_12345"

    # Environment
    ENVIRONMENT: str = "development"  # development or production

    # Facebook Graph API
    FACEBOOK_GRAPH_VERSION: str = "v18.0"
    FACEBOOK_GRAPH_URL: str = "https://graph.facebook.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Allow missing .env file in production
        extra = "allow"


# Initialize settings
settings = Settings()
