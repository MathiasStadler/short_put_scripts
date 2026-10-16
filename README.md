# Short Put Screener Tools

Dieses Verzeichnis enthält Skripte für das Screening von Short Put-Optionen via yfinance und IBKR.

## Verzeichnisstruktur

```
/home/hermes/short_put_scripts/
├── short_put_screener.py    # Täglicher Short Put Screener
├── download_earnings.py     # Earnings Kalender Downloader
└── my_project_env/          # Python Virtual Environment
```

## Installation & Setup

1. **Virtual Environment aktivieren:**
   ```bash
   cd /home/hermes/short_put_scripts
   source my_project_env/bin/activate
   ```

2. **Skripte ausführen:**
   ```bash
   my_project_env/bin/python short_put_screener.py
   # oder
   python short_put_screener.py  # nach Activierung
   ```

## Scripts im Detail

### 1. `short_put_screener.py`
Täglicher Screener für Short Put-Optionen.

**Kriterien (in Config oben im Skript einstellbar):**
- `MAX_STOCK_PRICE = 100.0` - Nur Aktien ≤ $100
- `MIN_PREMIUM_EUR = 80.0` - Mindestprämie pro Kontrakt
- `MAX_DELTA = -0.30` - Delta > -0.30 (OTM Puts)
- `MIN_DTE = 7` / `MAX_DTE = 45` - Tage bis Expiry
- `MAX_DIST_PCT = -15.0` - Max % unter Spot (OTM-Limit)
- `REQUIRE_REAL_BID = False` - True = nur echte Bids (EU-Stocks)

**Output:**
- Printet Top-Gelegenheiten nach CRV (Return on Capital)
- Speichert CSV: `short_puts_YYYYMMDD.csv`
- Enthält Spalten: ticker, strike, premium, delta, crv, roc, dist_pct, price_src, next_earnings

### 2. `download_earnings.py`
Lädt Earnings-Daten von yfinance für 74 Ticker.

**Output:**
- Speichert: `earnings_calendar.csv`
- Format: ticker, earnings_date, source
- Erkennt Termine bis zu 6 Monate im Voraus

## Beispiel-Output

```
SHORT PUT SCREENER  |  2026-10-15 16:08
Kriterien: Premium >= 80.0€  |  Delta > -0.3  |  DTE 7-45  |  Keine Earnings  |  Max Stock Price $100.0

✅ 9 von 63 Ticker <= $100.0: KO, PFE, BMY, SLB, OXY, UBER, PYPL, ZM, DOCU

  [1/9] KO... 0 Treffer
  [2/9] PFE... 0 Treffer
  [3/9] BMY... 0 Treffer
  [4/9] SLB... 0 Treffer
  [5/9] OXY... 0 Treffer
  [6/9] UBER... 0 Treffer
  [7/9] PYPL... 0 Treffer
  [8/9] ZM... 12 Treffer
  [9/9] DOCU... 5 Treffer

GESAMT: 17 Short-Put-Gelegenheiten

TOP 10 nach CRV:
ticker     expiry  strike  premium_eur  delta   crv   roc  dist_pct price_src next_earnings
  DOCU 2026-11-20    70.0        164.0 -0.237 0.117 11.71     -9.58       BID    2026-12-03
  ZM 2026-11-20    87.5        182.0 -0.260 0.104 10.40     -8.35       BID    2026-11-24
  ...
```

## Abhängigkeiten

Die im `my_project_env/` Virtual Environment installierten Pakete:
- yfinance, pandas, numpy, scipy
- BeautifulSoup4 (für Download-Script)
- Läuft unter Python 3.13

## Täglicher Workflow

```bash
# 1. Earnings Kalender aktualisieren (wöchentlich ausreichend)
my_project_env/bin/python download_earnings.py

# 2. Daily Screening ausführen
my_project_env/bin/python short_put_screener.py
```

Die CSV-Dateien landen im Verzeichnis `/home/hermes/short_put_scripts/`.