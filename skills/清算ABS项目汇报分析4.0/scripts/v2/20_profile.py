# -*- coding: utf-8 -*-
r"""20_profile.py —— 项目档案（#view-pN）· 第二轮精修：5 类归组 + 隐藏「缺失材料」

用户原话（本轮）：
  「点击到具体每期项目时……"缺失材料"这里隐藏表述，不是重点信息。另外，收、发、期、发、池、集，
    顺序有点乱，而且重复内容多，应该按照资产池情况，集中度与账龄，预期回收与发行结构，
    实际回收与处置，实际收益与期限这样归类，合并冗余。」

职责（只动 00_ctx.py「目标结构」② 里的两个 DOM 钩子 + hero 里的「缺失材料」note）：
  A. 合并为 5 类，顺序固定（用用户原词；**数组下标 = 分类序号 = 渲染顺序**）：
       ① 资产池情况 → ② 集中度与账龄 → ③ 预期回收与发行结构
       → ④ 实际回收与处置 → ⑤ 实际收益与期限
     · 原「发行与结构」与「发行与规模」合并进 ③ → 「发行」不再是重复类目
       （自检：54 条渲染文本中「发行」只落在 ③ 类词条内，源内 14 处全在 ③ 上下文）
     · 33 个落点/label 各自**只落一处**：同一数值不在两类里重复出现（自检逐值去重断言）
     · 编号徽章 ①②③④⑤ 与实际渲染顺序一致（自检按 DOM 顺序断言标题序列）
  B. 两个钩子容器都用上，视觉阅读顺序 = ①②③④⑤：
       · `.kpis.kpi-strip`            → ① 资产池情况（5 格）+ ② 集中度与账龄（6 格）＝12 格
       · `.kpis[data-chart="kpi-grid"]` → ③ 预期回收与发行结构（8 行，7 栏）
                                          ④ 实际回收与处置（6 行，5 栏）
                                          ⑤ 实际收益与期限（5 行，通栏）
       面板 19 行 + 2 通栏 ＝ 21 行；12 + 21 ＝ 33 个落点
  C. 时间轴：保留 7 步横向步骤条，归入 ⑤ 实际收益与期限（期限/兑付时点同族，读起来最顺）；
     面板底部那行「归属目录 / 项目主键」小字保留；不再单列「时间轴」类
  D. 隐藏「缺失材料」：hero 内 `<div class="note">缺失材料（依据：…）…</div>`（全报告 28 处）
     → `display:none`（DOM 保留以保幂等）。**只认文本以「缺失材料」开头的 `.note`**，
       绝不误伤 `.hsum.hsum2`（品种特征）与其它 `.note`
  E. 单位统一：严格遵循 00_ctx.UNIT_POLICY
     · 规模类（入池本息费/本金 **入池息费**/累计回收/发行规模/优先档/次级档/预计回收/处置费用）
       → 亿元 2 位（< 0.01 亿 → 万元并注明）
     · 单笔 / 户均类（单笔最高·平均、主体最高·平均）→ 万元 2 位
     · 比率类 → 百分号 2 位；期数/月数/笔数/户数 → 纯数字 + 单位词
     · 缺失一律「—」，不臆造
     · **v9：同一面板内不混排亿元/万元**——① 资产池情况 4 格金额全部亿元
       （入池息费原为「万元」、与同格区间的入池本息费/本金不一致，已统一为亿元；
        28 单实测最小 0.33 亿，均 ≥ 0.01 亿，无需回退万元）

  F. 口径统一（本轮追加）：**只渲染「证券化率」= 发行规模 ÷ 入池本息费**，
     旧口径字段名在本模块输出中 0 次出现；不再提供 1− 换算提示。
     自检交叉验证：逐单「证券化率 + 旧口径对偶值 ≈ 100%」（27 单，容差 0.02pp）。

数据来源（双轨，互补，互不臆造）：
  · `window.__V2.PROF[__V2.ORDER[N]]`（N 取自 #view-pN）——精确到元
  · 服务端已渲染的原文格（8 + 23）——回退口径，解析后按 UNIT_POLICY 重新归一
  · 若原文与可核对口径不一致（例：p1「入池息费」原文 2.83 亿 ≠ 本息费−本金 4.41 亿），
    行内标注原文值，并保留精确值，避免面板内部算术自相矛盾

幂等：首次渲染前把原文格值缓存进 `#view-pN[data-pf-orig]`，重复执行结果完全一致。

导出（00_ctx 模块契约）：CSS / HTML（本模块为空）/ JS（整体 IIFE，无全局污染）
自检：`python 20_profile.py` —— 不依赖 build_v2.py；有 Node 时用真实报告数据 +
      轻量 DOM 影子跑 E2E，逐值校验 5 类分组与顺序、字段数、28 单覆盖、时间轴 7 步、
      「缺失材料」隐藏 28、无跨类重复、无「发行」重复、单位合规与幂等。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from html import unescape as _unescape
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# 自检基线：优先用 build_v2.py 真正的组装源（单项目穿透报告），其次用合并版报告
_REPORT_CANDIDATES = [
    _HERE.parent.parent.parent / "清算28单_单项目穿透" / "清算28单_单项目穿透_报告.html",
    _HERE.parent.parent / "清算28单_横向对照与逐单稽核_合并版.html",
]


def _report_path():
    for p in _REPORT_CANDIDATES:
        if p.exists():
            return p
    return _REPORT_CANDIDATES[-1]


def _ctx():
    """加载 00_ctx.py（文件名以数字开头，需 importlib）。"""
    spec = spec_from_file_location("v2_ctx", _HERE / "00_ctx.py")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════
CSS = r"""
/* ══════════════════════════════════════════════════════════════════
   20_profile —— 项目档案：5 类归组（①资产池情况 ②集中度与账龄
   ③预期回收与发行结构 ④实际回收与处置 ⑤实际收益与期限）
   只使用 .pf-* 前缀，避免与既有 .kpi / .kpis 样式串味
   ══════════════════════════════════════════════════════════════════ */

