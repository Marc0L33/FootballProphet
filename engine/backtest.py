#!/usr/bin/env python3
"""
Prophet v1.0.0 — Backtesting Tool
================================
Run methodology predictions across historical matches and compute accuracy metrics.

Usage:
  python backtest.py --matches matches.jsonl
  python backtest.py --matches matches.jsonl --output results.json
"""

import json
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from predictor import ProphetEngine


def run_backtest(matches: list) -> dict:
    """Run predictions across all matches and compute metrics."""
    engine = ProphetEngine()
    results = []
    stats = {
        "total": 0, "direction_correct": 0, "exact_correct": 0,
        "by_round": {"MD1": {"total": 0, "correct": 0, "exact": 0},
                     "MD2": {"total": 0, "correct": 0, "exact": 0},
                     "MD3": {"total": 0, "correct": 0, "exact": 0}}
    }

    for m in matches:
        pred = engine.predict(m)

        ah, aa = m["actual"]["home"], m["actual"]["away"]
        ph = pred["methodology_score"]["home"]
        pa = pred["methodology_score"]["away"]

        actual_dir = "home" if ah > aa else ("away" if ah < aa else "draw")
        pred_dir = pred["methodology_score"]["direction"]
        direction_ok = actual_dir == pred_dir
        exact_ok = (ph == ah and pa == aa)

        rnd = m.get("round", "MD1")
        stats["total"] += 1
        if direction_ok: stats["direction_correct"] += 1
        if exact_ok: stats["exact_correct"] += 1
        if rnd in stats["by_round"]:
            stats["by_round"][rnd]["total"] += 1
            if direction_ok: stats["by_round"][rnd]["correct"] += 1
            if exact_ok: stats["by_round"][rnd]["exact"] += 1

        results.append({
            "match_id": m.get("match_id"),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "predicted": f"{ph}-{pa}",
            "actual": f"{ah}-{aa}",
            "direction_correct": direction_ok,
            "exact": exact_ok,
            "round": rnd
        })

    total = stats["total"]
    return {
        "results": results,
        "summary": {
            "total_matches": total,
            "direction_accuracy": f"{stats['direction_correct']}/{total} ({stats['direction_correct']/total*100:.0f}%)" if total else "N/A",
            "exact_accuracy": f"{stats['exact_correct']}/{total} ({stats['exact_correct']/total*100:.0f}%)" if total else "N/A",
            "by_round": {
                rnd: {
                    "direction": f"{s['correct']}/{s['total']} ({s['correct']/s['total']*100:.0f}%)" if s['total'] else "N/A",
                    "exact": f"{s['exact']}/{s['total']}" if s['total'] else "N/A"
                } for rnd, s in stats["by_round"].items() if s["total"] > 0
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Prophet v1.0.0 Backtest Tool")
    parser.add_argument("--matches", "-m", required=True, help="Matches JSONL/JSON file")
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    with open(args.matches) as f:
        if args.matches.endswith(".jsonl"):
            matches = [json.loads(line) for line in f if line.strip()]
        else:
            matches = json.load(f)

    result = run_backtest(matches)

    json_output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_output)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
