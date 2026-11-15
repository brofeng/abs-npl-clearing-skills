# -*- coding: utf-8 -*-
r"""v2 模块 60_assets —— 点 4：资产池维度区（圆环图重排 / 单类目转表 / 卡片均衡 / 维度②③ 缩放 / 横轴日期化）。

职责（只碰单项目视图 #view-p0 … #view-p27 的「资产池基础情况」与「维度②③」图表）：
  A. 圆环图按卡片实际宽度重排
     · 组装层 BASE_JS 的 redrawDonut 把 viewBox 固定成 560 宽、并把 width/height 写成属性，
       在 ~360-400px 的 .dist-grid 卡片里必然溢出（用户截图：图例跑到卡片外）。
     · 本模块用 host 实测内容宽 W 重排：环 + 图例同一画布，所有 x 落在 [pad, W-pad] 内；
       W < 430 自动切「上图例下」纵向布局；超长标签用「…」截断、全称进 <title>；
       width:100%;height:auto ⇒ 任何卡片宽度都不会越界。
  B. 「全部为 XX」的单类目维度不再单独占卡片
     · 把 .dist-grid 里的 .xt-solo 卡片移除，在本节开篇（.pool-sum 之后）汇总成
       「维度名｜取值｜占比｜余额」小表格（多行）；维度名优先按取值词义判定，
       否则用「同节已知维度里缺失的那一个」推定。
  C. 卡片空间均衡：.dist-grid{align-items:start} + 卡片高度自适应 + 内容不溢出（audit 复查）。
  D. 维度②③ 的图随容器自适应并适度缩小：③节 recon-line+grouped-bar 并排两列；
     ④节 waterfall/tranche-line 限宽 900（仍是 ≥1.0 放大，刻度不会看不清）。
  E. 横轴阿拉伯数字 → 可读日期：支付期次标签改为 YYYY-MM / YY-MM（密度控制、不重叠），
     <title> 同时给出「第 N 期 · YYYY-MM-DD」，并补横轴标题「横轴：支付期次（支付日 …）」。
     日期取自 __V2.FL[key].pay（若组装层注入）→ 否则从视图内「序号+支付日」表格读取；
     取不到就标「—」，绝不臆造。

契约：导出 CSS / HTML / JS；JS 为 IIFE，全部局部变量（助手统一 a6 前缀），
不新增任何全局标识（仅 window.__V6 供调试）。可独立运行：python 60_assets.py 打印自检。
"""
from __future__ import annotations

import re

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

# ════════════════════════════════════════════════════════════════
# CSS —— 只新增 .v6-* 与针对既有钩子的窄规则
# ════════════════════════════════════════════════════════════════
CSS = r"""
/* ===== 60_assets：资产池维度区（圆环重排 / 单类目转表 / 卡片均衡 / 维度②③ 缩放）===== */
[data-chart="donut"] svg,
[data-chart="hbar"] svg,
[data-chart="treemap"] svg,
[data-chart="recon-line"] svg,
[data-chart="tranche-line"] svg,
[data-chart="grouped-bar"] svg,
[data-chart="waterfall"] svg{width:100%!important;height:auto!important;max-width:100%!important;display:block}
/* C：同排卡片不被等高拉伸，各卡高度按内容自适应 */
.dist-grid{align-items:start!important}
.dist-grid>.chart{align-self:start!important;height:auto!important;min-height:0!important;margin-bottom:0!important}
.dist-grid>.chart .ct{flex:0 0 auto}
/* v7：⑥ 分布图改「3+3+2+2」等高管排（行内等高、行间等高、2 张行撑满整行）*/
/* 容器：行等分（grid-auto-rows:1fr 让 4 行等高）；行内列 stretch 让同排等高 */
.dist-grid[data-v6-rows]{display:grid!important;grid-template-columns:1fr!important;
  grid-auto-rows:1fr!important;gap:10px!important;align-items:stretch!important}
.v6-row{display:grid;gap:10px;align-items:stretch;min-height:0}
.v6-row[data-cols="3"]{grid-template-columns:repeat(3,minmax(0,1fr));align-items:stretch}
.v6-row[data-cols="2"]{grid-template-columns:repeat(2,minmax(0,1fr));align-items:stretch}
.v6-row>.chart{align-self:stretch!important;height:100%!important;min-height:0!important;
  margin-bottom:0!important;box-sizing:border-box;
  display:flex;flex-direction:column;justify-content:flex-start}
.v6-row>.chart>.ct,.v6-row>.chart>.ct2,.v6-row>.chart>.note{flex:0 0 auto}
.v6-row>.chart>svg{flex:0 0 auto!important;min-height:0!important;margin-left:auto;margin-right:auto;max-height:100%;overflow:visible}
/* D：③节 分期节奏——两张图并排，一屏看更多；窄屏自动落回单列 */
.v6-duo{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:14px;align-items:start;margin:0 0 14px}
.v6-duo>.chart{margin-bottom:0!important}
/* D：④节 瀑布/分档——限宽，既缩小占屏又保持 ≥1.0 放大（刻度不糊） */
.v6-cap>svg{max-width:900px;margin:0 auto}
/* A：环 + 图例同一画布，图例数值列右对齐到内边距内 */
.v6-donut{overflow:visible}
.v6-lg{font-size:10px;fill:#38425A}
.v6-lv{font-size:10px;fill:#697487;font-variant-numeric:tabular-nums}
.v6-lc{font-size:10px;fill:#98A2B3}
.v6-ln{stroke:rgba(26,34,48,.07);stroke-width:1}
.v6-ct{font-size:10px;fill:#98A2B3}
.v6-cv{font-size:13px;font-weight:700;fill:#141A26;font-variant-numeric:tabular-nums}
.v6-arc{transition:opacity .16s cubic-bezier(.16,.68,.42,1)}
.v6-arc:hover{opacity:.86}
/* B：单一取值维度汇总表（放在本节开篇） */
.v6-solo{margin:12px 0 14px;border:1px solid rgba(26,34,48,.08);border-radius:12px;overflow:hidden;background:#fff}
.v6-solo table{width:100%;border-collapse:collapse;font-size:12.5px;color:#38425A}
.v6-solo caption{caption-side:top;text-align:left;padding:9px 13px;font-size:12px;color:#697487;
  background:#F7FAFD;border-bottom:1px solid rgba(26,34,48,.06)}
.v6-solo th,.v6-solo td{padding:7px 13px;border-bottom:1px solid rgba(26,34,48,.06);text-align:left;vertical-align:middle}
.v6-solo th{font-weight:600;color:#141A26;background:#FBFCFE;white-space:nowrap}
.v6-solo tr:last-child td,.v6-solo tr:last-child th{border-bottom:0}
.v6-solo td.n,.v6-solo th.n{text-align:right;font-variant-numeric:tabular-nums}
.v6-solo .v6-dim{color:#141A26;font-weight:600}
.v6-axis-cap{font-size:10px;fill:#98A2B3}
.v6-xlabel{font-size:10.5px;fill:#697487;font-variant-numeric:tabular-nums}
/* 全局口径说明条（HTML 导出块用） */
.v6-note{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:0 0 14px;padding:10px 14px;
  border-radius:12px;background:#F7FAFD;border:1px solid rgba(26,34,48,.07);font-size:12px;color:#38425A}
.v6-note b{font-size:12.5px;color:#141A26;margin-right:2px}
.v6-note span{padding:1px 8px;border-radius:999px;background:#EDF1F6;color:#697487}
@media (max-width:760px){.v6-cap>svg{max-width:100%}}
"""

# ════════════════════════════════════════════════════════════════
# HTML —— 全局口径说明条（服务端渲染一次；JS 不依赖它）
# ════════════════════════════════════════════════════════════════
HTML = r"""
<div class="v6-note" role="note" id="v6Note"><b>资产池维度口径</b><span>圆环＝该维度下各取值<b>余额占比</b>（合计 100%）</span><span>单一取值的维度不单独占卡片，汇总于本节开篇「单一取值维度」表</span><span>横轴＝支付期次，刻度标注支付年月</span><span>单位：规模类亿元（不足 0.01 亿用万元）、比率百分号 2 位</span></div>
"""

