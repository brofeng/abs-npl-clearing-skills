# scripts/pipeline/ · 上游解析工具箱

把「中债官网 PDF → payload.json + metrics.json」这一段固化。产出的 payload
直接喂给 `scripts/single/build_single.py`。

## 环境

- **Python 3.12**（必须有 `PyMuPDF` / `fitz` 与 `rapidocr`）。默认的 3.13 无 `fitz`。
- 只需要浏览器的是下游的 G2/G3；本目录**不需要浏览器**（OCR 除外）。

## 目录约定

```
<批次根>/                      ← ABS_BATCH
  兴瑞2021年第一期/             ← 单期目录，--proj 指向它
    01_下载文档/*.pdf
    02_提取数据/{文本,OCR,*.json,payload.json,metrics.json}
    03_报告产出/
```

## 环境变量（4.0 起全部参数化，无写死路径）

| 变量 | 含义 | 缺省 |
|---|---|---|
| `ABS_SKILL` | 技能根 | 由脚本位置反推（上溯两级） |
| `ABS_ASSETS` | 单期输入目录 | `<技能根>/assets/single` |
| `ABS_BATCH` | 批次根 | 由 `--proj` 的父目录推出 |
| `ABS_PREFIX` | 期次目录名前缀（兴瑞/建鑫/惠元/和萃） | **`_build_all.py` / `_g1.py` 必填** |

## 执行顺序

```
02 → 07 → 03 → 04 → 05 → 06 → 08 → 14 → (build_single → verify_single)
```

## 各脚本一句话

| 脚本 | 输入 | 输出 |
|---|---|---|
| `02_parse_prospectus.py` | 发行说明书 | `_sm_parsed.json` |
| `03_parse_dist.py` | 发行说明书（含扫描件） | `_dist_parsed.json`、`_dist_xy.json` |
| `04_extract.py` | 全部 PDF | `文本/*.txt` 或 `OCR/*.ocr.txt` |
| `05_parse_trustee.py` | 受托机构报告 N 份 | `_trustee_parsed.json` |
| `06_parse_liquidation.py` | 清算审计 + 清算报告 | `_liq_parsed.json` |
| `07_parse_rating.py` | 中债资信评级报告 | `_rating_parsed.json` |
| `08_assemble.py` | 以上全部 | `payload.json`、`metrics.json` |
| `14_to_layout.py` | payload/metrics | `payload_layout.json`（+ 独立 stage） |
| `_build_all.py` | 批次根 | 批量跑全链路 + 断言 |
| `_g1.py` | 批次根 | 逐单 G1 哈希 + 更新 golden |
| `_recon.py` | 批次根 | 逐科目对账 CSV（**交付前必跑**） |
| `_scope_check.py` | 三源清单 | 项目池范围核定 CSV |
| `_numfix.py` | — | 金额粘连切分（11 位护栏） |
| `_xy_dist.py` / `_ocr_xy2.py` | 扫描件分布表 | 坐标法还原 + 硬校验 |
| `_ocr_*.py` | 扫描 PDF | OCR 文本 |

## 三条硬规则

1. **每单独立 stage**。共用 stage 目录会把上一单数据混进下一单，断言看不出来。
2. **先查 `references/23-四行体例差异台账.md` 再动手**。四家银行三种清算体例、
   两种固资体例、两种列序、两种单位。
3. **交付前跑 `_recon.py`**。本项目四个真缺陷全部属「总额对、明细错」，
   汇总断言看不见，只有逐期并排比对才抓得到。

## 已知边界

- 上游解析器按**中信/招商/建设/兴业**四行体例调过。第五家银行请先跑 `23` 的 10 步检查。
- 存续期单（无清算报告）无法做固资 A/B 反推 → `sub_fixed_total` 应记 `None`。
- 扫描件版面未构成完整表时，坐标法也无解 → 置灰 `scan-unparsable`，写真实原因。
