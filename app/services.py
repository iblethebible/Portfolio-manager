import time
import threading
from typing import Dict
import requests
import yfinance as yf

# -----------------------------
# FX utilities
# -----------------------------

_YF_FX_TICKER = {
    ("USD", "GBP"): "USDGBP=X",
    ("GBP", "USD"): "GBPUSD=X",
    ("EUR", "GBP"): "EURGBP=X",
    ("GBP", "EUR"): "GBPEUR=X",
    ("USD", "EUR"): "USDEUR=X",
    ("EUR", "USD"): "EURUSD=X",
}

def fx_rate(base: str, quote: str) -> float:
    """Return FX rate base->quote using yfinance. 1 base = ? quote."""
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0
    tkr = _YF_FX_TICKER.get((base, quote))
    if tkr is None:
        # Triangulate via USD or EUR/GBP as needed
        via = "USD" if base != "USD" and quote != "USD" else ("EUR" if base != "EUR" and quote != "EUR" else "GBP")
        return fx_rate(base, via) * fx_rate(via, quote)
    t = yf.Ticker(tkr)
    price = (t.fast_info or {}).get("last_price")
    if price is None:
        hist = t.history(period="1d")
        if hist.empty:
            raise RuntimeError(f"FX price unavailable for pair {base}/{quote}")
        price = hist["Close"].iloc[-1]
    return float(price)

# -----------------------------
# CoinGecko (crypto)
# -----------------------------

# -----------------------------
# CoinGecko symbol/name -> id resolver (24h cached)
# -----------------------------
_CG_SYM_TO_ID: Dict[str, str] | None = None   # 'ETH'   -> 'ethereum'
_CG_NAME_TO_ID: Dict[str, str] | None = None  # 'ethereum' (name lower) -> 'ethereum' (id)
_CG_INDEX_EXPIRES_AT: float = 0.0
_CG_INDEX_TTL_SEC = 24 * 60 * 60
_CG_LOCK = threading.Lock()

def _refresh_cg_index_if_needed() -> None:
    """Cache CoinGecko coin list for symbol/name lookups."""
    global _CG_SYM_TO_ID, _CG_NAME_TO_ID, _CG_INDEX_EXPIRES_AT
    now = time.time()
    with _CG_LOCK:
        if _CG_SYM_TO_ID is not None and now < _CG_INDEX_EXPIRES_AT:
            return
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/list",
            params={"include_platform": "false"},
            timeout=25,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        coins = r.json()  # [{id,symbol,name}, ...]
        sym_map, name_map = {}, {}
        for c in coins:
            cid  = (c.get("id") or "").lower()
            sym  = (c.get("symbol") or "").upper()
            name = (c.get("name") or "").lower()
            if cid:
                if sym and sym not in sym_map:
                    sym_map[sym] = cid
                if name and name not in name_map:
                    name_map[name] = cid
        _CG_SYM_TO_ID, _CG_NAME_TO_ID = sym_map, name_map
        _CG_INDEX_EXPIRES_AT = now + _CG_INDEX_TTL_SEC

def _cg_normalize_id(symbol_or_id_or_name: str) -> str:
    """
    Accepts 'ETH', 'Ethereum', or 'ethereum' and returns a CoinGecko id ('ethereum').
    """
    s = (symbol_or_id_or_name or "").strip()
    if not s:
        raise ValueError("Empty crypto identifier")
    # If already looks like an id (lowercase, no spaces), accept directly
    if s.lower() == s and " " not in s:
        return s.lower()
    _refresh_cg_index_if_needed()
    # Try symbol (ETH)
    sym = s.upper()
    if _CG_SYM_TO_ID and sym in _CG_SYM_TO_ID:
        return _CG_SYM_TO_ID[sym]
    # Try human name (Ethereum)
    name = s.lower()
    if _CG_NAME_TO_ID and name in _CG_NAME_TO_ID:
        return _CG_NAME_TO_ID[name]
    raise ValueError(f"Unknown crypto symbol/name/id: {symbol_or_id_or_name}")


