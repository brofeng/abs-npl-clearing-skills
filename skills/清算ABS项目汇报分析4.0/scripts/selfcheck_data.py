#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""清算ABS穿透分析 · 数据门控自检

用途：每次开工第一步跑这个，确认「字段有什么、缺什么、哪些不能用」。
输出：字段可得率表 + 已知缺陷清单 + 瀑布重建校验。

用法：
    <python> selfcheck_data.py --payload path/to/payload.json
    <python> selfcheck_data.py --payload ... --json out.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# (字段名, 说明, 是否可用于出图)
CRITICAL = [
    ("disposeFeeRate", "处置费率", True),
    ("disposeFee", "处置费用", True),
    ("recovered", "累计回收", True),
    ("recRate", "实际回收率", True),
    ("poolTotal", "入池本息费", True),
    ("poolPrincipal", "资产本金规模（气泡用）", True),
    ("expRecRate", "中债预测回收率", True),
    ("vsForecast", "达成率", True),
    ("issue", "发行规模", True),
    ("sen", "优先档规模", True),
    ("sub", "次级档规模", True),
    ("cpSen", "优先档票面", True),
    ("xirrSen", "优先档 XIRR", True),
    ("xirrSub", "次级档 XIRR", True),
    ("subExcess", "次级档超额收益", True),
    ("subMultiple", "次级档回报倍数", True),
    ("cat", "品种", True),
    # 禁止使用（不存在或不可靠）
    ("预测XIRR", "预测 XIRR", False),
    ("发行利差", "发行利差", False),
    ("约定资金成本率", "次级约定资金成本率", False),
]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def waterfall_check(raw):
    """按「分档兑付表口径 + 处置费用重复检测」重建瀑布，返回统计。"""
    out, bad, dbl_list = [], [], []
    for p in raw.get("projects", []):
        a, a2 = p.get("alloc") or {}, p.get("alloc2") or {}
        rec, outp = a.get("rec_total"), a.get("out_total")
        rows = a2.get("rows") or []
        if rec is None or not rows:
            continue
        fees = [r for r in rows if r.get("role") == "leaf" and r.get("item") == "fee"]
        disp = next((r.get("cum") or 0.0 for r in fees if "处置费用" in str(r.get("label"))), 0.0)
        dbl = bool(disp and outp is not None and abs((rec - outp) + disp) < max(1.0, rec * 0.005))
        if dbl:
            dbl_list.append(p["key"])
        tot = sum((r.get("cum") or 0) for r in fees if not (dbl and "处置费用" in str(r.get("label"))))
        tot += sum((r.get("cum") or 0) for r in rows if r.get("role") == "leaf" and r.get("tier"))
        tot += sum((r.get("cum") or 0) for r in rows
                   if r.get("role") == "leaf" and r.get("item") == "carry")
        res = rec - tot
        pct = abs(res) / rec * 100 if rec else 999
        out.append({"key": p["key"], "residual": res, "pct": round(pct, 3)})
        if pct > 5:
            bad.append(p["key"])
    return out, bad, dbl_list


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True, help="原始 payload.json 路径")
    ap.add_argument("--prof", help="适配层 payload_28.json 路径（不传则自动搜索）")
    ap.add_argument("--json", help="把结果写成 JSON")
    args = ap.parse_args()

    raw = load(args.payload)
    projects = raw.get("projects") or []
    n = len(projects)
    print("=" * 78)
    print(f"清算ABS 数据门控自检   单数 {n}")
    print("=" * 78)

    # ── 1. 项目顶层键 ──
    keys = set()
    for p in projects:
        keys |= set(p.keys())
    print("\n[1] 顶层键（合并 28 单）")
    print("   ", " ".join(sorted(keys)))

    # ── 2. 字段可得率（从适配层或直接推） ──
    print("\n[2] 关键字段可得率")
    print(f"   {'字段':<22}{'可得':>8}   状态")
    print("   " + "-" * 60)
    prof_path = None
    if args.prof:
        prof_path = Path(args.prof)
    else:
        # 自动搜索：payload 同目录、祖先目录下的 设计资产/payload_28.json
        base = Path(args.payload).resolve()
        cands = []
        for up in list(base.parents)[:5]:
            cands += [up / "设计资产" / "payload_28.json",
                      up / "payload_28.json",
                      up / ".." / "清算28单_不良ABS分析" / "设计资产" / "payload_28.json"]
        for c in cands:
            if c.exists():
                prof_path = c.resolve()
                break
    avail = {}
    if prof_path and prof_path.exists():
        prof = json.loads(prof_path.read_text(encoding="utf-8")).get("PROF") or {}
        for f, desc, usable in CRITICAL:
            if not usable:
                print(f"   {f:<22}{'禁止':>8}   ❌ 不存在/不可靠，禁止出图")
                continue
            cnt = sum(1 for k in prof if prof[k].get(f) not in (None, "", [], {}))
            avail[f] = cnt
            flag = "✅" if cnt == len(prof) else ("⚠ 缺 %d" % (len(prof) - cnt))
            print(f"   {f:<22}{cnt:>4}/{len(prof)}   {flag}  {desc}")
    else:
        print(f"   ⚠ 未找到适配层 {prof_path}，跳过可得率（请先跑适配脚本）")

    # ── 3. 已知缺陷扫描 ──
    print("\n[3] 已知缺陷扫描")
    # 3.1 处置费用重复计入
    _, bad_wf, dbl = waterfall_check(raw)
    print(f"   处置费用重复计入：{len(dbl)} 单", ("→ " + ", ".join(dbl)) if dbl else "")
    # 3.2 pool_intfee 不一致
    inconsistent = []
    for p in projects:
        pool = p.get("pool") or {}
        bsf, prin, intfee = pool.get("pool_bsf"), pool.get("pool_prin"), pool.get("pool_intfee")
        if None in (bsf, prin, intfee):
            continue
        if abs((bsf - prin) - intfee) > 1000:
            inconsistent.append((p["key"], round(bsf - prin - intfee, 2)))
    print(f"   pool_intfee 与 (本息费−本金) 不一致：{len(inconsistent)} 单")
    for k, d in inconsistent:
        print(f"      {k}  差 {d:,.2f} 元  ← 需回源说明书核对")
    # 3.3 subFixed 真伪
    true_fixed, derived = [], []
    dbl_set = set(dbl)
    all_fx = {}
    for p in projects:
        rows = (p.get("alloc2") or {}).get("rows") or []
        fx = next((r.get("cum") for r in rows if "固定资金成本" in str(r.get("label"))), None)
        if not fx:
            continue
        per = sum(o.get("amount", 0) for q in (p.get("periods") or [])
                  for o in (q.get("outflow") or []) if "固定资金成本" in o.get("label", ""))
        all_fx[p["key"]] = fx
        if abs(per - (fx or 0)) < 1:
            true_fixed.append(p["key"])
        else:
            derived.append(p["key"])
    # 适配层里 subFixed 有值但 alloc2 无该科目 → 推算值（不得当披露值用）
    if prof_path and prof_path.exists():
        for k, v in prof.items():
            if v.get("subFixed") not in (None, 0) and k not in all_fx:
                derived.append(k)
    print(f"   subFixed 真实单列：{len(true_fixed)} 单 → {true_fixed}")
    print(f"   subFixed 推算/无明细：{len(derived)} 单（**不得当披露值用**）")
    print(f"      → 其余 {len(projects) - len(true_fixed)} 单无该科目单列明细；"
          f"「收益合计−超额−未拆分」是推算值，禁止当披露值出图")
    # 3.4 alloc vs periods 口径差（排除上面已识别的处置费重复计入）
    diffs = []
    for p in projects:
        a = p.get("alloc") or {}
        rec, outp = a.get("rec_total"), a.get("out_total")
        if rec is None or outp is None:
            continue
        d = rec - outp
        if p["key"] in dbl_set:
            continue
        if rec and abs(d) / rec > 0.01:
            diffs.append((p["key"], round(d / 1e4, 1), round(abs(d) / rec * 100, 2)))
    print(f"   分配表 vs 逐期账户口径差 >1%：{len(diffs)} 单（已排除处置费重复计入单；瀑布按「账面结余」如实显示，勿强行调平）")

    # ── 4. 瀑布重建校验 ──
    wf, _, _ = waterfall_check(raw)
    if wf:
        worst = max(wf, key=lambda x: x["pct"])
        good = sum(1 for x in wf if x["pct"] < 1)
        print(f"\n[4] 瀑布重建校验（分档兑付表口径）")
        print(f"   覆盖 {len(wf)} 单 ｜ 残差 <1%：{good} 单 ｜ 最大残差 {worst['pct']}%（{worst['key']}）")
        print(f"   超 5% 的单：{len(bad_wf)} 单（应优先追查）")

    # ── 5. 结论 ──
    print("\n" + "=" * 78)
    blockers = []
    if not prof_path.exists():
        blockers.append("缺适配层 payload_28.json")
    if inconsistent:
        blockers.append(f"{len(inconsistent)} 单 pool_intfee 需回源")
    if bad_wf:
        blockers.append(f"{len(bad_wf)} 单瀑布残差 >5%")
    if blockers:
        print("⚠ 开工前需处理：")
        for b in blockers:
            print("   -", b)
    else:
        print("✅ 数据门控通过，可开工（注意：缺失一律「—」，n 动态，禁臆造）")
    print("=" * 78)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "n_projects": n, "availability": avail,
            "dup_dispose_fee": dbl, "pool_intfee_inconsistent": inconsistent,
            "subfixed_true": true_fixed, "subfixed_derived_count": len(derived),
            "waterfall_residual": wf, "waterfall_bad": bad_wf,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结果已写入 {args.json}")


if __name__ == "__main__":
    main()
