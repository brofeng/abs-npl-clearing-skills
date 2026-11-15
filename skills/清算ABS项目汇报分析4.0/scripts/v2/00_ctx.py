# -*- coding: utf-8 -*-
r"""v2 共享契约与上下文（Lead 维护）。

════════════════════════════════════════════════════════════════
模块契约（每个 section 模块必须导出三个字符串常量）
════════════════════════════════════════════════════════════════
    CSS  : str  —— 该模块的样式，会被拼进 <style>（在主题之后）
    HTML : str  —— 该模块需要服务端渲染的 HTML（可空）
    JS   : str  —— 该模块的客户端脚本，会被包进 IIFE（可空）

约定：
  · JS 里**不要**用 `const/let` 声明与外层同名的变量；一律用 IIFE 内部局部变量。
  · 需要数据时读全局 `window.__V2`（由 build_v2.py 注入）：
        __V2.PROF  {key: profile}   28 单档案
        __V2.ORDER [key...]         项目键（自然序）
        __V2.AUDIT {…}              稽核数据
        __V2.fmt(v) / __V2.pct(v) / __V2.yi(v) / __V2.wan(v) / __V2.num(v)
  · DOM 钩子见下方“目标结构”。

════════════════════════════════════════════════════════════════
设计令牌（沿用三单设计系统）
════════════════════════════════════════════════════════════════
  --ink #141A26  --ink2 #38425A  --sub #697487  --mute #98A2B3
  --bg #F2F5F9   --card #fff    --surface #EDF1F6  --hover #F8FAFD
  --red #A52524  --navy #2D3955 --pos #B3261E  --neg #1F7A5C  --warn #B0763F
  --r 16px  --r-chip 9px
  --ease cubic-bezier(.16,.68,.42,1)

  品种配色：信用卡不良 #A52524 ／ 个人消费贷款 #2D3955 ／ 个人经营贷款 #1F7A5C

════════════════════════════════════════════════════════════════
目标结构（原报告 DOM，客户端增强直接操作）
════════════════════════════════════════════════════════════════
① 总览 28 单卡片
   #view-overview 内  .ov-grid > .ov-card[data-view="pN"]
   卡片内：.oname(项目名) .obank(银行) .vchip(品种) 以及若干 .ok>span+span 行
   → 目标：每行 3 张、加宽、每卡 2 列信息、提升质感

② 单项目 项目档案（#view-pN 内）
   .kpis.kpi-strip[data-chart="kpi-strip"]  8 格
   .kpis[data-chart="kpi-grid"]            23 格（银行/支付期数/设立日/清算日/
        预期到期日(优)/法定到期日(优)/预期到期日(次)/法定到期日(次)/
        合同处置费率、上限/入池本息费/入池本金/入池息费/预计回收/
        资产笔数/主体户数/单笔最高/单笔平均/主体最高/主体平均/
        前5大占比/前10大占比/加权平均逾期/是否回购）
   → 目标：删掉“账户配平”，按指定 15 项重排；冗余日期字段收进好看的面板

③ 横向对照 #view-xcompare（由 sections/30_compare.py 重新生成整节）
④ 逐单稽核 #view-audit（由 sections/40_audit.py 重新生成整节）

⑤ 折线图（#view-pN 内）
   [data-chart="recon-line"]    累计回收曲线（实际实线/预计虚线），viewBox 680×240
   [data-chart="tranche-line"]  分档累计本金走势，viewBox 680×230
   → 目标：重绘并让每个数据点可悬停读数

⑥ 全部图表 tooltip
   已有全局 #xtTip（读最近祖先的 <title>）；确保重绘的图也带 <title>
"""
from __future__ import annotations

import json
from pathlib import Path

# ── 根路径解析（v12：支持搬迁）─────────────────────────────────────
# 优先级：环境变量 NPL_ABS_HOME > 本目录 _root.txt > 默认 E:\不良ABS穿透研究
# 目标结构：<HOME>\清算28单_单项目穿透\ 与 <HOME>\清算28单_不良ABS分析\
def _resolve_home():
    import os as _os
    from pathlib import Path as _P
    _v = _os.environ.get("NPL_ABS_HOME")
    if _v:
        _p = _P(_v)
        if _p.exists():
            return _p
    _c = _P(__file__).resolve().parent / "_root.txt"
    if _c.exists():
        try:
            _s = _c.read_text(encoding="utf-8").strip()
            if _s and _P(_s).exists():
                return _P(_s)
        except Exception:
            pass
    return _P(r"E:\不良ABS穿透研究")
