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

