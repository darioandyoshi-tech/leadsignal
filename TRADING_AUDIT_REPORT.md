# LeadSignal Trading System — Code Audit Report

**Date:** 2026-06-19  
**Reviewer:** Subagent (automated)  
**Scope:** `backend/app/market/{broker.py, portfolio.py, recommender.py, scorer.py}` + `backend/app/market/scripts/{execute_paper_trades.py, daily_market_scan.py, sync_alpaca_fills.py}`

---

## 1. `broker.py` — AlpacaBroker

### 🐛 Confirmed Bugs

#### BUG-B01: `submit_market_sell()` rounding truncates fractional shares — **CRITICAL**
**Lines:** 370–396 (specifically `kwargs["qty"] = round(float(qty), 8)`)

```python
if qty:
    kwargs["qty"] = round(float(qty), 8)
```

**Problem:** `round(qty, 8)` is not the bug per se, but when the position holds fractional shares (e.g. from a notional buy order), `submit_market_sell` is called with the full fractional qty. However, the real problem is in the calling code (`sync_alpaca_fills.py` and `execute_paper_trades.py`) which never calls `submit_market_sell` at all for liquidation — there is **no automated exit/liquidation path**. When a position's stop or target fires at Alpaca, the local DB only discovers it via `sync_positions()` seeing the position gone. This means:

1. `submit_market_sell()` is **never called by any script** for routine exits.
2. `submit_oco_exit()` is also **never called by any script**.
3. The only exit mechanism is the bracket order's attached legs placed at entry time via `submit_bracket_entry()`.

**Impact:** If the bracket order's stop-loss or take-profit legs are rejected or cancelled by Alpaca, the position has **no exit mechanism** and will remain open indefinitely. There is no fallback liquidation.

#### BUG-B02: `submit_oco_exit()` — Not a true OCO; one leg can fill without the other being cancelled
**Lines:** 316–360

```python
stop_order = self.client.submit_order(stop_leg)
tp_order = self.client.submit_order(tp_leg)
```

**Problem:** Two independent orders are submitted. A true OCO (One-Cancels-Other) would cancel the stop when the take-profit fills (and vice versa). With two separate orders, if the take-profit fills, the stop-loss order remains open and could trigger a short sale on a position you no longer hold. Alpaca does support OCO orders via the `OTO`/`BRACKET` order class, but this method doesn't use them.

**Impact:** If both legs are live and one fills, the other remains active. For the stop leg, this means a sell order on zero shares → either rejected or creates an unintended short. For the limit leg, a limit sell on zero shares → rejected. This is a **potential unintended short position** bug.

#### BUG-B03: `submit_oco_exit()` — If first leg (stop) fails, second leg (take-profit) is still submitted
**Lines:** 340–356

```python
stop_order = self.client.submit_order(stop_leg)
tp_order = self.client.submit_order(tp_leg)
```

If `submit_order(stop_leg)` raises `APIError`, the exception is caught and the take-profit order is **never submitted** — but the function returns failure. However, if the stop order is *accepted but partially filled* and then the take-profit submission fails, you have a position with only a stop-loss and no take-profit. No retry or cleanup logic.

#### BUG-B04: `submit_bracket_entry()` — No take-profit limit_price validation
**Lines:** 267–295

```python
take_profit={"limit_price": round(float(take_profit_price), 2)},
stop_loss={"stop_price": round(float(stop_loss_price), 2)},
```

If `take_profit_price <= 0` or `stop_loss_price <= 0` or `take_profit_price <= stop_loss_price`, Alpaca will reject the order. There's no pre-validation. This is an edge case that can happen if ATR is very small or zero.

### ⚠️ Edge Cases Not Handled

