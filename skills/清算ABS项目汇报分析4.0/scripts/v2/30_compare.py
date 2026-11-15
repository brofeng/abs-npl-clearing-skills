# -*- coding: utf-8 -*-
r"""v2 · ③ 横向对照（#view-xcompare）—— v10 五板块重构。

模块契约（见 00_ctx.py）：
    CSS  : str  —— 该节样式（注入 <style>）
    HTML : str  —— 视图内容（**不含 <section> 外壳**，由 build_v2.py 包一层
                    <section class="view" id="view-xcompare">）
    JS   : str  —— 客户端增强，纯 IIFE 局部变量（不含 <script> 外壳）

五个板块（发行定价 → 回收去向 的链条）：
    01 四象限：实际回收率 × 处置费率，气泡 = 资产本金规模
    02 中债预测回收率 vs 实际回收率（45° 对角线 + 实际/预测比值分布）
    03 定价假设 vs 实际兑现 + 次级档超额收益
    04 回收款去向：全周期分配瀑布 + 逐期 100% 堆叠 + 科目帕累托
    05 定价思考：次级档固定资金成本倒算（n=8）+ 各家定价特点热力矩阵

数据门控（严格按 Lead 核实的可得性执行，不臆造 / 不补 0 / 不把推算值当披露值）：
    · 处置费率 PROF.disposeFeeRate 28/28；实际回收率 recRate 27/28（缺 邮盈惠兴2024年第四期，空心点＋n=27）
    · 气泡 = 资产本金规模 poolPrincipal 27/28（**不是发行规模**）
    · 中债预测回收率 expRecRate 27/28
    · **预测 XIRR 全样本不存在** → 03 标题为「定价假设 vs 实际兑现」；优先档用票面 cpSen，
      次级档「约定率」仅 8 单可由「固定资金成本 ÷ 次级发行规模 ÷ 期限」倒算（n=8）
    · 04 瀑布直接用 __V2.WF（00_ctx.build_waterfall 已重建，不在此重算）；逐期堆叠取
      payload.projects[].periods[].outflow；帕累托取 payload.projects[].alloc.cum
    · 05 次级固定资金成本：只有分配明细单列该科目的 8 单计入；其余 20 单「—」
    · 发行利差字段不存在 → 热力矩阵该列用「次级超额收益率」替代

集成约定：
    · 无 `<section>` 外壳；CSS 不写 `#view-xcompare` 前缀（组装器会 scope_css 再加一层）
    · `xc-` 类名前缀；JS 纯 IIFE；幂等；SVG 只写 viewBox + preserveAspectRatio（不写死 width/height）

独立运行： python 30_compare.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import statistics as st
import xml.etree.ElementTree as ET
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

# ══════════════════════════════════════════════════════════════════
# 0. 上下文 / 令牌
# ══════════════════════════════════════════════════════════════════
ROOT = _HOME / "清算28单_不良ABS分析"
V2DIR = ROOT / "脚本" / "v2"
ASSET = ROOT / "设计资产"
RAW = _HOME / "清算28单_单项目穿透" / "_校验件" / "payload.json"

CATS = ["信用卡不良", "个人消费贷款", "个人经营贷款"]
CAT_COLOR = {"信用卡不良": "#A52524", "个人消费贷款": "#2D3955", "个人经营贷款": "#1F7A5C"}

INK, INK2, INK3, INK4 = "#141A26", "#38425A", "#697487", "#98A2B3"
NAVY, RED, GREEN, WARN = "#2D3955", "#A52524", "#1F7A5C", "#B0763F"
GRID = "rgba(20,26,38,.07)"
SEN_C = "#6B7C9C"
SUB_C = "#1F7A5C"


def _ctxmod():
    try:
        spec = importlib.util.spec_from_file_location("_ctx00", V2DIR / "00_ctx.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_CTX = _ctxmod()
if _CTX is not None and isinstance(getattr(_CTX, "CAT_COLOR", None), dict):
    CAT_COLOR.update(_CTX.CAT_COLOR)


# ══════════════════════════════════════════════════════════════════
# 1. 数据装载
# ══════════════════════════════════════════════════════════════════
def _payload():
    return json.loads((ASSET / "payload_28.json").read_text(encoding="utf-8"))


def _audit():
    return json.loads((ASSET / "audit_payload.json").read_text(encoding="utf-8"))


def _raw():
    """原始 payload（逐期 outflow / alloc.cum）。读不到则返回 None，图表层降级。"""
    try:
        return json.loads(RAW.read_text(encoding="utf-8"))
    except Exception:
        return None


def _waterfall():
    """直接复用 00_ctx.build_waterfall()（v6 重建：分档兑付表 + 处置费剔除 + 残差）。"""
    if _CTX is not None and hasattr(_CTX, "build_waterfall"):
        try:
            return _CTX.build_waterfall()
        except Exception:
            return {}
    return {}


# 回收款去向：逐期堆叠的 4 类归并
PERIOD_GROUPS = [
    ("费用与税", "#B0763F", ("税费支出", "处置费用", "贷款服务机构报酬", "受托机构报酬",
                        "资金保管机构报酬", "代理兑付费用", "跟踪评级服务费",
                        "发行费用", "审计费", "其他费用支出", "流动性支持承诺费")),
    ("优先档本息", "#2D3955", ("优先档资产支持证券本金", "优先档资产支持证券利息")),
    ("次级档本息与收益", "#7FBFA8", ("次级档资产支持证券固定资金成本",
                            "次级档资产支持证券超额收益")),
    ("结转/转存", "#B6BECC", ("转存下期金额",)),
]


def _year(key):
    m = re.search(r"(20\d{2})年", key or "")
    return m.group(1) if m else "—"


def build_records():
    p = _payload()
    prof, order = p["PROF"], p["ORDER"]
    audit = _audit()
    wf = _waterfall()

    recs = []
    for i, k in enumerate(order):
        v = prof[k]
        r = {
            "i": i, "view": f"p{i}", "key": k, "short": v.get("short") or k,
            "cat": v.get("cat"), "bank": v.get("issuer"), "year": _year(k),
            "disp": v.get("disposeFee"), "dispRate": v.get("disposeFeeRate"),
            "rec": v.get("recRate"), "recovered": v.get("recovered"),
            "expRec": v.get("expRecRate"), "forecast": v.get("forecast"),
            "poolPrin": v.get("poolPrincipal"), "pool": v.get("poolTotal"),
            "issue": v.get("issue"), "sec": v.get("secRatio"),
            "cpSen": v.get("cpSen"), "xirrSen": v.get("xirrSen"), "xirrSub": v.get("xirrSub"),
            "sub": v.get("sub"), "subFixed": v.get("subFixed"),
            "subExcess": v.get("subExcess"), "subTotal": v.get("subTotal"),
            "months": v.get("months"), "subMultiple": v.get("subMultiple"),
            "wf": wf.get(k),
        }
        # 实际/预测 比值（02 辅助图；只算，不叫「达成率」）
        r["ratio"] = (r["rec"] / r["expRec"]) if (r["rec"] is not None and r["expRec"]) else None
        r["exYield"] = (r["subExcess"] / r["sub"]) if (r["subExcess"] is not None and r["sub"]) else None
        recs.append(r)
    return recs, audit


# ══════════════════════════════════════════════════════════════════
# 2. 统计 / 格式化
# ══════════════════════════════════════════════════════════════════
def _clean(xs):
    return [x for x in xs if x is not None]


def _med(xs):
    xs = _clean(xs)
    return st.median(xs) if xs else None


def _mean(xs):
    xs = _clean(xs)
    return sum(xs) / len(xs) if xs else None


def _q(xs, p):
    xs = sorted(_clean(xs))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = p * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _pearson(xs, ys):
    pr = [(a, b) for a, b in zip(xs, ys) if a is not None and b is not None]
    n = len(pr)
    if n < 3:
        return None
    mx = sum(a for a, _ in pr) / n
    my = sum(b for _, b in pr) / n
    sxy = sum((a - mx) * (b - my) for a, b in pr)
    sxx = sum((a - mx) ** 2 for a, _ in pr)
    syy = sum((b - my) ** 2 for _, b in pr)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _ols(xs, ys):
    pr = [(a, b) for a, b in zip(xs, ys) if a is not None and b is not None]
    n = len(pr)
    if n < 3:
        return None
    mx = sum(a for a, _ in pr) / n
    my = sum(b for _, b in pr) / n
    sxx = sum((a - mx) ** 2 for a, _ in pr)
    if sxx <= 0:
        return None
    k = sum((a - mx) * (b - my) for a, b in pr) / sxx
    return k, my - k * mx


def _nice_step(vmax, target=4):
    if not vmax or vmax <= 0:
        return 1.0
    raw = vmax / float(target)
    mag = 10.0 ** math.floor(math.log10(raw))
    for mult in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= mult * mag + 1e-12:
            return mult * mag
    return 10.0 * mag


def esc(s):
    return (str("" if s is None else s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def yi(v, d=2):
    return "—" if v is None else f"{v / 1e8:,.{d}f}"


def wan(v, d=0):
    return "—" if v is None else f"{v / 1e4:,.{d}f}"


def pct(v, d=2):
    return "—" if v is None else f"{v * 100:,.{d}f}%"


def num(v, d=2):
    return "—" if v is None else f"{v:,.{d}f}"


def bp(v):
    return "—" if v is None else f"{v * 10000:+,.0f} bp"


def amt(v):
    """金额自适应：≥1 亿 → x.xx 亿；≥1 万 → x.xx 万；否则元。"""
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e8:
        return f"{v / 1e8:,.2f} 亿"
    if a >= 1e4:
        return f"{v / 1e4:,.2f} 万"
    return f"{v:,.0f} 元"


def pp(v, d=2):
    return "—" if v is None else f"{v * 100:+.{d}f} pp"


def tip(head, lines):
    return "<title>" + esc(head + "｜" + "\n".join(str(x) for x in lines)) + "</title>"


def tx(x, y, s, cls="", anchor="", extra=""):
    a = f' text-anchor="{anchor}"' if anchor else ""
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}"{a}{c}{extra}>{esc(s)}</text>'


class Ax:
    def __init__(self, x0, y0, x1, y1, vx0, vx1, vy0, vy1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.vx0, self.vx1, self.vy0, self.vy1 = vx0, vx1, vy0, vy1

    def X(self, v):
        return self.x0 + (v - self.vx0) / (self.vx1 - self.vx0) * (self.x1 - self.x0)

    def Y(self, v):
        return self.y1 - (v - self.vy0) / (self.vy1 - self.vy0) * (self.y1 - self.y0)

    def set_y(self, a, b):
        self.vy0, self.vy1 = a, b


def _svg(w, h, label, body):
    return (f'<svg class="xc-svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" '
            f'role="img" aria-label="{esc(label)}">{body}</svg>')


def _r_size(val, vmin, vmax, rmin=3.0, rmax=17.0):
    if val is None or vmax <= vmin:
        return rmin
    t = max(0.0, min(1.0, (val - vmin) / (vmax - vmin)))
    return rmin + (rmax - rmin) * math.sqrt(t)


# ══════════════════════════════════════════════════════════════════
# 3. 聚合
# ══════════════════════════════════════════════════════════════════
class Ctx:
    def __init__(self, recs, audit):
        self.recs = recs
        self.audit = audit
        # 01：X 处置费率 28/28，Y 回收率 27/28
        self.q = [r for r in recs if r["rec"] is not None and r["dispRate"] is not None]
        self.gap = [r for r in recs if r["rec"] is None or r["dispRate"] is None]
        # 02：预测 27/28
        self.fc = [r for r in recs if r["expRec"] is not None and r["rec"] is not None]
        # 03：优先档 28（票面 & XIRR 均披露）；次级档 28（只读披露 XIRR，不做任何资金成本推导）
        self.pri = [r for r in recs if r["cpSen"] is not None and r["xirrSen"] is not None]
        self.subAll = [r for r in recs if r["xirrSub"] is not None]

        self.mDis = _med([r["dispRate"] for r in recs])
        self.mRec = _med([r["rec"] for r in recs])
        self.pp = [r["poolPrin"] for r in recs if r["poolPrin"]]
        self.pp_min, self.pp_max = (min(self.pp), max(self.pp)) if self.pp else (1, 1)

        self.r_dis_rec = _pearson([r["dispRate"] for r in recs], [r["rec"] for r in recs])
        self.fit = _ols([r["dispRate"] for r in recs], [r["rec"] for r in recs])
        self.r_fc = _pearson([r["expRec"] for r in recs], [r["rec"] for r in recs])
        self.ratios = [r["ratio"] for r in recs if r["ratio"] is not None]
        self.mRatio, self.aRatio = _med(self.ratios), _mean(self.ratios)
        self.r_ratio_rec = _pearson([r["ratio"] for r in recs], [r["rec"] for r in recs])

        # 03 偏差（只有优先档：实际 XIRR − 票面；票面=定价假设，XIRR=现金流口径）
        for r in recs:
            r["devPri"] = (r["xirrSen"] - r["cpSen"]) if (r["cpSen"] is not None) else None
            r["diff"] = (r["rec"] - r["expRec"]) if (r["rec"] is not None and r["expRec"] is not None) else None
        self.devPri = [abs(r["devPri"]) for r in self.pri]
        self.pri_by_cp = sorted(self.pri, key=lambda r: -(r["cpSen"] or 0))       # 票面降序
        self.pri_by_dev = sorted(self.pri, key=lambda r: -(abs(r["devPri"]) if r["devPri"] is not None else -1))
        # 02 差异摘要（图外 2 行）
        self.diff_rows = [r for r in recs if r["diff"] is not None]
        self.diff_hi = sorted(self.diff_rows, key=lambda r: -r["diff"])[:3]
        self.diff_lo = sorted(self.diff_rows, key=lambda r: r["diff"])[:3]
        # 03 次级 XIRR 披露值
        self.sub_med = _med([r["xirrSub"] for r in self.subAll])
        self.sub_min = min((r["xirrSub"] for r in self.subAll), default=None)
        self.sub_max = max((r["xirrSub"] for r in self.subAll), default=None)
        self.sub_rows = []
        for b in sorted({r["bank"] for r in recs}):
            g = [r for r in self.subAll if r["bank"] == b]
            if not g:
                continue
            self.sub_rows.append({"bank": b, "recs": g,
                                  "med": _med([r["xirrSub"] for r in g])})
        self.sub_rows.sort(key=lambda x: -(x["med"] or 0))
        # 03 超额收益 Top10 + Bottom5
        self.exc_sorted = sorted(recs, key=lambda r: -(r["subExcess"] or 0))
        self.exc_top = self.exc_sorted[:10]
        self.exc_bot = list(reversed(self.exc_sorted[-5:]))
        self.exc_rest = self.exc_sorted[10:-5]

        # 04 瀑布聚合（用 WF，不重算）
        self.wf_agg = {}
        self.wf_rec = 0.0
        self.wf_res = 0.0
        self.wf_n = 0
        for r in recs:
            w = r["wf"]
            if not w:
                continue
            self.wf_n += 1
            self.wf_rec += w["rec"]
            self.wf_res += w["residual"]
            for s in w["steps"]:
                if s["kind"] == "in":
                    continue
                self.wf_agg[s["label"]] = self.wf_agg.get(s["label"], 0.0) + s["value"]
        self.wf_disp = self.wf_agg.get("处置费用", 0.0)
        self.wf_out = sum(self.wf_agg.values())
        # 期末残差为聚合残差
        self.wf_end = self.wf_rec - self.wf_out
        self.wf_dbl_n = sum(1 for r in recs if r["wf"] and r["wf"].get("dbl"))

        # 04 逐期堆叠
        raw = _raw()
        self.per_cat = [(g[0], g[1]) for g in PERIOD_GROUPS]
        self.per_rows = []
        self.per_n = {}
        if raw:
            acc = {}
            stk = {}
            for pr in raw.get("projects") or []:
                for idx, pe in enumerate(pr.get("periods") or []):
                    key = idx + 1
                    if key > 12:
                        key = 13
                    d = acc.setdefault(key, {c[0]: 0.0 for c in PERIOD_GROUPS})
                    stk[key] = stk.get(key, 0) + 1
                    for o in (pe.get("outflow") or []):
                        lab = o.get("label")
                        amt = o.get("amount") or 0.0
                        for gname, _col, labs in PERIOD_GROUPS:
                            if lab in labs:
                                d[gname] += amt
                                break
            for key in sorted(acc):
                d = acc[key]
                tot = sum(d.values())
                if tot <= 0:
                    continue
                self.per_rows.append({
                    "label": ("第1–12期" if key == 13 else f"第{key}期"),
                    "n": stk[key], "tot": tot,
                    "shares": {c[0]: d[c[0]] / tot for c in PERIOD_GROUPS},
                    "raw": d,
                })
        self.per_n = {r["label"]: r["n"] for r in self.per_rows}

        # 04 帕累托
        self.par_rows = []
        if raw:
            cum = {}
            for pr in raw.get("projects") or []:
                for lab, v in ((pr.get("alloc") or {}).get("cum") or {}).items():
                    cum[lab] = cum.get(lab, 0.0) + (v or 0.0)
            self.par_total = sum(cum.values())
            run = 0.0
            for lab, v in sorted(cum.items(), key=lambda x: -x[1]):
                if v <= 0:
                    continue
                run += v
                self.par_rows.append({"label": lab, "v": v,
                                      "share": v / self.par_total,
                                      "cum": run / self.par_total})
        else:
            self.par_total = 0.0
        self.par_80 = next((x for x in self.par_rows if x["cum"] >= 0.80), None)

        # 05 各家实际各单 IRR 点评（只用披露字段：cpSen / xirrSen / xirrSub / subExcess / recRate）
        self.banks = []
        for b in sorted({r["bank"] for r in recs}):
            g = [r for r in recs if r["bank"] == b]
            sen = _clean([r["xirrSen"] for r in g])
            sub = _clean([r["xirrSub"] for r in g])
            self.banks.append({
                "bank": b, "n": len(g), "recs": g,
                "sen_med": _med(sen), "sen_min": min(sen) if sen else None, "sen_max": max(sen) if sen else None,
                "sub_med": _med(sub), "sub_min": min(sub) if sub else None, "sub_max": max(sub) if sub else None,
                "miss": (len([r for r in g if r["xirrSen"] is None]),
                         len([r for r in g if r["xirrSub"] is None])),
                "exc": _med([r["subExcess"] for r in g]),
                "issue": sum(r["issue"] for r in g if r["issue"]),
                "cats": sorted({r["cat"] for r in g}),
            })
        self.banks.sort(key=lambda r: -r["issue"])
        self.cats_agg = []
        for cat in CATS:
            g = [r for r in recs if r["cat"] == cat]
            if not g:
                continue
            sen = _clean([r["xirrSen"] for r in g])
            sub = _clean([r["xirrSub"] for r in g])
            self.cats_agg.append({
                "cat": cat, "n": len(g),
                "sen_med": _med(sen), "sen_min": min(sen) if sen else None, "sen_max": max(sen) if sen else None,
                "sub_med": _med(sub), "sub_min": min(sub) if sub else None, "sub_max": max(sub) if sub else None,
            })
        # 异常单（各最多 3 单，只列披露值）
        self.anom = {
            "sen_hi": sorted([r for r in recs if r["xirrSen"] is not None], key=lambda r: -r["xirrSen"])[:3],
            "sen_lo": sorted([r for r in recs if r["xirrSen"] is not None], key=lambda r: r["xirrSen"])[:3],
            "sub_hi": sorted([r for r in recs if r["xirrSub"] is not None], key=lambda r: -r["xirrSub"])[:3],
            "sub_lo": sorted([r for r in recs if r["xirrSub"] is not None], key=lambda r: r["xirrSub"])[:3],
        }
        # 04 费用类帕累托（只含费用科目，本金/利息不入主图）
        fee_labels = ["处置费用", "贷款服务机构报酬", "税费支出", "受托机构报酬", "发行费用",
                      "资金保管机构报酬", "审计费", "跟踪评级服务费", "代理兑付费用", "其他费用支出"]
        self.fee_rows = []
        raw2 = raw
        if raw2:
            cum = {}
            for pr in raw2.get("projects") or []:
                for lab, v in ((pr.get("alloc") or {}).get("cum") or {}).items():
                    if lab in fee_labels:
                        cum[lab] = cum.get(lab, 0.0) + (v or 0.0)
            self.fee_total = sum(cum.values())
            run = 0.0
            for lab, v in sorted(cum.items(), key=lambda x: -x[1]):
                run += v
                self.fee_rows.append({"label": lab, "v": v, "share": v / self.fee_total if self.fee_total else 0,
                                      "cum": run / self.fee_total if self.fee_total else 0})
        else:
            self.fee_total = 0.0


# ══════════════════════════════════════════════════════════════════
# 4. 01 四象限：实际回收率 × 处置费率
# ══════════════════════════════════════════════════════════════════
XD0, XD1 = 0.0, 0.50          # 处置费率
YD0, YD1 = 0.0, 0.48          # 实际回收率
QUAD = {
    "HI-X/HI-Y": ("高处置费率 · 高回收", "回收厚但被处置费切走更多"),
    "LO-X/HI-Y": ("低处置费率 · 高回收", "费用效率最优 → 双优"),
    "HI-X/LO-Y": ("高处置费率 · 低回收", "回收薄且费用重 → 双弱"),
    "LO-X/LO-Y": ("低处置费率 · 低回收", "回收偏弱但费用轻"),
}


def _bub(r, ctx, ax, rmax=17.0, cls="xc-b"):
    rad = _r_size(r["poolPrin"], ctx.pp_min, ctx.pp_max, 3.0, rmax)
    body = [f'{r["bank"]} ／ {r["cat"]} ／ {r["year"]}',
            f'处置费率 {pct(r["dispRate"])}',
            f'实际回收率 {pct(r["rec"])}' if r["rec"] is not None else "实际回收率 缺失（—）",
            f'资产本金规模 {yi(r["poolPrin"])} 亿' if r["poolPrin"] else "资产本金规模 缺失（—）"]
    return (f'<circle class="{cls}" cx="{ax.X(r["dispRate"]):.1f}" cy="{ax.Y(r["rec"]):.1f}" '
            f'r="{rad:.1f}" fill="{CAT_COLOR.get(r["cat"], NAVY)}" data-cat="{esc(r["cat"])}" '
            f'data-bank="{esc(r["bank"])}" data-view="{r["view"]}">'
            f'{tip(r["key"], body)}</circle>')


def svg_q_main(ctx, W=1300, H=430):
    RX = W - 292
    ax = Ax(64, 26, RX - 18, H - 62, XD0, XD1, YD0, YD1)
    b = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.x1 - ax.x0}" height="{ax.y1 - ax.y0}" class="xc-frame"/>']
    for t in [0, .1, .2, .3, .4]:
        y = ax.Y(t)
        b.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x1}" y2="{y:.1f}" class="xc-gl"/>')
        b.append(tx(ax.x0 - 8, y + 3.5, pct(t, 0), "xc-tk", "end"))
    for t in [0, .1, .2, .3, .4, .5]:
        x = ax.X(t)
        b.append(f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y1}" class="xc-gl"/>')
        b.append(tx(x, ax.y1 + 16, pct(t, 0), "xc-tk", "middle"))
    b.append(f'<line x1="{ax.x0}" y1="{ax.y1}" x2="{ax.x1}" y2="{ax.y1}" class="xc-axis"/>')
    b.append(f'<line x1="{ax.x0}" y1="{ax.y0}" x2="{ax.x0}" y2="{ax.y1}" class="xc-axis"/>')
    b.append(tx((ax.x0 + ax.x1) / 2, H - 18, "处置费率 = 处置费用 / 累计回收", "xc-axt", "middle"))
    b.append(f'<text class="xc-axt" x="16" y="{(ax.y0 + ax.y1) / 2:.1f}" text-anchor="middle" '
             f'transform="rotate(-90 16 {(ax.y0 + ax.y1) / 2:.1f})">实际回收率 = 累计回收 / 入池本息费</text>')
    if ctx.fit:
        k, bb = ctx.fit
        b.append(f'<line x1="{ax.X(XD0):.1f}" y1="{ax.Y(k * XD0 + bb):.1f}" x2="{ax.X(XD1):.1f}" '
                 f'y2="{ax.Y(k * XD1 + bb):.1f}" class="xc-fit">'
                 f'{tip("最小二乘趋势线", [f"斜率 {k:.3f}", f"Pearson r = {num(ctx.r_dis_rec, 3)}", f"n = {len(ctx.q)}"])}</line>')
    mx, my = ax.X(ctx.mDis), ax.Y(ctx.mRec)
    mt = tip("中位参考线", [f"中位处置费率 {pct(ctx.mDis)}", f"中位实际回收率 {pct(ctx.mRec)}", f"n = {len(ctx.q)}"])
    b.append(f'<line x1="{mx:.1f}" y1="{ax.y0}" x2="{mx:.1f}" y2="{ax.y1}" class="xc-med">{mt}</line>')
    b.append(f'<line x1="{ax.x0}" y1="{my:.1f}" x2="{ax.x1}" y2="{my:.1f}" class="xc-med">{mt}</line>')
    for q, (anchor, x, y) in {
        "HI-X/HI-Y": ("end", ax.x1 - 8, ax.y0 + 18),
        "LO-X/HI-Y": ("start", ax.x0 + 8, ax.y0 + 18),
        "HI-X/LO-Y": ("end", ax.x1 - 8, ax.y1 - 10),
        "LO-X/LO-Y": ("start", ax.x0 + 8, ax.y1 - 10),
    }.items():
        b.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" class="xc-qlab">'
                 f'{tip(QUAD[q][0], [QUAD[q][1]])}{esc(QUAD[q][0])}</text>')
    for r in sorted(ctx.q, key=lambda z: -(z["poolPrin"] or 0)):
        b.append(_bub(r, ctx, ax))
    for r in ctx.gap:
        x = ax.X(r["dispRate"])
        _dr = pct(r["dispRate"])
        _gt = tip(r["key"], ["缺失：实际回收率 / 资产本金规模 未披露", "处置费率 " + _dr, "不参与四象限定位与统计"])
        b.append(f'<circle class="xc-b xc-bgap" cx="{x:.1f}" cy="{ax.y1 - 4:.1f}" r="7" '
                 f'style="fill:none;stroke:{CAT_COLOR.get(r["cat"], NAVY)}" data-cat="{esc(r["cat"])}" '
                 f'data-bank="{esc(r["bank"])}" data-view="{r["view"]}">{_gt}</circle>')
        b.append(f'<line x1="{x:.1f}" y1="{ax.y1 - 12:.1f}" x2="{x:.1f}" y2="{ax.y1:.1f}" class="xc-gapsep"/>')
        b.append(tx(x + 6, ax.y1 - 14, "缺失", "xc-gapsub"))
    nano = []
    _hx = max(ctx.q, key=lambda z: z["dispRate"])
    _hy = max(ctx.q, key=lambda z: z["rec"])
    nano.append((_hx, f'处置费率最高 {pct(_hx["dispRate"])}', -14, -18, "end"))
    nano.append((_hy, f'回收率最高 {pct(_hy["rec"])}', 14, 22, "start"))
    for i, r in enumerate(sorted(ctx.q, key=lambda z: -(z["poolPrin"] or 0))[:3]):
        nano.append((r, f'规模 Top{i + 1}：{yi(r["poolPrin"])} 亿', 14, (-30, 34, 58)[i], "start"))
    b.append('<g class="xc-annos">')
    for r, label, dx, dy, anc in nano:
        px, py = ax.X(r["dispRate"]), ax.Y(r["rec"])
        tx_, ty_ = px + dx, py + dy
        b.append(f'<g class="xc-ag" data-cat="{esc(r["cat"])}">'
                 f'<line class="xc-leader" x1="{px:.1f}" y1="{py:.1f}" x2="{tx_ - (10 if anc == "start" else -10):.1f}" y2="{ty_ - 4:.1f}"/>'
                 f'<text x="{tx_:.1f}" y="{ty_:.1f}" text-anchor="{anc}" class="xc-anno">'
                 f'{tip(r["short"], [label, r["bank"]])}{esc(r["short"] + "：" + label)}</text></g>')
    b.append('</g>')
    b.append(tx(RX, 40, f"n = {len(ctx.q)}", "xc-lgttl"))
    b.append(tx(RX, 60, f"r = {num(ctx.r_dis_rec, 2)}", "xc-lgt"))
    b.append(tx(RX, 80, f"中位 X {pct(ctx.mDis)}", "xc-lgt"))
    b.append(tx(RX, 98, f"中位 Y {pct(ctx.mRec)}", "xc-lgt"))
    b.append(tx(RX, 134, "气泡 = 资产本金规模", "xc-lgttl"))
    for i, v in enumerate([0.1, 0.5, 1.0]):
        rr = _r_size(v * ctx.pp_max, ctx.pp_min, ctx.pp_max, 3.0, 17.0)
        b.append(f'<circle cx="{RX + 14 + i * 44}" cy="{176}" r="{max(2.5, rr * 0.8):.1f}" class="xc-lgcirc"/>')
        b.append(tx(RX + 14 + i * 44, 198, f'{num(v, 1)}×', "xc-minisub", "middle"))
    b.append(tx(RX, 232, "空心点 = 回收率缺失", "xc-minisub"))
    return _svg(W, H, "实际回收率与处置费率四象限", "".join(b))
def svg_q_mini(ctx, cat, W=420, H=268):
    ax = Ax(44, 24, 396, 216, XD0, XD1, YD0, YD1)
    col = CAT_COLOR[cat]
    rows = [r for r in ctx.q if r["cat"] == cat]
    b = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.x1 - ax.x0}" height="{ax.y1 - ax.y0}" class="xc-frame"/>']
    for t in [0, .1, .2, .3, .4]:
        y = ax.Y(t)
        b.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x1}" y2="{y:.1f}" class="xc-gl"/>')
        b.append(tx(ax.x0 - 6, y + 3, pct(t, 0), "xc-tk", "end"))
    for t in [0, .1, .2, .3, .4]:
        x = ax.X(t)
        b.append(f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y1}" class="xc-gl"/>')
        b.append(tx(x, ax.y1 + 14, pct(t, 0), "xc-tk", "middle"))
    md = _med([r["dispRate"] for r in rows])
    mr = _med([r["rec"] for r in rows])
    if md is not None and mr is not None:
        b.append(f'<line x1="{ax.X(md):.1f}" y1="{ax.y0}" x2="{ax.X(md):.1f}" y2="{ax.y1}" stroke="{col}" class="xc-med2"/>')
        b.append(f'<line x1="{ax.x0}" y1="{ax.Y(mr):.1f}" x2="{ax.x1}" y2="{ax.Y(mr):.1f}" stroke="{col}" class="xc-med2"/>')
    for r in sorted(rows, key=lambda z: -(z["poolPrin"] or 0)):
        b.append(_bub(r, ctx, ax, rmax=9.0))
    b.append(tx(ax.x0, 14, cat, "xc-minit", "start", f' fill="{col}"'))
    b.append(tx(ax.x1, 14, f'n={len(rows)}', "xc-minisub", "end"))
    return _svg(W, H, f"{cat} 处置费率与回收率", "".join(b))


def _table_metrics(ctx):
    rows = sorted(ctx.recs, key=lambda r: -(r["dispRate"] or 0))
    out = ['<div class="xc-caption">附：28 单指标明细 —— 证券化率 ＝ 发行规模 / 入池本息费，'
           '仅作参考列（本页横轴为处置费率，不用证券化率）</div>'
           '<div class="xc-scroll"><table class="xc-tbl" id="xc-tbl"><thead><tr>'
           '<th class="l">项目</th><th class="l">发起机构</th><th class="l">品种</th>'
           '<th data-sort="year">发行年份</th><th data-sort="disp">处置费率</th>'
           '<th data-sort="rec">实际回收率</th>'
           '<th data-sort="pp">资产本金规模<span class="u"> 亿元</span></th>'
           '<th data-sort="sec">证券化率<span class="u"> 辅助字段</span></th></tr></thead><tbody>']
    for r in rows:
        out.append(
            f'<tr class="xc-trow" data-cat="{esc(r["cat"])}">'
            f'<td class="l">{esc(r["short"])}</td><td class="l">{esc(r["bank"])}</td>'
            f'<td class="l"><span class="xc-cat" style="--c:{CAT_COLOR.get(r["cat"], NAVY)}">{esc(r["cat"])}</span></td>'
            f'<td class="n" data-k="year" data-v="{r["year"]}">{r["year"]}</td>'
            f'<td class="n" data-k="disp" data-v="{r["dispRate"] if r["dispRate"] is not None else ""}">{pct(r["dispRate"])}</td>'
            f'<td class="n" data-k="rec" data-v="{r["rec"] if r["rec"] is not None else ""}">{pct(r["rec"])}</td>'
            f'<td class="n" data-k="pp" data-v="{r["poolPrin"] if r["poolPrin"] else ""}">{yi(r["poolPrin"])}</td>'
            f'<td class="n" data-k="sec" data-v="{r["sec"] if r["sec"] is not None else ""}">{pct(r["sec"])}</td></tr>')
    out.append('</tbody></table></div>')
    return "".join(out)


# ══════════════════════════════════════════════════════════════════
# 5. 02 中债预测回收率 vs 实际回收率
# ══════════════════════════════════════════════════════════════════
def svg_fc_scatter(ctx, W=860, H=410):
    """02 主图：45° 对角线散点；项目级差异只在 tooltip，图内零文字标签。"""
    top = 0.52
    ax = Ax(64, 22, 640, 352, 0.0, top, 0.0, top)
    b = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.x1 - ax.x0}" height="{ax.y1 - ax.y0}" class="xc-frame"/>']
    for t in [0, .1, .2, .3, .4, .5]:
        y, x = ax.Y(t), ax.X(t)
        b.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x1}" y2="{y:.1f}" class="xc-gl"/>')
        b.append(tx(ax.x0 - 8, y + 3, pct(t, 0), "xc-tk", "end"))
        b.append(f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y1}" class="xc-gl"/>')
        b.append(tx(x, ax.y1 + 15, pct(t, 0), "xc-tk", "middle"))
    for k, lab in ((1.2, "120%"), (0.8, "80%")):
        xa = ax.X(top if k <= 1 else top / k)
        b.append(f'<line x1="{ax.X(0):.1f}" y1="{ax.Y(0):.1f}" x2="{xa:.1f}" y2="{ax.Y(top if k <= 1 else top / k):.1f}" '
                 f'class="xc-fcb">{tip(lab + " 参考线", ["实际回收率 = " + lab + " × 中债预测回收率"])}</line>')
    b.append(f'<line x1="{ax.X(0):.1f}" y1="{ax.Y(0):.1f}" x2="{ax.X(top):.1f}" y2="{ax.Y(top):.1f}" class="xc-diag">'
             f'{tip("y = x（45° 对角线）", ["实际回收率 = 中债预测回收率", "线上方＝好于预测，线下方＝不及预测"])}</line>')
    b.append(tx((ax.x0 + ax.x1) / 2, 392, "中债预测回收率 = 预测回收额 / 入池本息费", "xc-axt", "middle"))
    b.append(f'<text class="xc-axt" x="16" y="{(ax.y0 + ax.y1) / 2:.1f}" text-anchor="middle" '
             f'transform="rotate(-90 16 {(ax.y0 + ax.y1) / 2:.1f})">实际回收率 = 累计回收 / 入池本息费</text>')
    top5 = sorted(ctx.fc, key=lambda z: -abs(z["diff"] or 0))[:5]
    top5k = {r["key"] for r in top5}
    for r in sorted(ctx.fc, key=lambda z: -z["issue"]):
        rad = _r_size(r["poolPrin"], ctx.pp_min, ctx.pp_max, 3.0, 15.0)
        st = "已披露" if (r["rec"] is not None and r["expRec"] is not None) else "缺失"
        tip_lines = [
            f'{r["bank"]} ／ {r["cat"]} ／ {r["year"]}',
            f'预测回收率 {pct(r["expRec"])}',
            f'实际回收率 {pct(r["rec"])}',
            f'差异（实际 − 预测）{pp(r["diff"])}',
            f'样本状态 {st}',
        ]
        b.append(f'<circle class="xc-b" cx="{ax.X(r["expRec"]):.1f}" cy="{ax.Y(r["rec"]):.1f}" r="{rad:.1f}" '
                 f'fill="{CAT_COLOR.get(r["cat"], NAVY)}" data-cat="{esc(r["cat"])}" data-bank="{esc(r["bank"])}" '
                 f'data-view="{r["view"]}">'
                 f'{tip(r["key"], tip_lines)}</circle>')
        if r["key"] in top5k:
            extra = ["偏离最大 5 单之一", "差异 " + pp(r["diff"])]
            b.append(f'<circle cx="{ax.X(r["expRec"]):.1f}" cy="{ax.Y(r["rec"]):.1f}" r="{rad + 3.4:.1f}" '
                     f'fill="none" stroke="#A52524" stroke-width="1.5" opacity=".85">'
                     f'{tip(r["key"], extra)}</circle>')
    b.append(tx(656, 40, f'n={len(ctx.fc)}', "xc-lgttl"))
    b.append(tx(656, 58, f'r = {num(ctx.r_fc, 2)}', "xc-lgt"))
    b.append(tx(656, 76, f'比值中位 {num(ctx.mRatio, 2)}', "xc-lgt"))
    b.append(tx(656, 112, "红环 =", "xc-lgttl"))
    b.append(tx(656, 130, "偏离最大 5 单", "xc-lgttl"))
    b.append(tx(656, 148, "（无文字标签）", "xc-minisub"))
    return _svg(W, H, "中债预测回收率与实际回收率散点", "".join(b))


def diff_note(ctx):
    """02 图外 2 行差异摘要（不压在图内）。"""
    if not ctx.diff_rows:
        return ""
    hi = "、".join(f'{"<b>" if i == 0 else ""}{esc(r["short"])} {pp(r["diff"])}</b>' if i == 0 else f'{esc(r["short"])} {pp(r["diff"])}' for i, r in enumerate(ctx.diff_hi))
    lo = "、".join(f'{esc(r["short"])} {pp(r["diff"])}' for r in ctx.diff_lo)
    return (f'<div class="xc-note2"><b>差异最大 Top3</b>：{hi}<br><b>最小 Top3</b>：{lo}'
            f'<span class="u-hint">（差异 = 实际回收率 − 中债预测回收率，pp；完整读数见悬停）</span></div>')


def svg_fc_ratio(ctx):
    W, H = 420, 410
    vals = ctx.ratios
    lo, hi = 0.5, 1.5
    bins = 10
    cnt = [0] * bins
    for v in vals:
        t = min(max(v, lo), hi - 1e-9)
        cnt[int((t - lo) / (hi - lo) * bins)] += 1
    nmax = max(cnt) or 1
    ax = Ax(44, 50, 392, 330, lo, hi, 0, nmax)
    b = []
    base, top = 330, 50
    b.append(f'<line x1="{ax.x0}" y1="{base}" x2="{ax.x1}" y2="{base}" class="xc-axis"/>')
    for i, c in enumerate(cnt):
        x0 = ax.X(lo + (hi - lo) * i / bins)
        x1 = ax.X(lo + (hi - lo) * (i + 1) / bins)
        h = 0 if c == 0 else max(3.0, (base - top) * c / nmax)
        col = "#1F7A5C" if (lo + (hi - lo) * (i + 0.5) / bins) >= 1.0 else "#B0763F"
        b.append(f'<rect x="{x0 + 1:.1f}" y="{base - h:.1f}" width="{max(2.0, x1 - x0 - 2):.1f}" '
                 f'height="{h:.1f}" rx="2" fill="{col}" opacity=".82">'
                 f'{tip(f"比值 {(lo + (hi - lo) * i / bins):.2f}–{(lo + (hi - lo) * (i + 1) / bins):.2f}", [f"{c} 单"])}</rect>')
        if c:
            b.append(tx((x0 + x1) / 2, base - h - 5, str(c), "xc-barval", "middle"))
    for t in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]:
        x = ax.X(t)
        b.append(tx(x, base + 14, num(t, 1), "xc-tk", "middle"))
    # 1.0 参考线 + 中位
    b.append(f'<line x1="{ax.X(1.0):.1f}" y1="{top}" x2="{ax.X(1.0):.1f}" y2="{base}" class="xc-diag">'
             f'{tip("比值 = 1.0", ["实际 = 预测"])}</line>')
    b.append(f'<line x1="{ax.X(ctx.mRatio):.1f}" y1="{top}" x2="{ax.X(ctx.mRatio):.1f}" y2="{base}" class="xc-med">'
             f'{tip("比值中位数", [num(ctx.mRatio, 3), f"n = {len(vals)}"])}</line>')
    b.append(tx(ax.x0, 22, "实际 / 预测 比值分布（直方图，10 桶）", "xc-minit"))
    b.append(tx(ax.x0, 368, f'中位 {num(ctx.mRatio, 3)} ／ 均值 {num(ctx.aRatio, 3)} ／ n={len(vals)}', "xc-lgt"))
    b.append(tx(ax.x0, 386, "比值 >1.2 或 <0.8 的单需单独核对口径", "xc-minisub"))
    return _svg(W, H, "实际与预测回收率比值分布", "".join(b))


# ══════════════════════════════════════════════════════════════════
# 6. 03 定价假设 vs 实际兑现
# ══════════════════════════════════════════════════════════════════


def svg03_pri_bars(ctx, W=1300, H=470):
    """03-1：优先档票面利率排序条形 + XIRR 圆点叠加（28 单，票面降序）。"""
    rows = ctx.pri_by_cp
    L, R = 196, 980
    top, bot = 34, 396
    ax = Ax(L, top, R, bot, 0.019, 0.0335, 0, 1)
    b = []
    for t in [0.020, 0.022, 0.024, 0.026, 0.028, 0.030, 0.032]:
        x = ax.X(t)
        b.append(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{bot + 4}" class="xc-gl"/>')
        b.append(tx(x, bot + 22, pct(t, 1), "xc-tk", "middle"))
    pitch = (bot - top) / len(rows)
    bh = max(5.0, pitch * 0.46)
    for i, r in enumerate(rows):
        y = top + pitch * i + pitch / 2
        x1 = ax.X(r["cpSen"])
        xd = ax.X(r["xirrSen"])
        head = f'{r["key"]} · 优先档'
        lines = [f'{r["bank"]} ／ {r["cat"]}',
                 f'票面（定价假设） {pct(r["cpSen"])}',
                 f'优先档 XIRR（现金流口径） {pct(r["xirrSen"])}',
                 f'偏差 {bp(r["devPri"])}']
        b.append(f'<g class="xc-xrow" data-cat="{esc(r["cat"])}">'
                 f'<text x="{L - 10}" y="{y + 4:.1f}" text-anchor="end" class="xc-rn">{esc(r["short"])}</text>'
                 f'<rect x="{ax.x0:.1f}" y="{y - bh / 2:.1f}" width="{max(1.5, x1 - ax.x0):.1f}" '
                 f'height="{bh:.1f}" rx="2" fill="{SEN_C}" opacity=".55">{tip(head, lines)}</rect>'
                 f'<circle cx="{xd:.1f}" cy="{y:.1f}" r="4.6" fill="{CAT_COLOR.get(r["cat"], NAVY)}">'
                 f'{tip(head, lines)}</circle>'
                 f'<text x="{R + 24}" y="{y + 4:.1f}" class="xc-rv">{pct(r["cpSen"])} → {pct(r["xirrSen"])}</text>'
                 f'<text x="{W - 14}" y="{y + 4:.1f}" text-anchor="end" class="xc-rv">{bp(r["devPri"])}</text>'
                 f'</g>')
    span = max(r["cpSen"] for r in rows) - min(r["cpSen"] for r in rows)
    b.append(tx(L, 18, "优先档｜横向条 = 票面利率（定价假设）　圆点 = 优先档 XIRR（现金流口径）｜28 单按票面降序", "xc-lgttl"))
    b.append(tx(W - 14, 18, "右列 = 偏差", "xc-lgttl", "end"))
    b.append(tx(L, bot + 44, f"票面区间 {pct(min(r['cpSen'] for r in rows))}–{pct(max(r['cpSen'] for r in rows))}"
                             f"（跨度 {num(span * 10000, 0)} bp）；偏差仅 {bp(min(r['devPri'] for r in rows))} ~ "
                             f"{bp(max(r['devPri'] for r in rows))}", "xc-minisub"))
    return _svg(W, H, "优先档票面利率与 XIRR 叠加", "".join(b))


def svg03_dev_strip(ctx, W=620, H=300):
    """03-2：优先档 |偏差| 分布点条（bp 刻度，n=28）。"""
    vals = ctx.devPri
    if not vals:
        return _svg(W, H, "优先档偏差分布", tx(20, 40, "无样本", "xc-lgt"))
    hi_bp = max(4, int(math.ceil(max(vals) * 10000 * 1.1)))
    if hi_bp % 2:
        hi_bp += 1
    lo, hi = 0.0, hi_bp / 10000.0
    ax = Ax(64, 70, W - 60, 210, lo, hi, 0, 1)
    b = [tx(64, 26, "优先档 |偏差| 分布（bp 刻度）", "xc-minit")]
    b.append(f'<line x1="{ax.x0}" y1="{ax.y1}" x2="{ax.x1}" y2="{ax.y1}" class="xc-axis"/>')
    for tbp in (0, hi_bp // 2, hi_bp):
        b.append(tx(ax.X(tbp / 10000.0), ax.y1 + 22, str(int(tbp)), "xc-tk", "middle"))
    m = _med(vals)
    b.append(f'<line x1="{ax.X(m):.1f}" y1="{ax.y0 + 6}" x2="{ax.X(m):.1f}" y2="{ax.y1 + 8}" class="xc-medtick" stroke="{RED}">'
             f'{tip("中位数", [bp(m), f"n={len(vals)}"])}</line>')
    for i, v in enumerate(sorted(vals)):
        b.append(f'<circle cx="{ax.X(v):.1f}" cy="{ax.y1 - 26 + (i % 5) * 9:.1f}" r="2.8" fill="{RED}" opacity=".6">'
                 f'{tip("优先档 |偏差|", [bp(v)])}</circle>')
    b.append(tx(64, 262, f'中位 {bp(m)} ／ 最大 {bp(max(vals))} ／ n={len(vals)}', "xc-lgt"))
    b.append(tx(64, 284, "偏差 = 实际 XIRR − 票面（bp）", "xc-minisub"))
    return _svg(W, H, "优先档偏差分布", "".join(b))


def svg03_sub_dist(ctx, W=620, H=316):
    """03-3：次级档 XIRR 披露值分布（28 单，按银行分行；只读披露值）。"""
    rows = ctx.sub_rows
    if not rows:
        return _svg(W, H, "次级档 XIRR 分布", tx(20, 40, "无样本", "xc-lgt"))
    x0, x1 = 0.07, 0.30
    ax = Ax(104, 44, W - 52, 244, x0, x1, 0, 1)
    b = [tx(104, 26, "次级档 XIRR 披露值分布（按发起机构分行）", "xc-minit")]
    for t in [0.10, 0.15, 0.20, 0.25]:
        x = ax.X(t)
        b.append(f'<line x1="{x:.1f}" y1="{ax.y0 - 6}" x2="{x:.1f}" y2="{ax.y1 + 4}" class="xc-gl"/>')
        b.append(tx(x, ax.y1 + 18, pct(t, 0), "xc-tk", "middle"))
    m = ctx.sub_med
    b.append(f'<line x1="{ax.X(m):.1f}" y1="{ax.y0 - 6}" x2="{ax.X(m):.1f}" y2="{ax.y1 + 4}" class="xc-diag">'
             f'{tip("全样本中位", [pct(m), f"n={len(ctx.subAll)}"])}</line>')
    pitch = (ax.y1 - ax.y0) / len(rows)
    for i, row in enumerate(rows):
        y = ax.y0 + pitch * i + pitch / 2
        b.append(f'<text x="{ax.x0 - 10}" y="{y + 4:.1f}" text-anchor="end" class="xc-rn">{esc(row["bank"])}</text>')
        for r in row["recs"]:
            tip_lines = [f'{r["bank"]} ／ {r["cat"]}',
                         f'次级档 XIRR {pct(r["xirrSub"])}',
                         f'回报倍数 {num(r["subMultiple"], 3)}',
                         "披露状态：已披露"]
            b.append(f'<circle cx="{ax.X(r["xirrSub"]):.1f}" cy="{y:.1f}" r="4.0" '
                     f'fill="{CAT_COLOR.get(r["cat"], NAVY)}" opacity=".82">'
                     f'{tip(r["key"], tip_lines)}</circle>')
        b.append(f'<line x1="{ax.X(row["med"]):.1f}" y1="{y - 5:.1f}" x2="{ax.X(row["med"]):.1f}" y2="{y + 5:.1f}" '
                 f'stroke="{INK3}" stroke-width="1.6"/>')
    b.append(tx(104, 296, f'全样本 {pct(ctx.sub_min)}–{pct(ctx.sub_max)}，中位 {pct(ctx.sub_med)}，n={len(ctx.subAll)}',
                "xc-lgt"))
    return _svg(W, H, "次级档 XIRR 披露值分布", "".join(b))


def svg03_excess(ctx, W=1300, H=530):
    """03-4：次级档超额收益 Top10 + Bottom5 双面板。"""
    top = ctx.exc_top
    bot = ctx.exc_bot
    rest = ctx.exc_rest
    vmax = max([r["subExcess"] or 0 for r in top] or [1])
    L, R = 214, 900
    b = [tx(L, 22, "次级档超额收益｜上：Top10　下：Bottom5（其余合并见脚注）", "xc-minit")]
    ax = Ax(L, 0, R, 1, 0, vmax, 0, 1)

    def panel(rows, y0, color, cap):
        out = [tx(L, y0 - 10, cap, "xc-lgttl")]
        for i, r in enumerate(rows):
            y = y0 + 16 + i * 22
            v = r["subExcess"] or 0
            w = max(1.5, ax.X(v) - ax.x0)
            head = f'{r["key"]} · 次级档超额收益'
            lines = [f'{r["bank"]} ／ {r["cat"]}',
                     f'超额收益 {amt(v)}',
                     f'占次级档规模 {pct(r["exYield"])}',
                     f'次级档 XIRR {pct(r["xirrSub"])} ／ 回报倍数 {num(r["subMultiple"], 3)}']
            out.append(f'<g class="xc-xrow" data-cat="{esc(r["cat"])}">'
                       f'<text x="{L - 12}" y="{y + 5:.1f}" text-anchor="end" class="xc-rn">{esc(r["short"])}</text>'
                       f'<rect x="{ax.x0:.1f}" y="{y - 8:.1f}" width="{w:.1f}" height="16" rx="2" fill="{color}">'
                       f'{tip(head, lines)}</rect>'
                       f'<text x="{ax.X(v) + 8:.1f}" y="{y + 5:.1f}" class="xc-rv">{amt(v)}</text></g>')
        return out

    b += panel(top, 46, "#4FA98A", "Top10（超额收益最高）")
    sep_y = 46 + 16 + 10 * 22 + 16
    b.append(f'<line x1="{L - 12}" y1="{sep_y:.1f}" x2="{W - 40}" y2="{sep_y:.1f}" class="xc-conn"/>')
    rows_b = bot + [None]  # None = 其他
    b.append(tx(L, sep_y + 26, f'Bottom5（最低）＋ 其他（n={len(rest)}）', "xc-lgttl"))
    for i, r in enumerate(rows_b):
        y = sep_y + 52 + i * 22
        if r is None:
            v = sum(x["subExcess"] or 0 for x in rest)
            head = "其余项目合计"
            lines = [f'其他（n={len(rest)}）：{amt(v)}', "逐单明细见 01 节指标表"]
            lab = f'其他（n={len(rest)}）'
            col = "#98A2B3"
        else:
            v = r["subExcess"] or 0
            head = f'{r["key"]} · 次级档超额收益'
            lines = [f'{r["bank"]} ／ {r["cat"]}', f'超额收益 {amt(v)}',
                     f'占次级档规模 {pct(r["exYield"])}', f'次级档 XIRR {pct(r["xirrSub"])}']
            lab = r["short"]
            col = "#B6BECC"
        w = max(1.5, ax.X(v) - ax.x0)
        b.append(f'<g class="xc-xrow" data-cat="{esc(r["cat"]) if r else ""}">'
                 f'<text x="{L - 12}" y="{y + 5:.1f}" text-anchor="end" class="xc-rn">{esc(lab)}</text>'
                 f'<rect x="{ax.x0:.1f}" y="{y - 8:.1f}" width="{w:.1f}" height="16" rx="2" fill="{col}">'
                 f'{tip(head, lines)}</rect>'
                 f'<text x="{ax.X(v) + 8:.1f}" y="{y + 5:.1f}" class="xc-rv">{amt(v)}</text></g>')
    return _svg(W, H, "次级档超额收益 Top10 与 Bottom5", "".join(b))


def svg_waterfall(ctx, W=1300, H=400):
    """04-A：全周期资金分配瀑布；中间支出项按金额降序（期初/流入/期末位置不变）。"""
    rec = ctx.wf_rec
    core = {
        "优先档·本金": ctx.wf_agg.get("优先档  本金", 0.0),
        "次级档·本金": ctx.wf_agg.get("次级档  本金", 0.0),
        "处置费用": ctx.wf_agg.get("处置费用", 0.0),
        "贷款服务机构报酬": ctx.wf_agg.get("贷款服务机构报酬", 0.0),
        "次级档·收益合计": ctx.wf_agg.get("次级档  收益合计", 0.0),
    }
    rest = sum(v for k, v in ctx.wf_agg.items()
               if k not in ("优先档  本金", "次级档  本金", "次级档  收益合计",
                            "处置费用", "贷款服务机构报酬"))
    core["其他费用（10 项）"] = rest
    items = sorted(core.items(), key=lambda x: -x[1])
    cum, pts = rec, [("回收流入", 0.0, rec, rec, "in")]
    for lab, v in items:
        pts.append((lab, cum, cum - v, -v, "out"))
        cum -= v
    pts.append(("期末结余", 0.0, ctx.wf_end, ctx.wf_end, "end"))
    vmax = rec * 1.06
    ax = Ax(120, 30, W - 70, 300, 0, 1, 0, vmax)
    b = []
    for t in range(5):
        v = vmax * t / 4
        y = ax.Y(v)
        b.append(f'<line x1="{ax.x0 - 10}" y1="{y:.1f}" x2="{ax.x1}" y2="{y:.1f}" class="xc-gl"/>')
        b.append(tx(ax.x0 - 16, y + 3, yi(v, 0), "xc-tk", "end"))
    bw = (ax.x1 - ax.x0) / len(pts) * 0.54
    for i, (lab, s0, s1, val, kind) in enumerate(pts):
        cx = ax.x0 + (ax.x1 - ax.x0) * (i + 0.5) / len(pts)
        y0, y1 = ax.Y(max(s0, s1)), ax.Y(min(s0, s1))
        h = max(1.5, y1 - y0)
        col = {"in": "#2D3955", "end": "#1F7A5C"}.get(kind, "#C2543F")
        b.append(f'<rect x="{cx - bw / 2:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{col}">'
                 f'{tip(lab, [f"金额 {yi(abs(val))} 亿", "回收流入（+）" if kind == "in" else ("期末结余" if kind == "end" else "分配流出（−），按金额降序")])}</rect>')
        b.append(tx(cx, y0 - 8, yi(abs(val)), "xc-barval", "middle"))
        b.append(f'<text x="{cx:.1f}" y="322" text-anchor="end" transform="rotate(-40 {cx:.1f} 322)" '
                 f'class="xc-tk">{esc(lab)}</text>')
        if i:
            b.append(f'<line x1="{ax.x0 + (ax.x1 - ax.x0) * (i - 0.5) / len(pts):.1f}" y1="{ax.Y(pts[i - 1][2]):.1f}" '
                     f'x2="{cx - bw / 2:.1f}" y2="{ax.Y(s0):.1f}" class="xc-conn"/>')
    b.append(tx(120, 16, f"全周期资金分配瀑布（{ctx.wf_n} 单聚合，__V2.WF 口径）", "xc-lgttl"))
    b.append(tx(W - 70, 16, f"合计流出 {yi(ctx.wf_out)} 亿 ／ 期末结余 {yi(ctx.wf_end)} 亿", "xc-lgttl", "end"))
    return _svg(W, H, "全周期资金分配瀑布", "".join(b))


def svg_period_stack(ctx, W=760, H=420):
    """04-B：逐期 100% 堆叠（分母＝该期分配流出合计；<1% 段并入「其他」）。"""
    rows = ctx.per_rows
    if not rows:
        return _svg(W, H, "逐期回收款去向", tx(20, 40, "逐期数据不可用", "xc-lgt"))
    b = [tx(96, 20, "逐期 100% 堆叠（分母＝该期分配流出合计）", "xc-minit")]
    pitch, top = 28, 34
    ax = Ax(96, top, W - 70, top + pitch * len(rows), 0, 1, 0, 1)
    for i, r in enumerate(rows):
        y = top + i * pitch
        xcur = ax.x0
        segs, merged = [], []
        for gname, gcol in ctx.per_cat:
            sh = r["shares"][gname]
            if sh <= 0:
                continue
            if sh < 0.01:
                merged.append((gname, sh))
                continue
            segs.append((gname, gcol, sh, r["raw"].get(gname, 0.0)))
        if merged:
            segs.append(("其他（<1%）", "#98A2B3", sum(m[1] for m in merged),
                         r["tot"] * sum(m[1] for m in merged)))
        for gname, gcol, sh, amt_v in segs:
            w = max(2.0, sh * (ax.x1 - ax.x0))
            lines = [f"占当期 {pct(sh)}", f"金额 {amt(amt_v)}"]
            if merged and gname.startswith("其他"):
                lines.append("含 " + "、".join(m[0] for m in merged))
            b.append(f'<rect x="{xcur:.1f}" y="{y:.1f}" width="{w:.1f}" height="20" fill="{gcol}">'
                     f'{tip(r["label"] + " · " + gname, lines)}</rect>')
            xcur += w
        b.append(tx(ax.x0 - 8, y + 14, r["label"], "xc-tk", "end"))
        b.append(tx(ax.x1 + 8, y + 14, f'{r["n"]} 单', "xc-minisub"))
    b.append(tx(96, top + pitch * len(rows) + 22,
                "第13行起为「第12期及以后」合并；<1% 的科目并入「其他」并保留 tooltip；分母为该期分配流出合计（分配表口径）",
                "xc-minisub"))
    return _svg(W, H, "逐期回收款去向 100% 堆叠", "".join(b))


FEE_SHORT = {"处置费用": "处置费", "贷款服务机构报酬": "服务报酬", "税费支出": "税费",
             "受托机构报酬": "受托报酬", "发行费用": "发行费", "资金保管机构报酬": "保管费",
             "审计费": "审计费", "跟踪评级服务费": "评级费", "代理兑付费用": "代理兑付",
             "其他费用支出": "其他费用"}


def svg_pareto(ctx, W=560, H=420):
    """04-C：费用类科目帕累托（证券本金/利息不入主图）。"""
    rows = ctx.fee_rows
    if not rows:
        return _svg(W, H, "费用科目帕累托", tx(20, 40, "分配明细不可用", "xc-lgt"))
    L, R, top, bot = 56, W - 62, 44, 296
    n = len(rows)
    slot = (R - L) / n
    bw = max(18.0, slot * 0.6)
    ax = Ax(L, top, R, bot, 0, max(1.0, rows[0]["share"] * 1.08), 0, 1)
    ax2 = Ax(L, top, R, bot, 0, 1, 0, 1)     # 累计线右轴 0–100%
    b = [tx(L, 18, "费用类科目帕累托（分子＝各费用科目累计额，看费用集中度）", "xc-minit")]
    for i, r in enumerate(rows):
        cx = L + slot * (i + 0.5)
        y = ax.Y(r["share"])
        h = bot - y
        fee_tip = ["金额 " + yi(r["v"]) + " 亿",
                   "占费用合计 " + pct(r["share"]),
                   "累计 " + pct(r["cum"])]
        b.append(f'<rect x="{cx - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(1.0, h):.1f}" rx="2" fill="#8FA6C4">'
                 f'{tip(r["label"], fee_tip)}</rect>')
        b.append(tx(cx, y - 6, pct(r["share"], 1), "xc-barval", "middle"))
        b.append(f'<text x="{cx:.1f}" y="{bot + 14}" text-anchor="start" '
                 f'transform="rotate(40 {cx:.1f} {bot + 14})" class="xc-tk">'
                 f'{esc(FEE_SHORT.get(r["label"], r["label"]))}</text>')
    pts = [(L + slot * (i + 0.5), ax2.Y(r["cum"])) for i, r in enumerate(rows)]
    b.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
             '" fill="none" stroke="#A52524" stroke-width="1.8"/>')
    for pct_mark, lab in ((0.8, "80%"), (0.9, "90%")):
        y = ax2.Y(pct_mark)
        b.append(f'<line x1="{L}" y1="{y:.1f}" x2="{R}" y2="{y:.1f}" class="xc-med">{tip(lab + " 分位", ["累计占比 " + lab])}</line>')
        b.append(tx(R + 6, y + 3, lab, "xc-tk"))
    hit = next((r for r in rows if r["cum"] >= 0.8), None)
    b.append(tx(L, 384, f'费用合计 {yi(ctx.fee_total)} 亿；累计跨过 80% 的科目：{hit["label"] if hit else "—"}', "xc-lgt"))
    b.append(tx(L, 404, "红线 = 累计占比（右轴）；本金与利息不计入本图；完整科目名见悬停", "xc-minisub"))
    return _svg(W, H, "费用科目帕累托", "".join(b))


# ══════════════════════════════════════════════════════════════════
# 8. 05 各家实际各单 IRR（XIRR）点评（只读披露值，不做任何推导）
# ══════════════════════════════════════════════════════════════════
def _tbl_bank_irr(ctx):
    out = ['<div class="xc-caption">按发起机构汇总（只读披露值；n 为实际有值样本数，缺失不补）</div>',
           '<div class="xc-scroll"><table class="xc-tbl" id="xc-tbl"><thead><tr>',
           '<th class="l">发起机构</th><th>项目数 n</th><th>优先档 XIRR 中位</th><th>优先档区间</th>',
           '<th>次级档 XIRR 中位</th><th>次级档区间</th><th>缺失（优先/次级）</th></tr></thead><tbody>']
    for r in ctx.banks:
        out.append(f'<tr class="xc-brow" data-bank="{esc(r["bank"])}">'
                   f'<td class="l"><b>{esc(r["bank"])}</b></td><td class="n">{r["n"]}</td>'
                   f'<td class="n">{pct(r["sen_med"])}</td>'
                   f'<td class="n">{pct(r["sen_min"])}–{pct(r["sen_max"])}</td>'
                   f'<td class="n">{pct(r["sub_med"])}</td>'
                   f'<td class="n">{pct(r["sub_min"])}–{pct(r["sub_max"])}</td>'
                   f'<td class="n">{r["miss"][0]} / {r["miss"][1]}</td></tr>')
    out.append('</tbody></table></div>')
    return "".join(out)


def _tbl_cat_irr(ctx):
    out = ['<div class="xc-caption">按品种汇总</div>',
           '<div class="xc-scroll xc-scroll-s"><table class="xc-tbl"><thead><tr>',
           '<th class="l">品种</th><th>n</th><th>优先档 XIRR 中位</th><th>优先档区间</th>',
           '<th>次级档 XIRR 中位</th><th>次级档区间</th></tr></thead><tbody>']
    for r in ctx.cats_agg:
        out.append(f'<tr class="xc-trow" data-cat="{esc(r["cat"])}"><td class="l">{esc(r["cat"])}</td>'
                   f'<td class="n">{r["n"]}</td><td class="n">{pct(r["sen_med"])}</td>'
                   f'<td class="n">{pct(r["sen_min"])}–{pct(r["sen_max"])}</td>'
                   f'<td class="n">{pct(r["sub_med"])}</td>'
                   f'<td class="n">{pct(r["sub_min"])}–{pct(r["sub_max"])}</td></tr>')
    out.append('</tbody></table></div>')
    return "".join(out)


def _anoms(ctx):
    def block(title, rows, key, fmt=pct):
        items = "".join(f'<li><span class="nm">{esc(r["short"])}</span>'
                        f'<span class="v">{fmt(r[key])}</span>'
                        f'<span class="bk">{esc(r["bank"])}</span></li>' for r in rows)
        return f'<div class="xc-anom"><h4>{title}</h4><ol>{items}</ol></div>'
    return ('<div class="xc-anoms">' +
            block("优先档 XIRR 最高", ctx.anom["sen_hi"], "xirrSen") +
            block("优先档 XIRR 最低", ctx.anom["sen_lo"], "xirrSen") +
            block("次级档 XIRR 最高", ctx.anom["sub_hi"], "xirrSub") +
            block("次级档 XIRR 最低", ctx.anom["sub_lo"], "xirrSub") +
            '</div>')


def _comment(ctx):
    best = max(ctx.banks, key=lambda r: r["sub_med"] or 0)
    worst = min(ctx.banks, key=lambda r: r["sub_med"] or 0)
    sen_all = _clean([r["xirrSen"] for r in ctx.recs])
    dv = [abs(r["xirrSen"] - r["cpSen"]) for r in ctx.recs
          if r["xirrSen"] is not None and r["cpSen"] is not None]
    gap = (ctx.sub_max - ctx.sub_min) * 100
    n_max = max(bi["n"] for bi in ctx.banks)
    n_min = min(bi["n"] for bi in ctx.banks)
    return ('<div class="xc-cmt">'
            f'<p><b>① 优先档高度收敛。</b>{len(sen_all)} 单优先档 XIRR 集中在 {pct(min(sen_all))}–{pct(max(sen_all))}'
            f'（跨度 {num((max(sen_all) - min(sen_all)) * 100, 1)} 个百分点，中位 {pct(_med(sen_all))}）；'
            f'票面是发行时的定价假设、XIRR 是清算现金流口径，二者偏差 {bp(min(dv))} ~ {bp(max(dv))}，'
            '兑现一致但不可直接等同。</p>'
            f'<p><b>② 次级档分化大。</b>次级档 XIRR 从 {pct(ctx.sub_min)} 到 {pct(ctx.sub_max)}'
            f'（跨度 {num(gap, 1)} 个百分点，中位 {pct(ctx.sub_med)}），远超优先档区间；'
            f'机构层面次级档中位最高为 {esc(best["bank"])}（{pct(best["sub_med"])}，n={best["n"]}），'
            f'最低为 {esc(worst["bank"])}（{pct(worst["sub_med"])}，n={worst["n"]}）。</p>'
            f'<p><b>③ 样本限制。</b>单家机构最多 {n_max} 单、最少 {n_min} 单，中位数对个别项目敏感；'
            '次级档 XIRR 受清仓时点与超额收益分配影响，只宜作横截面参考，不构成对未来定价的推断。</p>'
            '</div>')


def _card(cid, num, title, sub, plots, legend, foot, cls=""):
    return (f'<div class="xc-card {cls}" id="{cid}">'
            f'<div class="xc-ch"><h2><span class="xc-idx">{num}</span>{title}</h2>'
            f'<p class="xc-sub">{sub}</p></div>'
            f'<div class="xc-cb">{plots}</div>'
            + (f'<div class="xc-lg">{legend}</div>' if legend else '')
            + f'<div class="xc-cf">{foot}</div></div>')


def _plot(svg, span=12, cls="", ph=None):
    st = f"grid-column:span {span}" + (f";--ph:{ph}px" if ph else "")
    cl = (cls + (" xc-ph" if ph else "")).strip()
    return f'<figure class="xc-plot {cl}" style="{st}">{svg}</figure>'


def _legend(items, extra=""):
    out = ['<div class="lg-list">']
    for col, label in items:
        dot = (f'<i style="background:{col}"></i>' if col else '<i class="xc-lgi"></i>')
        out.append(f'<span class="lg-i">{dot}{label}</span>')
    out.append('</div>')
    if extra:
        out.append(f'<span class="lg-extra">{extra}</span>')
    return "".join(out)


def _kpi(ctx):
    rec_all = sum(r["recovered"] for r in ctx.recs if r["recovered"])
    items = [
        ("样本", f'{len(ctx.recs)} 单', "3 品种 · 9 家发起机构"),
        ("累计回收", f'{yi(rec_all)} 亿', "回收流入口径"),
        ("处置费率中位", pct(ctx.mDis), "处置费用 / 累计回收（n=28）"),
        ("实际回收率中位", pct(ctx.mRec), "累计回收 / 入池本息费（n=27）"),
        ("实际/预测 比值中位", num(ctx.mRatio, 2), "中债预测口径（n=27）"),
        ("次级档 XIRR 区间", f'{pct(min(r["xirrSub"] for r in ctx.recs))}–{pct(max(r["xirrSub"] for r in ctx.recs))}', "n=28"),
        ("优先档 XIRR 中位", pct(_med([r["xirrSen"] for r in ctx.recs])), "现金流口径（n=28）"),
        ("期末结余", f'{yi(ctx.wf_end)} 亿', f'瀑布闭合 {ctx.wf_n} 单'),
    ]
    out = ['<div class="xc-kpi">']
    for lab, v, s in items:
        out.append(f'<div class="xc-kpi-i"><div class="l">{esc(lab)}</div><div class="v">{esc(v)}</div><div class="s">{esc(s)}</div></div>')
    out.append('</div>')
    return "".join(out)


NOTE03 = ('哑铃/叠加图比较优先档票面利率与优先档 XIRR，票面为定价假设、XIRR 为现金流口径，'
          '二者不可直接等同；次级档仅展示披露 XIRR，不进行固定资金成本倒算。')


def build_html(ctx=None):
    if ctx is None:
        _r, _a = build_records()
        ctx = Ctx(_r, _a)
    H = []
    H.append('<div class="xc-wrap" data-quad="all">')

    # 顶部：板块头（口径 + 筛选状态，高度固定）
    H.append('<header class="xc-hd">'
             '<h1>横向对照 · 从发行定价到回收去向</h1>'
             '<div class="xc-meta">'
             '<span><b>处置费率</b> = 处置费用 / 累计回收（本页唯一费用口径）</span>'
             '<span><b>实际回收率</b> = 累计回收 / 入池本息费</span>'
             '<span><b>中债预测回收率</b> = 预测回收额 / 入池本息费</span>'
             '<span><b>实际/预测比值</b> = 实际回收率 / 中债预测回收率</span>'
             '</div>'
             '<div class="xc-tools"><div class="xc-chips" role="group" aria-label="品种筛选">'
             f'<button type="button" class="xc-chip on" data-cat="全部">全部 {len(ctx.recs)}</button>')
    for c in CATS:
        n = len([r for r in ctx.recs if r["cat"] == c])
        H.append(f'<button type="button" class="xc-chip" data-cat="{esc(c)}">{esc(c)} {n}</button>')
    H.append('</div><span class="xc-fnote" id="xc-filter-note">筛选：全部 28 单</span></div></header>')
    H.append(_kpi(ctx))

    # ── 01 ──
    lgend = _legend([(CAT_COLOR[c], c) for c in CATS], "空心点＝回收率缺失（不参与定位）")
    H.append(_card(
        "s01", "01",
        "四象限：实际回收率 × 处置费率，气泡 = 资产本金规模",
        '这一节说明：<b>处置费率高低与回收兑现是否同向</b>——两者同在回收侧，'
        '只作横截面刻画，不解读为因果；分品种小图同刻度可横比。',
        _plot(svg_q_main(ctx), 12) +
        "".join(_plot(svg_q_mini(ctx, c), 4, "xc-mini-p") for c in CATS) +
        f'<div class="xc-tablewrap" style="grid-column:span 12">'
        f'<details class="xc-fold" data-fold="1"><summary class="xc-fold-h"><span>＋</span>'
        f'28 单指标明细（含证券化率等辅助字段，点开可排序）</summary>'
        f'<div class="xc-fold-b">{_table_metrics(ctx)}</div></details></div>',
        lgend,
        '<b>口径</b>：处置费率 = 处置费用 ÷ 累计回收；实际回收率 = 累计回收 / 入池本息费。'
        '两者<b>共享回收侧口径</b>，存在内生/同向关系，仅作横截面刻画、<b>不解读为因果</b>；'
        'n=27（1 单回收率与资产本金规模未披露，空心点单列）。'
        '证券化率 = 发行规模 / 入池本息费（辅助字段）；'
        '之所以不把证券化率放在横轴，是因为它与处置费率同在回收侧、易与处置费率混淆，'
        '证券化率的品种差异见 05 节热力矩阵与 28 单明细列。',
        "s01"))

    # ── 02 ──
    H.append(_card(
        "s02", "02",
        "中债预测回收率 vs 实际回收率",
        '这一节说明：<b>中债预测与实际回收的偏离方向与幅度</b>——45° 对角线上下即「好于/不及预测」；'
        '项目级差异只放在悬停读数里，图内不压文字标签。',
        _plot(svg_fc_scatter(ctx), 8, ph=410) + _plot(svg_fc_ratio(ctx), 4, ph=410) + diff_note(ctx),
        _legend([(CAT_COLOR[c], c) for c in CATS], "气泡 = 资产本金规模；红环 = 偏离最大 5 单（无文字标签）"),
        f'<b>口径</b>：X、Y 分母同为入池本息费（同口径可比），n={len(ctx.fc)}；'
        '差异 = 实际回收率 − 预测回收率（pp）；比值 = 实际 / 预测，中位 '
        f'{num(ctx.mRatio, 2)}、均值 {num(ctx.aRatio, 2)}。'
        '比值只描述偏离方向与幅度，<b>不等同于「达成率」考核口径</b>；次级档仅展示披露 XIRR，不做任何资金成本推导。',
        "s02"))

    # ── 03 ──
    H.append(_card(
        "s03", "03",
        "定价假设 vs 实际兑现 + 次级档超额收益",
        '这一节说明：<b>发行时的定价假设兑现到什么程度</b>——票面与 XIRR 的偏差、次级档披露 XIRR 的分化、'
        '以及超额收益集中在哪些单。',
        _plot(svg03_pri_bars(ctx), 12, ph=470) +
        _plot(svg03_dev_strip(ctx), 6, ph=300) +
        _plot(svg03_sub_dist(ctx), 6, ph=316) +
        _plot(svg03_excess(ctx), 12, ph=530),
        _legend([(SEN_C, "票面利率（定价假设）"), ("#A52524", "优先档偏差 / 中位"),
                 ("#4FA98A", "次级档超额收益"),
                 (CAT_COLOR["信用卡不良"], "信用卡不良"), (CAT_COLOR["个人消费贷款"], "个人消费贷款"),
                 (CAT_COLOR["个人经营贷款"], "个人经营贷款")],
                "优先档 n=28 ／ 次级档 n=28（仅披露 XIRR）"),
        NOTE03, "s03"))

    # ── 04 ──
    wf_note = ('中间支出项按金额降序排列，非合同支付顺序；期初、回收流入、期末位置不变，累计扣减逻辑不变。')
    H.append(_card(
        "s04", "04",
        "回收款去向：全周期瀑布 + 逐期堆叠 + 费用帕累托",
        '这一节说明：<b>回收进来的钱按什么顺序流到谁手里</b>——瀑布看全周期分档去向（中间支出按金额降序），'
        '逐期堆叠看结构随时间的迁移，费用帕累托看费用集中度。',
        _plot(svg_waterfall(ctx), 12, ph=400) +
        _plot(svg_period_stack(ctx), 7, ph=420) +
        _plot(svg_pareto(ctx), 5, ph=420),
        _legend([("#2D3955", "回收流入"), ("#C2543F", "分配流出（降序）"), ("#1F7A5C", "期末结余"),
                 ("#B0763F", "费用与税"), ("#7FBFA8", "次级档本息与收益"),
                 ("#B6BECC", "结转/转存"), ("#98A2B3", "其他（<1%）")],
                "瀑布仅标金额、长标签已旋转；逐期堆叠分母＝该期分配流出合计"),
        wf_note +
        f'　累计流出 {yi(ctx.wf_out)} 亿 ／ 期末结余 {yi(ctx.wf_end)} 亿；处置费用（瀑布口径）{yi(ctx.wf_disp)} 亿'
        + (f'（{ctx.wf_dbl_n} 单已在处置收入环节扣除，不重复计入）' if ctx.wf_dbl_n else '')
        + '；帕累托只含费用类科目，本金/利息不入主图。',
        "s04"))

    # ── 05 ──
    H.append(_card(
        "s05", "05",
        "各家实际各单 IRR（XIRR）点评",
        '这一节说明：<b>只读披露值</b>——按发起机构与品种汇总 XIRR 的中位与区间，并点出异常单；'
        '不推导、不补值，样本 n 逐行动态计算。',
        _tbl_bank_irr(ctx) + _tbl_cat_irr(ctx) + _anoms(ctx) + _comment(ctx),
        "",
        '口径：票面是定价假设、XIRR 是现金流口径，二者不可直接等同；'
        '次级档 XIRR 为清算分配结果，只作横截面参考，样本量有限（单家 2–6 单）。',
        "s05"))

    H.append('</div>')
    return "".join(H)


# ══════════════════════════════════════════════════════════════════
# 10. CSS
# ══════════════════════════════════════════════════════════════════
CSS = """
.xc-wrap{
  --ink:#141A26;--ink2:#38425A;--ink3:#697487;--ink4:#98A2B3;
  --canvas:#F2F5F9;--card:#fff;--surface:#EDF1F6;--surface2:#E4EAF2;--hover:#F8FAFD;
  --line:rgba(20,26,38,.11);--line2:rgba(20,26,38,.07);--line3:rgba(20,26,38,.20);
  --accent:#2D3955;--pos:#B3261E;--neg:#1F7A5C;--warn:#B0763F;
  --ease:cubic-bezier(.16,.68,.42,1);
  --gap:14px;--head-h:96px;--legend-h:44px;--foot-h:56px;--r:16px;
  background:var(--canvas);color:var(--ink);
  font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei UI","Microsoft YaHei",sans-serif;
  font-variant-numeric:tabular-nums;letter-spacing:.004em;
}
.xc-wrap *{box-sizing:border-box}
.xc-wrap{max-width:1360px;margin:0 auto;padding:24px 20px 64px}
.xc-wrap h1{font-size:24px;line-height:1.3;margin:0 0 8px;font-weight:650;letter-spacing:-.01em}
/* ── 顶部板块头（高度固定）── */
.xc-hd{height:var(--head-h);display:flex;flex-direction:column;justify-content:center;
  margin:0 0 12px;overflow:hidden}
