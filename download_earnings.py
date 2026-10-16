#!/usr/bin/env python3
"""
Earnings Calendar Downloader - yfinance für spezifische Ticker
Lädt Earnings-Daten via yfinance für gegebene Ticker-Liste und speichert als CSV.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

OUTPUT_FILE = "earnings_calendar.csv"
MONTHS_AHEAD = 6

# Ticker für die wir Earnings brauchen (aus short_put_screener)
TICKERS = [
    "KO", "PFE", "BMY", "SLB", "OXY", "UBER", "PYPL", "ZM", "DOCU",
    # Erweiterbar: alle Ticker aus dem Screener
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA",
    "AVGO", "PEP", "COST", "ADBE", "NFLX", "CSCO", "TMUS", "INTC",
    "AMD", "TXN", "QCOM", "AMAT", "HON", "INTU", "SBUX", "BKNG",
    "JPM", "V", "MA", "UNH", "HD", "PG", "WMT", "ABBV", "MRK",
    "TMO", "ABT", "DHR", "LLY", "AMGN", "XOM", "CVX", "COP",
    "EOG", "MPC", "VLO", "CAT", "DE", "MMM", "GE", "RTX",
    "LMT", "NOC", "BA", "ASML", "SAP", "ORCL", "CRM", "NOW",
    "SNPS", "CDNS", "UBER", "ABNB", "SQ", "SHOP", "ROKU", "TEAM"
]

def get_earnings_for_ticker(ticker):
    """Holt Earnings-Daten für einen Ticker via yfinance."""
    try:
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        
        if cal is None:
            return []
        
        earnings = []
        today = datetime.now().date()
        cutoff = today + timedelta(days=MONTHS_AHEAD * 30)
        
        # yfinance calendar kann Dict oder DataFrame sein
        dates = []
        if isinstance(cal, pd.DataFrame):
            dates = pd.to_datetime(cal.index).tolist()
        elif isinstance(cal, dict):
            # 'Earnings Date' Key
            ed = cal.get('Earnings Date', [])
            if isinstance(ed, list):
                dates = [pd.to_datetime(d).date() for d in ed]
            elif ed:
                dates = [pd.to_datetime(ed).date()]
            else:
                # Fallback: alle values
                for v in cal.values():
                    try:
                        dates.append(pd.to_datetime(v).date())
                    except:
                        pass
        
        for earn_date in dates:
            if isinstance(earn_date, pd.Timestamp):
                earn_date = earn_date.date()
            if today <= earn_date <= cutoff:
                earnings.append({
                    'ticker': ticker,
                    'earnings_date': earn_date.strftime('%Y-%m-%d'),
                    'source': 'yfinance'
                })
        
        return earnings
        
    except Exception as e:
        print(f"  {ticker}: {e}")
        return []


def main():
    print(f"{'='*60}")
    print(f"EARNINGS CALENDAR (yfinance)  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"Ticker: {len(TICKERS)} | Monate voraus: {MONTHS_AHEAD}")
    
    all_earnings = []
    
    for i, ticker in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {ticker}...", end=" ", flush=True)
        earnings = get_earnings_for_ticker(ticker)
        all_earnings.extend(earnings)
        print(f"{len(earnings)} Termine")
        time.sleep(0.2)  # yfinance rate limit
    
    if all_earnings:
        df = pd.DataFrame(all_earnings)
        df = df.drop_duplicates(subset=['ticker', 'earnings_date'], keep='first')
        df = df.sort_values(['earnings_date', 'ticker'])
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Gespeichert: {OUTPUT_FILE} ({len(df)} Einträge)")
        print(df.to_string(index=False))
    else:
        print("\n❌ Keine Earnings-Daten gefunden")
        pd.DataFrame(columns=['ticker', 'earnings_date', 'source']).to_csv(OUTPUT_FILE, index=False)


if __name__ == '__main__':
    main()