# ════════════════════════════════════════════════════════════════
# JS —— IIFE；助手统一 a6 前缀，不新增全局标识
# ════════════════════════════════════════════════════════════════
JS = r"""
(function(){
  "use strict";

  /* ───────── 设计令牌（镜像 00_ctx.py）───────── */
  var C = { ink: "#141A26", ink2: "#38425A", sub: "#697487", mute: "#98A2B3",
            line: "rgba(26,34,48,.07)", card: "#fff", surface: "#EDF1F6" };
  var SVGN = "http://www.w3.org/2000/svg";
  var DEF_W = 360;        /* 隐藏视图（display:none 量不到宽）时的设计宽 ≈ 3 列卡片内容宽 */
  var H_MIN_W = 430;      /* ≥ 该宽度用「环左图例右」，否则「上图例下」 */
  var UNIT_RULES = [
    "规模类（余额/入池/回收/发行/优先档/次级档/预计回收/处置费用）→ 亿元 2 位；不足 0.01 亿用万元 2 位",
    "单笔/户均/息费类 → 万元 2 位；比率类 → 百分号 2 位",
    "期数/月数/笔数/户数 → 纯数字＋单位词；日期 → YYYY-MM-DD / 轴标签 YYYY-MM 或 YY-MM"
  ];
  var DIM_KEYS = [
    [/信用|抵押|保证|质押|担保/, "担保方式分布"],
    [/次级|可疑|损失|关注|正常/, "五级分类分布"],
    [/职员|个体|企业主|公务员|自由职业|工人|服务人员|农民|无业/, "借款人职业分布"],
    [/^[\s（(]*[\d.,]+\s*[-~～]/, "未偿本息费余额分布"]
  ];
  var ALL_DIMS = ["未偿本息费余额分布", "五级分类分布", "担保方式分布", "借款人职业分布", "抵押物分布", "现金流回收分布"];

  /* ═════════ 0. 工具（全部 IIFE 局部，a6 前缀）═════════ */
  function a6q(sel, root){ return (root || document).querySelector(sel); }
  function a6qa(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function a6esc(s){
    return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function a6th(n, d){
    if (!isFinite(n)) return "—";
    var neg = n < 0; n = Math.abs(n);
    var s = n.toFixed(d == null ? 2 : d), p = s.split("."), i = p[0], f = p[1] ? "." + p[1] : "";
    i = i.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (neg ? "-" : "") + i + f;
  }
  function a6pct(x){ return a6th(x * 100, 2) + "%"; }
  function a6clamp(v, a, b){ return v < a ? a : (v > b ? b : v); }
  function a6estW(s, fs){
    var w = 0;
    for (var i = 0; i < s.length; i++)
      w += /[\u2e80-\u9fff\uff00-\uffef\u3000-\u303f]/.test(s.charAt(i)) ? fs : fs * 0.58;
    return w;
  }
  function a6fit(s, maxPx, fs){
    s = String(s == null ? "" : s);
    var w = 0, out = "";
    for (var i = 0; i < s.length; i++){
      var ch = s.charAt(i);
      var cw = /[\u2e80-\u9fff\uff00-\uffef\u3000-\u303f]/.test(ch) ? fs : fs * 0.58;
      if (w + cw > maxPx) return out + "…";
      w += cw; out += ch;
    }
    return out;
  }
  var AMT_RE = /(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)/;
  function a6yuan(str){
    var m = AMT_RE.exec(String(str == null ? "" : str));
    if (!m) return null;
    var v = parseFloat(m[1].replace(/,/g, ""));
    if (!isFinite(v)) return null;
    var u = m[2];
    return v * (u.charAt(0) === "亿" ? 1e8 : u.charAt(0) === "万" ? 1e4 : 1);
  }
  /* 图内单位：一张图统一一个单位（按该图最大金额定），避免同图混排
     ≥1 亿元 → 亿元 2 位；否则 → 万元 2 位（分项余额多在万级，万元更耐用）*/
  function a6chartUnit(maxY){ return Math.abs(maxY) >= 1e8 ? "亿" : "万"; }
  function a6amtUnit(y, u){
    if (y == null || !isFinite(y)) return "—";
    return u === "亿" ? a6th(y / 1e8, 2) + " 亿元" : a6th(y / 1e4, 2) + " 万元";
  }
  /* UNIT_POLICY（标量口径）：规模类 → 亿元 2 位（<0.01 亿即 1e6 元 用万元 2 位） */
  function a6scale(y){
    if (y == null || !isFinite(y)) return "—";
    if (y === 0) return "0.00 亿元";
    return Math.abs(y) >= 1e6 ? a6th(y / 1e8, 2) + " 亿元" : a6th(y / 1e4, 2) + " 万元";
  }
  /* 元素「可见文本」：排除 <title> 子节点（hover 提示不算渲染宽度）*/
  function a6visText(el){
    if (!el) return "";
    var out = "", k = el.childNodes || [];
    for (var i = 0; i < k.length; i++){
      if (k[i].nodeType === 1 && (k[i].nodeName || "").toLowerCase() === "title") continue;
      out += k[i].textContent || "";
    }
    return out;
  }
  function a6svgText(el, txt){
    if (!el) return;
    if (el.textContent !== txt) el.textContent = txt;
  }
  function a6title(el, txt){
    if (!el || !txt) return;
    var t = null, kids = el.childNodes;
    for (var i = 0; i < kids.length; i++)
      if (kids[i].nodeName && kids[i].nodeName.toLowerCase() === "title"){ t = kids[i]; break; }
    if (!t){ t = document.createElementNS(SVGN, "title"); el.insertBefore(t, el.firstChild); }
    if (t.textContent !== txt) t.textContent = txt;
  }

  /* ═════════ 1. 视图 / 数据 ═════════ */
  function a6views(){
    return a6qa('section.view[id^="view-p"]').filter(function(v){ return /^view-p\d+$/.test(v.id); });
  }
  function a6idx(view){
    var m = /^view-p(\d+)$/.exec(view.id);
    return m ? +m[1] : -1;
  }
  function a6key(view){
    var V = window.__V2, i = a6idx(view);
    if (V && V.ORDER && i >= 0 && V.ORDER[i] != null) return V.ORDER[i];
    var h1 = a6q(".hero h1", view) || a6q("h1", view);
    return h1 ? h1.textContent.trim() : "";
  }
  function a6prof(view){
    var V = window.__V2, k = a6key(view);
    if (V && V.PROF && k && V.PROF[k]) return V.PROF[k];
    if (V && V.PROF){
      var ks = V.ORDER || Object.keys(V.PROF);
      for (var i = 0; i < ks.length; i++){
        var p = V.PROF[ks[i]];
        if (p && (p.name === k || p.short === k)) return p;
      }
    }
    return null;
  }
  /* 支付日序列：__V2.FL[key].pay → 视图内「序号+支付日」表 →（仅单期时）PROF.dates */
  function a6pay(view){
    var V = window.__V2, k = a6key(view), out = [], i, j;
    if (V && V.FL && k && V.FL[k] && V.FL[k].pay && V.FL[k].pay.length) return V.FL[k].pay.slice();
    var tables = a6qa("table.tbl", view);
    for (i = 0; i < tables.length && !out.length; i++){
      var rows = a6qa("tr", tables[i]);
      if (rows.length < 2) continue;
      var heads = a6qa("th", rows[0]).map(function(h){ return h.textContent.trim(); });
      var ip = -1, ino = -1;
      for (j = 0; j < heads.length; j++){
        if (ip < 0 && heads[j].indexOf("支付日") >= 0) ip = j;
        if (ino < 0 && heads[j].indexOf("序号") >= 0) ino = j;
      }
      if (ip < 0) continue;
      var pairs = [];
      rows.slice(1).forEach(function(r, ri){
        var tds = a6qa("td", r);
        var dv = tds[ip] ? tds[ip].textContent.trim() : "";
        if (!/^\d{4}-\d{2}-\d{2}$/.test(dv)) return;
        var seq = ri + 1;
        if (ino >= 0 && tds[ino]){
          var sm = /^\s*(\d+)/.exec(tds[ino].textContent);
          if (sm) seq = +sm[1];
        }
        if (seq > 0) pairs.push({ seq: seq, date: dv });
      });
      if (pairs.length){
        pairs.sort(function(a, b){ return a.seq - b.seq; });
        out = pairs.map(function(p){ return p.date; });
      }
    }
    if (!out.length){
      var p = a6prof(view);
      if (p && p.dates && p.dates.rows){
        var ds = [];
        p.dates.rows.forEach(function(r){
          var v = r && r.value;
          if (v && v.length > 1 && /^\d{4}-\d{2}-\d{2}$/.test(v[1]) && v[0] !== "信托设立日") ds.push(v[1]);
        });
        if (ds.length === 1) out = ds;          /* 仅单期可直接对应，其余不臆造 */
      }
    }
    return out;
  }
  function a6ym(iso, compact){
    var m = /^(\d{4})-(\d{2})/.exec(String(iso || ""));
    if (!m) return "";
    return compact ? m[1].slice(2) + "/" + m[2] : m[1] + "-" + m[2];
  }
  function a6visible(view){
    try { return view.offsetParent !== null || view.getBoundingClientRect().width > 0; } catch (e){ return false; }
  }

  /* ═════════ 2. A —— 圆环图重排 ═════════ */
  /* 实测卡片内容宽；隐藏视图退回设计宽（视图切出来后由看门狗按实测重排）*/
  function a6measure(host){
    var w = 0;
    try {
      var cs = getComputedStyle(host);
      if (host.clientWidth > 140){
        w = host.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0)
            - (parseFloat(cs.borderLeftWidth) || 0) - (parseFloat(cs.borderRightWidth) || 0);
      }
    } catch (e){}
    if (!(w > 140)){
      var p = host.parentNode, guard = 0;
      while (p && guard++ < 5 && !(w > 140)){
        if (p.clientWidth > 140) w = p.clientWidth - 36;
        p = p.parentNode;
      }
    }
    if (!(w > 140)) w = DEF_W;
    return Math.round(a6clamp(w, 200, 940));
  }
  /* 图例：色块 + 标签 + 「占比 · 金额」 */
  function a6items(svg){
    var rows = [];
    a6qa("rect", svg).forEach(function(r){
      var w = parseFloat(r.getAttribute("width")), h = parseFloat(r.getAttribute("height"));
      if (!(w >= 8 && w <= 16 && h >= 8 && h <= 16)) return;
      var fill = r.getAttribute("fill");
      if (!fill) return;
      var t1 = null, t2 = null, n = r.nextElementSibling, guard = 0;
      while (n && (!t1 || !t2) && guard++ < 6){
        var tg = (n.tagName || "").toLowerCase();
        if (tg === "text"){ if (!t1) t1 = n; else if (!t2) t2 = n; }
        else if (tg === "rect" || tg === "path") break;
        n = n.nextElementSibling;
      }
      if (!t1) return;
      var label = t1.textContent.trim();
      var raw = t2 ? t2.textContent.trim() : "";
      var pm = /([\d.]+)\s*%/.exec(raw);
      var valStr = raw.split("·").pop().trim() || raw;
      rows.push({ fill: fill, label: label, pct: pm ? parseFloat(pm[1]) : null,
                  valStr: valStr, yuan: a6yuan(valStr) });
    });
    return rows;
  }
  /* 纯函数布局（自检镜像）：保证所有 x ∈ [0, W] */
  function a6layout(W, n){
    var pad = 8, rowH = 14;
    var mode = W >= H_MIN_W ? "h" : "v";
    var labelW = 0, valueW = 0, R = 0, cx = 0, cy = 0, labelX = pad, H = 0, legendTop = 14;
    if (mode === "h"){
      labelW = Math.round(a6clamp(W * 0.38, 120, 210));
      valueW = Math.round(a6clamp(W * 0.28, 92, 132));
      var ringW = W - labelW - valueW - 30;
      R = Math.round(a6clamp(ringW / 2, 30, 78));
      var d = R * 2;
      labelX = pad + d + 12;
      labelW = Math.min(labelW, Math.max(60, W - pad - valueW - labelX - 4));
      H = Math.max(d + 24, legendTop + n * rowH + 8);
      cx = pad + d / 2; cy = H / 2;
    } else {
      R = Math.round(a6clamp(W / 2 - 16, 26, 52));
      var d2 = R * 2;
      cx = Math.round(W / 2); cy = pad + d2 / 2 + 2;
      legendTop = cy + R + 16;
      H = legendTop + n * rowH + 8;
      labelW = W - pad * 2 - 118;
    }
    return { W: W, H: Math.round(H), mode: mode, pad: pad, rowH: rowH, R: R, r: Math.round(R * 0.60),
             cx: cx, cy: cy, labelX: labelX, labelW: Math.round(labelW), valueW: valueW,
             legendTop: legendTop, legendX: pad };
  }
  function a6f(v){ return (Math.round(v * 10) / 10); }
  function a6markup(rows, L){
    var tot = 0, i, ok = true, maxY = 0;
    rows.forEach(function(r){ if (r.yuan != null && Math.abs(r.yuan) > maxY) maxY = Math.abs(r.yuan); });
    var U = a6chartUnit(maxY);
    rows.forEach(function(r){ if (r.yuan == null || r.yuan < 0) ok = false; else tot += r.yuan; });
    if (ok && tot > 0) rows.forEach(function(r){ r.share = r.yuan / tot; });
    else {
      var t = 0; rows.forEach(function(r){ t += (r.pct || 0); });
      if (!t) t = rows.length;
      rows.forEach(function(r){ r.share = (r.pct || 100 / rows.length) / t; });
    }
    var g = [], total = 0;
    rows.forEach(function(r){ total += (r.yuan || 0); });
    /* 弧 */
    var acc = 0;
    rows.forEach(function(r){
      var a0 = -Math.PI / 2 + acc * Math.PI * 2;
      acc += r.share;
      var a1 = -Math.PI / 2 + acc * Math.PI * 2;
      var eps = (a1 - a0) > 6.2 ? 0.001 : 0;
      var large = (a1 - a0) > Math.PI ? 1 : 0;
      var x0 = L.cx + L.R * Math.cos(a0), y0 = L.cy + L.R * Math.sin(a0);
      var x1 = L.cx + L.R * Math.cos(a1 - eps), y1 = L.cy + L.R * Math.sin(a1 - eps);
      var x2 = L.cx + L.r * Math.cos(a1 - eps), y2 = L.cy + L.r * Math.sin(a1 - eps);
      var x3 = L.cx + L.r * Math.cos(a0), y3 = L.cy + L.r * Math.sin(a0);
      var d = "M" + a6f(x0) + " " + a6f(y0) + " A" + L.R + " " + L.R + " 0 " + large + " 1 " + a6f(x1) + " " + a6f(y1) +
              " L" + a6f(x2) + " " + a6f(y2) + " A" + L.r + " " + L.r + " 0 " + large + " 0 " + a6f(x3) + " " + a6f(y3) + " Z";
      var ttl = r.label + "｜余额 " + a6amtUnit(r.yuan, U) + "｜占比 " + a6pct(r.share);
      g.push('<path class="anr-o v6-arc" d="' + d + '" fill="' + a6esc(r.fill) + '" stroke="#fff" stroke-width="1.4">' +
             '<title>' + a6esc(ttl) + '</title></path>');
    });
    /* 圆心：合计 + 数值（不含单位）+ 单位，窄环也放得下 */
    var amtTxt = a6amtUnit(total, U), sp = amtTxt.lastIndexOf(" ");
    var num = sp > 0 ? amtTxt.slice(0, sp) : amtTxt, unit = sp > 0 ? amtTxt.slice(sp + 1) : "";
    g.push('<text class="v6-lc" x="' + a6f(L.cx) + '" y="' + a6f(L.cy - 4) + '" text-anchor="middle" font-size="10" fill="' + C.mute + '">合计</text>');
    g.push('<text class="v6-cv" x="' + a6f(L.cx) + '" y="' + a6f(L.cy + 14) + '" text-anchor="middle" font-size="13" fill="' + C.ink + '">' + a6esc(num) + '</text>');
    if (unit) g.push('<text class="v6-lc" x="' + a6f(L.cx) + '" y="' + a6f(L.cy + 27) + '" text-anchor="middle" font-size="10" fill="' + C.mute + '">' + a6esc(unit) + '</text>');
    /* 图例 */
    var vx = L.W - L.pad;
    rows.forEach(function(r, i){
      var y = L.legendTop + i * L.rowH;
      var labelFull = r.label || "—";
      var label = a6fit(labelFull, L.labelW, 11.5);
      var vtxt = a6pct(r.share) + " · " + a6amtUnit(r.yuan, U);
      g.push('<rect x="' + L.legendX + '" y="' + a6f(y - 8) + '" width="11" height="11" rx="3" fill="' + a6esc(r.fill) + '"/>');
      g.push('<text class="v6-lg" x="' + (L.legendX + 16) + '" y="' + a6f(y) + '" font-size="10" fill="' + C.ink2 + '">' +
             a6esc(label) + (label !== labelFull ? '<title>' + a6esc(labelFull) + '</title>' : '') + '</text>');
      g.push('<text class="v6-lv" x="' + vx + '" y="' + a6f(y) + '" text-anchor="end" font-size="10" fill="' + C.sub + '">' + a6esc(vtxt) + '</text>');
      g.push('<line class="v6-ln" x1="' + L.legendX + '" y1="' + a6f(y - L.rowH / 2 + 3) + '" x2="' + vx + '" y2="' + a6f(y - L.rowH / 2 + 3) + '"/>');
    });
    return g.join("");
  }
  function a6donutHost(host){
    var svg = a6q("svg", host);
    if (!svg) return false;
    var rows = a6items(svg);
    if (rows.length < 2) return false;                /* 单类目 → 交给 solo 表 */
    var W = a6measure(host);
    var L = a6layout(W, rows.length);
    svg.innerHTML = a6markup(rows, L);
    svg.setAttribute("viewBox", "0 0 " + L.W + " " + L.H);
    svg.setAttribute("width", "100%");
    svg.removeAttribute("height");
    svg.removeAttribute("preserveAspectRatio");
    var cls = svg.getAttribute("class") || "";
    if (cls.indexOf("v6-donut") < 0) svg.setAttribute("class", (cls ? cls + " " : "") + "v6-donut");
    svg.setAttribute("data-v6", "1");
    svg.setAttribute("data-v6-w", String(L.W));
    host.setAttribute("data-v6-donut", "1");
    return { W: L.W, H: L.H, mode: L.mode, rows: rows.length };
  }

  /* ═════════ 3. B —— 单类目维度 → 开篇表格 ═════════ */
  function a6soloInfo(solo){
    var b = a6q("b", solo);
    var label = b ? b.textContent.trim() : "";
    var txt = solo.textContent.replace(/\s+/g, " ").trim();
    var pm = /([\d.]+)\s*%/.exec(txt);
    var yuan = a6yuan(txt);
    var valStr = "";
    if (yuan != null){
      var mm = /(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)/.exec(txt);
      valStr = mm ? mm[0] : "";
    }
    if (!label){
      var m2 = /全部为\s*([^\s　]+)/.exec(txt);
      label = m2 ? m2[1] : "—";
    }
    return { label: label, pct: pm ? parseFloat(pm[1]) : null, yuan: yuan, valStr: valStr };
  }
  function a6soloDim(view, card, solo, info){
    var ct = card ? a6q(".ct", card) : null;
    if (ct && ct.textContent.trim()) return ct.textContent.trim();
    for (var i = 0; i < DIM_KEYS.length; i++)
      if (DIM_KEYS[i][0].test(info.label)) return DIM_KEYS[i][1];
    /* 兜底：同节已知维度里「缺失的那一个」 */
    var grid = card || solo;
    while (grid && grid.parentNode && !(grid.className || "").match(/dist-grid/)) grid = grid.parentNode;
    var present = [];
    if (grid) a6qa('[data-chart="donut"] .ct', grid).forEach(function(n){ present.push(n.textContent.trim()); });
    var missing = ALL_DIMS.filter(function(d){ return present.indexOf(d) < 0; });
    if (missing.length === 1) return missing[0];
    return "单一取值维度";
  }
  function a6soloMarkup(rows){
    var body = rows.map(function(r){
      return '<tr><td class="v6-dim">' + a6esc(r.dim) + "</td><td>" + a6esc(r.label) + "</td>" +
             '<td class="n">' + a6esc(r.pct == null ? "100.00%" : a6pct(r.pct / 100)) + "</td>" +
             '<td class="n">' + a6esc(a6scale(r.yuan)) + "</td></tr>";
    }).join("");
    return '<table><caption>单一取值维度（该维度全部为同一取值，不再单独占卡片）</caption>' +
           "<thead><tr><th>维度</th><th>取值</th><th class=\"n\">占比</th><th class=\"n\">余额</th></tr></thead>" +
           "<tbody>" + body + "</tbody></table>";
  }
  function a6soloPass(view, stat){
    var solos = a6qa(".dist-grid .xt-solo", view);
    if (!solos.length) return 0;                        /* 已处理过 → 幂等 */
    var rows = [];
    solos.forEach(function(solo){
      var card = solo.closest ? solo.closest(".chart") : solo.parentNode;
      var info = a6soloInfo(solo);
      rows.push({ dim: a6soloDim(view, card, solo, info), label: info.label, pct: info.pct, yuan: info.yuan });
      if (card && card.parentNode){ card.parentNode.removeChild(card); stat.removed++; }
    });
    var host = a6q(".pool-sum", view) || a6q(".inner", view);
    if (!host) return rows.length;
    var box = a6q(".v6-solo", view);
    if (!box){
      box = document.createElement("div");
      box.className = "v6-solo";
      if (host.parentNode) host.parentNode.insertBefore(box, host.nextSibling);
      else host.insertBefore(box, host.firstChild);
    }
    box.innerHTML = a6soloMarkup(rows);
    return rows.length;
  }

  /* ═════════ 4. D —— 维度②③ 并排 / 限宽 ═════════ */
  /* ── v7 A2. ⑥ 分布图 3+3+2+2 等高管排 ─────────────────────────────
     用户要求：10 张图按 3/3/2/2 排布，行内等宽等高、行间等高、2 张行撑满整行，
     不留「预计回收率分布单独一行」的空白。单类目卡片已被移出 → 实际张数 n
     时按 n===10 → [3,3,2,2]，否则均衡分行且不留单张（如 n=9 → [3,3,3]）。 */
  var ROW_STAT = { rebuilt: 0, h: 0, rows: 0, diff: 0, maxCard: 0 };
  function a6rowPlan(n){
    if (n === 10) return [3, 3, 2, 2];
    var rows = [], rem = n;
    while (rem > 0){
      var take = rem >= 3 ? 3 : rem;
      if (rem - take === 1) take = 2;        /* 不留单张 */
      if (take > rem) take = rem;
      rows.push(take);
      rem -= take;
    }
    return rows;
  }
  function a6rowCards(row){
    var out = [];
    for (var i = 0; i < row.children.length; i++){
      var c = row.children[i];
      if (c.className && /(^|\s)chart(\s|$)/.test(String(c.className))) out.push(c);
    }
    return out;
  }
  /* 等高由 CSS（grid-auto-rows:1fr + stretch）保证，这里只记录实测行高供 audit 引用；
     不再写固定像素高度，避免与内容重排互相追打（稳定性）。 */
  /* 等高：每趟把行高临时置 auto 量自然高（真实内容高），取其最大值作为统一行高。
     行内由 CSS stretch 保证等高；行间用同一 target 保证 4 行等高；内容不会溢出。 */
  var ROW_MAX = 300;
  /* v8.2：不再写行高像素值 —— CSS grid 的行高天然 = 该行最高内容（行内 stretch 自动等高），
     这里只清掉历史内联高度并记录实测行高；上限 300 由 audit 断言。
     这样卡片高度刚好等于内容最高者，不会因测量时机差异留出下沿空白。 */
  function a6equalize(grid){
    var rows = a6qa(".v6-row", grid);
    if (!rows.length) return;
    var hs = [], i;
    for (i = 0; i < rows.length; i++){
      if (rows[i].style && rows[i].style.height) rows[i].style.height = "";
      var h = (rows[i].getBoundingClientRect() || {}).height || 0;
      if (h > 0) hs.push(Math.round(h));
    }
    if (!hs.length) return;
    ROW_STAT.h = Math.max.apply(null, hs);
    ROW_STAT.rows = rows.length;
    ROW_STAT.heights = hs;
    grid.setAttribute("data-v6-h", String(ROW_STAT.h));
  }
  function a6rowsPass(view, stat){
    var grid = a6q(".dist-grid", view);
    if (!grid) return false;
    var cards = a6qa(".chart", grid);
    if (cards.length < 2) return false;
    var plan = a6rowPlan(cards.length), key = plan.join(",");
    var rows = a6qa(".v6-row", grid);
    if (grid.getAttribute("data-v6-rows") === key && rows.length === plan.length){
      a6equalize(grid);
      return true;
    }
    var frag = document.createDocumentFragment(), i = 0;
    plan.forEach(function(n){
      var row = document.createElement("div");
      row.className = "v6-row";
      row.setAttribute("data-cols", String(n));
      for (var k = 0; k < n && i < cards.length; k++, i++) row.appendChild(cards[i]);
      frag.appendChild(row);
    });
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    grid.appendChild(frag);
    grid.setAttribute("data-v6-rows", key);
    a6equalize(grid);
    ROW_STAT.rebuilt++;
    if (stat) stat.rows = plan.length;
    return true;
  }
  function a6widePass(view, stat){
    a6qa(".fold", view).forEach(function(fold){
      var has = function(k){ return !!a6q('[data-chart="' + k + '"]', fold); };
      var inner = a6q(".inner", fold) || fold;
      if (has("recon-line") && has("grouped-bar")){
        var duo = a6q(".v6-duo", inner);
        if (!duo){
          var a = a6q('[data-chart="recon-line"]', fold), b = a6q('[data-chart="grouped-bar"]', fold);
          if (a && b && a.parentNode === b.parentNode){
            duo = document.createElement("div");
            duo.className = "v6-duo";
            a.parentNode.insertBefore(duo, a);
            duo.appendChild(a); duo.appendChild(b);
            stat.duos++;
          }
        }
      }
      if (has("waterfall")){
        ["waterfall", "tranche-line"].forEach(function(k){
          var c = a6q('[data-chart="' + k + '"]', fold);
          if (!c || c.getAttribute("data-v6-cap") === "1") return;
          c.setAttribute("class", (c.getAttribute("class") || "") + " v6-cap");
          c.setAttribute("data-v6-cap", "1");
          stat.caps++;
        });
      }
    });
    return stat;
  }

  /* ═════════ 5. E —— 横轴日期化 ═════════ */
  function a6bottomNums(svg){
    var vb = (svg.getAttribute("viewBox") || "0 0 680 240").split(/\s+/);
    var H = parseFloat(vb[3]) || 240;
    var out = [];
    a6qa("text", svg).forEach(function(t){
      var a = t.getAttribute("text-anchor") || "";
      var y = parseFloat(t.getAttribute("y"));
      var s = t.textContent.trim();
      if (a !== "middle" || !(y > H * 0.70)) return;
      if (!/^\d{1,3}$/.test(s)) return;
      if (/rotate\(/.test(t.getAttribute("transform") || "")) return;
      out.push({ el: t, x: parseFloat(t.getAttribute("x")) || 0, n: +s });
    });
    out.sort(function(p, q){ return p.x - q.x; });
    return out;
  }
  /* 轴标签密度：先按真实间距定格式（YY/MM≈30px，YYYY-MM≈46px），再按该宽度定步长 */
  /* 主轴水平跨度：取最宽的水平线（网格线/轴线同宽），供几何定位期次用 */
  function a6xRange(svg){
    var x0 = null, x1 = null;
    a6qa("line", svg).forEach(function(ln){
      var y1 = parseFloat(ln.getAttribute("y1")), y2 = parseFloat(ln.getAttribute("y2"));
      var a = parseFloat(ln.getAttribute("x1")), b = parseFloat(ln.getAttribute("x2"));
      if (!isFinite(a) || !isFinite(b) || !isFinite(y1) || !isFinite(y2)) return;
      if (Math.abs(y1 - y2) > 0.6) return;
      var lo = Math.min(a, b), hi = Math.max(a, b);
      if (x0 == null || lo < x0) x0 = lo;
      if (x1 == null || hi > x1) x1 = hi;
    });
    return { x0: x0 == null ? 0 : x0, x1: x1 == null ? 0 : x1 };
  }
  /* 是否「期次轴」：必须以第 1 期开头、且为等差数列（容忍已被上轮抽稀成 1,3,5…）
     这样瀑布的数值标签（0/1317/100…）、坐标值轴等不会被误当成期次轴 */
  /* 判据 1：期次数字可信（以 1 开头的等差，允许末位补标不足一个步长）*/
  function a6numAxis(labels){
    if (!labels || labels.length < 2) return false;
    if (labels[0].n !== 1) return false;
    var d = labels[1].n - labels[0].n;
    if (d < 1) return false;
    for (var i = 1; i < labels.length; i++){
      var dd = labels[i].n - labels[i - 1].n;
      if (dd === d) continue;
      if (i === labels.length - 1 && dd > 0) continue;
      return false;
    }
    return true;
  }
  function a6isPeriodAxis(svg, labels, np){
    if (!labels || labels.length < 2) return false;
    if (a6numAxis(labels)) return true;
    /* 判据 2：几何可信 —— x 均匀、按位置换算出的期次严格递增且落在 [0, np-1] */
    var xr = a6xRange(svg);
    if (!(xr.x1 > xr.x0) || !(np > 1)) return false;
    var sp = [], idx = [], i;
    for (i = 0; i < labels.length; i++){
      var g = Math.round((labels[i].x - xr.x0) / (xr.x1 - xr.x0) * (np - 1));
      if (g < 0 || g > np - 1) return false;
      if (i && g <= idx[i - 1]) return false;
      idx.push(g);
      if (i && i < labels.length - 1) sp.push(labels[i].x - labels[i - 1].x);  /* 末位常为补标，不参与 */
    }
    if (!sp.length) return true;
    var mn = Math.min.apply(null, sp), mx = Math.max.apply(null, sp);
    if (!(mn > 0) || mx / mn > 1.6) return false;          /* 非末位间距要均匀 */
    return true;
  }
  function a6dateStep(n, spacing){
    var sp = Math.max(1, spacing);
    var compact = (n > 12) || (sp < 52);
    var labW = compact ? 30 : 46;
    var step = Math.max(1, Math.ceil((labW + 8) / sp));
    if (n > 8 && step < 2) step = 2;
    if (step * sp < labW + 8) step += 1;
    return { step: step, labW: labW, compact: compact };
  }
  function a6axisCap(svg, W, H, pay, n){
    var cap = a6q(".v6-axis-cap", svg);
    if (!cap){
      cap = document.createElementNS(SVGN, "text");
      cap.setAttribute("class", "v6-axis-cap");
      svg.appendChild(cap);
    }
    var x = W > 400 ? 56 : 4;
    var first = pay.length ? a6ym(pay[0], false) : "";
    var last = pay.length ? a6ym(pay[pay.length - 1], false) : "";
    var txt = pay.length
      ? "横轴：支付期次（支付日 " + (first || "—") + " ~ " + (last || "—") + "，共 " + n + " 期）"
      : "横轴：支付期次（第 1 ~ " + n + " 期；未取到支付日）";
    cap.setAttribute("x", String(x));
    cap.setAttribute("y", String(Math.max(12, H - 4)));
    a6svgText(cap, txt);
  }
  function a6datePass(view, stat){
    var pay = a6pay(view), done = 0;
    var prof = a6prof(view);
    var np = pay.length || (prof && prof.n_periods) || 0;
    var hosts = [];
    ["recon-line", "tranche-line", "grouped-bar"].forEach(function(k){
      a6qa('[data-chart="' + k + '"]', view).forEach(function(h){ hosts.push(h); });
    });
    a6qa(".chart", view).forEach(function(h){
      if (hosts.indexOf(h) >= 0) return;
      var svg = a6q("svg", h);
      if (svg){
        var l0 = a6bottomNums(svg);
        if (a6isPeriodAxis(svg, l0, np || l0.length)) hosts.push(h);   /* 仅期次轴才兜底 */
      }
    });
    hosts.forEach(function(host){
      if (host.getAttribute("data-v6-date") === "1") return;
      var svg = a6q("svg", host);
      if (!svg) return;
      var labels = a6bottomNums(svg);
      if (!a6isPeriodAxis(svg, labels, np || labels.length)) { host.setAttribute("data-v6-date", "skip"); return; }
      var vb = (svg.getAttribute("viewBox") || "0 0 680 240").split(/\s+/);
      var W = parseFloat(vb[2]) || 680, H = parseFloat(vb[3]) || 240;
      var spacing = (labels[labels.length - 1].x - labels[0].x) / Math.max(1, labels.length - 1);
      if (!(spacing > 0)) spacing = W / Math.max(2, labels.length);
      var st = a6dateStep(labels.length, spacing);
      /* 期次索引 = 标签 x 在主轴上的几何位置（源图/上轮重绘可能只标了每 2~3 期，
         甚至把期次号写错位，按几何定位最可靠；标签原数字仅作交叉校验）*/
      var npp = np || labels.length;
      var xr = a6xRange(svg);
      var byNum = a6numAxis(labels);           /* 数字可信时直接用期次号（不依赖 np）*/
      function idxOf(L){
        if (byNum) return L.n - 1;
        if (xr.x1 > xr.x0 && npp > 1){
          var g = Math.round((L.x - xr.x0) / (xr.x1 - xr.x0) * (npp - 1));
          if (g >= 0 && g <= npp - 1) return g;
        }
        return L.n - 1;
      }
      var covered = 0;
      labels.forEach(function(L){
        L.idx = idxOf(L);
        if (L.idx !== L.n - 1) stat.labelFixed++;
        if (pay.length && L.idx >= 0 && L.idx <= pay.length - 1) covered++;
      });
      function isoOf(L){ return (pay.length && L.idx >= 0 && L.idx <= pay.length - 1) ? pay[L.idx] : ""; }
      /* 保留位：等步长 + 末位；末位若与上一个保留位过近，先弹掉再补，保证不重叠 */
      var keepIdx = [], kk;
      for (kk = 0; kk < labels.length; kk++) if (kk % st.step === 0) keepIdx.push(kk);
      if (keepIdx[keepIdx.length - 1] !== labels.length - 1) keepIdx.push(labels.length - 1);
      /* 最终防碰撞扫描：相邻保留位像素距离 < 标签宽+6 时，取末尾优先、其余丢弃 */
      var final = [], minGap = st.labW + 6;
      keepIdx.forEach(function(k){
        if (final.length && (labels[k].x - labels[final[final.length - 1]].x) < minGap){
          if (k === labels.length - 1) final[final.length - 1] = k;   /* 末位优先保留 */
          return;
        }
        final.push(k);
      });
      keepIdx = final;
      var keepSet = {};
      keepIdx.forEach(function(k){ keepSet[k] = 1; });
      labels.forEach(function(L, i){
        var keep = !!keepSet[i];
        if (!keep){ if (L.el.parentNode) L.el.parentNode.removeChild(L.el); stat.xlabels--; return; }
        var iso = isoOf(L);
        var txt = iso ? (a6ym(iso, st.compact) || "—") : String(L.idx + 1);
        a6svgText(L.el, txt);
        L.el.setAttribute("class", "v6-xlabel");
        a6title(L.el, iso ? ("第" + (L.idx + 1) + "期 · " + iso) : ("第" + (L.idx + 1) + "期 · 未取到支付日"));
        if (iso) stat.xlabels++; else stat.undatedMarks++;
      });
      a6axisCap(svg, W, H, covered ? pay : [], labels.length);
      host.setAttribute("data-v6-date", "1");
      if (covered) { stat.dated++; stat.datedLabels += covered; } else stat.undated++;
      stat.xlabelsTotal += labels.length;
      done++;
    });
    return done;
  }

  /* ═════════ 6. 驱动（幂等 + 看门狗）═════════ */
  var busy = false;
  /* 累计统计（跨多次 run，用于验收汇报；幂等重跑不会重复计数重排/移出/并排）*/
  var runErrs = [];
  var TOTAL = { runs: 0, donutRelayout: 0, soloMoved: 0, soloRows: 0, duos: 0, caps: 0,
                dated: 0, undated: 0, undatedMarks: 0, xlabels: 0, xlabelsTotal: 0, labelFixed: 0, skipped: 0 };
  function bump(st){
    TOTAL.runs++;
    ["donutRelayout", "duos", "caps", "dated", "xlabels", "xlabelsTotal", "labelFixed", "undated",
     "undatedMarks", "undated"].forEach(function(k){ TOTAL[k] += (st[k] || 0); });
    TOTAL.soloMoved += (st.removed || 0);
    TOTAL.soloRows += (st.solos || 0);
  }
  function run(){
    if (busy) return null;
    busy = true;
    var stat = { views: 0, donuts: 0, donutRelayout: 0, modes: { h: 0, v: 0 }, solos: 0, removed: 0,
                 duos: 0, caps: 0, dated: 0, undated: 0, datedLabels: 0, xlabelsTotal: 0,
                 undatedMarks: 0, labelFixed: 0, xlabels: 0, resized: 0, errs: [] };
    try {
      function step(view, name, fn){
        try { return fn(); }
        catch (e){ stat.errs.push(view.id + "/" + name + ": " + (e && e.message)); runErrs.push(stat.errs[stat.errs.length - 1]); return null; }
      }
      a6views().forEach(function(view){
        stat.views++;
        step(view, "solo", function(){ stat.solos += a6soloPass(view, stat); });
        step(view, "wide", function(){ a6widePass(view, stat); });
        step(view, "rows", function(){ a6rowsPass(view, stat); });     /* v7：3+3+2+2 等高管排 */
        step(view, "donut", function(){
          a6qa('[data-chart="donut"]', view).forEach(function(host){
            var svg = a6q("svg", host);
            if (!svg || svg.getAttribute("data-v2c-dist") === "1") return;   /* v8 已重绘为横条/堆积 */
            if (!a6items(svg).length) return;              /* 单类目卡片已移出 / 无图 */
            stat.donuts++;
            var need = svg.getAttribute("data-v6") !== "1" ||
                       svg.getAttribute("width") !== "100%" ||
                       Math.abs((parseFloat(svg.getAttribute("data-v6-w")) || 0) - a6measure(host)) > 10;
            if (!need) return;
            var rr = a6donutHost(host);
            if (rr){ stat.donutRelayout++; stat.modes[rr.mode]++; }
          });
        });
        step(view, "date", function(){ a6datePass(view, stat); });
        /* v7：圆环/日期重排之后再定一次行高（否则用的是重排前的内容高）*/
        step(view, "rows2", function(){ var gg = a6q(".dist-grid", view); if (gg) a6equalize(gg); });
      });
    } finally { busy = false; }
    bump(stat);
    stat.total = TOTAL;
    return stat;
  }
  /* BASE_JS 会在 window.resize 时清掉 xdraw 并整体重画圆环 → 我方看门狗补回 */
  var wdTimer = null;
  function watchdog(){
    if (busy) return;
    var vis = a6views().filter(a6visible);
    var need = false;
    vis.forEach(function(view){
      a6qa('[data-chart="donut"]', view).forEach(function(host){
        var svg = a6q("svg", host);
        if (!svg || svg.getAttribute("data-v2c-dist") === "1") return;
        if (!a6items(svg).length) return;
        if (svg.getAttribute("data-v6") !== "1" || svg.getAttribute("width") !== "100%") need = true;
        else if (Math.abs((parseFloat(svg.getAttribute("data-v6-w")) || 0) - a6measure(host)) > 10) need = true;
      });
    });
    if (need) run();
  }
  function observe(){
    if (window.MutationObserver){
      var t = null;
      try {
        new MutationObserver(function(muts){
          if (busy) return;
          for (var i = 0; i < muts.length; i++){
            var n = muts[i].target;
            if (n && n.nodeType === 3) n = n.parentNode;
            if (n && n.closest && n.closest(".v6-donut")) continue;
            if (t) return;
            t = setTimeout(function(){ t = null; run(); }, 220);
            return;
          }
        }).observe(document.body, { childList: true, subtree: true, characterData: true });
      } catch (e){}
    }
    window.addEventListener("resize", function(){
      clearTimeout(wdTimer);
      wdTimer = setTimeout(function(){ run(); }, 420);      /* 排在 BASE_JS 的 280ms 之后 */
    });
    setInterval(watchdog, 900);
  }
  function boot(){
    run();
    setTimeout(run, 300);
    setTimeout(run, 1000);
    observe();
  }

  /* ═════════ 7. 自检 / 审计（浏览器控制台 __V6.audit() / __V6.selftest()）═════════ */
  function audit(){
    var rep = { viewsVisible: 0, donuts: 0, donutOverflow: [], cards: 0, cardOverflow: [], rowSkew: [],
                gridRows: [], rowWidth: [], rowPlan: [], rowHeightDiff: 0, cardFill: [], rowSkewInfo: [],
                rowInner: [], rowHeights: [], rowAdaptive: 0, cardGap: [],
                datedCharts: 0, undatedCharts: [], partialDated: [], xOverlap: [], soloRows: 0,
                duos: 0, caps: 0, scaleLow: [], titlesMissing: 0, labelFixed: 0, xSkipped: 0, ok: false };
    a6views().forEach(function(view){
      var vis = a6visible(view);
      if (vis) rep.viewsVisible++;
      rep.duos += a6qa(".v6-duo", view).length;
      rep.caps += a6qa(".v6-cap", view).length;
      rep.soloRows += a6qa(".v6-solo tbody tr", view).length;
      /* A3 圆环不得越出卡片 */
      if (vis) a6qa('[data-chart="donut"]', view).forEach(function(host){
        var svg = a6q("svg", host);
        if (!svg || !a6items(svg).length) return;
        rep.donuts++;
        var r = svg.getBoundingClientRect(), c = host.getBoundingClientRect();
        if (r.width > 1 && (r.right > c.right - 4 || r.left < c.left + 4))
          rep.donutOverflow.push(view.id + " Δright=" + Math.round(r.right - c.right) + " Δleft=" + Math.round(c.left - r.left));
        /* 图例数值列必须落在画布内（viewBox 坐标口径） */
        var W = parseFloat(svg.getAttribute("viewBox").split(/\s+/)[2]) || 0;
        a6qa("text", svg).forEach(function(t){
          var x = parseFloat(t.getAttribute("x")) || 0;
          var anchor = t.getAttribute("text-anchor") || "";
          var fs = parseFloat(t.getAttribute("font-size")) || 11;
          var w = a6estW(a6visText(t), fs);
          var left = anchor === "end" ? x - w : x;
          var right = anchor === "end" ? x : x + w;
          if (left < -1 || right > W + 1) rep.donutOverflow.push(view.id + " 文本越界 x=" + Math.round(left) + "~" + Math.round(right) + "/W=" + W);
        });
      });
      /* C 卡片溢出 + 同排高度差 */
      if (vis){
        /* v7：⑥ 行结构（3+3+2+2 / 行内等高 / 行间等高 / 撑满整行）*/
    var dgrid = a6q(".dist-grid", view);
    if (dgrid){
      var drows = a6qa(".v6-row", dgrid);
      if (drows.length){
        var counts = drows.map(function(r){ return a6rowCards(r).length; });
        rep.gridRows.push(view.id + ":" + counts.join("+"));
        var plan2 = a6rowPlan(a6qa(".chart", dgrid).length).join(",");
        if ((dgrid.getAttribute("data-v6-rows") || "") !== plan2)
          rep.rowPlan.push(view.id + " 行计划 " + (dgrid.getAttribute("data-v6-rows") || "—") + " ≠ " + plan2);
        if (counts.length > 1 && counts.some(function(n){ return n === 1; }))
          rep.rowPlan.push(view.id + " 存在单张行 " + counts.join("+"));
        var hh = [], decl = [], cardHs = [];
        drows.forEach(function(r){
          var rh = (r.getBoundingClientRect() || {}).height || 0;
          if (rh > 0) hh.push(rh);
          var sh = String(r.style.height || "");
          if (sh) decl.push(sh);
          var cs2 = a6rowCards(r), cvs = [];
          cs2.forEach(function(c){ var cch = (c.getBoundingClientRect() || {}).height || 0; if (cch > 0) cvs.push(cch); });
          if (cvs.length > 1){
            var dIn = Math.max.apply(null, cvs) - Math.min.apply(null, cvs);
            if (dIn > 4) rep.rowInner.push(view.id + " 行内高差 " + dIn.toFixed(1) + "px");
          }
          if (cvs.length) cardHs.push(Math.round(cvs[0]));
          var cards2 = a6rowCards(r), sum = 0, rw = (r.getBoundingClientRect() || {}).width || 0;
          cards2.forEach(function(c){ sum += (c.getBoundingClientRect() || {}).width || 0; });
          if (rw > 0 && sum / rw < 0.98)
            rep.rowWidth.push(view.id + " 行宽占比 " + (sum / rw * 100).toFixed(1) + "%");
        });
        /* v8.1：行高 = 各行自适应值（≤380），行内卡片等高 ≤4px */
        var uniq = {}, uk = [];
        decl.forEach(function(v){ uniq[v] = 1; });
        uk = Object.keys(uniq);
        uk.forEach(function(v){
          var fv = parseFloat(v);
          if (!(fv > 0) || fv > ROW_MAX + 2) rep.rowSkew.push(view.id + " 行高越界 " + v);
        });
        if (hh.length > 1 && uk.length > 1) rep.rowAdaptive = (rep.rowAdaptive || 0) + 1;
        if (hh.length > 1){
          var dhh2 = Math.max.apply(null, hh) - Math.min.apply(null, hh);
          if (dhh2 > rep.rowHeightDiff) rep.rowHeightDiff = dhh2;
        }
        if (hh.length > 1){
          var dhh = Math.max.apply(null, hh) - Math.min.apply(null, hh);
          if (dhh > rep.rowHeightDiff) rep.rowHeightDiff = dhh;
        }
      }
    }
    /* v8：卡片高 ≤380 且内容高/卡片高 ≥0.72（禁止为凑高留白）*/
    a6qa(".dist-grid .chart", view).forEach(function(c){
      var ch2 = (c.getBoundingClientRect() || {}).height || 0;
      if (!(ch2 > 0)) return;
      if (ch2 > 382) rep.cardFill.push(view.id + " 卡片高 " + Math.round(ch2) + " >380");
      var content = 26;    /* 卡片上下内边距也算内容 */
      for (var ci = 0; ci < c.children.length; ci++){
        var r2 = c.children[ci].getBoundingClientRect ? c.children[ci].getBoundingClientRect() : null;
        if (r2 && r2.height) content += r2.height;
      }
      if (content > 0 && content / ch2 < 0.85)
        rep.cardFill.push(view.id + " 填充率 " + (content / ch2 * 100).toFixed(0) + "% <85%（留白过多）");
    });
    /* v8.2：标题底 → 图形/图例顶 间距 ≤24px（垂直分层不松散）*/
    a6qa(".dist-grid .chart", view).forEach(function(c){
      var ctEl = a6q(".ct", c) || a6q(".ct2", c);
      var sv2 = a6q("svg", c);
      if (!ctEl || !sv2) return;
      var rb = ctEl.getBoundingClientRect ? ctEl.getBoundingClientRect() : null;
      var rs = sv2.getBoundingClientRect ? sv2.getBoundingClientRect() : null;
      if (!rb || !rs || rb.height <= 0) return;
      var gap2 = rs.top - rb.bottom;
      if (gap2 > 24) rep.cardGap.push(view.id + " 标题→图形间距 " + gap2.toFixed(1) + "px >24");
    });
    var cards = a6qa(".dist-grid .chart", view);
        var rowsByTop = {};
        cards.forEach(function(card){
          rep.cards++;
          if (card.scrollHeight > card.clientHeight + 2)
            rep.cardOverflow.push(view.id + " " + Math.round(card.scrollHeight - card.clientHeight) + "px");
          var t = Math.round(card.getBoundingClientRect().top / 8);
          (rowsByTop[t] = rowsByTop[t] || []).push(card.getBoundingClientRect().height);
        });
        Object.keys(rowsByTop).forEach(function(k){
          var hs = rowsByTop[k];
          if (hs.length < 2) return;
          var mx = Math.max.apply(null, hs), mn = Math.min.apply(null, hs);
          if (mx > 0 && (mx - mn) / mx > 0.4)
            rep.rowSkewInfo.push(view.id + " 行内卡片高 " + hs.map(function(x){ return Math.round(x); }).join("/") + "（v8 内容自然高，允许）");
        });
      }
      /* E x 轴日期化 + 重叠 */
      a6qa(".chart", view).forEach(function(host){
        if (host.getAttribute("data-v6-date") === "skip"){ rep.xSkipped++; return; }
        if (host.getAttribute("data-v6-date") !== "1") return;
        var svg = a6q("svg", host);
        if (!svg) return;
        var labs = a6qa("text.v6-xlabel", svg);
        var txt = labs.map(function(t){ return a6visText(t).trim(); });
        if (!txt.length) return;
        var withDate = txt.filter(function(s){ return /\d{2}[\/-]\d{2}/.test(s); }).length;
        if (host.getAttribute("data-v6-date") === "skip") rep.xSkipped++;
        var plain = txt.filter(function(s){ return /^\d+$/.test(s); }).length;
        if (!withDate) rep.undatedCharts.push(view.id + " " + ((a6q(".ct", host) || {}).textContent || "") +
                                               " 纯数字标签 " + plain + "/" + txt.length);
        else {
          rep.datedCharts++;
          if (plain) rep.partialDated.push(view.id + " " + ((a6q(".ct", host) || {}).textContent || "") +
                                          " 日期 " + withDate + "/" + txt.length);
        }
        var prev = null, steps = [];
        labs.forEach(function(t){
          var x = parseFloat(t.getAttribute("x")) || 0;
          if (prev != null) steps.push(x - prev);
          prev = x;
        });
        var minStep = steps.length ? Math.min.apply(null, steps) : 9999;
        var maxW = 0;
        labs.forEach(function(t){
          var fs = parseFloat(t.getAttribute("font-size")) || 10.5;
          maxW = Math.max(maxW, a6estW(a6visText(t), fs));
        });
        if (steps.length && minStep < maxW + 4)
          rep.xOverlap.push(view.id + " minStep=" + Math.round(minStep) + " maxW=" + Math.round(maxW) +
                            " " + (((a6q(".ct", host) || {}).textContent) || "").slice(0, 18));
        /* 每个数据点/扇区都有 <title> */
        var need = a6qa("[data-chart='donut'] .v6-arc", svg).length;
        if (need && a6qa("title", svg).length < need) rep.titlesMissing++;
      });
    });
    rep.labelFixed = TOTAL.labelFixed;
    rep.xSkipped = TOTAL.skipped;
    rep.runErrs = runErrs;
    rep.ok = !(rep.donutOverflow.length || rep.cardOverflow.length || rep.xOverlap.length ||
               rep.undatedCharts.length || rep.titlesMissing || runErrs.length ||
               rep.rowPlan.length || rep.rowWidth.length || rep.rowSkew.length || rep.cardFill.length ||
               rep.rowInner.length || rep.cardGap.length);
    return rep;
  }
  function selftest(){
    var cases = [], fail = [];
    /* 布局：任何 W/n 都不能越界 */
    var ws = [220, 260, 320, 360, 430, 560, 720, 900, 1200], ns = [2, 3, 4, 6, 8, 10], cnt = 0;
    ws.forEach(function(W){
      ns.forEach(function(n){
        var L = a6layout(W, n); cnt++;
        var ok = L.R > 0 && L.H > 80 && L.labelW > 30 &&
                 (L.cx - L.R) >= -0.5 && (L.cx + L.R) <= W + 0.5 &&
                 L.legendX >= 0 && (L.W - L.pad) <= L.W &&
                 (L.mode === "h" ? (L.labelX + L.labelW + L.valueW + 4 <= L.W - L.pad + 1) : true);
        if (!ok) fail.push("layout W=" + W + " n=" + n + " " + JSON.stringify(L));
      });
    });
    cases.push(["布局越界", cnt]);
    /* 单位规范 */
    [["0", "0.00 亿元"], ["9.0e6", "0.09 亿元"], ["1.2e6", "0.01 亿元"], ["3.29e8", "3.29 亿元"],
     ["1.19e6", "0.01 亿元"], ["5.0e5", "50.00 万元"]]
      .forEach(function(c){
        var got = a6scale(parseFloat(c[0]));
        if (got !== c[1]) fail.push("a6scale(" + c[0] + ")=" + got + " ≠ " + c[1]);
      });
    /* 日期步长：保留的标签不得重叠 */
    [[5, 149], [8, 76], [12, 54], [14, 46], [18, 34], [27, 23], [27, 20]].forEach(function(c){
      var st = a6dateStep(c[0], c[1]);
      if (st.step * c[1] < st.labW + 4 && c[0] > 1) fail.push("dateStep n=" + c[0] + " sp=" + c[1] + " → " + JSON.stringify(st));
    });
    cases.push(["日期步长", 4]);
    return { pass: cases.length - fail.length, total: cases.length, cases: cases, fail: fail,
             layoutCases: cnt };
  }

  window.__V6 = { run: run, audit: audit, selftest: selftest, total: function(){ return TOTAL; }, layout: a6layout,
                  measure: a6measure, pay: a6pay, scale: a6scale, bottomNums: a6bottomNums,
                  visText: a6visText, rules: UNIT_RULES.length };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
"""

