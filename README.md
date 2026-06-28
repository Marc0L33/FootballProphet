# Prophet v1.1.0 — Football Match Prediction Engine

> [:cn: 中文](i18n/README_CN.md) · [:es: Español](i18n/README_ES.md) · [:brazil: Português](i18n/README_PT.md) · [:jp: 日本語](i18n/README_JA.md) · [:th: ไทย](i18n/README_TH.md) · [:ru: Русский](i18n/README_RU.md) · [:sa: العربية](i18n/README_AR.md)

A rule-based football score prediction engine with **dual-score output** (methodology + market-adjusted), **3D confidence**, and a **web frontend** for batch match browsing.

Applies to: **World Cup, continental tournaments, domestic leagues, cups, Champions League** — same workflow, different data sources.

> Directional accuracy ~67%, exact score ~22%. Calibrated across 72 matches from the 2026 World Cup (including all 18 MD3 matches across Groups D–L).

## Quick Start

```bash
# 1. Prepare an input file (see test/spain_uruguay.json for full template)
cat > match.json << 'EOF'
{
  "home_team": "South Africa", "away_team": "Canada",
  "home": {
    "tournament_matches": [{"gf":0,"ga":2},{"gf":1,"ga":1},{"gf":1,"ga":0}],
    "key_player_missing": [{"player":"Zwane","tier":"core_playmaker"}],
    "attacking_tier": 3, "rotation_count": 0
  },
  "away": {
    "tournament_matches": [{"gf":1,"ga":1},{"gf":6,"ga":0},{"gf":1,"ga":2}],
    "key_player_missing": [{"player":"Koné","tier":"core_playmaker"}],
    "attacking_tier": 2, "is_host": true, "rotation_count": 0
  },
  "match": {
    "tactical_matchup": {"home_advantage": "even", "away_advantage": "clear_advantage"},
    "venue_rain": false
  },
  "market": {
    "moneyline": {"home":5.00,"draw":3.40,"away":1.66},
    "handicap": "Canada -0.75",
    "totals": "Under 2.25",
    "signals": [{"type":"adjust_total","delta":-1,"reason":"U2.25 → low-scoring knockout"}]
  }
}
EOF

# 2. Run the engine (single match)
python3 engine/predictor.py -i match.json

# 3. Batch mode — process all matches in a directory
python3 engine/predictor.py --input output/predictions/ --out-dir output/web/

# 4. Launch web frontend
cd output/web && python3 -m http.server 8080
```

## Installation

```bash
git clone https://github.com/marcolee/prophet.git
cd prophet
# Dependencies: Python 3.8+ standard library only. No pip install needed.
python3 engine/predictor.py -i test/spain_uruguay.json
```

## Project Structure

```
prophet/
├── README.md                       # English (this file)
├── i18n/                           # Multi-language READMEs
│   ├── README_CN.md                # 中文
│   ├── README_ES.md                # Español
│   ├── README_PT.md                # Português
│   ├── README_JA.md                # 日本語
│   ├── README_TH.md                # ไทย
│   ├── README_RU.md                # Русский
│   └── README_AR.md                # العربية
├── SKILL.md                        # Claude Code skill entry point
├── rules.md                        # Human-readable rule documentation
├── bayesian.md                     # Bayesian methodology
├── ledger.md                       # 72-match ledger + retrospectives
├── data/
│   ├── rules.json                  # 20 rules (engine reads this)
│   └── teams.json                  # Team baseline GF/GA (v1.2 audit)
├── engine/
│   ├── predictor.py                # Core prediction engine
│   ├── bayesian.py                 # Bayesian parameter updater
│   └── backtest.py                 # Batch backtesting tool
├── test/
│   ├── egypt_iran.json             # Minimal example
│   └── spain_uruguay.json          # Full-rule test input
├── output/
│   ├── match_input_template.json   # Input template
│   ├── predictions/                # Match input JSONs
│   └── web/                        # Frontend + output JSONs
│       ├── index.html              # Multi-match browser (← → nav)
│       └── *.json                  # Predicted output files
└── docs/
```

## Two Scores, Two Purposes

The engine outputs **two scores side by side** with distinct roles:

| | Methodology Score | Market-Adjusted Score |
|---|---|---|
| **Source** | Pure formula (⑭+②+Σγδ) | Formula + market signals |
| **Reproducibility** | ✅ Deterministic | ❌ Requires qualitative judgment |
| **Usage** | Baseline; detect methodology drift | Practical betting reference |
| **Distribution** | Shares methodology λ | Same λ, different rounded score |

When the two scores diverge, the market knows something the methodology doesn't — injuries, morale, collusion — but the methodology distribution remains grounded in football reality.

## Prediction Formula

