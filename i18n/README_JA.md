# Prophet v1.1.0 — サッカー試合予測エンジン

> [:us: English](../README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

ルールベースのサッカースコア予測エンジン。**デュアルスコア出力**（方法論 + 市場調整）、**3D信頼度**、試合一覧ブラウジング用の**Webフロントエンド**を搭載。

対象: **W杯、大陸選手権、国内リーグ、カップ戦、チャンピオンズリーグ** — 同じワークフロー、異なるデータソース。

> 方向精度 ~67%、正確スコア ~22%。2026年W杯72試合（グループD〜LのMD3全18試合を含む）でキャリブレーション済み。

## クイックスタート

```bash
# 1. 入力ファイルを準備（完全なテンプレートは test/spain_uruguay.json を参照）
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

# 2. エンジンを実行（単一試合）
python3 engine/predictor.py -i match.json

# 3. バッチモード — ディレクトリ内の全試合を処理
python3 engine/predictor.py --input output/predictions/ --out-dir output/web/

# 4. Webフロントエンドを起動
cd output/web && python3 -m http.server 8080
```

## インストール

```bash
git clone https://github.com/marcolee/prophet.git
cd prophet
# 依存関係: Python 3.8+ 標準ライブラリのみ。pip install 不要。
python3 engine/predictor.py -i test/spain_uruguay.json
```

## プロジェクト構成

```
prophet/
├── README.md                       # 英語（本家）
├── i18n/                           # 多言語README
│   ├── README_CN.md                # 中文
│   ├── README_ES.md                # Español
│   ├── README_PT.md                # Português
│   ├── README_JA.md                # 日本語
│   ├── README_TH.md                # ไทย
│   ├── README_RU.md                # Русский
│   └── README_AR.md                # العربية
├── SKILL.md                        # Claude Code スキルエントリポイント
├── rules.md                        # ルール解説（人間可読）
├── bayesian.md                     # ベイズ方法論
├── ledger.md                       # 72試合の台帳 + 振り返り
├── data/
│   ├── rules.json                  # 20ルール（エンジンが読み取り）
│   └── teams.json                  # チーム基準GF/GA（v1.2監査済み）
├── engine/
│   ├── predictor.py                # コア予測エンジン
│   ├── bayesian.py                 # ベイズパラメータ更新
│   └── backtest.py                 # バッチバックテストツール
├── test/
│   ├── egypt_iran.json             # 最小構成の例
│   └── spain_uruguay.json          # 全ルールテスト入力
├── output/
│   ├── match_input_template.json   # 入力テンプレート
│   ├── predictions/                # 試合入力JSON群
│   └── web/                        # フロントエンド + 出力JSON
│       ├── index.html              # 複数試合ブラウザ（← → ナビゲーション）
│       └── *.json                  # 予測出力ファイル
└── docs/
```

## 2つのスコア、2つの目的

エンジンは**2つのスコアを並べて出力**し、それぞれ異なる役割を持ちます:

| | 方法論スコア | 市場調整スコア |
|---|---|---|
| **ソース** | 純粋な計算式 (⑭+②+Σγδ) | 計算式 + 市場シグナル |
| **再現性** | ✅ 決定論的 | ❌ 定性的判断が必要 |
| **用途** | ベースライン; 方法論のドリフト検出 | 実践的なベッティング参考値 |
| **分布** | 方法論 λ を共有 | 同一 λ、異なる丸めスコア |

2つのスコアが乖離する場合、市場は方法論が知らない何か — 怪我、士気、談合 — を知っています。しかし方法論の分布はサッカーの現実に根ざしています。

## 予測式

```
Goals_A = r14_blend_GF × r02_opponent_coeff + Σ(triggered_rule_i × γ_i × δ_i)
Goals_B = same, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## ルールシステム（20ルール）

優先順位チェーンに従う20のルール。4状態ライフサイクル: `🆕 Shadow → 🔵 Active → ⚠️ Demoted → ❌ Deleted`

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

完全なドキュメント: [rules.md](../rules.md) · [bayesian.md](../bayesian.md) · [ledger.md](../ledger.md).

### v1.1.0 の主要ルール

| ルール | 機能 | 理由 |
|------|-------------|-----|
| ㉑ Bench Strength | ベンチ ≥ 0.7 の場合 r16 ペナルティを完全相殺 | 5-sub時代: 「温存」スターが30分プレー |
| ⑳ Rain | 持続的な雨天時に1チームあたり -0.25 λ | イングランド雨天試合: 0-0 vs ガーナ, 2-0 vs パナマ |
| ⑲ スタッキング禁止 | `draw_both_advance=true` → adjust_total 追加不可 | クロアチア-ガーナ: 方法論 2-1 的中, 市場 0-0 外れ |

## Claude Code 連携 (SKILL.md)

このプロジェクトは **Claude Code スキル**としても機能します。ワークフロー:

```
検索 (予選データ、怪我、xG、天候、ベッティングオッズ)
  → データ監査 (⑥ 洗浄、クロス検証、AFCラウンド分割)
  → 定性判断 (⑦ 欠如、⑫ 戦術、⑲ 談合)
  → 🔴 市場シグナル抽出（必須、空のままにしない）
  → match.json に入力 → エンジン実行 → デュアルスコア出力
```

SKILL.md の主要マンデート:
- **中国語ソース優先** でスタメン、スコア、カードを取得（懂球帝/虎扑/直播吧）
- **天気予報**は試合前に必ず確認（⑳ 発動条件）
- **市場シグナル**はオッズデータが存在する場合、空配列不可
- **⑲ + adjust_total のスタッキング禁止**（クロアチア-ガーナで検証済みの三重計上バグ）

完全なワークフローは [SKILL.md](../SKILL.md) を参照。

## エンジン vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| 計算式の適用 + ルール実行 | ✅ | — |
| 怪我・スタメン・天候の検索 | — | ✅ |
| データ汚染の検出 (⑥) | — | ✅ |
| 市場シグナルの抽出 | — | ✅ |
| 72試合のバッチバックテスト | ✅ | — |
| オッズと定性シグナルの解釈 | — | ✅ |

## Web フロントエンド

`output/web/index.html` — ドラッグ＆ドロップのバッチ試合ビューア:
- 複数の予測JSONをアップロード
- ← → キーボードで試合間を移動
- デュアルスコア表示（方法論 | 市場調整）
- チーム別ゴール確率分布（バーチャート付き）
- 勝ち/引き分け/負けの結合確率バー
- 市場調整の透明性表示

```bash
cd output/web && python3 -m http.server 8080
# http://localhost:8080 を開く
```

## MD3 JKL 振り返り (v1.1.0)

| 試合 | 方法論 | 実際 | 備考 |
|-------|-----------|------|------|
| Croatia vs Ghana | **2-1** ✅ | 2-1 | 完全一致 |
| DR Congo vs Uzbekistan | **2-1** ✅ | 3-1 | 終盤失点、それ以外は一致 |
| Panama vs England | 0-3 | 0-2 | 雨天 + 低モチベ (⑳) |
| Colombia vs Portugal | 2-2 | 0-0 | VARオフサイド、両者慎重 |
| Jordan vs Argentina | 1-2 | 1-3 | PK +1; ㉑ ベンチコールバック |
| Algeria vs Austria | 0-1 | 3-3 | ⑲ 談合が初失点後に崩壊 |

方向: 4/6 (67%). 完全一致: 2/6 (33%). 台帳: 全体で 12/18 方向一致.

## ライセンス

MIT

## コントリビューション

歓迎する内容: 新ルール提案（バックテストデータ付き）、チームデータ更新、係数キャリブレーション、Claude Code スキルワークフローの強化。