- **EC-B01:** `get_positions()` returns `[{"error": "...", "code": ...}]` on failure. Downstream code in `execute_paper_trades.py` (line ~82) does `{p["symbol"] for p in open_positions}` which would raise `KeyError` on the error dict.
- **EC-B02:** `get_pending_sell_symbols()` catches `APIError` but not network timeouts or connection errors. A transient network failure would crash the entire execution.
- **EC-B03:** `submit_bracket_entry()` — if the buy fills but the attached stop/take-profit legs are rejected by Alpaca (happens with tight prices), the position is open with no exit orders. No detection or retry.
- **EC-B04:** `_normalize_status("DONE_FOR_DAY") → "filled"` — a `DONE_FOR_DAY` status means the order is done for the day but may not be fully filled. Mapping it to `"filled"` is incorrect.

### 💡 Improvement Opportunities

- **IMP-B01:** Add a `cancel_order(broker_order_id)` method for cancelling individual legs.
- **IMP-B02:** Add pre-validation in `submit_bracket_entry()`: `take_profit > current_price > stop_loss > 0`.
- **IMP-B03:** Add a `get_position(symbol)` method to fetch a single position for targeted checks.
- **IMP-B04:** Use Alpaca's native OCO order class if available via `alpaca-py` rather than emulating with two orders.

---

## 2. `execute_paper_trades.py`

### 🐛 Confirmed Bugs

#### BUG-E01: Portfolio heat calculation uses `PaperPosition.notional` (stale entry value) not current market value
**Lines:** 61–67

```python
open_positions_value = sum(p.notional or 0 for p in (
    await db.execute(select(PaperPosition).where(PaperPosition.status == PositionStatus.open))
).scalars().all())
cash = float(account.get("cash", 0))
heat = open_positions_value / cash if cash > 0 else 0
```

**Problem:** `p.notional` is the entry-time notional, not current market value. If positions have gained 20%, the real portfolio heat is higher than reported. This could allow over-deployment.

**Also:** The denominator is `cash` only, not total equity. If $40k is deployed and $10k cash remains, heat = `40k/10k = 400%`. This makes the `max_portfolio_heat` setting (0.5 = 50%) essentially useless — it will almost always be exceeded. The heat ratio should be `deployed / (deployed + cash)` i.e. `deployed / equity`.

#### BUG-E02: `open_positions` from Alpaca used for `skip_symbols` but local DB check is separate — race condition
**Lines:** 73–84, then 133–139

```python
# Alpaca positions checked here:
open_symbols = {p["symbol"] for p in open_positions}
skip_symbols = open_symbols | pending_sell_symbols
# ...later, in the loop:
existing = await db.execute(
    select(PaperPosition).where(
        PaperPosition.symbol == plan.symbol,
        PaperPosition.status == PositionStatus.open,
    )
)
```

Between checking Alpaca positions and the local DB check, a bracket order could fill. The local DB may not yet reflect the fill. The skip set from Alpaca is fetched once at the start, not refreshed per-iteration.

#### BUG-E03: `slots_remaining` calculation double-counts `blocked_symbols`
**Lines:** `portfolio.py` `select_picks_to_buy()`, lines 82–93

```python
slots_remaining = max(0, self.max_open_positions - len(blocked_symbols))
```

`blocked_symbols` includes both Alpaca open positions AND pending sell symbols. But `max_open_positions` is the max *total* positions. If some blocked symbols are pending-sell-only (position already closed but sell order still pending), they shouldn't count as open positions. This can prevent new trades when positions are being liquidated.

#### BUG-E04: Entry price fallback to `plan.entry_price` when `filled_avg_price` is None
**Lines:** 165–166

```python
entry_price = result["order"].get("filled_avg_price") or plan.entry_price
shares = result["order"].get("filled_qty") or plan.shares
```

**Problem:** Bracket market orders on Alpaca may return `filled_avg_price = None` if not yet filled (status `accepted` not `filled`). The code records `plan.entry_price` (the predicted close) as the entry price, and `plan.shares` (the intended shares) as the actual shares. This creates a **phantom position** in the DB that may not match reality. If the order fills later at a different price, the DB is wrong until sync runs.

#### BUG-E05: `notes` field can crash if `pick` is None
**Line:** 181

