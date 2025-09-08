from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Session, select
from .services import fetch_spot_by_source, fx_rate
from .config import BASE_CCY

# -----------------------------
# Tables
# -----------------------------

class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Friendly symbol you use internally: BTC, ETH, XMR, XAG, AAPL, VOD.L, etc.
    symbol: str
    # 'crypto' | 'metal' | 'equity' | 'cash' | 'manual'
    type: str
    # 'coingecko' | 'yfinance' | 'manual'
    source: str
    # e.g., 'bitcoin', 'ethereum' (CoinGecko); 'AAPL', 'VOD.L', 'XAGUSD=X' (Yahoo)
    source_ref: str
    # Optional hint for native currency (e.g., 'USD', 'GBX')
    native_ccy: Optional[str] = None
    # Informational field; not used in logic (we store normalized prices)
    quote_ccy: str | None = "NATIVE"

class Holding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account: str = "Default"
    asset_id: int
    qty: float

class Price(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int
    ts: datetime
    price: float                 # stored in BASE_CCY at poll time (default GBP)
    source: str
    base_ccy: str = BASE_CCY     # currency in which price was stored

# -----------------------------
# Init / seed
# -----------------------------

def init_db(engine):
    with Session(engine) as s:
        if not s.exec(select(Asset)).first():
            s.add_all([
                # Crypto via CoinGecko
                Asset(symbol="BTC",  type="crypto", source="coingecko", source_ref="bitcoin"),
                Asset(symbol="XMR",  type="crypto", source="coingecko", source_ref="monero"),
                Asset(symbol="ETH",  type="crypto", source="coingecko", source_ref="ethereum"),
                # Silver via yfinance (we’ll resolve robustly)
                Asset(symbol="XAG",  type="metal",  source="yfinance",  source_ref="XAGUSD=X", native_ccy="USD"),
                # Equities via yfinance
                Asset(symbol="AAPL", type="equity", source="yfinance",  source_ref="AAPL",    native_ccy="USD"),
                Asset(symbol="VOD.L",type="equity", source="yfinance",  source_ref="VOD.L",  native_ccy="GBX"),
            ])
            s.commit()

        if not s.exec(select(Holding)).first():
            # Some demo holdings
            btc  = s.exec(select(Asset).where(Asset.symbol == "BTC")).one()
            xmr  = s.exec(select(Asset).where(Asset.symbol == "XMR")).one()
            xag  = s.exec(select(Asset).where(Asset.symbol == "XAG")).one()
            aapl = s.exec(select(Asset).where(Asset.symbol == "AAPL")).one()
            s.add_all([
                Holding(account="Default", asset_id=btc.id,  qty=0.1),
                Holding(account="Default", asset_id=xmr.id,  qty=5),
                Holding(account="Default", asset_id=xag.id,  qty=20),   # ounces
                Holding(account="Broker",  asset_id=aapl.id, qty=10),
            ])
            s.commit()

# -----------------------------
# Price polling
# -----------------------------

def poll_prices(engine):
    """Fetch latest spot for all assets in BASE_CCY and store them."""
    with Session(engine) as s:
        assets = s.exec(select(Asset)).all()
        for a in assets:
            try:
                px, src = fetch_spot_by_source(a.type, a.source, a.source_ref, BASE_CCY, a.native_ccy)
                s.add(Price(asset_id=a.id, ts=datetime.utcnow(), price=float(px), source=src, base_ccy=BASE_CCY))
            except Exception:
                # swallow per-asset errors to keep loop going
                continue
        s.commit()

# -----------------------------
# Query helpers
# -----------------------------

def latest_price_for_asset(engine, asset_id: int, desired_ccy: str) -> Optional[float]:
    """Return latest price for asset in desired_ccy (convert if needed)."""
    desired_ccy = desired_ccy.upper()
    with Session(engine) as s:
        row = s.exec(
            select(Price.price, Price.base_ccy)
            .where(Price.asset_id == asset_id)
            .order_by(Price.ts.desc())
        ).first()
        if row is None:
            return None
        price, stored_ccy = row
        stored_ccy = (stored_ccy or BASE_CCY).upper()
        if stored_ccy == desired_ccy:
            return float(price)
        return float(price) * fx_rate(stored_ccy, desired_ccy)

def portfolio_overview(engine, base_ccy: Optional[str] = None):
    """Return aggregated overview: total in base_ccy + per-asset lines."""
    base = (base_ccy or BASE_CCY).upper()
    with Session(engine) as s:
        rows = s.exec(
            select(Asset.id, Asset.symbol, Asset.type, Holding.qty)
            .join(Holding, Holding.asset_id == Asset.id)
        ).all()

        total = 0.0
        items = []
        for asset_id, symbol, a_type, qty in rows:
            px = latest_price_for_asset(engine, asset_id, base)
            if px is None:
                continue
            val = float(qty) * float(px)
            total += val
            items.append({
                "symbol": symbol,
                "type": a_type,
                "qty": qty,
                "last_px": px,
                "value": val,
            })

        return {"total": total, "base_ccy": base, "items": items}
