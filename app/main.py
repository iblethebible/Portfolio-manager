# app/main.py
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import SQLModel
from fastapi.staticfiles import StaticFiles

from .models import init_db, poll_prices
from .routes import router as api_router
from .config import PRICE_POLL_MINUTES, DATABASE_URL
from .db import engine

app = FastAPI(title="Open Portfolio Manager", version="0.4.0 (MySQL + Dashboard)")

# Attach API routes under /api
app.include_router(api_router)

# Serve static dashboard (index.html at /)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Background scheduler for price polling
scheduler = BackgroundScheduler()

@app.on_event("startup")
def on_startup():
    print(">>> Using DATABASE_URL:", DATABASE_URL)
    # Create schema if missing
    SQLModel.metadata.create_all(engine)
    # Seed demo assets/holdings if none exist
    init_db(engine)
    # Poll prices once on boot
    poll_prices(engine)
    # Start background price polling
    scheduler.add_job(
        lambda: poll_prices(engine),
        "interval",
        minutes=PRICE_POLL_MINUTES,
        id="price_poll",
        replace_existing=True,
    )
    scheduler.start()

@app.on_event("shutdown")
def on_shutdown():
    if scheduler.running:
        scheduler.shutdown()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
