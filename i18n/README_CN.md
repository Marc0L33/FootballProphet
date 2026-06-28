# Prophet v1.1.0 — 足球比分预测引擎

> [:us: English](../README.md) · [:es: Español](README_ES.md) · [:brazil: Português](README_PT.md) · [:jp: 日本語](README_JA.md) · [:th: ไทย](README_TH.md) · [:ru: Русский](README_RU.md) · [:sa: العربية](README_AR.md)

基于规则的足球比分预测引擎，**双比分输出**（方法论 + 市场修正），**3D 置信度**模块，**Web 前端**批量浏览。

适用赛事：**世界杯、洲际杯、联赛、杯赛、欧冠**——流程相同，仅数据源不同。

> 方向准确率 ~67%，精确比分 ~22%。基于 2026 世界杯 72 场比赛校准（含 D–L 组 MD3 全部 18 场）。

## 快速上手

```bash
# 1. 准备输入 JSON（完整模板见 test/spain_uruguay.json）
cat > match.json << 'EOF'
{
  "home_team": "南非", "away_team": "加拿大",
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
    "handicap": "加拿大 -0.75",
    "totals": "小 2.25",
    "signals": [{"type":"adjust_total","delta":-1,"reason":"小盘→沉闷淘汰赛"}]
  }
}
EOF

# 2. 单场预测
python3 engine/predictor.py -i match.json

# 3. 批量模式
python3 engine/predictor.py --input output/predictions/ --out-dir output/web/

# 4. 启动前端
cd output/web && python3 -m http.server 8080
```

## 安装

```bash
git clone https://github.com/marcolee/prophet.git
cd prophet
# 零依赖，Python 3.8+ 标准库即可
python3 engine/predictor.py -i test/spain_uruguay.json
```

## 项目结构

```
prophet/
├── README.md                       # 英文主文档
├── i18n/                           # 多语言 README
│   ├── README_CN.md                # 中文（本文件）
│   └── README_*.md                 # 其他 6 种语言
├── SKILL.md                        # Claude Code 技能入口
├── rules.md                        # 规则说明文档
├── bayesian.md                     # 贝叶斯方法论
├── ledger.md                       # 72 场历史账本 + 复盘
├── data/
│   ├── rules.json                  # 20 条规则定义
│   └── teams.json                  # 球队基线 GF/GA（v1.2 全量审计）
├── engine/
│   ├── predictor.py                # 核心预测引擎
│   ├── bayesian.py                 # 贝叶斯参数更新
│   └── backtest.py                 # 批量回测工具
├── test/
│   └── spain_uruguay.json          # 完整示例
├── output/
│   ├── predictions/                # 比赛输入 JSON
│   └── web/                        # 前端 + 输出 JSON
│       ├── index.html              # 多场翻页浏览器（← → 导航）
│       └── *.json                  # 预测结果
└── docs/
```

## 双比分，双用途

引擎输出**两个比分**，各司其职：

| | 方法论比分 | 市场修正比分 |
|---|---|---|
| **来源** | 纯公式计算（⑭+②+Σγδ） | 公式 + 市场信号 |
| **可复现** | ✅ 确定性 | ❌ 需定性判断 |
| **用途** | 基线；检测方法论漂移 | 实战参考 |
| **概率分布** | 方法论 λ | 同 λ，仅比分不同 |

两比分分歧时，市场知道方法论不知道的事——伤病、士气、默契球——但方法论分布仍扎根足球现实，不被市场污染。

## 预测公式

```
进球_A = ⑭混合_GF × ②对手系数 + Σ(触发规则_i × γ_i × δ_i)
进球_B = 同上，对称计算
最终比分 = (round(进球_A), round(进球_B))
```

## 规则体系（20 条）

四态生命周期：`🆕 影子准入 → 🔵 活跃 → ⚠️ 降级 → ❌ 删除`

