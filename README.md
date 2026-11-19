# structure-one-feed
## Options calibration

`calibration/params.json` holds the hand-edited settings the site uses to pick a strike from an uploaded 7–21 DTE chain (delta band and target, spread and open-interest limits, theta cap, stop %, scoring weights, per-symbol overrides). `calib.py` runs after every hourly feed: it adds measured HV20, HV60 and ATR% from the daily bars plus the 13-week T-bill rate (^IRX) for the Greeks, writes `data/calibration.json`, and puts a `cal` block in each `data/chart/SYM.json`. Edit `params.json`, commit, and the next run carries it to the site.
