from fastapi import APIRouter, Query, Body
from sqlmodel import Session, select, delete
from sqlalchemy import func  # <- correct import
from .models import (
    Asset,
    Holding,
    portfolio_overview,
    latest_price_for_asset,
    poll_one_asset,
)
from .db import engine
from .config import BASE_CCY

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
    # Normalise
    norm_symbol = (symbol or "").strip().upper()
    src = (source or "").strip().lower()
    t = (type or "").strip().lower()
    ref = (source_ref or "").strip()

    # --- Autofill helpers ---
    cg_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "XMR": "monero",
        "LTC": "litecoin",
        "ADA": "cardano",
        "XRP": "ripple",
        "DOGE": "dogecoin",
        "SOL": "solana",
    }

    if src == "coingecko":
        if not ref:
            ref = cg_map.get(norm_symbol, "")
        if not ref:
            return {"error": "For coingecko, please provide source_ref (e.g., 'monero' for XMR)"}

    if src == "yfinance":
        if norm_symbol.endswith(".L") and not native_ccy:
            native_ccy = "GBX"
        if t == "metal" and not ref:
            if norm_symbol == "XAG":
                ref = "XAGUSD=X"; native_ccy = native_ccy or "USD"
            elif norm_symbol == "XAU":
                ref = "XAUUSD=X"; native_ccy = native_ccy or "USD"

    with Session(engine) as s:
        # case-insensitive duplicate check
        exists = s.exec(
            select(Asset).where(func.upper(Asset.symbol) == norm_symbol)
        ).first()
        if exists:
            return {"error": f"Asset '{norm_symbol}' already exists"}

        a = Asset(
            symbol=norm_symbol,
            type=t,
            source=src,
            source_ref=ref,
            native_ccy=native_ccy,
        )
        s.add(a)
        s.commit()
        s.refresh(a)

    # Poll immediately so Positions/pie can render it right away
    poll_one_asset(engine, a.id, BASE_CCY)
    return a

@router.delete("/assets/{symbol}")
def delete_asset(symbol: str):
    norm_symbol = (symbol or "").strip().upper()
    with Session(engine) as s:
        asset = s.exec(
            select(Asset).where(func.upper(Asset.symbol) == norm_symbol)
        ).first()
        if not asset:
            return {"deleted": 0}
        s.exec(delete(Holding).where(Holding.asset_id == asset.id))
        s.delete(asset)
        s.commit()
        return {"deleted": 1}

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
    norm_symbol = (asset_symbol or "").strip().upper()
    with Session(engine) as s:
        asset = s.exec(
            select(Asset).where(func.upper(Asset.symbol) == norm_symbol)
        ).first()
        if not asset:
            return {"error": f"Unknown asset symbol '{asset_symbol}'"}

        h = Holding(account=account, asset_id=asset.id, qty=qty)
        s.add(h)
        s.commit()
        s.refresh(h)
        holding_id = h.id
        asset_id = asset.id

    # ensure fresh price so it shows up immediately
    poll_one_asset(engine, asset_id, BASE_CCY)
    return {"id": holding_id, "ok": True}

@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int):
    with Session(engine) as s:
        h = s.get(Holding, holding_id)
        if not h:
            return {"deleted": 0}
        s.delete(h)
        s.commit()
        return {"deleted": 1}

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
