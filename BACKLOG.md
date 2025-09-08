# Backlog

## 🛠 Bugs / KEL links
- [ ] KE-1: Normalize CoinGecko ids (`XMR` → `monero`), add search fallback.
- [ ] KE-2: Guarantee price on create; expose fetch errors in UI.
- [ ] KE-3: Show `asset_symbol` in holdings table (API join).
- [ ] KE-4: Add `PATCH /holdings/{id}` and inline edit on dashboard.

## ✨ Features
- [ ] Watchlist: track assets without holdings (separate section).
- [ ] “Poll now” button → `POST /api/prices/poll`.
- [ ] CSV import/export (holdings).
- [ ] Multi-base currency history chart (total value over time).
- [ ] Ticker lookup helper (autocomplete for yfinance tickers).
- [ ] Auth (API key or simple login) for future hosted demo.

## 🧹 Chores / DX
- [ ] Env flag `SEED_DEMO=false` to disable seeding in prod.
- [ ] Docker Compose: MySQL + app (dev ready).
- [ ] Alembic migrations (MySQL).
- [ ] Unit tests for services (CoinGecko & Yahoo paths).
- [ ] CI: lint & test on PR (GitHub Actions).
