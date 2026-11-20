#!/usr/bin/env bash
# Today's save times (New York time), in order. The session loop re-reads this file
# before every wait, so a change pushed here takes effect within a minute, mid-day.
# :01 = full hourly feed (C1 at 10:01 ... C7 at 16:01); every other minute = forming candle only.
t=""
for m in $(seq 31 59); do t="$t 09:$m"; done
for h in 10 11 12 13 14 15; do
  for m in $(seq -w 1 59); do t="$t $h:$m"; done
done
echo $t 16:01 16:20
