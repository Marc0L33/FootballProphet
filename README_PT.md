# Prophet v1.0.0 — Motor de Previsão de Partidas de Futebol

> [:us: English](README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

Um motor de previsão de resultados de futebol baseado em regras com **saída de pontuação dupla**: metodologia pura e ajustada ao mercado.

Aplica-se a: **Copa do Mundo, torneios continentais, ligas nacionais (Premier League, La Liga, etc.), copas (Champions League, FA Cup, etc.)** — mesmo fluxo de trabalho, fontes de dados diferentes.

> Precisão direcional alvo ~70%, placar exato ~20%. Metodologia calibrada em mais de 60 partidas da Copa de 2026.

## Início Rápido

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

## Instalação

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# Dependências: apenas biblioteca padrão Python 3.8+. Não requer pip install.
python engine/predictor.py --input test/egypt_iran.json
```

## Duas Pontuações, Dois Propósitos

| | Metodologia | Ajustado ao Mercado |
|---|---|---|
| **Fonte** | Cálculo puro de fórmula | Fórmula + señales de mercado |
| **Entradas** | GF/GA clasificatorio + valores δ | Columna izq. + cuotas, niveles, sentimiento |
| **Reprodutibilidade** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **Uso** | Línea base; detectar desviación | Referencia práctica |

Quando as duas pontuações divergem, o mercado sabe algo que a metodologia não — lesões, moral, conluio — e a pontuação ajustada ao mercado deve ser preferida.

## Fórmula de Previsão

```
Goals_A = r14_baseline_GF × r02_opponent_coeff + Σ(triggered_rules_i × γ_i × δ_i)
Goals_B = same computation, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## Sistema de Regras

Dezenove regras em ordem de cadeia de prioridade. Cada regra possui um ciclo de vida de quatro estados:

```
Admissão Sombra (🆕) → Ativa (🔵) → Rebaixada Sombra (⚠️) → Excluída (❌)
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

Documentação completa: [rules.md](rules.md). Bayesian: [bayesian.md](bayesian.md).

## Integração com Claude Code

Este projeto também funciona como uma **habilidade do Claude Code**. O Claude cuida de:

1. **Busca**: dados de classificação, lesões, xG, odds
2. **Julgamento qualitativo**: ⑥ contaminação de dados, ⑦ impacto de lesões, ⑫ confronto tático, ⑲ conluio
3. **Preencher o JSON**: popular `match.json` com os resultados da busca
4. **Executar o motor**: `python engine/predictor.py -i match.json`
5. **Interpretar a saída**: traduzir JSON em um relatório de previsão em linguagem natural

O motor cuida de todo o cálculo determinista. O Claude cuida da busca e do julgamento — cada um fazendo o que faz de melhor.

See [SKILL.md](SKILL.md).

## Atualização Bayesiana

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

## Backtesting

```bash
python engine/backtest.py --matches backtest_matches.json
```

## Divisão de Trabalho: Engine vs. Claude

| | Engine (Python) | Claude |
|---|---|---|
| Compute `GF × coeff + Σ(γ×δ)` | ✅ | — |
| **Busca**: dados de classificação, lesões, xG, odds | — | ✅ |
| **Julgamento qualitativo**: ⑥ contaminação de dados, ⑦ impacto de lesões, ⑫ confronto tático, ⑲ conluio | — | ✅ |
| Apply rule lifecycle state machine | ✅ | — |
| Run 60-match backtest in 10 seconds | ✅ | — |
| **Interpretar a saída**: traduzir JSON em um relatório de previsão em linguagem natural | — | ✅ |

## Licença

MIT

## Contribuições

Issues and PRs welcome.
