import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/pcr_lims"
)