_HOME = _resolve_home()
# ──────────────────────────────────────────────────────────────────

# ── 路径 ──
E = _HOME / "清算28单_不良ABS分析"
V2 = E / "脚本" / "v2"
ASSET = E / "设计资产"
OUT_NAME = "清算28单_不良ABS穿透分析报告_v11.html"
OUT = E / OUT_NAME
LOG = E / "_rebuild_log"

# ── 设计令牌 ──
TOKENS = {
    "ink": "#141A26", "ink2": "#38425A", "sub": "#697487", "mute": "#98A2B3",
    "bg": "#F2F5F9", "card": "#fff", "surface": "#EDF1F6",
    "red": "#A52524", "navy": "#2D3955", "pos": "#B3261E", "neg": "#1F7A5C", "warn": "#B0763F",
    "ease": "cubic-bezier(.16,.68,.42,1)",
}
CAT_COLOR = {"信用卡不良": "#A52524", "个人消费贷款": "#2D3955", "个人经营贷款": "#1F7A5C"}


# ── 数据加载 ──
def load_payload() -> dict:
    return json.loads((ASSET / "payload_28.json").read_text(encoding="utf-8"))


def load_audit() -> dict:
    return json.loads((ASSET / "audit_payload.json").read_text(encoding="utf-8"))


def build_v2_data() -> dict:
    """装配注入前端的 __V2 数据对象。"""
    p = load_payload()
    a = load_audit()
    prof = p["PROF"]
    order = p["ORDER"]
    # 补齐前端常用派生字段
    for k in order:
        v = prof[k]
        pt = v.get("poolTotal")
        v["dispIntensity"] = None  # 用户要求删除“成本强度”定义，置空
        v["dispPct"] = (v.get("disposeFee") / v.get("recovered")) if (v.get("disposeFee") and v.get("recovered")) else None
        v["dispOverPool"] = (v.get("disposeFee") / pt) if (v.get("disposeFee") and pt) else None
        v["senShare"] = (v.get("sen") / v.get("issue")) if (v.get("sen") and v.get("issue")) else None
        v["subShare"] = (v.get("sub") / v.get("issue")) if (v.get("sub") and v.get("issue")) else None
        # 证券化率＝发行规模 ÷ 入池本息费；全报告统一用证券化率，不再提供折价率字段
        v["secRatio"] = (v.get("issue") / pt) if (v.get("issue") and pt) else v.get("secRatio")
    return {"PROF": prof, "ORDER": order, "AUDIT": a, "CAT": CAT_COLOR,
            "TOKENS": TOKENS, "WF": build_waterfall(), "DIST": build_dist()}


# ══════════════════════════════════════════════════════════════
# 分布数据（v8）：供图表层按真实数据重绘 / 换图
#   DIST[key][类型] = [{label, bal, bal_pct, n, n_pct, rec, rec_pct, avg}, ...]
#   类型：balance 余额 / grade 五级分类 / guarantee 担保方式 / overdue 逾期时间 /
#         age 年龄 / income 年收入 / credit 授信额度 / occupation 职业 / region 地区 / recrate 预计回收率
#   ⚠ 每桶同时含 bal（金额，万元）与 n（笔数）；绘图必须显式声明按哪个口径
# ══════════════════════════════════════════════════════════════
def build_dist() -> dict:
    raw = json.loads(RAW_PAYLOAD.read_text(encoding="utf-8"))
    out = {}
    for p in raw["projects"]:
        d = p.get("dist") or {}
        if d:
            out[p["key"]] = d
    return out


# ══════════════════════════════════════════════════════════════
# 瀑布重建（v6）：修正「取错字段 + 处置费用重复计入」
#   ① 证券受偿一律取「分档兑付表」(alloc2 的 tier leaf)，
#      不用 alloc.cum —— 后者把「优先档本金」写成优先+次级的总本金
#      （例：中誉至诚2023第四期 alloc.cum=226,994,300，实为优先170,000,000+次级56,994,300）
#   ② 处置费用默认计入瀑布（它是分配表真实流出）；
#      仅当检测到「回收 − 各项流出 ≈ −处置费用」（比值≈−1，即重复计入）时剔除，单列注释
# ══════════════════════════════════════════════════════════════
RAW_PAYLOAD = _HOME / "清算28单_单项目穿透" / "_校验件" / "payload.json"


