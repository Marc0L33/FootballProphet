# Prophet v1.0.0 — Motor de Predicción de Partidos de Fútbol

> [:us: English](README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

Un motor de predicción de resultados de fútbol basado en reglas con **salida de doble puntuación**: metodología pura y ajustada al mercado.

Aplica a: **Mundial, torneos continentales, ligas domésticas (Premier League, La Liga, etc.), copas (Champions League, FA Cup, etc.)** — mismo flujo de trabajo, diferentes fuentes de datos.

> Precisión direccional objetivo ~70%, puntuación exacta ~20%. Metodología calibrada en más de 60 partidos del Mundial 2026.

## Inicio Rápido

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

## Instalación

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# Dependencias: solo biblioteca estándar de Python 3.8+. No se necesita pip install.
python engine/predictor.py --input test/egypt_iran.json
```

## Dos Puntuaciones, Dos Propósitos

| | Metodología | Ajustado al Mercado |
|---|---|---|
| **Fuente** | Cálculo puro de fórmula | Fórmula + señales de mercado |
| **Entradas** | GF/GA clasificatorio + valores δ | Columna izq. + cuotas, niveles, sentimiento |
| **Reproducibilidad** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **Uso** | Línea base; detectar desviación | Referencia práctica |

Cuando las dos puntuaciones divergen, el mercado sabe algo que la metodología no — lesiones, moral, colusión — y se debe preferir la puntuación ajustada al mercado.

## Fórmula de Predicción

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## Sistema de Reglas

Diecinueve reglas en orden de cadena de prioridad. Cada regla tiene un ciclo de vida de cuatro estados:

```
Admisión Sombra (🆕) → Activa (🔵) → Degradada Sombra (⚠️) → Eliminada (❌)
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

Documentación completa: [rules.md](rules.md). Bayesian: [bayesian.md](bayesian.md).

## Integración con Claude Code

Este proyecto también funciona como una **habilidad de Claude Code**. Claude se encarga de:

1. **Búsqueda**: datos de clasificación, lesiones, xG, cuotas
2. **Juicio cualitativo**: ⑥ contaminación de datos, ⑦ impacto de lesiones, ⑫ enfrentamiento táctico, ⑲ colusión
3. **Rellenar el JSON**: completar `match.json` con los resultados de la búsqueda
4. **Ejecutar el motor**: `python engine/predictor.py -i match.json`
5. **Interpretar la salida**: traducir JSON a un informe de predicción en lenguaje natural

El motor maneja todo el cálculo determinista. Claude maneja la búsqueda y el juicio — cada uno haciendo lo que mejor sabe hacer.

See [SKILL.md](SKILL.md).

## Actualización Bayesiana

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

## Backtesting

```bash
python engine/backtest.py --matches backtest_matches.json
```

## División de Trabajo: Engine vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| **Búsqueda**: datos de clasificación, lesiones, xG, cuotas | — | ✅ |
| **Juicio cualitativo**: ⑥ contaminación de datos, ⑦ impacto de lesiones, ⑫ enfrentamiento táctico, ⑲ colusión | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| **Interpretar la salida**: traducir JSON a un informe de predicción en lenguaje natural | — | ✅ |

## Licencia

MIT

## Contribuciones

Issues and PRs welcome.
