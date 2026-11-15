---
name: 清算ABS多行工作台聚合展示
version: 1.0.0
display_name: 清算ABS多行工作台聚合展示
display_name_en: NPL ABS Multi-Deal Workbench Builder
description_zh: 把逐单清算期不良 ABS 报告聚合成一个 N 单「策略与投资人回报」单文件工作台。含逐单输出契约、行数据字典、切片与 Ctrl 多选、银行×品种矩阵、四象限定位、现金流分配板、报告查看器、导出与打印；配输入指纹、行数据 SHA256、字节级 G1 与数据/交互 G2/G3 门禁，参考实现 74 单 5 家银行 13 张 ECharts。
description_en: Aggregates per-deal NPL ABS reports into a single-file N-deal workbench for strategy and investor returns. Includes the per-deal output contract, row data dictionary, slicers and multi-select, bank-by-product matrix, four-quadrant positioning, cash-flow distribution board, report viewer, export and print, with input fingerprints, row SHA256, byte-level G1 and data/interaction G2/G3 gates. Reference build: 74 deals, 5 banks, 13 ECharts.
description: 【1.0 / 2026-11-06】把逐单清算期不良ABS报告聚合成 N 单「策略与投资人回报」工作台（参考实现 V9：74 单、5 家银行、13 张 ECharts + 1 个 HTML 现金流分配板）。覆盖逐单输出契约、74 行数据字典、切片/Ctrl 多选、银行×品种矩阵、四象限、现金流账本横条、报告查看器、导出/打印/夜盘、版本留档；含输入指纹、行数据 SHA256、产物字节级 G1、数据/交互 G2/G3 门禁与零到一复刻脚本。当用户提到多行工作台、ABS 聚合展示、策略与投资人回报、跨单对比、切片联动、现金流去向、哈希门禁、V9 工作台时使用。单项目八节报告请用「清算ABS项目汇报分析4.0」。
---

# 清算ABS多行工作台聚合展示 · 1.0

> **定位：第二技能。** 第一技能负责“一个项目 → 一份八节 HTML”；本技能负责“已经验收的 N 个项目 → 一个可复刻的多行工作台”。
>
> 参考实现：**V9**，74 单 / 5 家银行 / 14 个视觉图（13 张 ECharts + 1 个 HTML 现金流分配板）。
> V9 字节基线：**11,385,763 B**，SHA256 **`8ae21fd0266387ae9fde9b00ceecf432bcac4ed864eaf7a1e2e11a680d037593`**。

---

## 0. 先判断：这是不是本技能

| 用户要做的事 | 用哪个技能 |
|---|---|
| 从 PDF 做**一个项目**的穿透报告 | 第一技能 `清算ABS项目汇报分析4.0` |
| 把多个项目做成**横向对照 / 工作台** | **本技能** |
| 改 V9 的图、切片、布局、现金流板 | **本技能** |
| 改单项目八节报告、取数、断言 | 第一技能 |

**铁律：本技能不重新解析 PDF，不改单项目数值。** 单项目没有过 G1/G2/G3，本技能拒绝聚合。

---

## 1. 30 秒上手

```bash
# 1) 重建 V9（从本包基线 + 源 + 74 行）
python -X utf8 scripts/build_workbench.py --check

# 2) 一键门禁（G1 字节 + G2 结构/数据 + G3 交互）
python -X utf8 scripts/gate.py --html dist/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html

# 3) 看产物
#    dist/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html
#    11,385,763 B / SHA256 8ae21fd0…
```

预期：

| 项 | 值 |
|---|---|
| 大小 | **11,385,763 B** |
| SHA256 | **`8ae21fd0266387ae9fde9b00ceecf432bcac4ed864eaf7a1e2e11a680d037593`** |
| V3_FULL | 74 行 |
| REPORTS | 74 份单项目报告 |
| ECharts | 13 张 |
| HTML 现金流分配板 | 1 个，8 行 |
| `__v3cashflowParsed` | 74 |
| KPI 初始 | 74 单 |
| JS 错误 | 0 |

---

## 2. 交付物长什么样

单文件 HTML，离线双击可开；左侧固定侧栏 + 顶栏筛选 + 8 个对比区块 + 5 家银行页 + 74 单明细 + 报告查看器。

