# Structure One feed · intrahour snapshot (runs every 15 minutes in the session loop).
#   data/forming.json  the 1-hour candle still forming (C1 = 9:30-10:00, then full hours to 16:00),
#                      labelled by the close time it will have, and today's session so far,
#                      both built from Yahoo 1-minute bars. A forming candle is never a close.
#                      The day row carries a 7th element: today's COMPLETED 15-minute candles
#                      ([[close time, o, h, l, c, v], ...], 09:45 ... ), for the website's 15-minute timing read.
import json
import os

import pandas as pd
import yfinance as yf

SYMS = "AAPL NFLX NVDA SPY AMD AMZN AVGO BAC CVX GLD GOOG INTC JPM META MSFT MU OXY QQQ SLV TSLA USO XOM".split()
ET = "America/New_York"
now = pd.Timestamp.now(tz=ET)
today = now.strftime("%Y-%m-%d")
open_t = now.normalize() + pd.Timedelta(hours=9, minutes=30)
close_t = now.normalize() + pd.Timedelta(hours=16)
os.makedirs("data", exist_ok=True)

out = {"generated": now.tz_convert("UTC").isoformat(timespec="seconds"), "tz": ET,
       "note": "forming = the 1-hour candle in progress, labelled by its close time; day = today's session so far; "
               "built from 1-minute bars; neither is a completed close",
       "at": now.strftime("%H:%M"), "forming": {}, "day": {}}

if open_t <= now < close_t + pd.Timedelta(minutes=5):
    start = open_t if now < open_t + pd.Timedelta(minutes=30) else now.floor("h")
    if start < open_t:
        start = open_t
    end = (open_t + pd.Timedelta(minutes=30)) if start == open_t else start + pd.Timedelta(hours=1)
    label = end.strftime("%Y-%m-%d %H:%M")
    df = yf.download(SYMS, period="1d", interval="1m", group_by="ticker", auto_adjust=False,
                     prepost=False, progress=False, threads=True)
    for s in SYMS:
        try:
            d = df[s] if isinstance(df.columns, pd.MultiIndex) else df
            d = d.dropna(subset=["Close"]).copy()
            d.index = d.index.tz_convert(ET)
            d = d[(d.index >= open_t) & (d.index < close_t) & (d.index.strftime("%Y-%m-%d") == today)]
            if d.empty:
                continue
            v = d["Volume"].fillna(0)
            out["day"][s] = [today, round(float(d.Open.iloc[0]), 2), round(float(d.High.max()), 2),
                             round(float(d.Low.min()), 2), round(float(d.Close.iloc[-1]), 2), int(v.sum())]
            # today's completed 15-minute candles (a bucket counts once 2 minutes past its close, so its last minute bar is in)
            try:
                q = d.copy()
                q["Volume"] = q["Volume"].fillna(0)
                g15 = q.groupby(q.index.floor("15min")).agg(Open=("Open", "first"), High=("High", "max"),
                                                              Low=("Low", "min"), Close=("Close", "last"),
                                                              Volume=("Volume", "sum"))
                rows15 = []
                for t, r in g15.iterrows():
                    ct = t + pd.Timedelta(minutes=15)
                    if ct + pd.Timedelta(minutes=2) <= now:
                        rows15.append([ct.strftime("%Y-%m-%d %H:%M"), round(float(r.Open), 2), round(float(r.High), 2),
                                       round(float(r.Low), 2), round(float(r.Close), 2), int(r.Volume)])
                out["day"][s].append(rows15)
            except Exception as e:
                out.setdefault("m15_errors", {})[s] = str(e)[:200]
            h = d[(d.index >= start) & (d.index < end)]
            if now < end and not h.empty:
                out["forming"][s] = [label, round(float(h.Open.iloc[0]), 2), round(float(h.High.max()), 2),
                                     round(float(h.Low.min()), 2), round(float(h.Close.iloc[-1]), 2),
                                     int(h["Volume"].fillna(0).sum())]
        except Exception as e:
            out.setdefault("errors", {})[s] = str(e)[:200]

json.dump(out, open("data/forming.json", "w"), separators=(",", ":"))
print("forming", out["at"], len(out["forming"]), "symbols")
