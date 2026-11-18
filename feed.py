import json, datetime as dt
import yfinance as yf

SYMS = "AAPL NFLX NVDA SPY AMD AMZN AVGO BAC CVX GLD GOOG INTC JPM META MSFT MU OXY QQQ SLV TSLA USO XOM".split()

df = yf.download(SYMS, period="10d", interval="1h", group_by="ticker",
                 auto_adjust=False, prepost=False, progress=False)
out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
       "interval": "1h", "tz": "America/New_York", "bars": {}}
for s in SYMS:
    d = df[s].dropna()
    d.index = d.index.tz_convert("America/New_York")
    out["bars"][s] = [[t.strftime("%Y-%m-%d %H:%M"), round(r.Open, 2), round(r.High, 2),
                       round(r.Low, 2), round(r.Close, 2), int(r.Volume)] for t, r in d.iterrows()]
json.dump(out, open("data/h1.json", "w"), separators=(",", ":"))
