#!/usr/bin/env python3
"""Poll FIFA API for lineups. Run once or loop until found.
Usage:
  python3 engine/poll_lineups.py          # poll once
  python3 engine/poll_lineups.py --loop   # loop every 5min until all found
"""
import json, os, ssl, sys, time, urllib.request, subprocess
from datetime import datetime, timezone, timedelta

CONFIG = "data/upcoming_matches.json"
PROXY = "http://127.0.0.1:7897"
INTERVAL = 300  # 5 min
WINDOW_MIN = 90

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def api_get(url):
    ctx = ssl._create_unverified_context()
    ph = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
    op = urllib.request.build_opener(ph, urllib.request.HTTPSHandler(context=ctx))
    with op.open(url) as r:
        return json.loads(r.read())

def fifa_ids(url):
    p = url.rstrip("/").split("/")
    return p[-4], p[-3], p[-2], p[-1]

def update(input_json):
    subprocess.run([sys.executable, f"{BASE}/engine/fetch_odds.py", "--match", input_json],
                   cwd=BASE, capture_output=True)
    fname = os.path.basename(input_json).replace(".json", "_output.json")
    out = f"{BASE}/output/web/{fname}"
    subprocess.run([sys.executable, f"{BASE}/engine/predictor.py", "-i", input_json, "-o", out],
                   cwd=BASE, capture_output=True)

def check(m):
    a,b,c,d = fifa_ids(m["fifa_url"])
    data = api_get(f"https://api.fifa.com/api/v3/live/football/{a}/{b}/{c}/{d}?language=en")
    h = [p for p in data["HomeTeam"]["Players"] if p["Status"]==1]
    aw = [p for p in data["AwayTeam"]["Players"] if p["Status"]==1]
    return len(h)==11 and len(aw)==11, data

def mark_done(match_id, config_path):
    with open(config_path) as f:
        matches = json.load(f)
    remaining = [m for m in matches if m["id"] != match_id]
    with open(config_path, "w") as f:
        json.dump(remaining, f, indent=2, ensure_ascii=False)
    print(f"  Removed {match_id} from queue, {len(remaining)} remaining")

def main():
    loop = "--loop" in sys.argv
    with open(os.path.join(BASE, CONFIG)) as f:
        matches = json.load(f)

    while True:
        now = datetime.now(timezone.utc).astimezone()
        active = []
        for m in matches:
            ko = datetime.fromisoformat(m["kickoff"])
            if now >= ko:
                mark_done(m["id"], os.path.join(BASE, CONFIG))
                continue
            if ko - timedelta(minutes=WINDOW_MIN) <= now:
                active.append(m)

        if not active:
            print(f"[{now:%H:%M}] No matches in window")
            if not loop: break
            time.sleep(INTERVAL)
            continue

        all_done = True
        for m in active:
            try:
                ok, _ = check(m)
                if ok:
                    print(f"[{now:%H:%M}] ✅ {m['home']} vs {m['away']} — CONFIRMED, updating...")
                    update(os.path.join(BASE, m["input_json"]))
                    mark_done(m["id"], os.path.join(BASE, CONFIG))
                else:
                    print(f"[{now:%H:%M}] ⏳ {m['home']} vs {m['away']}")
                    all_done = False
            except Exception as e:
                print(f"[{now:%H:%M}] ❌ {m['home']} vs {m['away']}: {e}")
                all_done = False

        # Stop cron by clearing config — when file empties, exit 0 signals caller
        if not active or all_done:
            print(f"[{now:%H:%M}] All lineups collected, stopping.")
            break
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
