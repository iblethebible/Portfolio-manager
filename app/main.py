from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import SQLModel
from .models import init_db, poll_prices
from .routes import router as api_router
from .config import PRICE_POLL_MINUTES, DATABASE_URL
from .db import engine

app = FastAPI(title="Open Portfolio Manager", version="0.4.0 (MySQL)")

# Attach API routes
app.include_router(api_router)

# Background scheduler for price polling
scheduler = BackgroundScheduler()

@app.on_event("startup")
def on_startup():
    print(">>> Using DATABASE_URL:", DATABASE_URL)  # sanity check
    SQLModel.metadata.create_all(engine)
    init_db(engine)          # seed demo rows if empty
    poll_prices(engine)      # fetch once on boot
    scheduler.add_job(lambda: poll_prices(engine),
                      "interval",
                      minutes=PRICE_POLL_MINUTES,
                      id="price_poll",
                      replace_existing=True)
    scheduler.start()

@app.on_event("shutdown")
def on_shutdown():
    if scheduler.running:
        scheduler.shutdown()

@app.get("/")
def root():
    return {"msg": "Open Portfolio Manager API (MySQL) running"}
