import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://pcr_admin:supersecretpassword@localhost:5432/pcr_analyzer",
)
