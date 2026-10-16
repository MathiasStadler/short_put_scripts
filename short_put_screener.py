#!/usr/bin/env python3
"""
Daily Short Put Screener für yfinance
- Short Puts mit Delta > -0.30 (d.h. -0.30 bis 0)
- Mindestens 80 € Prämie pro Kontrakt (100 Aktien)
- Keine Earnings während Optionslaufzeit
- CRV (Chance-Risiko-Verhältnis) Anzeige
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
import math
import warnings
warnings.filterwarnings('ignore')

# ─── Config ───
EARNINGS_CSV = "earnings_calendar.csv"  # Pfad zur Earnings-CSV
TICKERS = [
    "MSFT", "AAPL", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "V", "MA", "UNH", "HD", "PG", "KO", "PEP", "COST", "WMT",
    "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "LLY", "BMY", "AMGN",
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "OXY", "MPC", "VLO",
    "CAT", "DE", "HON", "MMM", "GE", "RTX", "LMT", "NOC", "BA",
    "ASML", "SAP", "ORCL", "CRM", "ADBE", "INTU", "NOW", "SNPS", "CDNS",
    "UBER", "ABNB", "PYPL", "SQ", "SHOP", "ROKU", "ZM", "DOCU", "TEAM",
]

MAX_STOCK_PRICE = 100.0       # Max Spot-Preis in $ (nur Aktien <= 100 $)
MIN_PREMIUM_EUR = 80.0        # Mindestprämie pro Kontrakt
MAX_DELTA = -0.30             # Delta > -0.30 (also -0.30 bis 0)
MIN_DTE = 7                   # Mindest Tage bis Expiry
MAX_DTE = 45                  # Max Tage bis Expiry
MAX_DIST_PCT = -15.0          # Max % unter Spot (OTM), z.B. -15%
MIN_VOLUME = 1                # Mindest Volume für Liquidität
MIN_OI = 10                   # Mindest Open Interest
RISK_FREE_RATE = 0.035        # ~3.5% risikofrei
REQUIRE_REAL_BID = False      # False = auch lastPrice/BS-Preis nutzen


# ─── Black-Scholes Delta für Puts ───
def bs_put_delta(S, K, T, r, sigma):
    """Delta eines European Put (negativ)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return norm.cdf(d1) - 1  # Put Delta = N(d1) - 1 (negativ)


# ─── Earnings aus CSV laden ───
def load_earnings_from_csv(csv_path=EARNINGS_CSV):
    """Lädt Earnings-Daten aus CSV und gibt Dict {ticker: [date objects]} zurück."""
    earnings_dict = {}
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return earnings_dict
        
        for _, row in df.iterrows():
            ticker = row['ticker']
            date_str = row['earnings_date']
            try:
                # pd.to_datetime gibt Timestamp, .date() macht daraus Python date
                earn_date = pd.to_datetime(date_str).date()
                if ticker not in earnings_dict:
                    earnings_dict[ticker] = []
                earnings_dict[ticker].append(earn_date)
            except:
                pass
        
        # Sortieren
        for ticker in earnings_dict:
            earnings_dict[ticker].sort()
            
    except FileNotFoundError:
        print(f"⚠️  Earnings-CSV nicht gefunden: {csv_path}")
    except Exception as e:
        print(f"⚠️  Fehler beim Laden der Earnings-CSV: {e}")
    
    return earnings_dict


# Global laden einmal
EARNINGS_DICT = load_earnings_from_csv()


def get_earnings_dates(ticker, months_ahead=3):
    """Gibt Earnings-Daten für Ticker aus geladenem Dict zurück."""
    dates = EARNINGS_DICT.get(ticker, [])
    cutoff = datetime.now().date() + timedelta(days=months_ahead * 30)
    return [d for d in dates if d <= cutoff]


def has_earnings_during_option(earnings_dates, expiry_date):
    """Prüft ob Earnings in [heute, expiry] liegen."""
    today = datetime.now().date()
    expiry = expiry_date  # bereits date object
    for ed in earnings_dates:
        # ed ist bereits date object aus CSV
        if today <= ed <= expiry:
            return True, ed.strftime("%Y-%m-%d")
    return False, None