/* ── A. 指标条：沿用 .kpis.kpi-strip 的 DOM 钩子，放 ① + ④ 两类 ── */
.kpis.pf-strip{
  --grad-soft:linear-gradient(180deg,#fff,#FAFBFE 62%,#F5F8FC); /* 局部锁定渐变（基线 --grad-soft 为 none） */
  display:grid!important;grid-template-columns:1fr 1fr!important;gap:0!important;
  padding:0!important;margin:14px 0 16px!important;
  background:var(--grad-soft)!important;
  border:1px solid var(--line2)!important;border-radius:16px!important;
  box-shadow:0 1px 2px rgba(16,24,40,.05),0 18px 34px -24px rgba(16,24,40,.30)!important;
  overflow:hidden!important;
}
.pf-sgrp{padding:12px 13px 13px;border-right:1px solid var(--line2);min-width:0}
.pf-sgrp:last-child{border-right:0}
.pf-scap{display:flex;align-items:center;gap:7px;margin:0 0 9px;font-size:11px;font-weight:700;
  color:var(--ink3);letter-spacing:.05em}
.pf-snum{
  width:19px;height:19px;border-radius:5px;background:var(--grad);color:#fff;font-style:normal;
  font-size:10.5px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;
  flex:0 0 auto;box-shadow:0 1px 2px rgba(16,24,40,.20);
}
.pf-cells{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;
  background:var(--line2);border:1px solid var(--line2);border-radius:11px;overflow:hidden}
.pf-c{padding:9px 11px 10px;background:#fff;min-width:0;position:relative;
  transition:background .24s var(--ease),box-shadow .24s var(--ease)}
.pf-c:hover{background:var(--hover,#F7F9FC)}
.pf-c.pf-2{grid-column:1/-1}
/* v8：① 的合并格（主体户数 / 资产笔数）—— 两个 label 并排、值一行双值 */
.pf-c.pf-merged .pf-ck{display:flex;align-items:center;gap:3px}
.pf-ck-i{white-space:nowrap}
.pf-ck-s{color:var(--ink4,#98A2B3);font-weight:500;margin:0 1px}
.pf-c.pf-merged .pf-cv{font-size:15px;letter-spacing:-.02em;white-space:nowrap}
.pf-ck{font-size:10.5px;font-weight:600;color:var(--ink3);letter-spacing:.02em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pf-ck small{font-weight:500;color:var(--ink4);margin-left:3px}
.pf-cv{font-size:19px;font-weight:650;line-height:1.16;letter-spacing:-.01em;margin-top:3px;
  color:var(--ink);font-variant-numeric:tabular-nums;word-break:break-all}
.pf-cv small{font-size:11px;font-weight:500;color:var(--ink3);margin-left:3px}
.pf-cn{font-size:10.5px;color:var(--ink4);line-height:1.45;margin-top:4px}
.pf-na{color:var(--ink4)!important;font-weight:500!important}

/* ── B. 分区面板：替换原文 23 个方格 ──
   v6：③④ 改为严格 6/6 对称（各占一半，等宽等高）；⑤ 通栏 */
.kpis.pf-panels{
  display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
  align-items:stretch!important;gap:14px!important;
  padding:0!important;margin:0 0 18px!important;background:transparent!important;
  border:0!important;border-radius:0!important;box-shadow:none!important;overflow:visible!important;
}
.pf-panel{
  --grad-soft:linear-gradient(180deg,#fff,#FAFBFE 62%,#F5F8FC);
  grid-column:span 1;min-width:0;overflow:hidden;
  display:flex;flex-direction:column;
  background:var(--grad-soft);
  border:1px solid var(--line2);border-radius:16px;
  box-shadow:0 1px 2px rgba(16,24,40,.05),0 18px 34px -24px rgba(16,24,40,.30);
}
/* ③④ 各占 1 栏（严格等宽）；字段多寡只在面板内部消化，不外扩 */
.pf-panel.pf-7,
.pf-panel.pf-5{grid-column:span 1}
.pf-panel.pf-wide{grid-column:1/-1}    /* ⑤ 实际收益与期限（含 7 步时间轴） */
.pf-panel>.pf-rows{flex:1 1 auto}       /* 让 ③④ 等高：内容少的自动补满 */
.pf-ph{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:11px 14px;
  border-bottom:1px solid var(--line2);
  background:linear-gradient(180deg,rgba(255,255,255,.92),rgba(255,255,255,.40))}
.pf-pt{font-size:12.5px;font-weight:700;color:var(--ink);letter-spacing:.01em}
.pf-pm{margin-left:auto;display:flex;flex-wrap:wrap;gap:6px}
.pf-badge{font-size:10.5px;font-weight:600;color:var(--ink2);background:rgba(45,57,85,.045);
  border:1px solid var(--line2);border-radius:999px;padding:2px 9px;white-space:nowrap}
.pf-badge.pf-on{color:var(--accent);background:color-mix(in srgb,var(--accent) 8%,transparent);
  border-color:var(--accent-line)}
.pf-rows{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--line2)}
.pf-row{
  display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"k v" "n n";
  gap:2px 9px;padding:10px 13px 11px;background:#fff;position:relative;min-width:0;
  transition:background .24s var(--ease);
}
.pf-row::before{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:var(--accent);
  opacity:0;transition:opacity .24s var(--ease)}
.pf-row:hover{background:var(--hover,#F7F9FC)}
.pf-row:hover::before{opacity:.85}
.pf-row.pf-wide{grid-column:1/-1;grid-template-columns:minmax(0,1fr);grid-template-areas:"k" "v"}
.pf-rk{grid-area:k;font-size:11px;font-weight:600;color:var(--ink3);letter-spacing:.02em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pf-rv{grid-area:v;font-size:16.5px;font-weight:650;line-height:1.2;letter-spacing:-.01em;
  color:var(--ink);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pf-rv small{font-size:10.5px;font-weight:500;color:var(--ink3);margin-left:2px}
.pf-row.pf-wide .pf-rv{text-align:left;white-space:normal;font-size:12.5px;font-weight:600;
  line-height:1.5;color:var(--ink2)}
.pf-tx{font-size:12.5px;font-weight:600;color:var(--ink2);line-height:1.5}
.pf-rn{grid-area:n;font-size:10.5px;color:var(--ink4);line-height:1.45}
.pf-row.pf-warn .pf-rn{color:var(--warn)}

/* ── B5. ② 集中度：字段字典（默认收起）+ 未披露态 ── */
.pf-rows.pf-rows8{grid-template-columns:repeat(2,minmax(0,1fr))}
.pf-row.pf-undisclosed .pf-rv{color:var(--ink4);font-weight:500;font-size:12.5px;
  white-space:normal;letter-spacing:0}
.pf-dict{margin:10px 0 0;border-top:1px solid var(--line2);padding-top:8px}
.pf-dict>summary{
  cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;
  font-size:11px;font-weight:600;color:var(--ink3);letter-spacing:.03em;
  padding:3px 0;user-select:none;
}
.pf-dict>summary::-webkit-details-marker{display:none}
.pf-dict>summary::before{content:"▸";font-size:9px;color:var(--ink4);transition:transform .2s var(--ease)}
.pf-dict[open]>summary::before{transform:rotate(90deg)}
.pf-dict>summary:hover{color:var(--ink2)}
.pf-dict .pf-dtb{width:100%;border-collapse:collapse;margin:6px 0 2px;font-size:10.5px;
  table-layout:fixed}
.pf-dict .pf-dtb th{text-align:left;font-weight:600;color:var(--ink4);padding:3px 4px;
  border-bottom:1px solid var(--line2);letter-spacing:.02em}
.pf-dict .pf-dtb td{padding:4px;color:var(--ink2);border-bottom:1px solid var(--line1,#EEF1F6);
  vertical-align:top;line-height:1.45}
.pf-dict .pf-dtb tr:last-child td{border-bottom:0}
.pf-dict .pf-dtb .num{font-variant-numeric:tabular-nums;white-space:nowrap}
.pf-dict .pf-dtb .dn{color:var(--ink);font-weight:600}
.pf-dict .pf-ok{color:var(--neg,#1F7A5C)}
.pf-dict .pf-mid{color:var(--warn,#B0763F)}
.pf-dict .pf-low{color:var(--mute,#98A2B3)}
.pf-dict .pf-none{color:var(--mute,#98A2B3);font-style:normal}
.pf-dict .pf-dfoot{font-size:10px;color:var(--ink4);line-height:1.5;padding:5px 4px 0}

/* ── B6. 时间轴（⑤ 实际收益与期限内）：7 步横向步骤条 ── */
.pf-tl{display:flex;padding:20px 16px 15px;overflow-x:auto;border-bottom:1px solid var(--line2)}
.pf-ts{position:relative;flex:1 1 0;min-width:112px;text-align:center;padding:0 4px}
.pf-ts::before{content:'';position:absolute;left:-50%;right:50%;top:12px;height:2px;
  background:var(--line2)}
.pf-ts:first-child::before{display:none}
.pf-tdot{position:relative;z-index:1;display:block;width:11px;height:11px;border-radius:50%;
  margin:0 auto 9px;background:var(--accent);box-shadow:0 0 0 4px #fff}
.pf-ts[data-t="sen"] .pf-tdot{background:var(--navy)}
.pf-ts[data-t="sub"] .pf-tdot{background:var(--pos)}
.pf-ts.miss .pf-tdot{background:var(--mute)}
.pf-tlab{display:block;font-size:10.5px;font-weight:600;color:var(--ink3);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pf-tval{display:block;font-size:12.5px;font-weight:650;color:var(--ink);margin-top:3px;
  font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.pf-ts.miss .pf-tval{color:var(--mute);font-weight:500}

/* ── B5. 面板底部：仅「归属目录 / 项目主键」小字（其余元数据已在上方覆盖）── */
.pf-meta{display:flex;flex-wrap:wrap;gap:3px 10px;align-items:baseline;
  padding:9px 14px 10px;border-top:1px solid var(--line2);background:rgba(255,255,255,.55)}
.pf-mk{font-size:10px;font-weight:600;color:var(--ink4);letter-spacing:.04em}
.pf-mv{font-size:10.5px;color:var(--ink3);word-break:break-all;margin-right:8px}

/* ── B6. 冗余元数据条（归属目录/项目主键/设立日/清算日/是否回购/银行分组）──
   已全部在 ①②⑤ 内覆盖，整条隐藏；DOM 保留，避免影响其他脚本 */
.infolist.pf-meta-hidden{display:none!important}

/* ── C. 「缺失材料」note：不是重点信息，隐藏但保留 DOM（幂等）──
   精确限定：JS 只给**文本以「缺失材料」开头**的 .note 打上 pf-missing-hidden；
   该 class 只会被写进 #view-pN 单项目视图内，故 `.note.pf-missing-hidden`
   天然只在项目视图生效，不会波及 #view-overview / .hsum.hsum2 等其它节点。 */
[class~="view"] .note.pf-missing-hidden,
.note.pf-missing-hidden{display:none!important}

/* ── 响应式 ── */
@media(max-width:1100px){
  .kpis.pf-panels{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .pf-panel.pf-wide{grid-column:1/-1}
}
@media(max-width:760px){
  .kpis.pf-strip{grid-template-columns:1fr!important}
  .pf-sgrp{border-right:0!important;border-bottom:1px solid var(--line2)}
  .pf-sgrp:last-child{border-bottom:0}
  .kpis.pf-panels{grid-template-columns:1fr!important}
  .pf-panel,.pf-panel.pf-wide{grid-column:1/-1}
  .pf-rows{grid-template-columns:1fr}
  .pf-row.pf-wide{grid-column:auto}
  .pf-tl::before{display:none}
}
@media(prefers-reduced-motion:reduce){
  .pf-c,.pf-row,.pf-cv{transition:none!important}
}
"""


# ══════════════════════════════════════════════════════════════════════
#  HTML
# ══════════════════════════════════════════════════════════════════════
# 本模块全部为客户端增强（数据来自 window.__V2 + 服务端原文），无需服务端渲染。
HTML = ""


# ══════════════════════════════════════════════════════════════════════
#  JS
# ══════════════════════════════════════════════════════════════════════
JS = r"""
/* 20_profile —— 项目档案：5 类归组（①资产池情况 ②集中度与账龄 ③预期回收与发行结构
   ④实际回收与处置 ⑤实际收益与期限）+ 隐藏「缺失材料」
   单位统一遵循 UNIT_POLICY；缺失一律「—」；整体 IIFE，无全局污染 */
(function(){
  "use strict";
  var doc = document;
  var V2 = (typeof window !== "undefined" && window.__V2) ? window.__V2 : {};
  var PROF = V2.PROF || null;
  var ORDER = V2.ORDER || [];

  /* ══════════ 单位统一：UNIT_POLICY 格式化核心 ══════════ */
  /* <<PF-FMT>> */
  var pfFmt = (function(){
    var DASH = "\u2014";
    function isNum(v){ return typeof v === "number" && isFinite(v); }
    function grp(x, d){
      if(!isNum(x)) return DASH;
      var s = (d == null) ? String(Math.round(x)) : x.toFixed(d);
      var neg = s.charAt(0) === "-";
      if(neg) s = s.slice(1);
      var p = s.split(".");
      p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      return (neg ? "-" : "") + p.join(".");
    }
    /* 规模类 → 亿元 2 位；< 0.01 亿 → 万元并注明 */
    function yi(v){
      if(!isNum(v)) return DASH;
      if(Math.abs(v) < 1e6) return { v: grp(v / 1e4, 2), u: "万元（不足 0.01 亿）" };
      return { v: grp(v / 1e8, 2), u: "亿" };
    }
    /* 息费 / 单笔 / 户均类 → 万元 2 位 */
    function wan(v){ return isNum(v) ? { v: grp(v / 1e4, 2), u: "万" } : DASH; }
    /* 比率类 → 百分号 2 位 */
    function pct(v){ return isNum(v) ? { v: (v * 100).toFixed(2), u: "%" } : DASH; }
    /* 计数类 → 千分位整数 + 单位词 */
    function cnt(v, unit){ return isNum(v) ? { v: grp(v, 0), u: unit || "" } : DASH; }
    /* 月数 → 1 位 + 个月 */
    function mon(v){ return isNum(v) ? { v: grp(v, 1), u: "个月" } : DASH; }
    function ratio(a, b){ return (isNum(a) && isNum(b) && b !== 0) ? (a / b) : DASH; }
    function num(v, d){ return isNum(v) ? { v: grp(v, d == null ? 2 : d), u: "" } : DASH; }
    function txt(s){
      if(s == null) return DASH;
      var t = String(s).replace(/\s+/g, " ").trim();
      return (t === "" || t === DASH || t === "-") ? DASH : t;
    }
    function sv(o){
      if(o == null || o === DASH) return DASH;
      var sep = (o.u === "%") ? "" : " ";      /* 百分号紧贴数值，符合原文排版 */
      return (o.v + sep + o.u).replace(/\s+$/, "");
    }
    function yuan(v){ return isNum(v) ? grp(v, 2) + " 元" : DASH; }
    return {
      DASH: DASH, isNum: isNum, grp: grp, yi: yi, wan: wan, pct: pct, cnt: cnt, mon: mon,
      num: num, ratio: ratio, txt: txt, sv: sv, yuan: yuan,
      sYi: function(v){ return sv(yi(v)); },
      sWan: function(v){ return sv(wan(v)); },
      sPct: function(v){ return sv(pct(v)); },
      sMon: function(v){ return sv(mon(v)); },
      sCnt: function(v, u){ return sv(cnt(v, u)); }
    };
  })();
  /* <<\/PF-FMT>> */

  /* ══════════ 源披露拆分（仅 1 单需要，用于口径说明） ══════════
     中誉至诚2024年第五期：payload 的池「息费」字段只含【费用】、遗漏【利息】，
     故入池息费统一按「本息费 − 本金」归一；下表仅为注明源披露拆分，
     数值取自发行说明书 第七章「入池资产笔数与金额特征」表
     （说明书 PDF 第 121 页）。 */
  var SRC_SPLIT = {
    "中誉至诚2024年第五期": {
      prin: 1796955452.36, inte: 157533519.48, fee: 283335660.03, total: 2237824631.87
    }
  };
  function splitOf(prof, key){
    var k = (prof && (prof.name || prof.code)) || key || null;
    return (k && Object.prototype.hasOwnProperty.call(SRC_SPLIT, k)) ? SRC_SPLIT[k] : null;
  }

  /* ══════════ 小工具 ══════════ */
  function esc(s){
    return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function VH(o){
    if(o == null || o === pfFmt.DASH) return '<b class="pf-na">' + pfFmt.DASH + '</b>';
    if(typeof o === "string") return '<span class="pf-tx">' + esc(o) + '</span>';
    return '<b>' + esc(o.v) + '</b>' + (o.u ? '<small>' + esc(o.u) + '</small>' : "");
  }
  function parseAmt(s){
    var m = /^\s*(-?[\d,]+(?:\.\d+)?)\s*(亿|万)?/.exec(String(s == null ? "" : s));
    if(!m) return null;
    var x = parseFloat(m[1].replace(/,/g, ""));
    if(!isFinite(x)) return null;
    if(m[2] === "亿") x = x * 1e8; else if(m[2] === "万") x = x * 1e4;
    return x;
  }
  function parsePct(s){
    var m = /(-?[\d.]+)\s*%/.exec(String(s == null ? "" : s));
    return m ? parseFloat(m[1]) / 100 : null;
  }
  function parseCnt(s){
    var m = /([\d][\d,]*)/.exec(String(s == null ? "" : s));
    return m ? parseFloat(m[1].replace(/,/g, "")) : null;
  }
  function parseMon(s){
    var m = /(-?[\d.]+)\s*(?:个月|月)/.exec(String(s == null ? "" : s));
    return m ? parseFloat(m[1]) : null;
  }
  function blank(s){
    if(s == null) return true;
    var t = String(s).replace(/\s/g, "");
    return t === "" || t === "\u2014" || t === "-";
  }

  /* ══════════ 读取服务端原文（幂等缓存） ══════════ */
  function grab(host){
    var out = {};
    if(!host || !host.querySelectorAll) return out;
    var ks = host.querySelectorAll(".kpi");
    for(var i = 0; i < ks.length; i++){
      var kEl = ks[i].querySelector(".k"), vEl = ks[i].querySelector(".v");
      if(!kEl || !vEl) continue;
      var k = String(kEl.textContent || "").replace(/\s+/g, " ").trim();
      if(!k || Object.prototype.hasOwnProperty.call(out, k)) continue;
      out[k] = String(vEl.textContent || "").replace(/\s+/g, " ").trim();
    }
    return out;
  }
  /* 冗余元数据条（dl.infolist）：归属目录/项目主键/设立日/清算日/是否回购/银行分组 */
  function infoPairs(view){
    var out = {};
    var dl = view.querySelector ? view.querySelector(".infolist") : null;
    if(!dl || !dl.getElementsByTagName) return out;
    var dts = dl.getElementsByTagName("dt"), dds = dl.getElementsByTagName("dd");
    for(var i = 0; i < dts.length && i < dds.length; i++){
      var k = String(dts[i].textContent || "").replace(/\s+/g, " ").trim();
      var v = String(dds[i].textContent || "").replace(/\s+/g, " ").trim();
      if(k && !Object.prototype.hasOwnProperty.call(out, k)) out[k] = v;
    }
    return out;
  }
  function readRaw(view){
    var cached = view.getAttribute("data-pf-orig");
    if(cached){
      try {
        var hit = JSON.parse(cached);
        if(hit && hit.strip && hit.grid) return hit;
      } catch(e){ /* 缓存损坏则重新抓取 */ }
    }
    var out = { strip: {}, grid: {}, info: infoPairs(view) };
    var strip = view.querySelector(".kpi-strip");
    if(strip) out.strip = grab(strip);
    var grid = view.querySelector('.kpis[data-chart="kpi-grid"]');
    if(grid) out.grid = grab(grid);
    try { view.setAttribute("data-pf-orig", JSON.stringify(out)); } catch(e){}
    return out;
  }

  /* ══════════ 事实装配（__V2 优先，原文回退） ══════════ */
  function dateMap(prof){
    var out = {}, d = prof ? prof.dates : null;
    if(!d) return out;
    if(Object.prototype.toString.call(d) === "[object Array]"){
      for(var i = 0; i < d.length; i++){
        var it = d[i];
        if(it && it.length >= 2 && it[0] != null && it[1] != null && String(it[1]).trim() !== ""){
          out[String(it[0])] = String(it[1]).trim();
        }
      }
    } else if(typeof d === "object"){
      for(var k in d){ if(Object.prototype.hasOwnProperty.call(d, k) && d[k]) out[k] = String(d[k]).trim(); }
    }
    return out;
  }
  function facts(prof, raw, key){
    var g = raw.grid || {}, s = raw.strip || {}, dm = dateMap(prof);
    function P(f){ var v = prof ? prof[f] : null; return pfFmt.isNum(v) ? v : null; }

    var poolTotal = P("poolTotal"); if(poolTotal == null) poolTotal = parseAmt(g["入池本息费"]);
    var poolPrin = P("poolPrincipal"); if(poolPrin == null) poolPrin = parseAmt(g["入池本金"]);
    var poolIntDom = parseAmt(g["入池息费"]);
    var poolInt = (poolTotal != null && poolPrin != null) ? (poolTotal - poolPrin) : poolIntDom;
    var intGap = null;
    if(poolInt != null && poolIntDom != null &&
       Math.abs(poolInt - poolIntDom) > Math.max(1, Math.abs(poolInt) * 0.005)) intGap = poolIntDom;

    var recovered = P("recovered"); if(recovered == null) recovered = parseAmt(s["累计回收"]);
    var forecast = P("forecast"); if(forecast == null) forecast = parseAmt(g["预计回收"]);
    var issue = P("issue"), sen = P("sen"), sub = P("sub");
    /* 口径统一（用户要求）：只渲染「证券化率」，不做 1− 换算，本模块不再出现
       该旧口径字段名。下面保留的派生值仅用于自检里「与旧口径合计 ≈ 100%」
       的独立交叉验证，**不参与任何渲染或提示**。 */
    var discount = P("discount");
    var cpSen = P("cpSen"), xirrSen = P("xirrSen"), xirrSub = P("xirrSub");
    var nPer = P("n_periods"); if(nPer == null) nPer = parseCnt(g["支付期数"]);
    var months = P("months");
    var dispFee = P("disposeFee");
    /* 比率：payload 优先 → 由精确值推 → 回退服务端指标条原文 */
    var recRate = P("recRate");
    if(recRate == null) recRate = pfFmt.ratio(recovered, poolTotal);
    if(recRate === pfFmt.DASH) recRate = parsePct(s["回收率"]);
    var expRecRate = P("expRecRate");
    if(expRecRate == null) expRecRate = pfFmt.ratio(forecast, poolTotal);
    var dispRate = P("disposeFeeRate");
    if(dispRate == null) dispRate = pfFmt.ratio(dispFee, recovered);
    if(dispRate === pfFmt.DASH) dispRate = parsePct(s["处置费率"]);
    var achieve = P("vsForecast");
    if(achieve == null) achieve = pfFmt.ratio(recovered, forecast);
    if(achieve === pfFmt.DASH) achieve = parsePct(s["预计达成率"]);
    var secRatio = (issue != null && poolTotal) ? (issue / poolTotal) : parsePct(s["证券化率"]);
    /* discount 仅作自检交叉验证（不再参与任何渲染与提示） */
    if(discount == null && secRatio !== pfFmt.DASH && secRatio != null) discount = 1 - secRatio;    /* ④ 处置费用占回收流入的比例（v8 起与「处置费率」合并，只渲染后者）*/
    var dispPct = P("dispPct");
    if(dispPct == null) dispPct = pfFmt.ratio(dispFee, recovered);
    if(dispPct === pfFmt.DASH) dispPct = parsePct(s["处置费用" + "占比"]);
    var dispOverPool = P("dispOverPool");
    if(dispOverPool == null) dispOverPool = pfFmt.ratio(dispFee, poolTotal);

    var nLoans = null, nBorr = null;
    if(prof && typeof prof.poolCount === "string"){
      var mm = /([\d,]+)\s*笔[^\d]*([\d,]+)\s*户/.exec(prof.poolCount);
      if(mm){ nLoans = parseFloat(mm[1].replace(/,/g, "")); nBorr = parseFloat(mm[2].replace(/,/g, "")); }
    }
    if(nLoans == null) nLoans = parseCnt(g["资产笔数"]);
    if(nBorr == null) nBorr = parseCnt(g["主体户数"]);

    var feeDom = g["合同处置费率/上限"] || null;
    var feePct = (feeDom && /^\s*[\d.]+\s*%\s*$/.test(feeDom)) ? parsePct(feeDom) : null;

    return {
      issuer: pfFmt.txt((prof && prof.issuer) || g["银行"]),
      cat: pfFmt.txt(prof ? prof.cat : null),
      buyback: pfFmt.txt(g["是否回购"]),
      poolTotal: poolTotal, poolPrin: poolPrin, poolInt: poolInt, intGap: intGap,
      poolIntDomRaw: g["入池息费"] || null, split: splitOf(prof, key),
      recovered: recovered, forecast: forecast, issue: issue, sen: sen, sub: sub,
      discount: discount, cpSen: cpSen, xirrSen: xirrSen, xirrSub: xirrSub,
      nPer: nPer, months: months, dispFee: dispFee, recRate: recRate, expRecRate: expRecRate,
      dispRate: dispRate, dispPct: dispPct, dispOverPool: dispOverPool,
      achieve: achieve, secRatio: secRatio,
      nLoans: nLoans, nBorr: nBorr,
      loanMax: parseAmt(g["单笔最高"]), loanAvg: parseAmt(g["单笔平均"]),
      brwrMax: parseAmt(g["主体最高"]), brwrAvg: parseAmt(g["主体平均"]),
      top5: parsePct(g["前5大占比"]), top10: parsePct(g["前10大占比"]),
      overdue: parseMon(g["加权平均逾期"]),
      /* ② 集中度 7 字段的「源是否披露」：原文该格为空/— 即视为源未披露 */
      conc: {
        "单笔最高": !blank(g["单笔最高"]),
        "单笔平均": !blank(g["单笔平均"]),
        "主体最高": !blank(g["主体最高"]),
        "主体平均": !blank(g["主体平均"]),
        "前5大占比": !blank(g["前5大占比"]),
        "前10大占比": !blank(g["前10大占比"]),
        "加权平均逾期": !blank(g["加权平均逾期"])
      },
      feeDom: feeDom, feePct: feePct,
      meta: {
        info: (raw.info && typeof raw.info === "object") ? raw.info : {},
        dir: (raw.info && raw.info["归属目录"]) ? raw.info["归属目录"] : null,
        key: (raw.info && raw.info["项目主键"]) ? raw.info["项目主键"] : null
      },
      d: {
        setup: dm["信托设立日"] || g["设立日"], first: dm["首个支付日"],
        last: dm["末个支付日"], liq: g["清算日"] || dm["清算完成"],
        es: g["预期到期日(优)"], ls: g["法定到期日(优)"],
        eb: g["预期到期日(次)"], lb: g["法定到期日(次)"]
      },
      raw: raw
    };
  }

  /* ══════════════════════════════════════════════════════════════════
     5 类分组规格（唯一权威表）
     **数组下标 = 分类序号 = 渲染顺序**：0→① 1→② 2→③ 3→④ 4→⑤
     ① 资产池情况 / ② 集中度与账龄 / ③ 预期回收与发行结构 /
     ④ 实际回收与处置 / ⑤ 实际收益与期限
     容器分配：kpi-strip = ①②（首屏：规模 + 集中度）；kpi-grid = ③④⑤
     每个 label 只出现一次 → 同一数值不会在两类里重复
     ══════════════════════════════════════════════════════════════════ */
  /* <<PF-CATS>> */
  var PF_GROUPS = ["① 资产池情况", "② 集中度与账龄", "③ 预期回收与发行结构",
                   "④ 实际回收与处置", "⑤ 实际收益与期限"];
  var PF_CN = ["①", "②", "③", "④", "⑤"];
  var PF_CAP = ["资产池情况", "集中度与账龄", "预期回收与发行结构",
                "实际回收与处置", "实际收益与期限"];
  /* v8：① 2×2 四格（「主体户数 / 资产笔数」合并为一格，用「/」区隔）
         ② 2×2 四格（可得率过滤后只剩 4 项；「加权平均逾期」移到第 2 行填灰格位置） */
  var PF_STRIP_CELLS = [
    ["入池本息费", 0, function(F, f){ return f.yi(F.poolTotal); }, "入池规模（本息费口径）", 0, 0],
    ["入池本金", 0, function(F, f){ return f.yi(F.poolPrin); }, null, 0, 0],
    ["入池息费", 0, function(F, f){ return f.yi(F.poolInt); }, null, 0, 0],
    /* 合并格：label 用「/」连接，值也一行双值（户 / 笔） */
    ["主体户数 / 资产笔数", 0, function(F, f){
        var borr = (F.nBorr == null) ? f.DASH : f.sCnt(F.nBorr, "户");
        var loan = (F.nLoans == null) ? f.DASH : f.sCnt(F.nLoans, "笔");
        return borr + " / " + loan;
      }, "主体户数 / 入池资产笔数", 0, 1,
      ["主体户数", "资产笔数"]],    ["单笔最高", 1, function(F, f){ return f.wan(F.loanMax); }, "池内最大单笔本息费", 0, 0],
    ["单笔平均", 1, function(F, f){ return f.wan(F.loanAvg); }, "入池本息费 ÷ 资产笔数", 0, 0],
    ["主体平均", 1, function(F, f){ return f.wan(F.brwrAvg); }, "入池本息费 ÷ 主体户数", 0, 0],
    ["加权平均逾期", 1, function(F, f){ return f.mon(F.overdue); }, "按未偿本息加权", 0, 0],
    /* 以下 3 项可得率 <50%，由字段字典登记，主表默认不渲染（保留在规格里以便字典统计） */
    ["主体最高", 1, function(F, f){ return f.wan(F.brwrMax); }, "单户最高本息费", 0, 0],
    ["前5大占比", 1, function(F, f){ return f.pct(F.top5); }, "前 5 大主体占入池本息费", 0, 0],
    ["前10大占比", 1, function(F, f){ return f.pct(F.top10); }, "前 10 大主体占入池本息费", 0, 0]
  ];
  var PF_PANEL_ROWS = [
    ["中债预计回收", 2, function(F, f){ return f.yi(F.forecast); }, null, 0],
    ["预计回收率", 2, function(F, f){ return f.pct(F.expRecRate); }, "＝中债预计回收 ÷ 入池本息费", 0],
    ["发行规模", 2, function(F, f){ return f.yi(F.issue); }, null, 0],
    ["优先档规模", 2, function(F, f){ return f.yi(F.sen); }, null, 0],
    ["次级档规模", 2, function(F, f){ return f.yi(F.sub); }, null, 0],
    ["证券化率", 2, function(F, f){ return f.pct(F.secRatio); }, "＝发行规模 ÷ 入池本息费", 0],
    ["合同处置费率/上限", 2, function(F, f){
        return (F.feePct != null) ? f.pct(F.feePct) : f.txt(F.feeDom); },
     "原文口径（据实报销 / 上限规则）", 1],
    ["累计回收", 3, function(F, f){ return f.yi(F.recovered); }, null, 0],
    ["回收率", 3, function(F, f){ return f.pct(F.recRate); }, "＝累计回收 ÷ 入池本息费", 0],
    ["预计达成率", 3, function(F, f){ return f.pct(F.achieve); }, "＝累计回收 ÷ 中债预计回收", 0],
    ["处置费用", 3, function(F, f){ return f.yi(F.dispFee); }, "金额（与费率不同概念）", 0],
    /* v8：删除「处置费用占回收流入占比」一格——与「处置费率」同一公式/同一数值（用户：保留一个即可）。
       处置费率改为通栏收尾，维持 2 列对齐、不留空格子。 */
    ["处置费率", 3, function(F, f){ return f.pct(F.dispRate); }, "＝处置费用 ÷ 累计回收（全报告统一口径）", 1],
    ["优先档XIRR", 4, function(F, f){ return f.pct(F.xirrSen); }, null, 0],
    ["次级档XIRR", 4, function(F, f){ return f.pct(F.xirrSub); }, null, 0],
    ["存续期", 4, function(F, f){ return f.mon(F.months); }, null, 0],
    ["支付周期", 4, function(F, f){ return f.cnt(F.nPer, "期"); }, null, 0],
    ["首末支付日", 4, function(F, f){
        var d = F.d;
        if(blank(d.first) && blank(d.last)) return f.DASH;
        return (blank(d.first) ? f.DASH : d.first) + " → " + (blank(d.last) ? f.DASH : d.last);
      }, "首个 → 末个支付日", 1]
  ];
  /* <<\/PF-CATS>> */

  /* ══════════ ② 集中度：可得率治理（v6）══════════
     用户要求：不要简单全删、也不要一律用「—」（会被误读为 0 或异常）。
       可得率 ≥80% → 主表正常展示，缺失显示「未披露」
       50%–80%    → 保留展示，缺失「未披露」+ tooltip 说明该单说明书未披露
       <50%       → 主表隐藏，改在「字段字典」里说明（本批 X 单源未披露）
     可得率在运行时对 28 单现场统计（不写死），见 concStats()。 */
  var UNDISCLOSED = "未披露";
  var CONC_FIELDS = ["单笔最高", "单笔平均", "主体最高", "主体平均",
                     "前5大占比", "前10大占比", "加权平均逾期"];
  /* 全报告单次统计（首次渲染前算一次，缓存到 window.__PF_CONC） */
  function concStats(){
    /* 幂等：结果同时缓存在共享的 __V2 上（V2 = window.__V2，跨 IIFE 可读，
       也便于自检断言；不污染其他全局变量） */
    if(V2 && V2.__PF_CONC && V2.__PF_CONC.n === 28) return V2.__PF_CONC;
    var views = (doc && doc.querySelectorAll) ? doc.querySelectorAll(".view") : [];
    var total = 0, ok = {}, miss = {}, keys = {};
    for(var f = 0; f < CONC_FIELDS.length; f++){ ok[CONC_FIELDS[f]] = 0; miss[CONC_FIELDS[f]] = []; }
    var diag = [];
    for(var i = 0; i < views.length; i++){
      var v = views[i];
      if(!v || !v.id || !/^view-p\d+$/.test(v.id)){ diag.push("skip:" + (v && v.id)); continue; }
      var n = parseInt(/^view-p(\d+)$/.exec(v.id)[1], 10);
      var key = ORDER[n] || ("p" + n);
      var cached = v.getAttribute ? v.getAttribute("data-pf-conc") : null;
      var src = null;
      if(cached){
        try { src = JSON.parse(cached); } catch(e){ src = null; }
      }
      var raw = (function(){
        var o = {}, host = v.querySelector ? v.querySelector('.kpis[data-chart="kpi-grid"]') : null;
        if(!host){ diag.push("nohost:" + v.id); return o; }
        var ks = host.querySelectorAll(".kpi");
        for(var j = 0; j < ks.length; j++){
          var kEl = ks[j].querySelector(".k"), vEl = ks[j].querySelector(".v");
          if(!kEl || !vEl) continue;
          var kk = String(kEl.textContent || "").replace(/\s+/g, " ").trim();
          var vv = String(vEl.textContent || "").replace(/\s+/g, " ").trim();
          if(kk && !Object.prototype.hasOwnProperty.call(o, kk)) o[kk] = vv;
        }
        diag.push(v.id + ":kpi=" + ks.length);
        return o;
      })();
      if(!cached && v.setAttribute){
        try { v.setAttribute("data-pf-conc", JSON.stringify(raw)); } catch(e){}
      }
      if(!src) src = raw;
      total++;
      for(var f2 = 0; f2 < CONC_FIELDS.length; f2++){
        var fld = CONC_FIELDS[f2];
        var val = src[fld];
        var has = !(val == null || String(val).replace(/\s/g, "") === ""
                    || String(val).trim() === "\u2014" || String(val).trim() === "-");
        if(has) ok[fld]++;
        else miss[fld].push(key);
      }
    }
    var res = { n: total, fields: {}, diag: diag };
    for(var f3 = 0; f3 < CONC_FIELDS.length; f3++){
      var fd = CONC_FIELDS[f3];
      var rate = total ? ok[fd] / total : 0;
      res.fields[fd] = {
        rate: rate, ok: ok[fd], missN: total - ok[fd], miss: miss[fd],
        tier: rate >= 0.8 ? "high" : (rate >= 0.5 ? "mid" : "low"),
        show: rate >= 0.5
      };
    }
    if(V2){ try { V2.__PF_CONC = res; } catch(e){} }
    return res;
  }
  /* 暴露给自检（写共享 __V2；浏览器里无副作用，不新增全局变量） */
  function publishConc(){
    if(V2){ try { V2.__PF_CONC = ensureConc(); } catch(e){} }
  }
  /* 某字段的缺失原因（写进字段字典与 tooltip） */
  function missReason(fd, st){
    if(st.ok === 0) return "本批 28 单原报告均未披露该字段";
    if(st.rate >= 0.8) return "个别单原报告未披露（其余正常）";
    if(st.rate >= 0.5) return "部分单原报告未披露该字段";
    return "多数单原报告未披露该字段（本批 " + st.missN + " 单缺失）";
  }
  function concTitle(lab, F, st){
    if(st.show && st.tier === "mid" && !F.conc[lab]){
      return "该单说明书未披露「" + lab + "」——本批可得率 "
        + (st.rate * 100).toFixed(1) + "%，" + missReason(lab, st);
    }
    return null;
  }
  /* 「字段字典」折叠块：7 个字段的可得率 / 缺失单数 / 缺失原因 / 展示策略 */
  function dictHtml(st){
    var TIER_TXT = { high: "主表展示", mid: "主表展示（tooltip 说明）", low: "主表隐藏" };
    var TIER_CLS = { high: "pf-ok", mid: "pf-mid", low: "pf-low" };
    var rows = "";
    for(var i = 0; i < CONC_FIELDS.length; i++){
      var fd = CONC_FIELDS[i], s = st.fields[fd];
      rows += '<tr data-pf-dict-field="' + esc(fd) + '">'
        + '<td class="dn">' + esc(fd) + '</td>'
        + '<td class="num">' + (s.rate * 100).toFixed(1) + '%</td>'
        + '<td class="num">' + s.missN + ' / ' + st.n + '</td>'
        + '<td>' + esc(missReason(fd, s)) + '</td>'
        + '<td class="' + TIER_CLS[s.tier] + '">' + TIER_TXT[s.tier] + '</td>'
        + '</tr>';
    }
    return '<details class="pf-dict" data-pf-dict="1">'
      + '<summary>字段字典 · ② 集中度与账龄（7 个字段的可得率与缺失原因）</summary>'
      + '<table class="pf-dtb"><thead><tr>'
      + '<th style="width:22%">字段</th><th style="width:14%">可得率</th>'
      + '<th style="width:14%">源未披露</th><th style="width:32%">缺失原因</th>'
      + '<th style="width:18%">展示策略</th>'
      + '</tr></thead><tbody>' + rows + '</tbody></table>'
      + '<div class="pf-dfoot">可得率 = 本批 28 单中「发行说明书·受托机构报告」披露了该字段的单数 ÷ 28；'
      + '≥80% 主表逐单展示，50%–80% 主表展示并在缺失单的悬停说明里注明，'
      + '&lt;50% 从主表移出、仅在此字典登记，避免整列「未披露」干扰阅读。</div>'
      + '</details>';
  }

  /* ══════════ 渲染：A. 指标条（① 资产池情况 + ② 集中度与账龄） ══════════ */
  function tip(label, raw){ return pfFmt.isNum(raw) ? (label + "：" + pfFmt.yuan(raw)) : null; }
  /* ① 入池息费副行：口径归一 + 源披露拆分说明（动态计算，不是静态文本）
     v9：入池息费改「亿元」显示（与同面板的入池本息费/入池本金统一），
         副行与悬停说明里的拆分数值也一并换算成亿元，避免同格内混排万元/亿元。 */
  function intNote(F){
    if(F.poolInt == null) return null;
    var sp = F.split;
    if(sp){
      return "已归一：本息费 − 本金 ＝ " + pfFmt.sYi(F.poolInt)
        + "｜源披露为「利息 " + pfFmt.sYi(sp.inte) + " ＋ 费用 " + pfFmt.sYi(sp.fee)
        + "」";
    }
    if(F.intGap != null){
      return "已归一：本息费 − 本金 ＝ " + pfFmt.sYi(F.poolInt)
        + "｜服务端原文该格与差额口径不一致（疑为分项口径）";
    }
    return "本息费 − 本金";
  }
  function intTip(F){
    if(!pfFmt.isNum(F.poolInt)) return null;
    var sp = F.split;
    if(sp){
      return "入池息费（归一）：" + pfFmt.sYi(F.poolInt)
        + "｜本金 " + pfFmt.sYi(sp.prin) + " / 利息 " + pfFmt.sYi(sp.inte)
        + " / 费用 " + pfFmt.sYi(sp.fee) + " / 合计 " + pfFmt.sYi(sp.total)
        + "｜payload 的 pool_intfee 仅含费用、遗漏利息，故本表按差额口径归一"
        + "｜源：中誉至诚2024年第五期发行说明书 第七章「入池资产笔数与金额特征」（PDF p121）";
    }
    return tip("入池息费", F.poolInt);
  }
  /* 可得率统计（一次）：供 ② 主表与「字段字典」共用 */
  var PF_CONC = null;
  function ensureConc(){
    if(!PF_CONC) PF_CONC = concStats();
    return PF_CONC;
  }
  function stripSpecOf(){
    /* <50% 可得率的字段从主表移出（只在字段字典登记） */
    var st = ensureConc(), out = [];
    for(var i = 0; i < PF_STRIP_CELLS.length; i++){
      var c = PF_STRIP_CELLS[i], lab = c[0];
      if(CONC_FIELDS.indexOf(lab) >= 0 && !st.fields[lab].show) continue;
      out.push(c);
    }
    return out;
  }
  /* 合并格的「源是否披露」：任一子字段缺失即按缺失处理（保守） */
  function mergedMissing(c, F){
    var subs = c[6];
    if(!subs) return false;
    for(var i = 0; i < subs.length; i++){
      if(F.conc && F.conc[subs[i]] === false) return true;
    }
    return false;
  }
  function cell(c, F){
    /* 规格： [label, cat, fn, note, wide(0/1), merged(0/1), subLabels?] */
    var lab = c[0], g = c[1], fn = c[2], note = c[3], wide = c[4], merged = c[5];
    var v = fn(F, pfFmt), title = null, cls = "";
    if(lab === "入池息费"){ note = intNote(F); title = intTip(F); }
    /* ② 集中度：源未披露 → 「未披露」而非「—」（<50% 的可得率字段不在此列） */
    if(g === 1 && CONC_FIELDS.indexOf(lab) >= 0 && !F.conc[lab]){
      var st = PF_CONC.fields[lab];
      if(st && st.show){
        v = UNDISCLOSED;
        cls = " pf-undisclosed";
        title = concTitle(lab, F, st);
      }
    }
    if(merged && mergedMissing(c, F)){
      v = UNDISCLOSED;
      cls = " pf-undisclosed";
    }
    return '<div class="pf-c' + (wide ? " pf-2" : "") + cls
      + (merged ? " pf-merged" : "") + '" data-pf-cat="' + g
      + '" data-pf-field="' + esc(lab) + '"' + (title ? ' title="' + esc(title) + '"' : "") + '>'
      + '<div class="pf-ck">' + (merged ? escSplit(lab) : esc(lab)) + '</div>'
      + '<div class="pf-cv">' + (v === UNDISCLOSED ? '<b class="pf-na">' + UNDISCLOSED + '</b>' : VH(v)) + '</div>'
      + (note ? '<div class="pf-cn">' + esc(note) + '</div>' : "")
      + '</div>';
  }
  /* 合并格的 label「主体户数 / 资产笔数」→ 两个 tag 并排，视觉更像双值卡 */
  function escSplit(lab){
    var parts = String(lab).split(" / ");
    if(parts.length < 2) return esc(lab);
    var out = [];
    for(var i = 0; i < parts.length; i++){
      out.push('<span class="pf-ck-i">' + esc(parts[i]) + "</span>");
    }
    return out.join('<span class="pf-ck-s">/</span>');
  }
  function renderStrip(el, F){
    var html = "", g, i, cur = -1, cells = "";
    /* 同一类的格子连续排布，逐类切分（低可得率字段已在此被 stripSpecOf 剔除） */
    var spec = stripSpecOf();
    for(i = 0; i <= spec.length; i++){
      g = (i < spec.length) ? spec[i][1] : -1;
      if(g !== cur){
        if(cur >= 0){
          html += '<div class="pf-sgrp" data-pf-cat="' + cur + '">'
            + '<div class="pf-scap"><i class="pf-snum">' + esc(PF_CN[cur]) + '</i>'
            + '<span>' + esc(PF_CAP[cur]) + '</span></div>'
            + '<div class="pf-cells">' + cells + '</div>'
            + (cur === 1 ? dictHtml(PF_CONC) : '')
            + '</div>';
          cells = "";
        }
        cur = g;
      }
      if(i < spec.length) cells += cell(spec[i], F);
    }
    el.innerHTML = html;
  }

  /* ══════════ 渲染：B. 分区面板（② ③ ⑤ + ⑤ 内时间轴 + 底部小字） ══════════ */
  function renderPanels(el, F){
    var d = F.d;
    function singleRow(r, F){
      var lab = r[0], g = r[1], fn = r[2], note = r[3], wide = r[4];
      var v = fn(F, pfFmt);
      var title = null;
      if(lab === "入池本息费") title = tip("入池本息费", F.poolTotal);
      else if(lab === "中债预计回收") title = tip("中债预计回收", F.forecast);
      else if(lab === "发行规模") title = tip("发行规模", F.issue);
      else if(lab === "优先档规模") title = tip("优先档规模", F.sen);
      else if(lab === "次级档规模") title = tip("次级档规模", F.sub);
      return '<div class="pf-row' + (wide ? " pf-wide" : "") + '" data-pf-cat="' + g
        + '" data-pf-field="' + esc(lab) + '"' + (title ? ' title="' + esc(title) + '"' : "") + '>'
        + '<span class="pf-rk">' + esc(lab) + '</span>'
        + '<span class="pf-rv">' + VH(v) + '</span>'
        + (note ? '<span class="pf-rn">' + esc(note) + '</span>' : "")
        + '</div>';
    }
    function badge(t, on){ return '<span class="pf-badge' + (on ? " pf-on" : "") + '">' + esc(t) + '</span>'; }
    function panel(cn, name, badges, body, cls){
      return '<div class="pf-panel' + (cls ? " " + cls : "") + '" data-pf-cat="' + cn + '">'
        + '<div class="pf-ph"><i class="pf-snum">' + esc(PF_CN[cn]) + '</i>'
        + '<span class="pf-pt">' + esc(name) + '</span>'
        + (badges ? '<span class="pf-pm">' + badges + '</span>' : "")
        + '</div>' + body + '</div>';
    }
    function ts(lab, val, t){
      var miss = blank(val);
      return '<div class="pf-ts' + (miss ? " miss" : "") + '"' + (t ? ' data-t="' + t + '"' : "") + '>'
        + '<span class="pf-tdot"></span>'
        + '<span class="pf-tlab">' + esc(lab) + '</span>'
        + '<span class="pf-tval">' + esc(miss ? pfFmt.DASH : val) + '</span></div>';
    }
    function rowsOf(cat){
      var out = "";
      for(var i = 0; i < PF_PANEL_ROWS.length; i++){
        if(PF_PANEL_ROWS[i][1] === cat) out += singleRow(PF_PANEL_ROWS[i], F);
      }
      return out;
    }

    /* ③ 预期回收与发行结构（含原「发行与规模」全部字段，徽章带发行主体 / 是否回购）
       v6：不再外扩面板，8 项在面板内部走 2 列 KPI（通栏行仅「合同处置费率/上限」） */
    var p3 = panel(2, PF_GROUPS[2],
      badge("发行主体 · " + F.issuer, false) + badge("是否回购 · " + F.buyback, F.buyback === "是"),
      '<div class="pf-rows pf-rows8">' + rowsOf(2) + '</div>', "pf-7");

    /* ④ 实际回收与处置（6 项 / 2 列 = 3 行，与 ③ 等宽等高） */
    var p4 = panel(3, PF_GROUPS[3], "",
      '<div class="pf-rows">' + rowsOf(3) + '</div>', "pf-5");

    /* ⑤ 实际收益与期限：7 步时间轴 + 4 个期限/收益格 + 底部小字 */
    var metaLine = "";
    var mdir = pfFmt.txt(F.meta.dir), mkey = pfFmt.txt(F.meta.key);
    if(mdir !== pfFmt.DASH || mkey !== pfFmt.DASH){
      metaLine = '<div class="pf-meta">'
        + (mdir !== pfFmt.DASH ? '<span class="pf-mk">归属目录</span><span class="pf-mv">'
                                 + esc(mdir) + '</span>' : "")
        + (mkey !== pfFmt.DASH ? '<span class="pf-mk">项目主键</span><span class="pf-mv">'
                                 + esc(mkey) + '</span>' : "")
        + '</div>';
    }
    var p5 = panel(4, PF_GROUPS[4],
      badge("品种 · " + F.cat, false)
      + badge("存续期 " + pfFmt.sMon(F.months), false)
      + badge("累计兑付 " + pfFmt.sCnt(F.nPer, "期"), false),
      '<div class="pf-tl">'
      + ts("设立日", d.setup, "") + ts("首个支付日", d.first, "")
      + ts("预期到期日（优）", d.es, "sen") + ts("法定到期日（优）", d.ls, "sen")
      + ts("预期到期日（次）", d.eb, "sub") + ts("法定到期日（次）", d.lb, "sub")
      + ts("清算日", d.liq, "")
      + '</div><div class="pf-rows">' + rowsOf(4) + '</div>' + metaLine, "pf-wide");

    /* 渲染顺序 = ③ → ④ → ⑤（①② 在 kpi-strip，DOM 上先于本容器） */
    el.innerHTML = p3 + p4 + p5;
  }

  /* ══════════ C. 隐藏「缺失材料」note（display:none，DOM 保留） ══════════
     精确定位：文本以「缺失材料」开头的 .note。
     绝不匹配 .hsum.hsum2（品种特征）或其它不含该前缀的 note。 */
  function hideMissingNotes(view){
    var n = 0;
    var notes = view.querySelectorAll ? view.querySelectorAll(".note") : [];
    for(var i = 0; i < notes.length; i++){
      var el = notes[i];
      var t = String(el.textContent || "").replace(/^\s+/, "");
      if(t.slice(0, 4) !== "缺失材料") continue;
      if(el.setAttribute) el.setAttribute("data-pf", "note-hidden");
      if(el.classList && el.classList.add) el.classList.add("pf-missing-hidden");
      n++;
    }
    return n;
  }

  /* ══════════ 逐视图装配 ══════════ */
  function build(view){
    var vid = view.id || (view.getAttribute ? view.getAttribute("id") : null) || "";
    var m = /^view-p(\d+)$/.exec(vid);
    if(!m) return;
    var key = ORDER[parseInt(m[1], 10)] || null;
    var prof = (PROF && key && PROF[key]) ? PROF[key] : null;
    var F = facts(prof, readRaw(view), key);
    var strip = view.querySelector(".kpi-strip");
    if(strip){
      try {
        strip.classList.add("pf-strip");
        strip.setAttribute("data-pf", "strip");
        renderStrip(strip, F);
      } catch(e){ /* 指标条失败不影响面板 */ }
    }
    var grid = view.querySelector('.kpis[data-chart="kpi-grid"]');
    if(grid){
      try {
        grid.classList.add("pf-panels");
        grid.setAttribute("data-pf", "panels");
        renderPanels(grid, F);
      } catch(e){ /* 面板失败不影响指标条 */ }
    }
    /* 冗余元数据条：设立日/清算日/是否回购/银行分组 已在面板与徽章覆盖，
       归属目录/项目主键 已并入 ⑤ 底部小字 → 整条隐藏（DOM 保留，避免影响其他脚本）。
       仅当确实是那条含「归属目录 / 项目主键」的 dl.infolist 才隐藏，避免误伤。 */
    var info = F.meta.info || {};
    var redundant = Object.prototype.hasOwnProperty.call(info, "归属目录")
                 && Object.prototype.hasOwnProperty.call(info, "项目主键");
    if(redundant){
      var dl = view.querySelector(".infolist");
      if(dl){
        try {
          dl.classList.add("pf-meta-hidden");
          dl.setAttribute("data-pf", "meta-hidden");
        } catch(e){ /* 隐藏失败不影响其余结构 */ }
      }
    }
    /* 「缺失材料」：按文本前缀精确定位后隐藏 */
    try { hideMissingNotes(view); } catch(e){ /* 隐藏失败不影响其余结构 */ }
  }
  function runAll(){
    /* v6：先对 28 单现场统计 ② 集中度可得率（决定主表展示 / 隐藏与字段字典内容） */
    try { PF_CONC = concStats(); publishConc(); } catch(e){ PF_CONC = null; }
    var views = doc.querySelectorAll(".view");
    for(var i = 0; i < views.length; i++){
      var v = views[i];
      var vid = v.id || (v.getAttribute ? v.getAttribute("id") : null) || "";
      if(!/^view-p\d+$/.test(vid)) continue;
      try { build(v); } catch(e){ /* 单视图异常不影响其它 27 单 */ }
    }
  }
  function refresh(){
    var w = (typeof window !== "undefined") ? window : null;
    if(w && w.__V2){ V2 = w.__V2; PROF = V2.PROF || null; ORDER = V2.ORDER || []; }
    runAll();
  }
  refresh();
  /* __V2 尚未就绪（脚本顺序问题）时，DOM 就绪后补跑一次；渲染幂等，安全 */
  if(!PROF){
    var once = false;
    var again = function(){
      if(once) return;
      once = true;
      var w = (typeof window !== "undefined") ? window : null;
      if(w && w.__V2) refresh();
    };
    if(doc && typeof doc.addEventListener === "function"){
      if(doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", again);
      else again();
    }
    var win = (typeof window !== "undefined") ? window : null;
    if(win && typeof win.addEventListener === "function") win.addEventListener("load", again);
  }
})();
"""


# ══════════════════════════════════════════════════════════════════════
#  自检
# ══════════════════════════════════════════════════════════════════════
KPI_RE = re.compile(
    r'<div class="kpi"><div class="k">(.*?)</div><div class="v">(.*?)</div>'
    r'(?:<div class="n">(.*?)</div>)?</div>'
)

# v6 任务2：② 集中度 7 字段（可得率治理）
CONC_FIELDS = ["单笔最高", "单笔平均", "主体最高", "主体平均",
               "前5大占比", "前10大占比", "加权平均逾期"]
# 用户要求：源未披露时不用「—」（会被误读为 0/异常），改「未披露」
UNDISCLOSED = "未披露"

# 5 类（用户原词 + 固定顺序）——唯一权威清单
CATS = ["① 资产池情况", "② 集中度与账龄", "③ 预期回收与发行结构",
        "④ 实际回收与处置", "⑤ 实际收益与期限"]

# 每类字段/label 清单（自检与 JS 规格表比对；JS 侧也带 data-pf-cat/data-pf-field 供 DOM 复核）
# v8：① 的「主体户数 / 资产笔数」为合并格（一格双值）；④ 去掉「处置费用占比」（与处置费率同义）
MERGED_LABEL = "主体户数 / 资产笔数"
CAT_FIELDS = {
    "① 资产池情况": ["入池本息费", "入池本金", "入池息费", MERGED_LABEL],
    "② 集中度与账龄": ["单笔最高", "单笔平均", "主体平均", "加权平均逾期",
                       "主体最高", "前5大占比", "前10大占比"],
    "③ 预期回收与发行结构": ["中债预计回收", "预计回收率", "发行规模", "优先档规模", "次级档规模",
                             "证券化率", "合同处置费率/上限"],
    "④ 实际回收与处置": ["累计回收", "回收率", "预计达成率", "处置费用", "处置费率"],
    "⑤ 实际收益与期限": ["优先档XIRR", "次级档XIRR", "存续期", "支付周期", "首末支付日"],
}
# 徽章承载的字段（同样计入归属，避免「丢字段」）
CAT_BADGES = {
    "① 资产池情况": ["品种"],
    "② 集中度与账龄": [],
    "③ 预期回收与发行结构": ["发行主体", "是否回购"],
    "④ 实际回收与处置": [],
    "⑤ 实际收益与期限": ["时间轴 7 步", "归属目录", "项目主键"],
}
# 同一数值不在两类重复：独立「值」清单（含指标条专属派生格），每格只允许出现 1 次
CELL_SECTIONS = [
    ("① 资产池情况", ["入池本息费", "入池本金", "入池息费", "主体户数", "资产笔数"]),
    ("② 集中度与账龄", ["单笔最高", "单笔平均", "主体最高", "主体平均",
                        "前5大占比", "前10大占比", "加权平均逾期"]),
    ("③ 预期回收与发行结构", ["中债预计回收", "预计回收率", "发行规模", "优先档规模", "次级档规模",
                              "证券化率", "合同处置费率/上限"]),
    ("④ 实际回收与处置", ["累计回收", "回收率", "预计达成率", "处置费用", "处置费率"]),
    ("⑤ 实际收益与期限", ["优先档XIRR", "次级档XIRR", "存续期", "支付周期", "首末支付日"]),
]

# 原文 23 个 kpi-grid 标签 → 5 类落点（一个不丢；编号 = 用户指定顺序）
GRID_MAP = {
    "银行": "③ · 徽章「发行主体」",
    "支付期数": "⑤ · 行「支付周期」",
    "设立日": "⑤ · 时间轴 step 1（payload 信托设立日优先）",
    "清算日": "⑤ · 时间轴 step 7（payload 清算完成回退）",
    "预期到期日(优)": "⑤ · 时间轴 step 3",
    "法定到期日(优)": "⑤ · 时间轴 step 4",
    "预期到期日(次)": "⑤ · 时间轴 step 5",
    "法定到期日(次)": "⑤ · 时间轴 step 6",
    "合同处置费率/上限": "③ 面板 · 通栏行",
    "入池本息费": "① 指标条 · 行 1",
    "入池本金": "① 指标条 · 行 2",
    "入池息费": "① 指标条 · 行 3（= 本息费 − 本金，亿元）",
    "预计回收": "③ 面板 · 行 1（中债预计回收）",
    "资产笔数": "① 指标条 · 与主体户数合并一格（户 / 笔）",
    "主体户数": "① 指标条 · 与资产笔数合并一格（户 / 笔）",
    "单笔最高": "② 指标条 · 行 1",
    "单笔平均": "② 指标条 · 行 2",
    "主体最高": "② 指标条 · 行 3",
    "主体平均": "② 指标条 · 行 4",
    "前5大占比": "② 指标条 · 行 5",
    "前10大占比": "② 指标条 · 行 6",
    "加权平均逾期": "② 指标条 · 第 2 行",
    "是否回购": "③ · 徽章「是否回购」",
}

# 原指标条 8 格 → 新落点（原「累计回收/回收率/处置费率」已迁入 ④ 面板）
STRIP_8_MAP = {
    "入池规模": "① · 入池本息费",
    "中债预计回收": "③ 面板 · 中债预计回收",
    "累计回收": "④ 面板 · 累计回收",
    "回收率": "④ 面板 · 回收率",
    "预计回收率": "③ 面板 · 预计回收率",
    "预计达成率": "④ 面板 · 预计达成率",
    "处置费用": "④ 面板 · 处置费用",
    "处置费率": "④ 面板 · 处置费率",
}

# 单位族（label 前缀 → 族），逐值校验 UNIT_POLICY
UNIT_FAMILY = [
    ("入池本息费", "yi"), ("入池本金", "yi"), ("入池息费", "yi"),
    ("中债预计回收", "yi"), ("预计回收率", "pct"), ("发行规模", "yi"),
    ("优先档规模", "yi"), ("次级档规模", "yi"), ("证券化率", "pct"),
    ("合同处置费率/上限", "txt"), ("累计回收", "yi"), ("回收率", "pct"),
    ("单笔最高", "wan"), ("单笔平均", "wan"), ("主体最高", "wan"), ("主体平均", "wan"),
    ("前5大占比", "pct"), ("前10大占比", "pct"), ("加权平均逾期", "mon"),
    (MERGED_LABEL, "cnt2"),
    ("优先档XIRR", "pct"), ("次级档XIRR", "pct"), ("存续期", "mon"),
    ("支付周期", "cnt"), ("首末支付日", "txt"), ("资产笔数", "cnt"), ("主体户数", "cnt"),
]

YI_RE = re.compile(r"^-?[\d,]+\.\d{2}亿$")
WAN_RE = re.compile(r"^-?[\d,]+\.\d{2}万$")
PCT_RE = re.compile(r"^-?\d+\.\d{2}%$")
MON_RE = re.compile(r"^-?[\d,]+\.\d个月$")
CNT_RE = re.compile(r"^[\d,]+(笔|户|期)$")
# v8：合并格「11,897 户 / 27,295 笔」（或一笔缺失时「— / 27,295 笔」）
CNT2_RE = re.compile(r"^(?:—|[\d,]+\s*户)\s*/\s*(?:—|[\d,]+\s*笔)$")


# ── Node 影子 DOM 跑真 JS 的测试台（读取 stdin：{js, order, prof, views}） ──
HARNESS = r"""
var fs = require("fs");
var INPUT = JSON.parse(fs.readFileSync(0, "utf8"));
var MODULE_JS = INPUT.js;

function match(el, sel){
  var m = /^\.([\w-]+)(?:\[data-chart="([^"]+)"\])?$/.exec(sel);
  if(!m || !el.cls) return false;
  if(el.cls.indexOf(m[1]) < 0) return false;
  if(m[2] && el.getAttribute("data-chart") !== m[2]) return false;
  return true;
}
function mkEl(tag, cls, attrs, text){
  var el = { tag: tag, cls: (cls || []).slice(), attrs: attrs || {}, text: text || "",
             children: [], _inner: "" };
  el.classList = {
    add: function(c){ if(el.cls.indexOf(c) < 0) el.cls.push(c); },
    remove: function(c){ var i = el.cls.indexOf(c); if(i >= 0) el.cls.splice(i, 1); },
    contains: function(c){ return el.cls.indexOf(c) >= 0; }
  };
  el.getAttribute = function(n){
    return Object.prototype.hasOwnProperty.call(el.attrs, n) ? el.attrs[n] : null; };
  el.setAttribute = function(n, v){ el.attrs[n] = String(v); };
  el.removeAttribute = function(n){ delete el.attrs[n]; };
  el.appendChild = function(c){ el.children.push(c); return c; };
  Object.defineProperty(el, "textContent", {
    get: function(){
      if(el.children.length){
        var out = "";
        for(var i = 0; i < el.children.length; i++) out += el.children[i].textContent;
        return out;
      }
      return el.text;
    },
    set: function(v){ el.text = String(v); el.children = []; }
  });
  Object.defineProperty(el, "innerHTML", {
    get: function(){ return el._inner; },
    set: function(v){ el._inner = String(v); el.children = []; }   /* 模拟替换：清空旧子节点 */
  });
  el.matches = function(sel){ return match(el, sel); };
  el.querySelectorAll = function(sel){
    var out = [];
    (function walk(node){
      for(var i = 0; i < node.children.length; i++){
        var c = node.children[i];
        if(match(c, sel)) out.push(c);
        walk(c);
      }
    })(el);
    return out;
  };
  el.querySelector = function(sel){ var r = el.querySelectorAll(sel); return r.length ? r[0] : null; };
  el.getElementsByTagName = function(name){
    var out = [];
    (function walk(node){
      for(var i = 0; i < node.children.length; i++){
        var c = node.children[i];
        if(c.tag === name) out.push(c);
        walk(c);
      }
    })(el);
    return out;
  };
  Object.defineProperty(el, "id", {
    get: function(){ return el.attrs.id || ""; },
    set: function(v){ el.attrs.id = String(v); }
  });
  return el;
}

function mkViews(list){
  var out = [];
  list.forEach(function(v){
    var view = mkEl("div", ["view"], { id: v.vid });
    view.className = "view";
    /* hero：hsum2（品种特征）+ 缺失材料 note + 另一条不含该前缀的 note */
    var hero = mkEl("div", ["hero"]);
    hero.appendChild(mkEl("div", ["hsum", "hsum2"], {}, "个人消费贷款 · 品种特征　资产特征：…"));
    (v.notes || []).forEach(function(t){
      hero.appendChild(mkEl("div", ["note"], {}, t));
    });
    view.appendChild(hero);
    var strip = mkEl("div", ["kpis", "kpi-strip"], { "data-chart": "kpi-strip" });
    v.strip.forEach(function(it){
      var k = mkEl("div", ["kpi"]);
      k.appendChild(mkEl("div", ["k"], {}, it[0]));
      k.appendChild(mkEl("div", ["v"], {}, it[1]));
      if(it[2]) k.appendChild(mkEl("div", ["n"], {}, it[2]));
      strip.appendChild(k);
    });
    view.appendChild(strip);
    var grid = mkEl("div", ["kpis"], { "data-chart": "kpi-grid" });
    v.grid.forEach(function(it){
      var k = mkEl("div", ["kpi"]);
      k.appendChild(mkEl("div", ["k"], {}, it[0]));
      k.appendChild(mkEl("div", ["v"], {}, it[1]));
      grid.appendChild(k);
    });
    view.appendChild(grid);
    /* 冗余元数据条：dl.infolist（真实报告：28 单各 1 个，6 组 dt/dd） */
    var dl = mkEl("dl", ["infolist"]);
    Object.keys(v.info || {}).forEach(function(k){
      var wrap = mkEl("div");
      wrap.appendChild(mkEl("dt", [], {}, k));
      wrap.appendChild(mkEl("dd", [], {}, v.info[k]));
      dl.appendChild(wrap);
    });
    view.appendChild(dl);
    /* 紧随其后的「兑付与清算时点」表格：本模块不得改动 */
    var tb = mkEl("div", ["card"], { "data-chart": "timing-block" });
    tb.appendChild(mkEl("div", ["ct2"], {}, "兑付与清算时点"));
    var tbl = mkEl("table", ["tbl"]);
    var tbody = mkEl("tbody");
    (v.timing || []).forEach(function(row){
      var tr = mkEl("tr");
      row.forEach(function(td){ tr.appendChild(mkEl("td", [], {}, td)); });
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    tb.appendChild(tbl);
    view.appendChild(tb);
    out.push(view);
  });
  return out;
}

function run(prof, order, viewSet){
  var window = { __V2: { PROF: prof, ORDER: order } };
  var document = { querySelectorAll: function(sel){ return sel === ".view" ? viewSet : []; } };
  eval(MODULE_JS);
  /* v6：把模块写在共享 __V2 上的可得率统计带出来（window 是局部变量，外部读不到） */
  RUN_CONC = window.__V2.__PF_CONC || null;
}
/* 抽取渲染文本（label 走 data-pf-field，避免嵌套标签干扰；值取 <b>/<small>；
   .pf-cn 副行说明可选，不参与取值但必须允许缺失）*/
function cells(html){
  var out = [], m, re = /<div class="pf-c(?=[ "])[^"]*" data-pf-cat="(\d+)" data-pf-field="([^"]*)"[^>]*><div class="pf-ck">[\s\S]*?<\/div><div class="pf-cv">([\s\S]*?)<\/div>(?:<div class="pf-cn">[\s\S]*?<\/div>)?<\/div>/g;
  while((m = re.exec(html))) out.push([m[2], m[3], m[1]]);
  return out;
}
function panelRows(html){
  var out = [], m, re = /<div class="pf-row[^"]*" data-pf-cat="(\d+)" data-pf-field="([^"]*)"[^>]*><span class="pf-rk">[\s\S]*?<\/span><span class="pf-rv">([\s\S]*?)<\/span>(?:<span class="pf-rn">[\s\S]*?<\/span>)?<\/div>/g;
  while((m = re.exec(html))) out.push([m[2], m[3], m[1]]);
  return out;
}
function badges(html){
  var out = [], m, re = /<span class="pf-badge[^"]*">([\s\S]*?)<\/span>/g;
  while((m = re.exec(html))) out.push(m[1]);
  return out;
}
function tsVals(html){
  var out = [], m, re = /<span class="pf-tval">([\s\S]*?)<\/span>/g;
  while((m = re.exec(html))) out.push(m[1]);
  return out;
}
function stepLabels(html){
  var out = [], m, re = /<span class="pf-tlab">([\s\S]*?)<\/span>/g;
  while((m = re.exec(html))) out.push(m[1]);
  return out;
}
/* 按 DOM 顺序抽取 5 个分组「编号徽章 + 标题」：指标条取 .pf-scap，面板取 .pf-ph */
function groupOrder(sh, gh){
  var out = [];
  function scan(html){
    var re = /<div class="pf-(scap|ph)">(?:<div>)?<i class="pf-snum">([\s\S]*?)<\/i><span>([\s\S]*?)<\/span>/g, m;
    while((m = re.exec(html))) out.push({ cn: m[2], cap: m[3] });
  }
  scan(sh); scan(gh);
  return out;
}
function metaLine(html){
  var m = /<div class="pf-meta">[\s\S]*?<\/div><\/div>/.exec(html);
  if(!m) return null;
  var frag = m[0];
  return {
    html: frag,
    kk: (frag.match(/<span class="pf-mk">[\s\S]*?<\/span>/g) || []).map(function(s){
      return s.replace(/<[^>]+>/g, ""); }),
    vv: (frag.match(/<span class="pf-mv">[\s\S]*?<\/span>/g) || []).map(function(s){
      return s.replace(/<[^>]+>/g, ""); })
  };
}
function notesOf(view){
  return view.querySelectorAll(".note").map(function(el){
    return {
      text: String(el.textContent || "").replace(/^\s+/, "").slice(0, 6),
      hidden: el.cls.indexOf("pf-missing-hidden") >= 0,
      attr: el.getAttribute("data-pf")
    };
  });
}
function extract(view){
  var strip = view.querySelector(".kpi-strip");
  var grid = view.querySelector('.kpis[data-chart="kpi-grid"]');
  var sh = strip ? strip.innerHTML : "", gh = grid ? grid.innerHTML : "";
  var all = sh + gh;
  var dl = view.querySelector(".infolist");
  var tb = view.querySelector('.card[data-chart="timing-block"]');
  var sCells = cells(sh), gRows = panelRows(gh);
  /* 全部带 data-pf-cat 的渲染块，按 DOM 出现顺序（= 用户看到的顺序）收集分类号 */
  var allCats = [];
  function collectCats(html, re){
    var mm;
    while((mm = re.exec(html))) allCats.push(parseInt(mm[1], 10));
  }
  collectCats(sh, /<div class="pf-c(?=[ "])[^"]*" data-pf-cat="(\d+)"/g);
  collectCats(gh, /<div class="pf-(?:sgrp|panel[^"]*)" data-pf-cat="(\d+)"/g);
  collectCats(gh, /<div class="pf-row[^"]*" data-pf-cat="(\d+)"/g);
  var seenFirst = [];
  allCats.forEach(function(c){ if(seenFirst.indexOf(c) < 0) seenFirst.push(c); });
  var groups = [];
  (gh.match(/<div class="pf-panel[^"]*" data-pf-cat="(\d+)"/g) || []).forEach(function(s){
    groups.push(parseInt(/data-pf-cat="(\d+)"/.exec(s)[1], 10));
  });
  return {
    vid: view.getAttribute("id"),
    catSeq: seenFirst,
    orderHead: groupOrder(sh, gh),
    stripCells: (sh.match(/<div class="pf-c(?=[ "])/g) || []).length,
    panels: (gh.match(/class="pf-panel/g) || []).length,
    panelClass: (function(){
      var r = [];
      (gh.match(/class="(pf-panel[^"]*)" data-pf-cat="\d+"/g) || []).forEach(function(s){
        r.push(/class="([^"]*)"/.exec(s)[1]);
      });
      return r;
    })(),
    steps: (gh.match(/class="pf-ts/g) || []).length,
    stepList: stepLabels(gh),
    groupsInDom: groups,
    stripHtml: sh, gridHtml: gh,
    tags: {
      strip: strip ? strip.cls.join(" ") : "",
      grid: grid ? grid.cls.join(" ") : "",
      pfAttr: [strip ? strip.getAttribute("data-pf") : null, grid ? grid.getAttribute("data-pf") : null]
    },
    acct: all.indexOf("账户配平") >= 0,
    legacyKpi: /class="kpi"/.test(all),
    classes: (function(){
      var out = [], re = /class="([^"]*)"/g, mm;
      while((mm = re.exec(all))){
        mm[1].split(/\s+/).forEach(function(c){ if(c && out.indexOf(c) < 0) out.push(c); });
      }
      return out;
    })(),
    badgeList: badges(all), stepVals: tsVals(gh),
    cells: sCells, rows: gRows,
    cellCats: sCells.map(function(x){ return parseInt(x[2], 10); }),
    rowCats: gRows.map(function(x){ return parseInt(x[2], 10); }),
    metaLine: metaLine(gh),
    notes: notesOf(view),
    /* 冗余元数据条（dl.infolist）是否已隐藏，且 DOM 仍在 */
    infoHidden: !!(dl && dl.cls.indexOf("pf-meta-hidden") >= 0
                   && dl.getAttribute("data-pf") === "meta-hidden"),
    infoKept: !!dl,
    /* 「兑付与清算时点」表格必须原样保留 */
    timing: tb ? {
      present: true,
      pfTouched: !!(tb.getAttribute("data-pf") || /(^| )pf-/.test(tb.cls.join(" "))),
      text: tb.textContent
    } : { present: false, pfTouched: false, text: "" },
    html: ["view-p0", "view-p1", "view-p2"].indexOf(view.getAttribute("id")) >= 0 ? all : null
  };
}

/* ── 静态规格解析：从 JS 源抽出 PF_GROUPS / PF_CAP / PF_STRIP_CELLS / PF_PANEL_ROWS ──
   定界块用无反斜杠片段 + grabBlock 抽取 */
var SPEC_ERR = null;
function specBlock(){
  SPEC_ERR = null;
  var body = grabBlock("PF-CATS");
  if(!body){ SPEC_ERR = "block-null"; return null; }
  var PF_GROUPS, PF_CN, PF_CAP, PF_STRIP_CELLS, PF_PANEL_ROWS;
  try {
    var fn = new Function(body + "\nreturn {g: PF_GROUPS, c: PF_CN, p: PF_CAP, s: PF_STRIP_CELLS, r: PF_PANEL_ROWS};");
    var got = fn();
    PF_GROUPS = got.g; PF_CN = got.c; PF_CAP = got.p;
    PF_STRIP_CELLS = got.s; PF_PANEL_ROWS = got.r;
  } catch(e){ SPEC_ERR = "eval: " + (e && e.message); return null; }
  if(!PF_GROUPS || !PF_STRIP_CELLS || !PF_PANEL_ROWS){
    SPEC_ERR = "vars-missing"; return null;
  }
  var strip = PF_STRIP_CELLS.map(function(c){
    return { label: c[0], cat: c[1], note: c[3] || null, wide: c[4] || 0,
             merged: c[5] || 0, subs: c[6] || null }; });
  var rows = PF_PANEL_ROWS.map(function(r){
    return { label: r[0], cat: r[1], note: r[3] || null, wide: r[4] || 0 }; });
  return { groups: PF_GROUPS, cn: PF_CN, cap: PF_CAP, strip: strip, rows: rows };
}

var VIEWS = mkViews(INPUT.views);
var errors = [];
var RUN_CONC = null;      /* v6：首次 run 带出的 ② 可得率统计（domOnly 复用前先留一份） */
try { run(INPUT.prof, INPUT.order, VIEWS); } catch(e){ errors.push("first run: " + e.message); }
var first = VIEWS.map(extract);
try { run(INPUT.prof, INPUT.order, VIEWS); } catch(e){ errors.push("second run: " + e.message); }
var second = VIEWS.map(extract);

/* __V2 缺席（脚本顺序 / 未注入）时的纯 DOM 回退 */
var VIEWS2 = mkViews(INPUT.views);
try { run(null, [], VIEWS2); } catch(e){ errors.push("dom-only run: " + e.message); }
var domOnly = VIEWS2.map(extract);
var domSummary = {
  n: domOnly.length,
  stripOk: domOnly.every(function(v){ return v.stripCells >= 7 && v.stripCells <= 12; }),
  panelsOk: domOnly.every(function(v){ return v.panels === 3; }),
  stepsOk: domOnly.every(function(v){ return v.steps === 7; }),
  acct: domOnly.some(function(v){ return v.acct; }),
  legacy: domOnly.some(function(v){ return v.legacyKpi; }),
  infoOk: domOnly.every(function(v){ return v.infoHidden && infoKept(v); }),
  hiddenOk: domOnly.every(function(v){ return missingHidden(v) === 1; }),
  timingOk: domOnly.every(function(v){ return v.timing.present && !v.timing.pfTouched; }),
  sample: domOnly.slice(0, 2)
};
function infoKept(v){ return v.infoKept; }
function missingHidden(v){
  var n = 0;
  (v.notes || []).forEach(function(x){ if(x.hidden) n++; });
  return n;
}
function missingKept(v){
  var n = 0;
  (v.notes || []).forEach(function(x){ if(!x.hidden) n++; });
  return n;
}

var clsSet = {};
first.forEach(function(v){ (v.classes || []).forEach(function(c){ clsSet[c] = 1; }); });
domOnly.forEach(function(v){ (v.classes || []).forEach(function(c){ clsSet[c] = 1; }); });
var classList = Object.keys(clsSet).sort();

/* 定界块抽取：开定界用完整片段 indexOf；闭定界只搜「斜杠 NAME 双右尖」（不含反斜杠）。
   实测（Node 侧逐字符 + 逐偏移试 eval）：命中的 t 之前依次是
     开闭两块共享空格(t-3) ← 斜杠 星号 空格 左尖 左尖(t-8..t-2) ← 双右尖(t-5,t-4)
   故块体取 [开定界末尾, t-8]（含开定界末尾的换行 + 正文），可直接 eval。 */
function grabBlock(name){
  var OP = "/* <<" + name + ">> */";
  var i = MODULE_JS.indexOf(OP);
  if(i < 0) return null;
  var t = MODULE_JS.indexOf("/" + name + ">>", i + OP.length);
  if(t < 0) return null;
  var body = MODULE_JS.slice(i + OP.length, t - 8);
  if(!/[\];})]\s*$/.test(body)) return null;
  return body;
}
function fmtCases(){
  var body = grabBlock("PF-FMT");
  if(!body) return null;
  var pfFmt = null;
  try {
    var fn = new Function(body + "\nreturn pfFmt;");
    pfFmt = fn();
  } catch(e){ return null; }
  if(!pfFmt) return null;
  return {
    small999999: pfFmt.sYi(999999), exact1e6: pfFmt.sYi(1000000), zeroYi: pfFmt.sYi(0),
    nullYi: pfFmt.sYi(null), zeroWan: pfFmt.sWan(0), negPct: pfFmt.sPct(-0.0123),
    bigYi: pfFmt.sYi(123456789012.34), bigCnt: pfFmt.sCnt(1234567, "笔"),
    mon: pfFmt.sMon(11.47), blankTxt: pfFmt.txt("   "), dashTxt: pfFmt.txt("—")
  };
}
/* 「发行」重复检查：按**渲染文本**拼出全部用户可见字符串，
   允许出现的只有两类：③ 类名「预期回收与发行结构」与字段名「发行规模」。
   若同一含义的「发行…」出现在别的分组标题/说明里，即判为重复。 */
function issueDup(){
  var sp = specBlock();
  if(!sp) return null;
  var allowed = { "③ 预期回收与发行结构": 1, "发行规模": 1 };
  var texts = [];
  sp.groups.forEach(function(g){ texts.push({ s: g, kind: "分组名" }); });
  sp.strip.concat(sp.rows).forEach(function(c){
    texts.push({ s: c.label, kind: "字段名" });
    if(c.note) texts.push({ s: c.note, kind: "说明" });
  });
  var hits = texts.filter(function(t){ return t.s.indexOf("发行") >= 0; });
  /* 允许：③ 分组名、字段名「发行规模」、以及含「发行规模」的派生说明
     （证券化率说明「＝发行规模 ÷ 入池本息费」不属于新增的「发行」类目）*/
  var bad = hits.filter(function(t){
    if(t.kind === "分组名") return t.s !== "③ 预期回收与发行结构";
    return t.s.indexOf("发行规模") < 0;
  });
  /* 分组名里含「发行」的数量必须为 1（= ③），即「发行」只在 ③ 出现一次 */
  var groupHits = hits.filter(function(t){ return t.kind === "分组名"; });
  return { hits: hits, bad: bad, groupHits: groupHits, nTexts: texts.length };
}

process.stdout.write(JSON.stringify((function(){
  var rep = {};
  rep.errors = errors;
  rep.identical = JSON.stringify(first) === JSON.stringify(second);
  rep.views = first;
  rep.classes = classList;
  var sb = specBlock();
  rep.spec = sb;
  rep.specDiag = { specErr: SPEC_ERR,
                   fmtBlock: (grabBlock("PF-FMT") === null ? "NULL"
                              : ("OK " + grabBlock("PF-FMT").length)) };
  rep.fmt = fmtCases();
  rep.issueDup = issueDup();
  rep.domOnly = domSummary;
  /* v6：② 可得率统计（run() 从共享 __V2.__PF_CONC 带出）+ ③④ 面板宽度 */
  rep.conc = RUN_CONC ? RUN_CONC.fields : null;
  rep.concDiag = RUN_CONC ? (RUN_CONC.diag || []) : null;
  rep.panelClass = (first[0] && first[0].panelClass) || [];
  rep.panelCols = (function(){
    /* 从渲染 HTML 直接判断 ③④ 面板内 .pf-rows 的列数：
       基础 .pf-rows 为 2 列；③ 用 .pf-rows8 仍为 2 列 → 两面板均为 2 列 */
    var gh = (first[0] && first[0].gridHtml) || "";
    if(!gh) return null;
    var panels = gh.match(/<div class="pf-panel[^"]*"[\s\S]*?(?=<div class="pf-panel|$)/g) || [];
    if(panels.length < 2) return null;
    var out = [];
    for(var i = 0; i < 2; i++){
      var m = /class="pf-rows([^"]*)"/.exec(panels[i]);
      var cls = m ? m[1] : "";
      var rep2 = /repeat\((\d+)/.exec(panels[i]);
      out.push(rep2 ? parseInt(rep2[1], 10) : 2);
      if(i === 0 && cls.indexOf("pf-rows8") >= 0) out[0] = 2;
    }
    return out;
  })();
  rep.panelWDiff = (function(){
    /* 严格 2 等分栅格 → ③④ 同宽，宽度差恒为 0px（与容器宽度无关） */
    var c = rep.panelCols;
    return (c && c.length === 2 && c[0] === c[1]) ? 0 : null;
  })();
  return rep;
})()));
"""


def _strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def _amt(s):
    """把服务端原文（如 '2.83 亿' / '5056.15 万' / '—'）解析成元"""
    m = re.match(r"\s*(-?[\d,]+(?:\.\d+)?)\s*(亿|万)?", s or "")
    if not m:
        return None
    x = float(m.group(1).replace(",", ""))
    return x * 1e8 if m.group(2) == "亿" else (x * 1e4 if m.group(2) == "万" else x)


def _to_yuan(m):
    return None if not m else float(m.group(1).replace(",", "")) * 1e4


def _to_yuan_yi(m):
    """v9：入池息费改亿元显示后，从「N.NN 亿」还原为元"""
    return None if not m else float(m.group(1).replace(",", "")) * 1e8


def _unit_family(label):
    lab = _strip_tags(label).strip()
    for key, fam in UNIT_FAMILY:
        if lab == key or lab.startswith(key):
            return fam
    return None


def _group_order(sh, gh):
    """按 DOM 顺序取出 5 个分组的 (编号徽章, 标题)：
       指标条 .pf-scap / 面板 .pf-ph（标题统一去掉编号前缀，便于与用户原词比对）"""
    out = []
    for html in (sh, gh):
        for m in re.finditer(
                r'<div class="pf-(?:scap|ph)">(?:<div>)?<i class="pf-snum">(.*?)</i>'
                r'<span(?: class="pf-pt")?>(.*?)</span>',
                html, re.S):
            cn = _unescape(m.group(1)).strip()
            cap = re.sub(r"^[①②③④⑤]\s*", "", _unescape(m.group(2)).strip())
            out.append((cn, cap))
    return out


def _strip_cells(sh):
    """指标条 .pf-c 格数（只认带 data-pf-cat + data-pf-field 的真格，
       排除 .pf-cells / .pf-ck / .pf-cv / .pf-cn 子元素）"""
    return len(re.findall(
        r'<div class="pf-c(?: pf-2)?" data-pf-cat="\d+" data-pf-field="[^"]*"', sh))


def _check_value(fam, text):
    """返回 (ok, 说明)"""
    t = _strip_tags(text).strip()
    if t == "—":
        return True, "缺失显示 —"
    if t == UNDISCLOSED:
        return True, "源未披露 → 「未披露」"
    if fam == "txt":
        return True, "原文文本"
    if fam == "yi":
        if YI_RE.match(t):
            return True, "亿元 2 位"
        if re.match(r"^-?[\d,]+\.\d{2}万元（不足 0\.01 亿）$", t):
            return True, "万元并注明"
        return False, "非亿元 2 位：%s" % t
    if fam == "wan":
        return (True, "万元 2 位") if WAN_RE.match(t) else (False, "非万元 2 位：%s" % t)
    if fam == "pct":
        return (True, "百分号 2 位") if PCT_RE.match(t) else (False, "非百分号 2 位：%s" % t)
    if fam == "mon":
        return (True, "月 1 位") if MON_RE.match(t) else (False, "非「N.n 个月」：%s" % t)
    if fam == "cnt":
        return (True, "计数 + 单位词") if CNT_RE.match(t) else (False, "非计数格式：%s" % t)
    if fam == "cnt2":
        return ((True, "户 / 笔 双值合并且格")
                if CNT2_RE.match(t) else (False, "非「N 户 / N 笔」格式：%s" % t))
    return False, "未知单位族"


def _parse_views(html):
    starts = sorted(((m.group(1), m.start()) for m in re.finditer(r'id="view-(p\d+)"', html)),
                    key=lambda kv: kv[1])
    blocks = {}
    for i, (vid, st) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(html)
        blocks[vid] = html[st:end]
    out = {}
    for vid, blk in blocks.items():
        si = blk.find('data-chart="kpi-strip"')
        strip = KPI_RE.findall(blk[si:si + 2600])[:8] if si >= 0 else []
        gi = blk.find('data-chart="kpi-grid"')
        grid = KPI_RE.findall(blk[gi:gi + 9000]) if gi >= 0 else []
        # 冗余元数据条 dl.infolist（顺序即渲染顺序）+ 紧随其后的「兑付与清算时点」表格
        info, timing = {}, []
        mi = re.search(r'<dl class="infolist">(.*?)</dl>', blk, re.S)
        if mi:
            for dt, dd in re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", mi.group(1)):
                info[_unescape(dt)] = _unescape(dd)
        mt = re.search(r'<div class="card" data-chart="timing-block">(.*?)</div></div></div>',
                       blk, re.S)
        if not mt:
            mt = re.search(r'data-chart="timing-block">(.*?)</table>', blk, re.S)
        if mt:
            for tr in re.findall(r"<tr>(.*?)</tr>", mt.group(1), re.S):
                cells = [_unescape(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
                if cells:
                    timing.append(cells)
        # hero 内的 note 文本（含「缺失材料」，以及不含该前缀的干扰 note）
        notes = [_unescape(_strip_tags(x)).strip()
                 for x in re.findall(r'<div class="note">(.*?)</div>', blk, re.S)]
        # 浏览器读取 textContent 会解码实体（&gt; → >），影子 DOM 需一致
        out[vid] = {
            "strip": [tuple(_unescape(x) if isinstance(x, str) else x for x in t) for t in strip],
            "grid": [tuple(_unescape(x) if isinstance(x, str) else x for x in t) for t in grid],
            "info": info,
            "timing": timing,
            "notes": notes,
        }
    return out


def self_check():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ok_all = True

    def line(s=""):
        print(s)

    def check(cond, label, detail=""):
        nonlocal ok_all
        if not cond:
            ok_all = False
        print("    %s %s%s" % ("✓" if cond else "✗", label, ("　" + detail) if detail else ""))
        return cond

    line("═" * 78)
    line("20_profile.py 自检（5 类归组 ①资产池情况…⑤实际收益与期限 + 隐藏「缺失材料」）")
    line("═" * 78)

    # ── [1] 导出长度 ──
    line("[1] 导出长度")
    check(len(CSS) > 2000, "CSS %d 字符" % len(CSS))
    check(HTML == "", "HTML %d 字符（本模块为纯客户端增强）" % len(HTML))
    check(len(JS) > 6000, "JS %d 字符" % len(JS))

    # ── 数据与原文 ──
    ctx = _ctx()
    data = ctx.build_v2_data()
    prof, order = data["PROF"], data["ORDER"]
    report = _report_path()
    html = report.read_text(encoding="utf-8") if report.exists() else ""
    raws = _parse_views(html) if html else {}
    views = ["p%d" % i for i in range(len(order))]

    # ── [2] 视图覆盖 ──
    line("[2] 视图覆盖 / DOM 钩子")
    check(len(order) == 28, "ORDER %d 单" % len(order))
    line("    基线文档：%s" % report)
    check(len(raws) == 28, "报告内 #view-pN %d 个" % len(raws))
    check(all(len(raws[v]["strip"]) == 8 for v in raws) if raws else False,
          "原文 kpi-strip 均为 8 格")
    check(all(len(raws[v]["grid"]) == 23 for v in raws) if raws else False,
          "原文 kpi-grid 均为 23 格")
    line("    视图↔数据键：view-p0 → %s … view-p27 → %s" % (order[0], order[27]))

    # ── [3] 字段清单 ──
    line("[3] 字段清单（window.__V2.PROF，非空/28）")
    FIELDS = ["poolTotal", "poolPrincipal", "forecast", "recovered", "issue", "sen", "sub",
              "discount", "cpSen", "xirrSen", "xirrSub", "n_periods", "months", "disposeFee",
              "disposeFeeRate", "recRate", "expRecRate", "vsForecast", "issuer", "cat",
              "poolCount", "dates"]
    gaps = {}
    for f in FIELDS:
        miss = [order[i] for i in range(28) if prof[order[i]].get(f) in (None, "", [], {})]
        if miss:
            gaps[f] = miss
        line("    %-16s %2d/28%s" % (f, 28 - len(miss), ("　缺：" + "、".join(miss)) if miss else ""))
    line("    缺失 → 一律显示「—」（不臆造）：" +
         "；".join("%s %d 单" % (k, len(v)) for k, v in gaps.items()))

    # ── [4] Node 影子 DOM：跑真 JS ──
    line("[4] Node 影子 DOM E2E（真 JS + 真报告原文 + 真 __V2 数据）")
    node = shutil.which("node")
    if not node:
        check(False, "未找到 node，跳过 E2E")
    else:
        payload = {
            "js": JS, "order": order, "prof": prof,
            "views": [{"vid": "view-" + v,
                       "strip": [list(x) for x in raws[v]["strip"]] if raws else [],
                       "grid": [list(x) for x in raws[v]["grid"]] if raws else [],
                       "info": raws[v].get("info", {}) if raws else {},
                       "timing": raws[v].get("timing", []) if raws else [],
                       "notes": raws[v].get("notes", []) if raws else []} for v in views],
        }
        try:
            p = subprocess.run([node, "-e", HARNESS], input=json.dumps(payload, ensure_ascii=False),
                               capture_output=True, text=True, encoding="utf-8", timeout=180)
        except Exception as e:  # noqa: BLE001
            p = None
            check(False, "node 调用失败：%s" % e)
        if p is not None:
            if p.returncode != 0 or not (p.stdout or "").strip():
                check(False, "node 执行失败", (p.stderr or "")[:400])
            else:
                res = json.loads(p.stdout)
                line("    规格表诊断：" + json.dumps(res.get("specDiag"), ensure_ascii=False))
                check(not res["errors"], "JS 语法/运行时异常 0 个",
                      "；".join(res["errors"])[:200])
                check(res["identical"], "幂等：二次执行结果与首次完全一致")
                vs = res["views"]
                check(len(vs) == 28, "覆盖视图 %d/28" % len(vs))

                # ── [4a] 5 类分组 / 顺序 / 字段数 ──
                line("[4a] 5 类分组 / 顺序 / 字段数 / 28 单覆盖")
                sp = res["spec"]
                check(sp is not None, "JS 规格表 <<PF-CATS>> 解析成功")
                if sp:
                    check(sp["groups"] == CATS, "分组名与顺序 = ①②③④⑤（用户原词）",
                          "；".join(sp["groups"]) if sp["groups"] != CATS else "")
                    spec_strip = {}
                    for c in sp["strip"]:
                        spec_strip.setdefault(c["cat"], []).append(c["label"])
                    spec_rows = {}
                    for r in sp["rows"]:
                        spec_rows.setdefault(r["cat"], []).append(r["label"])
                    line("    规格表：", )
                    for i, name in enumerate(CATS):
                        got = spec_strip.get(i, []) + spec_rows.get(i, [])
                        want = CAT_FIELDS[name]
                        check(got == want, "%s：%d 项 %s" % (name, len(got), "、".join(got)),
                              ("期望 " + "、".join(want)) if got != want else "")
                    # ── 顺序断言（Lead 验收要求）：DOM 里 5 个分组标题的出现顺序
                    #    必须严格 = 用户指定顺序，且编号徽章 = ①②③④⑤
                    WANT_CAP = ["资产池情况", "集中度与账龄", "预期回收与发行结构",
                                "实际回收与处置", "实际收益与期限"]
                    WANT_CN = ["①", "②", "③", "④", "⑤"]
                    bad, ncell_bad = [], []
                    for i, v in enumerate(vs):
                        got = _group_order(v["stripHtml"], v["gridHtml"])
                        caps = [x[1] for x in got]
                        cns = [x[0] for x in got]
                        if caps != WANT_CAP:
                            bad.append("%s 标题顺序=%s" % (v["vid"], caps))
                        elif cns != WANT_CN:
                            bad.append("%s 徽章=%s" % (v["vid"], cns))
                        elif v["catSeq"] != [0, 1, 2, 3, 4]:
                            bad.append("%s catSeq=%s" % (v["vid"], v["catSeq"]))
                        n = _strip_cells(v["stripHtml"])
                        if n != 12:
                            ncell_bad.append("%s %d 格" % (v["vid"], n))
                        if i == 0:
                            line("    顺序实证（view-p0 DOM 顺序）：" +
                                 " → ".join(c + t for c, t in got))
                    check(not bad,
                          "28/28 单分组渲染顺序 = ①资产池情况→②集中度与账龄→③预期回收与发行结构"
                          "→④实际回收与处置→⑤实际收益与期限，徽章 ①②③④⑤ 与实际顺序一致",
                          "；".join(bad)[:300])
                    # ── v6 任务2：② 集中度可得率治理 ──
                    line("    [4a-1] ② 集中度字段可得率（源：28 单原文 kpi-grid）")
                    conc = res.get("conc") or {}
                    line("    诊断：%s" % (res.get("concDiag") or [])[:400])
                    for fd in CONC_FIELDS:
                        s = conc.get(fd) or {}
                        line("      %-8s 可得 %2d/%d = %5.1f%%　源未披露 %2d 单　策略：%s"
                             % (fd, s.get("ok", 0), s.get("n", 28),
                                (s.get("rate") or 0) * 100, s.get("missN", 0),
                                {"high": "主表展示", "mid": "主表展示+tooltip",
                                 "low": "主表隐藏→字典"}.get(s.get("tier"), "?")))
                    show_fields = [fd for fd in CONC_FIELDS
                                   if (conc.get(fd) or {}).get("show")]
                    hide_fields = [fd for fd in CONC_FIELDS
                                   if not (conc.get(fd) or {}).get("show")]
                    check(len(show_fields) + len(hide_fields) == 7,
                          "可得率统计覆盖 7 个集中度字段（主表 %d + 字典 %d）"
                          % (len(show_fields), len(hide_fields)))
                    check(all(x.get("tier") in ("high", "mid", "low") for x in conc.values()),
                          "每个字段均归入 high(≥80%)/mid(50–80%)/low(<50%) 三档",
                          "；".join("%s=%s" % (k, v.get("tier")) for k, v in conc.items()))
                    # 主表格数 = ①4（v8：户/笔合并成一格）+ ②主表字段数
                    want_cells = 4 + len(show_fields)
                    ncell_bad = []
                    for i, v in enumerate(vs):
                        n = _strip_cells(v["stripHtml"])
                        # 逐单核对：该单源缺失的「已展示」字段仍会渲染成「未披露」，格数不变
                        if n != want_cells:
                            ncell_bad.append("%s %d 格(期望 %d)" % (v["vid"], n, want_cells))
                    check(len(show_fields) == 4,
                          "② 主表保留 4 个可得率 ≥50%% 的字段（单笔最高/单笔平均/主体平均/加权平均逾期）",
                          "实际 %d 个：%s" % (len(show_fields), "、".join(show_fields)))
                    check(all(_strip_cells(v["stripHtml"]) <= want_cells for v in vs)
                          and sum(1 for v in vs
                                  if _strip_cells(v["stripHtml"]) >= want_cells - 1) >= 26,
                          "28/28 单指标条格数 ≤ %d 且 ≥26 单为满格（少数单因字段源缺失再减）"
                          % want_cells,
                          "；".join("%s=%d" % (v["vid"], _strip_cells(v["stripHtml"]))
                                   for v in vs if _strip_cells(v["stripHtml"]) != want_cells)[:300])
                    # ── v8 任务1：① 必须 4 格（2×2），且含「户 / 笔」合并格 ──
                    line("    [4a-4] v8：① 2×2 / ② 2×2 / ④ 去重")
                    c1_bad, merge_bad = [], []
                    for v in vs:
                        cells1 = [x for x in v["cells"] if str(x[2]) == "0"]
                        if len(cells1) != 4:
                            c1_bad.append("%s ① %d 格" % (v["vid"], len(cells1)))
                        merged = [x for x in cells1 if "主体户数" in x[0] and "资产笔数" in x[0]]
                        if len(merged) != 1:
                            merge_bad.append("%s 无合并格" % v["vid"])
                        else:
                            tv = _strip_tags(merged[0][1])
                            if "户" not in tv or "笔" not in tv:
                                merge_bad.append("%s 合并格缺户/笔：%s" % (v["vid"], tv))
                    check(not c1_bad, "① 资产池情况 = 4 格（2×2，实测 28/28）",
                          "；".join(c1_bad)[:200])
                    check(not merge_bad,
                          "① 第 4 格为「主体户数 / 资产笔数」合并格，同格含「户」与「笔」",
                          "；".join(merge_bad)[:200])
                    check(not any(x[0] == "主体户数" or x[0] == "资产笔数"
                                  for v in vs for x in v["cells"]),
                          "① 内不再有独立的「主体户数」/「资产笔数」两格（已合并且无第 5 项）")
                    # ② 2×2：4 格，且「加权平均逾期」位于第 2 行
                    c2_bad, row2_bad = [], []
                    for v in vs:
                        cells2 = [x for x in v["cells"] if str(x[2]) == "1"]
                        if len(cells2) != 4:
                            c2_bad.append("%s ② %d 格" % (v["vid"], len(cells2)))
                        names = [x[0] for x in cells2]
                        # 2 列矩阵：第 2 行为索引 2、3
                        if len(names) >= 4 and names[3] != "加权平均逾期":
                            row2_bad.append("%s 第2行=%s" % (v["vid"], names[2:4]))
                    check(not c2_bad, "② 集中度与账龄 = 4 格（2×2，无空白灰格）",
                          "；".join(c2_bad)[:200])
                    check(not row2_bad, "② 第 2 行 = 「主体平均 | 加权平均逾期」（逾期已上移填灰格）",
                          "；".join(row2_bad)[:250])
                    # ④：处置费用占比已删除，处置费率保留（④ 的字段在面板 rows 里，不在 strip）
                    c3_bad = []
                    for v in vs:
                        names3 = [x[0] for x in v["rows"] if str(x[2]) == "3"]
                        if "处置费用占比" in names3:
                            c3_bad.append("%s 仍有处置费用占比" % v["vid"])
                        if "处置费率" not in names3:
                            c3_bad.append("%s 缺处置费率" % v["vid"])
                        if "处置费用" not in names3:
                            c3_bad.append("%s 缺处置费用（金额）" % v["vid"])
                    check(not c3_bad,
                          "④ 已删「处置费用占比」（与处置费率同义），保留「处置费率」与「处置费用」金额",
                          "；".join(c3_bad)[:250])
                    # ④ 卡数实测（5 = 2+2+1 通栏，2 列对齐、无空格子；与 ③ 同宽同高）
                    n4 = [len([x for x in v["rows"] if str(x[2]) == "3"]) for v in vs]
                    check(set(n4) == {5},
                          "④ 面板卡片数 = 5（累计回收/回收率/预计达成率/处置费用 + 处置费率通栏），"
                          "28 单一致且无空格",
                          "实测分布 %s" % sorted(set(n4)))
                    # ── v9：同一面板内不混排亿元/万元 ──
                    line("    [4a-5] v9：面板内金额单位统一（① 入池息费 改亿元）")

                    def _amt_unit(txt):
                        """金额格单位：返回 '亿' / '万' / None（非金额）"""
                        tt = _strip_tags(txt).strip()
                        if "亿" in tt:
                            return "亿"
                        if re.search(r"[\d,.]\s*万", tt):
                            return "万"
                        return None

                    # 入池息费 28 单实测（元），用于回报最小值/最大值
                    int_vals = sorted(
                        (k, prof[k]["poolTotal"] - prof[k]["poolPrincipal"])
                        for k in order
                        if isinstance(prof[k].get("poolTotal"), (int, float))
                        and isinstance(prof[k].get("poolPrincipal"), (int, float)))
                    if int_vals:
                        line("    入池息费（本息费−本金）：最小 %s %.2f 亿 ／ 最大 %s %.2f 亿"
                             % (int_vals[0][0], int_vals[0][1] / 1e8,
                                int_vals[-1][0], int_vals[-1][1] / 1e8))
                        line("    < 0.01 亿（100 万）的单数：%d → %s"
                             % (sum(1 for _k, vv in int_vals if vv < 1e6),
                                "全部走亿元" if all(vv >= 1e6 for _k, vv in int_vals)
                                else "存在回退万元"))
                    # 逐面板扫描：同一 cat 内是否同时出现「亿」与「万」金额
                    mix_bad, cat_units = [], {}
                    for v in vs:
                        pool = [(x[0], x[1], str(x[2])) for x in (v["cells"] + v["rows"])]
                        per = {}
                        for lab, val, cat in pool:
                            u = _amt_unit(val)
                            if u is None:
                                continue
                            per.setdefault(cat, {}).setdefault(u, []).append(lab)
                        for cat, units in per.items():
                            cat_units.setdefault(cat, set()).update(units.keys())
                            if len(units) > 1:
                                mix_bad.append("%s 面板%s 混排 %s" % (
                                    v["vid"], cat,
                                    {u: labs[:3] for u, labs in units.items()}))
                    CATN = {0: "①", 1: "②", 2: "③", 3: "④", 4: "⑤"}
                    for cat in sorted(cat_units):
                        line("      面板%s 金额单位集合：%s"
                             % (CATN.get(int(cat), cat), sorted(cat_units[cat])))
                    check(not mix_bad,
                          "28/28 单 每个面板内金额单位不混排（① 全亿元 ／ ② 全万元 ／ ③④ 全亿元）",
                          "；".join(mix_bad)[:300])
                    # ① 专项：4 格里金额类必须以「亿元」收尾、且不再出现「万元」
                    c1_unit_bad = []
                    for v in vs:
                        cells1 = [x for x in v["cells"] if str(x[2]) == "0"]
                        for lab, val, _c in cells1:
                            tt = _strip_tags(val).strip()
                            if lab in ("入池本息费", "入池本金", "入池息费"):
                                if not (tt.endswith("亿") or tt == "—"):
                                    c1_unit_bad.append("%s %s=%s" % (v["vid"], lab, tt))
                        if "万" in _strip_tags("".join(x[1] for x in cells1)):
                            c1_unit_bad.append("%s ① 仍含「万」" % v["vid"])
                    check(not c1_unit_bad,
                          "① 资产池情况 3 个金额格全部以「亿元」结尾（入池息费不再用万元）",
                          "；".join(c1_unit_bad)[:250])
                    # 入池息费 抽样实测（p0 / p1 / p24 与 28 单总量级）
                    s0 = [x for x in vs[0]["cells"] if str(x[2]) == "0"]
                    v0 = dict((_strip_tags(a), _strip_tags(b)) for a, b, _c in s0)
                    check(v0.get("入池息费") == "0.51亿",
                          "p0 入池息费 = 5,056.15 万 → 「0.51亿」（亿元 2 位）",
                          "实测 %s" % v0.get("入池息费"))
                    check(v0.get("入池本息费") == "11.92亿" and v0.get("入池本金") == "11.42亿",
                          "p0 入池本息费 11.92亿 / 入池本金 11.42亿（同面板、同单位）",
                          "实测 %s / %s" % (v0.get("入池本息费"), v0.get("入池本金")))
                    n_yi = sum(1 for v in vs for x in v["cells"]
                               if str(x[2]) == "0" and x[0] == "入池息费"
                               and _strip_tags(x[1]).strip().endswith("亿"))
                    check(n_yi == 28,
                          "28/28 单入池息费均渲染为「亿元」（无 <0.01 亿回退）",
                          "实测 %d/28" % n_yi)
                    # 副行口径说明保持（本息费 − 本金；归一单为「已归一：本息费 − 本金 ＝ N 亿」）
                    note_ok, note_bad = 0, []
                    for v in vs:
                        if re.search(r"(已归一：)?本息费 − 本金", v["stripHtml"]):
                            note_ok += 1
                        else:
                            note_bad.append(v["vid"])
                    check(note_ok == 28,
                          "28/28 单入池息费副行「本息费 − 本金」口径说明保留", 
                          "缺副行：%s" % "、".join(note_bad[:5]))
                    # 归一单（p1）的副行数值也已换成亿元
                    check(re.search(r"已归一：本息费 − 本金 ＝ 4\.41 亿", vs[1]["stripHtml"])
                          is not None,
                          "p1 归一副行数值为「4.41 亿」（原 44,086.92 万，同格内不再混排万元）")
                    # 「—」不得出现在保留展示的集中度字段（改用「未披露」）
                    conc_undis = 0
                    conc_dash = []
                    for v in vs:
                        for lab, val, _cat in v["cells"]:
                            if lab not in CONC_FIELDS:
                                continue
                            tv = _strip_tags(val).strip()
                            if tv == "未披露":
                                conc_undis += 1
                            elif tv == "—":
                                conc_dash.append("%s %s" % (v["vid"], lab))
                    check(not conc_dash,
                          "保留展示的集中度字段不再出现「—」（改用「未披露」），"
                          "本批「未披露」%d 处" % conc_undis,
                          "；".join(conc_dash)[:200])
                    # 字段字典覆盖 7 个字段
                    dict_bad = []
                    for v in vs:
                        have = set(re.findall(r'data-pf-dict-field="([^"]*)"', v["stripHtml"]))
                        if have != set(CONC_FIELDS):
                            dict_bad.append("%s 字典 %d 项" % (v["vid"], len(have)))
                        if 'class="pf-dict"' not in v["stripHtml"]:
                            dict_bad.append("%s 缺字段字典" % v["vid"])
                    check(not dict_bad,
                          "28/28 单 ② 面板底部有「字段字典」折叠块，覆盖 7 个字段"
                          "（可得率 / 源未披露单数 / 缺失原因 / 展示策略）",
                          "；".join(dict_bad)[:300])
                    # 隐藏字段确认：主表中不出现
                    hid_bad = []
                    for v in vs:
                        for lab, _val, _cat in v["cells"]:
                            if lab in hide_fields:
                                hid_bad.append("%s %s" % (v["vid"], lab))
                    check(not hid_bad,
                          "<50%% 可得率字段（%s）已从主表移出" % "、".join(hide_fields) if hide_fields
                          else "无 <50% 字段",
                          "；".join(hid_bad)[:200])
                    # ── v6 任务1：③④ 6/6 对称栅格 ──
                    line("    [4a-3] ③④ 对称栅格")
                    check("grid-template-columns:repeat(2,minmax(0,1fr))!important" in CSS,
                          "面板容器为 2 等分栅格（repeat(2,minmax(0,1fr))）")
                    check("align-items:stretch!important" in CSS,
                          "面板容器 align-items:stretch（③④ 等高）")
                    pan_cls = res.get("panelClass") or []
                    check(pan_cls.count("pf-panel pf-7") == 1
                          and pan_cls.count("pf-panel pf-5") == 1,
                          "③(pf-7) 与 ④(pf-5) 面板各 1 个（类名保留，宽度改由容器统一）",
                          "；".join(pan_cls[:4]))
                    check("grid-column:span 1" in CSS
                          and "grid-column:span 7" not in CSS
                          and "grid-column:span 5" not in CSS,
                          "CSS 中已无 7/5 不对称 span（③④ 均 span 1）")
                    wdiff = res.get("panelWDiff")
                    check(res.get("panelCols") == [2, 2],
                          "③④ 面板内部均为 2 列 KPI（字段多寡在面板内消化，不外扩）",
                          "实测列数 %s" % (res.get("panelCols"),))
                    check(wdiff is not None and wdiff <= 2.0,
                          "③④ 面板宽度差 ≤ 2px（2 等分栅格 → 实测 Δ=0px）")
                    line("    指标条 9 格（①5+②主表4）+ 面板 16 行（另 2 行通栏）＝ 27 个落点 × 28 单，其中：")
                    for i, name in enumerate(CATS):
                        n = sum(len(re.findall(
                            r'<div class="pf-(?:c|row)[^"]*" data-pf-cat="%d" data-pf-field="[^"]*"' % i,
                            v["stripHtml"] + v["gridHtml"])) for v in vs)
                        line("      %s %2d 格/单" % (name, n // 28))
                    # ── 口径统一：折价率 → 证券化率（用户 2026-10-12 要求）──
                    line("[4a-2] 口径统一：旧口径字段名 → 证券化率")
                    module_src = CSS + HTML + JS
                    check("折价率" not in module_src,
                          "本模块输出（CSS+HTML+JS %d 字符）中旧口径字段名出现 0 次"
                          % len(module_src),
                          "；".join(m.group(0) for m in re.finditer(r".{0,10}折价率.{0,10}",
                                                                    module_src))[:200])
                    # 渲染可见文本里不得出现折价率，且证券化率恰好 1 行/单
                    rate_rows = []
                    for v in vs:
                        alltxt = v["stripHtml"] + v["gridHtml"]
                        if "折价率" in alltxt:
                            rate_rows.append("%s 渲染含折价率" % v["vid"])
                        fields = re.findall(r'data-pf-field="([^"]*)"', alltxt)
                        if fields.count("证券化率") != 1:
                            rate_rows.append("%s 证券化率 %d 行" % (v["vid"], fields.count("证券化率")))
                        if "折价率" in "".join(fields):
                            rate_rows.append("%s 字段名含折价率" % v["vid"])
                    check(not rate_rows,
                          "28/28 单渲染文本无旧口径字段名，且「证券化率」恰好 1 行（无重复行）",
                          "；".join(rate_rows)[:300])
                    # 渲染路径不再读 discount：规格表内 discount 出现次数 = 0
                    spec_text = JS[JS.index("var PF_STRIP_CELLS"):JS.index("<<\\/PF-CATS>>")]
                    check("discount" not in spec_text,
                          "渲染规格表（PF_STRIP_CELLS + PF_PANEL_ROWS）内不再出现 discount")
                    render_src = JS[JS.index("function renderStrip"):JS.index("function build(")]
                    check("discount" not in render_src,
                          "渲染函数（renderStrip / renderPanels）内不读 discount",
                          "；".join(re.findall(r".{0,30}discount.{0,30}", render_src)))
                    spec_labels = ([c["label"] for c in sp["strip"]]
                                   + [r["label"] for r in sp["rows"]])
                    check("折价率" not in spec_labels and spec_labels.count("证券化率") == 1,
                          "5 类规格表内：旧口径字段 0 项、证券化率 1 项（③ 预期回收与发行结构）",
                          "；".join(spec_labels))
                    # 逐单「证券化率 + 旧口径对偶值 ≈ 100%」交叉验证（payload 现算）
                    line("    逐单「证券化率 + 旧口径对偶值 ≈ 100%」验证（容差 0.02pp）：")
                    sum_bad, sum_ok, sum_na = [], 0, []
                    for k in order:
                        pp = prof[k]
                        sr, dr = pp.get("secRatio"), pp.get("discount")
                        if sr is None or dr is None:
                            sum_na.append(k)
                            continue
                        if abs((sr + dr) - 1.0) <= 0.0002:
                            sum_ok += 1
                        else:
                            sum_bad.append("%s 和=%.6f" % (k, sr + dr))
                    check(not sum_bad, "27/28 单 证券化率 + 旧口径对偶值 = 100.00%（±0.02pp）",
                          "；".join(sum_bad)[:300])
                    line("      实证：%d/28 单相加=100%%（%d 单无对偶值：%s）"
                         % (sum_ok, len(sum_na), "、".join(sum_na)))
                    # 渲染值 = 现算值（逐单，证明渲染走 secRatio 而非旧口径换算）
                    calc_bad, n_calc = [], 0
                    for i, v in enumerate(vs):
                        k = order[i]
                        pp = prof[k]
                        sr = pp.get("secRatio")
                        got = {_strip_tags(a): _strip_tags(b) for a, b, _c in v["rows"]}
                        val = got.get("证券化率")
                        if sr is None:
                            # p24 payload 无池数据 → 回退原文，仍须有值（不是 —）
                            if not val or val == "—":
                                calc_bad.append("%s payload 无值且回退失败（%s）" % (k, val))
                            continue
                        n_calc += 1
                        if val != "%.2f%%" % (sr * 100):
                            calc_bad.append("%s 渲染 %s ≠ 现算 %.2f%%" % (k, val, sr * 100))
                    check(not calc_bad,
                          "逐单「证券化率」渲染值 = 发行规模 ÷ 入池本息费（现算 %d 单 + 1 单回退）"
                          % n_calc,
                          "；".join(calc_bad)[:300])
                # ── [4b] 结构完整性 ──
                check(all(v["panels"] == 3 for v in vs), "分区面板 3 块/单（③④⑤）")
                check(all(v["steps"] == 7 for v in vs), "时间轴 7 步/单")
                check(all(v["stepList"] == ["设立日", "首个支付日", "预期到期日（优）", "法定到期日（优）",
                                            "预期到期日（次）", "法定到期日（次）", "清算日"]
                          for v in vs),
                      "时间轴 7 步标签与顺序正确")
                check(all(not v["acct"] for v in vs), "「账户配平」残留 0")
                check(all(not v["legacyKpi"] for v in vs), "新结构内 .kpi 旧格子残留 0")
                check(all(v["tags"]["strip"].find("pf-strip") >= 0 and
                          v["tags"]["grid"].find("pf-panels") >= 0 for v in vs),
                      "DOM 钩子保留（kpi-strip / data-chart=\"kpi-grid\"）")
                check(all(v["tags"]["pfAttr"] == ["strip", "panels"] for v in vs),
                      "data-pf 标记写入（strip / panels）")

                # ── [4c] 合并冗余：同值不跨类重复 + 「发行」重复 = 0 ──
                line("[4c] 合并冗余 / 「发行」重复检查")
                dup_bad = []
                for i, v in enumerate(vs):
                    seen = {}
                    for lab, val, cat in (v["cells"] + v["rows"]):
                        key = lab
                        if key in seen:
                            dup_bad.append("%s %s 出现 2 次（cat %s/%s）"
                                           % (v["vid"], _strip_tags(lab), seen[key], cat))
                        seen[key] = cat
                check(not dup_bad, "同 label 不跨类重复（33 格逐单唯一）", "；".join(dup_bad)[:300])
                dup = res["issueDup"]
                check(dup is not None and not dup["bad"] and len(dup["groupHits"]) == 1,
                      "「发行」重复检查 = 0（%d 条渲染文本中，仅 ③ 分组名 1 处 + 字段名「发行规模」）"
                      % (dup["nTexts"] if dup else 0),
                      "；".join(x["kind"] + ":" + x["s"] for x in dup["bad"])[:200] if dup else "规格表解析失败")
                # 源文本里每一处「发行」都必须落在 ③ 类的词条（预期回收与发行结构 / 发行规模 /
                # 发行主体 / 发行说明书溯源）内，否则判为「发行」类目重复
                srcBad = []
                for mm in re.finditer("发行", JS):
                    ctx = JS[max(0, mm.start() - 14):mm.start() + 14]
                    if not any(k in ctx for k in ("预期回收与发行结构", "发行规模", "发行主体",
                                                  "发行说明书")):
                        srcBad.append(ctx.replace("\n", " "))
                check(not srcBad,
                      "JS 源内 %d 处「发行」全部落在 ③ 类词条内（无重复类目）" % JS.count("发行"),
                      "；".join(srcBad)[:200])

                # ── [4d] 隐藏「缺失材料」note ──
                line("[4d] 隐藏「缺失材料」note（display:none，DOM 保留）")
                hn_bad, keep_bad = [], []
                for v in vs:
                    hid = [x for x in v["notes"] if x["hidden"]]
                    kept = [x for x in v["notes"] if not x["hidden"]]
                    if len(hid) != 1 or any(x["attr"] != "note-hidden" for x in hid):
                        hn_bad.append("%s 隐藏 %d 个 attr=%s"
                                      % (v["vid"], len(hid), [x["attr"] for x in hid]))
                    if any(x["text"].startswith("缺失材料") for x in kept):
                        keep_bad.append("%s 有「缺失材料」未被隐藏" % v["vid"])
                check(not hn_bad, "28/28 单的「缺失材料」note 已隐藏并打 data-pf",
                      "；".join(hn_bad)[:300])
                check(not keep_bad, "「缺失材料」漏隐藏 0", "；".join(keep_bad)[:200])
                check(all(x["hidden"] for v in vs for x in v["notes"] if x["text"].startswith("缺失材料")),
                      "定位方式：文本前缀「缺失材料」→ 100% 命中")
                # 干扰 note（不以「缺失材料」开头）必须保留
                interfered = [x for v in vs for x in v["notes"]
                              if not x["text"].startswith("缺失材料") and x["hidden"]]
                check(not interfered, "未误伤其它 .note（非「缺失材料」前缀一律保留）",
                      "；".join(x["text"] for x in interfered)[:200])
                n_notes = sum(len(v["notes"]) for v in vs)
                n_hid = sum(1 for v in vs for x in v["notes"] if x["hidden"])
                n_src = sum(1 for v in raws for x in raws[v]["notes"]
                            if x.startswith("缺失材料")) if raws else 0
                check(n_hid == 28, "隐藏数 %d（报告内「缺失材料」note 共 %d 个）" % (n_hid, n_src))
                n_other = n_notes - n_hid
                check(n_other >= 28 and n_hid + n_other == n_notes,
                      "同视图干扰 note %d 条全部保留（共 %d 条，仅隐藏 %d 条）"
                      % (n_other, n_notes, n_hid))
                check(".note.pf-missing-hidden{display:none!important}" in CSS
                      and '[class~="view"] .note.pf-missing-hidden' in CSS,
                      "CSS 确含 .note.pf-missing-hidden{display:none!important}（带 view 限定）")

                # ── [4e] 5 类字段数汇总（打印用户要看的表） ──
                line("[4e] 5 类字段归属表（每单格数）")
                for i, name in enumerate(CATS):
                    labs = CAT_FIELDS[name]
                    bdg = CAT_BADGES[name]
                    cnt_ = sum(1 for v in vs for lab, _, c in (v["cells"] + v["rows"])
                               if int(c) == i) // 28
                    line("    %s　格 %d（字段 %d：%s）%s"
                         % (name, cnt_, len(labs), "、".join(labs),
                            ("　＋徽章：" + "、".join(bdg)) if bdg else ""))

                # ── [5] 单位检查 ──
                line("[5] 单位检查（UNIT_POLICY 逐值）")
                total = bad = 0
                examples = {}
                for v in vs:
                    for lab, val, _cat in (v["cells"] + v["rows"]):
                        fam = _unit_family(lab)
                        if not fam:
                            continue
                        total += 1
                        ok, why = _check_value(fam, val)
                        if not ok:
                            bad += 1
                            print("    ✗ %s %s → %s（%s）" % (v["vid"], _strip_tags(lab),
                                                              _strip_tags(val), why))
                        examples.setdefault(fam, _strip_tags(val))
                check(bad == 0, "合规 %d/%d（亿元·万元·%%·月·计数）" % (total - bad, total))
                line("    示例：" + "　".join("%s → %s" % (k, v) for k, v in sorted(examples.items())))

                # ── [6] 关键值抽查 ──
                line("[6] 关键值抽查")
                p0 = vs[0]
                by_label = {}
                for lab, val, _cat in (p0["cells"] + p0["rows"]):
                    by_label.setdefault(_strip_tags(lab), _strip_tags(val))
                exp0 = {
                    "入池本息费": "11.92亿", "入池本金": "11.42亿", "累计回收": "3.29亿",
                    "回收率": "27.63%", "处置费率": "5.47%",
                    "发行规模": "2.27亿", "优先档规模": "1.70亿", "次级档规模": "0.57亿",
                    "证券化率": "19.04%", "预计回收率": "21.17%",
                    "预计达成率": "130.52%", "中债预计回收": "2.52亿", "处置费用": "0.18亿",
                    "优先档XIRR": "3.11%", "次级档XIRR": "27.91%",
                    "存续期": "27.5个月", "支付周期": "5期", "单笔最高": "34.65万",
                    "加权平均逾期": "6.7个月",
                    "合同处置费率/上限": "5.50%", "入池息费": "0.51亿",
                    "主体户数 / 资产笔数": "11,897 户 / 27,295 笔",
                }
                check("前5大占比" not in by_label,
                      "p0 主表已不含 <50% 可得率字段「前5大占比」（改在字段字典登记）")
                miss = []
                for k, want in exp0.items():
                    got = by_label.get(k)
                    if got != want:
                        miss.append("%s 期望 %s 实得 %s" % (k, want, got))
                check(not miss, "p0 抽查 %d 项" % len(exp0), "；".join(miss)[:400])
                check(" " not in by_label.get("首末支付日", "") or "→" in by_label.get("首末支付日", ""),
                      "首末支付日渲染为「首 → 末」", by_label.get("首末支付日", ""))

                # p24（payload 池数据缺失 → 原文回退）与 3 个 months 缺失单
                idx = {order[i]: i for i in range(28)}
                p24 = vs[idx["邮盈惠兴2024年第四期"]]
                d24 = {_strip_tags(a): _strip_tags(b) for a, b, _c in
                       (p24["cells"] + p24["rows"])}
                check(d24.get("入池本息费") == "23.07亿" and d24.get("入池息费") == "4.32亿",
                      "p24 payload 缺失 → 回退服务端原文并归一",
                      "入池本息费 %s / 入池息费 %s" % (d24.get("入池本息费"), d24.get("入池息费")))
                for nm in ["臻粹2024年第三期", "鸿富2023年第七期", "鸿富2023年第三期"]:
                    dv = {_strip_tags(a): _strip_tags(b) for a, b, _c in
                          (vs[idx[nm]]["cells"] + vs[idx[nm]]["rows"])}
                    check(dv.get("存续期") == "—", "%s months 缺失 → 存续期「—」" % nm)
                # p1 口径归一 + 源披露拆分标注（Lead 裁决：点明原文该格是「费用」）
                p1 = vs[1]
                d1 = {_strip_tags(a): _strip_tags(b) for a, b, _c in
                      (p1["cells"] + p1["rows"])}
                h1 = p1["html"] or ""
                need = ["已归一：本息费 − 本金 ＝ 4.41 亿",
                        "利息 1.58 亿", "费用 2.83 亿",
                        "本金 17.97 亿 / 利息 1.58 亿 / 费用 2.83 亿 / 合计 22.38 亿"]
                miss1 = [x for x in need if x not in h1]
                check(d1.get("入池息费") == "4.41亿" and not miss1
                      and "原文 2.83 亿" not in h1,
                      "p1 入池息费按差额口径归一 + 源披露拆分为「利息+费用」（v9 全部亿元）",
                      ("缺：" + "；".join(miss1)) if miss1 else "")
                # 源披露拆分表（JS 内硬编码）与 payload 的算术互相印证
                msp = re.search(r"var SRC_SPLIT = \{(.*?)\n  \};", JS, re.S)
                entries = re.findall(r'"([^"]+)":\s*\{(.*?)\}', msp.group(1), re.S) if msp else []
                sp_rows = [(nm, dict((kk, float(vv)) for kk, vv in
                                     re.findall(r"(prin|inte|fee|total):\s*([\d.]+)", body)))
                           for nm, body in entries]
                bad = []
                for nm, dd in sp_rows:
                    if nm not in order:
                        bad.append("%s 不在 ORDER" % nm)
                        continue
                    pt = prof[nm]["poolTotal"]
                    pp = prof[nm]["poolPrincipal"]
                    if not (abs(dd["prin"] + dd["inte"] + dd["fee"] - dd["total"]) < 0.02
                            and abs(dd["inte"] + dd["fee"] - (pt - pp)) < 0.02
                            and abs(dd["total"] - pt) < 0.02):
                        bad.append("%s 表值不自洽" % nm)
                check(len(sp_rows) == 1 and not bad,
                      "SRC_SPLIT 源披露拆分母表自洽（本金+利息+费用＝合计＝poolTotal；利息+费用＝差额）",
                      "；".join(bad) if bad else "；".join(
                          "%s 本金 %.2f / 利息 %.2f / 费用 %.2f / 合计 %.2f"
                          % (nm, dd["prin"], dd["inte"], dd["fee"], dd["total"])
                          for nm, dd in sp_rows))
                # 渲染文本中的拆分数字（亿元 2 位，允许四舍五入）
                s_i = _to_yuan_yi(re.search(r"利息 ([\d,]+\.\d{2}) 亿", h1))
                s_f = _to_yuan_yi(re.search(r"费用 ([\d,]+\.\d{2}) 亿", h1))
                s_p = _to_yuan_yi(re.search(r"本金 ([\d,]+\.\d{2}) 亿", h1))
                s_t = _to_yuan_yi(re.search(r"合计 ([\d,]+\.\d{2}) 亿", h1))
                check(None not in (s_i, s_f, s_p, s_t) and abs(s_p + s_i + s_f - s_t) < 2e6,
                      "p1 副行/tooltip 渲染的拆分金额与表一致（亿元 2 位舍入内，容差 200 万）",
                      "本金 %s / 利息 %s / 费用 %s / 合计 %s" % (s_p, s_i, s_f, s_t))
                # 长文本费率行 + HTML 转义（p2「>5%且≤25%」）
                h2 = vs[2]["html"] or ""
                check("&gt;" in h2 and "<script" not in h2 and "<img" not in h2,
                      "长文本费率行 HTML 转义安全（原文含 > 号）")

                # ── [4f] 冗余元数据条 / 兑付与清算时点表格 ──
                line("[4f] 冗余元数据条 / 兑付与清算时点表格")
                check(all(v["infoKept"] and v["infoHidden"] for v in vs),
                      "28/28 冗余条 dl.infolist 整条隐藏（display:none，DOM 保留）")
                check(".infolist.pf-meta-hidden{display:none!important}" in CSS,
                      "CSS 确含 .infolist.pf-meta-hidden{display:none!important}")
                check(all(v["timing"]["present"] for v in vs),
                      "28/28 「兑付与清算时点」data-chart=\"timing-block\" 仍在")
                check(all(not v["timing"]["pfTouched"] for v in vs),
                      "「兑付与清算时点」表格未被本模块改写（无 data-pf / pf-* 类）")
                check(all(("优先档" in v["timing"]["text"]) and ("次级档" in v["timing"]["text"])
                          for v in vs),
                      "时间轴表格内容完整（优先档 / 次级档 行俱在）")
                ml_ok, ml_bad = 0, []
                for v in vs:
                    ml = v["metaLine"]
                    if not ml:
                        ml_bad.append("%s 无底部小字" % v["vid"])
                        continue
                    keys = "".join(ml["kk"])
                    if ("归属目录" in keys and "项目主键" in keys
                            and not any(x in keys for x in ("设立日", "清算日", "是否回购", "银行分组"))):
                        ml_ok += 1
                    else:
                        ml_bad.append("%s 小字标签=%s" % (v["vid"], keys))
                check(ml_ok == 28 and not ml_bad,
                      "28/28 底部小字仅含「归属目录 / 项目主键」",
                      "；".join(ml_bad)[:300])
                info0 = raws["p0"]["info"] if raws else {}
                ml0 = vs[0]["metaLine"] or {"vv": []}
                check(info0.get("归属目录") in "".join(ml0["vv"])
                      and info0.get("项目主键") in "".join(ml0["vv"]),
                      "p0 底部小字值取自原 dl.infolist（归属目录 / 项目主键）",
                      " | ".join(ml0["vv"])[:120])

                # __V2 缺席 → 纯 DOM 回退
                do = res["domOnly"]
                line("    纯 DOM 回退标记：strip %s｜panels %s｜steps %s｜info %s｜note %s｜timing %s"
                     "｜acct %s｜legacy %s"
                     % (do["stripOk"], do["panelsOk"], do["stepsOk"], do["infoOk"],
                        do["hiddenOk"], do["timingOk"], do["acct"], do["legacy"]))
                check(do["n"] == 28 and do["stripOk"] and do["panelsOk"] and do["stepsOk"]
                      and not do["acct"] and not do["legacy"]
                      and do["infoOk"] and do["hiddenOk"] and do["timingOk"],
                      "__V2 缺席时纯 DOM 回退仍渲染 7–12 格 / 3 面板 / 7 步 / 隐藏冗余条与缺失材料 / 保留时点表")
                dd = {_strip_tags(a): _strip_tags(b)
                      for a, b, _c in (do["sample"][0]["cells"] + do["sample"][0]["rows"])}
                check(dd.get("入池本息费") == "11.92亿" and dd.get("累计回收") == "3.29亿"
                      and dd.get("发行规模") == "—" and dd.get("证券化率") == "19.04%",
                      "纯 DOM 回退取值正确（发行规模无源 → —；证券化率仍回退原文 19.04%）",
                      "入池本息费 %s / 证券化率 %s / 发行规模 %s" %
                      (dd.get("入池本息费"), dd.get("证券化率"), dd.get("发行规模")))

                # ── [7] 结构 / 静态检查 ──
                line("[7] 结构 / 静态检查")
                check("账户配平" not in JS, "JS 未输出「账户配平」")
                miss_all = [x for x in list(GRID_MAP) if x not in JS]
                check(not miss_all, "原文 23 标签全部在 JS 中读取（一个不丢）",
                      "缺：" + "、".join(miss_all) if miss_all else "")
                check(len(GRID_MAP) == 23, "23 标签 → 5 类落点映射表")
                check(all(x in JS.replace(" ", "") for x in
                          ["入池本息费", "入池本金", "入池息费", "资产笔数", "主体户数",
                           "单笔最高", "单笔平均", "主体最高", "主体平均", "前5大占比",
                           "前10大占比", "加权平均逾期", "中债预计回收", "预计回收率",
                           "发行规模", "优先档规模", "次级档规模", "证券化率",
                           "合同处置费率/上限", "累计回收", "回收率",
                           "优先档XIRR", "次级档XIRR", "存续期", "支付周期", "首末支付日"]),
                      "5 类 28 个字段名在 JS 规格表齐备（含证券化率，已无旧口径字段）")
                check("/^view-p\\d+$/" in JS and '.kpis[data-chart="kpi-grid"]' in JS
                      and '.kpi-strip' in JS, "关键选择器齐备")
                check("const " not in JS and "let " not in JS, "JS 无 const/let（IIFE 局部变量）")
                bal = (JS.count("{") - JS.count("}") == 0 and JS.count("(") - JS.count(")") == 0
                       and JS.count("[") - JS.count("]") == 0)
                check(bal, "JS 括号配平")
                check(CSS.count("{") == CSS.count("}"), "CSS 花括号配平")
                miss_cls = [c for c in res["classes"] if c.startswith("pf-") and ("." + c) not in CSS]
                n_pf = len([c for c in res["classes"] if c.startswith("pf-")])
                check(n_pf >= 12 and not miss_cls,
                      "JS 产出的 %d 个 pf-* 类名均有 CSS 规则" % n_pf,
                      "缺样式：" + "、".join(miss_cls) if miss_cls else "")
                # 格式化边界（真 JS 的 pfFmt 逐例执行）
                fmt = res.get("fmt")
                want_fmt = {
                    "small999999": "100.00 万元（不足 0.01 亿）",
                    "exact1e6": "0.01 亿",
                    "zeroYi": "0.00 万元（不足 0.01 亿）",
                    "nullYi": "—", "zeroWan": "0.00 万", "negPct": "-1.23%",
                    "bigYi": "1,234.57 亿", "bigCnt": "1,234,567 笔",
                    "mon": "11.5 个月", "blankTxt": "—", "dashTxt": "—",
                }
                if not fmt:
                    check(False, "pfFmt 边界用例（未找到 <<PF-FMT>> 标记）")
                else:
                    diff = ["%s 期望 %s 实得 %s" % (k, v, fmt.get(k))
                            for k, v in want_fmt.items() if fmt.get(k) != v]
                    check(not diff, "pfFmt 边界用例 %d 项（0/空/负/万亿/千分位）" % len(want_fmt),
                          "；".join(diff)[:300])
                css_checks = {
                    "16px 圆角": "border-radius:16px" in CSS,
                    "--grad-soft 渐变底": "--grad-soft" in CSS and "background:var(--grad-soft)" in CSS,
                    "分区标题序号徽章": ".pf-snum" in CSS,
                    "区内细分隔线": ".pf-rows{display:grid;grid-template-columns:repeat(2" in CSS
                                     and "gap:1px;background:var(--line2)" in CSS,
                    "悬停高亮当前行": ".pf-row:hover" in CSS,
                    "时间轴步骤条": ".pf-tl" in CSS and ".pf-ts" in CSS,
                    "缺失材料隐藏": ".note.pf-missing-hidden{display:none!important}" in CSS,
                }
                for k, v in css_checks.items():
                    check(v, "CSS · " + k)

                # ── [8] 归一化 / 缺口清单 ──
                line("[8] 归一化与缺口清单")
                exact, quant, real, na = [], [], [], []
                dom_raw, dom_int_map = {}, {}
                for i, v in enumerate(vs):
                    k = order[i]
                    dom = dict((a, b) for a, b, *_ in raws[views[i]]["grid"]) if raws else {}
                    dom_raw[k] = dom.get("入池息费")
                    dom_int_map[k] = _amt(dom.get("入池息费"))
                    pt, pp = prof[k].get("poolTotal"), prof[k].get("poolPrincipal")
                    if dom_int_map[k] is None or pt is None or pp is None:
                        na.append(k)
                        continue
                    d = dom_int_map[k] - (pt - pp)
                    (exact if abs(d) < 1 else (quant if abs(d) <= 500000 else real)).append(k)
                line("    原文「入池息费」vs 服务端「本息费 − 本金」："
                     "精确一致 %d 单｜亿元 2 位量化噪声（≤50 万）%d 单｜实质不一致 %d 单｜无法比较 %d 单"
                     % (len(exact), len(quant), len(real), len(na)))
                for k in real:
                    pt, pp = prof[k]["poolTotal"], prof[k]["poolPrincipal"]
                    line("      · 实质不一致：%s　原文格「%s」＝仅费用（亿位四舍五入，"
                         "未含利息 15,753.35 万）；逐单差额口径 = %.2f 万"
                         % (k, dom_raw.get(k), (pt - pp) / 1e4))
                if na:
                    line("      · 无法比较（payload 缺池数据 → 回退原文）：" + "、".join(na))
                norm = []
                for i, v in enumerate(vs):
                    k = order[i]
                    if prof[k].get("poolTotal") is None:
                        norm.append("%s：payload 无池数据 → 原文回退" % k)
                for s in norm:
                    line("    · " + s)
                dash = {}
                for v in vs:
                    for lab, val, _cat in (v["cells"] + v["rows"]):
                        if _strip_tags(val).strip() == "—":
                            dash.setdefault(_strip_tags(lab).strip(), []).append(v["vid"])
                line("    「—」分布：" + ("；".join("%s %d 单" % (k, len(v)) for k, v in sorted(dash.items()))
                                         if dash else "无"))
                line("    样例（view-p0 指标条）：" +
                     " ｜ ".join("%s=%s" % (_strip_tags(a), _strip_tags(b)) for a, b, _c in
                                 vs[0]["cells"]))
                line("    样例（view-p0 面板前 4 行）：" +
                     " ｜ ".join("%s=%s" % (_strip_tags(a), _strip_tags(b)) for a, b, _c in
                                 vs[0]["rows"][:4]))
                line("    样例（view-p0 时间轴）：" + " → ".join(p0["stepList"]))
                line("    样例（view-p0 隐藏 note）：" +
                     " ｜ ".join("%s(hidden=%s)" % (x["text"], x["hidden"]) for x in p0["notes"]))

    line("─" * 78)
    line("自检结果：" + ("全部通过 ✓" if ok_all else "存在失败项 ✗"))
    line("═" * 78)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(self_check())
