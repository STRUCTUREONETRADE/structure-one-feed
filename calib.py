"""Options calibration for the Structure One site.

Merges calibration/params.json (hand-edited strike-picking settings) with values
measured from the feed: HV20/HV60 (annualised close-to-close volatility of the
daily bars), ATR14 as % of price, and the 13-week T-bill yield (^IRX) used as the
risk-free rate when the site computes Greeks for an uploaded chain.

Writes data/calibration.json and adds a compact 'cal' block to every
data/chart/SYM.json (the documents the site reads). Missing values stay null;
nothing is estimated.
"""
import glob
import json
import math
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "calibration.json")


def hv(closes, n):
    if len(closes) < n + 1:
        return None
    r = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - n, len(closes)) if closes[i - 1] > 0 and closes[i] > 0]
    if len(r) < n - 1:
        return None
    m = sum(r) / len(r)
    v = sum((x - m) ** 2 for x in r) / (len(r) - 1)
    return round(math.sqrt(v) * math.sqrt(252), 4)


def atr_pct(bars, n=14):
    if len(bars) < n + 1:
        return None
    tr = []
    for i in range(len(bars) - n, len(bars)):
        h, l, pc = bars[i][2], bars[i][3], bars[i - 1][4]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    last = bars[-1][4]
    return round(sum(tr) / n / last * 100, 3) if last else None


def rate(prev):
    """13-week T-bill yield from Yahoo (^IRX, quoted in percent). Keeps the previous value if the fetch fails."""
    try:
        import yfinance as yf
        df = yf.download("^IRX", period="10d", interval="1d", progress=False, auto_adjust=False)
        s = df["Close"].dropna()
        if hasattr(s, "columns"):
            s = s.iloc[:, 0]
        if len(s):
            return {"value": round(float(s.iloc[-1]) / 100, 5), "asof": str(s.index[-1].date()), "source": "^IRX 13-week T-bill (Yahoo Finance)"}
    except Exception as e:  # network or parsing failure: keep the last good value
        print("rate fetch failed:", e)
    return prev


def main():
    params = json.load(open(os.path.join(HERE, "calibration", "params.json")))
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT))
        except Exception:
            prev = {}
    rf = rate(prev.get("rate"))
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rate": rf,
           "defaults": params["defaults"], "symbols": {}}
    for path in sorted(glob.glob(os.path.join(HERE, "data", "chart", "*.json"))):
        doc = json.load(open(path))
        sym = doc.get("sym") or os.path.basename(path)[:-5]
        d = doc.get("d") or []
        closes = [b[4] for b in d if b and b[4]]
        meas = {"asof": d[-1][0] if d else None, "last": closes[-1] if closes else None,
                "hv20": hv(closes, 20), "hv60": hv(closes, 60), "atrPct": atr_pct(d)}
        cfg = dict(params["defaults"])
        cfg.update(params["symbols"].get(sym, {}))
        cal = {"cfg": cfg, "m": meas, "rate": rf, "generated": out["generated"]}
        out["symbols"][sym] = {"overrides": params["symbols"].get(sym, {}), "measured": meas}
        doc["cal"] = cal
        with open(path, "w") as f:
            json.dump(doc, f, separators=(",", ":"))
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("calibration:", len(out["symbols"]), "symbols · rate", rf and rf.get("value"))


if __name__ == "__main__":
    main()