def screen_ticker(ticker):
    """Screened einen Ticker nach Short-Put-Kriterien."""
    results = []
    try:
        tk = yf.Ticker(ticker)
        spot = tk.fast_info.get('last_price') or tk.info.get('currentPrice')
        if not spot:
            return results

        # Earnings laden
        earnings = get_earnings_dates(ticker)

        # Option Chains
        expirations = tk.options
        if not expirations:
            return results

        today = datetime.now().date()

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if dte < MIN_DTE or dte > MAX_DTE:
                continue

            # Earnings-Check
            has_ern, ern_date = has_earnings_during_option(earnings, exp_date)
            if has_ern:
                continue

            T = dte / 365.0
            chain = tk.option_chain(exp_str)
            puts = chain.puts.copy()

            if puts.empty:
                continue

            # IV aus yfinance nutzen (impliedVolatility Spalte)
            puts['iv'] = puts['impliedVolatility'].fillna(0)
            puts = puts[puts['iv'] > 0.01]

            # Prämie: bid bevorzugt, dann midpoint (bid+ask)/2, dann lastPrice, dann BS-Theoretisch
            puts['midpoint'] = (puts['bid'] + puts['ask']) / 2
            puts['bid_clean'] = puts['bid'].where(puts['bid'] > 0, puts['midpoint'])
            puts['bid_clean'] = puts['bid_clean'].where(puts['bid_clean'] > 0, puts['lastPrice'])
            # BS-Theoretischer Preis als letzter Fallback
            def bs_put_price(S, K, T, r, sigma):
                if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
                    return 0.0
                d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

            puts['bs_price'] = puts.apply(
                lambda row: bs_put_price(spot, row['strike'], T, RISK_FREE_RATE, row['iv']),
                axis=1
            )
            puts['bid_clean'] = puts['bid_clean'].fillna(puts['bs_price'])
            puts = puts[puts['bid_clean'] > 0]

            # Delta berechnen
            puts['delta'] = puts.apply(
                lambda row: bs_put_delta(spot, row['strike'], T, RISK_FREE_RATE, row['iv']),
                axis=1
            )

            # Filter: Delta > -0.30 (also -0.30 bis 0, OTM)
            puts = puts[(puts['delta'] > MAX_DELTA) & (puts['delta'] < 0)]

            # Distanz zu Spot in %
            puts['dist_pct'] = ((puts['strike'] - spot) / spot * 100).round(2)
            puts = puts[puts['dist_pct'] >= MAX_DIST_PCT]  # Nicht zu weit OTM

            # Liquiditäts-Filter
            puts = puts[(puts['volume'].fillna(0) >= MIN_VOLUME) | (puts['openInterest'].fillna(0) >= MIN_OI)]

            # Prämie pro Kontrakt (bid_clean * 100)
            puts['premium_eur'] = puts['bid_clean'] * 100
            puts = puts[puts['premium_eur'] >= MIN_PREMIUM_EUR]

            # Qualitäts-Flag: echter Bid vs. Midpoint vs. lastPrice vs. BS
            def price_source(row):
                if row['bid'] > 0:
                    return 'BID'
                elif row['midpoint'] > 0:
                    return 'MID'
                elif row['lastPrice'] > 0:
                    return 'LAST'
                else:
                    return 'BS'
            puts['price_src'] = puts.apply(price_source, axis=1)
            if REQUIRE_REAL_BID:
                puts = puts[puts['price_src'] == 'BID']

            if puts.empty:
                continue

            # CRV berechnen: Return on Capital at Risk
            # Für Short Put: Margin ≈ 20% * Strike (IBKR Standard) oder Strike - Spot
            # CRV = Premium / Margin_Requirement
            puts['max_profit'] = puts['premium_eur']
            # Margin für nackten Put ≈ max(20% * Strike, Strike - Spot + Premium) * 100
            margin_pct = 0.20
            puts['margin'] = np.maximum(puts['strike'] * margin_pct, puts['strike'] - spot + puts['bid_clean']) * 100
            puts['crv'] = puts['max_profit'] / puts['margin']
            puts['roc'] = (puts['max_profit'] / puts['margin'] * 100).round(2)  # Return on Capital %

            # Spot-Distanz in %
            puts['dist_pct'] = ((puts['strike'] - spot) / spot * 100).round(2)

            # Nächste Earnings aus CSV-Dict
            earnings_dates = EARNINGS_DICT.get(ticker, [])
            next_earnings = min(earnings_dates) if earnings_dates else None

            for _, row in puts.iterrows():
                results.append({
                    'ticker': ticker,
                    'spot': round(spot, 2),
                    'expiry': exp_str,
                    'dte': dte,
                    'strike': row['strike'],
                    'bid': round(row['bid'], 2),
                    'ask': round(row['ask'], 2),
                    'premium_eur': round(row['premium_eur'], 2),
                    'delta': round(row['delta'], 3),
                    'iv': round(row['iv'] * 100, 1),
                    'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                    'oi': int(row['openInterest']) if pd.notna(row['openInterest']) else 0,
                    'dist_pct': row['dist_pct'],
                    'crv': round(row['crv'], 3),
                    'roc': round(row['roc'], 2),
                    'max_profit': round(row['max_profit'], 2),
                    'margin': round(row['margin'], 2),
                    'price_src': row['price_src'],
                    'earnings_ok': '✓',
                    'next_earnings': next_earnings.strftime('%Y-%m-%d') if next_earnings else 'N/A'
                })
    except Exception as e:
        print(f"  [{ticker}] Fehler: {e}")
    return results


