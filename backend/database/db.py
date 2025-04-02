import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the database URL from config
from .config import DATABASE_URL

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connection is still active before using
    echo=False,          # Set to True to see SQL queries in logs
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a scoped session for thread safety
SessionFactory = scoped_session(SessionLocal)

# Function to get a database session
def get_db():
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()

# Access to Base for creating tables
from .models import Base

# Function to create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)
    
# Function to drop all tables (use with caution!)
def drop_tables():
    Base.metadata.drop_all(bind=engine) 