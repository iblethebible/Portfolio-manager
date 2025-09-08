# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import func
from sqlmodel import SQLModel, Field, Session, select
from passlib.hash import bcrypt

from .config import BASE_CCY
from .services import fetch_spot_by_source


# ---------------------------
# DB MODELS
# ---------------------------

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)   # username (no email)
    display_name: str
    password_hash: str

    @staticmethod
    def hash_password(raw: str) -> str:
        return bcrypt.hash(raw)

    def verify_password(self, raw: str) -> bool:
        return bcrypt.verify(raw, self.password_hash)


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # e.g. "BTC", "XMR", "VOD.L", "XAG"
    symbol: str = Field(index=True)
    # 'crypto' | 'equity' | 'metal' | 'manual'
    type: str
    # 'coingecko' | 'yfinance' | 'manual'
    source: str
    # for coingecko: 'monero', 'bitcoin'
    # for yfinance: 'VOD.L', 'AAPL', 'XAGUSD=X'
    source_ref: str = ""
    # e.g. "USD", "GBX", etc. (for equities/metals quotes)
    native_ccy: Optional[str] = None
    # reserved for future use; keep column for schema compatibility
    quote_ccy: Optional[str] = None


class Holding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account: str = Field(default="Default", index=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    qty: float
    # NEW: owner of this holding (multi-user)
    user_id: int = Field(foreign_key="user.id", index=True)


class Price(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    ts: datetime = Field(index=True)
    price: float
    source: str
    base_ccy: str = Field(default=BASE_CCY)


# ---------------------------
# SEED / INIT
# ---------------------------

def _ensure_asset(
    s: Session,
    *,
    symbol: str,
    type: str,
    source: str,
    source_ref: str = "",
    native_ccy: Optional[str] = None,
) -> Asset:
    """Get-or-create Asset by symbol (case-insensitive)."""
    symu = symbol.strip().upper()
    a = s.exec(select(Asset).where(func.upper(Asset.symbol) == symu)).first()
    if a:
        return a
    a = Asset(
        symbol=symu,
        type=type,
        source=source,
        source_ref=source_ref,
        native_ccy=native_ccy,
    )
    s.add(a)
    s.commit()
    s.refresh(a)
    return a


def init_db(engine) -> None:
    """
    Idempotent seed. Creates demo user, demo assets (if empty),
    and demo holdings for that user (if holdings table is empty).
    Safe to call on every startup.
    """
    with Session(engine) as s:
        # Ensure a demo user (by username)
        demo = s.exec(select(User).where(func.lower(User.username) == "demo")).first()
        if not demo:
            demo = User(
                username="demo",
                display_name="Demo",
                password_hash=User.hash_password("demo123"),
            )
            s.add(demo)
            s.commit()
            s.refresh(demo)

        # Ensure assets
        has_any_asset = s.exec(select(Asset).limit(1)).first() is not None
        if not has_any_asset:
            _ensure_asset(s, symbol="BTC", type="crypto", source="coingecko", source_ref="bitcoin")
            _ensure_asset(s, symbol="XMR", type="crypto", source="coingecko", source_ref="monero")
            _ensure_asset(s, symbol="XAG", type="metal",  source="yfinance",  source_ref="XAGUSD=X", native_ccy="USD")
            _ensure_asset(s, symbol="AAPL", type="equity", source="yfinance",  source_ref="AAPL",     native_ccy="USD")

        # Seed holdings for demo user if none exist
        has_any_holding = s.exec(select(Holding).limit(1)).first() is not None
        if not has_any_holding:
            def maybe_add(sym: str, qty: float):
                a = s.exec(select(Asset).where(func.upper(Asset.symbol) == sym)).first()
                if a:
                    s.add(Holding(account="Demo", asset_id=a.id, qty=qty, user_id=demo.id))

            maybe_add("BTC", 0.05)
            maybe_add("XMR", 2.0)
            maybe_add("XAG", 10.0)
            maybe_add("AAPL", 3.0)
            s.commit()


# ---------------------------
# PRICING HELPERS
# ---------------------------

def poll_one_asset(engine, asset_id: int, base_ccy: str = BASE_CCY) -> bool:
    """
    Fetch and store a fresh price for a single asset.
    Returns True if a price row was inserted.
    """
    with Session(engine) as s:
        asset = s.get(Asset, asset_id)
        if not asset:
            return False
        try:
            px, src = fetch_spot_by_source(
                asset.type, asset.source, asset.source_ref, base_ccy, asset.native_ccy
            )
        except Exception as e:
            print(f"[poll_one_asset] {asset.symbol}: fetch error -> {e}")
            return False

        s.add(
            Price(
                asset_id=asset.id,
                ts=datetime.utcnow(),
                price=float(px),
                source=src,
                base_ccy=base_ccy,
            )
        )
        s.commit()
        return True


def poll_prices(engine, base_ccy: str = BASE_CCY) -> Dict[str, Any]:
    """
    Fetch prices for all assets and store one Price row each (best-effort).
    Returns a summary dict with counts.
    """
    ok = 0
    fail = 0
    with Session(engine) as s:
        assets: List[Asset] = s.exec(select(Asset)).all()
    for a in assets:
        try:
            px, src = fetch_spot_by_source(a.type, a.source, a.source_ref, base_ccy, a.native_ccy)
            with Session(engine) as s2:
                s2.add(
                    Price(
                        asset_id=a.id,
                        ts=datetime.utcnow(),
                        price=float(px),
                        source=src,
                        base_ccy=base_ccy,
                    )
                )
                s2.commit()
            ok += 1
        except Exception as e:
            print(f"[poll_prices] {a.symbol}: fetch error -> {e}")
            fail += 1
    return {"ok": ok, "fail": fail, "base_ccy": base_ccy}


def latest_price_for_asset(engine, asset_id: int, base_ccy: str = BASE_CCY) -> Optional[float]:
    """
    Return the latest price for asset_id in the requested base_ccy.
    If no price exists in that base, returns None (no implicit FX for now).
    """
    with Session(engine) as s:
        row = s.exec(
            select(Price)
            .where(Price.asset_id == asset_id, Price.base_ccy == base_ccy)
            .order_by(Price.ts.desc())
            .limit(1)
        ).first()
        if row:
            return float(row.price)
    return None


# ---------------------------
# READ / AGGREGATION
# ---------------------------

def portfolio_overview(engine, base_ccy: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Compute simple positions snapshot using latest prices per asset in a base currency.
    If user_id is provided, only include holdings for that user.
    Returns: { base_ccy, total, items: [ {symbol,type,qty,last_px,value}, ... ] }
    """
    base = (base_ccy or BASE_CCY).upper()
    items: List[Dict[str, Any]] = []
    total = 0.0

    with Session(engine) as s:
        # Gather holdings (optionally scoped to user)
        q = select(Holding)
        if user_id is not None:
            q = q.where(Holding.user_id == user_id)
        holds: List[Holding] = s.exec(q).all()
        if not holds:
            return {"base_ccy": base, "total": 0.0, "items": []}

        # Map asset_id -> Asset once
        asset_ids = {h.asset_id for h in holds}
        assets = s.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()
        am: Dict[int, Asset] = {a.id: a for a in assets}

    # For each holding, attach latest price in requested base
    for h in holds:
        a = am.get(h.asset_id)
        if not a:
            continue
        last = latest_price_for_asset(engine, a.id, base)
        if last is None:
            # Optionally, try to fetch on-demand for missing rows
            if poll_one_asset(engine, a.id, base):
                last = latest_price_for_asset(engine, a.id, base)
        if last is None:
            # still missing -> skip from positions
            continue

        value = float(h.qty) * float(last)
        total += value
        items.append(
            {
                "symbol": a.symbol,
                "type": a.type,
                "qty": h.qty,
                "last_px": last,
                "value": value,
                "account": h.account,
                "holding_id": h.id,
            }
        )

    # sort by value desc for a nicer UI
    items.sort(key=lambda r: r["value"], reverse=True)
    return {"base_ccy": base, "total": total, "items": items}
