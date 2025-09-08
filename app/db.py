# app/db.py
from sqlmodel import create_engine
from .config import DATABASE_URL

# Single shared engine for the whole app.
# pool_pre_ping avoids "MySQL server has gone away" on idle connections.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)
