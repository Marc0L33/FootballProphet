# Prophet v1.1.0 — Motor de Previsão de Partidas de Futebol

> [:us: English](../README.md) · [:cn: 中文](README_CN.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

Um motor de previsão de resultados de futebol baseado em regras com **saída de pontuação dupla** (metodologia + ajuste de mercado), **confiança 3D** e um **frontend web** para navegação de partidas em lote.

Aplica-se a: **Copa do Mundo, torneios continentais, ligas nacionais, copas, Champions League** — mesmo fluxo de trabalho, fontes de dados diferentes.

> Precisão direcional ~67%, placar exato ~22%. Calibrado em 72 partidas da Copa do Mundo de 2026 (incluindo todas as 18 partidas da MD3 dos Grupos D–L).

## Início Rápido

```bash
# 1. Prepare um arquivo de entrada (veja test/spain_uruguay.json para o modelo completo)
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

# 2. Execute o motor (partida única)
python3 engine/predictor.py -i match.json

# 3. Modo lote — processa todas as partidas em um diretório
python3 engine/predictor.py --input output/predictions/ --out-dir output/web/

# 4. Inicie o frontend web
cd output/web && python3 -m http.server 8080
```

## Instalação

```bash
git clone https://github.com/marcolee/prophet.git
cd prophet
# Dependências: apenas biblioteca padrão Python 3.8+. Não requer pip install.
python3 engine/predictor.py -i test/spain_uruguay.json
```

## Estrutura do Projeto

```
prophet/
├── README.md                       # Inglês (este arquivo)
├── i18n/                           # READMEs multilíngues
│   ├── README_CN.md                # 中文
│   ├── README_ES.md                # Español
│   ├── README_PT.md                # Português
│   ├── README_JA.md                # 日本語
│   ├── README_TH.md                # ไทย
│   ├── README_RU.md                # Русский
│   └── README_AR.md                # العربية
├── SKILL.md                        # Ponto de entrada da skill do Claude Code
├── rules.md                        # Documentação legível das regras
├── bayesian.md                     # Metodologia bayesiana
├── ledger.md                       # Registro de 72 partidas + retrospectivas
├── data/
│   ├── rules.json                  # 20 regras (lidas pelo motor)
│   └── teams.json                  # GF/GA base das equipes (auditado v1.2)
├── engine/
│   ├── predictor.py                # Motor de previsão principal
│   ├── bayesian.py                 # Atualizador de parâmetros bayesianos
│   └── backtest.py                 # Ferramenta de backtest em lote
├── test/
│   ├── egypt_iran.json             # Exemplo mínimo
│   └── spain_uruguay.json          # Entrada de teste com todas as regras
├── output/
│   ├── match_input_template.json   # Modelo de entrada
│   ├── predictions/                # JSONs de entrada das partidas
│   └── web/                        # Frontend + JSONs de saída
│       ├── index.html              # Navegador multi-partida (navegação ← →)
│       └── *.json                  # Arquivos de saída previstos
└── docs/
```

## Duas Pontuações, Dois Propósitos

O motor produz **duas pontuações lado a lado** com papéis distintos:

| | Pontuação Metodológica | Pontuação Ajustada ao Mercado |
|---|---|---|
| **Fonte** | Fórmula pura (⑭+②+Σγδ) | Fórmula + sinais de mercado |
| **Reprodutibilidade** | ✅ Determinista | ❌ Requer julgamento qualitativo |
| **Uso** | Linha de base; detectar desvio metodológico | Referência prática para apostas |
| **Distribuição** | Compartilha λ metodológico | Mesmo λ, placar arredondado diferente |

Quando as duas pontuações divergem, o mercado sabe algo que a metodologia não sabe — lesões, moral, conluio — mas a distribuição metodológica permanece ancorada na realidade do futebol.

## Fórmula de Previsão

```
Goals_A = r14_blend_GF × r02_opponent_coeff + Σ(triggered_rule_i × γ_i × δ_i)
Goals_B = same, symmetrically
Final Score = (round(Goals_A), round(Goals_B))
```

## Sistema de Regras (20 regras)

Vinte regras em cadeia de prioridade. Ciclo de vida de quatro estados: `🆕 Shadow → 🔵 Active → ⚠️ Demoted → ❌ Deleted`

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

Documentação completa: [rules.md](../rules.md) · [bayesian.md](../bayesian.md) · [ledger.md](../ledger.md).

### Principais Regras da v1.1.0

| Regra | O que faz | Por quê |
|------|-------------|-----|
| ㉑ Bench Strength | Compensa totalmente a penalidade r16 quando banco ≥ 0.7 | Era 5 substituições: estrelas "poupadas" jogam 30 min |
| ⑳ Rain | -0.25 λ por equipe em chuva persistente | Jogos com chuva da Inglaterra: 0-0 vs Gana, 2-0 vs Panamá |
| ⑲ Sem empilhamento | `draw_both_advance=true` → sem adjust_total extra | Croácia-Gana: metodologia 2-1 exato, mercado 0-0 errado |

## Integração com Claude Code (SKILL.md)

Este projeto também é uma **skill do Claude Code**. O fluxo de trabalho:

```
Busca (dados de classificação, lesões, xG, clima, odds de apostas)
  → Auditoria de dados (⑥ lavagem, verificação cruzada, divisão de rodada AFC)
  → Julgamento qualitativo (⑦ ausência, ⑫ tático, ⑲ conluio)
  → 🔴 Extrair sinais de mercado (obrigatório, nunca deixar vazio)
  → Preencher match.json → Executar motor → Gerar pontuação dupla
```

Mandatos principais no SKILL.md:
- **Prioridade de fontes chinesas** para escalações, placares, cartões (懂球帝/虎扑/直播吧)
- **Previsão do tempo** deve ser verificada antes da partida (aciona ⑳)
- **Sinais de mercado** não podem estar vazios quando existem dados de odds
- **Empilhamento ⑲ + adjust_total proibido** (bug de tripla contagem verificado por Croácia-Gana)

Veja [SKILL.md](../SKILL.md) para o fluxo de trabalho completo.

## Motor vs. Claude

| | Motor (Python) | Claude |
|---|---|---|
| Calcular fórmula + aplicar regras | ✅ | — |
| Buscar lesões, escalações, clima | — | ✅ |
| Detectar contaminação de dados (⑥) | — | ✅ |
| Extração de sinais de mercado | — | ✅ |
| Backtest em lote de 72 partidas | ✅ | — |
| Interpretar odds e sinais qualitativos | — | ✅ |

## Frontend Web

`output/web/index.html` — visualizador de partidas em lote com arrastar e soltar:
- Carregar múltiplos JSONs de previsão
- Navegação por teclado ← → entre partidas
- Exibição de pontuação dupla (metodologia | ajuste de mercado)
- Distribuições de probabilidade de gols por equipe com gráficos de barras
- Barras de probabilidade conjunta vitória/empate/derrota
- Transparência do ajuste de mercado

```bash
cd output/web && python3 -m http.server 8080
# Abra http://localhost:8080
```

## Retrospectiva MD3 JKL (v1.1.0)

| Partida | Metodologia | Real | Nota |
|-------|-----------|------|------|
| Croácia vs Gana | **2-1** ✅ | 2-1 | Acerto exato |
| RD Congo vs Uzbequistão | **2-1** ✅ | 3-1 | Gol tardio, caso contrário exato |
| Panamá vs Inglaterra | 0-3 | 0-2 | Chuva + baixa motivação (⑳) |
| Colômbia vs Portugal | 2-2 | 0-0 | VAR impedimento, ambos cautelosos |
| Jordânia vs Argentina | 1-2 | 1-3 | Pênalti +1; ㉑ retorno do banco |
| Argélia vs Áustria | 0-1 | 3-3 | ⑲ conluio quebrou após primeiro gol |

Direção: 4/6 (67%). Exato: 2/6 (33%). Registro: 12/18 direção no total.

## Licença

MIT

## Contribuições

Bem-vindas para: propostas de novas regras (com dados de backtest), atualizações de dados de equipes, calibração de coeficientes, melhorias no fluxo de trabalho da skill do Claude Code.
