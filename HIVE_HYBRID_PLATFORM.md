# HIVE Hybrid Trading Platform — Master Architecture

## Vision
A multi-signal, multi-model trading system that combines:
- Technical analysis (existing)
- Vendor incident alpha (existing, PulseWatch + TimesFM)
- ML/AI forecasting (TimesFM existing + Qlib/TFT/FinRL to add)
- Alternative data signals (insider, congressional, sentiment, earnings)
- Quantum-inspired portfolio optimization
- Reinforcement learning position management

## Current State (June 19, 2026)
- ✅ S&P 500 scanner (503 symbols, daily 7 PM CT)
- ✅ Technical indicators (RSI, MACD, BB, ATR, SMA)
- ✅ TimesFM microservice (local GPU, 4-day forecasts)
- ✅ Vendor incident alpha (35 vendors, precision map, TimesFM impact forecast)
- ✅ Alpaca paper trading ($10K, bracket orders, trailing stops, breakeven)
- ✅ Max-hold-day exit enforcement (10 AM CT liquidation)
- ✅ Sync system (imports unknown Alpaca orders/positions)

## Phase 1 — Foundation Signals (Week 1)
### 1.1 Kelly Criterion Position Sizing
- Replace fixed $2K per trade with fractional Kelly (0.25x)
- Use rolling 30-day win rate + average win/loss
- Expected: +0.2-0.5 Sharpe improvement
- Effort: ~100 lines in portfolio.py

### 1.2 FinBERT Sentiment Analysis
- Download FinBERT model (ProsusAI/finbert) to local GPU
- Daily scan: fetch news headlines for top 50 S&P 500 picks
- Sentiment score: positive/negative/neutral → filter/boost signal
- Expected: filter out negative-sentiment stocks before buying
- Effort: FinBERT model + news fetcher + sentiment scorer