```
一、各行对比
   01 总览与核心结论
   02 处置策略地图
   03 投资人：优先级 vs 次级
   04 预测 vs 实际回收
   05 资产质量结构
   06 品种·存续期·证券化率
   07 发行节奏与品种结构
   08 技能与口径
二、分银行项目
   中信 15 / 招商 18 / 建设 17 / 兴业 10 / 农业银行 14
三、逐单
   74 单明细（点击行 → 完整报告，可返回）
```

### 74 单构成（事实基线）

| 银行 | 单数 | 品种 |
|---|---:|---|
| 中信银行 | 15 | 信用卡 15 |
| 招商银行 | 18 | 信用卡 18 |
| 建设银行 | 17 | 信用卡 9 / 个人消费 4 / 住房抵押 4 |
| 兴业银行 | 10 | 信用卡 10 |
| 农业银行 | 14 | 个人经营 12 / 信用卡 2 |
| **合计** | **74** | 信用卡 54 / 个人经营 12 / 个人消费 4 / 住房抵押 4 |

状态：**70 已清算 / 4 存续**。回购：**61 有 / 13 无**。
数据限制：预测机构、评级字段未入库；小微 7 单剔除出零售对比口径；4 单存续；不要把回购价款重复计入回收。

---

## 3. 本包目录

```text
清算ABS多行工作台聚合展示/
├── SKILL.md
├── README.md
├── references/
│   ├── 00-零到一复刻手册.md
│   ├── 01-输入输出契约与行数据字典.md
│   ├── 02-聚合口径与现金流解析.md
│   ├── 03-V9架构与交互.md
│   ├── 04-图表版式与视觉规范.md
│   ├── 05-哈希门禁与验收.md
│   ├── 06-版本发布与故障排查.md
│   └── 07-反模式与门禁盲区.md
├── assets/
│   ├── workbench/不良ABS..._V9.html      参考产物 / 重建基线
│   ├── source/v3.js / v3.css / …          V3 层源码
│   ├── data/_rows_all.json               74 行 canonical
│   ├── data/_rows.json                   旧 67 行（仅供对照）
│   ├── docs/README_工作台说明.md
│   ├── docs/工作台_版本索引.md
│   └── golden/hashes.json                参考哈希
├── scripts/
│   ├── build_workbench.py                重建 V9（字节级）
│   ├── inject_v3.py                      注入器（唯一构建实现）
│   ├── aggregate_rows.py                 单项目目录 → 行数据
│   ├── gate.py                           G1+G2+G3
│   ├── verify_workbench.py               Playwright 交互门禁
│   └── hash_manifest.py                  清单/哈希生成
├── tests/                                 G3 说明（门禁在 scripts/gate.py）
├── templates/                             行 schema / 交付清单模板
└── dist/                                  输出目录
```

---

## 4. 不可违反的六条

1. **单项目先验收。** 单项目 FAIL≠0 或 SKIP 未解释，不进入工作台。
2. **输入先指纹。** 构建前校验 `_rows_all.json`、V3 源、ECharts、V9 基线的 SHA256；输入变了，先用 `--force` 说明原因并留痕。
3. **产物必须字节级可复刻。** 输出哈希必须等于 V9 基线；不等就查源/换行/顺序，不要手改产物。
4. **不静默补数。** 缺字段保留 `null`/空态；不得用其他项目、0、均值或“看起来合理”的值填补。
5. **不跨项目借现金流。** 现金流/回购只从本项目报告解析；缺矩阵就 0 行，不用邻单兜底。
6. **版本不覆盖。** V1→V9 全部留档，主文件只做最新版别名；每次发布更新版本索引和 SHA256。

---

## 5. 输入契约（单项目产出侧）

每个项目目录至少：

```text
<项目>/
├── 02_提取数据/
│   ├── metrics.json          ★ 指标主源
│   └── payload.json          ★ 元信息 / 资产池 / 分档 / 期次
├── 03_报告产出/
│   ├── <项目>_不良ABS穿透分析_v*.html  ★ 报告正文（查看器 + 现金流/回购解析）
│   └── _assert_single.json   ★ 单项目断言结果
└── 01_下载文档/               原始 PDF（工作台不读，归档）
```

