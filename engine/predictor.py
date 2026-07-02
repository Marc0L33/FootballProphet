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
import math
from typing import Dict, List, Tuple, Optional, Any

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RULES_PATH = os.path.join(DATA_DIR, "rules.json")
TEAMS_PATH = os.path.join(DATA_DIR, "teams.json")


class GoalDistribution:
    """Negative Binomial goal distribution for a single team.

    Converts pre-round λ (expected goals) and σ (variance) into
    a probability mass function for 0~6+ goals.

    When σ² ≤ λ: falls back to Poisson (NB r→∞ limit)."""

    def __init__(self, lam: float, sigma: float):
        self.lam = max(0.01, lam)
        self.sigma = max(0.01, sigma)
        self._compute()

    def _compute(self):
        var = self.sigma ** 2
        if var > self.lam:
            # Negative Binomial: r = λ²/(σ²-λ), p = r/(r+λ)
            self.r = self.lam ** 2 / (var - self.lam)
            self.p = self.r / (self.r + self.lam)
            self._model = "negbin"
        else:
            # Poisson fallback
            self.r = float('inf')
            self.p = 0.0
            self._model = "poisson"

        # PMF for 0..5, then 6+
        self.pmf = {}
        cum = 0.0
        for k in range(6):
            if self._model == "negbin":
                prob = self._nb_pmf(k)
            else:
                prob = self._poisson_pmf(k)
            self.pmf[str(k)] = round(prob, 4)
            cum += prob
        self.pmf["6+"] = round(max(0, 1.0 - cum), 4)

        # 5% scoring floor: P(0) capped at 95%, excess → 1球 (80%) + 2球 (15%) + 3球 (5%)
        # Real football: teams that barely score, when they do, it's almost always exactly 1.
        if self.pmf["0"] > 0.95:
            self.pmf["0"] = 0.95
            self.pmf["1"] = 0.04
            self.pmf["2"] = 0.01
            self.pmf["3"] = 0.0
            self.pmf["4"] = 0.0
            self.pmf["5"] = 0.0
            self.pmf["6+"] = 0.0

        # Right-tail compression: P(6+) capped at 5%, excess redistributed to 1-5
        if self.pmf["6+"] > 0.05:
            excess = self.pmf["6+"] - 0.05
            self.pmf["6+"] = 0.05
            total_body = sum(self.pmf[str(k)] for k in range(1, 6))
            if total_body > 0:
                for k in ["1","2","3","4","5"]:
                    self.pmf[k] = round(self.pmf[k] + excess * self.pmf[k] / total_body, 4)

    def _nb_pmf(self, k: int) -> float:
        """Negative Binomial PMF with parameters r (success count), p (success prob)."""
        from math import lgamma
        r, p = self.r, self.p
        return math.exp(
            lgamma(k + r) - lgamma(k + 1) - lgamma(r)
            + r * math.log(p) + k * math.log(1 - p)
        )

    def _poisson_pmf(self, k: int) -> float:
        return math.exp(-self.lam) * (self.lam ** k) / math.factorial(k)

    def to_table(self) -> str:
        """Render as a compact text bar chart."""
        bars = []
        max_p = max(self.pmf.values())
        labels = {"0": "0球", "1": "1球", "2": "2球", "3": "3球",
                  "4": "4球", "5": "5球", "6+": "6+"}
        for k in ["0","1","2","3","4","5","6+"]:
            p = self.pmf[k]
            bar_len = int(p / max_p * 18) if max_p > 0 else 0
            bar = "█" * bar_len
            bars.append(f"  {labels[k]:<4} {bar:<18} {p*100:5.1f}%")
        return "\n".join(bars)