```python
notes=f"Auto-paper buy. Forecast: {pick.forecast_return_4d*100:.2f}%" if pick else "Auto-paper buy",
```

The f-string is evaluated *before* the `if pick` condition. If `pick` is None, this crashes. The ternary should be:

```python
notes=f"Auto-paper buy. Forecast: {pick.forecast_return_4d*100:.2f}%" if pick else "Auto-paper buy",
```

Actually, looking again: Python evaluates the f-string `f"Auto-paper buy. Forecast: {pick.forecast_return_4d*100:.2f}%"` eagerly. If `pick` is None, `pick.forecast_return_4d` raises `AttributeError`. **This is a confirmed crash bug.** The fix:

```python
notes=(f"Auto-paper buy. Forecast: {pick.forecast_return_4d*100:.2f}%" if pick else "Auto-paper buy"),
```

Wait — re-reading more carefully, the ternary `A if cond else B` in Python evaluates `cond` first, then only evaluates the chosen branch. So if `pick` is None, it evaluates `"Auto-paper buy"` and never touches `pick.forecast_return_4d`. So this is **NOT a bug** — Python's conditional expression is lazy. Retracting.

**Correction:** NOT a bug. Python ternary is lazy. ✅

#### BUG-E06: No max-hold-day exit enforcement
**Lines:** entire file

**Problem:** `planned_exit_date` is set (line 179) but no script ever checks it. There is no cron job or scheduled task that says "if `planned_exit_date < now()`, liquidate." Positions that don't hit their stop or target will remain open forever.

### ⚠️ Edge Cases Not Handled

- **EC-E01:** If `account.get("cash", 0)` returns negative (margin used), `heat` calculation divides by negative — nonsensical result.
- **EC-E02:** If Alpaca `get_positions()` returns an error dict (see BUG-B01 / EC-B01), `{p["symbol"] for p in open_positions}` will raise `KeyError` because the error dict has no `"symbol"` key.
- **EC-E03:** If `daily_realized_pnl` is exactly equal to `-max_loss`, the `<=` comparison triggers the circuit breaker. This is correct behavior, but note that the daily P/L only counts *realized* losses — unrealized losses on open positions don't count.
- **EC-E04:** No check for market hours. If run during pre-market or after-hours, bracket orders may behave differently (GTC legs persist, but market order fill prices may be extreme).

### 💡 Improvement Opportunities

- **IMP-E01:** Add a **max-hold-day liquidation script** that runs daily: find positions where `planned_exit_date < now()` and `status == open`, submit market sell, update DB. This is critical — without it, the `max_hold_days` parameter is cosmetic.
- **IMP-E02:** Fix portfolio heat: use `account["equity"]` as denominator, and use current market values from `broker.get_positions()` instead of stale `notional`.
- **IMP-E03:** Add **trailing stop** logic: after a position gains >X%, move the stop-loss up to breakeven or to a trailing percentage. Currently stops are fixed at entry and never adjusted.
- **IMP-E04:** Add **partial exit** support: when a position hits 50% of take-profit, sell half and move stop to breakeven. This locks in gains while leaving upside.
- **IMP-E05:** Re-fetch `skip_symbols` from Alpaca inside the loop, or at least re-check before each order submission.

### 🔒 Risk Control Gaps

- **RISK-E01:** No daily loss circuit breaker for *unrealized* losses. Only realized P/L counts. A position down 30% that hasn't been sold doesn't trigger the breaker.
- **RISK-E02:** No per-symbol concentration limit. If the same symbol appears in multiple days' picks (possible if `is_active` logic has bugs), you could accumulate oversized position in one name.
- **RISK-E03:** No maximum drawdown check at portfolio level. Only daily max loss is checked.

---

## 3. `daily_market_scan.py`

### 🐛 Confirmed Bugs

#### BUG-S01: `persist_snapshots()` `on_conflict_do_update` only updates OHLCV, not technical indicators
**Lines:** 28–56

```python
.on_conflict_do_update(
    index_elements=["symbol", "date"],
    set_={
        "open": ...,
        "high": ...,
        "low": ...,
        "close": ...,
        "volume": ...,
    },
)
```

