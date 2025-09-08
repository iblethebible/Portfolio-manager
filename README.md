# Open Portfolio Manager

An open-source **personal portfolio tracker** for **crypto (BTC, XMR)**, **precious metals (Silver/XAG)**, and **stocks**.  
Built with **Python + FastAPI**, with plans for a simple web UI and CLI support.  

---

## ✨ Features (MVP)

- Track holdings across **crypto, metals, and equities**
- Fetch live prices:
  - Crypto: [CoinGecko API](https://www.coingecko.com/en/api)
  - Stocks: [yfinance](https://pypi.org/project/yfinance/)
  - Silver: XAG/USD via finance APIs
- Convert values into a base currency (GBP, USD, etc.)
- Portfolio overview with per-asset breakdown

---

## 🧩 Project Structure

The app is **compartmentalised** into layers:

```
+---------------------+       +------------------+
|     Frontend (UI)   | <-->  |    FastAPI API   |
| React/Svelte (WIP)  |       |   /overview etc. |
+---------------------+       +------------------+
              |
              v
       +------------------+
       |    Core Logic    |
       |  Price fetchers  |
       | P&L calculations |
       +------------------+
              |
              v
       +------------------+
       |    Database      |
       | SQLite (default) |
       | MySQL/Postgres   |
       +------------------+
```


## 🚀 Quick Start

Clone the repo:
```bash
git clone https://github.com/iblethebible/portfolio-manager.git
cd portfolio-manager


## Setup
1. Copy `.env.example` to `.env`
2. Update values if needed (DB password, currency, poll interval)
3. Run `uvicorn app.main:app --reload`


## Project Board & Logs

- **Known Errors Log:** see [`KEL.md`](./KEL.md)
- **Backlog / Roadmap:** see [`BACKLOG.md`](./BACKLOG.md)

> Tip: We mirror KEL items as GitHub Issues so they’re visible on the repo and can be tracked in a Project board.
