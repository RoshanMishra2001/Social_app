# In your database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use Railway's DATABASE_URL if available, otherwise fall back to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./social_app.db")

# Handle PostgreSQL URL format (Railway uses PostgreSQL)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

if DATABASE_URL.startswith("sqlite"):
    # SQLite needs special handling for foreign keys
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL connection
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