**Problem:** The `INSERT` includes `rsi_14`, `macd`, `macd_signal`, `bb_upper`, `bb_lower`, `atr_14`, `sma_20`, `sma_50` but the `on_conflict_do_update` only updates `open/high/low/close/volume`. If a snapshot already exists for that date, technical indicators are never updated. This is a **data staleness bug** — re-running the scan for the same date won't update indicators.

#### BUG-S02: Old picks marked inactive but their `exited_at` / `exit_return` never set
**Lines:** 88–93

```python
result = await db.execute(
    select(StockPick).where(StockPick.is_active == True)
)
for old in result.scalars():
    old.is_active = False
```

No `exited_at` timestamp is set. This makes it impossible to track when a pick was deactivated.

#### BUG-S03: `universe="sp500"` but class is `NASDAQ100Fetcher`
**Line:** 80

```python
fetcher = NASDAQ100Fetcher(lookback_days=120, universe="sp500")
```

The class is named `NASDAQ100Fetcher` but configured with `universe="sp500"`. This is a naming inconsistency that could cause confusion. Not a runtime bug if the class supports the parameter, but misleading.

### ⚠️ Edge Cases Not Handled

- **EC-S01:** No error handling around `fetcher.fetch()`. If the data source is down, `raw.empty` is checked, but network errors would raise unhandled exceptions.
- **EC-S02:** `build_technical_features(raw)` — if this fails for one symbol, the entire scan fails. No per-symbol error isolation.
- **EC-S03:** The scan runs `execute_paper_trades()` inline (line 125) rather than as a separate process. If the scan crashes during trade execution, the picks are already persisted but trades weren't executed — inconsistent state.
- **EC-S04:** No deduplication check: if the script is run twice in one day, it creates duplicate `StockPick` rows for the same symbol/date (all marked `is_active=True` since the deactivation only happens at the *start* of the next run).

### 💡 Improvement Opportunities

- **IMP-S01:** Fix `on_conflict_do_update` to include all technical indicator columns.
- **IMP-S02:** Set `exited_at` when deactivating old picks.
- **IMP-S03:** Add idempotency: check if today's picks already exist before creating new ones.
- **IMP-S04:** Separate scan and execution into independent cron jobs so a failure in one doesn't affect the other.

---

## 4. `portfolio.py` — PaperPortfolioManager

### 🐛 Confirmed Bugs

#### BUG-P01: `build_plan()` uses `predicted_close_4d` as entry price when `current_price` is None
**Lines:** 57–58

```python
price = current_price or pick.predicted_close_4d
```

