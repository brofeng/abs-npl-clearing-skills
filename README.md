# 清算期不良 ABS 穿透分析 · 双技能

> 把银行间市场披露的清算期不良 ABS 文档（说明书 / 受托报告 / 清算报告 / 评级报告），
> 变成**可复刻、可验收、可交付**的单项目穿透报告与多单工作台。
>
> 两个 WorkBuddy Agent Skill，遵循 `SKILL.md` 开放规范，Claude Code / Codex 等支持该规范的工具同样可装载。

| 项 | 值 |
|---|---|
| 技能一 | 清算ABS项目汇报分析 · **v4.2.0** |
| 技能二 | 清算ABS多行工作台聚合展示 · **v1.0.0** |
| 实操验证 | 四家银行 **86 单**（中信惠元 35 / 招商和萃 19 / 建设建鑫 24 / 兴业兴瑞 10），FAIL = 0 |
| 聚合参考实现 | **74 单 / 5 家银行 / 13 张 ECharts + 1 个现金流分配板** |
| 复刻精度 | 单项目交付件 **字节级一致**（205,040 B / `deeef1e0…` 命中） |
| 许可 | MIT |

---

## 这个技能能帮你做什么

> **一句话**：把清算期不良 ABS 的 PDF 文件，变成**可复刻、可验收、可交付**的单项目深度报告与多单工作台。

**适合谁用**

- 券商 / 银行 / AMC 的特殊资产、投行、研究与风控团队；
- 做不良 ABS 存续期跟踪、清算期回收测算、投后复盘的分析师；
- 需要给管理层或投资人快速出「同口径横向对比」的人。

**它替你做的四件事**

| 环节 | 你原本要做什么 | 这个技能给你什么 |
|---|---|---|
| 取数 | 从说明书 / 受托 / 清算 / 评级四类 PDF 里手抄、对账，扫描件还要认坐标 | `scripts/pipeline/` 输出 `payload.json`：扫描件坐标还原、逐科目对账，取数口径写死在代码里 |
| 成稿 | 八节报告逐节搭、每个指标重新算 | 单项目八节 HTML：证券化率、处置费率、回收率、达成率、优先/次级 XIRR 与 XNPV、清仓回购、信托终局判定、现金流分配瀑布、同业分位 |
| 聚合 | 把 N 份报告拼成一张总表，再手搓切片和图表 | 单文件工作台：切片、Ctrl 多选、银行 × 品种矩阵、四象限、现金流分配板、报告查看器、导出 / 打印（参考实现 **74 单 / 5 家银行 / 13 图**） |
| 验收 | 人工复核数字，心里没底 | 三级门禁 **G1 字节 / G2 数据 96 项 / G3 交互 137–144 项**，过不了就不交付 |

**为什么值得用（而不是又一个提示词模板）**

大多数「金融分析 Skill」是一段提示词 + 一张表格样式；这个技能是一条**带门禁的产线**：

- 同一份输入反复构建，产物**字节一致**（205,040 B / `deeef1e0…` 命中）；
- 数值一改，必须过 G2 数据断言与 G3 交互断言——防的是「门禁通过、总额正确、图内自洽，但明细全错」的 12 类真实缺陷；
- 换一家银行或会计师事务所的体例，按《四行体例差异台账》改取数即可，不用从零试错；
- 口径纪律（折年化是否整十、期次排序键、累计期次剔除、预计回收取源方向、XIRR 复算、清仓回购起算日）全部写成可查的表，不靠师傅带。

**上手**：见下文「三、30 秒开始」；只想先看效果，直接打开 `skills/清算ABS多行工作台聚合展示/dist/` 里的 V9 工作台（单文件 HTML，双击即用）。

## What it does

> **One line:** turn clearing-period NPL ABS documents (prospectus, trustee, liquidation and rating reports) into **reproducible, gated, deliverable** single-deal deep-dive reports and multi-deal workbenches.

**Who it is for**

- Special-situations, investment-banking, research and risk teams at brokers, banks and AMCs;
- analysts tracking NPL ABS performance, computing liquidation-period recoveries, or running post-mortems on deals;
- anyone who needs a like-for-like cross-deal comparison for management or investors, fast.

**Four things it does for you**

