# Prophet v1.1.0 — Motor de Predicción de Partidos de Fútbol

> [:us: English](../README.md) · [:cn: 中文](README_CN.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

Un motor de predicción de resultados de fútbol basado en reglas con **salida de doble puntuación** (metodología + ajuste de mercado), **confianza 3D** y un **frontend web** para navegación por lotes de partidos.

Aplica a: **Mundial, torneos continentales, ligas domésticas, copas, Champions League** — mismo flujo de trabajo, diferentes fuentes de datos.

> Precisión direccional ~67%, puntuación exacta ~22%. Calibrado en 72 partidos del Mundial 2026 (incluyendo los 18 partidos de MD3 de los Grupos D–L).

## Inicio Rápido

```bash
# 1. Preparar un archivo de entrada (plantilla completa en test/spain_uruguay.json)
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
    "signals": [{"type":"adjust_total","delta":-1,"reason":"U2.25 → partido cerrado de eliminatoria"}]
  }
}
EOF

# 2. Ejecutar el motor (partido individual)
python3 engine/predictor.py -i match.json

# 3. Modo por lotes — procesar todos los partidos en un directorio
python3 engine/predictor.py --input output/predictions/ --out-dir output/web/

# 4. Iniciar el frontend web
cd output/web && python3 -m http.server 8080
```

## Instalación

```bash
git clone https://github.com/marcolee/prophet.git
cd prophet
# Dependencias: solo biblioteca estándar de Python 3.8+. No se necesita pip install.
python3 engine/predictor.py -i test/spain_uruguay.json
```

## Estructura del Proyecto

```
prophet/
├── README.md                       # Inglés (archivo principal)
├── i18n/                           # READMEs multilingües
│   ├── README_CN.md                # 中文
│   ├── README_ES.md                # Español (este archivo)
│   ├── README_PT.md                # Português
│   ├── README_JA.md                # 日本語
│   ├── README_TH.md                # ไทย
│   ├── README_RU.md                # Русский
│   └── README_AR.md                # العربية
├── SKILL.md                        # Punto de entrada de la skill de Claude Code
├── rules.md                        # Documentación legible de las reglas
├── bayesian.md                     # Metodología bayesiana
├── ledger.md                       # Libro de 72 partidos + retrospectivas
├── data/
│   ├── rules.json                  # 20 reglas (el motor lee este archivo)
│   └── teams.json                  # GF/GA base por equipo (auditoría v1.2)
├── engine/
│   ├── predictor.py                # Motor de predicción principal
│   ├── bayesian.py                 # Actualizador de parámetros bayesianos
│   └── backtest.py                 # Herramienta de backtesting por lotes
├── test/
│   ├── egypt_iran.json             # Ejemplo mínimo
│   └── spain_uruguay.json          # Entrada de prueba con todas las reglas
├── output/
│   ├── match_input_template.json   # Plantilla de entrada
│   ├── predictions/                # JSONs de entrada de partidos
│   └── web/                        # Frontend + JSONs de salida
│       ├── index.html              # Navegador multi-partido (← → navegación)
│       └── *.json                  # Archivos de predicción generados
└── docs/
```

## Dos Puntuaciones, Dos Propósitos

El motor produce **dos puntuaciones lado a lado** con roles distintos:

| | Puntuación Metodológica | Puntuación Ajustada al Mercado |
|---|---|---|
| **Fuente** | Fórmula pura (⑭+②+Σγδ) | Fórmula + señales de mercado |
| **Reproducibilidad** | ✅ Determinista | ❌ Requiere juicio cualitativo |
| **Uso** | Línea base; detectar desviación metodológica | Referencia práctica para apuestas |
| **Distribución** | Comparte λ metodológica | Misma λ, puntuación redondeada distinta |

Cuando las dos puntuaciones divergen, el mercado sabe algo que la metodología no — lesiones, moral, colusión — pero la distribución metodológica permanece anclada en la realidad del fútbol.

## Fórmula de Predicción

```
Goals_A = r14_mezcla_GF × r02_coef_oponente + Σ(regla_disparada_i × γ_i × δ_i)
Goals_B = mismo cálculo, simétricamente
Puntuación Final = (round(Goals_A), round(Goals_B))
```

## Sistema de Reglas (20 reglas)

Veinte reglas en orden de cadena de prioridad. Ciclo de vida de cuatro estados: `🆕 Sombra → 🔵 Activa → ⚠️ Degradada → ❌ Eliminada`

| # | Regla | E[γ] | δ | Estado |
|---|------|------|-----|--------|
| ⑤ | Incapacidad Ofensiva | 0.89 | tope 1 gol | 🔵 |
| ⑩ | Gol Tempranero | 0.64 | +1.4 | 🔵 |
| ⑭ | Mezcla Base de Clasificación | 0.78 | por equipo | 🔵 GF/GA combinado |
| ⑫ | Enfrentamiento Táctico | 0.79 | ±0.5~1.5 | 🔵 |
| ⑯ | Decaimiento de Moral (A/B) | 0.55 | -1.5/-1.0 | 🔵 |
| ㉑ | Fondo de Banco | 0.60 | +100%/+25% × r16 | 🔵 era de 5 cambios |
| ⑰ | Calibración Intercontinental | 0.50 | ×1.20 | 🆕 |
| ⑮ | Interior/Clima Controlado | 0.50 | +0.25 | 🆕 |
| ⑱ | Pausa de Hidratación | 0.50 | +0.15/+0.25 | 🆕 |
| ⑲ | Colusión de Empate | 0.80 | -1.0 global | 🔵 prohibido apilar con adjust_total |
| ⑳ | Lluvia | 0.60 | -0.25 por equipo | 🔵 activa |
| ⑬ | Clima Extremo | 0.71 | -0.5 | 🔵 suspensión >30min |
| ⑪ | Heroísmo del Portero ≠ Defensa | 0.69 | — | 🔵 |
| ⑨ | Imprevisibilidad del Portero | 0.75 | — | 🔵 frontera |
| ⑧ | Defensa de Élite | 0.75 | -1.0 | 🔵 |
| ⑦ | Ausencia de Creatividad | 0.69 | -0.3~-1.2 | 🔵 |
| ⑥ | Contaminación de Datos | 0.77 | por nivel | 🔵 |
| ④ | Riesgo de Tarjeta Roja | 0.50 | +0.3 | ⚠️ degradada a sombra |
| ② | Coeficiente de Calidad del Oponente | 0.69 | 0.60x~1.40x | 🔵 |
| ③ | Ventaja Local | 0.70 | +0.4/+0.25 | 🔵 anfitrión/diáspora |
| ① | No se Predice Portería a Cero | 0.72 | +0.5 | 🔵 |

Documentación completa: [rules.md](../rules.md) · [bayesian.md](../bayesian.md) · [ledger.md](../ledger.md).

### Reglas Clave de v1.1.0

| Regla | Qué hace | Por qué |
|------|-------------|-----|
| ㉑ Fondo de Banco | Compensa totalmente la penalización r16 cuando banco ≥ 0.7 | Era de 5 cambios: las estrellas "descansadas" juegan 30 min |
| ⑳ Lluvia | -0.25 por equipo λ en lluvia persistente | Partidos con lluvia de Inglaterra: 0-0 vs Ghana, 2-0 vs Panamá |
| ⑲ Sin apilamiento | `draw_both_advance=true` → sin adjust_total adicional | Croacia-Ghana: metodología 2-1 exacto, mercado 0-0 falló |

## Integración con Claude Code (SKILL.md)

Este proyecto también es una **skill de Claude Code**. El flujo de trabajo:

```
Búsqueda (datos de clasificación, lesiones, xG, clima, cuotas)
  → Auditoría de datos (⑥ limpieza, verificación cruzada, división por rondas AFC)
  → Juicio cualitativo (⑦ ausencia, ⑫ táctico, ⑲ colusión)
  → 🔴 Extraer señales de mercado (obligatorio, nunca dejar vacío)
  → Rellenar match.json → Ejecutar motor → Salida de doble puntuación
```

Directrices clave en SKILL.md:
- **Prioridad de fuentes en chino** para alineaciones, resultados, tarjetas (懂球帝/虎扑/直播吧)
- **Pronóstico del clima** debe consultarse antes del partido (activa ⑳)
- **Las señales de mercado** no deben estar vacías cuando existen datos de cuotas
- **⑲ + adjust_total prohibido apilar** (bug de triple conteo verificado con Croacia-Ghana)

Ver [SKILL.md](../SKILL.md) para el flujo de trabajo completo.

## Motor vs. Claude

| | Motor (Python) | Claude |
|---|---|---|
| Calcular fórmula + aplicar reglas | ✅ | — |
| Buscar lesiones, alineaciones, clima | — | ✅ |
| Detectar contaminación de datos (⑥) | — | ✅ |
| Extracción de señales de mercado | — | ✅ |
| Backtesting por lotes de 72 partidos | ✅ | — |
| Interpretar cuotas y señales cualitativas | — | ✅ |

## Frontend Web

`output/web/index.html` — visor de partidos por lotes con arrastrar y soltar:
- Subir múltiples JSONs de predicción
- Navegación por teclado ← → entre partidos
- Visualización de doble puntuación (metodología | ajuste de mercado)
- Distribuciones de probabilidad de goles por equipo con gráficos de barras
- Barras de probabilidad conjunta de victoria/empate/derrota
- Transparencia del ajuste de mercado

```bash
cd output/web && python3 -m http.server 8080
# Abrir http://localhost:8080
```

## Retrospectiva MD3 JKL (v1.1.0)

| Partido | Metodología | Real | Nota |
|-------|-----------|--------|------|
| Croacia vs Ghana | **2-1** ✅ | 2-1 | Acierto exacto |
| RD Congo vs Uzbekistán | **2-1** ✅ | 3-1 | Gol tardío, de lo contrario exacto |
| Panamá vs Inglaterra | 0-3 | 0-2 | Lluvia + baja motivación (⑳) |
| Colombia vs Portugal | 2-2 | 0-0 | VAR fuera de juego, ambos cautelosos |
| Jordania vs Argentina | 1-2 | 1-3 | Penalti +1; ㉑ fondo de banco aplicado |
| Argelia vs Austria | 0-1 | 3-3 | ⑲ colusión rota tras el primer gol |

Dirección: 4/6 (67%). Exacto: 2/6 (33%). Libro: 12/18 en dirección general.

## Licencia

MIT

## Contribuciones

Bienvenidas: propuestas de nuevas reglas (con datos de backtesting), actualizaciones de datos de equipos, calibración de coeficientes, mejoras en el flujo de la skill de Claude Code.