**Problem:** `predicted_close_4d` is the *4-day forecast*, not the current price. If `current_price` is not passed (and it isn't — `execute_paper_trades.py` never passes it), the notional calculation uses the predicted future close as the entry price. This means:
- If the forecast is bullish (+5%), `price` = predicted close (higher than current), so fewer shares are bought.
- The `stop_loss` and `take_profit` from the recommendation are based on *current* close, but `notional` is based on *future* close → mismatch.

**Impact:** Position sizing is wrong. Should use `pick.latest_close` or fetch a real-time quote.

#### BUG-P02: `_round_qty()` rounds to 4 decimal places but `build_plan()` uses `int()` for whole shares
**Lines:** 43–44 vs 63

```python
def _round_qty(self, qty: float, price: float) -> float:
    return float(Decimal(str(qty)).quantize(Decimal("0.0001")))

# But in build_plan:
shares = int(self.capital_per_trade / price)
```

`_round_qty()` is defined but never called. `build_plan()` uses `int()` truncation which is correct for whole shares, but `_round_qty()` is dead code. Not a bug, but confusing dead code.

#### BUG-P03: `select_picks_to_buy()` doesn't count currently open positions correctly
**Lines:** 82–93

```python
slots_remaining = max(0, self.max_open_positions - len(blocked_symbols))
```

`blocked_symbols` is `skip_symbols` from `execute_paper_trades.py` which = Alpaca open positions ∪ pending sell symbols. But `max_open_positions` is the max number of concurrent positions. If you have 3 open positions and 2 pending sells (5 total blocked), and `max_open_positions=5`, then `slots_remaining = 0`. But you actually have 3 open + 2 liquidating = 5 total, so 0 new slots is correct. However, if the 2 pending sells are for *different* symbols than the 3 open positions, you'd have 5 blocked symbols, which is correct. The bug is if a pending sell is for the same symbol as an open position — then `blocked_symbols` deduplicates and you'd get 4, giving 1 slot when there should be 0.

Wait, actually `skip_symbols = open_symbols | pending_sell_symbols` — set union. If a position is open AND has a pending sell (e.g., stop order), it appears once in the set. So `len(blocked_symbols)` could be < actual open positions if some have pending sells. Example: 3 open positions, 2 of which have pending sell orders. `open_symbols` = 3, `pending_sell_symbols` = 2, union = 3. `slots_remaining = 5 - 3 = 2`. But you actually have 3 positions, so 2 new slots is correct. OK, this is actually fine.

**Real bug:** `slots_remaining` doesn't account for positions that are open in the local DB but not yet at Alpaca (e.g., just-placed bracket order that hasn't filled). The local DB check in `execute_paper_trades.py` (line 133-139) catches this, but `select_picks_to_buy()` doesn't.

### ⚠️ Edge Cases Not Handled

- **EC-P01:** `build_plan()` doesn't validate that `stop_loss < entry_price < take_profit`. If the recommender provides inverted values, the bracket order will be rejected by Alpaca.
- **EC-P02:** If `capital_per_trade / price` rounds to 0 shares (high-priced stock), the pick is silently skipped. No logging or warning.
- **EC-P03:** No check for `notional < 1.0` after rounding — actually this IS checked (line 69-70). ✅
- **EC-P04:** `execute_buy()` doesn't verify the broker order actually filled. A bracket order that's `accepted` but not `filled` returns `success=True`, and `execute_paper_trades.py` records it with `filled_qty=None` → falls back to `plan.shares` and `plan.entry_price`.

### 💡 Improvement Opportunities

- **IMP-P01:** Pass real-time price into `build_plan()` from `broker.get_position()` or a quote API instead of using `predicted_close_4d`.
- **IMP-P02:** Add **volatility-based position sizing**: reduce `capital_per_trade` when ATR is high. E.g., `adjusted_capital = capital_per_trade * (1 - volatility_20d)`.
- **IMP-P03:** Add **trailing stop** support to `TradePlan`: `trailing_stop_pct`, `trailing_stop_active` fields. After price reaches X% gain, activate trailing stop.
- **IMP-P04:** Add **partial exit levels**: `take_profit_1`, `take_profit_2`, `exit_qty_1`, `exit_qty_2` for scaling out.
- **IMP-P05:** Remove dead `_round_qty()` method or use it.

---

## 5. `recommender.py` — StockRecommender

### 🐛 Confirmed Bugs

#### BUG-R01: `rank()` returns ALL top_n recommendations including "avoid" and "hold"
**Lines:** 77–81

```python
def rank(self, scores: List[StockScore], top_n: int = 10) -> List[StockRecommendation]:
    ranked = sorted(scores, key=lambda s: s.score, reverse=True)
    return [self.recommend(s) for s in ranked[:top_n]]
```

**Problem:** The method returns the top N by score regardless of action. A stock with score 0.80 (buy) and one with score 0.45 (hold) are both returned. `execute_paper_trades.py` filters for `TradeAction.buy` only, so holds/avoids are harmlessly ignored. But `daily_market_scan.py` persists ALL of them as `StockPick` rows with their respective actions. This means the DB accumulates "hold" and "avoid" picks that are visible but never actionable. Not a crash bug, but a data quality issue.

#### BUG-R02: `confidence` calculation can exceed 1.0
**Line:** 63 (in `recommend()` for buy):