def _coingecko_simple(ids: list[str], vs: str) -> dict:
    url = "https://api.coingecko.com/api/v3/simple/price"
    r = requests.get(url, params={"ids": ",".join(ids), "vs_currencies": vs.lower()}, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_crypto_price_by_id(cg_id: str, target_ccy: str) -> tuple[float, str]:
    """Accepts symbol (ETH), name (Ethereum), or id (ethereum). Returns (price, source)."""
    normalized = _cg_normalize_id(cg_id)
    data = _coingecko_simple([normalized], target_ccy)
    px = data.get(normalized, {}).get(target_ccy.lower())
    if px is None:
        raise RuntimeError(f"Price unavailable for '{cg_id}' (resolved '{normalized}') in {target_ccy}")
    return float(px), f"coingecko({normalized}->{target_ccy.upper()})"


# -----------------------------
# yfinance helpers (metals/equities)
# -----------------------------

def _yf_last_price(ticker: str) -> float | None:
    """Best-effort getter that won't explode on Yahoo oddities."""
    try:
        t = yf.Ticker(ticker)
        finfo = t.fast_info or {}
        p = finfo.get("last_price")
        if p is not None:
            return float(p)
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None

# -----------------------------
# Silver (robust with fallbacks)
# -----------------------------

def fetch_silver_price(target_ccy: str) -> tuple[float | None, str]:
    """
    Robust silver price fetcher with fallbacks.
    Order:
      1) XAG<CCY>=X (e.g. XAGGBP=X, XAGEUR=X)
      2) XAGUSD=X then FX to target
      3) SI=F (COMEX front-month futures) then FX to target
    Returns (price, source). If all fail, returns (None, "unavailable").
    """
    target_ccy = target_ccy.upper()

    # 1) Direct XAG<CCY>=X
    direct_tkr = f"XAG{target_ccy}=X"
    p = _yf_last_price(direct_tkr)
    if p is not None:
        return p, f"yfinance({direct_tkr})"

    # 2) XAGUSD=X then FX
    p_usd = _yf_last_price("XAGUSD=X")
    if p_usd is not None:
        rate = fx_rate("USD", target_ccy)
        return p_usd * rate, "yfinance(XAGUSD=X)+fx"

    # 3) COMEX futures as proxy (USD/oz), then FX
    p_fut = _yf_last_price("SI=F")
    if p_fut is not None:
        rate = fx_rate("USD", target_ccy)
        return p_fut * rate, "yfinance(SI=F)+fx"

    # All failed
    return None, "unavailable"

# -----------------------------
# Equities (yfinance) with GBp normalization
# -----------------------------

def fetch_equity_price(symbol: str, target_ccy: str, native_ccy_hint: str | None = None) -> tuple[float, str]:
    """
    Return equity price normalized to target_ccy.
    - Detect native currency via fast_info['currency'] when available.
    - Normalize GBp (pence, 'GBX') to GBP by dividing by 100.
    - Convert using FX if needed.
    """
    target_ccy = target_ccy.upper()
    t = yf.Ticker(symbol)
    finfo = t.fast_info or {}
    native_ccy = (finfo.get("currency") or native_ccy_hint or "").upper()

    price = finfo.get("last_price")
    if price is None:
        hist = t.history(period="1d")
        if hist.empty:
            raise RuntimeError(f"No price history for {symbol}")
        price = hist["Close"].iloc[-1]

    px = float(price)

    # GBp/GBX normalization
    gbx_like = {"GBX", "GBP (PENCE)", "GBP (GBX)", "GBP/GBX", "GBP GBX", "GBP(GBX)", "GBp"}
    if native_ccy in gbx_like:
        px = px / 100.0
        native_ccy = "GBP"

    # Guess by suffix if unknown
    if not native_ccy:
        native_ccy = "GBP" if symbol.upper().endswith(".L") else "USD"

    if native_ccy != target_ccy:
        px *= fx_rate(native_ccy, target_ccy)
        return px, f"yfinance({symbol})+fx({native_ccy}->{target_ccy})"
    return px, f"yfinance({symbol})"

# -----------------------------
# Generic source-based fetcher
# -----------------------------

def fetch_spot_by_source(asset_type: str, source: str, source_ref: str, target_ccy: str, native_ccy_hint: str | None = None) -> tuple[float, str]:
    """
    Data-driven price resolver:
      - source='coingecko':   source_ref is CoinGecko id (e.g., 'ethereum')
      - source='yfinance':    source_ref is Yahoo ticker (e.g., 'AAPL', 'VOD.L', 'XAGUSD=X')
      - source='manual':      not fetched here (to be implemented separately)
    """
    source = (source or "").lower()
    asset_type = (asset_type or "").lower()
    target_ccy = target_ccy.upper()

    if source == "coingecko":
        if not source_ref:
            raise ValueError("coingecko source requires source_ref (e.g., 'ethereum')")
        px, src = fetch_crypto_price_by_id(source_ref, target_ccy)
        return px, src

    if source == "yfinance":
        if asset_type == "metal":
            # allow explicit ref or robust silver path
            if source_ref and source_ref.upper() != "XAG":
                p = _yf_last_price(source_ref)
                if p is not None:
                    native = (native_ccy_hint or "USD").upper()
                    if native != target_ccy:
                        p *= fx_rate(native, target_ccy)
                        return p, f"yfinance({source_ref})+fx({native}->{target_ccy})"
                    return p, f"yfinance({source_ref})"
            px, src = fetch_silver_price(target_ccy)
            if px is None:
                raise RuntimeError("Silver price unavailable")
            return px, src

        # equities and everything else via yfinance ticker
        return fetch_equity_price(source_ref or "", target_ccy, native_ccy_hint=native_ccy_hint)

    if source == "manual":
        # Placeholder for future manual price input path
        raise RuntimeError("Manual source not implemented yet (set via admin UI later).")

    raise ValueError(f"Unsupported source: {source}")
