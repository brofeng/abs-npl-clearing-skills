# -*- coding: utf-8 -*-
"""现金流污染门禁：检查报告 XNPV 表里的日期是否都属于本单。

背景：单项目构建器曾内置「惠元第三期」硬编码现金流兜底。次级档早期只有
一笔认购流出（1 个点）时，兜底会把别单的次级现金流带进本单 XNPV 表，
出现 2021-12-21、2022-06-20 等不属于本单的日期。

用法：
  python check_cashflow_contamination.py --report <report.html> --payload <payload.json>
  python check_cashflow_contamination.py --report <report.html> --payload <payload.json> --json
退出码：0=干净；1=发现非本单日期；2=输入/解析失败。
"""
import argparse
import io
import json
import re
import sys

DATE_RE = re.compile(r"<td>(\d{4}-\d{2}-\d{2})</td>")


def own_dates(payload):
    meta = payload.get("meta") or {}
    dates = set()
    if meta.get("issue_date"):
        dates.add(str(meta["issue_date"]))
    for p in payload.get("periods") or []:
        if p.get("pay_date"):
            dates.add(str(p["pay_date"]))
    return dates


def xnpv_dates(html):
    i = html.find('data-chart="xnpv-table"')
    if i < 0:
        return []
    seg = html[i:i + 12000]
    return DATE_RE.findall(seg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        html = io.open(args.report, encoding="utf-8", errors="ignore").read()
        payload = json.load(io.open(args.payload, encoding="utf-8"))
    except Exception as e:
        print("读取失败：%s" % e)
        return 2
    own = own_dates(payload)
    seen = xnpv_dates(html)
    foreign = sorted({d for d in seen if d not in own})
    if args.json:
        print(json.dumps({"report": args.report, "own": sorted(own),
                          "xnpv_dates": seen, "foreign": foreign},
                         ensure_ascii=False, indent=1))
    else:
        print("本单日期：%s" % "、".join(sorted(own)))
        print("XNPV 表日期：%s" % ("、".join(seen) or "（未找到 XNPV 表）"))
        print("非本单日期：%s" % ("、".join(foreign) or "无"))
    return 1 if foreign else 0


if __name__ == "__main__":
    raise SystemExit(main())