| # | 规则 | E[γ] | δ | 状态 |
|---|------|------|-----|--------|
| ⑤ | 结构性进攻无能 | 0.89 | 硬上限 1 球 | 🔵 |
| ⑩ | 开场进球 | 0.64 | +1.4 | 🔵 |
| ⑭ | 预选赛基准混合 | 0.78 | 按队 | 🔵 |
| ⑫ | 战术对位 | 0.79 | ±0.5~1.5 | 🔵 |
| ⑯ | 战意衰减（A/B型） | 0.55 | -1.5/-1.0 | 🔵 |
| ㉑ | 板凳深度 | 0.60 | +100%/+25%×r16 | 🔵 5换时代 |
| ⑰ | 跨洲校准 | 0.50 | ×1.20 | 🆕 |
| ⑮ | 室内/恒温 | 0.50 | +0.25 | 🆕 |
| ⑱ | 补水暂停 | 0.50 | +0.15/+0.25 | 🆕 |
| ⑲ | 平局博弈 | 0.80 | -1.0 全局 | 🔵 禁叠加 adjust_total |
| ⑳ | 雨战 | 0.60 | -0.25/队 | 🔵 |
| ⑬ | 极端天气 | 0.71 | -0.5 | 🔵 暂停>30min |
| ⑪ | GK超神≠防守 | 0.69 | — | 🔵 |
| ⑨ | 门将不可预测 | 0.75 | — | 🔵 方法论边界 |
| ⑧ | 精英防线 | 0.75 | -1.0 | 🔵 |
| ⑦ | 创造力缺阵 | 0.69 | -0.3~-1.2 | 🔵 |
| ⑥ | 数据污染 | 0.77 | 按等级 | 🔵 |
| ④ | 红牌风险 | 0.50 | +0.3 | ⚠️ 影子降级 |
| ② | 对手质量系数 | 0.69 | 0.60x~1.40x | 🔵 |
| ③ | 主场优势 | 0.70 | +0.4/+0.25 | 🔵 东道主/移民准主场 |
| ① | 不预测零封 | 0.72 | +0.5 | 🔵 |

完整文档：[rules.md](../rules.md) · [bayesian.md](../bayesian.md) · [ledger.md](../ledger.md)。

### v1.1.0 新增规则

| 规则 | 作用 | 驱动 |
|------|------|------|
| ㉑ 板凳深度 | bench≥0.7 → 全额抵消 r16 惩罚 | 5换时代："轮休"主力后30分钟照上 |
| ⑳ 雨战 | 持续降雨 → 双方 λ -0.25 | 英格兰雨战 0-0 加纳、2-0 巴拿马 |
| ⑲ 禁止叠加 | draw_both_advance=true → 不加 adjust_total | 克罗地亚 2-1 精确命中，市场修正 0-0 翻车 |

## Claude Code 集成（SKILL.md）

本项目同时也是 **Claude Code 技能**。工作流：

```
搜索（预选赛、伤停、xG、天气、赔率）
  → 数据审计（⑥清洗、交叉验证、AFC分轮）
  → 定性判断（⑦缺阵、⑫战术、⑲默契球）
  → 🔴 提炼 market signals（必修，不可留空）
  → 填 match.json → 跑引擎 → 输出双比分
```

SKILL.md 核心规则：
- **中文源优先**：首发、赛果、比分查 懂球帝/虎扑/直播吧
- **赛前搜天气**：触发 ⑳ 雨战规则
- **market signals 不可空**：有盘口数据就必须提炼
- **⑲ 禁止叠加 adjust_total**：三重计数已验证翻车

详见 [SKILL.md](../SKILL.md)。

## 分工

| | 引擎 (Python) | Claude |
|---|---|---|
| 公式计算 + 应用规则 | ✅ | — |
| 搜索伤停/首发/天气 | — | ✅ |
| 数据污染检测 (⑥) | — | ✅ |
| 提炼市场信号 | — | ✅ |
| 批量回测 72 场 | ✅ | — |
| 解读赔率和定性信号 | — | ✅ |

## Web 前端

`output/web/index.html`——拖拽式批量比赛浏览器：
- 多文件拖拽上传
- ← → 键盘翻页
- 双比分并列显示（方法论 | 市场修正）
- 每队进球概率分布柱状图
- 胜/平/负联合概率条
- 市场调整透明展示

```bash
cd output/web && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## MD3 JKL 组复盘（v1.1.0）

| 比赛 | 方法论 | 实际 | 备注 |
|------|--------|------|------|
| 克罗地亚 vs 加纳 | **2-1** ✅ | 2-1 | 精确命中 |
| 刚果(金) vs 乌兹别克 | **2-1** ✅ | 3-1 | 末段再进，否则精确命中 |
| 巴拿马 vs 英格兰 | 0-3 | 0-2 | 雨战+无欲→少进 1 球（⑳） |
| 哥伦比亚 vs 葡萄牙 | 2-2 | 0-0 | VAR 越位，双方保守 |
| 约旦 vs 阿根廷 | 1-2 | 1-3 | 点球+1；㉑ 板凳回调生效 |
| 阿尔及利亚 vs 奥地利 | 0-1 | 3-3 | ⑲ 默契球被意外进球打破 |

方向：4/6 (67%)。精确：2/6 (33%)。全 18 场 MD3 方向 67%。

## 许可证

MIT

## 贡献

欢迎提交：新规则提案（附回测数据）、球队数据更新、系数校准改进、Claude Code 技能流程优化。
