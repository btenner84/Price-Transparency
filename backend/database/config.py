import os

# PostgreSQL connection settings
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_USER = os.environ.get("PG_USER", "bentenner")
PG_PASS = os.environ.get("PG_PASS", "")
PG_DB = os.environ.get("PG_DB", "hospital_transparency")

# Database URI
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    f"postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}"
) 