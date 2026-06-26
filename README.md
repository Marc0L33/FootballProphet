# Prophet v1.0.0 — Football Match Prediction Engine

> [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

A rule-based football score prediction engine with **dual-score output**: pure methodology and market-adjusted.

Applies to: **World Cup, continental tournaments, domestic leagues (Premier League, La Liga, etc.), cups (Champions League, FA Cup, etc.)** — same workflow, different data sources.

> Directional accuracy target ~80%, exact score ~40%. Methodology calibrated across 60+ matches from the 2026 World Cup.

## Quick Start

```bash
# 1. Prepare an input file (JSON)
cat > match.json << 'EOF'
{
  "home_team": "Spain",
  "away_team": "Uruguay",
  "home": {
    "tournament_matches": [{"gf": 0, "ga": 0}, {"gf": 4, "ga": 0}],
    "locked_group_winner": false,
    "already_qualified": true,
    "rotation_count": 0,
    "key_player_missing": []
  },
  "away": {
    "tournament_matches": [{"gf": 1, "ga": 1}, {"gf": 2, "ga": 2}],
    "key_player_missing": [{"player": "Darwin Nunez", "tier": "main_striker"}]
  },
  "match": {
    "tactical_matchup": {"home_advantage": "clear_advantage", "away_advantage": "even"}
  },
  "market": {}
}
EOF

# 2. Run the engine
python engine/predictor.py --input match.json

# 3. Output
# ============================================================
# Prophet v1.0.0 — Spain vs Uruguay
# ============================================================
#    Methodology Score:  2 - 0 (home)
#    Market-Adjusted:    2 - 0 (home)
#    Confidence:         ⭐⭐⭐⭐ high
```

## Installation

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# Dependencies: Python 3.8+ standard library only. No pip install needed.
python engine/predictor.py --input test/egypt_iran.json
```

## Project Structure

```
prophet/
├── README.md                     # This file (English, default)
├── README_CN.md                  # 中文 · Chinese
├── README_ES.md                  # Español · Spanish
├── README_PT.md                  # Português · Portuguese
├── README_JA.md                  # 日本語 · Japanese
├── README_TH.md                  # ไทย · Thai
├── README_RU.md                  # Русский · Russian
├── README_AR.md                  # العربية · Arabic
├── SKILL.md                      # Claude Code skill entry point
├── rules.md                      # Human-readable rule documentation
├── bayesian.md                   # Bayesian methodology
├── ledger.md                     # Historical match ledger
├── data/
│   ├── rules.json                # Rule definitions (19 rules, engine reads this)
│   └── teams.json                # Team baseline GF/GA data
├── engine/
│   ├── predictor.py              # Core prediction engine
│   ├── bayesian.py               # Bayesian parameter updater
│   └── backtest.py               # Batch backtesting tool
├── test/
│   ├── egypt_iran.json           # Example input
│   └── spain_uruguay.json        # Full-rule test input
└── output/
    ├── match_input_template.json  # Input template for Claude/humans
    └── predictions/               # Prediction output directory
```

## Two Scores, Two Purposes

The engine outputs **two scores** with distinct roles:

| | Methodology Score | Market-Adjusted Score |
|---|---|---|
| **Source** | Pure formula computation | Formula + market signals |
| **Inputs** | Qualifying GF/GA + rule δ values | Left column + odds, water levels, sentiment |
| **Reproducibility** | ✅ Deterministic | ❌ Requires qualitative judgment |
| **Usage** | Baseline; detect methodology drift | Practical reference |

When the two scores diverge, the market knows something the methodology doesn't — injuries, morale, collusion — and the market-adjusted score should be preferred.

## Prediction Formula

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## Rule System

Nineteen rules in priority-chain order. Each rule has a four-state lifecycle:

```
Shadow Admission (🆕) → Active (🔵) → Shadow Demoted (⚠️) → Deleted (❌)
```

| # | Rule | E[γ] | δ | Status |
|---|------|------|-----|--------|
| ⑤ | Offensive Incapability | 0.89 | -1.5 | 🔵 hard cap |
| ⑩ | Early Goal | 0.64 | +1.4 | 🔵 |
| ⑭ | Qualifying Baseline | 0.78 | per team | 🔵 blended GF/GA |
| ⑫ | Tactical Matchup | 0.79 | ±0.5~1.5 | 🔵 |
| ⑯ | Morale Decay | 0.55 | -1.5/-1.0 | 🔵 v1.0.0 activated |
| ⑰ | Cross-Confederation Calibration | 0.50 | ×1.20 | 🆕 |
| ⑮ | Indoor/Climate-Controlled | 0.50 | +0.25 | 🆕 |
| ⑱ | Mandatory Water Break | 0.50 | +0.15/+0.25 | 🆕 |
| ⑲ | Draw Collusion Detection | 0.80 | -1.0(global) | 🔵 v1.0.0 activated |
| ⑬ | Extreme Weather | 0.71 | -0.5 | 🔵 |
| ⑪ | GK Heroics ≠ Defense | 0.69 | — | 🔵 |
| ⑨ | GK Unpredictability | 0.75 | — | 🔵 boundary |
| ⑧ | Elite Defense | 0.75 | -1.0 | 🔵 |
| ⑦ | Creativity Absence | 0.69 | -0.3~-1.2 | 🔵 |
| ⑥ | Data Pollution | 0.77 | per level | 🔵 incl. minnow wash |
| ④ | Red Card Risk | 0.50 | +0.3 | ⚠️ shadow-demoted |
| ② | Opponent Quality Coefficient | 0.69 | 0.60x~1.40x | 🔵 |
| ③ | Home Advantage | 0.70 | +0.4/+0.25 | 🔵 |
| ① | No Clean Sheet Prediction | 0.72 | +0.5 | 🔵 |

Full documentation: [rules.md](rules.md). Bayesian methodology: [bayesian.md](bayesian.md).

## Claude Code Integration

This project also functions as a **Claude Code skill**. Claude handles:

1. **Search**: qualifying data, injuries, xG, betting lines
2. **Qualitative judgment**: ⑥ data pollution, ⑦ injury impact, ⑫ tactical matchup, ⑲ collusion
3. **Fill the JSON**: populate `match.json` from search results
4. **Run the engine**: `python engine/predictor.py -i match.json`
5. **Interpret output**: translate JSON into a natural-language prediction report

The engine handles all deterministic computation. Claude handles search and judgment — each doing what it does best.

See [SKILL.md](SKILL.md) for the full Claude workflow.

## Bayesian Updating

After each match, update rule parameters with a single command:

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

Each triggered rule's α/β/n counters update automatically, E[γ] recalculates via posterior mean, and rule lifecycle changes (promotion/demotion/exit) are checked automatically.

## Backtesting

```bash
python engine/backtest.py --matches backtest_matches.json
```

Accepts JSON array or JSONL format. Outputs directional accuracy, exact-score rate, and per-round statistics.

## Data Sources (by Competition)

The engine itself contains no data — data is provided by the user (human or Claude) via input JSON. Different competitions require different data sources:

| Competition | "Qualifying" Equivalent (⑭) | Tournament Data | Example Sources |
|------------|---------------------------|-----------------|-----------------|
| **World Cup** | Qualifying GF/GA | Group stage matches played | FIFA.com, FBref |
| **Continental Cup** | Qualifying + friendlies GF/GA | Tournament matches played | UEFA.com, CONMEBOL |
| **Domestic League** | **Season average GF/GA** | Last 5 rounds + home/away split | WhoScored, Understat, Soccerway |
| **Domestic Cup** | League season data | Cup rounds played | Transfermarkt, FBref |
| **Champions League** | Group stage GF/GA + domestic league | Knockout rounds played | UEFA.com, Opta |

`data/teams.json` currently holds 2026 World Cup data — swap in competition-specific data for league/cup predictions.

## Engine vs. Claude: Division of Labor

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| Search for injury news | — | ✅ |
| Detect data pollution (⑥) | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| Interpret "odds +147, U2.0 heavy" | — | ✅ |

## License

MIT

## Contributing

Issues and PRs welcome, especially for:
- New rule proposals (with backtest data)
- Team data updates for new competitions
- Coefficient calibration improvements
- Claude Code skill workflow enhancements
