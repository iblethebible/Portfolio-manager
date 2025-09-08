from fastapi import APIRouter, Query, Body, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, delete
from sqlalchemy import func

from .models import Asset, Holding, User, portfolio_overview, latest_price_for_asset, poll_one_asset
from .db import engine
from .config import BASE_CCY
from .auth import create_token, set_token_cookie, clear_token_cookie, current_user_id

router = APIRouter(prefix="/api", tags=["api"])

@router.get("/health")
def health():
    return {"status": "ok"}

# ---------- Auth (username + password) ----------

@router.post("/auth/register")
def register(username: str = Body(...), password: str = Body(...), display_name: str = Body("User")):
    uname = (username or "").strip().lower()
    if not uname or not password:
        return JSONResponse({"error": "username and password required"}, status_code=400)
    with Session(engine) as s:
        if s.exec(select(User).where(func.lower(User.username) == uname)).first():
            return JSONResponse({"error": "username already taken"}, status_code=400)
        u = User(username=uname, display_name=(display_name or "User").strip(), password_hash=User.hash_password(password))
        s.add(u); s.commit(); s.refresh(u)
        resp = JSONResponse({"ok": True, "id": u.id, "username": u.username, "display_name": u.display_name})
        set_token_cookie(resp, create_token(u.id))
        return resp

@router.post("/auth/login")
def login(username: str = Body(...), password: str = Body(...)):
    uname = (username or "").strip().lower()
    with Session(engine) as s:
        u = s.exec(select(User).where(func.lower(User.username) == uname)).first()
        if not u or not u.verify_password(password or ""):
            return JSONResponse({"error": "invalid credentials"}, status_code=401)
        resp = JSONResponse({"ok": True, "id": u.id, "username": u.username, "display_name": u.display_name})
        set_token_cookie(resp, create_token(u.id))
        return resp

@router.post("/auth/logout")
def logout():
    resp = JSONResponse({"ok": True})
    clear_token_cookie(resp)
    return resp

@router.get("/me")
def me(request: Request):
    uid = current_user_id(request)
    with Session(engine) as s:
        u = s.get(User, uid)
        return {"id": u.id, "username": u.username, "display_name": u.display_name}

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
    norm_symbol = (symbol or "").strip().upper()
    src = (source or "").strip().lower()
    t = (type or "").strip().lower()
    ref = (source_ref or "").strip()

    # Autofill helpers
    cg_map = {"BTC": "bitcoin", "ETH": "ethereum", "XMR": "monero", "LTC": "litecoin", "ADA": "cardano",
              "XRP": "ripple", "DOGE": "dogecoin", "SOL": "solana"}
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
        exists = s.exec(select(Asset).where(func.upper(Asset.symbol) == norm_symbol)).first()
        if exists:
            return {"error": f"Asset '{norm_symbol}' already exists"}
        a = Asset(symbol=norm_symbol, type=t, source=src, source_ref=ref, native_ccy=native_ccy)
        s.add(a); s.commit(); s.refresh(a)

    # Poll immediately so Positions can render right away
    poll_one_asset(engine, a.id, BASE_CCY)
    return a

@router.delete("/assets/{symbol}")
def delete_asset(symbol: str):
    with Session(engine) as s:
        asset = s.exec(select(Asset).where(func.upper(Asset.symbol) == symbol.upper())).first()
        if not asset:
            return {"deleted": 0}
        s.exec(delete(Holding).where(Holding.asset_id == asset.id))
        s.delete(asset)
        s.commit()
        return {"deleted": 1}

# ---------- Holdings (per-user) ----------

@router.get("/holdings")
def list_holdings(request: Request):
    uid = current_user_id(request)
    with Session(engine) as s:
        rows = s.exec(
            select(Holding, Asset).where(Holding.user_id == uid, Holding.asset_id == Asset.id)
        ).all()
        return [{
            "id": h.id, "account": h.account, "qty": h.qty,
            "asset_id": h.asset_id, "asset_symbol": a.symbol, "asset_type": a.type
        } for (h, a) in rows]

@router.post("/holdings")
def create_holding(
    request: Request,
    asset_symbol: str = Body(...),
    qty: float = Body(...),
    account: str = Body("Default"),
):
    uid = current_user_id(request)
    norm_symbol = (asset_symbol or "").strip().upper()
    with Session(engine) as s:
        asset = s.exec(select(Asset).where(func.upper(Asset.symbol) == norm_symbol)).first()
        if not asset:
            return JSONResponse({"error": f"Unknown asset symbol '{asset_symbol}'"}, status_code=400)
        h = Holding(account=account, asset_id=asset.id, qty=qty, user_id=uid)
        s.add(h); s.commit(); s.refresh(h)
        # ensure we have a price soon
        poll_one_asset(engine, asset.id, BASE_CCY)
        return {"ok": True, "id": h.id}

@router.delete("/holdings/{holding_id}")
def delete_holding(request: Request, holding_id: int):
    uid = current_user_id(request)
    with Session(engine) as s:
        h = s.get(Holding, holding_id)
        if not h or h.user_id != uid:
            return {"deleted": 0}
        s.delete(h); s.commit()
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
def overview(request: Request, base_ccy: str = Query(None, description="Override base currency, e.g., GBP/USD/EUR")):
    uid = current_user_id(request)
    return portfolio_overview(engine, base_ccy, user_id=uid)