### 1.3 Insider Trading (Form 4) Scanner
- Fetch SEC EDGAR Form 4 filings daily
- Cluster buys: 3+ insiders buying within 30 days = strong signal
- Free via SEC EDGAR API (https://www.sec.gov/cgi-bin/browse-edgar)
- Expected: +2-4% abnormal returns on cluster buys
- Effort: EDGAR fetcher + cluster detector + signal integrator

### 1.4 Congressional Trading Tracker
- Free APIs: capitol-api (GitHub), CapitolExposed, CongressInvests
- Track committee members buying in their oversight sectors
- Signal: BUY when committee member buys, AVOID when sells
- Expected: +4-6% abnormal returns (12-month horizon, but front-loaded)
- Effort: API client + signal generator

### 1.5 Pre-FOMC Announcement Drift
- Enter long SPY at close D-2 before FOMC meetings
- Exit at close D0 (meeting day)
- Sharpe 0.5-0.8, only trades ~5% of days
- Effort: FOMC calendar + SPY trade executor

## Phase 2 — ML Enhancement (Week 2-4)
### 2.1 Microsoft Qlib Integration
- GitHub: microsoft/qlib (40K+ stars)
- Institutional-grade ML pipeline for quantitative trading
- Replace ad-hoc feature engineering with Qlib's framework
- Add LightGBM/XGBoost models for cross-sectional prediction
- Expected: better stock ranking, factor discovery

### 2.2 Earnings Call NLP (PEAD)
- Fetch earnings call transcripts from free sources
- FinBERT sentiment on Q&A section (less scripted = more signal)
- Post-Earnings Announcement Drift: buy positive surprise, avoid negative
- 5-20 day hold window aligns with swing trading
- Expected: +1-3% abnormal returns over 5-20 days

### 2.3 VIX Term Structure Regime Filter
- VIX futures curve: contango (normal) vs backwardation (stress)
- When backwardated: reduce position sizes, tighten stops
- When steep contango: normal trading, wider stops
- Expected: avoid trading during high-vol regimes

### 2.4 Hierarchical Risk Parity (HRP)
- Replace equal-weight portfolio with HRP allocation
- PyPortfolioOpt library (free, pip install)
- Allocates by risk contribution, not dollar weight
- More robust than Markowitz, no covariance inversion needed
- Expected: lower portfolio drawdowns

### 2.5 Black-Litterman with Vendor Alpha
- Use vendor incident signals as "views" in Black-Litterman model
- Combine market equilibrium with our active views
- Output: adjusted portfolio weights reflecting both
- Expected: systematic integration of vendor alpha into position sizing

## Phase 3 — Advanced Models (Month 2-3)
### 3.1 FinRL Reinforcement Learning Agent
- GitHub: AI4Finance-Foundation/FinRL (15K stars)
- PPO/SAC agent trained on S&P 500 historical data
- Manages position entry/exit/sizing as RL problem
- Start with paper trading, compare vs current system
- Expected: learn optimal exit timing beyond fixed rules

### 3.2 Temporal Fusion Transformer (TFT)
- Multi-horizon forecasting with known + unknown inputs
- Complements TimesFM: TFT for direction, TimesFM for magnitude
- GitHub: Soham-Deshpande/Stock-TFT (126 stars)
- Expected: better forecast accuracy on directional calls

### 3.3 StatArb Pairs Trading
- Cointegration-based pairs within S&P 500
- Trade spread deviations (z-score > 2 = entry, z-score < 0.5 = exit)
- Market-neutral: long one, short other
- Expected: uncorrelated alpha to directional swing trades

### 3.4 Options Flow Confirmation
- GitHub: fintools-ai/mcp-order-flow-server
- GammaRips free MCP (18 tools, no auth)
- Use unusual options activity as confirmation signal
- Expected: filter false positives from technical signals

### 3.5 SEC Risk Factor Diffs
- RiskDiff.com tracks 10-K risk changes for 431 S&P 500 companies
- New risk language = forward-looking negative signal
- 149 companies recently added AI risk language
- Expected: early warning for fundamental deterioration

## Phase 4 — Quantum-Inspired (Month 3-6)
### 4.1 Simulated Bifurcation Portfolio Optimization
- Toshiba's simulated bifurcation algorithm (runs on classical GPU)
- Solve portfolio optimization as Ising/QUBO problem
- GitHub: FixstarsLaboratories/simulated-bifurcation
- Expected: faster/better portfolio optimization for 500 assets

### 4.2 Tensor Network Time Series
- Matrix Product State (MPS) for compressing multi-stock correlations
- GitHub: tensor-network time series repos
- Expected: capture inter-stock dependencies TimesFM misses

### 4.3 Qiskit Finance Exploration
- Run QAOA/VQE on classical simulator for small portfolios (10-20 assets)
- GitHub: qiskit-community/qiskit-finance (314 stars)
- Research only — no production advantage yet (5-10 years away)
- Expected: understand quantum portfolio optimization for future

## Signal Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HIVE TRADING ENGINE                        │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Technical   │  │ Vendor Alpha │  │ Alternative Data    │  │
│  │ Indicators  │  │ (PulseWatch)  │  │ (Insider/Congress)  │  │
│  │ RSI/MACD/BB │  │ 35 vendors   │  │ Form 4 / Senate     │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                     │             │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌─────────┴──────────┐  │
│  │ TimesFM     │  │ FinBERT      │  │ Earnings NLP       │  │
│  │ Forecasts   │  │ Sentiment    │  │ PEAD Signal        │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                     │             │
│  ┌──────┴────────────────┴─────────────────────┴──────────┐  │
│  │              SIGNAL FUSION LAYER                        │  │
│  │  Weight: technical(0.3) + forecast(0.25) + sentiment(0.15)│
│  │  + vendor_alpha(0.15) + insider(0.10) + congress(0.05)   │
│  │  → Composite score per symbol → Rank → Top 15            │
│  └───────────────────────┬───────────────────────────────┘  │
│                           │                                  │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              RISK MANAGEMENT LAYER                      │  │
│  │  Kelly sizing + HRP allocation + VIX regime filter     │  │
│  │  Black-Litterman views → Portfolio weights             │  │
│  │  Max drawdown + concentration + heat limits            │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                           │                                  │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              EXECUTION LAYER                            │  │
│  │  Alpaca bracket orders + trailing stops + breakeven    │  │
│  │  Max-hold liquidation + Pre-FOMC overlay               │  │
│  │  FinRL agent for exit optimization (Phase 3)           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Signal Weighting (Phase 1)
| Signal | Weight | Source | Latency |
|--------|--------|--------|---------|
| Technical indicators | 30% | yfinance + computed | Daily |
| TimesFM forecast | 25% | Local GPU microservice | ~1.5s/symbol |
| Vendor incident alpha | 15% | PulseWatch + precision map | Real-time |
| FinBERT sentiment | 15% | News headlines + local model | Daily |
| Insider Form 4 | 10% | SEC EDGAR | 2-5 day lag |
| Congressional trades | 5% | Free APIs | 15-45 day lag |

## Implementation Priority (by edge × feasibility)
1. Kelly sizing — 100 lines, immediate Sharpe boost
2. FinBERT sentiment — model download + news fetcher
3. Insider Form 4 — SEC EDGAR API + cluster detection
4. Congressional tracker — free API client
5. Pre-FOMC drift — calendar + SPY executor
6. Qlib integration — ML pipeline upgrade
7. HRP — PyPortfolioOpt
8. VIX regime filter — VIX futures data
9. Black-Litterman — views integration
10. FinRL agent — RL training
11. TFT — multi-horizon forecast
12. StatArb pairs — cointegration
13. Options flow — GammaRips MCP
14. SEC risk diffs — RiskDiff API
15. Simulated bifurcation — portfolio optimization