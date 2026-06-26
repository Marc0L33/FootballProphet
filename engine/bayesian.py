#!/usr/bin/env python3
"""
Prophet v1.0.0 — Bayesian Update Engine
======================================
Post-match rule parameter updates following the Beta-Binomial model.

Each rule's α (correct triggers) and β (wrong triggers) update based on
whether the rule's effect direction matched the actual match outcome.

Usage:
  python bayesian.py --result match_result.json --rules ../data/rules.json --output ../data/rules.json
"""

import json
import argparse
import os
import sys
from typing import Dict, List, Optional


class BayesianUpdater:
    """Updates rule parameters after each match."""

    def __init__(self, rules_path: str):
        with open(rules_path) as f:
            self.data = json.load(f)
        self.rules = {r["id"]: r for r in self.data["rules"]}

    def update(self, match_result: Dict) -> Dict:
        """
        Process a match result and update rule α/β/n parameters.

        match_result format:
        {
            "match_id": 61,
            "home_team": "Spain",
            "away_team": "Uruguay",
            "prediction": { "methodology_score": {...}, "rule_application": {...} },
            "actual": { "home": 2, "away": 0 },
            "rule_reviews": [
                {
                    "rule_id": "r12_tactical_matchup",
                    "triggered": true,
                    "direction_correct": true,
                    "effect_magnitude_deviation": -0.3,
                    "notes": "Tactical advantage correct but margin smaller than expected"
                }
            ]
        }
        """
        actual = match_result["actual"]
        actual_dir = ("home" if actual["home"] > actual["away"]
                      else ("away" if actual["home"] < actual["away"] else "draw"))

        reviews = match_result.get("rule_reviews", [])
        changes = []

        for review in reviews:
            rid = review["rule_id"]
            if rid not in self.rules:
                continue

            rule = self.rules[rid]
            triggered = review.get("triggered", False)

            if triggered:
                rule["n"] = rule.get("n", 0) + 1

                if review.get("direction_correct", False):
                    rule["alpha"] += 1
                else:
                    rule["beta"] += 1

                # Recalculate E[γ] using posterior mean
                rule["gamma"] = round(
                    rule["alpha"] / (rule["alpha"] + rule["beta"]), 2
                )

                changes.append({
                    "rule_id": rid,
                    "name": rule["name"],
                    "alpha": rule["alpha"],
                    "beta": rule["beta"],
                    "gamma_new": rule["gamma"],
                    "n": rule["n"]
                })

        # Check rule lifecycle
        lifecycle_changes = self._check_lifecycle(match_result)
        changes.extend(lifecycle_changes)

        return {
            "match_id": match_result.get("match_id"),
            "actual": actual,
            "predicted_direction": match_result["prediction"]["methodology_score"]["direction"],
            "actual_direction": actual_dir,
            "parameter_updates": changes,
            "lifecycle_changes": lifecycle_changes
        }

    def _check_lifecycle(self, match_result: Dict) -> List[Dict]:
        """Check if any rules need status changes."""
        changes = []

        for rid, rule in self.rules.items():
            ec = rule.get("exit_conditions")
            if not ec:
                continue

            min_gamma = ec.get("min_gamma", 0.45)
            max_wrong = ec.get("max_consecutive_wrong", 5)

            if rule["status"] == "shadow_admission":
                # Promotion check: n >= 3 and gamma > 0.55
                if rule.get("n", 0) >= 3 and rule["gamma"] > 0.55:
                    rule["status"] = "active"
                    changes.append({
                        "rule_id": rid,
                        "name": rule["name"],
                        "lifecycle": "shadow_admission → active",
                        "reason": f"n={rule['n']}, γ={rule['gamma']}"
                    })

            elif rule["status"] == "active":
                # Demotion check
                if rule["gamma"] < min_gamma and rule.get("n", 0) >= max_wrong:
                    rule["status"] = "shadow_demoted"
                    changes.append({
                        "rule_id": rid,
                        "name": rule["name"],
                        "lifecycle": "active → shadow_demoted",
                        "reason": f"γ={rule['gamma']} < {min_gamma}"
                    })

            elif rule["status"] == "shadow_demoted":
                # Permanent deletion check
                strike_two = ec.get("strike_two") == "permanent_delete"
                if strike_two and rule["gamma"] < min_gamma and rule.get("n", 0) >= max_wrong + 5:
                    rule["status"] = "deleted"
                    changes.append({
                        "rule_id": rid,
                        "name": rule["name"],
                        "lifecycle": "shadow_demoted → deleted (EXIT)",
                        "reason": f"γ={rule['gamma']} sustained below {min_gamma}"
                    })

        # Update the rules data
        self.data["rules"] = list(self.rules.values())
        return changes

    def save(self, output_path: str):
        """Write updated rules back to file."""
        self.data["rules"] = list(self.rules.values())
        # Update active count
        active = sum(1 for r in self.rules.values() if r["status"] == "active")
        self.data["_meta"]["active"] = active
        self.data["_meta"]["updated"] = "auto"

        with open(output_path, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Prophet v1.0.0 Bayesian Rule Updater")
    parser.add_argument("--result", "-r", required=True, help="Match result JSON")
    parser.add_argument("--rules", default=None, help="Rules JSON path")
    parser.add_argument("--output", "-o", help="Output rules JSON path")

    args = parser.parse_args()

    rules_path = args.rules or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "rules.json"
    )

    with open(args.result) as f:
        match_result = json.load(f)

    updater = BayesianUpdater(rules_path)
    changes = updater.update(match_result)

    output_path = args.output or rules_path
    updater.save(output_path)

    print(json.dumps(changes, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
