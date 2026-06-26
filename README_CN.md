# Prophet v1.0.0 — 足球比分预测引擎

> [:us: English](README.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

基于规则的足球比赛比分预测引擎，支持**纯方法论输出**和**市场信号修正**双比分输出。

适用赛事：**世界杯、洲际杯、联赛（英超/西甲等）、杯赛（欧冠/足总杯等）**——流程相同，仅数据源不同。

> 方向准确率目标 ~70%，精确比分准确率 ~20%。方法论基于 60+ 场 2026 世界杯回测校准。

## 快速开始

```bash
# 1. 准备输入文件 (JSON)
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

# 2. 运行预测
python engine/predictor.py --input match.json

# 3. 输出
# ============================================================
# Prophet v1.0.0 — Spain vs Uruguay
# ============================================================
#    Methodology Score:  2 - 0 (home)
#    Market-Adjusted:    2 - 0 (home)
#    Confidence:         ⭐⭐⭐⭐ high
```

## 安装

```bash
git clone https://github.com/yourusername/prophet.git
cd prophet
# 依赖: 仅 Python 3.8+ 标准库
python engine/predictor.py --input test/egypt_iran.json
```

## 项目结构

```
prophet/
├── README.md                     # 本文件
├── SKILL.md                      # Claude Code skill 入口
├── rules.md                      # 人类可读的规则文档
├── bayesian.md                   # 贝叶斯方法论说明
├── ledger.md                     # 历史赛果账本
├── data/
│   ├── rules.json                # 规则定义 (19条, 引擎读取)
│   └── teams.json                # 48队预选赛数据
├── engine/
│   ├── predictor.py              # 核心预测引擎
│   ├── bayesian.py               # 贝叶斯参数更新
│   └── backtest.py               # 批量回测工具
├── test/
│   └── egypt_iran.json           # 示例输入
└── output/
    └── predictions/              # 预测输出
```

## 两个比分

引擎输出**两个比分**，各有不同用途：

| | 方法论比分 | 市场修正比分 |
|---|---|---|
| **来源** | 纯公式计算 | 公式 + 市场信号 |
| **输入** | 预选赛 GF/GA + 规则 δ | + 赔率、水位、市场情绪 |
| **确定性** | ✅ 可复现 | ❌ 需定性判断 |
| **用途** | 基准线，检测方法论偏差 | 实战参考 |

当两个比分分歧较大时，说明市场知道方法论不知道的信息（伤停、战意、默契球）——此时应优先信任市场修正比分。

## 预测公式

```
进球_A = ⑭基线_GF × ②对手系数 + Σ(触发规则_i × γ_i × δ_i)
进球_B = 同上，对称计算
最终比分 = (round(进球_A), round(进球_B))
```

## 规则系统

19 条规则按优先级链排序，每条规则有四个生命周期状态：

```
影子准入(🆕) → 活跃(🔵) → 影子降级(⚠️) → 退出(❌)
```

| # | 规则 | E[γ] | δ | 状态 |
|---|------|------|-----|------|
| ⑤ | 结构性进攻无能 | 0.89 | -1.5 | 🔵 cap硬上限 |
| ⑩ | 开场进球 | 0.64 | +1.4 | 🔵 |
| ⑭ | 预选赛基准 | 0.78 | per team | 🔵 混合GF/GA |
| ⑫ | 战术对位 | 0.79 | ±0.5~1.5 | 🔵 |
| ⑯ | 战意衰减 | 0.55 | -1.5/-1.0 | 🔵 v1.0.0 激活 |
| ⑰ | 跨洲校准 | 0.50 | ×1.20 | 🆕 |
| ⑮ | 室内/恒温 | 0.50 | +0.25 | 🆕 |
| ⑱ | 补水暂停 | 0.50 | +0.15/+0.25 | 🆕 |
| ⑲ | 平局博弈 | 0.80 | -1.0(全局) | 🔵 v1.0.0 激活 |
| ⑬ | 极端天气 | 0.71 | -0.5 | 🔵 |
| ⑪ | GK超神≠防守 | 0.69 | — | 🔵 |
| ⑨ | 门将不可预测 | 0.75 | — | 🔵 |
| ⑧ | 精英防线 | 0.75 | -1.0 | 🔵 |
| ⑦ | 创造力缺阵 | 0.69 | -0.3~-1.2 | 🔵 |
| ⑥ | 数据污染 | 0.77 | 按级别 | 🔵 含鱼腩清洗 |
| ④ | 红牌风险 | 0.50 | +0.3 | ⚠️ 影子降级 |
| ② | 对手质量系数 | 0.69 | 0.60x~1.40x | 🔵 |
| ③ | 主场优势 | 0.70 | +0.4/+0.25 | 🔵 |
| ① | 不预测零封 | 0.72 | +0.5 | 🔵 |

完整规则文档见 [rules.md](rules.md)，贝叶斯方法论见 [bayesian.md](bayesian.md)。

## Claude Code 集成

本项目同时是 Claude Code 的 **prophet skill**。Claude 负责：

1. **搜索**：预选赛数据、伤停、xG、盘口
2. **定性判断**：⑥ 数据污染、⑦ 伤停影响、⑫ 战术对位、⑲ 平局博弈
3. **填写 JSON**：将搜索结果填入 `match.json`
4. **运行引擎**：`python engine/predictor.py -i match.json`
5. **解释输出**：将引擎输出翻译为自然语言预测报告

详见 [SKILL.md](SKILL.md)。

## 贝叶斯更新

赛后使用 `bayesian.py` 更新规则参数：

```bash
python engine/bayesian.py --result match_result.json --rules data/rules.json
```

输入格式见 [test/egypt_iran.json](test/egypt_iran.json) 中的 `rule_reviews` 部分。每条触发规则的 α/β/n 自动更新，E[γ] 重新计算，规则生命周期自动检查。

## 回测

```bash
python engine/backtest.py --matches backtest_matches.json
```

支持 JSON 数组或 JSONL 格式。输出方向准确率、精确比分率、分轮次统计。

## 数据源

引擎本身不含数据——数据由使用者（人或 Claude）搜索后填入输入 JSON。不同赛事的数据源不同：

| 赛事类型 | ⑭ "预选赛"等效数据 | 正赛数据 | 示例数据源 |
|---------|-------------------|---------|----------|
| **世界杯** | 预选赛 GF/GA | 小组赛已赛场次 | FIFA.com, FBref |
| **洲际杯** | 预选赛 + 近期热身赛 | 正赛已赛场次 | UEFA.com, CONMEBOL |
| **联赛** | 本赛季前 N 轮 GF/GA | 最近 5 轮 | WhoScored, Understat |
| **杯赛** | 国内联赛赛季数据 | 杯赛已赛轮次 | Soccerway, Transfermarkt |
| **欧冠** | 小组赛 + 国内联赛 | 淘汰赛已赛回合 | UEFA.com, Opta |

`data/teams.json` 当前存有 2026 世界杯 48 队数据——联赛/杯赛使用时需替换为对应赛事数据。

## 许可证

MIT

## 贡献

欢迎提交 Issue 和 PR，特别是：
- 新规则提案（附带回测数据）
- 预选赛数据更新
- 系数校准优化
- Claude Code skill 工作流改进
