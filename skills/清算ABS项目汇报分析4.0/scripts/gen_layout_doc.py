#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""gen_layout_doc.py —— 从指纹 JSON 生成人读的版式/文案规格文档

设计意图：**规格文档不手写，一律从 report_spec.json 生成**。
这样文档永远与基线一致，不会出现"文档说 3 列、实际 6 列"的漂移。

用法：
    <python> gen_layout_doc.py --spec <golden/report_spec.json> --out <references/12-版式像素规格.md>
"""
import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))
    views = spec["views"]
    meta = spec["meta"]

    L = []
    L.append("# 12 · 版式与文案规格（**自动生成，勿手改**）")
    L.append("")
    L.append("> 本文件由 `scripts/gen_layout_doc.py` 从 `assets/golden/report_spec.json` 生成。")
    L.append("> 该 JSON 是**唯一权威**：由无头浏览器逐视图激活后实测采集（栅格/卡片/表行/SVG/字号/渲染后全文）。")
    L.append("> **任何版式或文案改动，必须同时更新基线**，否则 `probe_report.py --mode verify` 会失败。")
    L.append("")
    L.append("## 0. 总览")
    L.append("")
    L.append(f"- 视图数：**{meta['viewCount']}**")
    L.append(f"- 侧栏项：**{meta['navCount']}**")
    L.append(f"- 全页 SVG：**{meta['svgTotal']}** 张")
    L.append(f"- 页面标题：`{meta.get('title','')}`")
    L.append("")
    L.append("### 侧栏菜单（顺序即渲染顺序，不得增删改序）")
    L.append("")
    for i, t in enumerate(meta["navText"], 1):
        L.append(f"{i:>2}. `{t}`")
    L.append("")
    L.append("## 1. 视图清单与结构指纹")
    L.append("")
    rows = []
    for v in views:
        rows.append([
            f"`{v['vid']}`",
            v["nav"],
            v.get("cards", "-"),
            v.get("kpis", "-"),
            v.get("tr", "-"),
            v.get("svg", "-"),
            v.get("details", "-"),
            f"{v.get('detailsOpen',0)}",
            v.get("gridCols", 0) or "-",
        ])
    L.append(md_table(
        ["视图 id", "侧栏文案", "卡片", "KPI格", "表格行", "SVG", "折叠块", "默认展开", "栅格列"],
        rows))
    L.append("")
    L.append("> **判据**：以上任一数字与基线不符 → 版式已漂移。")
    L.append("")
    L.append("## 2. 卡片高度签名（前 12 个容器，px）")
    L.append("")
    L.append("高度是**布局正确性的强信号**：栅格错位、内容撑高、等高失效都会立刻改变高度。")
    L.append("")
    rows = []
    for v in views:
        h = v.get("heights") or []
        if h:
            rows.append([f"`{v['vid']}`", " / ".join(str(x) for x in h)])
    L.append(md_table(["视图", "高度序列"], rows))
    L.append("")
    L.append("> 容差：`probe_report.py` 做**精确比对**。若环境字体差异导致 ±1–2px，")
    L.append("> 应先统一环境（同 Edge 版本、同 window-size=1600×1400、同 `--hide-scrollbars`），")
    L.append("> 而不是放宽判据。")
    L.append("")
    L.append("## 3. 字号分布（SVG 内 text/tspan）")
    L.append("")
    L.append("字号是**视觉一致性**的直接体现；分布变了说明图表重绘逻辑变了。")
    L.append("")
    rows = []
    for v in views:
        f = v.get("fonts") or {}
        if f:
            s = " ".join(f"{k}×{n}" for k, n in sorted(f.items(), key=lambda x: float(x[0].replace('px', ''))))
            rows.append([f"`{v['vid']}`", s])
    L.append(md_table(["视图", "字号 → 数量"], rows))
    L.append("")
    L.append("## 4. 区块标题（每视图 h2/h3 顺序）")
    L.append("")
    L.append("标题文字与顺序是**内容结构**的指纹，改一个字都会被门禁抓到。")
    L.append("")
    for v in views:
        secs = v.get("sections") or []
        if not secs:
            continue
        L.append(f"### `{v['vid']}` — {v['nav']}")
        L.append("")
        for i, s in enumerate(secs, 1):
            L.append(f"{i}. {s}")
        L.append("")
    L.append("## 5. 渲染后全文（文案基线）")
    L.append("")
    L.append("**这是文案的唯一权威**——注意是**渲染后**文本（客户端改写之后的真值），")
    L.append("不是源文件文本。基线全文存在 `assets/golden/report_spec.json` 的 `views[].text` 字段")
    L.append("（每视图上限 60,000 字符），由 `probe_report.py` 逐行比对，报出**首个差异行号 + 期望值/实得值**。")
    L.append("")
    L.append("查看某视图的文案基线：")
    L.append("")
    L.append("```bash")
    L.append("# 用 python 打印某个视图的渲染后全文")
    L.append("<python> -c \"import json;d=json.load(open(r'assets/golden/report_spec.json',encoding='utf-8'));\" ^")
    L.append("        \"v=[x for x in d['views'] if x['vid']=='xcompare'][0];print(v['text'])\"")
    L.append("```")
    L.append("")
    L.append("## 6. 如何更新本规格")
    L.append("")
    L.append("```bash")
    L.append("# 1) 改完代码，重新构建")
    L.append("<python> scripts/v2/build_v2.py")
    L.append("")
    L.append("# 2) 重新生成基线指纹")
    L.append("<python> scripts/probe_report.py --html <新报告> --mode extract --out assets/golden/report_spec.json")
    L.append("")
    L.append("# 3) 重新生成本文档")
    L.append("<python> scripts/gen_layout_doc.py --spec assets/golden/report_spec.json \\")
    L.append("        --out references/12-版式像素规格.md")
    L.append("")
    L.append("# 4) 重新生成黄金截图")
    L.append("<python> scripts/visual_regression.py --html <新报告> --mode snapshot --out assets/golden/screens")
    L.append("```")
    L.append("")
    L.append("> ⚠ **基线不是「自动接受」**：更新基线等于宣布「新版本才是对的」。")
    L.append("> 更新必须在 README 里写清「为什么变」，否则视为回归。")
    L.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"✅ 已生成 {out}  ({out.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