```python
confidence=min(1.0, score.score + 0.15),
```

This is clamped with `min(1.0, ...)`. ✅ But for the "avoid with negative forecast" path (line 38):

```python
confidence=1.0 - score.score,
```

If `score.score` is 0.1, confidence = 0.9. That's fine. No bug here.

### ⚠️ Edge Cases Not Handled

- **EC-R01:** `recommend()` doesn't handle `score.score == None` or NaN. If the scorer returns NaN (e.g., from a division by zero in technical calculation), comparisons like `score.score >= self.buy_threshold` will return `False` and the stock is marked "avoid" silently.
- **EC-R02:** `stop_loss` and `take_profit` from `StockScore` are passed through without validation. If ATR is NaN, the scorer's fallback (`close * 0.95` / `close * 1.05`) is used, but if ATR is 0, stop = close, take_profit = close → immediate trigger.
- **EC-R03:** No sector/industry diversification check. The top N picks could all be from the same sector (e.g., all tech stocks), increasing correlated risk.

### 💡 Improvement Opportunities

- **IMP-R01:** Filter in `rank()`: only return `buy` recommendations, or add a `buy_only` parameter.
- **IMP-R02:** Add **sector diversification** constraint: max 2-3 picks from the same sector.
- **IMP-R03:** Add **correlation filtering**: check historical correlation between top picks and skip highly correlated ones.
- **IMP-R04:** Consider adding a **volatility-adjusted score** that penalizes extremely volatile stocks more than the current `vol_score` does.
- **IMP-R05:** The `playbook` string for buy uses `score.latest_close` for the entry price, but the actual entry will be at market price which could differ significantly. Use a range or estimate.

---

## 6. `scorer.py` — StockScorer (Bonus, since it drives the recommender)

### 🐛 Confirmed Bugs

#### BUG-SC01: `vol_score` uses raw volatility without annualization check
**Lines:** 90–91

```python
vol = latest["volatility_20d"] if pd.notna(latest["volatility_20d"]) else 0.5
vol_score = max(0.0, 1.0 - vol * 2.0)
```

If `volatility_20d` is daily volatility (e.g., 0.02 = 2% daily), then `vol * 2.0 = 0.04`, `vol_score = 0.96` — almost no penalty. If it's annualized (e.g., 0.40 = 40%), then `vol * 2.0 = 0.80`, `vol_score = 0.20`. The behavior depends entirely on how `volatility_20d` is computed upstream. If it's raw standard deviation of daily returns, most stocks get almost no volatility penalty.

#### BUG-SC02: Stop-loss/take-profit based on ATR can produce invalid values
**Lines:** 100–101

```python
stop = close - 2 * float(atr) if pd.notna(atr) else close * 0.95
target = close + 4 * float(atr) if pd.notna(atr) else close * 1.05
```

If `atr` is 0 or very small (low volatility period), stop and target are essentially at the close price. A stop at `close - 0.01` would trigger immediately on any tick. The risk-reward ratio is 2:4 = 1:2, which is fine, but the absolute values can be impractical.