| Step | What you would normally do | What the skill gives you |
|---|---|---|
| Extraction | Copy figures out of four document types by hand, reconcile line by line, fight scanned-page coordinates | `scripts/pipeline/` produces `payload.json` with scanned-page coordinate recovery and per-line reconciliation; the extraction rules live in code |
| Reporting | Build an eight-section report and recompute every metric | Eight-section HTML report: securitisation ratio, disposal cost ratio, recovery rate, target achievement, senior/subordinated XIRR and XNPV, clean-up call, trust wind-up tests, cash-distribution waterfall, peer percentile |
| Aggregation | Stitch N reports into one table, then hand-build slicers and charts | Single-file workbench: slicers, multi-select, bank × product matrix, four-quadrant view, cash-flow board, report viewer, export / print (reference: **74 deals / 5 banks / 13 charts**) |
| Acceptance | Re-check numbers by hand, never fully sure | Three-level gates: **G1 byte identity, G2 96 data assertions, G3 137–144 interaction assertions** — fail a gate, ship nothing |

**Why it is different** — most "financial analysis skills" are a prompt plus a table style. This is a production line with gates: the same input rebuilds to byte-identical output; any number change must pass the data and interaction assertions; a 12-item anti-pattern ledger and a four-bank style-divergence ledger capture real defects whose signature is *gates pass, totals are right, charts are self-consistent, and every detail is wrong*; and the counting conventions are written down instead of learned by trial and error.

**Start here** — see "三、30 秒开始" below, or open the bundled V9 workbench HTML (single file, opens in any browser).

---

## 一、这不是提示词模板

大多数「金融分析 Skill」是一段提示词 + 一张表格样式。这个不一样，它是**带门禁的产线**：

1. **上游取数固化**：`scripts/pipeline/` 把 PDF → `payload.json`，含扫描件坐标还原、逐科目对账，不是让模型「读一下 PDF 然后算」。
2. **下游成稿确定性**：同一份 payload 反复构建，产物字节一致（G1 字节门禁）；数值改了必须过 G2 数据门禁（96 项）与 G3 交互门禁（137–144 项语义断言）。
3. **反模式清单**：12 条真实缺陷，共同特征是「**门禁通过、总额正确、图内自洽，但明细全错**」，每条给出唯一解药（逐科目对账）。
4. **四行体例差异台账**：德勤版 / 毕马威版 / 信托散文版三种清算报告体例；次级档固定资金成本 A/B 两体例；期次排序键、累计期次剔除、预计回收取源方向、分布表列序、预测表单位——全部踩过并写成表。
5. **过不了门禁就不交付**：单项目不过 G1/G2/G3，不进工作台聚合。这条是硬规则，写在 SKILL.md 里。

## 二、两个技能怎么分工

```text
PDF / 说明书 / 受托报告 / 清算报告 / 评级报告
        │
        ▼  技能一 v4.2（单项目）
  payload.json + metrics.json + 八节 HTML + _assert_single.json
        │
        ▼  export_workbench_row.py（行契约桥接）
   N 行 canonical（74 行数据字典）
        │
        ▼  技能二 v1.0（多单工作台）
   单文件 HTML：切片 / 矩阵 / 14 图 / 查看器 / 导出 / 打印
```

| | 技能一 `清算ABS项目汇报分析` | 技能二 `清算ABS多行工作台聚合展示` |
|---|---|---|
| 输入 | 单项目 PDF 套件 | 已过门禁的 N 个项目 |
| 输出 | 八节深度报告（单文件 HTML） | N 单工作台（单文件 HTML） |
| 核心 | 取数、口径、断言 | 行契约、聚合、交互 |
| 不做什么 | 不负责多单聚合 | **不重新解析 PDF、不改单项目数值** |

## 三、30 秒开始

```bash
git clone https://github.com/brofeng/abs-npl-clearing-skills.git
cd abs-npl-clearing-skills

# 1) 装到 WorkBuddy（Windows 示例，macOS/Linux 换成 ~/.workbuddy/skills）
xcopy "skills\清算ABS项目汇报分析4.0" "%USERPROFILE%\.workbuddy\skills\清算ABS项目汇报分析4.0\" /E /I
xcopy "skills\清算ABS多行工作台聚合展示" "%USERPROFILE%\.workbuddy\skills\清算ABS多行工作台聚合展示\" /E /I

# 2) 技能二：重建参考实现并过门禁
cd "%USERPROFILE%\.workbuddy\skills\清算ABS多行工作台聚合展示"
python -X utf8 scripts/build_workbench.py --check
python -X utf8 scripts/gate.py --html "dist/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"
```