.xc-meta{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:11.5px;color:var(--ink3);line-height:1.5}
.xc-meta b{color:var(--ink2);font-weight:640}
.xc-tools{display:flex;align-items:center;gap:12px;margin-top:8px}
.xc-chips{display:flex;gap:6px;flex-wrap:wrap}
.xc-chip{border:1px solid var(--line);background:var(--card);font:inherit;font-size:12px;
  color:var(--ink2);padding:4px 10px;border-radius:999px;cursor:pointer;transition:all .16s var(--ease)}
.xc-chip:hover{background:var(--hover)}
.xc-chip.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.xc-fnote{font-size:11.5px;color:var(--ink4)}
/* ── KPI ── */
.xc-kpi{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin:0 0 14px}
.xc-kpi-i{background:var(--card);border:1px solid var(--line2);border-radius:12px;padding:9px 11px;
  box-shadow:0 1px 2px rgba(16,24,40,.04);overflow:hidden}
.xc-kpi-i .l{color:var(--ink3);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.xc-kpi-i .v{font-size:16.5px;font-weight:650;letter-spacing:-.01em;line-height:1.3;white-space:nowrap}
.xc-kpi-i .s{color:var(--ink4);font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* ── 卡片三分区：头 / 图网格 / 图例 / 脚注 ── */
.xc-card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
  box-shadow:0 1px 2px rgba(16,24,40,.04),0 1px 3px rgba(16,24,40,.06);
  margin:0 0 16px;padding:16px 18px 0;display:flex;flex-direction:column;overflow:hidden}
.xc-ch{flex:0 0 auto;margin-bottom:10px}
.xc-ch h2{font-size:16.5px;margin:0 0 3px;font-weight:640;letter-spacing:-.005em}
.xc-ch .xc-idx{display:inline-block;min-width:1.9em;color:var(--ink4);font-weight:600}
.xc-sub{color:var(--ink3);font-size:12.5px;margin:0;line-height:1.55}
.xc-sub b{color:var(--ink2)}
.xc-cb{flex:0 0 auto;display:grid;grid-template-columns:repeat(12,1fr);gap:var(--gap);align-items:stretch}
.xc-plot{position:relative;min-width:0;display:flex;flex-direction:column;margin:0;height:430px}
.xc-plot > svg{flex:1 1 auto;min-height:0;width:100%;height:100%;display:block;overflow:visible}
.xc-tablewrap{min-width:0}
.xc-plot-t{height:auto;min-height:0}
.s01 .xc-plot{height:430px}
.s01 .xc-plot.xc-mini-p{height:268px}
.s02 .xc-plot{height:410px}
.s03 .xc-plot{height:600px}
.xc-side{display:flex;flex-direction:column;gap:var(--gap)}
.xc-side .xc-plot{height:293px;flex:1 1 0}
.s04 .xc-plot{height:380px}
.s04 .xc-plot:not(:first-child){height:340px}
.s05 .xc-formula{height:346px}
.s05 .xc-plot{height:346px}
/* 图例区：固定 40–48px */
.xc-lg{flex:0 0 var(--legend-h);height:var(--legend-h);display:flex;align-items:center;
  gap:14px;overflow:hidden;border-top:1px dashed var(--line2);margin-top:10px}
.lg-list{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:11.5px;color:var(--ink3);
  align-content:center;max-height:100%;overflow:hidden}
.lg-i{display:inline-flex;align-items:center;white-space:nowrap}
.lg-i i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;flex:0 0 auto}
.lg-i i.xc-lgi{background:none;border:1.4px dashed var(--ink4);border-radius:50%}
.lg-extra{font-size:11px;color:var(--ink4);white-space:nowrap}
.lg-toggle{display:none;border:1px solid var(--line);background:var(--card);font:inherit;font-size:11.5px;
  color:var(--ink2);padding:3px 10px;border-radius:8px;cursor:pointer}