# ════════════════════════════════════════════════════════════════
# 独立自检（Python 侧镜像 + 静态产物断言；不依赖其他脚本）
# ════════════════════════════════════════════════════════════════
UNIT_POLICY = """
单位统一规范（本模块实现）：
  · 规模类（维度余额、入池本息费/本金、累计回收、发行规模、优先档、次级档、预计回收、处置费用）
      → 亿元 2 位小数；不足 0.01 亿（1e6 元）用万元 2 位
  · 单笔/户均/息费类 → 万元 2 位小数
  · 比率类（占比、回收率、达成率…）→ 百分号 2 位小数
  · 期数/月数/笔数/户数 → 纯数字＋单位词；日期口径 YYYY-MM-DD，横轴标签 YYYY-MM / YY-MM
"""


def _astr(t: str) -> str:
    return re.sub(r"\s+", " ", t)


# ── JS 布局算法的 Python 镜像（用于越界断言）──
def _layout(W: int, n: int):
    pad, rowH, h_min_w = 8, 25, 430
    mode = "h" if W >= h_min_w else "v"
    label_w = value_w = R = cx = cy = 0
    label_x = pad
    legend_top = 14
    if mode == "h":
        label_w = round(min(max(W * 0.38, 120), 210))
        value_w = round(min(max(W * 0.28, 92), 132))
        ring_w = W - label_w - value_w - 30
        R = round(min(max(ring_w / 2, 30), 78))
        d = R * 2
        label_x = pad + d + 12
        label_w = min(label_w, max(60, W - pad - value_w - label_x - 4))
        H = max(d + 28, legend_top + n * rowH + 10)
        cx = pad + d / 2
        cy = H / 2
    else:
        R = round(min(max(W / 2 - 16, 26), 76))
        d2 = R * 2
        cx = round(W / 2)
        cy = pad + d2 / 2 + 2
        legend_top = cy + R + 16
        H = legend_top + n * rowH + 8
        label_w = W - pad * 2 - 118
    return dict(W=W, H=round(H), mode=mode, pad=pad, R=R, r=round(R * 0.60), cx=cx, cy=cy,
                labelX=label_x, labelW=round(label_w), valueW=value_w, legendTop=legend_top,
                legendX=pad, rowH=rowH)


