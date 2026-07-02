#!/usr/bin/env python3
"""Fetch live odds from Odds-API.io via proxy and update match JSONs.

Usage:
    python3 engine/fetch_odds.py --match PATH
    python3 engine/fetch_odds.py --all
    python3 engine/fetch_odds.py --all --dry-run
"""
import json, ssl, os, argparse, urllib.request

API_KEY = "29785a1210e6c8f09cdc3800de024f8db1dda5892e4d6b77c35bff659039f4db"
BASE = "https://api.odds-api.io/v3"
BOOKMAKER = "Bet365"
PROXY = "http://127.0.0.1:7897"

def _get(url):
    ctx = ssl._create_unverified_context()
    ph = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
    opener = urllib.request.build_opener(ph, urllib.request.HTTPSHandler(context=ctx))
    with opener.open(url) as r:
        return json.loads(r.read())

def find_event(home, away, date="2026-07-01"):
    events = _get(f"{BASE}/events?apiKey={API_KEY}&sport=football&date={date}")
    hl, al = home.lower(), away.lower()
    for e in events:
        eh, ea = e["home"].lower(), e["away"].lower()
        # Fuzzy match: "DR Congo" vs "Congo DR", "Bosnia" vs "Bosnia and Herzegovina"
        if (hl in eh or eh in hl or any(w in eh for w in hl.split())) and \
           (al in ea or ea in al or any(w in ea for w in al.split())):
            return e
    return None

def get_odds(event_id):
    data = _get(f"{BASE}/odds/multi?apiKey={API_KEY}&eventIds={event_id}&bookmakers={BOOKMAKER}")
    return data[0] if data else None

def update(path, dry=False):
    with open(path) as f:
        m = json.load(f)
    home, away = m["home_team"], m["away_team"]
    print(f"  {home} vs {away} ...", end=" ")

    evt = find_event(home, away)
    if not evt:
        print("NOT FOUND")
        return
    odds = get_odds(evt["id"])
    if not odds:
        print("NO ODDS")
        return

    bm = odds.get("bookmakers", {}).get(BOOKMAKER, [])
    ml_v = spread_v = totals_v = None
    for mkt in bm:
        o = mkt["odds"][0] if mkt["odds"] else {}
        if mkt["name"] == "ML":
            ml_v = {"home": float(o["home"]), "draw": float(o["draw"]), "away": float(o["away"])}
        elif mkt["name"] == "Spread":
            spread_v = f"hdp={o.get('hdp','?')} H{o.get('home','?')} A{o.get('away','?')}"
        elif mkt["name"] == "Totals":
            totals_v = f"hdp={o.get('hdp','?')} O{o.get('over','?')} U{o.get('under','?')}"

    if ml_v:
        m["market"]["moneyline"] = ml_v
    if spread_v:
        old = m["market"].get("handicap", "").split("(")[0].strip()
        m["market"]["handicap"] = f"{old} ({BOOKMAKER} {spread_v})"
    if totals_v:
        m["market"]["totals"] = totals_v

    if not dry:
        with open(path, "w") as f:
            json.dump(m, f, indent=2, ensure_ascii=False)

    print(f"ML={ml_v} | spread={spread_v} | totals={totals_v}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--match")
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.match:
        update(a.match, a.dry_run)
    elif a.all:
        d = os.path.join(os.path.dirname(__file__), "..", "output", "predictions")
        for f in sorted(os.listdir(d)):
            if f.startswith("r32_") and f.endswith(".json"):
                update(os.path.join(d, f), a.dry_run)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
