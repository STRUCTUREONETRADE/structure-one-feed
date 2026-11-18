# Structure One hourly feed: 1-hour candles labelled by their CLOSE time
# (C1 = 10:00 = 9:30-10:00 ... C7 = 16:00), daily candles, and a latest quote per symbol.
import json
import pandas as pd
import yfinance as yf

SYMS = "AAPL NFLX NVDA SPY AMD AMZN AVGO BAC CVX GLD GOOG INTC JPM META MSFT MU OXY QQQ SLV TSLA USO XOM".split()
ET = "America/New_York"
now = pd.Timestamp.now(tz=ET)


def one(df, s):
    d = df[s] if isinstance(df.columns, pd.MultiIndex) else df
    d = d.dropna(subset=["Close"]).copy()
    d["Volume"] = d["Volume"].fillna(0)
    return d


def row(label, r):
    return [label, round(float(r.Open), 2), round(float(r.High), 2), round(float(r.Low), 2),
            round(float(r.Close), 2), int(r.Volume)]


m30 = yf.download(SYMS, period="30d", interval="30m", group_by="ticker",
                  auto_adjust=False, prepost=False, progress=False, threads=True)
day = yf.download(SYMS, period="9mo", interval="1d", group_by="ticker",
                  auto_adjust=False, progress=False, threads=True)

out = {"generated": now.tz_convert("UTC").isoformat(timespec="seconds"), "tz": ET,
       "note": "h1 = completed 1-hour candles labelled by CLOSE time (10:00 = C1 ... 16:00 = C7); "
               "forming = the hour still in progress; daily = completed sessions; quote = latest 30-minute price",
       "h1": {}, "forming": {}, "daily": {}, "quote": {}}
today = now.strftime("%Y-%m-%d")
for s in SYMS:
    try:
        d = one(m30, s)
        d.index = d.index.tz_convert(ET)
        close_at = (d.index + pd.Timedelta(minutes=30)).ceil("h")
        g = d.groupby(close_at).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
                                    Close=("Close", "last"), Volume=("Volume", "sum"))
        rows = [(t, row(t.strftime("%Y-%m-%d %H:%M"), r)) for t, r in g.iterrows()]
        out["h1"][s] = [x for t, x in rows if t <= now]
        if rows and rows[-1][0] > now:
            out["forming"][s] = rows[-1][1]

        dd = one(day, s)
        dd.index = pd.to_datetime(dd.index).strftime("%Y-%m-%d")
        done_day = [row(i, r) for i, r in dd.iterrows()
                    if i < today or (i == today and now.hour * 60 + now.minute >= 16 * 60 + 15)]
        out["daily"][s] = done_day

        last_t = d.index[-1]
        p = round(float(d["Close"].iloc[-1]), 2)
        qd = last_t.strftime("%Y-%m-%d")
        prev = [x for x in done_day if x[0] < qd]
        at = min(last_t + pd.Timedelta(minutes=30), now)
        q = {"p": p, "d": qd, "t": at.strftime("%H:%M")}
        if prev:
            q["prev"] = prev[-1][4]
            q["c"] = round((p / prev[-1][4] - 1) * 100, 2)
        out["quote"][s] = q
    except Exception as e:  # one bad symbol must not stop the others
        out.setdefault("errors", {})[s] = str(e)[:200]

with open("data/h1.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("ok", len(out["h1"]), "symbols", out.get("errors", ""))
