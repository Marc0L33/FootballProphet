#!/usr/bin/env python3
"""
Prophet v1.0.0 — Football Match Prediction Engine
================================================
Core calculation engine implementing the prophet methodology.

Formula:
  GF_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)

Architecture:
  1. Load rules from data/rules.json
  2. Load team data from data/teams.json
  3. Accept match input as JSON
  4. Apply rules in priority order
  5. Output two scores: methodology + market_adjusted

Usage:
  python predictor.py --input match_input.json
  python predictor.py --input match_input.json --output result.json
"""

import json
import argparse
import sys
import os
from typing import Dict, List, Tuple, Optional, Any

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RULES_PATH = os.path.join(DATA_DIR, "rules.json")
TEAMS_PATH = os.path.join(DATA_DIR, "teams.json")


class ProphetEngine:
    """Core prediction engine implementing the prophet methodology."""

    def __init__(self):
        self.rules = self._load_rules()
        self.teams = self._load_teams()
        self.priority_chain = self._build_priority_chain()

    def _load_rules(self) -> Dict:
        with open(RULES_PATH) as f:
            data = json.load(f)
        return {r["id"]: r for r in data["rules"]}

    def _load_teams(self) -> Dict:
        with open(TEAMS_PATH) as f:
            data = json.load(f)
        return data["teams"]

    def _build_priority_chain(self) -> List[str]:
        """Build sorted list of active rule IDs by priority."""
        active = [(r["priority"], r["id"]) for r in self.rules.values()
                  if r["status"] == "active"]
        active.sort()
        return [r[1] for r in active]

    # ─── ② Opponent Quality Coefficient ───────────────────────────
    def opponent_coefficient(self, opponent_ga_per_game: float) -> float:
        """Map opponent GA/game to multiplier coefficient (Rule 2)."""
        thresholds = [(0.30, 0.60), (0.50, 0.70), (0.70, 0.80),
                      (0.90, 0.90), (1.10, 1.00), (1.30, 1.10),
                      (1.50, 1.20), (1.80, 1.30), (float('inf'), 1.40)]
        for threshold, coeff in thresholds:
            if opponent_ga_per_game <= threshold:
                return coeff
        return 1.40

    # ─── ⑭ Qualifying Baseline Blend ─────────────────────────────
    def blend_gf_ga(self, team_name: str, tournament_matches: List[Dict]) -> Tuple[float, float]:
        """Blend qualifying data with tournament data (Rule 14)."""
        team = self.teams.get(team_name, {"gf": 1.0, "ga": 1.0})
        q_gf, q_ga = team["gf"], team["ga"]

        n = len(tournament_matches)
        if n == 0:
            return q_gf, q_ga
        elif n == 1:
            w_q, w_t = 0.85, 0.15
        else:  # n >= 2
            w_q, w_t = 0.70, 0.30

        t_gf = sum(m["gf"] for m in tournament_matches) / n
        t_ga = sum(m["ga"] for m in tournament_matches) / n

        gf = w_q * q_gf + w_t * t_gf
        ga = w_q * q_ga + w_t * t_ga
        return gf, ga

    # ─── Rule Application ────────────────────────────────────────
    def _get_team_context(self, side: Dict, team_name: str,
                          opp_ga: float, tournament_matches: List[Dict]) -> Dict:
        """Build context dict for a single team's rule evaluation."""
        baseline_gf, baseline_ga = self.blend_gf_ga(team_name, tournament_matches)
        opp_coeff = self.opponent_coefficient(opp_ga)
        team_data = self.teams.get(team_name, {})

        return {
            "team_name": team_name,
            "baseline_gf": baseline_gf,
            "baseline_ga": baseline_ga,
            "opponent_coefficient": opp_coeff,
            "goals": baseline_gf * opp_coeff,  # starting point
            "capped": False,
            "cap_value": None,
            "is_host": team_data.get("is_host", False),
            "diaspora_population": team_data.get("diaspora_us", 0),
            "confederation": team_data.get("conf", "UEFA"),
            "locked_group_winner": side.get("locked_group_winner", False),
            "already_qualified": side.get("already_qualified", False),
            "rotation_count": side.get("rotation_count", 0),
            "key_player_missing": side.get("key_player_missing", []),
            "previous_red_card": side.get("previous_red_card", False),
            "defense_is_elite": side.get("defense_is_elite", False),
            "attacking_tier": side.get("attacking_tier", 3),
            "consecutive_zero_openplay": side.get("consecutive_zero_openplay", 0),
            "cumulative_xg": side.get("cumulative_xg", 0),
            "xg_per_shot": side.get("xg_per_shot", 0.10),
            "actual_goals": side.get("actual_goals", 0),
            "system_maturity": side.get("system_maturity", False),
            "triggered_rules": [],
            "rule_details": []
        }

    def _apply_rule(self, rule_id: str, rule: Dict,
                    h_ctx: Dict, a_ctx: Dict, match: Dict) -> Tuple[Dict, Dict]:
        """Apply a single rule to both team contexts. Returns updated contexts."""

        def _apply_team(ctx, is_home):
            if rule_id == "r02_opponent_quality":
                # Base multiplier already applied in context init
                pass

            elif rule_id == "r03_home_advantage":
                if ctx["is_host"]:
                    bonus = rule["delta"]["host"] * rule["gamma"]
                    ctx["goals"] += bonus
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r03 host +{bonus:.2f}")
                elif ctx["diaspora_population"] >= 500000 and match.get("attendance_tilt") == "significant":
                    bonus = rule["delta"]["diaspora_pseudo_home"] * rule["gamma"]
                    ctx["goals"] += bonus
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r03 diaspora +{bonus:.2f}")

            elif rule_id == "r01_no_clean_sheet":
                if (ctx["goals"] > 0 and ctx["goals"] < 1.5
                    and ctx["opponent_coefficient"] < 0.80):
                    # Check r08 override
                    if "r08_elite_defense" not in ctx["triggered_rules"]:
                        bonus = rule["delta"] * rule["gamma"]
                        ctx["goals"] += bonus
                        ctx["triggered_rules"].append(rule_id)
                        ctx["rule_details"].append(f"r01 +{bonus:.2f}")

            elif rule_id == "r05_offensive_incapability":
                # Check exemption first
                if (ctx["cumulative_xg"] > 2.0 and ctx["actual_goals"] == 0):
                    pass  # variance regression exemption
                elif (ctx["xg_per_shot"] < 0.05
                      or ctx["consecutive_zero_openplay"] >= 2):
                    if ctx["goals"] > 1:
                        ctx["goals"] = 1
                        ctx["capped"] = True
                        ctx["cap_value"] = 1
                        ctx["triggered_rules"].append(rule_id)
                        ctx["rule_details"].append(f"r05 cap→1 goal")

            elif rule_id == "r16_morale_decay":
                # Type A
                if ctx["locked_group_winner"] and not ctx["is_host"]:
                    penalty = rule["delta"]["type_a"] * rule["gamma"]
                    ctx["goals"] += penalty
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r16A morale -{abs(penalty):.2f}")
                # Type B
                elif ctx["rotation_count"] >= 5 and ctx["already_qualified"]:
                    penalty = rule["delta"]["type_b"] * rule["gamma"]
                    ctx["goals"] += penalty
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r16B rotation -{abs(penalty):.2f}")

            elif rule_id == "r07_creativity_absence":
                if ctx["key_player_missing"]:
                    tier_deltas = []
                    for player in ctx["key_player_missing"]:
                        tier = player.get("tier", "main_striker")
                        delta = rule["effect_tiers"].get(tier, -0.5)
                        tier_deltas.append(delta)
                    # Take the most impactful absence + 50% of others
                    if tier_deltas:
                        total = max(tier_deltas) + 0.5 * sum(sorted(tier_deltas)[:-1])
                        impact = total * rule["gamma"]
                        ctx["goals"] += impact
                        ctx["triggered_rules"].append(rule_id)
                        ctx["rule_details"].append(f"r07 absence {impact:.2f}")

            elif rule_id == "r17_cross_conf":
                if ctx["confederation"] in ["AFC", "CONCACAF"] and ctx["system_maturity"]:
                    ctx["goals"] *= rule["delta"]
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r17 cross-conf ×{rule['delta']:.2f}")

            elif rule_id == "r08_elite_defense":
                if ctx["defense_is_elite"]:
                    opp_tier = is_home and a_ctx["attacking_tier"] or h_ctx["attacking_tier"]
                    my_tier = ctx["attacking_tier"]
                    if opp_tier <= my_tier - 2:
                        # This rule affects the opponent's goals
                        if is_home:
                            impact = rule["delta"] * rule["gamma"]
                            a_ctx["goals"] += impact
                            a_ctx["triggered_rules"].append(rule_id)
                            a_ctx["rule_details"].append(f"r08 elite_def -{abs(impact):.2f}")
                        else:
                            impact = rule["delta"] * rule["gamma"]
                            h_ctx["goals"] += impact
                            h_ctx["triggered_rules"].append(rule_id)
                            h_ctx["rule_details"].append(f"r08 elite_def -{abs(impact):.2f}")

            elif rule_id == "r10_early_goal":
                if match.get("early_goal_likely"):
                    bonus = rule["delta"] * rule["gamma"]
                    ctx["goals"] += bonus
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r10 early_goal +{bonus:.2f}")

            elif rule_id == "r12_tactical_matchup":
                if match.get("tactical_matchup"):
                    tm = match["tactical_matchup"]
                    side_key = "home" if is_home else "away"
                    tier = tm.get(f"{side_key}_advantage", "even")
                    delta = rule["effect_tiers"].get(tier, 0)
                    if delta != 0:
                        impact = delta * rule["gamma"]
                        ctx["goals"] += impact
                        ctx["triggered_rules"].append(rule_id)
                        ctx["rule_details"].append(f"r12 tactical {tier} {impact:+.2f}")

            elif rule_id == "r19_draw_collusion":
                if match.get("draw_both_advance"):
                    impact = rule["delta"] * rule["gamma"]
                    ctx["goals"] -= abs(impact) / 2  # half for each team
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r19 collusion -{abs(impact)/2:.2f}")

            elif rule_id == "r15_indoor":
                if match.get("venue_is_indoor") or match.get("venue_is_climate_controlled"):
                    bonus = rule["delta"] * rule["gamma"]
                    ctx["goals"] += bonus
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r15 indoor +{bonus:.2f}")

            elif rule_id == "r18_water_break":
                if match.get("has_mandatory_water_break"):
                    defense_bonus = rule["delta"]["momentum_interruption"] * rule["gamma"]
                    late_bonus = rule["delta"]["late_goals"] * rule["gamma"]
                    ctx["goals"] += late_bonus  # late goals apply to both
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r18 water_break +late {late_bonus:.2f}")

            elif rule_id == "r13_extreme_weather":
                if match.get("suspension_minutes", 0) > 30:
                    ctx["goals"] *= 0.5
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append("r13 weather ×0.5")

            return ctx

        h_ctx = _apply_team(h_ctx, is_home=True)
        a_ctx = _apply_team(a_ctx, is_home=False)
        return h_ctx, a_ctx

    # ─── Main Prediction ─────────────────────────────────────────
    def predict(self, match_input: Dict) -> Dict:
        """
        Run full prediction for a match.

        match_input format:
        {
            "home_team": "Spain",
            "away_team": "Uruguay",
            "home": { <team context> },
            "away": { <team context> },
            "match": { <match context> },
            "market": { <market signals, optional> }
        }
        """
        home_team = match_input["home_team"]
        away_team = match_input["away_team"]
        home_side = match_input.get("home", {})
        away_side = match_input.get("away", {})
        match_ctx = match_input.get("match", {})
        market = match_input.get("market", {})

        # Get tournament match history for ⑭ blend
        home_tournament = home_side.get("tournament_matches", [])
        away_tournament = away_side.get("tournament_matches", [])

        # Initial context
        h_ctx = self._get_team_context(home_side, home_team,
                                        self.blend_gf_ga(away_team, away_tournament)[1],
                                        home_tournament)
        a_ctx = self._get_team_context(away_side, away_team,
                                        self.blend_gf_ga(home_team, home_tournament)[1],
                                        away_tournament)

        # Apply rules in priority order
        for rule_id in self.priority_chain:
            rule = self.rules[rule_id]
            h_ctx, a_ctx = self._apply_rule(rule_id, rule, h_ctx, a_ctx, match_ctx)

        # Round to get methodology scores
        methodology_home = max(0, round(h_ctx["goals"]))
        methodology_away = max(0, round(a_ctx["goals"]))

        # Market-adjusted score (if market signals provided)
        market_home = methodology_home
        market_away = methodology_away
        market_adjustments = []

        if market:
            mh, ma, adjustments = self._apply_market_signals(
                methodology_home, methodology_away,
                h_ctx, a_ctx, market, match_ctx
            )
            market_home, market_away = mh, ma
            market_adjustments = adjustments

        # Build output
        methodology_direction = ("home" if methodology_home > methodology_away
                                else ("away" if methodology_home < methodology_away else "draw"))
        market_direction = ("home" if market_home > market_away
                           else ("away" if market_home < market_away else "draw"))

        return {
            "match": f"{home_team} vs {away_team}",
            "methodology_score": {
                "home": methodology_home,
                "away": methodology_away,
                "direction": methodology_direction,
                "total": methodology_home + methodology_away
            },
            "market_adjusted_score": {
                "home": market_home,
                "away": market_away,
                "direction": market_direction,
                "total": market_home + market_away
            },
            "confidence": self._calculate_confidence(h_ctx, a_ctx),
            "rule_application": {
                "home": {
                    "baseline_gf": round(h_ctx["baseline_gf"], 2),
                    "opponent_coefficient": h_ctx["opponent_coefficient"],
                    "triggered_rules": h_ctx["triggered_rules"],
                    "rule_details": h_ctx["rule_details"],
                    "capped": h_ctx["capped"]
                },
                "away": {
                    "baseline_gf": round(a_ctx["baseline_gf"], 2),
                    "opponent_coefficient": a_ctx["opponent_coefficient"],
                    "triggered_rules": a_ctx["triggered_rules"],
                    "rule_details": a_ctx["rule_details"],
                    "capped": a_ctx["capped"]
                }
            },
            "market_signals": market,
            "market_adjustments": market_adjustments
        }

    def _apply_market_signals(self, mh: int, ma: int,
                               h_ctx: Dict, a_ctx: Dict,
                               market: Dict, match_ctx: Dict) -> Tuple[int, int, List[str]]:
        """
        Apply qualitative market signal adjustments.
        These are heuristics - Claude should explain them in natural language.
        """
        adjustments = []
        adj_h, adj_ma = mh, ma

        # Signal 1: Draw collusion (⑲) - market often prices this
        if match_ctx.get("draw_both_advance"):
            adj_h = max(0, adj_h - 1)
            adj_ma = max(0, adj_ma - 1)
            adjustments.append("r19: draw collusion -1 global")

        # Signal 2: Large rotation (⑯B) - market reacts before we do
        h_rot = h_ctx.get("rotation_count", 0)
        a_rot = a_ctx.get("rotation_count", 0)
        if h_rot >= 5:
            adj_h = max(0, adj_h - 1)
            adjustments.append(f"r16B: home rotation {h_rot} → -1")
        if a_rot >= 5:
            adj_ma = max(0, adj_ma - 1)
            adjustments.append(f"r16B: away rotation {a_rot} → -1")

        # Signal 3: Market-derived signals (passed from Claude's analysis)
        market_signals = market.get("signals", [])
        for sig in market_signals:
            if sig.get("type") == "adjust_home":
                adj_h = max(0, adj_h + sig.get("delta", 0))
                adjustments.append(f"market: {sig.get('reason')}")
            elif sig.get("type") == "adjust_away":
                adj_ma = max(0, adj_ma + sig.get("delta", 0))
                adjustments.append(f"market: {sig.get('reason')}")
            elif sig.get("type") == "adjust_total":
                delta = sig.get("delta", 0)
                half = delta / 2
                adj_h = int(max(0, adj_h + half))
                adj_ma = int(max(0, adj_ma + half))
                adjustments.append(f"market: {sig.get('reason')}")

        return adj_h, adj_ma, adjustments

    def _calculate_confidence(self, h_ctx: Dict, a_ctx: Dict) -> Dict:
        """3D confidence module."""
        # Dimension A: Rule credibility bars
        all_triggers = set(h_ctx["triggered_rules"] + a_ctx["triggered_rules"])
        rule_credits = []
        for rid in all_triggers:
            rule = self.rules[rid]
            bar_length = int(rule["gamma"] * 10)
            n = rule.get("n", 0)
            level = "high" if rule["gamma"] > 0.75 else ("medium" if rule["gamma"] > 0.60 else "low")
            rule_credits.append({
                "rule_id": rid,
                "name": rule["name"],
                "gamma": rule["gamma"],
                "bar": "█" * bar_length + "░" * (10 - bar_length),
                "level": level,
                "n": n
            })

        # Dimension B: Conflict detection
        h_direction_positive = len([d for d in h_ctx["rule_details"] if "+" in d])
        h_direction_negative = len([d for d in h_ctx["rule_details"] if "-" in d])
        a_direction_positive = len([d for d in a_ctx["rule_details"] if "+" in d])
        a_direction_negative = len([d for d in a_ctx["rule_details"] if "-" in d])

        net_h = h_direction_positive - h_direction_negative
        net_a = a_direction_positive - a_direction_negative

        # Dimension C: Prediction interval
        # Simplified: variance from triggered rules' sigma
        total_sigma = sum(
            self.rules[rid]["sigma"]
            for rid in all_triggers
            if self.rules[rid].get("sigma")
        )

        # Composite confidence rating
        core_rules_gamma = min(
            self.rules[rid]["gamma"]
            for rid in ["r14_qualifying_baseline", "r12_tactical_matchup"]
            if rid in all_triggers
        ) if any(rid in all_triggers for rid in ["r14_qualifying_baseline", "r12_tactical_matchup"]) else 0.5

        interval_width = total_sigma * 3  # rough 80% interval
        net = net_h + net_a

        if net >= 2 and core_rules_gamma > 0.75 and interval_width < 2.0:
            rating = "⭐⭐⭐⭐ high"
        elif net >= 0 and (core_rules_gamma > 0.60 or interval_width < 3.0):
            rating = "⭐⭐⭐ medium"
        else:
            rating = "⭐⭐ low"

        return {
            "rating": rating,
            "dimension_a_rule_credibility": rule_credits,
            "dimension_b_conflict": {
                "home_net_effect": net_h,
                "away_net_effect": net_a,
                "total_net": net,
                "conflict_level": "none" if net >= 2 else ("slight" if net >= 0 else "significant")
            },
            "dimension_c_interval": {
                "width": round(interval_width, 2),
                "level": "narrow" if interval_width < 2.0 else ("medium" if interval_width < 3.0 else "wide")
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Prophet v1.0.0 Prediction Engine")
    parser.add_argument("--input", "-i", required=True, help="Match input JSON file")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON only")

    args = parser.parse_args()

    with open(args.input) as f:
        match_input = json.load(f)

    engine = ProphetEngine()
    result = engine.predict(match_input)

    json_output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(json_output)
        print(f"Prediction saved to {args.output}")
    else:
        if args.json:
            print(json_output)
        else:
            # Human-readable output
            print(f"\n{'='*60}")
            print(f"Prophet v1.0.0 — {result['match']}")
            print(f"{'='*60}")
            print(f"\n   Methodology Score:  {result['methodology_score']['home']} - {result['methodology_score']['away']} ({result['methodology_score']['direction']})")
            print(f"   Market-Adjusted:    {result['market_adjusted_score']['home']} - {result['market_adjusted_score']['away']} ({result['market_adjusted_score']['direction']})")
            print(f"   Confidence:         {result['confidence']['rating']}")
            print(f"\n   Rules triggered:")
            for side, label in [("home", "Home"), ("away", "Away")]:
                rules = result["rule_application"][side]["triggered_rules"]
                if rules:
                    print(f"     {label}: {', '.join(rules)}")
            if result["market_adjustments"]:
                print(f"\n   Market adjustments:")
                for adj in result["market_adjustments"]:
                    print(f"     - {adj}")
            print()


if __name__ == "__main__":
    main()