class JointDistribution:
    """Bivariate goal distribution with negative correlation.

    Uses a simple total-goals split model:
    1. Compute total goals distribution (home λ + away λ + covariance)
    2. Split each total by relative strength ratio ρ = λ_h / (λ_h + λ_a)
    3. This naturally produces negative correlation: when one team
       scores more, the other tends to score less."""

    def __init__(self, home_lam: float, away_lam: float,
                 home_sigma: float, away_sigma: float):
        self.h_lam = max(0.01, home_lam)
        self.a_lam = max(0.01, away_lam)
        total_lam = self.h_lam + self.a_lam
        # Pooled sigma: sqrt(σh² + σa² - 2*ρ*σh*σa) with ρ≈-0.15
        rho = -0.15
        total_var = home_sigma**2 + away_sigma**2 - 2 * rho * home_sigma * away_sigma
        total_sigma = math.sqrt(max(0.1, total_var))
        self.total_dist = GoalDistribution(total_lam, total_sigma)
        self.ratio = self.h_lam / total_lam if total_lam > 0 else 0.5

    def score_prob(self, h_goals: int, a_goals: int) -> float:
        """Probability of exact (h_goals, a_goals) using total-split model."""
        total = h_goals + a_goals
        # P(total) from total distribution
        if total < 6:
            p_total = self.total_dist.pmf[str(total)]
        else:
            # For total >= 6, allocate the tail evenly
            p_total = self.total_dist.pmf["6+"] / 10  # rough approximation

        # P(h_goals | total) from ratio split ~ Binomial(total, ratio)
        from math import comb
        p_h_given_t = comb(total, h_goals) * (self.ratio ** h_goals) * ((1 - self.ratio) ** a_goals)

        return p_total * p_h_given_t

    def direction_probs(self) -> Dict[str, float]:
        """Compute P(home win), P(draw), P(away win) by enumerating joint space."""
        h_win, draw, a_win = 0.0, 0.0, 0.0
        for h in range(10):
            for a in range(10):
                prob = self.score_prob(h, a)
                if h > a:
                    h_win += prob
                elif h == a:
                    draw += prob
                else:
                    a_win += prob
        total = h_win + draw + a_win
        return {
            "home_win": round(h_win / total, 3) if total > 0 else 0.0,
            "draw": round(draw / total, 3) if total > 0 else 0.0,
            "away_win": round(a_win / total, 3) if total > 0 else 0.0,
        }


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

        # Data quality: ⚠️ estimated teams get 1.3x variance, hosts 1.5x
        data_note = team_data.get("_note", "")
        is_host = side.get("is_host", team_data.get("is_host", False))
        if is_host and side.get("is_host", True):
            data_quality = 1.5
        elif "⚠️" in data_note:
            data_quality = 1.3
        else:
            data_quality = 1.0

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
            "bench_strength": side.get("bench_strength", 0),
            "_data_quality": data_quality,
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

            elif rule_id == "r21_bench_strength":
                bench = ctx.get("bench_strength", 0)
                if bench >= 0.70:
                    # 5换时代：板凳有5个世界级 → 轮换不是真轮换
                    # 全额抵消r16惩罚（后30分钟5个主力上来=准A队）
                    r16_details = [d for d in ctx["rule_details"] if d.startswith("r16")]
                    if r16_details:
                        try:
                            r16_penalty = float(r16_details[-1].split()[-1])
                            recovery = abs(r16_penalty) * 1.0 * rule["gamma"]
                            ctx["goals"] += recovery
                            ctx["triggered_rules"].append(rule_id)
                            ctx["rule_details"].append(f"r21 bench +{recovery:.2f} (5换时代全额回调)")
                        except (ValueError, IndexError):
                            pass
                elif bench >= 0.50:
                    r16_details = [d for d in ctx["rule_details"] if d.startswith("r16")]
                    if r16_details:
                        try:
                            r16_penalty = float(r16_details[-1].split()[-1])
                            recovery = abs(r16_penalty) * 0.25 * rule["gamma"]
                            ctx["goals"] += recovery
                            ctx["triggered_rules"].append(rule_id)
                            ctx["rule_details"].append(f"r21 bench +{recovery:.2f}")
                        except (ValueError, IndexError):
                            pass

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

            elif rule_id == "r22_knockout_decay":
                stage = match.get("stage", "")
                mline = match.get("_moneyline", {})
                if stage == "knockout":
                    fav_odds = mline.get("home", 99) if is_home else mline.get("away", 99)
                    if fav_odds < 1.60:
                        multiplier = rule["delta"]
                        old_goals = ctx["goals"]
                        ctx["goals"] *= multiplier
                        ctx["triggered_rules"].append(rule_id)
                        new_goals = ctx["goals"]
                        ctx["rule_details"].append(f'r22 knockout_decay x{multiplier:.2f} ({old_goals:.2f}->{new_goals:.2f})')

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

            elif rule_id == "r20_rain":
                if match.get("venue_rain"):
                    penalty = rule["delta"] * rule["gamma"]
                    ctx["goals"] += penalty
                    ctx["triggered_rules"].append(rule_id)
                    ctx["rule_details"].append(f"r20 rain {penalty:+.2f}")

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

        # Pass moneyline to match_ctx for r22 knockout_decay
        if "moneyline" in market:
            match_ctx["_moneyline"] = market["moneyline"]

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

        # Methodology scores use floor (Poisson mode), not round
        # round(2.82)=3 but P(2)=24% > P(3)=23%, bar chart shows 2
        methodology_home = max(0, int(h_ctx["goals"]))
        methodology_away = max(0, int(a_ctx["goals"]))

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

        # Boundary separation: when methodology == market and λ on floor/round edge,
        # push methodology to round for that team, market keeps floor. Forces divergence.
        if methodology_home == market_home and methodology_away == market_away:
            h_lam, a_lam = h_ctx["goals"], a_ctx["goals"]
            h_floor, h_round = int(h_lam), round(h_lam)
            a_floor, a_round = int(a_lam), round(a_lam)
            if h_floor != h_round:
                methodology_home = h_round
            elif a_floor != a_round:
                methodology_away = a_round

        # Build output
        methodology_direction = ("home" if methodology_home > methodology_away
                                else ("away" if methodology_home < methodology_away else "draw"))
        market_direction = ("home" if market_home > market_away
                           else ("away" if market_home < market_away else "draw"))

        return {
            "match": f"{home_team} vs {away_team}",
            "generated_at": "",
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
            "market_adjustments": market_adjustments,
            "distributions": self._compute_distributions(
                h_ctx, a_ctx, methodology_home, methodology_away,
                market_home, market_away
            )
        }

    def _compute_distributions(self, h_ctx, a_ctx,
                                mh, ma, mkt_h, mkt_a) -> Dict:
        """Generate Negative Binomial distributions and joint probabilities."""
        # Methodology lambdas and sigmas
        h_lam = h_ctx["goals"]  # pre-round value
        a_lam = a_ctx["goals"]

        # Sigma: pooled from triggered rules' sigmas + baseline
        h_sigma = self._pooled_sigma(h_ctx, mh)
        a_sigma = self._pooled_sigma(a_ctx, ma)

        # Market-adjusted distributions use methodology λ — market signals
        # only affect the final score display, not the underlying distribution.
        # Shifting λ by the rounded-score delta was causing absurd results
        # (e.g. Colombia λ 1.69 → 0.69, P(0)=50% with J罗+Díaz starting).

        m_dist = GoalDistribution(h_lam, h_sigma)
        a_dist = GoalDistribution(a_lam, a_sigma)
        joint = JointDistribution(h_lam, a_lam, h_sigma, a_sigma)

        # Market-adjusted: same football reality, different final score
        mkt_h_dist = m_dist
        mkt_a_dist = a_dist
        mkt_joint = joint

        dirs = joint.direction_probs()

        return {
            "methodology": {
                "home": {
                    "lambda": round(h_lam, 2),
                    "sigma": round(h_sigma, 2),
                    "model": m_dist._model,
                    "pmf": m_dist.pmf,
                },
                "away": {
                    "lambda": round(a_lam, 2),
                    "sigma": round(a_sigma, 2),
                    "model": a_dist._model,
                    "pmf": a_dist.pmf,
                },
                "joint": {
                    "home_win": dirs["home_win"],
                    "draw": dirs["draw"],
                    "away_win": dirs["away_win"],
                }
            },
            "market_adjusted": {
                "home": {
                    "lambda": round(h_lam, 2),
                    "sigma": round(h_sigma, 2),
                    "model": m_dist._model,
                    "pmf": m_dist.pmf,
                    "_score": mkt_h
                },
                "away": {
                    "lambda": round(a_lam, 2),
                    "sigma": round(a_sigma, 2),
                    "model": a_dist._model,
                    "pmf": a_dist.pmf,
                    "_score": mkt_a
                },
                "joint": {
                    "home_win": dirs["home_win"],
                    "draw": dirs["draw"],
                    "away_win": dirs["away_win"],
                }
            }
        }

    def _pooled_sigma(self, ctx, rounded_goals) -> float:
        """Pool sigma from triggered rules + baseline residual + data quality penalty."""
        rules = self.rules
        raw = ctx["goals"]
        total_var = raw  # Poisson baseline: var = λ
        for rid in ctx["triggered_rules"]:
            if rid in rules and rules[rid].get("sigma"):
                total_var += rules[rid]["sigma"] ** 2
        total_var += (raw - rounded_goals) ** 2

        # Data quality penalty: ⚠️ estimated teams get +30% variance, hosts +50%
        quality = ctx.get("_data_quality", 1.0)
        total_var *= quality

        return math.sqrt(max(0.1, total_var))

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
            rating = {"stars": "⭐⭐⭐", "zh": "高", "en": "high"}
        elif net >= 0 and (core_rules_gamma > 0.60 or interval_width < 3.0):
            rating = {"stars": "⭐⭐", "zh": "中", "en": "medium"}
        else:
            rating = {"stars": "⭐", "zh": "低", "en": "low"}

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
    parser.add_argument("--input", "-i", help="Match input JSON file (or directory with --out-dir)")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    parser.add_argument("--out-dir", "-d", help="Batch mode: process all .json in INPUT dir, save to OUTPUT dir")
    parser.add_argument("--json", action="store_true", help="Output raw JSON only")

    args = parser.parse_args()

    if args.out_dir:
        # Batch mode: process all .json files in input directory
        input_dir = args.input or "."
        out_dir = args.out_dir
        os.makedirs(out_dir, exist_ok=True)
        engine = ProphetEngine()

        files = sorted([f for f in os.listdir(input_dir) if f.endswith(".json")])
        if not files:
            print(f"No .json files found in {input_dir}")
            return

        for fname in files:
            in_path = os.path.join(input_dir, fname)
            with open(in_path) as f:
                match_input = json.load(f)

            result = engine.predict(match_input)
            from datetime import datetime, timezone
            ts = datetime.fromtimestamp(os.path.getmtime(in_path), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result["generated_at"] = ts
            json_output = json.dumps(result, indent=2, ensure_ascii=False)

            out_name = fname.replace(".json", "_output.json")
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, "w") as f:
                f.write(json_output)
            print(f"[{result['match']}] → {out_path}")

        print(f"\nDone. {len(files)} predictions saved to {out_dir}/")
        return

    if not args.input:
        parser.error("--input/-i is required (or use --out-dir for batch mode)")

    with open(args.input) as f:
        match_input = json.load(f)

    engine = ProphetEngine()
    result = engine.predict(match_input)

    # Timestamp = input JSON mtime (moment of last data update, not engine runtime)
    from datetime import datetime, timezone
    ts = datetime.fromtimestamp(os.path.getmtime(args.input), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["generated_at"] = ts

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
            # Human-readable output — market-adjusted distributions only
            match_name = result['match']
            home_name, away_name = match_name.split(" vs ")
            mkt_dist = result["distributions"]["market_adjusted"]
            mkt_joint = mkt_dist["joint"]
            mk = result["market_adjusted_score"]

            print(f"\n{'='*70}")
            print(f"  Prophet v1.0.0 — {match_name}")
            print(f"{'='*70}")

            mth = result["methodology_score"]
            print(f"\n  方法论 {mth['home']}-{mth['away']} / 市场修正 {mk['home']}-{mk['away']} ({mk['direction']})  |  信度: {result['confidence']['rating']}")

            # Rules
            h_rules = result["rule_application"]["home"]["triggered_rules"]
            a_rules = result["rule_application"]["away"]["triggered_rules"]
            if h_rules or a_rules:
                parts = []
                if h_rules: parts.append(f"主: {','.join(h_rules)}")
                if a_rules: parts.append(f"客: {','.join(a_rules)}")
                print(f"  触发规则:  {'; '.join(parts)}")

            # Market-adjusted distribution table — collapse weak sides
            def side_rows(pmf):
                """Return list of (label, prob) rows. Collapse 1..6+→'1+球' if P(0)≥80%."""
                if pmf["0"] >= 0.80:
                    return [("0球", pmf["0"]), ("1+球", round(1.0 - pmf["0"], 4))]
                else:
                    return [(f"{k}球", pmf[k]) for k in ["0","1","2","3","4","5","6+"]]

            h_rows = side_rows(mkt_dist["home"]["pmf"])
            a_rows = side_rows(mkt_dist["away"]["pmf"])
            max_rows = max(len(h_rows), len(a_rows))
            while len(h_rows) < max_rows: h_rows.append(("", 0.0))
            while len(a_rows) < max_rows: a_rows.append(("", 0.0))

            print(f"\n  ╔{'═'*25}╦{'═'*25}╗")
            print(f"  ║ {home_name:^23} ║ {away_name:^23} ║")
            print(f"  ╠{'═'*25}╬{'═'*25}╣")
            for (hl, hp), (al, ap) in zip(h_rows, a_rows):
                if hl == "" and al == "": continue
                h_bar = "█" * max(1, int(hp * 40)) if hl else ""
                a_bar = "█" * max(1, int(ap * 40)) if al else ""
                h_cell = f"{hl:>4} {h_bar:<18} {hp*100:>4.0f}%" if hl else ""
                a_cell = f"{al:>4} {a_bar:<18} {ap*100:>4.0f}%" if al else ""
                print(f"  ║ {h_cell:<23} ║ {a_cell:<23} ║")
            print(f"  ╚{'═'*25}╩{'═'*25}╝")
            mth_sigmas = result["distributions"]["methodology"]
            print(f"  λ={mkt_dist['home']['lambda']:.2f} σ={mth_sigmas['home']['sigma']:.2f} {'':>13} λ={mkt_dist['away']['lambda']:.2f} σ={mth_sigmas['away']['sigma']:.2f}")

            # Joint probabilities
            print(f"\n  方向概率: 主胜 {mkt_joint['home_win']*100:.0f}%  平 {mkt_joint['draw']*100:.0f}%  客胜 {mkt_joint['away_win']*100:.0f}%")

            # Market adjustments
            if result["market_adjustments"]:
                print(f"  市场调整: {'; '.join(result['market_adjustments'])}")

            print()


if __name__ == "__main__":
    main()