本技能只需要 `metrics.json` / `payload.json` / 报告 HTML 三件；PDF 不参与聚合。
缺报告 HTML：报告查看器为空，现金流/回购 0，不得拿别单兜底。

### 74 行字段（canonical）

`bank, proj, variety, issue_date, legal, term, state, life, issue, pool, sec_rate, sub_pct, coupon, recovery, exp, achieve, dispose, servicer, fee, sen_xirr, sub_xirr, mult, n_loans, n_bor, avg_loan, wavg_od, sub_bal, doubt, loss, sub_amt, doubt_amt, loss_amt, recovered, sen_issue, sub_issue, line, year, fails, skips`

公式：

- `sec_rate = issue / pool`
- `sub_pct = sub_issue / issue`
- `recovery = recovered / pool`
- `exp = recovered / achieve / pool`（不得由回收率反推后冒充披露值）
- `achieve = recovery / exp`（金额 ÷ 金额）
- `dispose = 已报销处置费用 / 累计回收`
- `mult = Σ次级现金分配 / 次级实际认购金额`
- `life`：已清算 = 终止−发行；存续 = 报告期末−发行（月）

完整字段、单位、允许缺失项 → `references/01` 与 `references/02`。

---

## 6. 聚合 ETL

### 6.1 单项目 → 行

```bash
python -X utf8 scripts/aggregate_rows.py --projects-root "<项目根>" \
  --canonical assets/data/_rows_all.json \
  --out dist/_rows_all.json
```

逻辑：

1. 扫描 `<项目根>/*/02_提取数据/metrics.json`；
2. 从 `metrics`/`payload` 映射核心字段；
3. 用 canonical 行补齐资产质量余额、`state`、`fails/skips` 等非 metrics 字段；
4. 校验 74/5/70/4、唯一键、日期、值域、`exp/recovery/achieve` 闭合；
5. 按 `issue_date` 升序，输出稳定 JSON（`indent=2, sort_keys=True, newline="\n"`）+ SHA256。

`--check` 只校验不写；`--strict` 缺字段即失败。
桥接单行也可用第一技能的 `scripts/export_workbench_row.py`。

### 6.2 行 + 报告 → V3_FULL / REPORTS

V9 的两块数据：

- `V3_FULL`：74 行全字段（本包 `_rows_all.json`）；
- `REPORTS`：74 份报告 HTML（从单项目 `03_报告产出/*.html` 汇总；本包 V9 已内嵌，源码可替换）。

**现金流解析**只在 `REPORTS` 上做：

```js
/<tr data-label="([^"]*)" data-cum="([^"]*)"[^>]*>([\s\S]*?)<\/tr>/g
```

`data-label` 以“优先档/次级档”开头 → 对应档；`class="l"` 第二列 = “费用” → 费用；其余 → 其他。
**回购**：`是否回购(?:[^是|否]{0,24})(是|否)` → `yes/no`；无匹配留空。
**现金流解析 74/74**；不得跨项目兜底；构建期断言日期属于本单发行日 / 支付日。

---

## 7. V9 架构

```text
基础工作台 HTML（含 META / REPORTS / SLICE_ROWS / 原有视图）
  + V3_STYLE  (v3.css + v3-extra.css + v3-gold.css)
  + V3_LIB    (echarts.min.js)
  + V3_DATA   (V3_FULL = 74 行)
  + V3_APP    (v3.js)
  → 单文件 V9 HTML
```

唯一构建入口：`scripts/inject_v3.py`；`build_workbench.py` 调它并做哈希门禁。
**不要直接改 V9 HTML 后当源码。** 改图/交互只改 `assets/source/`，重建。

### 页面区域