期望产物：**11,385,763 B**，SHA256 `8ae21fd0266387ae9fde9b00ceecf432bcac4ed864eaf7a1e2e11a680d037593`。

> G3 交互门禁需要 Microsoft Edge + Playwright；只跑 G1/G2 不需要浏览器。

## 四、目录结构

```text
skills/清算ABS项目汇报分析4.0/
├── SKILL.md                 触发与流程（含 4.2 变更说明）
├── references/              28 篇口径台账、反模式、体例差异、复现手册
├── scripts/
│   ├── pipeline/            上游解析（说明书/受托/清算/评级 → payload）
│   ├── single/              单项目构建 + 复刻门禁
│   └── v2/                  多单 N 单横向对照（产品线 B，兼容旧交付）
├── templates/               骨架生成与校验
└── assets/                  payload 样例、CSS、golden 规格、像素基线

skills/清算ABS多行工作台聚合展示/
├── SKILL.md
├── references/              8 篇：行契约、聚合口径、V9 架构、哈希门禁…
├── scripts/                 aggregate_rows / build_workbench / gate / hash_manifest
├── assets/                  74 行 canonical、V3 源、ECharts、V9 成品
└── dist/                    构建输出目录
```

## 五、口径纪律（本仓库最贵的部分）

这些不是风格偏好，是踩过一次就会算错账的硬约束，完整版见 `references/`：

- **折年化是否整十**——次级档固定资金成本必须用清算总额反推，再拿「折年化」交叉验证；
- **期次排序键**——必须用本期期末日，不能用报告标题里的期次序号；
- **年度受托报告累计期次必须剔除**——否则回收与利息算两遍，且只能靠等比例缩放掩盖；
- **预计回收取源方向相反**——中债预测与受托报告口径方向不同，取反会得到自洽的错数；
- **XIRR 可复算（1bp）**——守两套现金流并存，防「两套现金流各算各的」；
- **清仓回购起算日必须存在**——三分支判定，`recovery_includes_buyback` 开关防回购价款重复计入。

## 六、从技能市场安装

市场上搜「清算ABS」，或直接用仓库内 `market/` 打包好的安装包：

| 文件 | 用途 |
|---|---|
| `market/abs-clearing-report-4.2.0.zip` | 技能一上架包（≤3MB，已裁剪基线资产） |
| `market/abs-workbench-1.0.0.zip` | 技能二上架包（≤3MB） |
| `market/skill-01-icon.png` / `skill-02-icon.png` | 512×512 市场头像 |

> 市场包为保证 ≤3MB 上传限制，移除了可再生的像素基线与 V9 成品；克隆本仓库即得完整版。

## 七、已知边界

- **不含任何原始项目 PDF**：真实项目文档请自行获取，本仓库只含分析产物与示例 payload。
- **不构成投资建议**：所有指标都是对已披露信息的重构，口径与银行内部台账可能存在差异，用于决策前请自行复核。
- **Windows 优先**：脚本以 Windows + Python 3.11+ 为基线验证；macOS/Linux 需自行调整路径与 Edge 调用。
- **单项目从零重跑需原始资料**：仓库给的是 pipeline、示例、门禁与骨架，不是 74 份 PDF。

## 八、贡献

欢迎提 Issue 与 PR，最有价值的贡献是**新的体例差异**与**新的反模式**：

- 遇到某家银行/某家会计师事务所的报告体例与本台账不符 → 提 Issue，附字段位置与原文截图（脱敏）；
- 写了解析器踩坑 → 直接补 `references/24-反模式清单与门禁盲区.md`，一行一条，写清「现象 / 根因 / 解药」；
- 发现门禁能过但明细错的路径 → 这是最有价值的 Issue，请务必提。

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 九、免责声明

本仓库内容为个人对公开披露信息的技术与方法沉淀，不代表任何机构立场，不含任何机构的非公开数据、客户信息或内部资料。
使用者应自行确保其数据获取与使用方式符合所在机构的合规要求与法律法规。作者不对使用本仓库产生的任何结论或损失承担责任。

---

MIT License · 详见 [LICENSE](LICENSE)