def main():
    print(f"{'='*100}")
    print(f"SHORT PUT SCREENER  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Kriterien: Premium >= {MIN_PREMIUM_EUR}€  |  Delta > {MAX_DELTA}  |  DTE {MIN_DTE}-{MAX_DTE}  |  Keine Earnings  |  Max Stock Price ${MAX_STOCK_PRICE}")
    print(f"{'='*100}")

    # ─── Pre-Filter: Nur Aktien <= MAX_STOCK_PRICE ───
    print(f"\n🔍 Prüfe Spot-Preise für {len(TICKERS)} Ticker (Max ${MAX_STOCK_PRICE})...")
    filtered_tickers = []
    for i, ticker in enumerate(TICKERS, 1):
        try:
            tk = yf.Ticker(ticker)
            spot = tk.fast_info.get('last_price') or tk.info.get('currentPrice')
            if spot and spot <= MAX_STOCK_PRICE:
                filtered_tickers.append(ticker)
                print(f"  [{i}/{len(TICKERS)}] {ticker}: ${spot:.2f} ✓")
            elif spot:
                print(f"  [{i}/{len(TICKERS)}] {ticker}: ${spot:.2f} ✗ (zu teuer)")
            else:
                print(f"  [{i}/{len(TICKERS)}] {ticker}: Kein Preis")
        except Exception as e:
            print(f"  [{i}/{len(TICKERS)}] {ticker}: Fehler ({e})")

    print(f"\n✅ {len(filtered_tickers)} von {len(TICKERS)} Ticker <= ${MAX_STOCK_PRICE}: {', '.join(filtered_tickers)}")
    print(f"{'='*100}\n")

    all_results = []
    for i, ticker in enumerate(filtered_tickers, 1):
        print(f"  [{i}/{len(filtered_tickers)}] {ticker}...", end=" ", flush=True)
        res = screen_ticker(ticker)
        all_results.extend(res)
        print(f"{len(res)} Treffer")

    if not all_results:
        print("\nKeine Treffer gefunden.")
        return

    df = pd.DataFrame(all_results)
    df = df.sort_values(['crv', 'premium_eur'], ascending=[False, False])

    # Ausgabe
    pd.set_option('display.max_rows', 100)
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 180)
    pd.set_option('display.colheader_justify', 'right')

    print(f"\n{'='*100}")
    print(f"GESAMT: {len(df)} Short-Put-Gelegenheiten")
    print(f"{'='*100}")
    print(df[[
        'ticker', 'spot', 'expiry', 'dte', 'strike', 'bid', 'ask',
        'premium_eur', 'delta', 'iv', 'volume', 'oi', 'dist_pct',
        'crv', 'roc', 'max_profit', 'margin', 'price_src', 'earnings_ok', 'next_earnings'
    ]].to_string(index=False))

    # Top 10 nach CRV
    print(f"\n{'─'*100}")
    print("TOP 10 nach CRV:")
    print(df.head(10)[['ticker', 'expiry', 'strike', 'premium_eur', 'delta', 'crv', 'roc', 'dist_pct', 'price_src', 'next_earnings']].to_string(index=False))

    # CSV speichern
    outfile = f"short_puts_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(outfile, index=False)
    print(f"\n💾 Gespeichert: {outfile}")


if __name__ == "__main__":
    main()