If `atr` is negative (shouldn't happen but could from data errors), stop would be *above* close and target *below* → inverted.

### 💡 Improvement Opportunities

- **IMP-SC01:** Add minimum ATR threshold: `atr = max(atr, close * 0.01)`.
- **IMP-SC02:** Add **dynamic stop-loss** based on support/resistance levels instead of fixed ATR multiplier.
- **IMP-SC03:** Add **regime detection**: in high-volatility regimes (VIX > 30), widen stops and reduce position size. In low-volatility regimes, tighten stops.

---

## 7. `sync_alpaca_fills.py` (Bonus — Exit Reconciliation)

### 🐛 Confirmed Bugs

#### BUG-SYNC01: Exit price calculation from sell orders can divide by zero
**Lines:** `sync_positions()` around line 195

```python
avg_exit = sum(o.qty * (o.raw_response.get("filled_avg_price") or 0) for o in sell_orders if o.qty) / sum(o.qty for o in sell_orders if o.qty)
```

If all sell orders have `qty = None` or 0, this divides by zero. The `if o.qty` guard filters None/0, but if the filtered list is empty, `sum(...) = 0` → `ZeroDivisionError`.

#### BUG-SYNC02: `exit_price` fallback to `take_profit` or `stop_loss` is inaccurate
**Line:** 188

```python
exit_price = pos.exit_price or pos.take_profit or pos.stop_loss
```

If the position was closed by a market sell (manual liquidation), the exit price is neither the take-profit nor the stop-loss. Using these as fallbacks produces incorrect P/L.

### ⚠️ Edge Cases

- **EC-SYNC01:** No handling of partial fills. If a stop order partially fills (e.g., 50 of 100 shares), the position is marked closed but only half the shares were sold. The remaining shares are untracked.
- **EC-SYNC02:** `import_unknown_alpaca_orders` creates positions for unknown buys with `entry_price=filled_avg`. If `filled_avg` is None (order not yet filled), `entry_price=None` → downstream P/L calculations crash.

---

## Summary of Critical Issues

| Priority | File | Bug ID | Description |
|----------|------|--------|-------------|
| 🔴 CRITICAL | broker.py | BUG-B02 | `submit_oco_exit()` not a true OCO — can create unintended shorts |
| 🔴 CRITICAL | execute_paper_trades.py | BUG-E06 | No max-hold-day exit enforcement — positions stay open forever |
| 🔴 CRITICAL | execute_paper_trades.py | BUG-E01 | Portfolio heat calculation wrong (stale notional / cash-only denominator) |
| 🔴 CRITICAL | portfolio.py | BUG-P01 | `build_plan()` uses `predicted_close_4d` as entry price — wrong position sizing |
| 🟠 HIGH | daily_market_scan.py | BUG-S01 | `on_conflict_do_update` doesn't update technical indicators |
| 🟠 HIGH | broker.py | BUG-B03 | `submit_oco_exit()` — partial failure leaves orphaned orders |
| 🟠 HIGH | execute_paper_trades.py | BUG-E04 | Phantom positions when bracket order accepted but not filled |
| 🟠 HIGH | sync_alpaca_fills.py | BUG-SYNC01 | Division by zero in exit price calculation |
| 🟡 MEDIUM | scorer.py | BUG-SC01 | Volatility penalty depends on undefined vol scale |
| 🟡 MEDIUM | scorer.py | BUG-SC02 | ATR=0 → stop/target at close → immediate trigger |
| 🟡 MEDIUM | daily_market_scan.py | BUG-S04 | No dedup — re-run creates duplicate active picks |
| 🟡 MEDIUM | broker.py | EC-B01 | `get_positions()` error dict causes KeyError downstream |

## Top Exit Strategy Improvements

1. **Trailing stops:** After +2% gain, move stop to breakeven. After +4% gain, trail at 2% below current price. Requires a monitoring loop (not currently present).
2. **Partial exits:** Sell 50% at first take-profit, move stop to breakeven on remainder, let runner go to second target.
3. **Volatility-based stops:** Use ATR multiplier that adapts — `stop = close - max(2*ATR, 1.5% of close)`. Current fixed 2*ATR can be too tight in calm markets or too wide in volatile ones.
4. **Time-based exits:** Enforce `max_hold_days` with a daily liquidation script. Currently `planned_exit_date` is set but never checked.
5. **Breakeven stop activation:** When position reaches 50% of take-profit distance, move stop to entry price. Locks in no-loss exit.

## Top Risk Control Gaps

1. **No portfolio-level drawdown limit:** Only daily realized loss is checked. Multi-day drawdowns are unbounded.
2. **No concentration limit:** Multiple picks in the same symbol or sector can accumulate.
3. **No unrealized loss circuit breaker:** Open positions losing 30% don't trigger any protection.
4. **No market regime filter:** The system trades the same way in bull, bear, and sideways markets.
5. **No correlation check:** Top picks could be highly correlated, creating effective concentration.