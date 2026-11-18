# Structure One feed.
#   data/h1.json          latest quotes + recent candles (read every hour by the website sync)
#   data/chart/<SYM>.json chart history per symbol: 1-hour (C1 = 10:00 = 9:30-10:00 ... C7 = 16:00),
#                         daily and monthly candles, with enough extra history for MA200
#   data/hist/<SYM>.json  the growing store of 1-hour candles (Yahoo only serves 60 days of 30-minute data,
#                         so the store keeps everything already collected; Twelve Data back-fills 12 months
#                         when the TWELVEDATA_API_KEY secret is set)
import json
import os
import time
import urllib.parse
import urllib.request

import pandas as pd
import yfinance as yf

SYMS = "AAPL NFLX NVDA SPY AMD AMZN AVGO BAC CVX GLD GOOG INTC JPM META MSFT MU OXY QQQ SLV TSLA USO XOM".split()
ET = "America/New_York"
now = pd.Timestamp.now(tz=ET)
today = now.strftime("%Y-%m-%d")
TD_KEY = os.environ.get("TWELVEDATA_API_KEY", "").strip()
H1_KEEP = 1764 + 200      # about 12 months of 1-hour candles plus MA200 warm-up
D_KEEP = 252 + 200        # 12 months of sessions plus MA200 warm-up
M_KEEP = 260              # monthly candles (MA200 needs 200 months)
os.makedirs("data/chart", exist_ok=True)
os.makedirs("data/hist", exist_ok=True)


def one(df, s):
    d = df[s] if isinstance(df.columns, pd.MultiIndex) else df
    d = d.dropna(subset=["Close"]).copy()
    d["Volume"] = d["Volume"].fillna(0)
    return d


def row(label, r):
    return [label, round(float(r.Open), 2), round(float(r.High), 2), round(float(r.Low), 2),
            round(float(r.Close), 2), int(r.Volume)]


def fresh(s, kind):
    """Yahoo sometimes drops one symbol from a batch; fetch it alone once more."""
    if kind == "m30":
        return yf.download(s, period="60d", interval="30m", group_by="ticker", auto_adjust=False,
                           prepost=False, progress=False)
    return yf.download(s, period="max", interval="1d", group_by="ticker", auto_adjust=False, progress=False)


def get(df, s, kind):
    try:
        d = one(df, s)
    except Exception:
        d = pd.DataFrame()
    if d.empty:
        d = one(fresh(s, kind), s)
    return d


def to_hours(d):
    """30-minute bars (tz-aware, start-stamped) -> S1 hourly candles keyed by close time."""
    close_at = (d.index + pd.Timedelta(minutes=30)).ceil("h")
    return d.groupby(close_at).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
                                   Close=("Close", "last"), Volume=("Volume", "sum"))


def twelvedata_30m(s):
    """About 12 months of 30-minute bars from Twelve Data (one request, regular hours, ET)."""
    q = urllib.parse.urlencode({"symbol": s, "interval": "30min", "outputsize": 5000,
                                "timezone": ET, "order": "ASC", "apikey": TD_KEY})
    with urllib.request.urlopen("https://api.twelvedata.com/time_series?" + q, timeout=60) as r:
        js = json.load(r)
    if js.get("status") != "ok":
        raise RuntimeError(js.get("message", "Twelve Data error"))
    df = pd.DataFrame(js["values"])
    df.index = pd.to_datetime(df["datetime"]).dt.tz_localize(ET)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df = df[(df.index.time >= pd.Timestamp("09:30").time()) & (df.index.time < pd.Timestamp("16:00").time())]
    return df


m30 = yf.download(SYMS, period="60d", interval="30m", group_by="ticker",
                  auto_adjust=False, prepost=False, progress=False, threads=True)
day = yf.download(SYMS, period="max", interval="1d", group_by="ticker",
                  auto_adjust=False, progress=False, threads=True)

out = {"generated": now.tz_convert("UTC").isoformat(timespec="seconds"), "tz": ET,
       "note": "h1 = completed 1-hour candles labelled by CLOSE time (10:00 = C1 ... 16:00 = C7); "
               "forming = the hour still in progress; daily = completed sessions (last 260); "
               "monthly = month candles built from completed sessions, labelled YYYY-MM (the last one is the month in progress); "
               "quote = latest 30-minute price; full chart history per symbol is in data/chart/<SYM>.json",
       "h1": {}, "forming": {}, "daily": {}, "monthly": {}, "quote": {}}
td_used = 0
for s in SYMS:
    try:
        d = get(m30, s, "m30")
        d.index = d.index.tz_convert(ET)
        g = to_hours(d)
        rows = [(t, row(t.strftime("%Y-%m-%d %H:%M"), r)) for t, r in g.iterrows()]
        recent = [x for t, x in rows if t <= now]
        if rows and rows[-1][0] > now:
            out["forming"][s] = rows[-1][1]

        # grow the 1-hour store: older candles stay, the latest 60 days come from Yahoo
        hp = f"data/hist/{s}.json"
        hist = json.load(open(hp)) if os.path.exists(hp) else {"h1": [], "backfilled": False}
        keep = {x[0]: x for x in hist["h1"]}
        if TD_KEY and not hist.get("backfilled"):
            try:
                if td_used:
                    time.sleep(9)  # free plan: 8 requests a minute
                td_used += 1
                tg = to_hours(twelvedata_30m(s))
                for t, r in tg.iterrows():
                    if t <= now:
                        keep[t.strftime("%Y-%m-%d %H:%M")] = row(t.strftime("%Y-%m-%d %H:%M"), r)
                hist["backfilled"] = True
            except Exception as e:
                out.setdefault("td_errors", {})[s] = str(e)[:200]
        for x in recent:
            keep[x[0]] = x
        hist["h1"] = [keep[k] for k in sorted(keep)][-H1_KEEP:]
        json.dump(hist, open(hp, "w"), separators=(",", ":"))
        out["h1"][s] = recent

        dd = get(day, s, "d")
        dd.index = pd.to_datetime(dd.index).strftime("%Y-%m-%d")
        done_day = [row(i, r) for i, r in dd.iterrows()
                    if i < today or (i == today and now.hour * 60 + now.minute >= 16 * 60 + 15)]
        out["daily"][s] = done_day[-260:]
        months = []
        if done_day:
            md = pd.DataFrame(done_day, columns=["d", "Open", "High", "Low", "Close", "Volume"])
            md.index = pd.to_datetime(md["d"])
            mo = md.resample("MS").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last",
                                        "Volume": "sum"}).dropna()
            months = [row(t.strftime("%Y-%m"), r) for t, r in mo.iterrows()]
        out["monthly"][s] = months[-121:]

        json.dump({"sym": s, "generated": out["generated"], "h1": hist["h1"], "d": done_day[-D_KEEP:],
                   "m": months[-M_KEEP:]}, open(f"data/chart/{s}.json", "w"), separators=(",", ":"))

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
print("ok", len(out["h1"]), "symbols", out.get("errors", ""), out.get("td_errors", ""))
