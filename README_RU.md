# Prophet v1.0.0 — Футбольный Прогностический Движок

> [:us: English](README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

Основанный на правилах движок прогнозирования футбольных матчей с **двойным выводом счёта**: чистая методология и с поправкой на рынок.

Применяется к: **ЧМ, континентальным турнирам, национальным лигам (АПЛ, Ла Лига и др.), кубкам (ЛЧ, Кубок Англии и др.)** — единый рабочий процесс, разные источники данных.

> Целевая точность направления ~70%, точный счёт ~20%. Методология откалибрована на 60+ матчах ЧМ-2026.

## Быстрый старт

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

## Установка

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# Зависимости: только стандартная библиотека Python 3.8+. pip install не требуется.
python engine/predictor.py --input test/egypt_iran.json
```

## Два счёта, две цели

| | Методология | С поправкой на рынок |
|---|---|---|
| **Источник** | Cálculo puro de fórmula | Fórmula + señales de mercado |
| **Входные данные** | GF/GA clasificatorio + valores δ | Columna izq. + cuotas, niveles, sentimiento |
| **Воспроизводимость** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **Применение** | Línea base; detectar desviación | Referencia práctica |

Когда два счёта расходятся, рынок знает то, чего не знает методология — травмы, мораль, сговор — и следует предпочесть счёт с поправкой на рынок.

## Формула прогнозирования

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## Система правил

Девятнадцать правил в порядке приоритетной цепочки. Каждое правило имеет четырёхэтапный жизненный цикл:

```
Теневое допущение (🆕) → Активное (🔵) → Теневое понижение (⚠️) → Удалено (❌)
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

Полная документация: [rules.md](rules.md). Bayesian: [bayesian.md](bayesian.md).

## Интеграция с Claude Code

Этот проект также функционирует как **навык Claude Code**. Claude отвечает за:

1. **Поиск**: отборочные данные, травмы, xG, коэффициенты
2. **Качественная оценка**: ⑥ загрязнение данных, ⑦ влияние травм, ⑫ тактическое противостояние, ⑲ сговор
3. **Заполнение JSON**: заполнить `match.json` результатами поиска
4. **Запуск движка**: `python engine/predictor.py -i match.json`
5. **Интерпретация вывода**: преобразовать JSON в отчёт с прогнозом на естественном языке

Движок выполняет все детерминированные вычисления. Claude выполняет поиск и оценку — каждый делает то, что у него получается лучше всего.

See [SKILL.md](SKILL.md).

## Байесовское обновление

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

## Бэктестинг

```bash
python engine/backtest.py --matches backtest_matches.json
```

## Разделение труда: Движок vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| **Поиск**: отборочные данные, травмы, xG, коэффициенты | — | ✅ |
| **Качественная оценка**: ⑥ загрязнение данных, ⑦ влияние травм, ⑫ тактическое противостояние, ⑲ сговор | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| **Интерпретация вывода**: преобразовать JSON в отчёт с прогнозом на естественном языке | — | ✅ |

## Лицензия

MIT

## Участие в разработке

Issues and PRs welcome.
