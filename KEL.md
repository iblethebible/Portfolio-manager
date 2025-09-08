# Known Errors Log (KEL)

This log tracks defects we know about, current status, and workarounds.

> Convention: `KE-<number>` ids are mirrored as GitHub Issues.

---

## KE-1 — CoinGecko ref must be lowercase id (e.g., `monero`)
**Symptoms:** Adding XMR with source `coingecko` may fail to price if `source_ref` is missing or capitalized.  
**Root cause:** API expects CoinGecko **id** (lowercase), not the coin name/symbol.  
**Status:** Workaround in place; needs full normalization & fallback search.  
**Workaround:** Manually set `source_ref=monero` when adding XMR.  
**Fix idea:** Auto-map common symbols; lower-case ref; search fallback. _Planned in #KE-1._

---

## KE-2 — Positions omit holdings without a stored price
**Symptoms:** New holding doesn’t appear in Positions/Pie until a price exists.  
**Root cause:** Overview filters assets without latest price in `base_ccy`.  
**Status:** Partial fix: we call `poll_one_asset` on create.  
**Workaround:** Hit “Refresh” or call `POST /api/prices/poll`.  
**Fix idea:** Ensure immediate poll succeeds & surface fetch errors in UI toast.

---

## KE-3 — Holdings list shows `asset_id` (poor UX)
**Symptoms:** Holdings table shows numeric `asset_id`.  
**Root cause:** API returns raw holding model without join.  
**Status:** Pending UI/API enhancement.  
**Workaround:** None.  
**Fix idea:** Return `asset_symbol`/`asset_type` from `/api/holdings`.

---

## KE-4 — Editing holdings requires delete + re-add
**Symptoms:** No inline edit for qty/account.  
**Root cause:** PATCH endpoint/UI not implemented.  
**Status:** Planned (`PATCH /api/holdings/{id}`).  
**Workaround:** Delete & recreate holding.

---

## KE-5 — Seed data can reappear or crash with missing rows (historical)
**Symptoms:** Crash on `.one()` if seed assets deleted.  
**Root cause:** Non-idempotent `init_db`.  
**Status:** Fixed by idempotent seed.  
**Workaround:** n/a.

---

## KE-6 — UI polish
**Symptoms:** Basic styling, unclear labels, no “Poll now” button.  
**Root cause:** MVP dashboard.  
**Status:** Planned.  
**Workaround:** Use Swagger `/docs` for manual calls.

