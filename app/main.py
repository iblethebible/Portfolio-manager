# app/main.py
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import SQLModel
from fastapi.staticfiles import StaticFiles
# from fastapi.middleware.cors import CORSMiddleware  # (optional; see below)

from .models import init_db, poll_prices
from .routes import router as api_router
from .config import PRICE_POLL_MINUTES
from .db import engine

app = FastAPI(title="Open Portfolio Manager", version="0.5.0 (multi-user)")

# (Optional) If you later host a separate front-end, enable CORS:
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# API under /api
app.include_router(api_router)

# Serve static dashboard at /
app.mount("/", StaticFiles(directory="static", html=True), name="static")

scheduler = BackgroundScheduler()

@app.on_event("startup")
def on_startup():
    print(">>> Using DATABASE_URL:", engine.url)  # shows resolved DSN
    SQLModel.metadata.create_all(engine)
    init_db(engine)
    poll_prices(engine)
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
