# Prophet v1.0.0 — เครื่องมือทำนายผลการแข่งขันฟุตบอล

> [:us: English](README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

เครื่องมือทำนายผลฟุตบอลตามกฎ พร้อม**เอาต์พุตสองคะแนน**: คะแนนตามวิธีการล้วน และคะแนนที่ปรับตามตลาด

ใช้ได้กับ: **ฟุตบอลโลก, ทัวร์นาเมนต์ระดับทวีป, ลีกในประเทศ (พรีเมียร์ลีก, ลาลีกา ฯลฯ), ถ้วย (แชมเปี้ยนส์ลีก, เอฟเอคัพ ฯลฯ)** — เวิร์กโฟลว์เดียวกัน แหล่งข้อมูลต่างกัน

> ความแม่นยำเชิงทิศทางเป้าหมาย ~80%, สกอร์ที่แน่นอน ~40% ปรับเทียบจาก 60+ แมตช์ในฟุตบอลโลก 2026

## เริ่มต้นใช้งาน

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

## การติดตั้ง

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# การพึ่งพา: Python 3.8+ ไลบรารีมาตรฐานเท่านั้น ไม่ต้องใช้ pip install
python engine/predictor.py --input test/egypt_iran.json
```

## สองคะแนน สองวัตถุประสงค์

| | วิธีการ | ปรับตามตลาด |
|---|---|---|
| **แหล่งที่มา** | Cálculo puro de fórmula | Fórmula + señales de mercado |
| **ข้อมูลเข้า** | GF/GA clasificatorio + valores δ | Columna izq. + cuotas, niveles, sentimiento |
| **ความสามารถในการทำซ้ำ** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **การใช้งาน** | Línea base; detectar desviación | Referencia práctica |

เมื่อสองคะแนนแตกต่างกัน แสดงว่าตลาดรู้บางสิ่งที่วิธีการไม่รู้ — การบาดเจ็บ ขวัญกำลังใจ การสมรู้ร่วมคิด — และควรเลือกใช้คะแนนที่ปรับตามตลาด

## สูตรการทำนาย

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## ระบบกฎ

กฎ 19 ข้อเรียงตามลำดับความสำคัญ แต่ละกฎมีวงจรชีวิตสี่สถานะ:

```
รับเข้าเงา (🆕) → ใช้งาน (🔵) → ลดระดับเงา (⚠️) → ลบ (❌)
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

เอกสารฉบับเต็ม: [rules.md](rules.md). Bayesian: [bayesian.md](bayesian.md).

## การผสานรวมกับ Claude Code

โปรเจกต์นี้ยังทำงานเป็น **สกิล Claude Code** Claude รับผิดชอบ:

1. **ค้นหา**: ข้อมูลรอบคัดเลือก, การบาดเจ็บ, xG, อัตราต่อรอง
2. **การตัดสินเชิงคุณภาพ**: ⑥ การปนเปื้อนข้อมูล, ⑦ ผลกระทบจากการบาดเจ็บ, ⑫ แมตช์อัพเชิงกลยุทธ์, ⑲ การสมรู้ร่วมคิด
3. **กรอก JSON**: ป้อนข้อมูล `match.json` จากผลการค้นหา
4. **รันเอนจิน**: `python engine/predictor.py -i match.json`
5. **แปลผลลัพธ์**: แปลง JSON เป็นรายงานการทำนายภาษาธรรมชาติ

เอนจินจัดการการคำนวณที่แน่นอนทั้งหมด Claude จัดการการค้นหาและการตัดสิน — แต่ละอย่างทำในสิ่งที่ถนัดที่สุด

See [SKILL.md](SKILL.md).

## การอัปเดตแบบเบย์

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

## การทดสอบย้อนหลัง

```bash
python engine/backtest.py --matches backtest_matches.json
```

## การแบ่งงาน: เอนจิน vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| **ค้นหา**: ข้อมูลรอบคัดเลือก, การบาดเจ็บ, xG, อัตราต่อรอง | — | ✅ |
| **การตัดสินเชิงคุณภาพ**: ⑥ การปนเปื้อนข้อมูล, ⑦ ผลกระทบจากการบาดเจ็บ, ⑫ แมตช์อัพเชิงกลยุทธ์, ⑲ การสมรู้ร่วมคิด | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| **แปลผลลัพธ์**: แปลง JSON เป็นรายงานการทำนายภาษาธรรมชาติ | — | ✅ |

## ใบอนุญาต

MIT

## การมีส่วนร่วม

Issues and PRs welcome.