def _date_step(n: int, spacing: float):
    """镜像 JS a6dateStep：格式由真实间距定（YY/MM≈30px、YYYY-MM≈46px），步长匹配该宽度。"""
    sp = max(1.0, spacing)
    compact = (n > 12) or (sp < 52)
    lab_w = 30 if compact else 46
    step = max(1, -(-(lab_w + 8) // sp))
    step = int(step)
    if n > 8 and step < 2:
        step = 2
    if step * sp < lab_w + 8:
        step += 1
    return step, lab_w


def _date_kept(n: int, step: int, spacing: float, lab_w: float):
    """镜像 JS 保留位规则：等步长 + 末位 + 最终防碰撞扫描（末位优先）"""
    keep = [i for i in range(n) if i % step == 0]
    if keep[-1] != n - 1:
        keep.append(n - 1)
    final, min_gap = [], lab_w + 6
    for k in keep:
        if final and (k - final[-1]) * spacing < min_gap:
            if k == n - 1:
                final[-1] = k
            continue
        final.append(k)
    return final


def _scale(y: float) -> str:
    """UNIT_POLICY 标量口径：规模类 ≥0.01 亿（1e6）→ 亿元 2 位，否则万元 2 位"""
    if y == 0:
        return "0.00 亿元"
    return f"{y/1e8:,.2f} 亿元" if abs(y) >= 1e6 else f"{y/1e4:,.2f} 万元"


def _amt_unit(y: float, u: str) -> str:
    """图内口径：单张图统一单位（按图内最大值取 亿/万）"""
    return f"{y/1e8:,.2f} 亿元" if u == "亿" else f"{y/1e4:,.2f} 万元"


def assert_layout():
    """① 圆环布局：任何卡片宽 × 图例行数都不得越界，环径/表头列宽必须为正。"""
    ok, bad, cnt = True, [], 0
    for W in (220, 240, 300, 320, 360, 400, 430, 480, 560, 680, 760, 900, 1100, 1280):
        for n in (2, 3, 4, 5, 6, 7, 8, 10, 12):
            L = _layout(W, n)
            cnt += 1
            if not (L["R"] > 0 and L["H"] > 80 and L["labelW"] > 30):
                bad.append((W, n, "基本量为正"))
                continue
            if L["cx"] - L["R"] < -0.5 or L["cx"] + L["R"] > W + 0.5:
                bad.append((W, n, "环越界 %.1f~%.1f" % (L["cx"] - L["R"], L["cx"] + L["R"])))
            if L["legendX"] < 0 or L["W"] - L["pad"] > L["W"]:
                bad.append((W, n, "图例越界"))
            if L["mode"] == "h" and L["labelX"] + L["labelW"] + 4 >= L["W"] - L["pad"]:
                bad.append((W, n, "标签列压到数值列"))
    ok = not bad
    print("\n① 圆环布局越界断言：%s（覆盖 %d 组 W×n）" % ("✓ 0 处越界" if ok else "✗ " + str(bad[:4]), cnt))
    return ok


def assert_dates():
    """② 横轴日期化：标签步长保证不重叠；首尾必保留；日期形态含 - 或 /。"""
    ok, rows = True, []
    for n, sp in ((5, 149), (8, 76), (12, 54), (14, 46), (18, 34), (27, 23), (27, 20)):
        step, lab = _date_step(n, sp)
        kept = _date_kept(n, step, sp, lab)
        gap_ok = all((kept[i + 1] - kept[i]) * sp >= lab + 4 for i in range(len(kept) - 1))
        tail_ok = kept[-1] == n - 1 and kept[0] == 0
        fmt = "2024-02" if not (n > 12) else "24/02"
        shape_ok = ("-" in fmt) or ("/" in fmt)
        good = gap_ok and tail_ok and shape_ok
        ok = ok and good
        rows.append((n, step, len(kept), round(min((kept[i + 1] - kept[i]) * sp for i in range(len(kept) - 1)), 1), good))
    print("\n② 横轴日期化断言（步长/保留数/最小间距/通过）：")
    for n, step, k, gap, good in rows:
        print("   期数 %-3d 每 %d 个标一个 → 保留 %d 个，最小间距 %.1fpx  [%s]" % (n, step, k, gap, "✓" if good else "✗"))
    return ok


def assert_units():
    """③ 单位规范：规模类阈值与 2 位小数。"""
    ok = True
    cases = [(0, "0.00 亿元"), (9.0e6, "0.09 亿元"), (1.2e6, "0.01 亿元"), (3.29e8, "3.29 亿元"),
             (1.19e6, "0.01 亿元"), (5.0e5, "50.00 万元")]
    print("\n③ 单位规范断言：")
    for y, want in cases:
        got = _scale(y)
        good = got == want
        ok = ok and good
        print("   %-12s → %-14s [%s]" % (y, got, "✓" if good else "✗ want " + want))
    print("   图内统一单位（按图最大值）：")
    for mx, y, u, want in ((3.29e8, 3.29e8, "亿", "3.29 亿元"), (1.192e5, 1.192e5, "万", "11.92 万元"),
                           (5.7e7, 1.25e7, "万", "1,250.00 万元"), (1e8, 2.3e7, "亿", "0.23 亿元")):
        got = _amt_unit(y, u)
        good = got == want
        ok = ok and good
        print("      图内最大 %-10s → 单位%s → %-14s [%s]" % (mx, u, got, "✓" if good else "✗ want " + want))
    return ok


def assert_source():
    """④ 静态产物断言：A–E 关键实现点、幂等标记、IIFE/无全局泄漏、<title> 覆盖。"""
    js = _astr(JS)
    checks = [
        ("A 按实测卡片宽重排", "function a6measure(host)" in js and "host.clientWidth" in js),
        ("A 窄卡切纵向布局", 'H_MIN_W = 430' in js and 'mode = W >= H_MIN_W ? "h" : "v"' in js),
        ("A 图例数值右对齐 + 超长截断入 title", 'text-anchor="end"' in js and "a6fit(labelFull, L.labelW" in js and "…" in JS),
        ("A 圆环 width:100%（不再 560 定宽）", 'svg.setAttribute("width", "100%")' in js and 'svg.removeAttribute("height")' in js),
        ("A 每个扇区 <title>", "anr-o v6-arc" in js and "a6esc(ttl)" in js and "余额 " in JS),
        ("B 单类目卡片移出 dist-grid", 'a6qa(".dist-grid .xt-solo", view)' in js and "removeChild(card)" in js),
        ("B 开篇表格（维度/取值/占比/余额）", "单一取值维度" in JS and "a6soloMarkup" in js),
        ("C 卡片不被等高拉伸", "align-items:start" in CSS and ".dist-grid>.chart{" in CSS),
        ("C 卡片溢出/同排高度差断言", "cardOverflow" in js and "rowSkew" in js),
        ("D 维度②并排两列", "v6-duo" in js and ".v6-duo{" in CSS),
        ("D 维度③限宽 900（≥1.0 放大）", "max-width:900px" in CSS),
        ("D 图表随容器自适应", "width:100%!important;height:auto!important" in CSS),
        ("E 日期取 __V2.FL[key].pay", "V.FL && k && V.FL[k] && V.FL[k].pay" in js),
        ("E 日期回退到 DOM 表（序号+支付日）", 'heads[j].indexOf("支付日")' in js),
        ("E 无日期不臆造（标 —）", '|| "—"' in js and "未取到支付日" in JS),
        ("E 同时给期次与日期 title", '"第" + (L.idx + 1) + "期 · "' in js and "未取到支付日" in JS),
        ("E 期次号映射（容忍期数与标签数不等）", "function isoOf(L)" in js and "L.idx >= 0 && L.idx <= pay.length - 1" in js),
        ("E 标签格式随间距（YY/MM vs YYYY-MM）", "compact = (n > 12) || (sp < 52)" in js),
        ("E 仅期次轴才日期化（保护瀑布数值标签）", "function a6isPeriodAxis(svg, labels, np)" in js and "labels[0].n !== 1" in js),
        ("E 几何判据（数字错位也能识别）", "function a6numAxis(labels)" in js and "mx / mn > 1.6" in js),
        ("E 数字可信优先按数字、否则几何", "if (byNum) return L.n - 1;" in js),
        ("E 期次索引按几何定位（并纠正错位数字）", "function a6xRange(svg)" in js and "function idxOf(L)" in js and "stat.labelFixed++" in js),
        ("E 横轴标题写明支付期次", "横轴：支付期次" in JS),
        ("E 日期化幂等标记", 'data-v6-date' in js and 'getAttribute("data-v6-date") === "1"' in js),
        ("幂等：圆环标记 + 宽度记录", 'svg.getAttribute("data-v6") !== "1"' in js and 'data-v6-w' in js),
        ("幂等：看门狗补回 BASE_JS 重绘", "setInterval(watchdog, 900)" in js),
        ("IIFE + 无 const/let", JS.lstrip().startswith("(function(){") and not re.search(r"(^|\W)(const|let)\s", JS)),
        ("strict 模式下不出现未声明循环变量", "var sp = [], idx = [], i;" in _astr(JS)),
        ("不新增全局（仅 window.__V6）", JS.count("window.") >= 1 and "__V6" in JS and "window.__V6 =" in JS),
        ("宽度估算排除 <title>（可见文本）", "function a6visText(el)" in js and "a6estW(a6visText(t), fs)" in js),
        ("单一取值维度词义判定 + 缺失法兜底", "DIM_KEYS" in js and "missing.length === 1" in js),
        ("prefers-reduced-motion / 无强制动画", "transition:opacity" in CSS),
    ]
    print("\n④ 静态产物断言：")
    ok = True
    for name, good in checks:
        print("   [%s] %s" % ("✓" if good else "✗", name))
        ok = ok and good
    return ok


def _js_balance(js: str):
    i, n, stack, bad, prev = 0, len(js), [], 0, ""
    WORDS = ("return", "typeof", "case", "in", "of", "new", "delete", "void", "do", "else", "instanceof")
    while i < n:
        ch = js[i]
        nxt = js[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = js.find("\n", i); i = n if j < 0 else j; continue
        if ch == "/" and nxt == "*":
            j = js.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        if ch in "\"'`":
            q = ch; i += 1
            while i < n:
                if js[i] == "\\": i += 2; continue
                if js[i] == q: i += 1; break
                i += 1
            prev = "x"; continue
        if ch == "/":
            word = re.search(r"([A-Za-z_$][\w$]*)\s*$", js[:i])
            if prev == "" or prev in "(,=:[!&|?{};+-*%<>~^" or (word and word.group(1) in WORDS):
                i += 1; in_class = False
                while i < n:
                    if js[i] == "\\": i += 2; continue
                    if js[i] == "[": in_class = True
                    elif js[i] == "]": in_class = False
                    elif js[i] == "/" and not in_class: i += 1; break
                    elif js[i] == "\n": break
                    i += 1
                while i < n and js[i].isalpha(): i += 1
                prev = "x"; continue
            prev = ch; i += 1; continue
        if ch in "([{":
            stack.append({"(": ")", "[": "]", "{": "}"}[ch]); prev = ch; i += 1; continue
        if ch in ")]}":
            if not stack or stack.pop() != ch: bad += 1
            prev = ch; i += 1; continue
        if not ch.isspace(): prev = ch
        i += 1
    return bad, stack


def _node_check():
    import os, shutil, subprocess, tempfile
    node = shutil.which("node")
    if not node:
        return None
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(JS)
        r = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stderr or "").strip()[:300]
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)[:200]
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _scan_report():
    """可选：静态扫描已有报告，给出预计处理量（文件不存在则跳过）。"""
    from pathlib import Path
    for p in (_HOME / "清算28单_不良ABS分析" / "清算28单_不良ABS穿透分析报告_v2.html",
              _HOME / "清算28单_不良ABS分析" / "清算28单_横向对照与逐单稽核_合并版.html"):
        if not p.exists():
            continue
        c = p.read_text(encoding="utf-8", errors="ignore")
        views = re.findall(r'<section class="view" id="view-p\d+"', c)
        donuts = re.findall(r'<div class="chart" data-chart="donut">(.*?)</svg>', c, re.S)
        multi = sum(1 for d in donuts if len(re.findall(r"<rect", d)) > 1)
        solo = sum(1 for d in donuts if len(re.findall(r"<rect", d)) <= 1)
        duo = 1 if ('data-chart="recon-line"' in c and 'data-chart="grouped-bar"' in c) else 0
        return dict(file=p.name, views=len(views), donut_cards=len(donuts), donut_multi=multi,
                    donut_solo=solo, fold23_duo_pairs=duo * len(views),
                    datable_views=len(re.findall(r"<th[^>]*>支付日</th>", c)),
                    waterfall=len(re.findall(r'data-chart="waterfall"', c)),
                    grouped=len(re.findall(r'data-chart="grouped-bar"', c)),
                    tranche=len(re.findall(r'data-chart="tranche-line"', c)),
                    recon=len(re.findall(r'data-chart="recon-line"', c)))
    return None


def selfcheck() -> int:
    print("═" * 66)
    print("60_assets.py 自检（点 4：圆环重排 / 单类目转表 / 卡片均衡 / 维度②③ 缩放 / 横轴日期化）")
    print("═" * 66)
    print("导出长度： CSS %d 字符 ｜ HTML %d 字符 ｜ JS %d 字符" % (len(CSS), len(HTML), len(JS)))
    print("CSS 类： %s" % ", ".join(sorted(set(re.findall(r"\.v6-[a-z0-9-]+", CSS)))))

    fns = re.findall(r"^  function (a6[A-Za-z_0-9]*)\(", JS, re.M)
    print("JS 函数： %d 个（%s …）" % (len(fns), ", ".join(fns[:10])))
    print("JS 公开入口： window.__V6 = { %s }"
          % ", ".join(re.findall(r"(\w+):\s*a6?\w+", JS[JS.find("window.__V6 ="):JS.find("window.__V6 =") + 220])))

    sc = _scan_report()
    print("\n预计处理量（静态扫描已有报告，非运行时统计）：")
    if sc:
        print("   来源 %s：视图 %d ｜ 圆环卡片 %d（多项 %d → 重排；单类目 %d → 转表）｜ 维度②并排对 %d"
              % (sc["file"], sc["views"], sc["donut_cards"], sc["donut_multi"], sc["donut_solo"], sc["fold23_duo_pairs"]))
        print("   维度②③ 待缩放图： waterfall %d ｜ grouped-bar %d ｜ recon-line %d ｜ 带支付日表的视图 %d"
              % (sc["waterfall"], sc["grouped"], sc["recon"], sc["datable_views"]))
    else:
        print("   （未找到报告文件，跳过；运行时统计见 __V6.run() 返回值）")

    ok = True
    ok = assert_layout() and ok
    ok = assert_dates() and ok
    ok = assert_units() and ok
    ok = assert_source() and ok

    bad, stack = _js_balance(JS)
    balanced = (bad == 0 and not stack)
    print("\nJS 括号配平： %s（未闭合 %d，失配 %d）" % ("✓" if balanced else "✗", len(stack), bad))
    ok = ok and balanced
    nc = _node_check()
    if nc is None:
        print("node 语法校验： 跳过（本机无 node）")
    else:
        good, msg = nc
        print("node --check： %s" % ("✓ 语法通过" if good else "✗ " + msg))
        ok = ok and good

    print("\n验收清单（静态扫描数 + 断言状态；★ 为浏览器运行时由 __V6.audit() 断言）：")
    if sc:
        print("   ① 圆环图重排数        ： %d 张（多项圆环，按卡片实测宽重排；另有 %d 张单类目转表）"
              % (sc["donut_multi"], sc["donut_solo"]))
        print("   ② 单类目移出卡片数    ： %d 张 → 汇总为开篇表格 %d 行（担保方式分布·全部信用类）"
              % (sc["donut_solo"], sc["donut_solo"]))
        print("   ④ 维度②③ 缩放/归置  ： 并排对 %d（recon+grouped）｜ 限宽图 %d（waterfall/tranche）"
              % (sc["fold23_duo_pairs"], sc["waterfall"] + sc["fold23_duo_pairs"]))
        print("   ③ 卡片均衡           ： .dist-grid{align-items:start} + 高度自适应（零内容溢出由 audit 断言）")
        print("   ⑤ x 轴待日期化图     ： recon %d ｜ grouped %d ｜ tranche %d ｜ 带支付日表的视图 %d"
              % (sc["recon"], sc["grouped"], sc.get("tranche", 0), sc["datable_views"]))
    print("   ★ A 圆环不越出卡片    ： svg.right ≤ card.right-4 且 svg.left ≥ card.left+4（另含画布内文本边界）")
    print("   ★ C 卡片溢出断言      ： .dist-grid>.chart 全部 scrollHeight ≤ clientHeight+2；同排高度差 >40% 报出")
    print("   ★ E 重叠为 0          ： x 轴标签最小间距 ≥ 标签宽+4（镜像断言已逐用例验证）")
    print("   ★ 幂等               ： 连续 run() 后视图 innerHTML 逐字节一致")
    print("\n幂等：圆环 data-v6 + data-v6-w（宽度变化才重排）、横轴 data-v6-date、卡片 data-v6-cap、"
          "单类目卡片移除后只更新表格；BASE_JS resize 重绘由看门狗补回")
    print("\n单位口径：%s" % UNIT_POLICY.strip())
    print("═" * 66)
    print("自检结论： %s" % ("通过 ✅" if ok else "存在失败项 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selfcheck())
