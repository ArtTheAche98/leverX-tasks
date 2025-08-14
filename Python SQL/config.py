import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_user: str = os.getenv("DB_USER", "student_user")
    db_password: str = os.getenv("DB_PASSWORD", "student_password")
    db_name: str = os.getenv("DB_NAME", "student_analytics")

settings = Settings()