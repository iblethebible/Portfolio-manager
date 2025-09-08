from sqlmodel import create_engine
from .config import DATABASE_URL

# Pre-ping keeps pooled connections healthy when MySQL idles out
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # flip to True if you want SQL logs during debugging
)