| 区域 | 内容 |
|---|---|
| 顶栏 | 切片、Ctrl/⌘ 多选、播放、导出、打印、夜盘、切片链接 |
| 概览 | KPI、结论、银行×品种矩阵 + 中位数计分卡（并排） |
| s2 | 银行资产池表；资产池×预计回收率 + 回收率×处置费率（并排） |
| s3 | 票面 vs XIRR + 优先×次级（并排）；次级厚度 + Top/Bottom（并排）；现金流去向（HTML 通栏）；各行次级表 |
| s4 | 预测×实际 + 回收率分布（并排）；银行预测偏差表（通栏） |
| s5 | 资产质量按银行 + 按品种（并排） |
| s6 | 品种·证券化率·存续期 |
| s7 | 发行规模 + 年度表（并排）；银行×品种表（通栏） |
| s8 | 技能原则 / 哈希门禁 / 口径 |

### 交互

- 普通点击切片 = 单选；`Ctrl/⌘` 点击 = 多选/取消；再次点同项取消；
- 全部 14 张图跟随 `window.__slice`（品种/年份/期限/证券化率/达成率/状态/回购）；
- 银行×品种矩阵：点格子 → 银行页 + 品种切片；
- 气泡图：按银行配色，悬停只保留该银行；6 张气泡图带横/纵中位虚线四象限；
- 现金流 HTML 板：点横条 → 银行 + 品种；
- 报告查看器：点气泡/项目卡/明细行打开单项目 HTML，返回不丢切片；
- URL 保存切片；CSV / PNG / PDF / 打印 / 夜盘 / 分享链接。

细节 → `references/03`。

---

## 8. 图表与版式

14 个视觉图 = 13 个 ECharts + 1 个 HTML 现金流分配板。
**13 张 ECharts 清单**：策略、计分卡、票面 dumbbell、优先×次级、次级厚度、预测、分布、资产质量×银行、资产质量×品种、证券化率×存续期、发行、银行×品种矩阵、资产池×预计回收率。
**HTML 板**：现金流去向，4 个资金平衡指标 + 图例 + 银行分组 + 100% 横条 + 右侧金额/单数。

视觉纪律：

- 主题：墨蓝 / 香槟金 / 封包红 / 暖灰；纸面米白；银行色固定（中信蓝、招商金、建设绿、兴业紫、农行红）；
- 气泡图四象限：横/纵中位虚线 + “中位 …”标签；优先×次级保留 `次级 IRR=0`；预测图保留 `y=x`；
- 双列：6 组 `.v3-pair`；桌面 `1fr 1fr`，≤900px 单列；
- 卡片间距：统一 **14px**；s3 现金流板与上方网格不得贴住；
- 横条：s5 与现金流板同一套平涂/圆角/背景轨道/字号；
- 现金流板参考「资金平衡 / 分配瀑布 / 多账户勾稽」的账本横条，不用高饱和渐变；
- 报告页 iframe 注入主题，隐藏重复顶栏；夜盘保持暖纸图表。

细节 → `references/04`。

---

## 9. 哈希门禁（交付前必须全绿）

### G0 · 输入指纹

```bash
python -X utf8 scripts/hash_manifest.py --check
```

- `_rows_all.json` SHA256；
- `v3.js` / 三份 CSS / `echarts.min.js` SHA256；
- `assets/workbench/..._V9.html` 基线 SHA256；
- 任何不一致：先查是不是有意改版；无事由不得继续。

### G1 · 产物字节级

```bash
python -X utf8 scripts/build_workbench.py --check
```

- 输出 11,385,763 B；
- SHA256 = `8ae21fd0266387ae9fde9b00ceecf432bcac4ed864eaf7a1e2e11a680d037593`；
- **唯一允许失败的原因**：有意改版且已更新 golden；否则视为回归。

### G2 · 数据/结构

```bash
python -X utf8 scripts/gate.py --html "<产物>" --static-only
```

- `V3_FULL = 74`；`REPORTS = 74`；5 家银行；70 settled / 4 open；
- 13 张 ECharts + 1 HTML 板；`.cf-row=8`；`__v3cashflowParsed=74`；
- 14 个图卡/图容器存在；6 组 `.v3-pair`；卡片间距 14px；
- 74 行无重复 `proj`、无 NaN、日期序、`exp≈recovery/achieve`；
- 61/13 回购解析；4 单存续。

### G3 · 交互

```bash
python -X utf8 scripts/gate.py --html "<产物>"
```

