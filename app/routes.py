from fastapi import APIRouter, Query, Body
from sqlmodel import Session, select
from .models import Asset, Holding, portfolio_overview, latest_price_for_asset
from .db import engine

router = APIRouter(prefix="/api", tags=["api"])

@router.get("/health")
def health():
    return {"status": "ok"}

# ---------- Assets ----------

@router.get("/assets")
def list_assets():
    with Session(engine) as s:
        return s.exec(select(Asset)).all()

@router.post("/assets")
def create_asset(
    symbol: str = Body(...),
    type: str = Body(...),            # 'crypto' | 'equity' | 'metal' | 'manual'
    source: str = Body(...),          # 'coingecko' | 'yfinance' | 'manual'
    source_ref: str = Body(""),
    native_ccy: str | None = Body(None),
):
    with Session(engine) as s:
        a = Asset(symbol=symbol, type=type, source=source, source_ref=source_ref, native_ccy=native_ccy)
        s.add(a)
        s.commit()
        s.refresh(a)
        return a

# ---------- Holdings ----------

@router.get("/holdings")
def list_holdings():
    with Session(engine) as s:
        return s.exec(select(Holding)).all()

@router.post("/holdings")
def create_holding(
    asset_symbol: str = Body(...),
    qty: float = Body(...),
    account: str = Body("Default"),
):
    with Session(engine) as s:
        asset = s.exec(select(Asset).where(Asset.symbol == asset_symbol)).first()
        if not asset:
            return {"error": f"Unknown asset symbol '{asset_symbol}'"}
        h = Holding(account=account, asset_id=asset.id, qty=qty)
        s.add(h)
        s.commit()
        s.refresh(h)
        return h

# ---------- Prices / Overview ----------

@router.get("/prices/latest")
def latest_prices(base_ccy: str = Query(None, description="Override base currency, e.g., GBP/USD/EUR")):
    base = base_ccy.upper() if base_ccy else "GBP"
    with Session(engine) as s:
        assets = s.exec(select(Asset)).all()
        out = []
        for a in assets:
            px = latest_price_for_asset(engine, a.id, base)
            if px is not None:
                out.append({"symbol": a.symbol, "type": a.type, "price": px, "base_ccy": base})
        return out

@router.get("/overview")
def overview(base_ccy: str = Query(None, description="Override base currency, e.g., GBP/USD/EUR")):
    return portfolio_overview(engine, base_ccy)
