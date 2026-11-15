# 清算ABS多行工作台聚合展示 · 1.0

> 第二技能：把**已经验收**的逐单清算期不良ABS报告，聚合成一个可复刻的多行工作台。
>
> 参考实现 **V9**：74 单 / 5 家银行 / 13 张 ECharts + 1 个 HTML 现金流分配板。
> 基线：**11,385,763 B**，SHA256 **`8ae21fd0266387ae9fde9b00ceecf432bcac4ed864eaf7a1e2e11a680d037593`**。

---

## 它解决什么

单项目技能（`清算ABS项目汇报分析4.0`）负责“一个 PDF → 一份八节 HTML”。
本技能负责：

- 74 行数据契约与聚合；
- 单文件工作台的切片、多选、矩阵、查看器；
- 14 个视觉图（13 ECharts + 1 HTML 现金流板）；
- 输入指纹 / 产物 SHA256 / 数据 / 交互四道门；
- 版本 V1→V9 留档与可复刻发布。

**不做什么：** 不重新解析 PDF，不改单项目数值，不用其他项目兜底。

---

## 30 秒验证本包

```bash
python -X utf8 scripts/hash_manifest.py --check
python -X utf8 scripts/build_workbench.py --check
python -X utf8 scripts/gate.py --html dist/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html
```

期望：

| 项 | 值 |
|---|---|
| 产物 | 11,385,763 B |
| SHA256 | `8ae21fd0266387ae9fde9b00ceecf432bcac4ed864eaf7a1e2e11a680d037593` |
| 行数 | 74 |
| 银行 | 5 |
| ECharts | 13 |
| HTML 现金流板 | 1（8 行） |
| 现金流解析 | 74/74 |
| G0/G1/G2/G3 | 全 PASS |

---

## 目录

```text
SKILL.md                         主入口（边界、铁律、架构、门禁）
README.md                        本文件
references/                      00 零到一、01 契约、02 口径、03 架构、
                                 04 图表、05 门禁、06 发布/故障、07 反模式
assets/workbench/..._V9.html     参考产物 + 重建基线
assets/source/                   v3.js / 3 份 CSS / echarts.min.js
assets/data/_rows_all.json       74 行 canonical
assets/data/_rows.json           旧 67 行（只对照）
assets/docs/                     工作台说明 + 版本索引
assets/golden/hashes.json        V9 与源文件哈希
scripts/
  build_workbench.py             重建 + G1
  inject_v3.py                   唯一注入实现
  aggregate_rows.py              项目目录 → 行数据 + 行校验
  gate.py                        G1+G2+G3
  verify_workbench.py            Playwright G3
  hash_manifest.py               G0
templates/                        行 schema、交付清单
tests/                            G3 说明（实际门禁在 scripts/gate.py）
dist/                             构建输出
```

---

## 安装

### WorkBuddy / 通用目录

```powershell
# 解压到用户技能目录；目录名保持「清算ABS多行工作台聚合展示」
Expand-Archive -Path "<本包>.zip" -DestinationPath "$env:USERPROFILE\.workbuddy\skills" -Force
```

### DSH 入口

本包顶层 `03_DSH入口/abs-workbench/SKILL.md` 是适配入口；复制到工作区 `.dsh/skills/abs-workbench/`。
它只指向真实技能目录，不复制技能正文。

---

## 换一批项目

```bash
python -X utf8 scripts/aggregate_rows.py --projects-root "<项目根>" \
  --canonical assets/data/_rows_all.json --out dist/_rows_all.json
python -X utf8 scripts/aggregate_rows.py --check --rows dist/_rows_all.json
```

**边界：** 本包 V9 的基础壳已内嵌当前 74 单的 `META/REPORTS/SLICE_ROWS`。
替换成新数据集时，除行数据外还要重建基础壳的报告/项目索引；`references/00` 第 6 节说明边界。
只换 V3 行数据而不换基础壳，会出现“表里有行、查看器没有报告”的假成功。

---

## 版本

- 本技能 **1.0**，参考工作台 **V9**（2026-11-06）。
- V1–V9 全部保留；主文件只是最新别名。
- 交付必须附 `_rows_all.json` SHA256、V9 SHA256、G0–G3 结果。

---

## 三个数字先记住

1. **74**：中信 15 + 招商 18 + 建设 17 + 兴业 10 + 农行 14；
2. **70 / 4**：70 已清算、4 存续；
3. **13 + 1**：13 张 ECharts + 1 个 HTML 现金流分配板。

> 任何其中一个对不上，先停，不要用“界面看起来对”代替门禁。