def build_waterfall() -> dict:
    raw = json.loads(RAW_PAYLOAD.read_text(encoding="utf-8"))
    out = {}
    for p in raw["projects"]:
        k = p["key"]
        a = p.get("alloc") or {}
        a2 = p.get("alloc2") or {}
        rec = a.get("rec_total")
        outp = a.get("out_total")
        rows = a2.get("rows") or []
        if rec is None or not rows:
            continue
        fees = [r for r in rows if r.get("role") == "leaf" and r.get("item") == "fee"]
        disp = next((r.get("cum") or 0.0 for r in fees if "处置费用" in str(r.get("label"))), 0.0)
        # 重复计入检测：回收 − 各项流出 ≈ −处置费用
        dbl = bool(disp and outp is not None and abs((rec - outp) + disp) < max(1.0, rec * 0.005))
        steps = [{"label": "回收流入", "value": rec, "kind": "in"}]
        for r in fees:
            lab, val = str(r.get("label") or ""), (r.get("cum") or 0.0)
            if not val or (dbl and "处置费用" in lab):
                continue
            steps.append({"label": lab, "value": val, "kind": "out"})
        for r in rows:
            if r.get("role") == "leaf" and r.get("tier"):
                lab, val = str(r.get("label") or "").replace("·", ""), (r.get("cum") or 0.0)
                if val:
                    steps.append({"label": lab, "value": val, "kind": "sec"})
        carry = next((r.get("cum") or 0.0 for r in rows
                      if r.get("role") == "leaf" and r.get("item") == "carry"), 0.0)
        if carry:
            steps.append({"label": "转存下期", "value": carry, "kind": "out"})
        tot_out = sum(s["value"] for s in steps if s["kind"] != "in")
        out[k] = {"rec": rec, "disp": disp, "dbl": dbl, "steps": steps,
                  "totalOut": tot_out, "residual": rec - tot_out,
                  "note": (f"处置费用 {disp/1e4:,.2f} 万元已在处置收入环节直接扣除，"
                           f"不重复计入本瀑布" if dbl else "")}
    return out


# ── 单位统一规范（点 8）──
#   入池/回收/发行等“规模类”  → 亿元，保留 2 位
#   单笔/户均/息费等“小额类”  → 万元，保留 1–2 位
#   比率类                    → 百分比 2 位
UNIT_POLICY = """
单位统一规范：
  · 规模类（入池本息费、入池本金、累计回收、发行规模、优先档、次级档、预计回收、处置费用）
      → 一律「亿元」，2 位小数（<0.01 亿的用「万元」并注明）
  · 单笔/户均/息费类（单笔最高、单笔平均、主体最高、主体平均、入池息费）
      → 一律「万元」，1–2 位小数
  · 比率类（回收率、达成率、证券化率、XIRR、占比）
      → 一律百分号，2 位小数
  · 期数/月数/笔数/户数 → 不带单位前缀，纯数字 + 单位词
  · 【口径】证券化率 = 发行规模 ÷ 入池本息费（全报告统一用「证券化率」，不用「折价率」，
     用户明确不要 1− 转换）；处置费率只有一个口径 = 处置费用 ÷ 累计回收
"""


def fmt_yi(v):
    """元 → 亿元字符串"""
    return "—" if v is None else f"{v/1e8:,.2f}"


def fmt_wan(v, d=2):
    """元 → 万元字符串"""
    return "—" if v is None else f"{v/1e4:,.{d}f}"


if __name__ == "__main__":
    d = build_v2_data()
    print(f"__V2 装配自检")
    print(f"  ORDER {len(d['ORDER'])} 单")
    print(f"  PROF 键 {list(d['PROF'][d['ORDER'][0]].keys())[:16]} …")
    print(f"  AUDIT 键 {list(d['AUDIT'].keys())}")
    print(f"  品种 {d['CAT']}")
    print(UNIT_POLICY)