/* 脚注 1–2 行 */
.xc-cf{flex:0 0 auto;min-height:var(--foot-h);font-size:11px;color:var(--ink4);line-height:1.6;
  padding:8px 0 12px;border-top:1px solid var(--line2);margin-top:8px;overflow:hidden}
.xc-cf b{color:var(--ink3)}
/* ── SVG 通用 ── */
.xc-svg text{font-family:inherit}
.xc-tk{font-size:10px;fill:var(--ink4)}
.xc-axt{font-size:10.5px;fill:var(--ink3)}
.xc-gl{stroke:var(--line2);stroke-width:1}
.xc-frame{fill:#FCFDFE;stroke:var(--line2);stroke-width:1}
.xc-axis{stroke:var(--line3);stroke-width:1}
.xc-fit{stroke:var(--ink4);stroke-width:1.3;stroke-dasharray:6 5;opacity:.8}
.xc-diag{stroke:#1F7A5C;stroke-width:1.5;stroke-dasharray:7 5;opacity:.85}
.xc-fcb{stroke:var(--ink4);stroke-width:1;stroke-dasharray:3 4;opacity:.5}
.xc-med{stroke:var(--ink3);stroke-width:1;stroke-dasharray:5 4;opacity:.5}
.xc-med2{stroke-width:1.1;stroke-dasharray:4 4;opacity:.6}
.xc-medtick{stroke-width:2}
.xc-qlab{font-size:11px;font-weight:640;fill:var(--ink2)}
.xc-leader{stroke:var(--ink4);stroke-width:.9;stroke-dasharray:2.5 2.5}
.xc-anno{font-size:10px;font-weight:600;fill:var(--ink)}
.xc-ag{transition:opacity .18s var(--ease)}
.xc-ag.xc-dim{opacity:.14}
.xc-b{fill-opacity:.74;stroke:#fff;stroke-width:1.1;transition:opacity .18s var(--ease),fill-opacity .18s var(--ease)}
.xc-b:hover{fill-opacity:1;stroke-width:1.8}
.xc-bgap{stroke-width:1.8;stroke-dasharray:3 3;fill-opacity:.10}
.xc-dim{opacity:.14;transition:opacity .2s var(--ease)}
.xc-gapsep{stroke:var(--ink3);stroke-width:1;stroke-dasharray:2 3;opacity:.6}
.xc-gapsub{font-size:9.5px;fill:var(--ink3)}
.xc-lgttl{font-size:10.5px;fill:var(--ink3);font-weight:640}
.xc-lgt{font-size:10.5px;fill:var(--ink2)}
.xc-lgcirc{fill:none;stroke:var(--ink4);stroke-width:1;stroke-dasharray:2 2}
.xc-minit{font-size:11.5px;font-weight:640;fill:var(--ink2)}
.xc-minisub{font-size:9.5px;fill:var(--ink4)}
.xc-barval{font-size:9.5px;fill:var(--ink2);font-weight:640}
.xc-track{stroke:var(--line3);stroke-width:2.2;stroke-linecap:round}
.xc-rn{font-size:10.5px;fill:var(--ink2)}
.xc-rv{font-size:10.5px;fill:var(--ink2);font-weight:600}
.xc-conn{stroke:var(--ink4);stroke-width:1;stroke-dasharray:2 2;opacity:.6}
.xc-heatth{font-size:10.5px;fill:var(--ink3);font-weight:640}
.xc-heatrow{font-size:11px;fill:var(--ink2)}
.xc-heatv{font-size:10.5px;font-weight:600;pointer-events:none}
.xc-heatcell{transition:opacity .16s var(--ease)}
.xc-heatcell:hover{opacity:.84}
/* 公式卡 */
.xc-formula{display:flex;flex-direction:column}
.xc-fbox{background:var(--surface);border:1px solid var(--line2);border-radius:12px;padding:12px 14px;height:100%;overflow:hidden}
.xc-fh{font-size:13px;font-weight:640;margin-bottom:8px}
.xc-feq{font-size:11.5px;color:var(--ink2);background:var(--card);border:1px solid var(--line2);
  border-radius:8px;padding:7px 9px;line-height:1.6}
.xc-feq2{font-size:11.5px;color:var(--ink2);padding:6px 2px 8px}
.xc-fkv{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:var(--ink3);
  padding:3px 0;border-bottom:1px dashed var(--line2)}
.xc-fkv:last-child{border-bottom:0}
.xc-fkv b{color:var(--ink);font-weight:640}
/* 表格 */
.xc-caption{font-size:11px;color:var(--ink4);margin:0 0 6px;line-height:1.5}
.xc-scroll{overflow:auto;border:1px solid var(--line2);border-radius:10px;max-height:420px}
.xc-scroll-s{max-height:260px}
.xc-tbl{width:100%;border-collapse:collapse;font-size:12px}
.xc-tbl th,.xc-tbl td{padding:6px 9px;text-align:right;border-bottom:1px solid var(--line2);white-space:nowrap}
.xc-tbl th{color:var(--ink3);font-weight:640;font-size:11px;position:sticky;top:0;background:var(--card);z-index:2;line-height:1.3}
.xc-tbl th .u{color:var(--ink4);font-weight:400;font-size:10px}
.xc-tbl th.l,.xc-tbl td.l{text-align:left}
.xc-tbl th[data-sort]{cursor:pointer;user-select:none}
.xc-tbl th[data-sort].asc::after{content:" ▲";font-size:8px;color:var(--accent)}
.xc-tbl th[data-sort].desc::after{content:" ▼";font-size:8px;color:var(--accent)}
.xc-tbl tbody tr:hover{background:var(--hover)}
.xc-tbl .n{font-variant-numeric:tabular-nums}
.xc-cat{display:inline-block;padding:0 7px;border-radius:999px;font-size:10.5px;
  color:var(--c);background:var(--surface);border:1px solid color-mix(in srgb,var(--c) 26%,#fff)}
/* 折叠 */
details.xc-fold{border:1px solid var(--line2);border-radius:10px;background:#FCFDFE}
details.xc-fold>summary.xc-fold-h{cursor:pointer;padding:8px 12px;font-size:12px;font-weight:640;
  color:var(--ink2);list-style:none;display:flex;gap:8px;align-items:flex-start}
details.xc-fold>summary::-webkit-details-marker{display:none}
details.xc-fold>summary span:first-child{display:inline-flex;flex:0 0 auto;width:17px;height:17px;
  border-radius:5px;background:var(--surface2);color:var(--ink2);align-items:center;justify-content:center;font-weight:700}
details.xc-fold[open]>summary.xc-fold-h{color:var(--ink);border-bottom:1px solid var(--line2)}
details.xc-fold[open]>summary span:first-child{background:var(--accent);color:#fff}
.xc-fold-b{padding:8px 10px 10px}
/* 响应式：桌面 12 列 / 平板 6 列 / 手机 1 列 */
/* ── v11：02 图外差异摘要（2 行，不压图内） ── */
.xc-note2{grid-column:span 12;font-size:12px;color:var(--ink2);line-height:1.75;margin:0}
.xc-note2 b{color:var(--ink);font-weight:640}
.xc-note2 .u-hint{color:var(--ink4);font-size:11px;margin-left:6px}
/* ── v11：按图定制高度（01 不传 ph，不受影响） ── */
.xc-plot.xc-ph{height:var(--ph,430px) !important}
/* ── v11：03 节字号整体 +1（仅本板块） ── */
.s03 .xc-tk{font-size:11.5px}
.s03 .xc-axt{font-size:12px}
.s03 .xc-rn{font-size:12px}
.s03 .xc-rv{font-size:12px}
.s03 .xc-barval{font-size:11.5px}
.s03 .xc-lgttl{font-size:12px}
.s03 .xc-minisub{font-size:11px}
.s03 .lg-list{font-size:12px;gap:6px 18px}
.s03 .lg-extra{font-size:11.5px}
.s03 .xc-cf{font-size:12px}
.s03 .xc-lg{height:58px;flex:0 0 58px}
/* ── v11：05 表 / 清单 / 点评 ── */
.s05 .xc-cb > div{grid-column:span 12}
.xc-anoms{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;min-width:0}
.xc-anom{background:var(--surface);border:1px solid var(--line2);border-radius:10px;padding:10px 12px;min-width:0}
.xc-anom h4{margin:0 0 6px;font-size:12px;font-weight:640;color:var(--ink2)}
.xc-anom ol{margin:0;padding-left:16px;font-size:12px;color:var(--ink2);line-height:1.9}
.xc-anom li{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;list-style:decimal}
.xc-anom .nm{color:var(--ink)}
.xc-anom .v{color:var(--ink);font-weight:640;margin-left:6px}
.xc-anom .bk{color:var(--ink4);margin-left:6px;font-size:11px}
.xc-cmt{background:#FCFDFE;border:1px solid var(--line2);border-radius:10px;padding:12px 16px}
.xc-cmt p{margin:0 0 8px;font-size:12.5px;color:var(--ink2);line-height:1.8}
.xc-cmt p:last-child{margin-bottom:0}
.xc-cmt b{color:var(--ink)}
@media(max-width:1180px){
  .xc-wrap .xc-kpi{grid-template-columns:repeat(4,1fr) !important}
  .xc-wrap .xc-cb{grid-template-columns:repeat(6,1fr) !important}
  .xc-wrap .xc-cb > .xc-plot,
  .xc-wrap .xc-cb > .xc-side,
  .xc-wrap .xc-cb > .xc-formula{grid-column:span 6 !important}
  .xc-wrap .xc-plot{height:auto !important}
  .xc-wrap .xc-plot > svg{height:auto !important}
  .xc-wrap .xc-side{display:flex;flex-direction:column;gap:var(--gap)}
  .xc-wrap .xc-side .xc-plot{height:auto !important}
  .xc-wrap .xc-formula{height:auto !important}
  .xc-wrap .xc-fbox{height:auto}
}
@media(max-width:767px){
  .xc-wrap{padding:16px 12px 48px}
  .xc-wrap .xc-kpi{grid-template-columns:repeat(2,1fr) !important}
  .xc-wrap .xc-cb{grid-template-columns:1fr !important}
  .xc-wrap .xc-cb > *{grid-column:1 / -1 !important}
  .xc-wrap .xc-plot{height:auto !important}
  .xc-wrap .xc-plot > svg{height:auto !important;width:100% !important}
  .xc-wrap .xc-side{display:flex;flex-direction:column}
  .xc-wrap .xc-hd{height:auto !important;min-height:96px}
  .xc-wrap .xc-lg{flex-wrap:wrap;overflow:visible;height:auto !important;min-height:0}
  .xc-wrap .lg-toggle{display:inline-block}
  .xc-wrap .xc-lg:not(.open) .lg-list{display:none}
  .xc-wrap .xc-lg .lg-extra{display:none}
}
@media(prefers-reduced-motion:reduce){.xc-wrap *{transition:none!important;animation:none!important}}
"""


# ══════════════════════════════════════════════════════════════════
# 11. JS（IIFE）
# ══════════════════════════════════════════════════════════════════
JS = r"""
(function(){
  function boot(){
    var ROOT = document.getElementById('view-xcompare');
    if(!ROOT) return;
    var QUAD = ROOT.querySelector('.xc-wrap') || ROOT;
    function qa(s, el){ return Array.prototype.slice.call((el || document).querySelectorAll(s)); }
    function q(s, el){ return (el || document).querySelector(s); }

    /* 1. 品种筛选（板块头显示筛选状态） */
    var chips = qa('.xc-chip', ROOT);
    function applyCat(cat){
      chips.forEach(function(c){ c.classList.toggle('on', c.getAttribute('data-cat') === cat); });
      qa('.xc-b, .xc-xrow, .xc-trow, .xc-ag', ROOT).forEach(function(el){
        var ec = el.getAttribute('data-cat');
        el.classList.toggle('xc-dim', !(cat === '全部' || (ec && ec === cat)));
      });
      var note = q('#xc-filter-note', ROOT);
      if(note){
        var n = cat === '全部' ? qa('.xc-trow', ROOT).length : qa('.xc-trow[data-cat="' + cat + '"]', ROOT).length;
        note.textContent = cat === '全部' ? '筛选：全部 ' + n + ' 单' : '筛选：' + cat + ' ' + n + ' 单';
      }
    }
    chips.forEach(function(c){ c.addEventListener('click', function(){ applyCat(c.getAttribute('data-cat')); }); });

    /* 2. 表格排序 */
    qa('table.xc-tbl', ROOT).forEach(function(tbl){
      qa('th[data-sort]', tbl).forEach(function(th){
        th.addEventListener('click', function(){
          var key = th.getAttribute('data-sort');
          var dir = th.getAttribute('data-dir') === 'desc' ? 'asc' : 'desc';
          qa('th[data-sort]', tbl).forEach(function(x){
            x.removeAttribute('data-dir'); x.classList.remove('asc','desc');
          });
          th.setAttribute('data-dir', dir); th.classList.add(dir);
          if(!tbl.tBodies.length) return;
          var tb = tbl.tBodies[0], rows = qa('tr', tb);
          rows.sort(function(a, b){
            var ca = a.querySelector('td[data-k="' + key + '"]');
            var cb = b.querySelector('td[data-k="' + key + '"]');
            var va = ca ? parseFloat(ca.getAttribute('data-v')) : NaN;
            var vb = cb ? parseFloat(cb.getAttribute('data-v')) : NaN;
            if(isNaN(va)) va = -Infinity;
            if(isNaN(vb)) vb = -Infinity;
            return dir === 'desc' ? (vb - va) : (va - vb);
          });
          rows.forEach(function(r){ tb.appendChild(r); });
        });
      });
    });

    /* 3. 点击气泡 / 项目名 → 跳转该项目档案 */
    qa('[data-view]', ROOT).forEach(function(el){
      if(el.tagName.toLowerCase() === 'button') return;
      el.style.cursor = 'pointer';
      el.addEventListener('click', function(){
        var nav = document.querySelector('.sb-item[data-view="' + el.getAttribute('data-view') + '"]');
        if(nav && typeof nav.click === 'function') nav.click();
      });
    });

    /* 4. 窄屏图例折叠为「图例」按钮 */
    qa('.xc-lg', ROOT).forEach(function(lg){
      if(lg.querySelector('.lg-toggle')) return;
      var btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'lg-toggle'; btn.textContent = '图例';
      btn.addEventListener('click', function(){ lg.classList.toggle('open'); });
      lg.insertBefore(btn, lg.firstChild);
    });

    /* 5. Esc 复位筛选 */
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' || e.keyCode === 27) applyCat('全部');
    });
    applyCat('全部');
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
"""


# ══════════════════════════════════════════════════════════════════
# 12. 装配 + 自检
# ══════════════════════════════════════════════════════════════════
# 模块级 HTML（组装器 load_module 优先读常量；失败时回退 build_all()）
try:
    HTML = build_html()
except Exception:                                   # pragma: no cover
    HTML = ""


def build_all():
    recs, audit = build_records()
    ctx = Ctx(recs, audit)
    return CSS, build_html(ctx), JS, ctx


def selftest():
    css, html, js, c = build_all()
    n_svg = html.count("<svg")
    n_title = html.count("<title>")
    n_tr = html.count("<tr")
    problems = []

    print("═" * 74)
    print("30_compare.py · #view-xcompare v11 自检（02/03/04/05 重构，01 不动）")
    print("═" * 74)
    n_fold = html.count('class="xc-fold"')
    print(f"CSS {len(css):,} 字符 ／ HTML {len(html):,} 字符 ／ JS {len(js):,} 字符")
    print(f"SVG {n_svg} 张 ／ <title> {n_title} ／ <tr> {n_tr} ／ 折叠 {n_fold}")

    def chk(ok, label, extra=""):
        print(f"  {'✔' if ok else '✘'} {label}{('  ' + extra) if extra else ''}")
        if not ok:
            problems.append(label)

    # ── 01 未改动（哈希与 v10 基线一致）──
    i0 = html.index('id="s01"')
    i1 = html.index('id="s02"')
    h01 = hashlib.sha256(html[i0:i1].encode("utf-8")).hexdigest()[:16]
    print("─" * 74)
    chk(h01 == "57f987a0b3d13fa6", "01 节与 v10 基线逐字节一致", f"hash {h01}")

    # ── 02 ──
    s02 = html[html.index('id="s02"'):html.index('id="s03"')]
    chk("差异（实际 − 预测）" in s02, "02 tooltip 含差异读数")
    chk("xc-anno" not in s02, "02 图内无项目级文字标签")
    chk("差异最大 Top3" in s02 and "最小 Top3" in s02, "02 图外 2 行差异摘要")
    chk("对角" in s02 and "45°" in s02, "02 45° 对角线")
    chk("xc-note2" in s02 and s02.count("xc-note2") == 1, "02 摘要位于图外（独立块）")

    # ── 03 ──
    s03 = html[html.index('id="s03"'):html.index('id="s04"')]
    chk(s03.count("<svg") == 4, "03 四张图", f"{s03.count('<svg')} 张")
    chk("哑铃/叠加图比较优先档票面利率与优先档 XIRR" in s03, "03 固定图注逐字出现")
    chk("次级档仅展示披露 XIRR，不进行固定资金成本倒算" in s03, "03 图注含「不倒算」声明")
    chk("n=8" not in s03 and "可倒算" not in s03, "03 无 n=8 / 可倒算")
    chk("约定资金成本率" not in s03 and "固定资金成本率" not in s03, "03 无约定/固定资金成本率")
    chk("次级档 XIRR 披露值分布" in s03, "03 次级档披露值分布图")
    chk("Top10" in s03 and "Bottom5" in s03, "03 超额收益双面板")
    chk(f'其他（n={len(c.exc_rest)}）' in s03, "03 其余合并项明示", f"n={len(c.exc_rest)}")

    # ── 04 ──
    s04 = html[html.index('id="s04"'):html.index('id="s05"')]
    _wf = re.search(r'aria-label="全周期资金分配瀑布".*?</svg>', s04, re.S)
    _vals = [float(x) for x in re.findall(r'class="xc-barval">([\d,.]+)<', _wf.group(0))] if _wf else []
    chk(len(_vals) >= 8 and all(_vals[i] >= _vals[i + 1] for i in range(1, len(_vals) - 2)),
        "04 瀑布中间支出项按金额降序", "→".join(f"{v:.0f}" for v in _vals))
    chk("中间支出项按金额降序排列" in s04, "04 降序图注逐字出现")
    chk("分母＝该期分配流出合计" in s04, "04 堆叠分母口径")
    chk("其他（<1%）" in s04 or "xc-period" in s04, "04 细段合并保护")
    chk("费用类科目帕累托" in s04 and "80%" in s04 and "90%" in s04, "04 费用帕累托 + 80/90 分位")
    chk(len(c.fee_rows) == 10, "04 帕累托仅费用类 10 项", f"{len(c.fee_rows)} 项")

    # ── 05 ──
    s05 = html[html.index('id="s05"'):]
    chk("各家实际各单 IRR（XIRR）点评" in s05, "05 标题改为 IRR 点评")
    chk("倒算" not in s05 and "约定资金成本率" not in s05 and "固定资金成本率" not in s05, "05 零倒算")
    chk(s05.count('class="xc-brow"') == len(c.banks), "05 银行汇总表行数", f"{len(c.banks)} 行")
    chk(s05.count("xc-anom") >= 4, "05 异常单 4 栏")
    chk("样本限制" in s05, "05 含样本限制点评")

    # ── 全页口径 ──
    print("─" * 74)
    chk(html.count("倒算") == 1, "全节「倒算」仅 1 次（用户指定图注的否定句）", f"{html.count('倒算')} 次")
    chk(html.count("约定资金成本率") == 0 and html.count("固定资金成本率") == 0, "无约定/固定资金成本率")
    chk(html.count("可倒算") == 0 and html.count("n=8") == 0, "无「可倒算」/「n=8」")
    chk("预测 XIRR" not in html and "折价率" not in html, "无「预测 XIRR」「折价率」")
    bad = re.findall(r"处置费(?:率)?\s*[÷/]\s*入池", html)
    chk(not bad, "处置费率分母只＝累计回收", f"{len(bad)} 处")
    chk(html.count("证券化率") >= 5, "证券化率保留（表格辅助列）", f"{html.count('证券化率')} 次")

    # ── 结构 / SVG ──
    chk(n_tr >= 10, "<tr> ≥ 10", str(n_tr))
    chk("<section" not in html and "#view-xcompare" not in css, "无 section 外壳 / CSS 无 #view-xcompare")
    chk(html.count('class="xc-wrap"') == 1, "xc-wrap 唯一")
    chk(len(re.findall("<div" + r"\b", html)) == html.count("</div>"), "div 配平",
        f"{len(re.findall('<div' + chr(92) + 'b', html))}/{html.count('</div>')}")
    chk(not re.findall(r'<svg[^>]*\swidth="\d{3,}"[^>]*height="\d{3,}"', html), "SVG 无写死宽高")
    chk(html.count("preserveAspectRatio") == n_svg, "SVG 均带 preserveAspectRatio")
    badsvg = []
    for k, frag in enumerate(html.split("<svg")[1:], 1):
        frag = "<svg" + frag.split("</svg>")[0] + "</svg>"
        try:
            ET.fromstring(frag)
        except Exception as e:
            badsvg.append(f"svg#{k}: {e}")
    chk(not badsvg, f"SVG 良构 {n_svg - len(badsvg)}/{n_svg}", "；".join(badsvg))
    leak = [x for x in re.findall(r"<text[^>]*>([^<>]*)</text>", html) if ('"xc-' in x or '", "' in x)]
    chk(not leak, "无 f-string 断裂字面量", ("；".join(leak[:2])) if leak else f"扫描 {len(re.findall(r'<text[^>]*>', html))} 个 text")
    chk(n_title == html.count("</title>"), "<title> 成对")
    chk("const " not in js and "let " not in js and "<script" not in js, "JS 纯 IIFE")

    # ── 数据实测 ──
    print("─" * 74)
    print(f"02：n={len(c.fc)} r={num(c.r_fc, 2)} ／ 差异 最大 {pp(c.diff_hi[0]['diff'])}（{c.diff_hi[0]['short']}）"
          f" 最小 {pp(c.diff_lo[0]['diff'])}（{c.diff_lo[0]['short']}）")
    print(f"03-1 票面 {pct(min(r['cpSen'] for r in c.pri))}–{pct(max(r['cpSen'] for r in c.pri))}"
          f"（跨度 {num((max(r['cpSen'] for r in c.pri) - min(r['cpSen'] for r in c.pri)) * 10000, 0)}bp）"
          f" ／ 偏差 {bp(min(r['devPri'] for r in c.pri))} ~ {bp(max(r['devPri'] for r in c.pri))}"
          f" 中位 {bp(_med(c.devPri))}")
    print(f"03-2 优先档 |偏差| 中位 {bp(_med(c.devPri))} 最大 {bp(max(c.devPri))} n={len(c.pri)}")
    print(f"03-3 次级档 XIRR {pct(c.sub_min)}–{pct(c.sub_max)} 中位 {pct(c.sub_med)} n={len(c.subAll)}"
          f" ／ 银行行数 {len(c.sub_rows)}")
    print(f"03-4 超额收益 Top10 合计 {amt(sum(r['subExcess'] or 0 for r in c.exc_top))}"
          f" ／ Bottom5 最小 {amt(c.exc_bot[0]['subExcess'])} ／ 其他 n={len(c.exc_rest)}")
    print(f"04 瀑布 {c.wf_n} 单 流入 {yi(c.wf_rec)} 亿 流出 {yi(c.wf_out)} 亿 结余 {yi(c.wf_end)} 亿 ／ "
          f"逐期 {len(c.per_rows)} 段（n {min(c.per_n.values())}–{max(c.per_n.values())}）／ "
          f"费用帕累托 {len(c.fee_rows)} 项，合计 {yi(c.fee_total)} 亿")
    print(f"05 银行 {len(c.banks)} 家 ／ 品种 {len(c.cats_agg)} 类 ／ "
          f"优先 XIRR 中位 {pct(_med([r['xirrSen'] for r in c.recs]))} ／ 次级中位 {pct(c.sub_med)}")
    print("─" * 74)
    if problems:
        print("存在问题：" + "、".join(problems))
        return 1
    print(f"自检通过 ✔  HTML {len(html):,} 字符 · SVG {n_svg} 张 · 4 张 03 图 · 倒算 1 次（指定图注） · EXIT 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
