# Prophet v1.0.0 — محرك التنبؤ بمباريات كرة القدم

> [:us: English](README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

محرك للتنبؤ بنتائج مباريات كرة القدم قائم على القواعد مع **إخراج مزدوج للنتيجة**: المنهجية البحتة والمعدلة حسب السوق.

ينطبق على: **كأس العالم، البطولات القارية، الدوريات المحلية (الدوري الإنجليزي، الدوري الإسباني، إلخ)، الكؤوس (دوري الأبطال، كأس الاتحاد الإنجليزي، إلخ)** — نفس سير العمل، مصادر بيانات مختلفة.

> دقة الاتجاه المستهدفة ~80%، النتيجة الدقيقة ~40%. تمت معايرة المنهجية عبر أكثر من 60 مباراة في كأس العالم 2026.

## البدء السريع

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

## التثبيت

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# الاعتمادات: مكتبة Python 3.8+ القياسية فقط. لا حاجة لـ pip install.
python engine/predictor.py --input test/egypt_iran.json
```

## نتيجتان، غرضان

| | المنهجية | معدل حسب السوق |
|---|---|---|
| **المصدر** | Cálculo puro de fórmula | Fórmula + señales de mercado |
| **المدخلات** | GF/GA clasificatorio + valores δ | Columna izq. + cuotas, niveles, sentimiento |
| **قابلية التكرار** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **الاستخدام** | Línea base; detectar desviación | Referencia práctica |

عندما تتباعد النتيجتان، يعرف السوق شيئًا لا تعرفه المنهجية — الإصابات، الروح المعنوية، التواطؤ — ويجب تفضيل النتيجة المعدلة حسب السوق.

## صيغة التنبؤ

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## نظام القواعد

تسع عشرة قاعدة بترتيب سلسلة الأولوية. لكل قاعدة دورة حياة من أربع حالات:

```
قبول ظلي (🆕) → نشط (🔵) → تخفيض ظلي (⚠️) → محذوف (❌)
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

التوثيق الكامل: [rules.md](rules.md). Bayesian: [bayesian.md](bayesian.md).

## التكامل مع Claude Code

يعمل هذا المشروع أيضًا كـ **مهارة Claude Code**. يتولى Claude:

1. **البحث**: بيانات التصفيات، الإصابات، xG، الاحتمالات
2. **الحكم النوعي**: ⑥ تلوث البيانات، ⑦ تأثير الإصابات، ⑫ المواجهة التكتيكية، ⑲ التواطؤ
3. **ملء JSON**: تعبئة `match.json` من نتائج البحث
4. **تشغيل المحرك**: `python engine/predictor.py -i match.json`
5. **تفسير المخرجات**: ترجمة JSON إلى تقرير تنبؤ باللغة الطبيعية

يتولى المحرك جميع الحسابات الحتمية. يتولى Claude البحث والحكم — كلٌ يقوم بما يتقنه.

See [SKILL.md](SKILL.md).

## التحديث البايزي

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

## الاختبار العكسي

```bash
python engine/backtest.py --matches backtest_matches.json
```

## تقسيم العمل: المحرك مقابل Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| **البحث**: بيانات التصفيات، الإصابات، xG، الاحتمالات | — | ✅ |
| **الحكم النوعي**: ⑥ تلوث البيانات، ⑦ تأثير الإصابات، ⑫ المواجهة التكتيكية، ⑲ التواطؤ | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| **تفسير المخرجات**: ترجمة JSON إلى تقرير تنبؤ باللغة الطبيعية | — | ✅ |

## الترخيص

MIT

## المساهمة

Issues and PRs welcome.
