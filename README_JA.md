# Prophet v1.0.0 — サッカー試合予測エンジン

> [:us: English](README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

ルールベースのサッカースコア予測エンジン。**純粋方法論スコア**と**市場調整スコア**の二重出力をサポート。

対象: **W杯、大陸選手権、国内リーグ（プレミアリーグ、ラ・リーガ等）、カップ戦（CL、FAカップ等）** — 同じワークフロー、異なるデータソース。

> 方向精度目標 ~70%、正確スコア ~20%。2026年W杯60試合以上でキャリブレーション済み。

## クイックスタート

```bash
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

python engine/predictor.py --input match.json
```

## インストール

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# 依存関係: Python 3.8+ 標準ライブラリのみ。pip install 不要。
python engine/predictor.py --input test/egypt_iran.json
```

## 2つのスコア、2つの目的

| | 方法論 | 市場調整 |
|---|---|---|
| **ソース** | Cálculo puro de fórmula | Fórmula + señales de mercado |
| **入力** | GF/GA clasificatorio + valores δ | Columna izq. + cuotas, niveles, sentimiento |
| **再現性** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **用途** | Línea base; detectar desviación | Referencia práctica |

2つのスコアが乖離する場合、市場は方法論が知らない何か — 怪我、士気、談合 — を知っており、市場調整スコアを優先すべきです。

## 予測式

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## ルールシステム

優先順位チェーンに従う19のルール。各ルールには4つのライフサイクル状態があります：

```
シャドウ承認 (🆕) → アクティブ (🔵) → シャドウ降格 (⚠️) → 削除 (❌)
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

完全なドキュメント: [rules.md](rules.md). Bayesian: [bayesian.md](bayesian.md).

## Claude Code 連携

このプロジェクトは **Claude Code スキル**としても機能します。Claude の役割:

1. **検索**: 予選データ、怪我、xG、オッズ
2. **定性判断**: ⑥ データ汚染、⑦ 怪我の影響、⑫ 戦術的マッチアップ、⑲ 談合
3. **JSON入力**: 検索結果から `match.json` を作成
4. **エンジン実行**: `python engine/predictor.py -i match.json`
5. **出力解釈**: JSON を自然言語の予測レポートに変換

エンジンは決定論的計算を処理。Claude は検索と判断を処理 — それぞれが最も得意とすることを実行。

See [SKILL.md](SKILL.md).

## ベイズ更新

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

## バックテスト

```bash
python engine/backtest.py --matches backtest_matches.json
```

## 役割分担: エンジン vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| **検索**: 予選データ、怪我、xG、オッズ | — | ✅ |
| **定性判断**: ⑥ データ汚染、⑦ 怪我の影響、⑫ 戦術的マッチアップ、⑲ 談合 | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| **出力解釈**: JSON を自然言語の予測レポートに変換 | — | ✅ |

## ライセンス

MIT

## コントリビューション

Issues and PRs welcome.