- 0 pageerror / console error；
- 初始 KPI=74；切片信用卡 KPI=54；清除回 74；
- Ctrl/⌘ 多选；银行页；矩阵格子；现金流行点击；报告查看器开/关；返回不丢切片；
- 6 张气泡图各有横/纵中位 markLine；
- 移动端 390px 无横向溢出；打印/PDF 可出。

**任一 G 失败 = 不交付。** 失败定位 → `references/05`、`references/06`。

---

## 10. 零到一复刻（任意智能体）

```bash
# 0) 环境
python 3.12 + Microsoft Edge + 微软雅黑 UI；Playwright（仅 G3）
pip install playwright && playwright install msedge

# 1) 校验本包
python -X utf8 scripts/hash_manifest.py --check

# 2) 重建
python -X utf8 scripts/build_workbench.py --check
# 期望 V9 哈希

# 3) 门禁
python -X utf8 scripts/gate.py --html dist/不良ABS..._V9.html

# 4) 换成自己的 74 个项目
python -X utf8 scripts/aggregate_rows.py --projects-root "<根>" --canonical assets/data/_rows_all.json --out dist/_rows_all.json
python -X utf8 scripts/aggregate_rows.py --check --rows dist/_rows_all.json
# 注意：替换数据集同时要重建基础壳的 META/REPORTS/SLICE_ROWS；
# 本包 V9 可作为参考壳，详细边界见 references/00 第 6 节。

# 5) 发布
python -X utf8 scripts/hash_manifest.py --write
# 更新 工作台_版本索引.md，V10、V11… 不覆盖
```

**完整版步骤、检查点、15 个常见失败** → `references/00` / `references/06`。

---

## 11. 数据口径与已知边界

- 预测回收率：`实际回收 ÷ 达成率`；`exp` 只作展示，不在工作台冒充披露值。
- 资产池表按银行聚合，气泡/散点是单项目；两者不要混读。
- 现金流分配板：来自单项目报告「存续期分配明细矩阵」累计金额；费用含税费/处置费/服务费/中介等；其他含发行费/其他费用。
- 回购：61 有 / 13 无；由报告正文解析，不是结构化字段。
- 预测机构/评级：未入库，不造切片；筛选条已注明。
- 4 单存续：建鑫 2021 四、2021 七、2023 四、2023 七；次级倍数可能为 `—` 或低值，按已实现现金口径，不得补 1.0。
- 建设小微 7 单剔除出零售对比；工作台 74 单不是建鑫 24 单全量。
- 中信“达成偏低”：跨行 `life×achieve r≈-0.04`，同一信用卡 `r≈+0.66`、中信自身 `r≈+0.55`；提前退出是部分原因，不是全部。V9 已写入页面，改文案时保留这个口径。

---

## 12. 版本与交付

- 本技能版本 **1.0**（2026-11-06）；参考工作台 **V9**。
- 旧工作台 V1–V9 保留；主文件只是最新别名；每次发布会更新 `工作台_版本索引.md`。
- 交付必须附：
  1. 工作台 HTML + SHA256 + 字节数；
  2. `_rows_all.json` + SHA256；
  3. G0/G1/G2/G3 结果；
  4. 版本号、日期、变更记录；
  5. 数据限制和未完成项。

---

## 13. 参考文件

| 文件 | 何时读 |
|---|---|
| `references/00-零到一复刻手册.md` | 第一次开工，按步骤照做 |
| `references/01-输入输出契约与行数据字典.md` | 接新项目、字段映射、缺失处理 |
| `references/02-聚合口径与现金流解析.md` | 算指标、解析报告、回购/现金流 |
| `references/03-V9架构与交互.md` | 改页面、切片、查看器、导出 |
| `references/04-图表版式与视觉规范.md` | 改图、配色、双列、间距、打印 |
| `references/05-哈希门禁与验收.md` | 交付前门禁、失败定位 |
| `references/06-版本发布与故障排查.md` | 发布、V10、常见故障 |
| `references/07-反模式与门禁盲区.md` | 任何“看起来对但门禁过”的怀疑 |

> **一句话：** 单项目由第一技能保证“一份报告对”；本技能保证“把 74 份对的报告，聚合成一张对的工作台，并且每次都能字节级重建”。