```
Goals_A = r14_blend_GF × r02_opponent_coeff + Σ(triggered_rule_i × γ_i × δ_i)
Goals_B = same, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## Rule System (20 rules)

Twenty rules in priority-chain order. Four-state lifecycle: `🆕 Shadow → 🔵 Active → ⚠️ Demoted → ❌ Deleted`

| # | Rule | E[γ] | δ | Status |
|---|------|------|-----|--------|
| ⑤ | Offensive Incapability | 0.89 | cap 1 goal | 🔵 |
| ⑩ | Early Goal | 0.64 | +1.4 | 🔵 |
| ⑭ | Qualifying Baseline Blend | 0.78 | per team | 🔵 blended GF/GA |
| ⑫ | Tactical Matchup | 0.79 | ±0.5~1.5 | 🔵 |
| ⑯ | Morale Decay (A/B) | 0.55 | -1.5/-1.0 | 🔵 |
| ㉑ | Bench Strength | 0.60 | +100%/+25% × r16 | 🔵 5-sub era |
| ⑰ | Cross-Confederation | 0.50 | ×1.20 | 🆕 |
| ⑮ | Indoor/Climate-Controlled | 0.50 | +0.25 | 🆕 |
| ⑱ | Water Break | 0.50 | +0.15/+0.25 | 🆕 |
| ⑲ | Draw Collusion | 0.80 | -1.0 global | 🔵 no stack w/ adjust_total |
| ⑳ | Rain | 0.60 | -0.25 per team | 🔵 active |
| ⑬ | Extreme Weather | 0.71 | -0.5 | 🔵 suspension >30min |
| ⑪ | GK Heroics ≠ Defense | 0.69 | — | 🔵 |
| ⑨ | GK Unpredictability | 0.75 | — | 🔵 boundary |
| ⑧ | Elite Defense | 0.75 | -1.0 | 🔵 |
| ⑦ | Creativity Absence | 0.69 | -0.3~-1.2 | 🔵 |
| ⑥ | Data Pollution | 0.77 | per level | 🔵 |
| ④ | Red Card Risk | 0.50 | +0.3 | ⚠️ shadow-demoted |
| ② | Opponent Quality Coeff. | 0.69 | 0.60x~1.40x | 🔵 |
| ③ | Home Advantage | 0.70 | +0.4/+0.25 | 🔵 host/diaspora |
| ① | No Clean Sheet | 0.72 | +0.5 | 🔵 |

Full documentation: [rules.md](rules.md) · [bayesian.md](bayesian.md) · [ledger.md](ledger.md).

### Key v1.1.0 Rules

| Rule | What it does | Why |
|------|-------------|-----|
| ㉑ Bench Strength | Fully offsets r16 penalty when bench ≥ 0.7 | 5-sub era: "rested" stars play 30 min |
| ⑳ Rain | -0.25 per team λ in persistent rain | England rain games: 0-0 vs Ghana, 2-0 vs Panama |
| ⑲ No stacking | `draw_both_advance=true` → no extra adjust_total | Croatia-Ghana: methodology 2-1 exact, market 0-0 wrong |

## Claude Code Integration (SKILL.md)

This project is also a **Claude Code skill**. The workflow:

```
Search (qualifying data, injuries, xG, weather, betting odds)
  → Data audit (⑥ wash, cross-verify, AFC round split)
  → Qualitative judgment (⑦ absence, ⑫ tactical, ⑲ collusion)
  → 🔴 Extract market signals (mandatory, never leave empty)
  → Fill match.json → Run engine → Output dual scores
```

Key mandates in SKILL.md:
- **Chinese source priority** for lineups, scores, cards (懂球帝/虎扑/直播吧)
- **Weather forecast** must be checked pre-match (triggers ⑳)
- **Market signals** must be non-empty when odds data exists
- **⑲ + adjust_total stacking prohibited** (triple-counting bug verified by Croatia-Ghana)

See [SKILL.md](SKILL.md) for the complete workflow.

## Engine vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute formula + apply rules | ✅ | — |
| Search injuries, lineups, weather | — | ✅ |
| Detect data pollution (⑥) | — | ✅ |
| Market signal extraction | — | ✅ |
| Batch backtest 72 matches | ✅ | — |
| Interpret odds & qualitative signals | — | ✅ |

## Web Frontend

`output/web/index.html` — drag-and-drop batch match viewer:
- Upload multiple prediction JSONs
- ← → keyboard navigation between matches
- Dual score display (methodology | market-adjusted)
- Per-team goal probability distributions with bar charts
- Joint win/draw/loss probability bars
- Market adjustment transparency

```bash
cd output/web && python3 -m http.server 8080
# Open http://localhost:8080
```

## MD3 JKL Retrospective (v1.1.0)

| Match | Methodology | Actual | Note |
|-------|-----------|--------|------|
| Croatia vs Ghana | **2-1** ✅ | 2-1 | Exact hit |
| DR Congo vs Uzbekistan | **2-1** ✅ | 3-1 | Late goal, otherwise exact |
| Panama vs England | 0-3 | 0-2 | Rain + low motivation (⑳) |
| Colombia vs Portugal | 2-2 | 0-0 | VAR offside, both cautious |
| Jordan vs Argentina | 1-2 | 1-3 | Penalty +1; ㉑ bench callback |
| Algeria vs Austria | 0-1 | 3-3 | ⑲ collusion broke after first goal |

Direction: 4/6 (67%). Exact: 2/6 (33%). Ledger: 12/18 direction overall.

## License

MIT

## Contributing

Welcome for: new rule proposals (with backtest data), team data updates, coefficient calibration, Claude Code skill workflow enhancements.
