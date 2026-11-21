"""One-off research pull for the TYPE 8 study (branch research-t8 only; the live feed is untouched).
For each of the 22 symbols: ~15 months of 30-minute bars from Twelve Data -> S1 1-hour candles keyed by close time
(10:00 = C1 ... 16:00 = C7), exactly as feed.py builds them. If Twelve Data is unavailable, Yahoo 1-hour bars
(730 days) are used and flagged as src "yf1h" (Yahoo's hours start at :30, so C-numbers are approximate)."""
import json, os, time, urllib.parse, urllib.request
import pandas as pd, yfinance as yf
ET = "America/New_York"
SYMS = "AAPL AMD AMZN AVGO BAC CVX GLD GOOG INTC JPM META MSFT MU NFLX NVDA OXY QQQ SLV SPY TSLA USO XOM".split()
KEY = os.environ.get("TWELVEDATA_API_KEY", "")
os.makedirs("research/data", exist_ok=True)

def to_hours(d):
    close_at = (d.index + pd.Timedelta(minutes=30)).ceil("h")
    return d.groupby(close_at).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
                                   Close=("Close", "last"), Volume=("Volume", "sum"))

def td30(s):
    q = urllib.parse.urlencode({"symbol": s, "interval": "30min", "outputsize": 5000, "timezone": ET, "order": "ASC", "apikey": KEY})
    with urllib.request.urlopen("https://api.twelvedata.com/time_series?" + q, timeout=90) as r:
        js = json.load(r)
    if js.get("status") != "ok":
        raise RuntimeError(js.get("message", "Twelve Data error"))
    df = pd.DataFrame(js["values"])
    df.index = pd.to_datetime(df["datetime"]).dt.tz_localize(ET)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return df[(df.index.time >= pd.Timestamp("09:30").time()) & (df.index.time < pd.Timestamp("16:00").time())]

def rows(g):
    return [[t.strftime("%Y-%m-%d %H:%M"), round(float(r.Open), 4), round(float(r.High), 4), round(float(r.Low), 4),
             round(float(r.Close), 4), int(r.Volume)] for t, r in g.iterrows() if pd.notna(r.Close)]

report = {}
for i, s in enumerate(SYMS):
    src, h = None, None
    if KEY:
        try:
            if i: time.sleep(9)  # free plan: 8 requests a minute
            h = rows(to_hours(td30(s))); src = "td30"
        except Exception as e:
            report[s + "_td_error"] = str(e)[:200]
    if not h:
        d = yf.download(s, period="730d", interval="1h", auto_adjust=False, prepost=False, progress=False)
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        d.index = d.index.tz_convert(ET)
        d = d[(d.index.time >= pd.Timestamp("09:30").time()) & (d.index.time < pd.Timestamp("16:00").time())]
        lab = (d.index + pd.Timedelta(hours=1)).map(lambda t: min(t, t.normalize() + pd.Timedelta(hours=16)))
        d.index = lab; h = rows(d); src = "yf1h"
    dd = yf.download(s, period="5y", interval="1d", auto_adjust=False, progress=False)
    if isinstance(dd.columns, pd.MultiIndex): dd.columns = dd.columns.get_level_values(0)
    daily = [[t.strftime("%Y-%m-%d"), round(float(r.Open), 4), round(float(r.High), 4), round(float(r.Low), 4), round(float(r.Close), 4), int(r.Volume)]
             for t, r in dd.iterrows() if pd.notna(r.Close)]
    json.dump({"sym": s, "src": src, "h1": h, "d": daily}, open(f"research/data/{s}.json", "w"), separators=(",", ":"))
    report[s] = f"{src} {len(h)} bars {h[0][0] if h else ''} -> {h[-1][0] if h else ''}"
    print(s, report[s], flush=True)
json.dump(report, open("research/data/_report.json", "w"), indent=1)
