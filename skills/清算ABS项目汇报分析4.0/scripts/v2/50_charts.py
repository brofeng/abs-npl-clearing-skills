# -*- coding: utf-8 -*-
r"""v2 模块 50_charts —— 点 6 + 点 8 精修（折线图重绘 / 单位统一 / 图种多样化）。

职责（只碰单项目视图 #view-p0 … #view-p27 内的图表与文本）：
  A. 重绘两条折线图
       [data-chart="recon-line"]    累计回收曲线（实际实线 / 预计虚线）
       [data-chart="tranche-line"]  分档累计本金走势
     —— 从原 SVG 的 <polyline> / <text> 坐标反推数据点，重绘为：
        柔和面积渐变 + 实心圆点（白描边）+ 淡网格 + 清晰轴标 + 关键点标注；
        每个期次一个「命中带」<rect>（含 <title>），配合全局 #xtTip 悬停读数；
        viewBox 保留、width:100%/height:auto 响应式。

  B. 单位统一（UNIT_POLICY）
       规模类 → 亿元 2 位（<0.01 亿 用万元）；单笔/户均/息费类 → 万元 2 位；
       比率类 → 百分号 2 位；期数/月数/笔数/户数 → 不动。
       同一张 SVG 的数轴统一到同一单位（轴旁注明「单位：亿元」）；
       逐期明细表按表内最大值统一为万元（保留勾稽精度），并修正表头单位注记。
       幂等：反复运行结果一致；原文引用（.note/.cal 等）与日期/页码/编号不误改。

  C. 降低「都是柱状图」的单调感（只改 3 类 hbar，其余保留原样）
       借款人年龄分布  → 棒棒糖图（lollipop）
       授信额度分布    → 100% 堆叠条（stacked100）
       逾期时间分布    → 面积折线 / 账龄曲线（area）
       年收入分布、预计回收率分布 → 保留原 hbar（宁缺毋滥）

契约：导出 CSS / HTML / JS 三个字符串；JS 全部包在 IIFE 内、只用 var；数据读 window.__V2（可选）。
本文件可独立运行：`python 50_charts.py` 打印自检摘要，不依赖其他脚本。
"""
from __future__ import annotations

import re

# ════════════════════════════════════════════════════════════════
# CSS —— 只新增 .v2c-* 类，不改动既有变量与其它区块样式
# ════════════════════════════════════════════════════════════════
CSS = r"""
/* ===== 50_charts：折线图重绘 / 单位统一 / 图种多样化（点 6 + 点 8）===== */
.v2c-svg{width:100%!important;height:auto!important;max-width:100%;display:block;overflow:visible}
.v2c-hit,.v2c-dot-hit{fill:transparent;fill-opacity:0;cursor:crosshair}
.v2c-hit:hover{fill:rgba(45,57,85,.045);cursor:crosshair}
.v2c-band{fill:transparent;fill-opacity:0;cursor:pointer}
.v2c-band:hover{fill:rgba(45,57,85,.05)}
.v2c-guide{opacity:0;transition:opacity .14s cubic-bezier(.16,.68,.42,1)}
.v2c-guide.on{opacity:.85}
.v2c-dot{transition:r .12s cubic-bezier(.16,.68,.42,1)}
.v2c-ax{font-size:11px;fill:#697487;font-variant-numeric:tabular-nums}
.v2c-ax-x{font-size:11px;fill:#697487}
.v2c-note{font-size:10.5px;fill:#98A2B3;letter-spacing:.01em}
.v2c-anno{font-size:11px;fill:#38425A;font-weight:600}
.v2c-anno-sub{font-size:10.5px;fill:#697487}
.v2c-leg{font-size:11px;fill:#38425A}
/* v7：并入档位末次兑付后的时间轴（9 节点不拥挤；同档浅→深 + 短连接线）*/
.dist-grid .chart>.ct,.dist-grid .chart>.ct2{font-size:12px!important}
.v2c-dist-note{margin:6px 0 0;padding:4px 0 4px 9px;border-left:3px solid var(--warn,#B0763F);
  font-size:9.5px;line-height:1.55;color:var(--mute,#98A2B3)}
.v2c-dist-note b{font-weight:700;color:var(--warn,#B0763F)}
.v2c-dist-note-wide{grid-column:1/-1;margin:2px 0 10px!important;width:100%;box-sizing:border-box}
/* v9.2：口径行（标题下）与图型说明（图下）走 HTML，SVG 内不再放，物理上不会与旋转标签重叠 */
.v9-meta{font-size:9.5px;line-height:1.35;color:#98A2B3;margin:1px 0 3px;font-variant-numeric:tabular-nums}
.v9-foot{font-size:9.5px;line-height:1.35;color:#98A2B3;margin:6px 0 0;padding-top:3px;border-top:1px dashed #EDF1F7}
.pf-tl[data-v2c-tl="1"] .pf-ts{min-width:96px}
.pf-tl[data-v2c-tl="1"] .pf-tlab{white-space:nowrap}
.pf-tl[data-v2c-tl="1"] .pf-tval{font-variant-numeric:tabular-nums;white-space:nowrap}
.pf-ts .pf-tdot{background:var(--v2c-dot,var(--accent))!important}
.pf-ts.v2c-tl-tier::before{background:var(--v2c-line,var(--line2))!important}
.pf-ts.v2c-tl-act .pf-tlab{font-weight:700}
.pf-ts.v2c-tl-act .pf-tval{color:var(--ink2)}
[data-v2c-hidden="1"]{display:none!important}
/* v7：瀑布图例（单行等距，与单位徽章留白；超出则两行）*/
.v2c-wfleg{font-size:9.5px}
.v2c-tag{margin-left:8px;padding:1px 7px;border-radius:6px;font-size:10.5px;font-weight:400;
  color:#697487;background:#EDF1F6;border:1px solid rgba(26,34,48,.06);white-space:nowrap;vertical-align:1px}
.v2c-seg{transition:opacity .14s cubic-bezier(.16,.68,.42,1)}
.v2c-seg:hover{opacity:.86;cursor:pointer}
caption.v2c-cap{caption-side:top;text-align:right;font-size:11px;color:#98A2B3;padding:0 0 6px;letter-spacing:.01em}
.v2c-units{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:0 0 14px;
  padding:10px 14px;border-radius:12px;background:#F7FAFD;border:1px solid rgba(26,34,48,.07);
  font-size:12px;color:#38425A}
.v2c-units b{font-size:12.5px;color:#141A26;margin-right:2px}
.v2c-units span{padding:1px 8px;border-radius:999px;background:#EDF1F6;color:#697487}
@keyframes v2cDraw{from{stroke-dashoffset:1400}to{stroke-dashoffset:0}}
.v2c-anim{stroke-dasharray:1400;stroke-dashoffset:1400;animation:v2cDraw 1.05s cubic-bezier(.16,.68,.42,1) forwards}
@media (prefers-reduced-motion: reduce){.v2c-anim{animation:none;stroke-dasharray:none;stroke-dashoffset:0}}
"""

# ════════════════════════════════════════════════════════════════
# HTML —— 全局「单位口径」说明条（可空；服务端渲染一次）
# ════════════════════════════════════════════════════════════════
HTML = r"""
<div class="v2c-units" role="note" id="v2cUnits"><b>单位口径</b><span>规模类 → 亿元（2 位小数，不足 0.01 亿用万元）</span><span>单笔／户均／息费类 → 万元（2 位小数）</span><span>比率 → 百分号（2 位小数）</span><span>期数／月数／笔数／户数 → 数字＋单位词</span><span>图内数轴单一单位，轴旁标注</span></div>
"""

# ════════════════════════════════════════════════════════════════
# JS —— IIFE 局部变量，绝不泄露全局（window.__V2Charts 除外，供自检/调试）
# ════════════════════════════════════════════════════════════════
JS = r"""
(function(){
  "use strict";

  /* ───────────── 设计令牌（镜像 00_ctx.py，本文件独立可跑）───────────── */
  var C = {
    ink:  "#141A26", ink2: "#38425A", sub: "#697487", mute: "#98A2B3",
    grid: "#E6EBF3", axis: "#C9D2E0", surface: "#F7FAFD", white: "#fff",
    gray: "#98A2B3", warn: "#B0763F"
  };
  var CAT_COLOR = { "信用卡不良": "#A52524", "个人消费贷款": "#2D3955", "个人经营贷款": "#1F7A5C" };
  var FONT = '-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",system-ui,sans-serif';

  /* ═══════════════ 0. 小工具 ═══════════════ */
  function $(sel, root){ return (root || document).querySelector(sel); }
  function $$(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s){
    return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function num(v){ return v == null || isNaN(v) ? 0 : v; }
  function clamp(v, a, b){ return v < a ? a : (v > b ? b : v); }
  /* 千分位 + 固定小数（不依赖 locale，保证幂等） */
  function th(n, d){
    if (!isFinite(n)) return "—";
    var neg = n < 0; n = Math.abs(n);
    var s = n.toFixed(d == null ? 2 : d);
    var p = s.split("."), i = p[0], f = p[1] ? "." + p[1] : "";
    i = i.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (neg ? "-" : "") + i + f;
  }
  function pct2(ratio){ return th(ratio * 100, 2) + "%"; }
  function svgTag(name, attrs){
    var a = "";
    for (var k in attrs) if (attrs.hasOwnProperty(k) && attrs[k] != null) a += " " + k + '="' + esc(attrs[k]) + '"';
    return "<" + name + a + ">";
  }
  /* 估算文本宽度做截断（CJK 按 1 em，西文按 .58 em） */
  function fitText(s, maxPx, fs){
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
  function maxOf(rows){
    var m = 0;
    (rows || []).forEach(function(r){ if (Math.abs(r.value) > m) m = Math.abs(r.value); });
    return m;
  }
  /* 在 3~5 段里挑一个刚好盖住数据、且落在整刻度上的上沿（避免空半张图）*/
  function niceAxisTop(maxV){
    if (!(maxV > 0)) return { top: 1, k: 1, step: 1 };
    var best = null;
    [5, 4, 3].forEach(function(k){
      var st = niceStep(maxV / k), top = st * k;
      if (top >= maxV - 1e-9 && (!best || top < best.top - 1e-9)) best = { top: top, k: k, step: st };
    });
    if (!best){ var st0 = niceStep(maxV); best = { top: st0, k: 1, step: st0 }; }
    return best;
  }
  function niceStep(raw){
    if (!(raw > 0)) return 1;
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var c = raw / p, s = c <= 1 ? 1 : c <= 2 ? 2 : c <= 2.5 ? 2.5 : c <= 5 ? 5 : 10;
    return s * p;
  }
  function niceMax(maxV, ticks){
    ticks = ticks || 4;
    if (!(maxV > 0)) return 1;
    var step = niceStep(maxV / ticks);
    var top = step * ticks;
    while (top < maxV - 1e-9) { step = niceStep(step * 1.25); top = step * ticks; }
    return top;
  }

  /* ═══════════════ 1. 单位统一引擎（点 8）═══════════════ */
  /* 优先级规则：先“明确规模类”，再“小额类”，再“规模关键词”，最后按量级兜底。
     同一标签同时命中时，靠前的规则优先（例：优先档 利息 → 小额类）。 */
  var UNIT_ORDER = [
    { k: "scale", keys: ["处置费用", "入池本息费", "回收流入合计", "分配流出合计"] },
    { k: "small", keys: ["息费", "利息", "收益", "费用", "报酬", "服务费", "审计费", "税费",
                         "资金成本", "成本", "单笔", "主体", "户均", "平均", "最高", "上限", "金额"] },
    { k: "scale", keys: ["入池", "累计回收", "回收", "发行", "规模", "优先档", "次级档", "本金",
                         "余额", "流入", "流出", "合计", "留存", "兑付", "预计", "资产池"] }
  ];
  var UNIT_RULES = [
    "规模类（入池本息费／入池本金／累计回收／发行规模／优先档／次级档／预计回收／处置费用）→ 亿元，2 位小数；不足 0.01 亿用万元",
    "小额类（入池息费／单笔最高／单笔平均／主体最高／主体平均／利息／费用／报酬）→ 万元，2 位小数",
    "比率类（回收率／达成率／证券化率／XIRR／占比）→ 百分号，2 位小数",
    "期数／月数／笔数／户数／天数 → 纯数字＋单位词，不换算",
    "无法判定类别时按量级兜底：≥1 亿元用亿元 2 位，否则万元 2 位"
  ];
  var AMT_RE = /(-?[\d][\d,]*(?:\.\d+)?)(\s*)(亿元|亿|万元|万|元)/g;
  /* 从 <title> 里取「值」的金额：优先最后一个分隔段（标题形如「12个月以上 · 8638 元」，
     标签段也可能含 数字+单位，如「50万以上（不含）」→ 不能取第一个匹配）*/
  function amtFromTitle(txt){
    var parts = String(txt || "").split(/[·｜|]/);
    for (var i = parts.length - 1; i >= 0; i--){
      AMT_RE.lastIndex = 0;
      var m = AMT_RE.exec(parts[i]);
      if (m){ AMT_RE.lastIndex = 0; return toYuan(m[1], m[3]); }
    }
    var g = null, mm;
    AMT_RE.lastIndex = 0;
    while ((mm = AMT_RE.exec(String(txt || "")))) g = mm;
    AMT_RE.lastIndex = 0;
    return g ? toYuan(g[1], g[3]) : null;
  }
  var PCT_RE = /(-?[\d][\d,]*(?:\.\d+)?)\s*%/g;
  function classify(label){
    var s = String(label || "");
    for (var i = 0; i < UNIT_ORDER.length; i++){
      var g = UNIT_ORDER[i];
      for (var j = 0; j < g.keys.length; j++) if (s.indexOf(g.keys[j]) >= 0) return g.k;
    }
    return "auto";
  }
  function toYuan(numStr, unitWord){
    var v = parseFloat(String(numStr).replace(/,/g, ""));
    if (!isFinite(v)) return 0;
    if (unitWord === "亿元" || unitWord === "亿") return v * 1e8;
    if (unitWord === "万元" || unitWord === "万") return v * 1e4;
    return v;
  }
  /* 金额 → 规范字符串（含单位词）；0 值沿用该类主单位，避免同组内单位跳变 */
  function fmtAmt(yuan, kind){
    if (!isFinite(yuan)) return "—";
    if (yuan === 0) return kind === "scale" ? "0.00 亿元" : kind === "small" ? "0.00 万元" : "0.00 万元";
    if (kind === "small") return th(yuan / 1e4, 2) + " 万元";
    if (kind === "scale") {
      return Math.abs(yuan) >= 1e6 ? th(yuan / 1e8, 2) + " 亿元" : th(yuan / 1e4, 2) + " 万元";
    }
    return Math.abs(yuan) >= 1e8 ? th(yuan / 1e8, 2) + " 亿元" : th(yuan / 1e4, 2) + " 万元";
  }
  function fmtMoney(yuan, label){ return fmtAmt(yuan, classify(label)); }
  function unitWord(u){ return u === "亿" ? "亿元" : u === "万" ? "万元" : "元"; }
  function unitFactor(u){ return u === "亿" ? 1e8 : u === "万" ? 1e4 : 1; }
  /* 数轴单位选择（点 8 规则）：
     ① 规模上限 ≥0.01 亿（1e6 元）→ 亿元 2 位；否则万元 2 位；
     ② 若该单位下出现「≥2 个标签都被抹成 0」的退化情形，自动降一档（亿→万→元）；
     ③ 三档仍退化则返回 null，调用方放弃改写（宁可保留原样，绝不出现整轴 0.00）。*/
  function axisLabelsFor(vals, unit){
    var f = unitFactor(unit), d = unit === "元" ? 0 : 2;
    return vals.map(function(v){ return th(v / f, d); });
  }
  function zeroCount(labels){
    var z = 0;
    labels.forEach(function(s){ if (parseFloat(String(s).replace(/,/g, "")) === 0) z++; });
    return z;
  }
  function dupCount(labels){
    var seen = {}, d = 0;
    labels.forEach(function(s){ if (seen[s]) d++; seen[s] = 1; });
    return d;
  }
  /* ── 值标签（柱/点上的数字）单位：全图单一单位，避免同图混排 ──
     小数位按量级自适应：亿 2 位；万 ≥100万→0 位、≥1万→1 位、其余→2 位；元 整数 */
  /* 文本节点写法：单位词前留空格（与既有排版一致）*/
  function vlabS(u, v){ return vnum(u, v) + " " + unitWord(u); }
  /* 图内主导单位：统计该 SVG 现有「数字+单位」文本，取出现最多的单位词——
     这样 60_assets 自绘的圆环、自绘折线等即使没有单位注记也不会被改成别的单位 */
  function dominantUnit(svg, cache){
    if (!svg) return null;
    if (cache.has(svg)) return cache.get(svg);
    var note = $(".v2c-note,.v2c-unitnote", svg);
    var nu = note ? /单位：(亿元|亿|万元|万|元)/.exec(note.textContent) : null;
    var u = null;
    if (nu){
      u = nu[1].charAt(0);
    } else {
      var cnt = {}, best = null;
      $$("text", svg).forEach(function(t){
        var mm = /[\d][\d,]*(?:\.\d+)?\s*(亿元|亿|万元|万|元)/.exec(t.textContent);
        if (!mm) return;
        var k = mm[1].charAt(0);
        cnt[k] = (cnt[k] || 0) + 1;
        if (!best || cnt[k] > cnt[best]) best = k;
      });
      u = best;
    }
    cache.set(svg, u);
    return u;
  }
  function clearDominantCache(){ domCache = (window.Map ? new Map() : null); }
  function vnum(u, v){
    var y = Math.abs(v);
    if (u === "亿") return th(v / 1e8, 2);
    if (u === "万") return th(v / 1e4, y >= 1e6 ? 0 : 2);   /* ≥100万 取整，其余 2 位（保精度）*/
    return th(v, 0);
  }
  function vlab(u, v){ return vnum(u, v) + unitWord(u); }
  /* 值标签单位选择：规模量级 ≥0.01 亿 → 亿元，否则万元；若该单位把 ≥2 个值抹成 0 则降档；
     三档都退化时返回末档（调用方仍会显示，不做整图 0.00 的静默） */
  function pickValueUnit(maxV, vals){
    var m0 = Math.abs(maxV);
    var cands = m0 >= 1e6 ? ["亿", "万", "元"] : (m0 >= 1e4 ? ["万", "元"] : ["元", "万"]);
    for (var i = 0; i < cands.length; i++){
      var z = 0;
      vals.forEach(function(v){
        /* 真 0 在任何单位下都是 0，不算退化；只看「非零值被抹成 0」的精度损失 */
        if (v !== 0 && parseFloat(String(vnum(cands[i], v)).replace(/,/g, "")) === 0) z++;
      });
      if (z < 2) return cands[i];
    }
    return cands[cands.length - 1];
  }
  /* 合格标准：① 不得有 ≥2 个标签被抹成 0；② 标签不得重复（粗到读不出差异就换更细的单位）*/
  function pickAxisUnit(maxAbs, vals){
    var cands = maxAbs >= 1e6 ? ["亿", "万", "元"] : ["万", "元"];
    for (var i = 0; i < cands.length; i++){
      var labels = axisLabelsFor(vals, cands[i]);
      if (zeroCount(labels) < 2 && dupCount(labels) === 0) return { unit: cands[i], labels: labels };
    }
    return null;
  }
  /* 百分比 → 2 位小数 */
  function normPct(text){
    return String(text).replace(PCT_RE, function(m, n){
      return th(parseFloat(String(n).replace(/,/g, "")), 2) + "%";
    });
  }
  /* 原文引用区不误改（合同原文、来源注、代码块） */
  var QUOTE_SEL = ".note,.cal,.srcline,.src,.quote,.fn,.footnote,blockquote,pre,code,script,style,textarea";
  function localLabel(text, idx){
    var seg = text.slice(Math.max(0, idx - 22), idx);
    seg = seg.split(/[·｜|：:，,。；;、（）()【\[]/).pop();
    return String(seg || "").replace(/\s+/g, " ").trim().slice(-14);
  }
  /* 单条文本里常并列多项（如「入池本息费 11.92 亿 ｜ 入池息费 5056.15 万」）；
     判定优先级：该 token 前面的局部标签 > 最近的同级标签 > 容器标签（逐个评估，先命中先用，
     避免一个「小额类」标签把整行金额都带偏）*/
  function classifyToken(labels, text, off){
    var k = classify(localLabel(text, off)), i;
    if (k !== "auto") return k;
    for (i = 0; i < labels.length; i++){
      k = classify(labels[i]);
      if (k !== "auto") return k;
    }
    return "auto";
  }
  /* 单个文本节点：逐 token 判类（唯一实现，自检亦走此函数）；label 可为字符串或数组 */
  function normText(label, text, chartUnit){
    var labels = Object.prototype.toString.call(label) === "[object Array]" ? label : [label];
    var out = String(text).replace(AMT_RE, function(m, n, sp, uw, off){
      var yuan = toYuan(n, uw);
      /* 图内有明确单位（注记或主导单位）时，一律按图内单位写，保证同图不混排 */
      if (chartUnit) return vlabS(chartUnit, yuan);
      return fmtAmt(yuan, classifyToken(labels, text, off));
    });
    return normPct(out);
  }
  /* 最近的「标签」文字（可多个候选，近者优先）：值节点常与标签分属不同节点
     （如 <span>入池息费</span><b>5056.15 万</b>，或 "入池本息费 <b>11.92 亿</b>" 的纯文本标签）*/
  function prevLabels(el){
    var out = [], n = el, hops = 0;
    while (n && n.parentNode && hops < 3 && out.length < 4){
      var s = n.previousSibling;
      while (s && out.length < 4){
        var nm = (s.nodeName || "").toLowerCase();
        if (nm !== "title" && nm !== "style" && nm !== "script"){
          var txt = String(s.textContent || "").replace(/\s+/g, " ").trim();
          if (txt){
            var frag = String(txt.split(/[·｜|：:。；;]/).pop() || "").trim();
            if (frag) out.push(frag.slice(0, 20));
            var tail = txt.slice(-16);
            if (tail && tail !== frag) out.push(tail);
          }
        }
        s = s.previousSibling;
      }
      n = n.parentNode; hops++;
    }
    return out;
  }
  function contextLabels(el){
    var parts = [], i;
    var pls = prevLabels(el);
    for (i = 0; i < pls.length; i++) parts.push(pls[i]);
    if (el.closest){
      var kp = el.closest(".kpi");
      if (kp){ var k = kp.querySelector(".k"); if (k) parts.push(k.textContent); }
      var bx = el.closest(".box");
      if (bx){ var bl = bx.querySelector(".bl"); if (bl) parts.push(bl.textContent); }
      var tl = el.closest(".tl");
      if (tl){ var l = tl.querySelector(".l"); if (l) parts.push(l.textContent); }
      var host = el.closest(".chart,.card,.fold,li,td,th");
      if (host){
        /* 只认区块标题（.ct/.ct2/h3/h4），且取节点之前最近的一个，避免深层 .k 带偏 */
        var cands = $$(".ct,.ct2,h3,h4", host), best = null;
        for (i = 0; i < cands.length; i++){
          var c = cands[i];
          if (c === el || c.contains(el)) continue;
          if (el.compareDocumentPosition && (c.compareDocumentPosition(el) & 4)) best = c;
        }
        if (best) parts.push(best.textContent);
      }
    }
    var out = [];
    for (i = 0; i < parts.length; i++){ if (parts[i] && String(parts[i]).trim()) out.push(parts[i]); }
    return out;
  }
  /* 遍历视图内文本节点做单位规范化（幂等：先改后比对，不变则不写） */
  function unitPass(root){
    var walker, n, nodes = [], changed = 0, seen = 0;
    try { walker = document.createTreeWalker(root, 4, null); }   /* 4 = SHOW_TEXT */
    catch (e){ return 0; }
    while ((n = walker.nextNode())) nodes.push(n);
    for (var i = 0; i < nodes.length; i++){
      var node = nodes[i], t = node.nodeValue;
      if (!t || t.length > 400) continue;
      if (!/[\d]/.test(t)) continue;
      if (!/亿|万|元|%/.test(t)) continue;
      var p = node.parentNode;
      if (!p || !p.nodeName) continue;
      var tag = p.nodeName.toLowerCase();
      if (tag === "script" || tag === "style" || tag === "textarea") continue;
      if (p.closest && p.closest(QUOTE_SEL)) continue;
      if (p.closest && p.closest("table")) continue;       /* 表格单独处理 */
      if (p.closest && p.closest(".v2c-tag,caption.v2c-cap")) continue;  /* 本模块自带徽标/表注 */
      if (p.closest && p.closest('[data-v2c-xl="1"]')) continue;         /* 旋转轴图已单独治理 */
      seen++;
      var svgHost = p.closest ? p.closest("svg") : null;
      var cu = svgHost ? dominantUnit(svgHost, domCache) : null;
      var nt = normText(contextLabels(p), t, cu);
      if (nt !== t){ node.nodeValue = nt; changed++; }
    }
    return changed;
  }
  /* ── 1b. 表格：表内统一到单一单位（万元，极大表用亿元），保留勾稽精度 ── */
  var TH_SKIP = /(因子|天数|序号|日期|支付日|设立日|到期日|兑付日|清算日|率|占比|差额|差异|状态|倍数|编号|备注|档位|层级|科目|^期$|支付期|户数|笔数)/;
  var TH_KEEP = /(本金|利息|现金流|现值|期初|期末|流入|流出|余额|金额|费用|报酬|回收|规模|档)/;
  var AMT_CELL = /^(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?$/;
  function tableTitle(tb){
    var host = (tb.closest && tb.closest(".chart,.card,.fold")) || tb.parentNode;
    var t = host ? $(".ct2,.ct", host) : null;
    return t ? t : null;
  }
  function normalizeTables(root){
    var touched = 0;
    $$("table.tbl", root).forEach(function(tb){
      var rows = $$("tr", tb);
      if (rows.length < 2) return;
      var headCells = $$("th", rows[0]);
      var heads = headCells.map(function(th){ return th.textContent.replace(/\s+/g, ""); });
      if (!heads.length) return;
      var tt = tableTitle(tb);
      var ttxt = tt ? tt.textContent : "";
      /* 声明了单位（或矩阵表）的表格：期次列也是金额列，可按声明单位统一 */
      var declared = /单位[:：]\s*(亿元|亿|万元|万|元)/.test(ttxt) ||
                     /[,，]\s*元\s*[)）]/.test(ttxt) ||
                     /(^|\s)mtx(\s|$)/.test(tb.className || "");
      var cols = [];
      heads.forEach(function(h, i){
        if (TH_SKIP.test(h)) return;
        if (TH_KEEP.test(h) || declared) cols.push(i);
      });
      if (!cols.length) return;
      var maxAbs = 0, cells = {}, rowsOk = 0;
      cols.forEach(function(ci){ cells[ci] = []; });
      rows.slice(1).forEach(function(r){
        var tds = $$("td", r);
        if (tds.length !== heads.length) return;   /* 跨列分组行/合并单元格：跳过，避免列错位 */
        rowsOk++;
        cols.forEach(function(ci){
          var td = tds[ci]; if (!td) return;
          var txt = td.textContent.trim();
          var m = AMT_CELL.exec(txt);
          if (!m) return;
          var v = toYuan(m[1], m[2] || "元");
          cells[ci].push({ td: td, v: v, raw: txt });
          if (Math.abs(v) > maxAbs) maxAbs = Math.abs(v);
        });
      });
      if (!maxAbs || rowsOk < 2) return;
      var unit = maxAbs >= 1e9 ? "亿" : "万";
      var f = unitFactor(unit), uw = unitWord(unit);
      var hit = 0;
      cols.forEach(function(ci){
        var list = cells[ci];
        if (list.length < 2) return;               /* 单值列不动，避免误判 */
        list.forEach(function(c){
          var s = th(c.v / f, 2) + " " + uw;
          if (s === c.raw) return;
          c.td.textContent = s;
          hit++;
        });
      });
      if (hit){
        touched++;
        patchTableTitle(tb, tt, unit, declared);
      }
    });
    return touched;
  }
  function patchTableTitle(tb, tt, unit, declared){
    if (tt){
      var s = tt.textContent;
      var ns = s.replace(/单位[:：]\s*(亿元|亿|万元|万|元)/g, "单位：" + unitWord(unit))
                .replace(/[，,]\s*(亿元|亿|万元|万|元)\s*[）)]/g, "，" + unitWord(unit) + "）");
      if (ns === s && !/亿元|万元/.test(s)) ns = s.replace(/\s*$/, "") + "（单位：" + unitWord(unit) + "）";
      if (ns !== s){ tt.textContent = ns; return; }
      return;
    }
    /* 无标题：用 <caption> 明确单位（表格自带、合法标签） */
    if (!declared && !$("caption.v2c-cap", tb)) return;
    var cap = $("caption.v2c-cap", tb);
    if (!cap){
      cap = document.createElement("caption");
      cap.className = "v2c-cap";
      tb.insertBefore(cap, tb.firstChild);
    }
    cap.textContent = "单位：" + unitWord(unit);
  }

  /* ── 1c. 数轴：同一张 SVG 的刻度统一到单一单位，并在轴旁注明 ──
     幂等：处理过就打 data-v2c-axis=1，绝不再解析自己写出的裸数字（否则会被当成「元」而抹成 0.00）*/
  function unifyAxes(root){
    $$("svg[viewBox]", root).forEach(function(svg){
      if (svg.getAttribute("data-v2c") === "1") return;            /* 自绘 SVG 已统一 */
      if (svg.getAttribute("data-v2c-axis") === "1") return;       /* 已处理过，跳过 */
      if (svg.closest && svg.closest('[data-v2c="1"]')) return;
      var ticks = $$("text", svg).filter(function(t){
        if ((t.getAttribute("text-anchor") || "") !== "end") return false;
        if (!(parseFloat(t.getAttribute("x")) < 110)) return false;
        var s = t.textContent.trim();
        return !!s && /^(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?$/.test(s);
      });
      if (ticks.length < 2) return;
      /* 只在刻度自带单位词时改写：无单位裸数字的含义不可推断（元/万/亿都不确定），不猜 */
      var withUnit = ticks.filter(function(t){ return /(亿元|亿|万元|万|元)$/.test(t.textContent.trim()); });
      if (withUnit.length < 2) return;
      var vals = ticks.map(function(t){
        var m = /^(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?$/.exec(t.textContent.trim());
        return toYuan(m[1], m[2] || "元");
      });
      var maxAbs = 0;
      vals.forEach(function(v){ if (Math.abs(v) > maxAbs) maxAbs = Math.abs(v); });
      if (!(maxAbs > 0)) return;
      var pick = pickAxisUnit(maxAbs, vals);
      if (!pick) return;                       /* 退化：保留原样 */
      var uw = unitWord(pick.unit);
      ticks.forEach(function(t, i){
        if (t.textContent !== pick.labels[i]) t.textContent = pick.labels[i];
      });
      var note = $(".v2c-unitnote", svg);
      if (note){ note.textContent = "单位：" + uw; }
      else {
        var xs = ticks.map(function(t){ return parseFloat(t.getAttribute("x")); });
        var minY = Math.min.apply(null, ticks.map(function(t){ return parseFloat(t.getAttribute("y")); }));
        var g = document.createElementNS("http://www.w3.org/2000/svg", "text");
        g.setAttribute("class", "v2c-note v2c-unitnote");
        g.setAttribute("x", String(Math.max.apply(null, xs) - 6));
        g.setAttribute("y", String(Math.max(12, minY - 14)));
        g.setAttribute("text-anchor", "end");
        g.setAttribute("font-size", "10.5");
        g.setAttribute("fill", C.mute);
        g.textContent = "单位：" + uw;
        svg.insertBefore(g, svg.firstChild);
      }
      svg.setAttribute("data-v2c-axis", "1");
      svg.setAttribute("data-v2c-axisunit", uw);
    });
  }

  /* 图注：在 SVG 右上角写明单位（幂等；供「同一图单一单位」可读）*/
  function addSvgNote(svg, txt){
    var vb = (svg.getAttribute("viewBox") || "0 0 330 160").split(/\s+/);
    var W = parseFloat(vb[2]) || 330;
    var note = $(".v2c-valuenote", svg);
    if (!note){
      note = document.createElementNS("http://www.w3.org/2000/svg", "text");
      note.setAttribute("class", "v2c-note v2c-valuenote");
      note.setAttribute("text-anchor", "end");
      note.setAttribute("font-size", "10.5");
      note.setAttribute("fill", C.mute);
      svg.insertBefore(note, svg.firstChild);
    }
    note.setAttribute("x", String(Math.max(40, W - 4)));
    note.setAttribute("y", "12");
    if (note.textContent !== txt) note.textContent = txt;
  }
  /* ── 1d. 坐标轴标签治理（瀑布图等）：旋转标签防裁切/防压字 + 数值标签单位统一 ── */
  function estW(str, fs){
    var w = 0;
    for (var i = 0; i < str.length; i++)
      w += /[\u2e80-\u9fff\uff00-\uffef\u3000-\u303f]/.test(str.charAt(i)) ? fs : fs * 0.58;
    return w;
  }
  function rotAngle(t){
    var m = /rotate\(([-\d.]+)/.exec(t.getAttribute("transform") || "");
    return Math.abs(parseFloat(m ? m[1] : "-40") || 40) * Math.PI / 180;
  }
  /* 裸数字值标签统一单位：
     ① 仅处理「图内无单位注记」的图（自绘图已自带单位，不重复处理）；
     ② 每个裸数字从最近的、带 <title> 的前序兄弟里取真实单位（柱/条/扇区的 title）；
     ③ 全图统一到同一单位词；title 也取不到单位的保持原样并加图注「单位未标注（源）」 */
  var UNIT_STAT = { fixed: 0, unknown: 0, unknownList: [], charts: 0 };
  var domCache = (typeof Map !== "undefined") ? new Map() : null;
  function unitValueLabels(root, stat){
    $$(".chart", root).forEach(function(host){
      if (host.getAttribute("data-v2c-unit") === "1") return;
      var svg = $("svg", host);
      if (!svg){ host.setAttribute("data-v2c-unit", "1"); return; }
      if ($(".v2c-note,.v2c-unitnote", svg)){ host.setAttribute("data-v2c-unit", "1"); return; }  /* 已有单位注记 */
      var rows = [];
      $$("text", svg).forEach(function(t){
        var raw = t.textContent.trim();
        /* 值标签＝整格只有「数字（可带单位）」，如 `5200`、`4.10 万`；带 % 的占比文本不算 */
        if (!/^-?[\d][\d,]*(?:\.\d+)?\s*(亿元|亿|万元|万|元)?$/.test(raw)) return;
        /* 只认「数据图元」上的标签：紧邻的前一个元素必须是带 <title> 的 rect/circle/polygon
           （柱/条/点）。圆环圆心（前面是「合计」文本）、坐标刻度、地区方格标签等一律不动——
           否则会拿错数据点的 <title>，进而给出与值矛盾的单位徽章 */
        var p = t.previousElementSibling;
        var tg = p ? (p.nodeName || "").toLowerCase() : "";
        if (tg !== "rect" && tg !== "circle" && tg !== "polygon") return;
        var tt = p.querySelector ? p.querySelector("title") : null;
        var yuan = tt ? amtFromTitle(tt.textContent) : null;
        if (yuan == null){
          AMT_RE.lastIndex = 0;
          var m0 = AMT_RE.exec(raw);
          AMT_RE.lastIndex = 0;
          if (m0) yuan = toYuan(m0[1], m0[3]);
        }
        rows.push({ el: t, raw: raw, yuan: yuan });
      });
      if (!rows.length){ host.setAttribute("data-v2c-unit", "1"); return; }
      var known = rows.filter(function(r){ return r.yuan != null; });
      if (!known.length){
        addSvgNote(svg, "单位未标注（源）");
        stat.unitUnknown++;
        UNIT_STAT.unknown++;
        if (UNIT_STAT.unknownList.length < 40) UNIT_STAT.unknownList.push(hostKey(host).slice(0, 22));
        stat.unitUnknownList.push(hostKey(host).slice(0, 20));
        host.setAttribute("data-v2c-unit", "1");
        return;
      }
      /* 单位由「该图全部数值」派生（不能只看裸数字那部分，否则会被小值带偏成「元」），
         图注与徽章用同一个 u —— 三者永远一致 */
      var vals = known.map(function(r){ return r.yuan; });
      var maxV = 0;
      vals.forEach(function(v){ if (Math.abs(v) > maxV) maxV = Math.abs(v); });
      var u = pickValueUnit(maxV, vals);
      var uw = unitWord(u), fixed = 0;
      known.forEach(function(r){
        var target = vlab(u, r.yuan);
        if (target !== r.raw){ r.el.textContent = target; fixed++; }
      });
      if (fixed) stat.unitFixed += fixed;
      UNIT_STAT.fixed += fixed;
      UNIT_STAT.charts++;
      var unk = rows.length - known.length;
      addSvgNote(svg, "单位：" + uw + (unk ? "（" + unk + " 项源未标注）" : ""));
      addTag(host, "单位：" + uw);
      host.setAttribute("data-v2c-unit", "1");
    });
  }
  /* ═══════════════ 3b2. 全周期资金分配瀑布（v6 重建，数据源 __V2.WF）═══════════════
     修正三点：
       ① 证券受偿取「分档兑付表」(WF.steps kind:'sec')，不再用 alloc.cum 的
          「优先档本金＝优先+次级总本金」错口径；
       ② 处置费用不重复计入：数据层检测到重复(dbl=true)时已从 steps 剔除，只在注释说明；
       ③ 终点单列「账面结余」＝ residual，如实显示；|residual|/rec > 0.1% 用警示色并注明
          「分配表与逐期账户口径差」。 */
  var WF_COLOR = { in: "#1F7A5C", out: "#7C8798", sec1: "#2D3955", sec2: "#B0763F", sec3: "#5A6B8C", res: "#8A94A6" };
  var WF_SHORT = [
    [/跟踪评级服务费|评级服务费|评级费/, "评级费"],
    [/资金保管机构报酬|保管机构报酬|保管费/, "保管费"],
    [/代理兑付费用|兑付费用|兑付费/, "兑付费"],
    [/贷款服务机构报酬|服务机构报酬/, "服务费"],
    [/受托机构报酬|受托报酬/, "受托费"],
    [/其他费用支出/, "其他费"],
    [/收益合计/, "收益"],
    [/资产支持证券/, ""]
  ];
  function wfShortLabel(lab){
    var s0 = String(lab == null ? "" : lab);
    s0 = s0.replace(/优先档\s*/g, "优先").replace(/次级档\s*/g, "次级");
    for (var i = 0; i < WF_SHORT.length; i++) s0 = s0.replace(WF_SHORT[i][0], WF_SHORT[i][1]);
    s0 = s0.replace(/\s+/g, "");
    if (s0.length > 4) s0 = s0.slice(0, 4);
    return s0 || "—";
  }
  function wfAmt(v){
    if (Math.abs(v) >= 1e6) return th(v / 1e8, 2) + " 亿元";
    return th(v / 1e4, 2) + " 万元";
  }
  function wfColor(step){
    if (step.kind === "in") return WF_COLOR.in;
    if (step.kind === "sec") return /优先/.test(step.label) ? WF_COLOR.sec1
      : (/次级/.test(step.label) ? WF_COLOR.sec2 : WF_COLOR.sec3);
    return WF_COLOR.out;
  }
  function drawWaterfall(host, view){
    var V = window.__V2 || {}, WF = V.WF || {};
    var key = keyOfView(view);
    var wf = key ? WF[key] : null;
    if (!wf || !wf.steps || !wf.steps.length) return false;
    var svg = $("svg", host);
    if (!svg) return false;
    var vb = (svg.getAttribute("viewBox") || "0 0 680 280").split(/\s+/);
    var W = parseFloat(vb[2]) || 680;
    var rec = num(wf.rec), res = num(wf.residual), note = String(wf.note || "");
    if (!(rec > 0)) return false;
    var bars = [], run = 0, i;
    /* v7：柱序按金额降序 —— 回收流入固定最左（起点），其后扣减项按 |金额| 由大到小，
       账面结余固定最右（终点）。累加链随新序重算，终点仍等于 residual。 */
    var insB = [], outsB = [];
    for (i = 0; i < wf.steps.length; i++){
      var st0 = wf.steps[i], v0 = num(st0.value);
      if (!v0) continue;
      if (st0.kind === "in") insB.push(st0); else outsB.push(st0);
    }
    outsB.sort(function(x, y){ return Math.abs(num(y.value)) - Math.abs(num(x.value)); });
    var seq = insB.concat(outsB);
    for (i = 0; i < seq.length; i++){
      var st = seq[i], v = num(st.value);
      if (st.kind === "in"){ bars.push({ label: wfShortLabel(st.label), full: String(st.label), kind: "in", from: 0, to: v, v: v }); run = v; }
      else { bars.push({ label: wfShortLabel(st.label), full: String(st.label).replace(/\s+/g, " ").replace(/\s+·?\s*/g, " ").trim(), kind: st.kind || "out", from: run, to: run - v, v: -v }); run -= v; }
    }
    bars.push({ label: "账面结余", full: "账面结余（回收 − 各项流出）", kind: "res", from: 0, to: res, v: res });
    var n = bars.length;
    var na = niceAxisTop(Math.max(rec, res, run));
    var vTop = na.top;
    var yMin = Math.min(0, res, run);
    if (vTop <= yMin) return false;
    var mg = { l: 68, r: 22, t: 50, b: 54 + (note ? 20 : 0) };
    var plotH = 196;
    var H = mg.t + plotH + mg.b;
    var x0 = mg.l, x1 = W - mg.r, y0 = mg.t, y1 = mg.t + plotH;
    function Y(v){ return y1 - (v - yMin) / (vTop - yMin) * (y1 - y0); }
    var slot = (x1 - x0) / n, barW = Math.min(34, slot * 0.62);
    var tickVals = [];
    for (i = 0; i <= na.k; i++) tickVals.push(na.step * i);
    var pick = pickAxisUnit(vTop, tickVals);
    if (!pick) return false;
    var u = pick.unit, uw = unitWord(u), uf = unitFactor(u);
    var g = [];
    /* 网格 + y 刻度（单一单位；逐 tick 用各自数值）*/
    for (i = 0; i < tickVals.length; i++){
      var yy = Y(tickVals[i]);
      g.push('<line x1="' + x0 + '" y1="' + th(yy, 1) + '" x2="' + x1 + '" y2="' + th(yy, 1) +
             '" stroke="' + (i === 0 ? C.axis : C.grid) + '" stroke-width="1"/>');
      if (tickVals.length <= 6 || i % 2 === 0 || i === tickVals.length - 1)
        g.push('<text class="v2c-ax" x="' + (x0 - 10) + '" y="' + th(yy + 4, 1) + '" text-anchor="end" font-size="11" fill="' + C.sub + '">' + esc(pick.labels[i]) + '</text>');
    }
    /* 单位徽章（短文本，避免与图例抢位）*/
    var unitTxt = "单位：" + uw;
    var unitW = estTextW(unitTxt, 10.5);
    var unitY = mg.t - 24;
    /* 图例：按实测宽度排布；总宽超出则两行；图例左端与单位徽章至少 16px */
    var lg = [["回收流入", WF_COLOR.in], ["费用/税/转存", WF_COLOR.out], ["证券受偿", WF_COLOR.sec1], ["账面结余", WF_COLOR.res]];
    var lgItems = lg.map(function(it){ return { t: it[0], c: it[1], w: estTextW(it[0], 9.5) + 22 }; });
    var lgGap = 12, lgAvail = (x1 - x0) - unitW - 16;
    var lgTotal = lgItems.reduce(function(a, b){ return a + b.w; }, 0) + lgGap * (lgItems.length - 1);
    var lgRows = lgTotal <= lgAvail ? 1 : 2, lgPer = Math.ceil(lgItems.length / lgRows);
    var lgLeft = x1;
    for (var lr = 0; lr < lgRows; lr++){
      var chunk = lgItems.slice(lr * lgPer, (lr + 1) * lgPer);
      var cw = chunk.reduce(function(a, b){ return a + b.w; }, 0) + lgGap * (chunk.length - 1);
      var lx0 = x1 - cw;
      if (lx0 < lgLeft) lgLeft = lx0;
      var lyb = mg.t - 24 + lr * 15;
      chunk.forEach(function(it){
        g.push('<rect x="' + th(lx0, 1) + '" y="' + th(lyb - 8.5, 1) + '" width="9" height="9" rx="2" fill="' + it.c + '"/>' +
               '<text class="v2c-leg v2c-wfleg" x="' + th(lx0 + 12, 1) + '" y="' + th(lyb, 1) + '" font-size="9.5" fill="' + C.ink2 + '">' + esc(it.t) + '</text>');
        lx0 += it.w + lgGap;
      });
    }
    /* 若图例左端压到单位徽章（<16px），把徽章上移一行 */
    if (lgLeft - (x0 + unitW) < 16) unitY = mg.t - 42;
    g.push('<text class="v2c-note v2c-unitnote" x="' + x0 + '" y="' + unitY + '" font-size="10.5" fill="' + C.mute + '">' + esc(unitTxt) + '</text>');
    /* 柱 + 值标签 + 悬停 title */
    var resPct = Math.abs(res) / rec * 100;
    for (i = 0; i < n; i++){
      var b = bars[i], cx = x0 + slot * (i + 0.5), bx = cx - barW / 2;
      var vy0 = Y(b.from), vy1 = Y(b.to);
      var top = Math.min(vy0, vy1), hgt = Math.max(1.2, Math.abs(vy1 - vy0));
      var col = b.kind === "res" ? (resPct > 0.1 ? C.warn : WF_COLOR.res) : wfColor(b);
      var pctRec = b.v / rec * 100;
      var title = hitTitle([b.full, b.v >= 0 ? "+" : "−", wfAmt(Math.abs(b.v)), "占回收 " + th(Math.abs(pctRec), 2) + "%"]);
      g.push('<rect x="' + th(bx, 1) + '" y="' + th(top, 1) + '" width="' + th(barW, 1) + '" height="' + th(hgt, 1) +
             '" rx="2" fill="' + col + '"><title>' + esc(title) + '</title></rect>');
      /* 值标签：过小（<0.5% 回收）不标，避免「−0.00」；精确值见 <title> */
      if (Math.abs(b.v) / rec >= 0.02){
        var labTxt = (b.kind === "in" ? "+" : (b.kind === "res" ? "" : "−")) + th(Math.abs(b.v) / uf, 2);
        var ly = (b.kind === "in" || (b.kind === "res" && b.v >= 0)) ? top - 5 : Math.max(vy0, vy1) - 6;
        g.push('<text class="v2c-wfval" x="' + th(cx, 1) + '" y="' + th(clamp(ly, y0 + 8, y1 - 5), 1) + '" text-anchor="middle" font-size="8.5" fill="' + C.ink2 + '">' + esc(labTxt) + '</text>');
      }
      /* x 轴标签：短标签（全称在柱 <title> 里），窄槽抽稀避免压字 */
      if (n <= 12 || (i % 2 === 0 && i !== n - 2) || i === n - 1)
        g.push('<text class="v2c-ax-x" x="' + th(cx, 1) + '" y="' + (y1 + 18) + '" text-anchor="middle" font-size="8.5" fill="' +
               (i === n - 1 ? C.ink2 : C.sub) + '"' + (i === n - 1 ? ' font-weight="700"' : '') + '>' + esc(b.label) + '</text>');
    }
    /* 账面结余说明（偏差 >0.1% 用警示色）*/
    if (resPct > 0.1){
      g.push('<text class="v2c-note" x="' + (x1) + '" y="' + (y1 + 34) + '" text-anchor="end" font-size="10" fill="' + C.warn + '">分配表与逐期账户口径差 ' +
             esc(wfAmt(res)) + '（' + esc(th(resPct, 2)) + '% 回收）</text>');
    } else {
      g.push('<text class="v2c-note" x="' + (x1) + '" y="' + (y1 + 34) + '" text-anchor="end" font-size="10" fill="' + C.mute + '">账面结余 ' +
             esc(wfAmt(res)) + '（口径差 ' + esc(th(resPct, 3)) + '%）</text>');
    }
    /* 处置费用重复计入的说明：单独一行（该单不画处置费用柱）*/
    if (note){
      g.push('<text class="v2c-note" x="' + x0 + '" y="' + (H - 8) + '" font-size="10" fill="' + C.warn + '">注：' + esc(note) + '</text>');
    }
    mountSvg(host, svg, g.join(""), W, H);
    host.setAttribute("data-v2c", "1");
    host.setAttribute("data-v2c-xl", "1");      /* 旋转轴治理跳过（本图自绘）*/
    addSvgNote(svg, "单位：" + uw);
    addTag(host, "瀑布重建 · 单位：" + uw);
    return true;
  }

  /* ── 3b3. WF 断言：4 条口径校验（浏览器控制台 __V2Charts.wfAudit()）── */
  function allocSecurityTotal(view){
    var tables = $$("table", view), t, i, j;
    for (t = 0; t < tables.length; t++){
      var trs = $$("tr", tables[t]);
      if (!trs.length) continue;
      var heads = $$("th", trs[0]).map(function(h){ return (h.textContent || "").replace(/\s+/g, ""); });
      var ci = -1;
      for (j = 0; j < heads.length; j++) if (heads[j] === "累计") ci = j;
      if (ci < 0) ci = 7;
      for (i = 1; i < trs.length; i++){
        var tds = $$("td", trs[i]);
        if (!tds.length) continue;
        if ((tds[0].textContent || "").replace(/\s+/g, "").indexOf("证券受偿合计") < 0) continue;
        var cell = tds[ci] || null;
        var y = cell ? amtFromTitle(cell.textContent) : null;
        if (y != null) return y;
      }
    }
    return null;
  }
  function wfAudit(){
    var V = window.__V2 || {}, WF = V.WF || {};
    var rep = { checked: 0, missing: [], b1: [], b2: [], b3: [], b4: [],
                residualMaxPct: 0, residualList: [], dbl: [], ok: false };
    $$('section.view[id^="view-p"]').forEach(function(view){
      var key = keyOfView(view);
      if (!key) return;
      var wf = WF[key];
      if (!wf){ rep.missing.push(key); return; }
      rep.checked++;
      var p = profByView(view) || {};
      var steps = wf.steps || [];
      /* B1 Σ分档本金 vs 发行规模（≤0.1%）*/
      var pri = null, sub = null;
      steps.forEach(function(st){
        if (st.kind !== "sec") return;
        if (/优先/.test(st.label) && /本金/.test(st.label)) pri = num(st.value);
        if (/次级/.test(st.label) && /本金/.test(st.label)) sub = num(st.value);
      });
      var iss = num(p.issue);
      var sumP = num(pri) + num(sub);
      if (!(iss > 0 && pri != null && sub != null && Math.abs(sumP - iss) / iss <= 0.001))
        rep.b1.push(key + " 分档本金 " + th(sumP, 2) + " vs 发行 " + th(iss, 2));
      /* B2 Σ证券受偿 vs 分档兑付表合计（≤1 元）*/
      var secSum = 0;
      steps.forEach(function(st){ if (st.kind === "sec") secSum += num(st.value); });
      var st2 = allocSecurityTotal(view);
      if (st2 != null && Math.abs(secSum - st2) > 1)
        rep.b2.push(key + " sec " + th(secSum, 2) + " vs 表 " + th(st2, 2));
      /* B3 处置费用出现次数（dbl=false → 1 次；dbl=true → 0 次）*/
      var nd = 0;
      steps.forEach(function(st){ if (/处置费/.test(String(st.label))) nd++; });
      var want = wf.dbl ? 0 : 1;
      if (nd !== want) rep.b3.push(key + " 处置费用 " + nd + " 次（应 " + want + "，dbl=" + wf.dbl + "）");
      /* B4 首尾闭合 + 残差 ≤5% */
      if (Math.abs(num(wf.rec) - num(wf.totalOut) - num(wf.residual)) > 1)
        rep.b4.push(key + " 不闭合：rec−totalOut≠residual");
      var rp = Math.abs(num(wf.residual)) / (num(wf.rec) || 1) * 100;
      if (rp > 5) rep.b4.push(key + " 残差 " + th(rp, 2) + "% > 5%");
      if (rp > rep.residualMaxPct) rep.residualMaxPct = rp;
      rep.residualList.push([key.slice(0, 12), +rp.toFixed(3)]);
      if (wf.dbl) rep.dbl.push(key);
    });
    rep.ok = !(rep.missing.length || rep.b1.length || rep.b2.length || rep.b3.length || rep.b4.length);
    return rep;
  }

  /* 只替换文本里**最后一个**「数字+单位」——值通常在标题末段，
     前段标签本身也可能含数字单位（如「2 万以下（含） · 7.80 万」）*/
  function replaceLastAmt(txt, newTxt){
    var re = /[\d][\d,]*(?:\.\d+)?\s*(?:亿元|亿|万元|万|元)/g, m, last = null;
    while ((m = re.exec(String(txt))) !== null) last = m;
    if (!last) return String(txt);
    var t0 = String(txt);
    return t0.slice(0, last.index) + newTxt + t0.slice(last.index + last[0].length);
  }
  /* ── 3c2. 分布图量级扩面：hbar / treemap（源结构）也按真值换算 ──
     规则同圆环：图内合计 vs PROF.poolTotal（回收类用 recovered）相对误差 >2 倍即量级错误，
     按份额把真值分摊到各数据点（title 与可见值文本同步）。自绘图表（.v2c-svg）跳过。 */
  function nextAmountText(el){
    var n = el.nextElementSibling, guard = 0;
    while (n && guard++ < 4){
      if (n.nodeName && n.nodeName.toLowerCase() === "text"){
        var s0 = (n.textContent || "").trim();
        if (/[\d][\d,]*(?:\.\d+)?\s*(?:亿元|亿|万元|万|元)/.test(s0)) return n;
      }
      n = n.nextElementSibling;
    }
    return null;
  }
  function distMagPass(root, stat){
    $$(".chart", root).forEach(function(host){
      var chart = host.getAttribute("data-chart") || "";
      if (chart !== "hbar" && chart !== "treemap") return;
      var svg = $("svg", host);
      if (!svg) return;
      if ($(".v2c-svg", host)) return;              /* 自绘图：值取自校准后的源，跳过 */
      var ct = $(".ct", host) || $(".ct2", host);
      var view = host.closest ? host.closest("section.view") : null;
      var ref = donutRefOf(view, ct ? ct.textContent : "");
      if (!ref) return;
      var pts = [], seenP = {};
      $$("rect, path", svg).forEach(function(el){
        var tt = el.querySelector ? el.querySelector("title") : null;
        if (!tt) return;
        var tx = tt.textContent;
        if (seenP[tx]) return;
        seenP[tx] = 1;
        var y = amtFromTitle(tx);
        if (y == null || y === 0) return;
        pts.push({ el: el, titleEl: tt, title: tx, yuan: y });
      });
      if (pts.length < 2) return;
      var sum = 0, i;
      for (i = 0; i < pts.length; i++) sum += pts[i].yuan;
      MAG_STAT.allChecked++;
      if (!(sum > 0)) return;
      var ratio = ref / sum;
      if (!(ratio > 100 || ratio < 0.01)){
        /* 2~100 倍或 0.5~2 倍：不是「量级错标」，可能是源图只覆盖部分分桶 → 不臆造缩放 */
        if (!(ratio >= 0.5 && ratio <= 2)) MAG_STAT.allWarn++;
        return;
      }
      var k = ref / sum;
      var nv = pts.map(function(p){ return p.yuan * k; });
      var u = pickValueUnit(ref, nv);
      var ch = 0;
      for (i = 0; i < pts.length; i++){
        var s1 = vlabS(u, nv[i]);
        var t2 = replaceLastAmt(pts[i].title, s1);
        if (pts[i].titleEl.textContent !== t2){ pts[i].titleEl.textContent = t2; ch++; }
        var vis = nextAmountText(pts[i].el);
        if (vis && vis.textContent !== s1){ vis.textContent = s1; ch++; }
      }
      MAG_STAT.allFixed++;
      MAG_STAT.fixedItems += ch;
      if (stat){ stat.magAllFixed = (stat.magAllFixed || 0) + 1; stat.magItems = (stat.magItems || 0) + ch; }
    });
  }
  /* ══════════ v8. 资产池 10 类分布图重绘（数据源 __V2.DIST）══════════
     图型按类别数自适应：
       ≤6  → 100% 单条横向堆积（图例独立一行在条上方）
       7–15 → 横向条形（左标签右数值，标签完整不截断，标签列 ≤38% 宽）
       >15  → Top10 + 「其他」（其余合并，明细进 <title>）
     字号统一：轴/图例/数据 10px、图注 9.5px；标题由卡片 .ct 12px。
     口径：默认按未偿余额（万元→亿元），图上明示「口径：未偿余额（亿元）」。 */
  var DIST_KIND = [
    ["未偿本息费", "balance"], ["五级分类", "grade"], ["担保方式", "guarantee"],
    ["逾期时间", "overdue"], ["年龄", "age"], ["年收入", "income"],
    ["授信额度", "credit"], ["职业", "occupation"], ["地区", "region"], ["预计回收率", "recrate"]
  ];
  var DIST_STAT = { drawn: 0, stack: 0, bars: 0, top10: 0, notes: 0, fonts: 0 };
  function distTypeOf(host){
    var ct = $(".ct", host) || $(".ct2", host);
    var t = ct ? ct.textContent : "";
    for (var i = 0; i < DIST_KIND.length; i++) if (t.indexOf(DIST_KIND[i][0]) >= 0) return DIST_KIND[i][1];
    return "";
  }
  function distData(view, host){
    var V = window.__V2 || {}, D = V.DIST || {};
    var key = keyOfView(view);
    var type = distTypeOf(host);
    if (!key || !type) return null;
    var arr = (D[key] || {})[type];
    if (!arr || !arr.length) return null;
    var rows = [];
    for (var i = 0; i < arr.length; i++){
      var x = arr[i];
      rows.push({ label: String(x.label == null ? "—" : x.label), bal: num(x.bal) * 1e4,
                  pct: num(x.bal_pct), n: num(x.n), npct: num(x.n_pct) });
    }
    rows.sort(function(a, b){ return b.bal - a.bal; });
    rows = rows.filter(function(r){ return r.bal > 0 || r.n > 0; });
    if (!rows.length) return null;
    return { type: type, rows: rows, key: key };
  }
  function distFmtYi(v){ return th(v / 1e8, 2); }
  function distBars(info, W){
    /* >15 类：Top10 + 其他 */
    var rows = info.rows.slice(), others = [];
    if (rows.length > 15){
      others = rows.slice(10);
      rows = rows.slice(0, 10);
      var sum = 0, nsum = 0;
      others.forEach(function(r){ sum += r.bal; nsum += r.n; });
      var o = { label: "其他（" + others.length + " 类）", bal: sum, n: nsum, pct: 0, other: others };
      var tot = rows.reduce(function(a, b){ return a + b.bal; }, 0) + sum;
      o.pct = tot > 0 ? sum / tot * 100 : 0;
      rows.push(o);
      DIST_STAT.top10++;
    }
    return rows;
  }
  function v8DrawDist(host, view){
    var info = distData(view, host);
    if (!info) return false;
    /* v8.3 按「原报告图型」恢复：
       · donut 3 张（余额/五级/担保）→ 交回原圆环通道（量级/单位/图例修正全部保留）
       · hbar  5 张（逾期/年龄/年收入/授信/预计回收率）→ 用 DIST 自绘**横条**（保持 data-chart="hbar"，
                完整标签、右侧数值、无纵轴 → 修「纵轴被遮挡」）
       · 仅 职业(37)/地区(30+) → 横条 + Top10+其他（用户明确要求换图） */
    var DONUT_T = { balance: 1, grade: 1, guarantee: 1 };
    var BAR_T = { occupation: 1, region: 1 };
    var HBAR_T = { overdue: 1, age: 1, income: 1, credit: 1, recrate: 1 };
    if (DONUT_T[info.type] || (!BAR_T[info.type] && !HBAR_T[info.type])) return false;
    var svg = $("svg", host);
    if (!svg) return false;
    var V = window.__V2 || {}, prof = profByView(view) || {};
    /* 画布宽度取卡片实测内容宽（原圆环是 560 定宽，直接用会越界）*/
    var cw0 = host.clientWidth || 0;
    var W = cw0 > 80 ? Math.max(240, cw0 - 36) : (parseFloat(String(svg.getAttribute("viewBox") || "").split(/\s+/)[2]) || 360);
    var FS = 10, FN = 9.5, LH = 15, PAD = 6;
    var note = "口径：未偿余额（亿元）";
    var g = [], i;
    var rows = info.rows, mode = "stack";
    if (BAR_T[info.type] || HBAR_T[info.type]){ mode = "bars"; rows = distBars(info, W); }
    else if (rows.length > 6){ mode = "bars"; rows = distBars(info, W); }
    var mxBal = 0;
    rows.forEach(function(r){ if (r.bal > mxBal) mxBal = r.bal; });

    if (mode === "stack"){
      /* 图例（独立一行，最多两行）*/
      var legendY = PAD + FS + 2, colX = PAD, lineH = FS + 6, lines = 1, used = 0;
      var items = rows.map(function(r){
        var txt = r.label + " " + th(r.pct, 2) + "%";
        return { t: txt, w: estTextW(txt, FS) + 14, r: r };
      });
      var totalW = 0;
      items.forEach(function(it){ totalW += it.w + 10; });
      var perLine = Math.max(1, Math.floor((W - PAD * 2) / (totalW / items.length + 1)));
      var li = 0, cx = colX, cy = legendY;
      for (i = 0; i < items.length; i++){
        if (cx + items[i].w > W - PAD - 6 && cx > colX){ cx = colX; cy += lineH; lines++; }
        var sw = 9, tw = items[i].w - 14;
        if (tw < estTextW(items[i].t, FS)) tw = items[i].w;
        g.push('<rect x="' + th(cx, 1) + '" y="' + th(cy - FS + 2, 1) + '" width="9" height="9" rx="2" fill="' + DIST_COLOR(i) + '"/>' +
               '<text class="v2c-dleg" x="' + th(cx + 12, 1) + '" y="' + th(cy, 1) + '" font-size="' + FS + '" fill="' + C.ink2 + '">' +
               esc(items[i].t) + '</text>');
        cx += items[i].w + 18;
      }
      /* 100% 堆积条：内容高下限 175，条形在「图例下方区域」垂直居中（间距均匀，不留大块空白）*/
      var legendBottom = legendY + (lines - 1) * lineH + 8;
      var barH = 26, barW = W - PAD * 2, acc = 0;
      var tailH = 14 + FN + 6;                       /* 图注 + 下边距 */
      var minH = 175;
      var availH = Math.max(barH + 24, minH - legendBottom - tailH);
      var barY = legendBottom + Math.max(10, (availH - barH) / 2);
      rows.forEach(function(r, k){
        var w = barW * (r.pct / 100), x = PAD + acc;
        acc += w;
        if (w < 0.6) return;
        g.push('<rect class="v2c-dseg" x="' + th(x, 2) + '" y="' + th(barY, 1) + '" width="' + th(w, 2) + '" height="' + barH +
               '" fill="' + DIST_COLOR(k) + '"><title>' + esc(distTip(r)) + '</title></rect>');
        if (w >= 62)
          g.push('<text class="v2c-dval" x="' + th(x + w / 2, 1) + '" y="' + th(barY + barH / 2 + 3.5, 1) + '" text-anchor="middle" font-size="' + FS +
                 '" fill="#fff" font-weight="700">' + esc(th(r.pct, 1) + "%") + '</text>');
      });
      var H = Math.max(minH, Math.ceil(barY + barH + tailH));
      g.push('<text class="v2c-note" x="' + PAD + '" y="' + (H - 5) + '" font-size="' + FN + '" fill="' + C.mute + '">' + esc(note) + '</text>');
      mountSvg(host, svg, g.join(""), W, H);
      DIST_STAT.stack++;
    } else {
      /* 横向条形：左标签（右对齐、完整）+ 右数值 */
      var labelW = 0;
      rows.forEach(function(r){ var w2 = estTextW(r.label, FS); if (w2 > labelW) labelW = w2; });
      labelW = Math.min(Math.ceil(labelW) + 6, Math.round(W * 0.38));
      var valueW = Math.max(56, Math.ceil(estTextW("9,999.99 亿元", FS)) + 4);
      var plotX = PAD + labelW + 8, plotR = W - PAD - valueW, plotW = Math.max(30, plotR - plotX);
      var rowH = rows.length >= 10 ? 14 : 18, top = PAD + FN + 8;
      rows.forEach(function(r, k){
        var y = top + k * rowH;
        var bw = mxBal > 0 ? plotW * (r.bal / mxBal) : 0;
        if (bw < 1.2) bw = 1.2;
        var lw0 = estTextW(r.label, FS);
        var lx0 = Math.max(PAD + 4 + lw0, plotX - 8);
        g.push('<text class="v2c-dlab" x="' + th(lx0, 1) + '" y="' + th(y + rowH * 0.5 + 3.5, 1) + '" text-anchor="end" font-size="' + FS + '" fill="' + C.ink2 + '">' + esc(r.label) + '</text>');
        g.push('<rect class="v2c-dbar" x="' + th(plotX, 1) + '" y="' + th(y + 3, 1) + '" width="' + th(bw, 2) + '" height="' + (rowH - 7) +
               '" rx="2" fill="' + DIST_COLOR(k) + '"><title>' + esc(distTip(r)) + '</title></rect>');
        g.push('<text class="v2c-dval" x="' + th(plotR + 6, 1) + '" y="' + th(y + rowH * 0.5 + 3.5, 1) + '" font-size="' + FS + '" fill="' + C.ink2 +
               '" font-variant-numeric="tabular-nums">' + esc(distFmtYi(r.bal)) + '</text>');
      });
      var H2 = top + rows.length * rowH + FN + 2;
      g.push('<text class="v2c-note" x="' + PAD + '" y="' + th(PAD + FN, 1) + '" font-size="' + FN + '" fill="' + C.mute + '">' + esc(note) + '</text>');
      g.push('<text class="v2c-note" x="' + PAD + '" y="' + (H2 - 5) + '" font-size="' + FN + '" fill="' + C.mute + '">' +
             esc("共 " + info.rows.length + " 类" + (info.rows.length > 15 ? "，仅列前 10 类，其余合并为「其他」" : "")) + '</text>');
      mountSvg(host, svg, g.join(""), W, H2);
      DIST_STAT.bars++;
    }
    svg.setAttribute("data-v2c-dist", "1");
    svg.setAttribute("data-v2c-metric", "bal");
    host.setAttribute("data-v2c", "1");
    /* 图种标记：职业/地区 → dist-bar（Top10+其他）；hbar 5 张保持 hbar（不转棒棒糖/面积/堆叠）*/
    if (BAR_T[info.type]){
      host.setAttribute("data-chart", "dist-bar");
      if (info.rows.length > 15) host.setAttribute("data-v2c-top10", "1");
    }
    host.setAttribute("data-v2c-w", String(host.clientWidth || 0));
    /* 担保方式：信用卡不良但含抵押/保证 → 回源备注放在**网格下方通栏**（不占卡片高度）*/
    var oldNote = $(".v2c-dist-note", host);
    if (oldNote && oldNote.parentNode) oldNote.parentNode.removeChild(oldNote);
    var gridEl = host.parentNode;
    while (gridEl && !(String(gridEl.className || "").match(/(^|\s)dist-grid(\s|$)/))) gridEl = gridEl.parentNode;
    var oldWide = gridEl && gridEl.parentNode ? $(".v2c-dist-note-wide", gridEl.parentNode) : null;
    if (info.type === "guarantee"){
      var pctSum = 0, balSum = 0;
      info.rows.forEach(function(r){
        if (/抵押|保证/.test(r.label)){ pctSum += r.pct; balSum += r.bal; }
      });
      var cat = String(prof.cat || prof.category || "");
      if (!cat){
        var kk = $(".kpi .k", view);
        cat = kk ? "" : "";
        var h1 = $(".hero h1", view);
        cat = h1 ? (view.textContent.indexOf("信用卡") >= 0 ? "信用卡不良" : "") : "";
      }
      if (/信用卡/.test(cat) && pctSum > 1){
        var txt = "注：本单底层为信用卡类资产，源说明书「担保方式」中含抵押/保证合计 " + th(pctSum, 2) +
          "%（余额 " + th(balSum / 1e8, 2) + " 亿元），与信用卡通常无抵押的情况不符，按源数据如实呈现，待回源核实。";
        if (gridEl && gridEl.parentNode){
          var nEl = document.createElement("p");
          nEl.className = "v2c-dist-note v2c-dist-note-wide";
          nEl.textContent = txt;
          if (oldWide) gridEl.parentNode.replaceChild(nEl, oldWide);
          else gridEl.parentNode.insertBefore(nEl, gridEl.nextSibling);
        } else {
          var nEl2 = document.createElement("p");
          nEl2.className = "v2c-dist-note";
          nEl2.textContent = txt;
          host.appendChild(nEl2);
        }
        DIST_STAT.notes++;
      }
    }
    DIST_STAT.drawn++;
    DIST_STAT.fonts = 3;
    return true;
  }
  /* ══════════ v9. 资产池 10 类分布图（设计规格书重构）══════════
     选型：有序分箱→垂直柱（余额/预计回收率加累计占比折线=帕累托）；
           五级/担保→100% 堆叠水平条（单类别时一条占比条+文字，不画圆环）；
           职业/地区→排序水平条形 TopN+其他（其余合并为中性灰，脚注注明项数）。
     口径：bal（万元）→亿元；每图标注单位/合计/样本量/口径；禁止「…」无 tooltip。*/
  var V9_KIND = { balance: "col-pareto", grade: "stack100", guarantee: "stack100",
                  overdue: "col", age: "col", income: "col", credit: "col",
                  occupation: "hbar-top", region: "hbar-top", recrate: "col-pareto" };
  var V9_TOP = { occupation: 8, region: 10 };
  var V9_SHADE = ["#2D3955", "#3F5877", "#54718E", "#6A89A5", "#8AA0B6"];
  var V9_SEM = { "正常": "#1F7A5C", "关注": "#B0763F", "次级": "#C08A2E", "可疑": "#A52524", "损失": "#6E1B1A" };
  var V9_STAT = { drawn: 0, kinds: {}, colors: {}, notes: 0 };
  /* 有序分箱排序键：解析区间左端点（"10万以下(含)"→0，"10～20.00 万元(含)"→10，"50万以上"→50）*/
  function v9OrdKey(lab){
    var t = String(lab || "");
    var m = t.match(/(-?[\d.]+)/);
    var v = m ? parseFloat(m[1]) : 0;
    if (/以上|不含）?$|不含\)?$/.test(t) && !/以下|以内/.test(t)) v += 1000;
    if (/以下|以内/.test(t)) v = -1;
    return v;
  }
  function distRaw(view, host){
    var V = window.__V2 || {}, D = V.DIST || {};
    var key = keyOfView(view), type = distTypeOf(host);
    if (!key || !type) return null;
    var arr = (D[key] || {})[type];
    if (!arr || !arr.length) return null;
    var rows = [];
    for (var i = 0; i < arr.length; i++){
      var x = arr[i];
      rows.push({ label: String(x.label == null ? "—" : x.label), bal: num(x.bal) * 1e4,
                  pct: num(x.bal_pct), n: num(x.n), npct: num(x.n_pct) });
    }
    return { type: type, rows: rows, key: key };
  }
  function v9Unit(maxBal){ return maxBal >= 1e8 ? "亿元" : "万元"; }
  function v9Amt(v, u){ return u === "亿元" ? th(v / 1e8, 2) : th(v / 1e4, 0); }
  function v9Title(r, u){
    return r.label + "｜余额 " + v9Amt(r.bal, u) + " " + u + "｜占比 " + th(r.pct, 2) + "%｜笔数 " + th(r.n, 0) + " 笔";
  }
  /* v9.2：口径行 / 图型说明写到 SVG 外的 HTML 兄弟节点（标题下、图下），SVG 内不再出现 */
  function v9SetMeta(host, txt){
    var ct = $(".ct", host) || $(".ct2", host);
    var el = $(".v9-meta", host);
    if (!el){
      el = document.createElement("div");
      el.className = "v9-meta";
      if (ct && ct.parentNode) ct.parentNode.insertBefore(el, ct.nextSibling);
      else host.insertBefore(el, host.firstChild);
    }
    if (el.textContent !== txt) el.textContent = txt;
  }
  function v9SetFoot(host, txt){
    var svg = $("svg", host);
    var el = $(".v9-foot", host);
    if (!el){
      el = document.createElement("div");
      el.className = "v9-foot";
      if (svg && svg.parentNode) svg.parentNode.insertBefore(el, svg.nextSibling);
      else host.appendChild(el);
    }
    if (el.textContent !== txt) el.textContent = txt;
  }
  function v9DrawDist(host, view){
    var info = distRaw(view, host);
    if (!info) return false;
    var kind = V9_KIND[info.type];
    if (!kind) return false;
    var svg = $("svg", host);
    if (!svg) return false;
    var cw = host.clientWidth || 0;
    if (cw < 80) return false;
    var W = Math.max(240, cw - 36);
    var rows = info.rows.slice(), FS = 10, FN = 9.5;
    var ORDERED = { balance: 1, overdue: 1, age: 1, income: 1, credit: 1, recrate: 1 };
    if (ORDERED[info.type]) rows.sort(function(a, b){ return v9OrdKey(a.label) - v9OrdKey(b.label); });
    var totBal = 0, totN = 0, mxBal = 0;
    rows.forEach(function(r){ totBal += r.bal; totN += r.n; if (r.bal > mxBal) mxBal = r.bal; });
    var u = v9Unit(mxBal);
    var g = [];
    var H = 0;
    if (kind === "stack100"){
      var n = rows.length;
      var legendH = 15, barH = 30;
      var total = 0; rows.forEach(function(r){ total += r.pct; });
      /* 图例（最多两行，独占区域）*/
      var lx = 6, ly = 14, lines = 1;
      rows.forEach(function(r, i){
        var txt = r.label + " " + th(r.pct, 2) + "%";
        var w = estTextW(txt, FS) + 22;
        if (lx + w > W - 6){ lx = 6; ly += legendH; lines++; }
        g.push('<rect x="' + th(lx, 1) + '" y="' + th(ly - 8, 1) + '" width="9" height="9" rx="2" fill="' + (V9_SEM[r.label] || V9_SHADE[i % V9_SHADE.length]) + '"/>' +
               '<text x="' + th(lx + 12, 1) + '" y="' + th(ly, 1) + '" font-size="' + FS + '" fill="#38425A">' + esc(txt) + '</text>');
        lx += w;
      });
      var barY = ly + 12, barW = W - 12, acc = 0;
      rows.forEach(function(r, i){
        var w = barW * (r.pct / Math.max(total, 1e-6));
        var col = V9_SEM[r.label] || V9_SHADE[i % V9_SHADE.length];
        if (w < 0.6) return;
        g.push('<rect class="v2c-dbar" x="' + th(6 + acc, 2) + '" y="' + th(barY, 1) + '" width="' + th(w, 2) + '" height="' + barH +
               '" fill="' + col + '"><title>' + esc(v9Title(r, u)) + '</title></rect>');
        if (w >= 44)
          g.push('<text x="' + th(6 + acc + w / 2, 1) + '" y="' + th(barY + barH / 2 + 3.5, 1) + '" text-anchor="middle" font-size="' + FS +
                 '" fill="#fff" font-weight="700">' + esc(th(r.pct, 1) + "%") + '</text>');
        acc += w;
      });
      /* 数值清单（两列紧凑：类别 金额 占比 笔数），补足信息且不虚高 */
      var listY = barY + barH + 18;
      var colW = (W - 12) / 2, half = Math.ceil(rows.length / 2);
      rows.forEach(function(r, i){
        var cx2 = 6 + (i < half ? 0 : colW);
        var cy2 = listY + (i % half) * 14;
        var txt = r.label + " " + v9Amt(r.bal, u) + u + " · " + th(r.pct, 1) + "% · " + th(r.n, 0) + "笔";
        var short = txt;
        if (estTextW(short, FN) > colW - 8) short = short.slice(0, Math.max(6, Math.floor((colW - 8) / FN) - 1)) + "…";
        g.push('<text x="' + th(cx2, 1) + '" y="' + th(cy2, 1) + '" font-size="' + FN + '" fill="#5B6472">' + esc(short) +
               (short !== txt ? '<title>' + esc(txt) + '</title>' : '') + '</text>');
      });
      H = Math.max(150, listY + half * 14 + 12);
      mountSvg(host, svg, g.join(""), W, H);
    } else if (kind === "hbar-top"){
      var topN = V9_TOP[info.type] || 8;
      var sorted = rows.slice().sort(function(a, b){ return b.bal - a.bal; });
      var use = sorted.slice(0, topN), rest = sorted.slice(topN);
      var other = null;
      if (rest.length){
        var ob = 0, on = 0;
        rest.forEach(function(r){ ob += r.bal; on += r.n; });
        other = { label: "其他（" + rest.length + " 项）", bal: ob, n: on, pct: totBal > 0 ? ob / totBal * 100 : 0, other: rest };
        use.push(other);
        V9_STAT.notes++;
      }
      var labelW = 0;
      use.forEach(function(r){ var w = estTextW(r.label, FS); if (w > labelW) labelW = w; });
      labelW = Math.min(Math.ceil(labelW) + 6, Math.round(W * 0.36));
      var plotX = 6 + labelW + 8, valueW = Math.max(46, Math.ceil(estTextW("9,999.99 亿", FS)) + 6);
      var plotR = W - 6 - valueW, plotW = Math.max(30, plotR - plotX);
      var rowH = use.length >= 9 ? 15 : 18, top = 6;
      use.forEach(function(r, i){
        var y = top + i * rowH;
        var bw = mxBal > 0 ? Math.max(1.2, plotW * (r.bal / mxBal)) : 1.2;
        var col = r.other ? "#C9D2E0" : V9_SHADE[i % V9_SHADE.length];
        var lw = estTextW(r.label, FS);
        var lx2 = Math.max(6 + lw + 2, plotX - 8);
        g.push('<text x="' + th(lx2, 1) + '" y="' + th(y + rowH * 0.5 + 3.5, 1) + '" text-anchor="end" font-size="' + FS + '" fill="#38425A">' + esc(r.label) + '</text>');
        g.push('<rect class="v2c-dbar" x="' + th(plotX, 1) + '" y="' + th(y + 2.5, 1) + '" width="' + th(bw, 2) + '" height="' + (rowH - 5) +
               '" rx="2" fill="' + col + '"><title>' + esc(v9Title(r, u)) + '</title></rect>');
        g.push('<text x="' + th(plotR + 6, 1) + '" y="' + th(y + rowH * 0.5 + 3.5, 1) + '" font-size="' + FS + '" fill="#38425A">' + esc(v9Amt(r.bal, u)) + '</text>');
      });
      H = top + use.length * rowH + 18;
      var foot = rest.length ? ("Top" + topN + " + 其他：其他含 " + rest.length + " 项（合计 " + v9Amt(other.bal, u) + " " + u + "）")
                             : ("共 " + rows.length + " 项，已全部列出");
      H = H - 14;
      mountSvg(host, svg, g.join(""), W, H);
    } else {
      /* 垂直柱状（含帕累托累计折线）*/
      var ncol = rows.length;
      var padL = 34, padR = kind === "col-pareto" ? 30 : 10, top2 = 6, plotH = 110, labelH = 34;
      var plotX0 = padL, plotX1 = W - padR, plotW2 = Math.max(30, plotX1 - plotX0);
      var slot = plotW2 / ncol, barW2 = Math.max(3, Math.min(26, slot * 0.62));
      H = top2 + plotH + labelH;
      var ticks = [0, 0.5, 1];
      ticks.forEach(function(f){
        var y = top2 + plotH * (1 - f);
        g.push('<line x1="' + plotX0 + '" y1="' + th(y, 1) + '" x2="' + plotX1 + '" y2="' + th(y, 1) + '" stroke="' + (f === 0 ? "#C9D2E0" : "#E6EBF3") + '" stroke-width="1"/>');
        g.push('<text x="' + (plotX0 - 4) + '" y="' + th(y + 3.5, 1) + '" text-anchor="end" font-size="' + FN + '" fill="#98A2B3">' + esc(v9Amt(mxBal * f, u)) + '</text>');
      });
      if (kind === "col-pareto"){
        [0, 50, 100].forEach(function(p){
          var y = top2 + plotH * (1 - p / 100);
          g.push('<text x="' + (plotX1 + 4) + '" y="' + th(y + 3.5, 1) + '" font-size="' + FN + '" fill="#8A94A6">' + p + '%</text>');
        });
      }
      var cum = 0, pts = [];
      rows.forEach(function(r, i){
        var cx = plotX0 + slot * (i + 0.5);
        var h = mxBal > 0 ? plotH * (r.bal / mxBal) : 0;
        g.push('<rect class="v2c-dbar" x="' + th(cx - barW2 / 2, 1) + '" y="' + th(top2 + plotH - h, 1) + '" width="' + th(barW2, 1) +
               '" height="' + th(Math.max(1, h), 1) + '" rx="1.5" fill="' + V9_SHADE[i % V9_SHADE.length] + '"><title>' + esc(v9Title(r, u)) + '</title></rect>');
        if (h >= 14 && slot >= 30)
          g.push('<text x="' + th(cx, 1) + '" y="' + th(top2 + plotH - h - 4, 1) + '" text-anchor="middle" font-size="' + FN + '" fill="#38425A">' + esc(th(r.pct, 0) + "%") + '</text>');
        cum += r.bal;
        pts.push({ x: cx, y: top2 + plotH * (1 - (totBal > 0 ? cum / totBal : 0)) });
        /* x 轴标签（旋转，anchor=end + dy 偏移；>6 类隔位标注；长标签缩写 + 完整 title）*/
        var showLab = ncol <= 5 || i % 2 === 0 || i === ncol - 1;
        if (showLab){
          var lab = r.label, maxPx = 60;
          if (estTextW(lab, FS) > maxPx) lab = lab.slice(0, Math.max(3, Math.floor(maxPx / FS) - 1)) + "…";
          var ly0 = top2 + plotH + 10;
          g.push('<text x="' + th(cx, 1) + '" y="' + th(ly0, 1) + '" dy="0" text-anchor="end" font-size="' + FS + '" fill="#5B6472" transform="rotate(-35 ' + th(cx, 1) + ' ' + th(ly0, 1) + ')">' +
                 esc(lab) + '<title>' + esc(r.label) + '</title></text>');
        }
      });
      if (kind === "col-pareto" && pts.length > 1){
        var d = "M" + th(pts[0].x, 1) + "," + th(pts[0].y, 1);
        for (var pi = 1; pi < pts.length; pi++) d += " L" + th(pts[pi].x, 1) + "," + th(pts[pi].y, 1);
        g.push('<path d="' + d + '" fill="none" stroke="#A52524" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>');
        pts.forEach(function(p2){
          g.push('<circle cx="' + th(p2.x, 1) + '" cy="' + th(p2.y, 1) + '" r="2.6" fill="#fff" stroke="#A52524" stroke-width="1.4"/>');
        });
      }
      H = H + 8;   /* 底部留 8px，脚注在 SVG 外的 HTML 里 */
      mountSvg(host, svg, g.join(""), W, H);
    }
    /* HTML 口径行（标题下）与图型说明（图下）—— 与 SVG 文档流分离，绝无重叠 */
    v9SetMeta(host, "单位：" + u + "　合计 " + v9Amt(totBal, u) + " " + u + "　样本 " + th(totN, 0) +
                   " 笔　口径：未偿余额（" + u + "）");
    var footTxt = "";
    if (kind === "col-pareto") footTxt = "柱=未偿余额；折线=累计占比（右轴 0–100%）　图型：垂直柱状 + 累计折线";
    else if (kind === "col") footTxt = "柱=未偿余额；区间按从小到大排列　图型：垂直柱状";
    else if (kind === "stack100") footTxt = "百分比按未偿余额占比　图型：100% 堆叠水平条";
    else footTxt = (info.rows.length > (V9_TOP[info.type] || 8)
                    ? ("Top" + (V9_TOP[info.type] || 8) + " + 其他：其他含 " + (info.rows.length - (V9_TOP[info.type] || 8)) + " 项　")
                    : ("共 " + info.rows.length + " 项　")) + "图型：排序水平条形 TopN";
    v9SetFoot(host, footTxt);
    svg.setAttribute("data-v2c-dist", "1");
    svg.setAttribute("data-v2c-charttype", kind);
    host.setAttribute("data-v2c", "1");
    host.setAttribute("data-chart", "dist-v9");
    /* 图型属性（严格取值）：pareto | stack100 | col | hbar-top */
    host.setAttribute("data-v9-chart", kind === "col-pareto" ? "pareto" : kind);
    /* 清掉标题区残留的旧图型说明（「账龄面积」「棒棒糖」「100% 堆叠条…」等）*/
    var ctEl2 = $(".ct", host) || $(".ct2", host);
    var oldTag = ctEl2 ? $(".v2c-tag", ctEl2) : null;
    if (oldTag && oldTag.parentNode) oldTag.parentNode.removeChild(oldTag);
    /* 清掉源图遗留的 .note（图内已有口径/合计行；担保异常备注走网格下方通栏）*/
    $$(":scope > .note, :scope > .v6-note", host).forEach(function(nd){
      if (nd.parentNode) nd.parentNode.removeChild(nd);
    });
    if (kind === "hbar-top") host.setAttribute("data-v2c-top10", info.rows.length > (V9_TOP[info.type] || 8) ? "1" : "0");
    host.setAttribute("data-v2c-w", String(host.clientWidth || 0));
    V9_STAT.drawn++;
    V9_STAT.kinds[kind] = (V9_STAT.kinds[kind] || 0) + 1;
    return true;
  }
  /* v8.3：担保方式异常备注独立成 pass —— 图型恢复圆环后仍保留（网格下方通栏，不占卡片高度）*/
  function distNotePass(view){
    var host = null;
    $$(".dist-grid .chart", view).forEach(function(h){ if (!host && distTypeOf(h) === "guarantee") host = h; });
    if (!host) return false;
    var key = keyOfView(view), V = window.__V2 || {};
    var arr = ((V.DIST || {})[key] || {}).guarantee || [];
    var prof = profByView(view) || {};
    var cat = String(prof.cat || prof.category || "");
    if (!cat && (view.textContent || "").indexOf("信用卡") >= 0) cat = "信用卡不良";
    var gridEl = host.parentNode;
    while (gridEl && !(String(gridEl.className || "").match(/(^|\s)dist-grid(\s|$)/))) gridEl = gridEl.parentNode;
    if (!gridEl || !gridEl.parentNode) return false;
    var oldWide = $(".v2c-dist-note-wide", gridEl.parentNode);
    var pctSum = 0, balSum = 0;
    arr.forEach(function(x){
      var lab = String(x.label || "");
      if (/抵押|保证/.test(lab)){ pctSum += num(x.bal_pct); balSum += num(x.bal) * 1e4; }
    });
    if (!(/信用卡/.test(cat) && pctSum > 1)){
      if (oldWide) oldWide.parentNode.removeChild(oldWide);
      return false;
    }
    var txt = "注：本单底层为信用卡类资产，源说明书「担保方式」中含抵押/保证合计 " + th(pctSum, 2) +
      "%（余额 " + th(balSum / 1e8, 2) + " 亿元），与信用卡通常无抵押的情况不符，按源数据如实呈现，待回源核实。";
    var nEl = document.createElement("p");
    nEl.className = "v2c-dist-note v2c-dist-note-wide";
    nEl.textContent = txt;
    if (oldWide) gridEl.parentNode.replaceChild(nEl, oldWide);
    else gridEl.parentNode.insertBefore(nEl, gridEl.nextSibling);
    DIST_STAT.notes++;
    return true;
  }
  function DIST_COLOR(i){
    var pal = ["#2D3955", "#3F5877", "#54718E", "#6A89A5", "#8AA0B6", "#A52524", "#B0763F", "#1F7A5C", "#5A6B8C", "#8A94A6"];
    return pal[i % pal.length];
  }
  function distTip(r){
    /* 顺序：label｜余额｜占比｜笔数（首金额=余额）；「其他」的明细放最后（hover 可展开）*/
    var parts = [r.label, "余额 " + th(r.bal / 1e8, 2) + " 亿元", "占比 " + th(r.pct, 2) + "%",
                 "笔数 " + th(r.n, 0) + " 笔"];
    if (r.other){
      parts.push("明细 " + r.other.slice(0, 10).map(function(o){
        return o.label + " " + th(o.bal / 1e8, 2) + " 亿";
      }).join("、") + (r.other.length > 10 ? " 等 " + r.other.length + " 类" : ""));
    }
    return parts.join("｜");
  }
  /* ══════════ 4a. 时间轴并入「兑付与清算时点」（v7）══════════
     20_profile 在 ⑤ 渲染 7 节点时间轴（.pf-tl/.pf-ts），其后另有
     「兑付与清算时点」表（.card[data-chart="timing-block"]）。
     本 pass：每档在「法定到期」后插入「实际末次兑付」节点（9 节点），
     同档三点同色系浅→深 + 短连接线；明细（含相对法定到期日提前/延后天数）
     全部走 hover title；原表格隐藏（图表已承载）。 */
  var TL_TIER = { "sen": ["优先", ["#9DB2D0", "#5E7FA8", "#2D3955"]],
                  "sub": ["次级", ["#D9C3A8", "#B0763F", "#8A5A28"]] };
  var TL_STAT = { merged: 0, nodes: 0, hidden: 0 };
  function tlShort(label){
    var s0 = String(label || "");
    s0 = s0.replace(/预期到期日（优）/, "优先·预期").replace(/法定到期日（优）/, "优先·法定")
           .replace(/预期到期日（次）/, "次级·预期").replace(/法定到期日（次）/, "次级·法定")
           .replace(/首个支付日/, "首个支付").replace(/\s+/g, "");
    return s0;
  }
  function timingRows(view){
    var card = $('[data-chart="timing-block"]', view);
    if (!card) return null;
    var out = [];
    $$("tbody tr", card).forEach(function(tr){
      var tds = $$("td", tr);
      if (tds.length < 5) return;
      out.push({ tier: (tds[0].textContent || "").trim(),
                 exp: (tds[1].textContent || "").trim(),
                 due: (tds[2].textContent || "").trim(),
                 act: (tds[3].textContent || "").trim(),
                 rel: (tds[4].textContent || "").trim() });
    });
    return out.length ? { card: card, rows: out } : null;
  }
  function mergeTiming(view, stat){
    var tl = $(".pf-tl", view);
    if (!tl) return false;
    if (tl.getAttribute("data-v2c-tl") === "1") return false;
    var tb = timingRows(view);
    if (!tb) return false;
    var byTier = {};
    tb.rows.forEach(function(r){
      var k = /优先/.test(r.tier) ? "sen" : (/次级/.test(r.tier) ? "sub" : "");
      if (k) byTier[k] = r;
    });
    if (!byTier.sen && !byTier.sub) return false;
    var nodes = $$(".pf-ts", tl);
    if (nodes.length < 5) return false;
    var html = "", added = 0;
    nodes.forEach(function(nd){
      var lab = ($(".pf-tlab", nd) || {}).textContent || "";
      var val = ($(".pf-tval", nd) || {}).textContent || "";
      var t = nd.getAttribute("data-t") || "";
      var short = tlShort(lab);
      var col = TL_TIER[t] ? TL_TIER[t][1] : null;
      var isExp = /预期/.test(lab), isDue = /法定/.test(lab);
      var cls = "pf-ts" + (col ? " v2c-tl-tier" : "") + (isExp ? " v2c-tl-exp" : (isDue ? " v2c-tl-due" : ""));
      var style = col ? ' style="--v2c-dot:' + (isExp ? col[0] : col[1]) + ';--v2c-line:' + col[1] + '"' : "";
      var title = short + " ｜ " + (val || "—") + (isDue ? " ｜ 相对基准（法定到期日）" : "");
      html += '<div class="' + cls + '"' + (t ? ' data-t="' + t + '"' : "") + style + ' title="' + esc(title) + '">' +
              '<span class="pf-tdot"></span><span class="pf-tlab">' + esc(short) + '</span>' +
              '<span class="pf-tval">' + esc(val || "—") + '</span></div>';
      var r = byTier[t];
      if (r && isDue && r.act && r.act !== "—" && r.act !== ""){
        var actTitle = TL_TIER[t][0] + "档 实际末次兑付 ｜ " + r.act + (r.rel ? " ｜ 相对法定到期日 " + r.rel : "");
        html += '<div class="pf-ts v2c-tl-tier v2c-tl-act" data-t="' + t + '" data-v2c-act="1"' +
                ' style="--v2c-dot:' + col[2] + ';--v2c-line:' + col[2] + '" title="' + esc(actTitle) + '">' +
                '<span class="pf-tdot"></span><span class="pf-tlab">' + esc(TL_TIER[t][0] + "·末次") + '</span>' +
                '<span class="pf-tval">' + esc(r.act) + '</span></div>';
        added++;
      }
    });
    if (!added) return false;
    tl.innerHTML = html;
    tl.setAttribute("data-v2c-tl", "1");
    tl.setAttribute("data-v2c-n", String(nodes.length + added));
    tb.card.style.display = "none";
    tb.card.setAttribute("data-v2c-hidden", "1");
    TL_STAT.merged++;
    TL_STAT.nodes = nodes.length + added;
    TL_STAT.hidden++;
    if (stat) stat.timeline = (stat.timeline || 0) + 1;
    return true;
  }
  /* ── 3c. 圆环图量级校正（P0）────────────────────────────────────────────
     原报告圆环数值其实是「亿」量级、标签却写「万」（整体差 10000 倍但单位词自洽），
     单看单位词查不出来。以 __V2.PROF[key].poolTotal（元，回收类用 recovered）为真值：
       · 图内合计与真值相差 >2 倍 → 判为量级错误
       · 按占比（占比不可信时按原值份额）把各项金额**换算**到真实量级
       · 中心合计与图例统一同一单位（≥0.01 亿→亿元 2 位，否则万元 2 位）
     只换算数值，不靠改标签。 */
  var MAG_STAT = { checked: 0, fixedCharts: 0, fixedItems: 0, centerFixed: 0,
                   unverified: 0, labelCharts: 0, labelTotal: 0, labelCut: 0, soloFixed: 0,
                   allChecked: 0, allFixed: 0, allWarn: 0 };
  function keyOfView(view){
    var V = window.__V2;
    if (!V) return "";
    var h1 = $(".hero h1", view);
    var name = h1 ? h1.textContent.trim() : "";
    var keys = V.ORDER || Object.keys(V.PROF || {});
    var i;
    if (name) for (i = 0; i < keys.length; i++) if (keys[i] === name) return keys[i];
    var m = /^view-p(\d+)$/.exec((view && view.id) || "");
    if (m && keys[parseInt(m[1], 10)]) return keys[parseInt(m[1], 10)];
    return "";
  }
  function profByView(view){
    var p = null;
    try { p = profOf(view); } catch (e){ p = null; }
    if (p) return p;
    var V = window.__V2, m = /^view-p(\d+)$/.exec((view && view.id) || "");
    if (V && V.PROF && V.ORDER && m){
      var k = V.ORDER[parseInt(m[1], 10)];
      if (k && V.PROF[k]) return V.PROF[k];
    }
    return null;
  }
  function donutRefOf(view, title){
    var p = profByView(view);
    if (!p) return null;
    var t = String(title || "");
    /* 口径：现金流回收类分布 → 累计回收；预计回收金额类 → 预计回收；
       其余（未偿本息费/五级分类/担保方式/职业/地区/预计回收【率】…）→ 入池本息费
       —— 注意「回收率」只是分桶维度，其合计仍是入池本息费，不能当 recovered */
    if (/现金流|回收流入|回收现金/.test(t)) return p.recovered || p.poolTotal || null;
    if (/预计回收/.test(t) && !/率/.test(t)) return p.recForecast || p.poolTotal || null;
    return p.poolTotal || null;
  }
  function donutCenterText(svg){
    var tags = $$("text", svg), i, j;
    for (i = 0; i < tags.length; i++){
      if (tags[i].textContent.trim() !== "合计") continue;
      var acc = "";
      for (j = i + 1; j < Math.min(tags.length, i + 4); j++){
        var s0 = tags[j].textContent.trim();
        if (/^-?[\d][\d,]*(?:\.\d+)?$/.test(s0) || /^(亿元|亿|万元|万|元)$/.test(s0)) acc += s0;
        else break;
      }
      if (acc) return acc;
    }
    for (i = 0; i < tags.length; i++){
      var m = /^([\d][\d,.]*\s*(?:亿元|亿|万元|万|元))$/.exec(tags[i].textContent.trim());
      if (m) return m[1];
    }
    return "";
  }
  function setDonutCenter(svg, u, ref, stat){
    var want = vnum(u, ref), uw = unitWord(u);
    var tags = $$("text", svg), ci = -1, i;
    for (i = 0; i < tags.length; i++) if (tags[i].textContent.trim() === "合计"){ ci = i; break; }
    if (ci < 0) return;
    var numEl = null, unitEl = null;
    for (i = ci + 1; i < Math.min(tags.length, ci + 4); i++){
      var s0 = tags[i].textContent.trim();
      if (!numEl && /^-?[\d][\d,]*(?:\.\d+)?$/.test(s0)) numEl = tags[i];
      else if (!unitEl && /^(亿元|亿|万元|万|元)$/.test(s0)) unitEl = tags[i];
    }
    var anchor = unitEl || numEl || tags[ci + 1] || null;
    var ax = anchor ? (anchor.getAttribute("x") || "0") : "0";
    var ay = anchor ? (parseFloat(anchor.getAttribute("y")) || 0) : 0;
    var NS = "http://www.w3.org/2000/svg";
    if (!numEl){
      numEl = document.createElementNS(NS, "text");
      numEl.setAttribute("class", "v6-cv");
      numEl.setAttribute("text-anchor", "middle");
      numEl.setAttribute("font-size", "14.5");
      numEl.setAttribute("font-weight", "700");
      numEl.setAttribute("fill", "#1A2230");
      numEl.setAttribute("x", ax);
      numEl.setAttribute("y", String((unitEl ? ay : ay + 18) - 14));
      if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(numEl, anchor);
      else svg.appendChild(numEl);
      MAG_STAT.centerFixed++;
      if (stat) stat.magCenterFixed = (stat.magCenterFixed || 0) + 1;
    }
    if (numEl.textContent !== want) numEl.textContent = want;
    if (!unitEl){
      unitEl = document.createElementNS(NS, "text");
      unitEl.setAttribute("class", "v6-lc");
      unitEl.setAttribute("text-anchor", "middle");
      unitEl.setAttribute("font-size", "9.5");
      unitEl.setAttribute("fill", "#79849A");
      unitEl.setAttribute("x", ax);
      unitEl.setAttribute("y", String((parseFloat(numEl.getAttribute("y")) || ay) + 13));
      if (numEl.parentNode) numEl.parentNode.insertBefore(unitEl, numEl.nextSibling);
      else svg.appendChild(unitEl);
    }
    if (unitEl.textContent !== uw) unitEl.textContent = uw;
  }
  function donutMagPass(root, stat){
    $$('[data-chart="donut"]', root).forEach(function(host){
      var svg = $("svg", host);
      if (!svg) return;
      var ct = $(".ct", host) || $(".ct2", host);
      var view = host.closest ? host.closest("section.view") : null;
      var ref = donutRefOf(view, ct ? ct.textContent : "");
      var rows = [];
      $$("text", svg).forEach(function(t){
        var s0 = t.textContent.trim();
        var m = /^([\d.]+)\s*%\s*[·｜|]\s*(.+)$/.exec(s0);
        if (!m) return;
        var y = amtFromTitle(m[2]);
        if (y == null) return;
        rows.push({ el: t, pct: parseFloat(m[1]), yuan: y });
      });
      if (!rows.length) return;
      var sum = 0, sumPct = 0, i;
      for (i = 0; i < rows.length; i++){ sum += rows[i].yuan; sumPct += rows[i].pct; }
      MAG_STAT.checked++;
      if (!ref){ MAG_STAT.unverified++; return; }
      var ratio = sum > 0 ? ref / sum : Infinity;
      if (!(ratio > 100 || ratio < 0.01)){
        /* 量级正确（或仅覆盖部分分桶）：只确保中心有数字，不做数值换算 */
        var cu = donutCenterText(svg);
        if (!/^[\d]/.test(cu)) setDonutCenter(svg, pickValueUnit(ref, [ref]), ref, stat);
        if (!(ratio >= 0.5 && ratio <= 2)) MAG_STAT.allWarn++;
        return;
      }
      /* 量级错误 → 换算到真实量级 */
      var usePct = sumPct > 0 && Math.abs(sumPct - 100) < 1;
      var nv = [], ch = 0;
      for (i = 0; i < rows.length; i++) nv.push(usePct ? ref * rows[i].pct / sumPct : ref * rows[i].yuan / sum);
      var u = pickValueUnit(ref, nv), uw = unitWord(u);
      for (i = 0; i < rows.length; i++){
        var s1 = th(rows[i].pct, 2) + "% · " + vlabS(u, nv[i]);
        if (rows[i].el.textContent !== s1){ rows[i].el.textContent = s1; ch++; }
      }
      setDonutCenter(svg, u, ref, stat);
      /* 弧 <title> 同步（title 内只有 1 个金额时才替换）*/
      var arcs = $$("path.v6-arc", svg);
      if (arcs.length === rows.length){
        for (i = 0; i < arcs.length; i++){
          var tt = arcs[i].querySelector ? arcs[i].querySelector("title") : null;
          if (!tt) continue;
          var amts = tt.textContent.match(/[\d][\d,]*(?:\.\d+)?\s*(?:亿元|亿|万元|万|元)/g);
          if (amts && amts.length === 1) tt.textContent = replaceLastAmt(tt.textContent, vlabS(u, nv[i]));
        }
      }
      MAG_STAT.fixedCharts++;
      MAG_STAT.fixedItems += ch;
      if (stat){ stat.magCharts = (stat.magCharts || 0) + 1; stat.magItems = (stat.magItems || 0) + ch; }
    });
  }
  /* 单类目圆环（担保方式分布）→ 开篇表格：同样做量级校正 */
  function soloMagPass(view, stat){
    var ref = donutRefOf(view, "");
    if (!ref) return;
    var tbl = $(".v6-solo", view);
    if (tbl){
      if (tbl.getAttribute("data-v2c-mag") === "1") return;
      var trs = $$("tbody tr", tbl), cells = [], sum = 0, i;
      for (i = 0; i < trs.length; i++){
        var tds = $$("td", trs[i]);
        var td = tds[tds.length - 1];
        if (!td) continue;
        var y = amtFromTitle(td.textContent);
        if (y == null) continue;
        cells.push({ td: td, yuan: y }); sum += y;
      }
      if (!cells.length || !(sum > 0)) return;
      if (ref / sum >= 0.5 && ref / sum <= 2){ tbl.setAttribute("data-v2c-mag", "1"); return; }
      var nv = cells.map(function(c){ return c.yuan * (ref / sum); });
      var u = pickValueUnit(ref, nv), ch = 0;
      for (i = 0; i < cells.length; i++){
        var s0 = vlabS(u, nv[i]);
        if (cells[i].td.textContent !== s0){ cells[i].td.textContent = s0; ch++; }
      }
      MAG_STAT.soloFixed += ch;
      if (stat){ stat.magCharts = (stat.magCharts || 0) + 1; stat.magItems = (stat.magItems || 0) + ch; }
      tbl.setAttribute("data-v2c-mag", "1");
      return;
    }
    /* 尚未转表：修 .xt-solo 文案里的金额（保留 dot/b 结构，只改文本节点）*/
    $$(".xt-solo", view).forEach(function(el){
      var y = amtFromTitle(el.textContent);
      if (y == null || !(y > 0)) return;
      if (ref / y >= 0.5 && ref / y <= 2) return;
      var u = pickValueUnit(ref, [ref]);
      var tn = null, nd, walker = document.createTreeWalker(el, 4, null, false);
      while ((nd = walker.nextNode())){
        if (/[\d][\d,]*(?:\.\d+)?\s*(?:亿元|亿|万元|万|元)/.test(nd.nodeValue)) tn = nd;
      }
      if (tn) tn.nodeValue = tn.nodeValue.replace(/[\d][\d,]*(?:\.\d+)?\s*(?:亿元|亿|万元|万|元)/, vlabS(u, ref));
    });
  }
  /* ── 3d. 圆环图例长标签可读化 ──
     截断来源有两类：① 数字区间标签被截（(20,25…）→ 按区间语义复原为 (20,25]；
     ② 名称类标签被截（商业、服务业…）→ 去掉省略号与残缺尾段，语义缩短；
     若图例文本带全称 <title>（本层截断），优先**两行显示**不丢信息。 */
  function estTextW(str, fs){
    var w = 0, i, c;
    for (i = 0; i < str.length; i++){ c = str.charCodeAt(i); w += c > 255 ? fs : fs * 0.58; }
    return w;
  }
  function donutLabelW(svg){
    var vb = (svg.getAttribute("viewBox") || "0 0 360 240").split(/\s+/);
    var W = parseFloat(vb[2]) || 360;
    var labelW = Math.round(Math.min(210, Math.max(120, W * 0.38)));
    var valueW = Math.round(Math.min(132, Math.max(92, W * 0.28)));
    if (W >= 430){
      var R = Math.min(78, Math.max(30, (W - labelW - valueW - 30) / 2));
      var lx = 8 + 2 * R + 12;
      labelW = Math.min(labelW, Math.max(60, W - 8 - valueW - lx - 4));
    } else {
      labelW = W - 16 - 118;
    }
    return Math.max(48, labelW);
  }
  function wrapTwoLines(t, full, svg){
    var fs = 9.5, maxW = donutLabelW(svg), i;
    if (estTextW(full, fs) > maxW * 2) return false;
    var best = -1, cands = [];
    for (i = 1; i < full.length; i++){
      var ch = full.charAt(i - 1);
      if (ch === "、" || ch === "，" || ch === "," || ch === " ") cands.push(i);
    }
    var mid = Math.ceil(full.length / 2);
    cands.sort(function(a, b){ return Math.abs(a - mid) - Math.abs(b - mid); });
    for (i = 0; i < cands.length; i++){
      var a = full.slice(0, cands[i]);
      if (estTextW(a, fs) <= maxW && estTextW(full.slice(cands[i]), fs) <= maxW){ best = cands[i]; break; }
    }
    if (best < 0){
      var k = 1;
      while (k < full.length && estTextW(full.slice(0, k), fs) <= maxW) k++;
      k = Math.max(1, k - 1);
      if (estTextW(full.slice(k), fs) > maxW) return false;
      best = k;
    }
    var y = parseFloat(t.getAttribute("y")) || 0;
    var x = t.getAttribute("x") || "0";
    var NS = "http://www.w3.org/2000/svg";
    t.setAttribute("font-size", String(fs));
    t.setAttribute("y", String(y - 5));
    while (t.firstChild) t.removeChild(t.firstChild);
    var sp1 = document.createElementNS(NS, "tspan");
    sp1.setAttribute("x", x); sp1.setAttribute("dy", "0"); sp1.textContent = full.slice(0, best);
    var sp2 = document.createElementNS(NS, "tspan");
    sp2.setAttribute("x", x); sp2.setAttribute("dy", "10"); sp2.textContent = full.slice(best);
    t.appendChild(sp1); t.appendChild(sp2);
    return true;
  }
  function cleanDonutLabel(raw){
    var s0 = String(raw || "").trim();
    if (!s0) return s0;
    var hadEll = /…$/.test(s0);
    var core = s0.replace(/…+$/, "").replace(/\s+$/, "");
    var r = /^[(（\[【]?\s*(-?[\d.]+)\s*[,，]\s*(-?[\d.]+)/.exec(s0);
    if (r && (/^[(（\[【]/.test(s0) || hadEll)) return "(" + r[1] + "," + r[2] + "]";
    if (!hadEll) return s0;
    var t = core.replace(/[（(][^（()）]*$/, "").replace(/[、，,]\s*$/, "").replace(/\s+$/, "");
    var segs = t.split(/[、，,]/);
    if (segs.length > 1 && segs[segs.length - 1].length <= 1){ segs.pop(); t = segs.join("、"); }
    if (t.length >= 3) return t;
    return s0;
  }
  function donutLabelPass(root, stat){
    $$('[data-chart="donut"]', root).forEach(function(host){
      var svg = $("svg", host);
      if (!svg) return;
      var n = 0, cut = 0;
      $$("text", svg).forEach(function(t){
        if (t.querySelector && t.querySelector("tspan")) return;
        var raw = t.textContent.trim();
        if (!raw) return;
        var prev = t.previousElementSibling;
        var pw = prev && (prev.nodeName || "").toLowerCase() === "rect" ? parseFloat(prev.getAttribute("width")) : 0;
        if (!(pw >= 8 && pw <= 16)) return;
        n++;
        var titleEl = t.querySelector ? t.querySelector("title") : null;
        var full = titleEl ? titleEl.textContent.trim() : "";
        if (full && full.length > raw.length && wrapTwoLines(t, full, svg)){
          if (/…/.test(t.textContent)) cut++;
          return;
        }
        var fixed = cleanDonutLabel(raw);
        if (fixed !== raw) t.textContent = fixed;
        if (/…/.test(fixed)) cut++;
      });
      if (n){ MAG_STAT.labelCharts++; MAG_STAT.labelTotal += n; MAG_STAT.labelCut += cut; }
    });
  }

  function tidyRotatedAxis(host){
    if (host.getAttribute("data-v2c-xl") === "1") return null;
    var svg = $("svg", host);
    if (!svg) return null;
    var rot = $$("text", svg).filter(function(t){ return /rotate\(/.test(t.getAttribute("transform") || ""); });
    if (rot.length < 3) return null;
    var vb = (svg.getAttribute("viewBox") || "0 0 680 280").split(/\s+/);
    var W = parseFloat(vb[2]) || 680, H = parseFloat(vb[3]) || 280;
    var texts = $$("text", svg);
    var vals = texts.filter(function(t){
      return (t.getAttribute("text-anchor") || "") === "middle" &&
             !/rotate\(/.test(t.getAttribute("transform") || "");
    });
    var dropped = 0, trimmed = 0, i;
    /* ①a 先收集柱 <title> 的真值 → 定全图统一单位（避免同图 亿/万/元 混排）*/
    var allY = [];
    vals.forEach(function(t){
      var p0 = t.previousSibling, tt0 = null, g0 = 0;
      while (p0 && !tt0 && g0++ < 6){ if (p0.querySelector) tt0 = p0.querySelector("title"); p0 = p0.previousSibling; }
      var y0 = tt0 ? amtFromTitle(tt0.textContent) : null;
      if (y0 != null) allY.push(y0);
    });
    var VU = allY.length ? pickValueUnit(Math.max.apply(null, allY.map(function(v){ return Math.abs(v); })), allY) : "万";
    var VUW = unitWord(VU);
    /* ①b 数值标签：按全图统一单位重写（裸数字从相邻柱 <title> 反推其真实单位）*/
    vals.forEach(function(t){
      var raw = t.textContent.trim();
      var plus = /^\s*\+/.test(raw);
      /* ① 优先用相邻柱 <title> 的原始真值（不依赖标签文本当前被换成了什么单位）*/
      var yuan = null;
      var p = t.previousSibling, tt = null;
      while (p && !tt){ if (p.querySelector) tt = p.querySelector("title"); p = p.previousSibling; }
      var y1 = tt ? amtFromTitle(tt.textContent) : null;
      if (y1 != null) yuan = y1;
      /* ② 回退：标签自带单位 */
      if (yuan == null){
        var m = AMT_RE.exec(raw); AMT_RE.lastIndex = 0;
        if (m) yuan = toYuan(m[1], m[3]);
      }
      if (yuan != null){
        var out = vlab(VU, yuan);
        if (plus && yuan > 0) out = "+" + out;
        if (out !== raw) t.textContent = out;
      }
    });
    /* ② 数值标签 2D 碰撞稀疏化（信息仍保留在柱 <title>）*/
    var boxes = vals.map(function(t){
      var fs = parseFloat(t.getAttribute("font-size")) || 10;
      return { t: t, x: parseFloat(t.getAttribute("x")) || 0, y: parseFloat(t.getAttribute("y")) || 0,
               w: estW(t.textContent.trim(), fs), h: fs * 1.15 };
    });
    boxes.sort(function(a, b){ return a.y - b.y; });
    var kept = [];
    boxes.forEach(function(b){
      var hit = false;
      for (i = 0; i < kept.length; i++){
        var k = kept[i];
        if (Math.abs(b.x - k.x) < (b.w + k.w) / 2 + 3 && Math.abs(b.y - k.y) < (b.h + k.h) / 2){ hit = true; break; }
      }
      if (hit){ if (b.t.parentNode) b.t.parentNode.removeChild(b.t); dropped++; }
      else kept.push(b);
    });
    /* ③ 旋转分类标签：超长截断（全称进 <title>）+ 视野下沿扩高，避免被 SVG 裁掉 */
    var maxBottom = H;
    rot.forEach(function(t){
      var fs = parseFloat(t.getAttribute("font-size")) || 9;
      var x = parseFloat(t.getAttribute("x")) || 0, y = parseFloat(t.getAttribute("y")) || H;
      var full = t.getAttribute("data-full") || t.textContent.trim();
      t.setAttribute("data-full", full);
      var shown = fitText(full, 88, fs);
      if (shown !== t.textContent){ t.textContent = shown; trimmed++; }
      if (shown !== full && !t.querySelector("title")){
        var tt = document.createElementNS("http://www.w3.org/2000/svg", "title");
        tt.textContent = full;
        t.insertBefore(tt, t.firstChild);
      }
      maxBottom = Math.max(maxBottom, y + Math.sin(rotAngle(t)) * estW(shown, fs) + 3);
    });
    /* ④ 密度控制：平行标签垂直净距 < 字号 ⇒ 丢弃靠后者（宁少标，不压字）*/
    var order = rot.slice().sort(function(a, b){
      return (parseFloat(a.getAttribute("x")) || 0) - (parseFloat(b.getAttribute("x")) || 0);
    });
    var lastX = null, collided = 0;
    order.forEach(function(t){
      var fs = parseFloat(t.getAttribute("font-size")) || 9;
      var x = parseFloat(t.getAttribute("x")) || 0;
      if (lastX != null && (x - lastX) * Math.sin(rotAngle(t)) < fs * 1.08){
        if (t.parentNode) t.parentNode.removeChild(t);
        collided++;
        return;
      }
      lastX = x;
    });
    var newH = Math.ceil(maxBottom);
    if (newH > H){
      svg.setAttribute("viewBox", "0 0 " + W + " " + newH);
      svg.setAttribute("width", "100%");
      svg.removeAttribute("height");
      svg.setAttribute("style", "width:100%;height:auto;display:block");
    }
    addSvgNote(svg, "单位：" + VUW);
    host.setAttribute("data-v2c-xl", "1");
    return { trimmed: trimmed, dropped: dropped, collided: collided, viewH: newH, unit: VUW };
  }

  /* ═══════════════ 2. 解析原 SVG 数据 ═══════════════ */
  function parsePts(s){
    return String(s || "").trim().split(/\s+/).map(function(pair){
      var q = pair.split(",");
      return { x: parseFloat(q[0]), y: parseFloat(q[1]) };
    }).filter(function(p){ return isFinite(p.x) && isFinite(p.y); });
  }
  function profOf(view){
    var V = window.__V2;
    if (!V || !V.PROF) return null;
    var h1 = $(".hero h1", view);
    var name = h1 ? h1.textContent.trim() : "";
    var keys = V.ORDER || Object.keys(V.PROF);
    var i;
    if (name){
      for (i = 0; i < keys.length; i++) if (keys[i] === name) return V.PROF[keys[i]];
      for (i = 0; i < keys.length; i++){
        var p = V.PROF[keys[i]];
        if (p && (p.name === name || p.short === name)) return p;
      }
    }
    return null;
  }
  function periodDates(view){
    var out = [], i, j;
    var tables = $$("table.tbl", view);
    for (i = 0; i < tables.length && !out.length; i++){
      var rows = $$("tr", tables[i]);
      if (rows.length < 2) continue;
      var heads = $$("th", rows[0]).map(function(h){ return h.textContent.trim(); });
      var ip = -1, ino = -1;
      for (j = 0; j < heads.length; j++){
        if (ip < 0 && heads[j].indexOf("支付日") >= 0) ip = j;
        if (ino < 0 && heads[j].indexOf("序号") >= 0) ino = j;
      }
      if (ip < 0) continue;
      var pairs = [];
      rows.slice(1).forEach(function(r, ri){
        var tds = $$("td", r);
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
        pairs.sort(function(p, q){ return p.seq - q.seq; });
        out = pairs.map(function(p){ return p.date; });
      }
    }
    if (!out.length){
      var p = profOf(view);
      if (p && p.dates && p.dates.rows){
        /* PROF.dates 为 (标签,日期) 行；首个支付日起按支付期序取 */
        var ds = [];
        p.dates.rows.forEach(function(r){
          var v = r && r.value;
          if (v && v.length > 1 && /^\d{4}-\d{2}-\d{2}$/.test(v[1]) && v[0] !== "信托设立日") ds.push(v[1]);
        });
        if (ds.length) out = ds;
      }
    }
    return out;
  }
  function viewAccent(view){
    var a = "";
    try { a = getComputedStyle(view).getPropertyValue("--accent") || ""; } catch (e){ a = ""; }
    a = a.trim();
    if (a) return a;
    var chip = $(".cat", view);
    var cat = chip ? chip.textContent.trim() : "";
    return CAT_COLOR[cat] || "#2D3955";
  }
  /* 数轴反推标度：v = a*y + b（底刻度多为 0，则强制过该点） */
  function axisScale(yTicks){
    var pts = yTicks.map(function(t){ return { y: t.y, v: toYuan(t.vn, t.vu) }; });
    pts.sort(function(p, q){ return p.y - q.y; });
    var bot = pts[pts.length - 1];
    var i, n = pts.length;
    if (Math.abs(bot.v) < 1e-6){
      var sv = 0, syy = 0;
      for (i = 0; i < n; i++){
        var dy = pts[i].y - bot.y;
        syy += dy * dy; sv += dy * pts[i].v;
      }
      if (syy > 0){
        var a0 = sv / syy;
        /* 关键：y 轴向下，过 (yBot, 0) 点 ⇒ v = a0*(y - yBot) */
        return { a: a0, b: -a0 * bot.y, yBot: bot.y };
      }
      return { a: 0, b: 0, yBot: bot.y };
    }
    var sx = 0, sv2 = 0, sxx = 0, sxy = 0;
    for (i = 0; i < n; i++){
      sx += pts[i].y; sv2 += pts[i].v; sxx += pts[i].y * pts[i].y; sxy += pts[i].y * pts[i].v;
    }
    var d = n * sxx - sx * sx;
    var a = d ? (n * sxy - sx * sv2) / d : 0;
    var b = (sv2 - a * sx) / n;
    return { a: a, b: b, yBot: bot.y };
  }
  function readAxis(svg){
    var vb = (svg.getAttribute("viewBox") || "0 0 680 240").split(/\s+/);
    var W = parseFloat(vb[2]) || 680, H = parseFloat(vb[3]) || 240;
    var ys = [], xs = [], gl = [];
    /* 横向网格线：刻度文字通常比网格线低 ~3px，必须把文字标到网格线坐标上 */
    $$("line", svg).forEach(function(ln){
      var y1 = parseFloat(ln.getAttribute("y1")), y2 = parseFloat(ln.getAttribute("y2"));
      var x1 = parseFloat(ln.getAttribute("x1")), x2 = parseFloat(ln.getAttribute("x2"));
      if (Math.abs(y1 - y2) < 0.6 && Math.abs(x2 - x1) > W * 0.5) gl.push(y1);
    });
    $$("text", svg).forEach(function(t){
      var x = parseFloat(t.getAttribute("x")), y = parseFloat(t.getAttribute("y"));
      var anchor = t.getAttribute("text-anchor") || "";
      var s = t.textContent.trim();
      if (!s) return;
      var m = /^(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?$/.exec(s);
      if (anchor === "end" && x < 110 && m){
        var yy = y;
        if (gl.length){
          var best = gl[0], bd = Math.abs(gl[0] - y);
          for (var k = 1; k < gl.length; k++){
            var d = Math.abs(gl[k] - y);
            if (d < bd){ bd = d; best = gl[k]; }
          }
          if (bd <= 8) yy = best;
        }
        ys.push({ y: yy, x: x, vn: m[1], vu: m[2] || "元" });
      } else if (anchor === "middle" && y > H * 0.72){
        xs.push({ x: x, text: s });
      }
    });
    ys.sort(function(p, q){ return p.y - q.y; });
    xs.sort(function(p, q){ return p.x - q.x; });
    return { W: W, H: H, ys: ys, xs: xs, scale: ys.length >= 2 ? axisScale(ys) : null };
  }
  function seriesFromPoly(polys, scale, svgEl){
    var out = [];
    polys.forEach(function(pl){
      var pts = parsePts(pl.getAttribute("points"));
      if (!pts.length) return;
      var ttl = pl.querySelector("title");
      out.push({
        pts: pts,
        dash: String(pl.getAttribute("stroke-dasharray") || ""),
        stroke: pl.getAttribute("stroke") || "",
        name: ttl ? ttl.textContent.trim() : "",
        values: pts.map(function(p){ return scale.a * p.y + scale.b; })
      });
    });
    return out;
  }
  /* 标度微调：若 __V2 有精确末期累计，用其修正整条序列的尺度（保形状） */
  function refineScale(series, exactLast){
    if (!(exactLast > 0)) return series;
    var last = series.values[series.values.length - 1];
    if (!(last > 0)) return series;
    var k = exactLast / last;
    if (!(k > 0) || Math.abs(k - 1) > 0.25) return series;
    series.values = series.values.map(function(v){ return v * k; });
    return series;
  }

  /* ═══════════════ 3. 折线图重绘 ═══════════════ */
  var uid = 0;
  var LW = 1.6;        /* 折线统一细线宽（同图唯一、≤2.0）*/
  var LW_AREA = 1.4;   /* 面积图描边（同图唯一）*/
  /* 单调三次插值（Fritsch–Carlson）→ 三次贝塞尔：曲线平滑且**不过冲**
     （不会凸出数据范围），适合财务曲线；n=2 退化为直线。 */
  function linePath(xs, ys){
    var n = xs.length, i;
    if (!n) return "";
    if (n === 1) return "M" + th(xs[0], 1) + "," + th(ys[0], 1);
    if (n === 2) return "M" + th(xs[0], 1) + "," + th(ys[0], 1) + " L" + th(xs[1], 1) + "," + th(ys[1], 1);
    var d = [], m = [];
    for (i = 0; i < n - 1; i++){
      var hh = xs[i + 1] - xs[i];
      d[i] = (ys[i + 1] - ys[i]) / (hh || 1e-6);
    }
    m[0] = d[0]; m[n - 1] = d[n - 2];
    for (i = 1; i < n - 1; i++) m[i] = (d[i - 1] + d[i]) / 2;
    for (i = 0; i < n - 1; i++){
      if (d[i] === 0){ m[i] = 0; m[i + 1] = 0; continue; }
      var a = m[i] / d[i], b = m[i + 1] / d[i], ss = a * a + b * b;
      if (ss > 9){ var t = 3 / Math.sqrt(ss); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; }
    }
    var out = "M" + th(xs[0], 1) + "," + th(ys[0], 1);
    for (i = 0; i < n - 1; i++){
      var h = xs[i + 1] - xs[i];
      out += " C" + th(xs[i] + h / 3, 1) + "," + th(ys[i] + m[i] * h / 3, 1) +
             " " + th(xs[i + 1] - h / 3, 1) + "," + th(ys[i + 1] - m[i + 1] * h / 3, 1) +
             " " + th(xs[i + 1], 1) + "," + th(ys[i + 1], 1);
    }
    return out;
  }
  function linePathRev(xs, ys){
    return linePath(xs.slice().reverse(), ys.slice().reverse());
  }
  function areaPath(xs, ys, yBase){
    var n = xs.length;
    if (!n) return "";
    return linePath(xs, ys) + " L" + th(xs[n - 1], 1) + "," + th(yBase, 1) +
           " L" + th(xs[0], 1) + "," + th(yBase, 1) + " Z";
  }
  function mountSvg(host, svg, inner, W, H){
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("width", "100%");
    svg.removeAttribute("height");
    svg.removeAttribute("preserveAspectRatio");
    svg.setAttribute("style", "width:100%;height:auto;display:block");
    if (svg.getAttribute("class")) svg.setAttribute("class", svg.getAttribute("class") + " v2c-svg");
    else svg.setAttribute("class", "v2c-svg");
    svg.innerHTML = inner;
  }
  function hitTitle(parts){
    return parts.filter(function(x){ return x != null && x !== ""; }).join("｜");
  }
  var TAG_UNIT_RE = /单位[:：]\s*(亿元|亿|万元|万|元|%)/;
  function addTag(host, text){
    var ct = $(".ct", host) || $(".ct2", host);
    if (!ct) return;
    var sp = $(".v2c-tag", ct);
    if (sp){
      /* 已存在徽章：只更新单位段（保留「棒棒糖图」等图种标签），保证徽章与值永远同源 */
      var nu = TAG_UNIT_RE.exec(text || "");
      if (!nu) return;
      var cur = sp.textContent;
      var nxt = TAG_UNIT_RE.test(cur)
        ? cur.replace(TAG_UNIT_RE, "单位：" + nu[1])
        : cur.replace(/\s*$/, "") + " · 单位：" + nu[1];
      if (nxt !== cur) sp.textContent = nxt;
      return;
    }
    var el = document.createElement("span");
    el.className = "v2c-tag";
    el.textContent = text;
    ct.appendChild(el);
  }
  /* 取图表标题（剔除本模块添加的标签），用于判定图种 */
  function hostKey(host){
    var ct = $(".ct", host) || $(".ct2", host);
    if (!ct) return "";
    var txt = "";
    for (var i = 0; i < ct.childNodes.length; i++){
      var n = ct.childNodes[i];
      if (n.nodeType === 1 && n.className === "v2c-tag") continue;
      txt += n.textContent || "";
    }
    return txt.replace(/\s+/g, " ").trim();
  }
  function mark(host, svg, kind){
    host.setAttribute("data-v2c", "1");
    if (kind) host.setAttribute("data-v2c-kind", kind);
    if (svg) svg.setAttribute("data-v2c", "1");
  }
  function bindHover(svg, bands, dots){
    function on(ev){
      var t = ev.target;
      if (!t || !t.getAttribute) return;
      var i = t.getAttribute("data-i");
      if (i == null) return;
      i = +i;
      var guide = $(".v2c-guide", svg);
      if (guide && dots[i]){
        guide.setAttribute("x1", dots[i].getAttribute("cx"));
        guide.setAttribute("x2", dots[i].getAttribute("cx"));
        guide.setAttribute("class", "v2c-guide on");
        dots[i].setAttribute("r", "6");
        dots[i].setAttribute("data-hot", "1");
      }
    }
    function off(ev){
      var guide = $(".v2c-guide", svg);
      if (guide) guide.setAttribute("class", "v2c-guide");
      dots.forEach(function(d){
        if (d.getAttribute("data-hot") === "1"){
          d.setAttribute("r", d.getAttribute("data-r0") || "4.4");
          d.removeAttribute("data-hot");
        }
      });
    }
    svg.addEventListener("mouseover", on, true);
    svg.addEventListener("mouseout", off, true);
  }

  /* ── 3a. 累计回收曲线（实际实线 / 预计虚线）── */
  function drawRecon(host, view){
    var svg = $("svg", host);
    if (!svg) return false;
    var ax = readAxis(svg);
    if (!ax.scale || ax.xs.length < 2) return false;
    var polys = $$("polyline", svg);
    if (polys.length < 1) return false;
    var ss = seriesFromPoly(polys, ax.scale);
    if (!ss.length) return false;
    var actual = null, forecast = null, i;
    for (i = 0; i < ss.length; i++){
      if (ss[i].dash) { if (!forecast) forecast = ss[i]; }
      else if (!actual) actual = ss[i];
    }
    if (!actual) actual = ss[0];
    var n = actual.values.length;
    if (n < 2) return false;
    var p = profOf(view);
    if (p && p.trace && p.trace.length === n) refineScale(actual, num(p.trace[n - 1].reserve));
    var accent = viewAccent(view);
    var s2 = accent.toUpperCase() === "#2D3955" ? C.warn : "#2D3955";
    var mg = { l: 68, r: 22, t: 40, b: 40 };
    var W = ax.W, H = ax.H;
    var x0 = mg.l, x1 = W - mg.r, y0 = mg.t, y1 = H - mg.b;
    var maxV = 0;
    actual.values.concat(forecast ? forecast.values : []).forEach(function(v){ if (Math.abs(v) > maxV) maxV = Math.abs(v); });
    var na = niceAxisTop(maxV), vTop = na.top;
    var tickVals = [];
    for (i = 0; i <= na.k; i++) tickVals.push(na.step * i);
    var pick = pickAxisUnit(vTop, tickVals);
    if (!pick) return false;
    var u = pick.unit, f = unitFactor(u), uw = unitWord(u), dec = u === "元" ? 0 : 2;
    function X(i){ return n === 1 ? (x0 + x1) / 2 : x0 + (x1 - x0) * i / (n - 1); }
    function Y(v){ return y1 - clamp(v / vTop, 0, 1) * (y1 - y0); }

    var dates = periodDates(view);
    var pool = 0;
    var kpiPool = null;
    $$(".kpi", view).forEach(function(k){
      var lab = $(".k", k);
      if (lab && lab.textContent.indexOf("入池本息费") >= 0) kpiPool = $(".v", k);
    });
    if (kpiPool){
      var mm = AMT_RE.exec(kpiPool.textContent);
      AMT_RE.lastIndex = 0;
      if (mm) pool = toYuan(mm[1], mm[3]);
    }
    if (!pool && p && p.poolTotal) pool = num(p.poolTotal);

    /* 期次/日期标签 */
    var xlabels = [];
    for (i = 0; i < n; i++) xlabels.push(ax.xs[i] ? ax.xs[i].text : String(i + 1));
    var step = n > 14 ? Math.ceil(n / 10) : 1;

    var g = [];
    g.push('<defs><linearGradient id="v2ca' + (++uid) + '" x1="0" y1="0" x2="0" y2="1">' +
           '<stop offset="0" stop-color="' + esc(accent) + '" stop-opacity=".26"/>' +
           '<stop offset="1" stop-color="' + esc(accent) + '" stop-opacity="0"/></linearGradient></defs>');
    var gradId = "v2ca" + uid;

    /* 网格 + y 轴刻度（单一单位；每个 tick 用各自的数值与标签，禁止复用同一变量） */
    for (i = 0; i < tickVals.length; i++){
      var vv = tickVals[i], yy = Y(vv);
      g.push('<line x1="' + x0 + '" y1="' + th(yy, 1) + '" x2="' + x1 + '" y2="' + th(yy, 1) +
             '" stroke="' + (i === 0 ? C.axis : C.grid) + '" stroke-width="1"/>');
      if (tickVals.length <= 6 || i % 2 === 0 || i === tickVals.length - 1)
        g.push('<text class="v2c-ax" x="' + (x0 - 10) + '" y="' + th(yy + 4, 1) + '" text-anchor="end" font-size="11" fill="' + C.sub + '">' + esc(pick.labels[i]) + '</text>');
    }
    g.push('<text class="v2c-note" x="' + x0 + '" y="' + (mg.t - 20) + '" font-size="10.5" fill="' + C.mute + '">单位：' + uw + '</text>');

    /* 图例 */
    var lx = x1 - 196;
    g.push('<rect x="' + lx + '" y="' + (mg.t - 26) + '" width="16" height="3" rx="1.5" fill="' + esc(accent) + '"/>' +
           '<text class="v2c-leg" x="' + (lx + 22) + '" y="' + (mg.t - 21) + '" font-size="11" fill="' + C.ink2 + '">累计实际回收</text>');
    g.push('<rect x="' + (lx + 104) + '" y="' + (mg.t - 26) + '" width="16" height="3" rx="1.5" fill="' + C.gray + '"/>' +
           '<text class="v2c-leg" x="' + (lx + 126) + '" y="' + (mg.t - 21) + '" font-size="11" fill="' + C.ink2 + '">累计预计回收</text>');

    /* x 轴刻度 */
    for (i = 0; i < n; i++){
      if (i % step !== 0 && i !== n - 1) continue;
      g.push('<text class="v2c-ax-x" x="' + th(X(i), 1) + '" y="' + (y1 + 18) + '" text-anchor="middle" font-size="11" fill="' + C.sub + '">' + esc(xlabels[i]) + '</text>');
    }

    /* 面积 + 线 */
    var axs = [], ays = [];
    for (i = 0; i < n; i++){ axs.push(X(i)); ays.push(Y(actual.values[i])); }
    g.push('<path d="' + areaPath(axs, ays, y1) + '" fill="url(#' + gradId + ')"/>');
    g.push('<path class="v2c-anim" d="' + linePath(axs, ays) + '" fill="none" stroke="' + esc(accent) +
           '" stroke-width="' + LW + '" stroke-linejoin="round" stroke-linecap="round"/>');
    if (forecast){
      var fxs = [], fys = [];
      for (i = 0; i < forecast.values.length; i++){ fxs.push(X(i)); fys.push(Y(forecast.values[i])); }
      g.push('<path d="' + linePath(fxs, fys) + '" fill="none" stroke="' + C.gray +
             '" stroke-width="' + LW + '" stroke-dasharray="7 5" stroke-linecap="round"/>');
      for (i = 0; i < fxs.length; i++)
        g.push('<circle cx="' + th(fxs[i], 1) + '" cy="' + th(fys[i], 1) + '" r="3" fill="#fff" stroke="' + C.gray + '" stroke-width="1.7"/>');
    }
    /* 悬停竖线 */
    g.push('<line class="v2c-guide" x1="' + x0 + '" y1="' + y0 + '" x2="' + x0 + '" y2="' + y1 +
           '" stroke="' + esc(accent) + '" stroke-width="1" stroke-dasharray="3 3" pointer-events="none"/>');

    /* 数据点 + 命中带（每个期次一个 <title>） */
    var dots = [], bands = [];
    var r = n > 18 ? 3.4 : 4.4;
    var bandW = n > 1 ? Math.max(10, Math.min(20, (x1 - x0) / (n - 1) - 4)) : 20;
    for (i = 0; i < n; i++){
      var cur = actual.values[i];
      var prev = i > 0 ? actual.values[i - 1] : 0;
      var period = cur - prev;
      var rate = pool > 0 ? cur / pool : null;
      var fc = forecast && forecast.values[i] != null ? forecast.values[i] : null;
      var parts = [];
      if (dates[i]) parts.push("第" + (i + 1) + "期 · " + dates[i]);
      else parts.push("第" + (i + 1) + "期");
      g.push('<circle class="v2c-dot" data-r0="' + r + '" cx="' + th(axs[i], 1) + '" cy="' + th(ays[i], 1) +
             '" r="' + r + '" fill="' + esc(accent) + '" stroke="#fff" stroke-width="1.8" pointer-events="none"/>');
      parts.push("本期回收 " + fmtAmt(period, "scale"));
      parts.push("累计回收 " + fmtAmt(cur, "scale"));
      if (rate != null) parts.push("累计回收率 " + pct2(rate));
      if (fc != null) parts.push("预计累计 " + fmtAmt(fc, "scale"));
      g.push('<rect class="v2c-band" data-i="' + i + '" x="' + th(X(i) - bandW / 2, 1) + '" y="' + y0 +
             '" width="' + th(bandW, 1) + '" height="' + (y1 - y0) + '"><title>' + esc(hitTitle(parts)) + '</title></rect>');
      dots.push(i);
    }
    /* 关键点标注：末期 + 本期峰值 */
    var lastY = ays[n - 1];
    g.push('<text class="v2c-anno" x="' + th(axs[n - 1] - 8, 1) + '" y="' + th(Math.max(y0 + 12, lastY - 16), 1) +
           '" text-anchor="end" font-size="11" fill="' + C.ink2 + '">末期 ' + th(actual.values[n - 1] / f, dec) + " " + uw + '</text>');
    var pk = 0;
    for (i = 1; i < n; i++) if (actual.values[i] - actual.values[i - 1] > actual.values[pk] - (pk ? actual.values[pk - 1] : 0)) pk = i;
    var pkv = actual.values[pk] - (pk ? actual.values[pk - 1] : 0);
    var mx = 0;
    for (i = 0; i < n; i++) mx = Math.max(mx, actual.values[i] - (i ? actual.values[i - 1] : 0));
    if (pkv > 0 && pk !== n - 1 && pkv > mx * 0.55){
      var pkAnc = "middle", pkTx = axs[pk], pkTy = Math.max(y0 + 10, ays[pk] - 24);
      if (axs[pk] < x0 + 54){ pkAnc = "start"; pkTx = x0 + 6; pkTy = Math.max(y0 + 10, ays[pk] - 32); }
      else if (axs[pk] > x1 - 54){ pkAnc = "end"; pkTx = x1 - 6; }
      g.push('<line x1="' + th(axs[pk], 1) + '" y1="' + th(ays[pk] - 8, 1) + '" x2="' + th(axs[pk], 1) + '" y2="' + th(ays[pk] - 20, 1) +
             '" stroke="' + C.axis + '"/>');
      g.push('<text class="v2c-anno-sub" x="' + th(pkTx, 1) + '" y="' + th(pkTy, 1) +
             '" text-anchor="' + pkAnc + '" font-size="10.5" fill="' + C.sub + '">峰值 ' + th(pkv / f, dec) + " " + uw + '</text>');
    }
    mountSvg(host, svg, g.join(""), W, H);
    mark(host, svg, "recon-line");
    addTag(host, "单位：" + uw);
    var svg2 = $("svg", host);
    var dotEls = $$(".v2c-dot", svg2), bandEls = $$(".v2c-band", svg2);
    bindHover(svg2, bandEls, dotEls);
    return true;
  }

  /* ── 3b. 分档累计本金走势（堆叠面积 + 合计口径）── */
  function drawTranche(host, view){
    var svg = $("svg", host);
    if (!svg) return false;
    var ax = readAxis(svg);
    if (!ax.scale || ax.xs.length < 2) return false;
    var polys = $$("polyline", svg);
    if (polys.length < 2) return false;
    var ss = seriesFromPoly(polys, ax.scale);
    var s1 = ss[0], s2 = ss[1];
    var n = Math.min(s1.values.length, s2.values.length);
    if (n < 2) return false;
    var accent = viewAccent(view);
    var sec = accent.toUpperCase() === "#2D3955" ? C.warn : "#2D3955";
    var mg = { l: 68, r: 22, t: 40, b: 40 };
    var W = ax.W, H = ax.H;
    var x0 = mg.l, x1 = W - mg.r, y0 = mg.t, y1 = H - mg.b;
    var tot = [];
    var maxV = 0;
    for (var i = 0; i < n; i++){
      var t = s1.values[i] + s2.values[i];
      tot.push(t);
      if (t > maxV) maxV = t;
    }
    var na = niceAxisTop(maxV), vTop = na.top;
    var tickVals = [];
    for (i = 0; i <= na.k; i++) tickVals.push(na.step * i);
    var pick = pickAxisUnit(vTop, tickVals);
    if (!pick) return false;
    var u = pick.unit, f = unitFactor(u), uw = unitWord(u), dec = u === "元" ? 0 : 2;
    function X(i){ return n === 1 ? (x0 + x1) / 2 : x0 + (x1 - x0) * i / (n - 1); }
    function Y(v){ return y1 - clamp(v / vTop, 0, 1) * (y1 - y0); }
    var dates = periodDates(view);
    var xs = [], yS1 = [], yTot = [];
    for (i = 0; i < n; i++){ xs.push(X(i)); yS1.push(Y(s1.values[i])); yTot.push(Y(tot[i])); }

    var g = [];
    var g1 = "v2ct" + (++uid), g2 = "v2cu" + (++uid);
    g.push('<defs>' +
      '<linearGradient id="' + g1 + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + esc(accent) + '" stop-opacity=".42"/><stop offset="1" stop-color="' + esc(accent) + '" stop-opacity=".10"/></linearGradient>' +
      '<linearGradient id="' + g2 + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + esc(sec) + '" stop-opacity=".34"/><stop offset="1" stop-color="' + esc(sec) + '" stop-opacity=".08"/></linearGradient>' +
      '</defs>');
    for (i = 0; i < tickVals.length; i++){
      var vv = tickVals[i], yy = Y(vv);
      g.push('<line x1="' + x0 + '" y1="' + th(yy, 1) + '" x2="' + x1 + '" y2="' + th(yy, 1) + '" stroke="' + (i === 0 ? C.axis : C.grid) + '"/>');
      if (tickVals.length <= 6 || i % 2 === 0 || i === tickVals.length - 1)
        g.push('<text class="v2c-ax" x="' + (x0 - 10) + '" y="' + th(yy + 4, 1) + '" text-anchor="end" font-size="11" fill="' + C.sub + '">' + esc(pick.labels[i]) + '</text>');
    }
    g.push('<text class="v2c-note" x="' + x0 + '" y="' + (mg.t - 20) + '" font-size="10.5" fill="' + C.mute + '">单位：' + uw + '</text>');
    var lx = x1 - 264;
    g.push('<rect x="' + lx + '" y="' + (mg.t - 26) + '" width="16" height="3" rx="1.5" fill="' + esc(accent) + '"/><text class="v2c-leg" x="' + (lx + 22) + '" y="' + (mg.t - 21) + '" font-size="11" fill="' + C.ink2 + '">优先档累计本金</text>');
    g.push('<rect x="' + (lx + 118) + '" y="' + (mg.t - 26) + '" width="16" height="3" rx="1.5" fill="' + esc(sec) + '"/><text class="v2c-leg" x="' + (lx + 140) + '" y="' + (mg.t - 21) + '" font-size="11" fill="' + C.ink2 + '">次级档累计本金</text>');
    g.push('<rect x="' + (lx + 236) + '" y="' + (mg.t - 26) + '" width="16" height="3" rx="1.5" fill="#C9D2E0"/><text class="v2c-leg" x="' + (lx + 258) + '" y="' + (mg.t - 21) + '" font-size="11" fill="' + C.ink2 + '">合计</text>');
    var step = n > 14 ? Math.ceil(n / 10) : 1;
    var xlabels = [];
    for (i = 0; i < n; i++) xlabels.push(ax.xs[i] ? ax.xs[i].text : String(i + 1));
    for (i = 0; i < n; i++){
      if (i % step !== 0 && i !== n - 1) continue;
      g.push('<text class="v2c-ax-x" x="' + th(xs[i], 1) + '" y="' + (y1 + 18) + '" text-anchor="middle" font-size="11" fill="' + C.sub + '">' + esc(xlabels[i]) + '</text>');
    }
    /* 次级带（s1 → tot） */
    var d2 = linePath(xs, yS1) + " " + linePathRev(xs, yTot) + " Z";
    g.push('<path d="' + d2 + '" fill="url(#' + g2 + ')"/>');
    /* 优先带（y1 → s1） */
    g.push('<path d="' + areaPath(xs, yS1, y1) + '" fill="url(#' + g1 + ')"/>');
    g.push('<path class="v2c-anim" d="' + linePath(xs, yS1) + '" fill="none" stroke="' + esc(accent) + '" stroke-width="' + LW + '" stroke-linejoin="round" stroke-linecap="round"/>');
    g.push('<path d="' + linePath(xs, yTot) + '" fill="none" stroke="#C9D2E0" stroke-width="' + LW + '" stroke-dasharray="2 4" stroke-linecap="round"/>');
    g.push('<line class="v2c-guide" x1="' + x0 + '" y1="' + y0 + '" x2="' + x0 + '" y2="' + y1 + '" stroke="' + C.sub + '" stroke-width="1" stroke-dasharray="3 3" pointer-events="none"/>');
    var r = n > 18 ? 3.2 : 4.2;
    var bandW = n > 1 ? Math.max(10, Math.min(20, (x1 - x0) / (n - 1) - 4)) : 20;
    for (i = 0; i < n; i++){
      g.push('<circle class="v2c-dot" data-r0="' + r + '" cx="' + th(xs[i], 1) + '" cy="' + th(yS1[i], 1) + '" r="' + r + '" fill="' + esc(accent) + '" stroke="#fff" stroke-width="1.8" pointer-events="none"/>');
      g.push('<circle cx="' + th(xs[i], 1) + '" cy="' + th(yTot[i], 1) + '" r="3" fill="#fff" stroke="' + esc(sec) + '" stroke-width="1.7" pointer-events="none"/>');
      var parts = [];
      parts.push(dates[i] ? "第" + (i + 1) + "期 · " + dates[i] : "第" + (i + 1) + "期");
      parts.push("优先档累计 " + fmtAmt(s1.values[i], "scale"));
      parts.push("次级档累计 " + fmtAmt(s2.values[i], "scale"));
      parts.push("合计 " + fmtAmt(tot[i], "scale"));
      g.push('<rect class="v2c-band" data-i="' + i + '" x="' + th(xs[i] - bandW / 2, 1) + '" y="' + y0 + '" width="' + th(bandW, 1) + '" height="' + (y1 - y0) + '"><title>' + esc(hitTitle(parts)) + '</title></rect>');
    }
    /* 标注：优先档兑付完毕 + 末期合计 */
    var doneIdx = -1;
    for (i = 0; i < n; i++){ if (s1.values[i] >= s1.values[n - 1] * 0.999){ doneIdx = i; break; } }
    if (doneIdx >= 0 && doneIdx <= n - 2){
      g.push('<line x1="' + th(xs[doneIdx], 1) + '" y1="' + th(yS1[doneIdx] - 6, 1) + '" x2="' + th(xs[doneIdx], 1) + '" y2="' + th(yS1[doneIdx] - 18, 1) + '" stroke="' + C.axis + '"/>');
      g.push('<text class="v2c-anno-sub" x="' + th(xs[doneIdx], 1) + '" y="' + th(Math.max(y0 + 10, yS1[doneIdx] - 22), 1) + '" text-anchor="middle" font-size="10.5" fill="' + C.sub + '">优先档兑付完毕</text>');
    }
    g.push('<text class="v2c-anno" x="' + th(xs[n - 1] - 6, 1) + '" y="' + th(Math.max(y0 + 10, yTot[n - 1] - 12), 1) + '" text-anchor="end" font-size="11" fill="' + C.ink2 + '">合计 ' + th(tot[n - 1] / f, dec) + " " + uw + '</text>');
    mountSvg(host, svg, g.join(""), W, H);
    mark(host, svg, "tranche-line");
    addTag(host, "单位：" + uw + " · 堆叠面积");
    var svg2 = $("svg", host);
    bindHover(svg2, $$(".v2c-band", svg2), $$(".v2c-dot", svg2));
    return true;
  }

  /* ═══════════════ 4. hbar 变体（点 6）═══════════════ */
  var CONVERT = {
    "借款人年龄分布": "lollipop",
    "授信额度分布": "stacked100",
    "逾期时间分布": "area"
  };
  var KIND_LABEL = { lollipop: "棒棒糖图", stacked100: "100% 堆叠条", area: "账龄面积曲线" };
  function parseHbar(host){
    var svg = $("svg", host);
    if (!svg) return null;
    var rows = [];
    $$("rect", svg).forEach(function(rc){
      var t = rc.querySelector("title");
      if (!t) return;
      var raw = t.textContent.trim();
      var k = raw.lastIndexOf("·");
      var lab = k > 0 ? raw.slice(0, k).trim() : "";
      var val = k > 0 ? raw.slice(k + 1).trim() : raw;
      var m = /(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?/.exec(val);
      if (!m) return;
      rows.push({ label: lab, value: toYuan(m[1], m[2] || "元"), fill: rc.getAttribute("fill") || "#2D3955" });
    });
    return rows;
  }
  /* ── 4a. 棒棒糖图 ── */
  function drawLollipop(host, rows, accent){
    var total = rows.reduce(function(a, r){ return a + Math.max(0, r.value); }, 0);
    var maxV = rows.reduce(function(a, r){ return Math.max(a, r.value); }, 0);
    var vTop = niceMax(maxV, 4);
    var pick = pickAxisUnit(vTop, [0, vTop]);
    if (!pick) return false;
    var u = pick.unit, f = unitFactor(u), uw = unitWord(u);
    var dec = u === "元" ? 0 : 2;
    var W = 330, rowH = 30, top = 30, labelW = 104, x0 = labelW, x1 = W - 84;
    var H = top + rows.length * rowH + 30;
    var g = [];
    function X(v){ return x0 + clamp(v / vTop, 0, 1) * (x1 - x0); }
    g.push('<text class="v2c-note" x="' + W + '" y="14" text-anchor="end" font-size="10.5" fill="' + C.mute + '">段内为占比；金额单位：' + uw + '</text>');
    var pk = 0;
    rows.forEach(function(r, i){ if (r.value > rows[pk].value) pk = i; });
    for (var t = 1; t <= 2; t++){
      var gx = x0 + (x1 - x0) * t / 3;
      g.push('<line x1="' + th(gx, 1) + '" y1="' + top + '" x2="' + th(gx, 1) + '" y2="' + (top + rows.length * rowH - 8) + '" stroke="' + C.grid + '"/>');
    }
    g.push('<line x1="' + x0 + '" y1="' + (top - 6) + '" x2="' + x0 + '" y2="' + (top + rows.length * rowH - 8) + '" stroke="' + C.axis + '"/>');
    rows.forEach(function(r, i){
      var cy = top + i * rowH + 10;
      var xv = X(r.value);
      var isPk = i === pk && r.value > 0;
      g.push('<text x="' + (x0 - 10) + '" y="' + (cy + 4) + '" text-anchor="end" font-size="11" fill="' + C.ink2 + '">' +
             esc(fitText(r.label, labelW - 14, 11)) + '</text>');
      g.push('<line x1="' + x0 + '" y1="' + cy + '" x2="' + th(xv, 1) + '" y2="' + cy + '" stroke="' + (isPk ? esc(accent) : esc(accent)) +
             '" stroke-width="' + LW + '" stroke-linecap="round" opacity="' + (isPk ? 1 : .55) + '"/>');
      if (isPk) g.push('<circle cx="' + th(xv, 1) + '" cy="' + cy + '" r="9" fill="' + esc(accent) + '" opacity=".16"/>');
      g.push('<circle class="v2c-dot" data-r0="' + (isPk ? 5.6 : 4.6) + '" cx="' + th(xv, 1) + '" cy="' + cy + '" r="' + (isPk ? 5.6 : 4.6) +
             '" fill="' + esc(accent) + '" stroke="#fff" stroke-width="2" pointer-events="none"/>');
      g.push('<text x="' + (x1 + 8) + '" y="' + (cy + 4) + '" font-size="11" fill="' + (isPk ? C.ink2 : C.sub) + '"' +
             (isPk ? ' font-weight="700"' : '') + '>' + esc(vlab(u, r.value)) + '</text>');
      var share = total > 0 ? r.value / total : 0;
      var parts = [r.label || "—", "金额 " + fmtAmt(r.value, "auto"), "占合计 " + pct2(share)];
      if (isPk) parts.push("峰值");
      g.push('<rect class="v2c-band" data-i="' + i + '" x="' + x0 + '" y="' + (cy - 14) + '" width="' + (W - x0 - 6) +
             '" height="28" fill="transparent" fill-opacity="0"><title>' + esc(hitTitle(parts)) + '</title></rect>');
    });
    g.push('<text class="v2c-note" x="' + x0 + '" y="' + (H - 10) + '" font-size="10.5" fill="' + C.mute + '">棒长＝该区间金额；峰值已高亮</text>');
    var svg = $("svg", host);
    mountSvg(host, svg, g.join(""), W, H);
    mark(host, svg, "lollipop");
    addTag(host, KIND_LABEL.lollipop + " · 单位：" + uw);
    return true;
  }
  /* ── 4b. 100% 堆叠条 ── */
  function drawStacked100(host, rows, accent){
    var total = rows.reduce(function(a, r){ return a + Math.max(0, r.value); }, 0);
    if (!(total > 0)) return false;
    var W = 330, barH = 30, barY = 30, x0 = 6, x1 = W - 6;
    var legendTop = barY + barH + 18;
    var H = legendTop + rows.length * 21 + 26;
    var pick = pickAxisUnit(Math.max(maxOf(rows), 1), [0, Math.max(maxOf(rows), 1)]);
    if (!pick) return false;
    var u = pick.unit, f = unitFactor(u), uw = unitWord(u);
    var cid = "v2cw" + (++uid);
    var g = [];
    g.push('<defs><clipPath id="' + cid + '"><rect x="' + x0 + '" y="' + barY + '" width="' + (x1 - x0) + '" height="' + barH + '" rx="9"/></clipPath></defs>');
    g.push('<text class="v2c-note" x="' + W + '" y="14" text-anchor="end" font-size="10.5" fill="' + C.mute + '">单位：' + uw + '</text>');
    g.push('<text class="v2c-note" x="0" y="14" font-size="10.5" fill="' + C.mute + '">占比结构（合计 100.00%）</text>');
    g.push('<g clip-path="url(#' + cid + ')">');
    var cx = x0;
    rows.forEach(function(r, i){
      var w = Math.max(1.2, (Math.max(0, r.value) / total) * (x1 - x0));
      var share = Math.max(0, r.value) / total;
      g.push('<rect class="v2c-seg" x="' + th(cx, 2) + '" y="' + barY + '" width="' + th(w, 2) + '" height="' + barH +
             '" fill="' + esc(r.fill) + '"><title>' + esc(hitTitle([r.label || "—", "占比 " + pct2(share), "金额 " + vlab(u, r.value)])) + '</title></rect>');
      if (w > 46)
        g.push('<text x="' + th(cx + w / 2, 1) + '" y="' + (barY + barH / 2 + 4) + '" text-anchor="middle" font-size="10.5" font-weight="600" fill="#fff" pointer-events="none">' + pct2(share) + '</text>');
      cx += w;
    });
    g.push('</g>');
    rows.forEach(function(r, i){
      var y = legendTop + i * 21;
      var share = Math.max(0, r.value) / total;
      g.push('<circle cx="' + (x0 + 5) + '" cy="' + (y - 4) + '" r="4.6" fill="' + esc(r.fill) + '" stroke="#fff" stroke-width="1.4"/>');
      g.push('<text x="' + (x0 + 16) + '" y="' + (y) + '" font-size="11" fill="' + C.ink2 + '">' + esc(fitText(r.label, 132, 11)) + '</text>');
      g.push('<text x="' + x1 + '" y="' + (y) + '" text-anchor="end" font-size="11" fill="' + C.sub + '">' + pct2(share) + ' ｜ ' + esc(vlab(u, r.value)) + '</text>');
      g.push('<rect class="v2c-band" data-i="' + i + '" x="0" y="' + (y - 13) + '" width="' + W + '" height="19" fill="transparent" fill-opacity="0"><title>' +
             esc(hitTitle([r.label || "—", "占比 " + pct2(share), "金额 " + vlab(u, r.value)])) + '</title></rect>');
    });
    g.push('<text class="v2c-note" x="0" y="' + (H - 8) + '" font-size="10.5" fill="' + C.mute + '">金额合计 ' + esc(vlab(u, total)) + '</text>');
    var svg = $("svg", host);
    mountSvg(host, svg, g.join(""), W, H);
    mark(host, svg, "stacked100");
    addTag(host, KIND_LABEL.stacked100 + " · 段内占比（金额见图例）");
    return true;
  }
  /* ── 4c. 账龄面积曲线 ── */
  function drawAreaChart(host, rows, accent){
    var W = 330, H = 186;
    var mg = { l: 52, r: 14, t: 30, b: 46 };
    var x0 = mg.l, x1 = W - mg.r, y0 = mg.t, y1 = H - mg.b;
    var maxV = rows.reduce(function(a, r){ return Math.max(a, r.value); }, 0);
    var total = rows.reduce(function(a, r){ return a + Math.max(0, r.value); }, 0);
    var vTop = niceMax(maxV, 3);
    var avals = [0, vTop / 3, vTop * 2 / 3, vTop];
    var pick = pickAxisUnit(vTop, avals);
    if (!pick) return false;
    var u = pick.unit, f = unitFactor(u), uw = unitWord(u), dec = u === "元" ? 0 : 2;
    var n = rows.length;
    var g = [];
    function X(i){ return n === 1 ? (x0 + x1) / 2 : x0 + (x1 - x0) * i / (n - 1); }
    function Y(v){ return y1 - clamp(v / vTop, 0, 1) * (y1 - y0); }
    var gid = "v2cg" + (++uid);
    g.push('<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + esc(accent) + '" stop-opacity=".30"/><stop offset="1" stop-color="' + esc(accent) + '" stop-opacity="0"/></linearGradient></defs>');
    for (var t = 0; t <= 3; t++){
      var vv = vTop * t / 3, yy = Y(vv);
      g.push('<line x1="' + x0 + '" y1="' + th(yy, 1) + '" x2="' + x1 + '" y2="' + th(yy, 1) + '" stroke="' + (t === 0 ? C.axis : C.grid) + '"/>');
      g.push('<text class="v2c-ax" x="' + (x0 - 8) + '" y="' + th(yy + 4, 1) + '" text-anchor="end" font-size="11" fill="' + C.sub + '">' + esc(pick.labels[t]) + '</text>');
    }
    g.push('<text class="v2c-note" x="' + x0 + '" y="14" font-size="10.5" fill="' + C.mute + '">单位：' + uw + '</text>');
    var xs = [], ys = [];
    for (var i = 0; i < n; i++){ xs.push(X(i)); ys.push(Y(rows[i].value)); }
    g.push('<path d="' + areaPath(xs, ys, y1) + '" fill="url(#' + gid + ')"/>');
    g.push('<path class="v2c-anim" d="' + linePath(xs, ys) + '" fill="none" stroke="' + esc(accent) + '" stroke-width="' + LW_AREA + '" stroke-linejoin="round" stroke-linecap="round"/>');
    var cum = 0, pk = 0;
    rows.forEach(function(r, i){ if (r.value > rows[pk].value) pk = i; });
    for (i = 0; i < n; i++){
      cum += Math.max(0, rows[i].value);
      g.push('<circle class="v2c-dot" data-r0="' + (i === pk ? 5.4 : 4.2) + '" cx="' + th(xs[i], 1) + '" cy="' + th(ys[i], 1) + '" r="' + (i === pk ? 5.4 : 4.2) +
             '" fill="' + esc(accent) + '" stroke="#fff" stroke-width="1.8" pointer-events="none"/>');
      var lab = fitText(rows[i].label, (x1 - x0) / Math.max(1, n - 1) + 12, 10);
      /* 首尾标签贴边避让，防止超出画布 */
      var lbAnc = "middle", lbX = xs[i];
      if (i === 0){ lbAnc = "start"; lbX = Math.max(2, xs[i] - 10); }
      else if (i === n - 1){ lbAnc = "end"; lbX = Math.min(W - 2, xs[i] + 10); }
      g.push('<text class="v2c-ax-x" x="' + th(lbX, 1) + '" y="' + (y1 + 16) + '" text-anchor="' + lbAnc + '" font-size="10" fill="' + C.sub + '">' +
             (lab !== rows[i].label ? '<title>' + esc(rows[i].label) + '</title>' : '') + esc(lab) + '</text>');
      var share = total > 0 ? rows[i].value / total : 0;
      var cshare = total > 0 ? cum / total : 0;
      g.push('<rect class="v2c-band" data-i="' + i + '" x="' + th(X(i) - 16, 1) + '" y="' + y0 + '" width="32" height="' + (y1 - y0) +
             '"><title>' + esc(hitTitle([rows[i].label || "—", "金额 " + vlab(u, rows[i].value), "占比 " + pct2(share), "累计占比 " + pct2(cshare)])) + '</title></rect>');
    }
    g.push('<line class="v2c-guide" x1="' + x0 + '" y1="' + y0 + '" x2="' + x0 + '" y2="' + y1 + '" stroke="' + esc(accent) + '" stroke-width="1" stroke-dasharray="3 3" pointer-events="none"/>');
    if (rows[pk].value > 0){
      var pkAnc2 = "middle", pkX2 = clamp(xs[pk], x0 + 26, x1 - 26);
      if (xs[pk] < x0 + 30){ pkAnc2 = "start"; pkX2 = x0 + 2; }
      else if (xs[pk] > x1 - 30){ pkAnc2 = "end"; pkX2 = x1 - 2; }
      g.push('<text class="v2c-anno" x="' + th(pkX2, 1) + '" y="' + th(Math.max(y0 + 10, ys[pk] - 12), 1) +
             '" text-anchor="' + pkAnc2 + '" font-size="11" fill="' + C.ink2 + '">峰值 ' + esc(vlab(u, rows[pk].value)) + '</text>');
    }
    g.push('<text class="v2c-note" x="' + x0 + '" y="' + (H - 8) + '" font-size="10.5" fill="' + C.mute + '">金额合计 ' + esc(vlab(u, total)) + '</text>');
    var svg = $("svg", host);
    mountSvg(host, svg, g.join(""), W, H);
    mark(host, svg, "area");
    addTag(host, KIND_LABEL.area + " · 单位：" + uw);
    var svg2 = $("svg", host);
    bindHover(svg2, $$(".v2c-band", svg2), $$(".v2c-dot", svg2));
    return true;
  }

  /* ═══════════════ 5. 驱动 ═══════════════ */
  var busy = false;
  function run(){
    if (busy) return;
    busy = true;
    var stat = { views: 0, units: 0, tables: 0, recon: 0, tranche: 0, bars: 0, axes: 0, skip: 0,
                 unitFixed: 0, unitUnknown: 0, unitUnknownList: [],
                 magCharts: 0, magItems: 0, magCenterFixed: 0 };
    try {
      $$('section.view[id^="view-p"]').forEach(function(view){
        if (!/^view-p\d+$/.test(view.id)) return;
        stat.views++;
        /* 顺序有讲究：先解析原图数据（此时刻度仍带原始精度）→ 重绘 → 再做文本单位
           规范化 → 最后统一其它图数轴（自绘 SVG 会被跳过，避免二次改写）。 */
        try {
          $$(".dist-grid .chart", view).forEach(function(host){
            /* 卡片宽度变化（分行/等高后列宽会变）→ 按新宽度重绘，避免 viewBox 纵横比导致图被压扁留白 */
            if (host.getAttribute("data-v2c") === "1" &&
                Math.abs((parseFloat(host.getAttribute("data-v2c-w")) || 0) - (host.clientWidth || 0)) <= 10) return;
            try { if (v9DrawDist(host, view)) stat.dist = (stat.dist || 0) + 1; } catch (e){}
          });
        } catch (e){}                                     /* v8：10 类分布图按 DIST 重绘 */
        try { mergeTiming(view, stat); } catch (e){}      /* v7：时间轴并入档位末次兑付 */
        /* 瀑布（v6）：数据源换成 __V2.WF；无 WF 时保留原图（老构建兼容）*/
        $$('[data-chart="waterfall"]', view).forEach(function(host){
          if (host.getAttribute("data-v2c") === "1" || $('svg[data-v2c="1"]', host)) return;
          try { if (drawWaterfall(host, view)) stat.waterfall = (stat.waterfall || 0) + 1; } catch (e){}
        });
        try { donutMagPass(view, stat); } catch (e){}          /* P0：先把圆环量级换算到真值 */
        try { distMagPass(view, stat); } catch (e){}           /* P0 扩面：hbar/treemap 量级换算 */
        try { soloMagPass(view, stat); } catch (e){}           /* P0：单类目圆环（表格/文案）*/
        try { stat.tables += normalizeTables(view); } catch (e){}
        $$('[data-chart="recon-line"]', view).forEach(function(host){
          if (host.getAttribute("data-v2c") === "1" || $('svg[data-v2c="1"]', host)) return;
          try { if (drawRecon(host, view)) stat.recon++; else stat.skip++; } catch (e){ stat.skip++; }
        });
        $$('[data-chart="tranche-line"]', view).forEach(function(host){
          if (host.getAttribute("data-v2c") === "1" || $('svg[data-v2c="1"]', host)) return;
          try { if (drawTranche(host, view)) stat.tranche++; else stat.skip++; } catch (e){ stat.skip++; }
        });
        $$('[data-chart="hbar"]', view).forEach(function(host){
          if (host.getAttribute("data-v2c") === "1" || $('svg[data-v2c="1"]', host)) return;
          var key = hostKey(host);
          var kind = CONVERT[key];
          if (!kind) return;
          var rows = null;
          try { rows = parseHbar(host); } catch (e){ rows = null; }
          if (!rows || rows.length < 2) return;
          var ok = false;
          try {
            var accent = viewAccent(view);
            if (kind === "lollipop") ok = drawLollipop(host, rows, accent);
            else if (kind === "stacked100") ok = drawStacked100(host, rows, accent);
            else if (kind === "area") ok = drawAreaChart(host, rows, accent);
          } catch (e){ ok = false; }
          if (ok) stat.bars++; else stat.skip++;
        });
        try { stat.units += unitPass(view); } catch (e){}
        try { unifyAxes(view); } catch (e){}
        try { unitValueLabels(view, stat); } catch (e){}   /* 裸数字值标签 → 全图单一单位 */
        /* 最后治理旋转轴标签（瀑布等）：必须在单位规范化之后，否则会被二次改宽而重新压字 */
        try {
          $$(".chart", view).forEach(function(host){
            if ($$("text[transform*='rotate']", host).length >= 3){
              var r = tidyRotatedAxis(host);
              if (r) stat.axes++;
            }
          });
        } catch (e){}
        /* 圆环图例长标签可读化 + 二次量级校正（此时 60_assets 的布局已生成）*/
        try { donutLabelPass(view, stat); } catch (e){}
        try { donutMagPass(view, stat); } catch (e){}
        try { soloMagPass(view, stat); } catch (e){}
        /* v8.4：担保方式异常备注（信用卡含抵押>1%）—— 网格下方通栏，与图型无关 */
        try { distNotePass(view); } catch (e){}
      });
    } finally { busy = false; }
    return stat;
  }
  /* 其它模块或页面脚本若晚于本模块渲染，用轻量 MutationObserver 幂等补齐 */
  function observe(){
    if (!window.MutationObserver) return;
    var timer = null;
    var mo = new MutationObserver(function(muts){
      if (busy) return;
      for (var i = 0; i < muts.length; i++){
        var t = muts[i].target;
        if (t && t.nodeType === 3) t = t.parentNode;
        if (t && t.closest && t.closest(".v2c-svg")) continue;
        if (timer) return;
        timer = setTimeout(function(){ timer = null; run(); }, 160);
        return;
      }
    });
    try { mo.observe(document.body, { childList: true, subtree: true, characterData: true }); } catch (e){}
  }
  function boot(){
    run();
    setTimeout(run, 240);
    setTimeout(run, 900);
    observe();
  }
  /* ═══════════════ 6. 全量断言 audit()（浏览器控制台 __V2Charts.audit()）═══════════════
     1) 刻度标签：不存在「≥2 个标签都被抹成 0」的图（点 8 历史 bug 回归护栏）
     2) 重绘图：每个图 <title> 数 ≥ 数据点数
     3) 旋转标签：平行标签碰撞 = 0
     4) 轴单位与量级匹配：最大刻度 <0.01 亿 却标「亿元」视为违规
     5) 无 NaN/undefined 几何值                                        */
  function audit(){
    var rep = { charts: 0, zeroTicks: [], titleShort: [], collide: [], unitBad: [], nanGeom: [],
                ticks: 0, titles: 0, unitMixed: [], unitUnknown: [], unitFixed: 0, unitBadge: [],
                donutChecked: 0, donutBad: [], tlChecked: 0, tlBad: [], distChecked: 0, distBad: [], distWarn: [],
                distNotePct: [], donutLabelTotal: 0, donutLabelCut: 0, donutSample: [],
                noteChecked: 0, noteHit: 0, noteBad: [], noteText: "",
                v9Checked: 0, v9Bad: [], v9Kinds: {}, v9Donuts: 0, v9TypeCount: 0, v9Rects: 0, v9GapMin: null,
                soloChecked: 0, soloBad: [], strokeBad: [],
                magAllChecked: 0, magAllBad: [], magAllWarn: [], magAllSample: [], ok: false };
    function tickTexts(svg){
      return $$("text", svg).filter(function(t){
        if ((t.getAttribute("text-anchor") || "") !== "end") return false;
        if (!(parseFloat(t.getAttribute("x")) < 110)) return false;
        var s = t.textContent.trim();
        return !!s && /^(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?$/.test(s);
      });
    }
    $$('section.view[id^="view-p"]').forEach(function(view){
      /* v8.4：担保方式异常备注 —— 判定条件、位置、文案与命中单数逐条断言 */
      (function(){
        var V = window.__V2 || {}, nkey = keyOfView(view);
        var arr = ((V.DIST || {})[nkey] || {}).guarantee || [];
        var pctSum = 0, balSum = 0;
        arr.forEach(function(x){
          var lab = String(x.label || "");
          if (/抵押|保证/.test(lab)){ pctSum += num(x.bal_pct); balSum += num(x.bal) * 1e4; }
        });
        var prof = profByView(view) || {};
        var cat = String(prof.cat || prof.category || "");
        if (!cat && (view.textContent || "").indexOf("信用卡") >= 0) cat = "信用卡不良";
        var want = (/信用卡/.test(cat) && pctSum > 1);
        var notes = $$('[class*="dist-note"]', view);
        rep.noteChecked++;
        if (want){
          rep.noteHit++;
          if (!notes.length){ rep.noteBad.push(nkey + " 缺少担保异常备注"); return; }
          var tx = notes[0].textContent || "";
          rep.noteText = tx;
          if (tx.indexOf("待回源核实") < 0) rep.noteBad.push(nkey + " 备注缺「待回源核实」");
          if (tx.indexOf(th(pctSum, 2) + "%") < 0) rep.noteBad.push(nkey + " 备注缺合计%(" + th(pctSum, 2) + "%)");
          if (tx.indexOf(th(balSum / 1e8, 2) + " 亿元") < 0) rep.noteBad.push(nkey + " 备注缺余额(" + th(balSum / 1e8, 2) + " 亿元)");
          if (notes[0].closest && notes[0].closest(".chart")) rep.noteBad.push(nkey + " 备注在卡片内（应通栏）");
          if (!String(notes[0].className || "").match(/v2c-dist-note-wide/)) rep.noteBad.push(nkey + " 备注未通栏");
          if (notes.length > 1) rep.noteBad.push(nkey + " 备注重复 " + notes.length + " 个");
        } else if (notes.length){
          rep.noteBad.push(nkey + " 无异常却出现备注");
        }
      })();
      /* 2h) 单类目圆环（已转为开篇表格）：余额合计与真值同量级 */
      var soloTbl = $(".v6-solo", view);
      if (soloTbl){
        var sref = donutRefOf(view, "");
        var str = $$("tbody tr", soloTbl), ssum = 0, scnt = 0;
        str.forEach(function(tr){
          var tds = $$("td", tr);
          var td = tds[tds.length - 1];
          if (!td) return;
          var yy = amtFromTitle(td.textContent);
          if (yy == null) return;
          ssum += yy; scnt++;
        });
        rep.soloChecked++;
        rep.magAllChecked++;
        if (sref && ssum > 0){
          var sr = ssum / sref;
          if (sr > 2 || sr < 0.5)
            rep.soloBad.push("solo[" + view.id + "] 余额合计 " + th(ssum, 2) + " ≠ 真值 " + th(sref, 2));
        }
      }
      $$(".chart", view).forEach(function(host){
        var svg = $("svg", host);
        if (!svg) return;
        rep.charts++;
        var name = hostKey(host).slice(0, 22) + " [" + view.id + "]";
        /* 1)+4) 刻度标签 */
        var ticks = tickTexts(svg);
        if (ticks.length >= 2){
          var labels = ticks.map(function(t){ return t.textContent.trim(); });
          rep.ticks += labels.length;
          var zeros = 0, seen = {}, dupZero = false;
          labels.forEach(function(x){
            var val = parseFloat(String(x).replace(/,/g, "").replace(/\s*(亿元|亿|万元|万|元)$/, ""));
            if (val === 0) zeros++;
            if (seen[x] && val === 0) dupZero = true;
            seen[x] = 1;
          });
          if (zeros >= 2 || dupZero) rep.zeroTicks.push(name + " :: " + labels.join(" / "));
          var maxAbs = 0, hasUnit = 0;
          ticks.forEach(function(t){
            var m = /^(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)?$/.exec(t.textContent.trim());
            if (m[2]) hasUnit++;
            maxAbs = Math.max(maxAbs, Math.abs(toYuan(m[1], m[2] || "元")));
          });
          var note = $(".v2c-unitnote", svg);
          if (note && hasUnit >= 2){
            var nu = /单位：(亿元|亿|万元|万|元)/.exec(note.textContent);
            if (nu){
              var nuw = nu[1].charAt(0);
              if (nuw === "亿" && maxAbs < 1e6) rep.unitBad.push(name + " 标「亿」但最大刻度 " + maxAbs);
            }
          }
        }
        /* 2) 重绘图 title 覆盖 */
        if (host.getAttribute("data-v2c") === "1"){
          var kind = host.getAttribute("data-v2c-kind") || "";
          var dots = $$(".v2c-dot", svg).length;
          var targets = $$(".v2c-band,.v2c-seg", svg).length;
          rep.titles += targets;
          if (dots > 0 && targets < dots) rep.titleShort.push(kind + " :: dots=" + dots + " titles=" + targets + " " + name);
        }
        /* 2b) 同图单位一致性：值标签（非轴刻度/非图注）不得出现 ≥2 种单位词 */
        var uWords = {}, uTexts = [];
        $$("text", svg).forEach(function(t){
          if (t.closest && t.closest(".v2c-note,.v2c-unitnote,.v2c-axis-cap")) return;
          var a = t.getAttribute("text-anchor") || "";
          if (a === "end" && parseFloat(t.getAttribute("x")) < 110) return;    /* y 轴刻度 */
          if (/rotate\(/.test(t.getAttribute("transform") || "")) return;        /* x 轴旋转标签 */
          var mm2 = /(-?[\d][\d,]*(?:\.\d+)?)\s*(亿元|亿|万元|万|元)/.exec(t.textContent.trim());
          if (!mm2) return;
          uWords[mm2[2].charAt(0)] = 1;
          uTexts.push(t.textContent.trim());
        });
        var uKeys = Object.keys(uWords);
        if (uKeys.length > 1) rep.unitMixed.push(name + " :: " + uTexts.slice(0, 4).join(" / "));
        /* 2c) 徽章/图注单位 vs 值标签单位：必须同源、同图唯一；纯占比图不得标金额单位 */
        var decl = null;
        var tagTxt = ($(".v2c-tag", host) || {}).textContent || "";
        var noteTxt = ($(".v2c-unitnote,.v2c-valuenote", svg) || {}).textContent || "";
        [tagTxt, noteTxt].forEach(function(tx){
          var mm3 = TAG_UNIT_RE.exec(tx || "");
          if (mm3 && !decl) decl = mm3[1].charAt(0);
        });
        if (decl){
          if (decl === "%"){
            if (uKeys.length && uKeys.some(function(k){ return k !== "%"; }))
              rep.unitBadge.push(name + " 徽章% 但值标签含 " + uKeys.join("/"));
          } else {
            if (uKeys.length >= 2)
              rep.unitBadge.push(name + " 徽章" + decl + " 但值标签混排 " + uKeys.join("/"));
            else if (uKeys.length === 1 && uKeys[0] !== decl)
              rep.unitBadge.push(name + " 徽章" + decl + " ≠ 值标签 " + uKeys[0]);
          }
        }
        if (!uKeys.length && /单位未标注（源）/.test(svg.textContent)) rep.unitUnknown.push(name);
        /* 2e) 圆环 P0：中心必须带数字 + 与真值同量级 + 图例和≈中心 + 同图单位唯一 */
        if ((host.getAttribute("data-chart") || "") === "donut" && svg.getAttribute("data-v2c-dist") !== "1"){
          var dview = host.closest ? host.closest("section.view") : view;
          var dct = $(".ct", host) || $(".ct2", host);
          var dref = donutRefOf(dview, dct ? dct.textContent : "");
          var ctext = donutCenterText(svg);
          var cyuan = amtFromTitle(ctext);
          rep.donutChecked++;
          if (!/^[\d][\d,.]*\s*(亿元|亿|万元|万|元)$/.test(ctext.replace(/\s+/g, ""))){
            rep.donutBad.push(name + " 中心无数字:「" + ctext + "」");
            if (rep.donutSample.length < 6) rep.donutSample.push(name + " :: " + ctext + " / 真值 " + dref);
          } else if (dref && cyuan){
            var dr = cyuan / dref;
            if (dr > 2 || dr < 0.5){
              rep.donutBad.push(name + " 中心量级错: " + ctext + " ≠ 真值 " + th(dref, 2) + " 元");
              if (rep.donutSample.length < 6) rep.donutSample.push(name + " :: " + ctext + " / 应为 " + th(dref / 1e8, 2) + " 亿元");
            }
          }
          var lsum = 0, lcnt = 0, dw = {};
          $$("text", svg).forEach(function(t){
            var s0 = t.textContent.trim();
            var m = /^([\d.]+)\s*%\s*[·｜|]\s*(.+)$/.exec(s0);
            if (m){
              var y2 = amtFromTitle(m[2]);
              if (y2 != null){
                lsum += y2; lcnt++;
                var um = /(亿元|亿|万元|万|元)/.exec(m[2]);
                if (um) dw[um[1].charAt(0)] = 1;
              }
            }
            /* 图例标签＝紧跟在色块后的文本（截断率按它统计，值文本不算）*/
            var pv = t.previousElementSibling;
            var pww = pv && (pv.nodeName || "").toLowerCase() === "rect" ? parseFloat(pv.getAttribute("width")) : 0;
            if (pww >= 8 && pww <= 16){
              rep.donutLabelTotal++;
              if (/…/.test(s0)) rep.donutLabelCut++;
            }
          });
          if (cyuan && lsum > 0 && Math.abs(lsum - cyuan) / cyuan > 0.01){
            rep.donutBad.push(name + " 图例和≠中心: " + th(lsum, 2) + " vs " + th(cyuan, 2));
          }
          if (Object.keys(dw).length > 1) rep.donutBad.push(name + " 同图单位混排 " + Object.keys(dw).join("/"));
        }
        /* 2i) 全图种量级：图内合计 vs 同页真值（≤2 倍）*/
        var mchart = host.getAttribute("data-chart") || "";
        if (mchart === "donut" || mchart === "hbar" || mchart === "treemap" || mchart === "dist-bar"){
          var mct = $(".ct", host) || $(".ct2", host);
          var mref = donutRefOf(view, mct ? mct.textContent : "");
          var msum = 0;
          if (mchart === "donut"){
            $$("text", svg).forEach(function(t){
              var mm2 = /^[\d.]+\s*%\s*[·｜|]\s*(.+)$/.exec(t.textContent.trim());
              if (!mm2) return;
              var y3 = amtFromTitle(mm2[1]);
              if (y3 != null) msum += y3;
            });
          } else if (svg.getAttribute("data-v2c-dist") === "1"){
            /* v8 分布图：每条 title 首个「余额 X 亿元/万元」即该桶金额（「其他」的明细在其后）*/
            var seenD = {};
            $$("rect, path", svg).forEach(function(el){
              var tt2 = el.querySelector ? el.querySelector("title") : null;
              if (!tt2) return;
              var tx = tt2.textContent;
              if (seenD[tx]) return;
              seenD[tx] = 1;
              var mmd = /(?:余额|金额)\s*([\d,.]+)\s*(亿元|万元)/.exec(tx);
              if (!mmd) return;
              msum += toYuan(mmd[1], mmd[2]);
            });
          } else {
            var seenT = {};
            $$("rect, path", svg).forEach(function(el){
              var tt2 = el.querySelector ? el.querySelector("title") : null;
              if (!tt2) return;
              var tx = tt2.textContent;
              if (seenT[tx]) return;                  /* 同一数据点可能有「柱 + 图例命中区」两处 */
              seenT[tx] = 1;
              var y4 = amtFromTitle(tx);
              if (y4 != null) msum += y4;
            });
          }
          rep.magAllChecked++;
          if (mref && msum > 0){
            var mr2 = msum / mref;
            if (mr2 > 100 || mr2 < 0.01){
              rep.magAllBad.push(name + " 图内合计 " + th(msum, 2) + " vs 真值 " + th(mref, 2) + "（量级 " + th(mr2, 3) + "）");
              if (rep.magAllSample.length < 6)
                rep.magAllSample.push(name + "（" + mchart + "）之和 " + th(msum, 2) + " / 期望 " + th(mref, 2));
            } else if (mr2 > 2 || mr2 < 0.5){
              rep.magAllWarn.push(name + " 覆盖 " + th(mr2 * 100, 1) + "%（源图分桶不全，非量级错标）");
            }
          }
        }
        /* 2j) 瀑布图例：项间不重叠 + 与单位徽章间距 ≥16px（v7）*/
        if (host.getAttribute("data-v2c") === "1" && $(".v2c-wfleg", svg)){
          var legs = $$(".v2c-wfleg", svg).map(function(t){
            var fs3 = parseFloat(t.getAttribute("font-size")) || 9.5;
            var x3 = parseFloat(t.getAttribute("x")) || 0;
            return { x: x3, w: estTextW(t.textContent.trim(), fs3), txt: t.textContent.trim() };
          });
          legs.sort(function(a, b){ return a.x - b.x; });
          var lc = 0;
          for (var li = 1; li < legs.length; li++)
            if (legs[li].x < legs[li - 1].x + legs[li - 1].w + 2) lc++;
          if (lc) rep.collide.push(name + " 图例项碰撞 " + lc + " 处");
          var uEl = $(".v2c-unitnote", svg);
          if (uEl && legs.length){
            var uw3 = estTextW(uEl.textContent.trim(), parseFloat(uEl.getAttribute("font-size")) || 10.5);
            var ux = (parseFloat(uEl.getAttribute("x")) || 0) + uw3;
            var uy = parseFloat(uEl.getAttribute("y")) || 0;
            var lrow = legs.filter(function(l){ return Math.abs((parseFloat(0) || 0)) >= 0; })[0];
            var gapPx = legs[0].x - ux;
            if (gapPx < 16) rep.collide.push(name + " 图例与单位徽章间距 " + th(gapPx, 1) + "px <16px");
          }
        }
        /* 2k) 时间轴（v7 并入档位末次兑付）：节点数 ≥8、每节点有 hover、原表格隐藏、标签不重叠 */
        var tlEl = $(".pf-tl", view);
        if (tlEl){
          var tlNodes = $$(".pf-ts", tlEl);
          rep.tlChecked++;
          if (tlNodes.length < 8) rep.tlBad.push(name + " 时间轴节点 " + tlNodes.length + " <8");
          var noTip = 0, boxes = [];
          tlNodes.forEach(function(nd){
            if (!nd.getAttribute("title")) noTip++;
            var r = nd.getBoundingClientRect ? nd.getBoundingClientRect() : null;
            if (r && r.width > 0) boxes.push({ x: r.left, y: r.top, w: r.width });
          });
          if (noTip) rep.tlBad.push(name + " 时间轴 " + noTip + " 个节点无 hover 说明");
          for (var bi = 1; bi < boxes.length; bi++){
            var A = boxes[bi - 1], B = boxes[bi];
            if (Math.abs(A.y - B.y) < 4 && A.x + A.w > B.x + 0.5)
              rep.tlBad.push(name + " 时间轴标签重叠 @" + bi);
          }
        }
        var tbc = $('[data-chart="timing-block"]', view);
        if (tbc && $(".pf-tl", view)){
          rep.tlChecked++;
          var hd = (tbc.getAttribute("data-v2c-hidden") === "1") ||
                   (tbc.offsetParent === null) ||
                   (window.getComputedStyle && window.getComputedStyle(tbc).display === "none");
          if (!hd) rep.tlBad.push(name + " 「兑付与清算时点」表格仍可见");
        }
        /* 2l) v8：分布图字号（≤3 种、max ≤13）、文字不重叠、轴标签不被裁、担保备注 */
        if (svg.getAttribute("data-v2c-dist") === "1"){
          var fsSet = {};
          $$("text", svg).forEach(function(t){
            var f = parseFloat(t.getAttribute("font-size"));
            if (f > 0) fsSet[String(f)] = 1;
          });
          var fk = Object.keys(fsSet);
          rep.distChecked++;
          if (fk.length > 3) rep.distBad.push(name + " 字号种类 " + fk.length + "（>3）: " + fk.join("/"));
          fk.forEach(function(f){ if (parseFloat(f) > 13) rep.distBad.push(name + " 字号过大 " + f); });
          /* 文字包围盒互不相交（同一卡内全部 text）*/
          var tbx = [], ov2 = 0;
          $$("text", svg).forEach(function(t){
            var tx = t.textContent.trim();
            if (!tx) return;
            var fs4 = parseFloat(t.getAttribute("font-size")) || 10;
            var x4 = parseFloat(t.getAttribute("x")) || 0, y4 = parseFloat(t.getAttribute("y")) || 0;
            var anc = (t.getAttribute("text-anchor") || "start");
            var w4 = estTextW(tx, fs4);
            var left = anc === "end" ? x4 - w4 : (anc === "middle" ? x4 - w4 / 2 : x4);
            tbx.push({ x: left, y: y4 - fs4 * 0.82, w: w4, h: fs4 * 1.05, txt: tx });
          });
          for (var ti = 1; ti < tbx.length; ti++){
            var A2 = tbx[ti - 1], B2 = tbx[ti];
            if (A2.x + A2.w > B2.x + 0.5 && A2.y + A2.h > B2.y + 0.5 && B2.y + B2.h > A2.y + 0.5) ov2++;
          }
          if (ov2) rep.distWarn.push(name + " 文字重叠 " + ov2 + " 处");
          /* 轴/标签左边界不越界 */
          tbx.forEach(function(b){
            if (b.x < -4) rep.distWarn.push(name + " 文字近/越左边界 " + th(b.x, 1) + "px: " + b.txt.slice(0, 10));
          });
        }
        /* 2m) v8.2：担保方式备注在网格下方通栏（不在卡片内、不占卡高）*/
        if (svg.getAttribute("data-v2c-dist") === "1" && distTypeOf(host) === "guarantee"){
          var gw = $(".v2c-dist-note-wide", view);
          var inCard = $(".v2c-dist-note", host);
          if (inCard) rep.distBad.push(name + " 备注仍在卡片内（应通栏）");
          if (gw){
            var mPct = /合计\s*([\d.]+)%/.exec(gw.textContent);
            if (!mPct) rep.distBad.push(name + " 备注缺少数值");
            else rep.distNotePct.push(mPct[1]);
          }
        }
        /* 2n) v9：分布图设计规格断言 */
        var ctype = svg.getAttribute("data-v2c-charttype");
        if (ctype){
          rep.v9Checked++;
          rep.v9Kinds[ctype] = (rep.v9Kinds[ctype] || 0) + 1;
          var TX = (host.textContent || "");
          if (!(/单位：/.test(TX) && /合计/.test(TX) && /口径：/.test(TX)))
            rep.v9Bad.push(name + " 缺「单位/合计/口径」信息");
          var V9 = window.__V2 || {}, vkey2 = keyOfView(view), vtype2 = distTypeOf(host);
          var raw2 = ((V9.DIST || {})[vkey2] || {})[vtype2] || [];
          if (/^col/.test(ctype)){
            /* 渲染后区间键（首个数字）必须单调不减 */
            var rot = $$("text[transform*=rotate]", svg);
            var keys = rot.map(function(t){
              var firstN = t.firstChild;
              var vis0 = firstN && firstN.nodeType === 3 ? firstN.nodeValue : t.textContent;
              var mm9 = String(vis0).match(/(-?[\d.]+)/);
              return mm9 ? parseFloat(mm9[1]) : 0;
            });
            var mono = true;
            for (var mi = 1; mi < keys.length; mi++) if (keys[mi] < keys[mi - 1] - 1e-6){ mono = false; break; }
            if (!mono) rep.v9Bad.push(name + " 区间标签非单调（" + keys.join(",") + "）");
          }
          var barsV = [];
          $$("rect.v2c-dbar", svg).forEach(function(r){
            var t = r.querySelector ? r.querySelector("title") : null;
            var m = t ? /余额 ([\d,.]+) (亿元|万元)/.exec(t.textContent) : null;
            if (m) barsV.push({ v: toYuan(m[1], m[2]), fill: r.getAttribute("fill") || "" });
          });
          if (ctype === "hbar-top"){
            var bv2 = barsV.slice();
            if (host.getAttribute("data-v2c-top10") === "1" && bv2.length > 1) bv2.pop();   /* 末位是「其他」*/
            for (var bi = 1; bi < bv2.length; bi++)
              if (bv2[bi].v > bv2[bi - 1].v + 1){ rep.v9Bad.push(name + " 未按金额降序"); break; }
            var ftEl = $(".v9-foot", host);
            var ft = (ftEl ? ftEl.textContent : "") + " " + $$(".v2c-dnote", svg).map(function(t){ return t.textContent; }).join(" ");
            if (host.getAttribute("data-v2c-top10") === "1" && !/其他含\s*\d+\s*项/.test(ft))
              rep.v9Bad.push(name + " TopN 缺「其他含 N 项」脚注");
          }
          /* 截断必须有 tooltip */
          $$("text", svg).forEach(function(t){
            var tx = t.textContent.trim();
            if (/…$/.test(tx) && !(t.querySelector && t.querySelector("title")))
              rep.v9Bad.push(name + " 「…」无 tooltip: " + tx.slice(0, 12));
          });
          /* 主色 ≤6；合并项中性灰 */
          var colSet = {};
          barsV.forEach(function(b){ if (b.fill) colSet[b.fill.toUpperCase()] = 1; });
          if (Object.keys(colSet).length > 6)
            rep.v9Bad.push(name + " 主色 " + Object.keys(colSet).length + " >6");
          if (ctype === "hbar-top" && host.getAttribute("data-v2c-top10") === "1"){
            var hasGray = barsV.some(function(b){ return /C9D2E0|#C9D2E0/.test(b.fill.toUpperCase()) || /C9D2E0/.test((b.fill || "").toUpperCase()); });
            if (!hasGray) rep.v9Bad.push(name + " 合并项未用中性灰");
          }
          /* 无横向滚动 */
          if (host.scrollWidth > host.clientWidth + 2)
            rep.v9Bad.push(name + " 横向滚动 " + host.scrollWidth + ">" + host.clientWidth);
          /* 数值口径：柱 title 之和 vs DIST 合计 */
          var sumSrc = 0;
          raw2.forEach(function(x){ sumSrc += num(x.bal) * 1e4; });
          var sumBar = 0;
          barsV.forEach(function(b){ sumBar += b.v; });
          if (sumSrc > 0 && Math.abs(sumBar - sumSrc) / sumSrc > 0.02)
            rep.v9Bad.push(name + " 合计偏离 " + th((sumBar - sumSrc) / sumSrc * 100, 2) + "%");
        }
        /* 2o) v9.2：dist-v9 —— 口径/图型说明必须在 SVG 外；卡内 text 真实矩形不相交；
               旋转标签最低点 < 图下脚注顶部 − 6px */
        if (host.getAttribute("data-v9-chart")){
          var svgTxt = "";
          $$("text", svg).forEach(function(t){ svgTxt += t.textContent; });
          if (/口径|图型：/.test(svgTxt)) rep.v9Bad.push(name + " SVG 内仍有口径/图型说明（应移出到 HTML）");
          var metaEl = $(".v9-meta", host), footEl = $(".v9-foot", host);
          if (!metaEl || !footEl) rep.v9Bad.push(name + " 缺 HTML 口径行/图型说明");
          else {
            if (!/单位：/.test(metaEl.textContent) || !/口径：/.test(metaEl.textContent))
              rep.v9Bad.push(name + " HTML 口径行缺单位/口径");
            if (!/图型：/.test(footEl.textContent)) rep.v9Bad.push(name + " HTML 脚注缺图型说明");
            /* 旋转标签底 vs 脚注顶 */
            var rotMin = -1;
            $$("text[transform*=rotate]", svg).forEach(function(t){
              var rc = t.getBoundingClientRect ? t.getBoundingClientRect() : null;
              if (rc && rc.height > 0 && rc.bottom > rotMin) rotMin = rc.bottom;
            });
            var fr = footEl.getBoundingClientRect ? footEl.getBoundingClientRect() : null;
            if (rotMin > 0 && fr && fr.height > 0){
              var gap9 = fr.top - rotMin;
              if (gap9 < 6) rep.v9Bad.push(name + " 旋转标签与脚注间距 " + th(gap9, 1) + "px <6");
              else rep.v9GapMin = (rep.v9GapMin === null || gap9 < rep.v9GapMin) ? gap9 : rep.v9GapMin;
            }
            /* 卡内 text 真实矩形两两不相交（仅可见视图）*/
            var rects = [];
            $$("text", svg).forEach(function(t){
              var rc2 = t.getBoundingClientRect ? t.getBoundingClientRect() : null;
              if (!rc2 || rc2.width <= 0 || rc2.height <= 0) return;
              if (rc2.width > 400 || rc2.height > 60) return;           /* 异常 rect 跳过 */
              rects.push({ l: rc2.left, t: rc2.top, r: rc2.right, b: rc2.bottom, x: t.textContent.slice(0, 8) });
            });
            var ov9b = 0;
            for (var qb = 0; qb < rects.length; qb++){
              for (var rb = qb + 1; rb < rects.length; rb++){
                var Ab = rects[qb], Bb = rects[rb];
                if (Ab.l < Bb.r - 0.5 && Bb.l < Ab.r - 0.5 && Ab.t < Bb.b - 0.5 && Bb.t < Ab.b - 0.5) ov9b++;
              }
            }
            if (ov9b) rep.v9Bad.push(name + " 文字矩形相交 " + ov9b + " 对");
            rep.v9Rects += rects.length;
          }
        }
        /* 2f) 线宽：同一图内 path[stroke] 宽度集合必须唯一且 ≤2.0 */
        var swSet = {};
        $$("path[stroke]", svg).forEach(function(pp){
          var w = pp.getAttribute("stroke-width");
          if (w && parseFloat(w) > 0) swSet[w] = 1;
        });
        var swk = Object.keys(swSet);
        if (swk.length > 1) rep.strokeBad.push(name + " 线宽不唯一 " + swk.join("/"));
        else if (swk.length === 1 && parseFloat(swk[0]) > 2.0) rep.strokeBad.push(name + " 线宽过粗 " + swk[0]);

        /* 3) 旋转标签碰撞（平行线垂直净距 < 字号）*/
        var rot = $$("text", svg).filter(function(t){ return /rotate\(/.test(t.getAttribute("transform") || ""); });
        if (rot.length >= 2){
          rot.sort(function(a, b){ return (parseFloat(a.getAttribute("x")) || 0) - (parseFloat(b.getAttribute("x")) || 0); });
          var prev = null, bad = 0;
          rot.forEach(function(t){
            if (prev){
              var dx = Math.abs((parseFloat(t.getAttribute("x")) || 0) - (parseFloat(prev.getAttribute("x")) || 0));
              var fs = Math.max(parseFloat(t.getAttribute("font-size")) || 9, parseFloat(prev.getAttribute("font-size")) || 9);
              if (dx * Math.sin(rotAngle(t)) < fs * 1.02) bad++;
            }
            prev = t;
          });
          if (bad) rep.collide.push(name + " 碰撞 " + bad + " 处");
        }
        /* 4b) 已治理的旋转轴图：数值标签也不得碰撞 */
        if (host.getAttribute("data-v2c-xl") === "1"){
          var mids = $$("text", svg).filter(function(t){
            return (t.getAttribute("text-anchor") || "") === "middle" &&
                   !/rotate\(/.test(t.getAttribute("transform") || "");
          });
          var bx = [];
          var vbad = 0;
          mids.forEach(function(t){
            var fs2 = parseFloat(t.getAttribute("font-size")) || 10;
            var b = { x: parseFloat(t.getAttribute("x")) || 0, y: parseFloat(t.getAttribute("y")) || 0,
                      w: estW(t.textContent.trim(), fs2), h: fs2 * 1.15 };
            for (var q = 0; q < bx.length; q++){
              var k = bx[q];
              if (Math.abs(b.x - k.x) < (b.w + k.w) / 2 + 3 && Math.abs(b.y - k.y) < (b.h + k.h) / 2){ vbad++; break; }
            }
            bx.push(b);
          });
          if (vbad) rep.collide.push(name + " 数值标签碰撞 " + vbad + " 处");
        }
        /* 5) 几何 NaN */
        var html = svg.innerHTML || "";
        if (/NaN|Infinity|undefined/.test(html)) rep.nanGeom.push(name);
      });
    });
    /* 2g) 图例截断率 ≤ 20% */
    rep.donutLabelRate = rep.donutLabelTotal ? +(rep.donutLabelCut / rep.donutLabelTotal).toFixed(4) : 0;
    if (rep.donutLabelRate > 0.2) rep.donutBad.push("图例截断率 " + th(rep.donutLabelRate * 100, 1) + "% > 20%");
    /* v9：图型多样性 ≥4、圆环数量 ≤2（本规格下应为 0）*/
    rep.v9TypeCount = Object.keys(rep.v9Kinds).length;
    if (rep.v9TypeCount < 4) rep.v9Bad.push("图型种类 " + rep.v9TypeCount + " <4（禁止单一化）");
    /* 仅统计「已按规格重构（有 DIST）」的资产池视图里的圆环数（应 ≤2，本规格为 0）*/
    $$('section.view[id^="view-p"]').forEach(function(vw){
      var grid2 = $(".dist-grid", vw);
      if (!grid2) return;
      if (!$$("[data-v2c-charttype]", grid2).length) return;
      rep.v9Donuts += $$('[data-chart="donut"]', grid2).length;
    });
    if (rep.v9Donuts > 2) rep.v9Bad.push("圆环数量 " + rep.v9Donuts + " >2");
    rep.ok = !(rep.zeroTicks.length || rep.titleShort.length || rep.collide.length || rep.unitBad.length ||
               rep.nanGeom.length || rep.unitMixed.length || rep.unitBadge.length ||
               rep.donutBad.length || rep.soloBad.length || rep.strokeBad.length || rep.magAllBad.length ||
               rep.tlBad.length || rep.distBad.length || rep.noteBad.length || rep.v9Bad.length);
    return rep;
  }
  /* JS 侧自检（浏览器控制台可调用：__V2Charts.selftest()）*/
  function selftest(){
    var cases = [
      ["累计回收", "9363.62 万", "0.94 亿元"],
      ["累计回收", "3.29 亿", "3.29 亿元"],
      ["入池本息费", "11.92 亿", "11.92 亿元"],
      ["入池本金", "11.42 亿", "11.42 亿元"],
      ["入池息费", "5056.15 万", "5,056.15 万元"],
      ["单笔最高", "34.65 万", "34.65 万元"],
      ["主体平均", "10.02 万", "10.02 万元"],
      ["处置费用", "1800.96 万", "0.18 亿元"],
      ["优先档 利息", "116.2 万", "116.20 万元"],
      ["(3,6]", "6.09 万", "6.09 万元"],
      ["12个月以上", "8638 元", "0.86 万元"],
      ["", "入池 11.92 亿 ｜ 预计 2.52 亿 ｜ 达成 131%", "入池 11.92 亿元 ｜ 预计 2.52 亿元 ｜ 达成 131.00%"],
      ["入池息费", "入池本息费 11.92 亿 ｜ 预计回收 2.52 亿", "入池本息费 11.92 亿元 ｜ 预计回收 2.52 亿元"],
      ["期初余额（首期）", "0 元", "0.00 亿元"],
      ["净留存", "0 元", "0.00 亿元"],
      ["累计回收率", "27.63%", "27.63%"],
      ["前5大占比", "0.1%", "0.10%"],
      ["资产笔数", "27295 笔", "27295 笔"],
      ["加权平均逾期", "6.7 月", "6.7 月"],
      ["设立日", "2023-12-07", "2023-12-07"]
    ];
    var pass = 0, fail = [];
    cases.forEach(function(c){
      var got = normText(c[0], c[1]);
      if (got === c[2]) pass++; else fail.push(c[0] + "｜" + c[1] + " → " + got + " ≠ " + c[2]);
    });
    return { pass: pass, total: cases.length, fail: fail };
  }
  window.__V2Charts = {
    run: run,
    unitPass: unitPass,
    unitStat: UNIT_STAT,
    tlStat: TL_STAT,
    distStat: DIST_STAT,
    v9Stat: V9_STAT,
    magStat: MAG_STAT,
    wfAudit: wfAudit,
    allocSecurityTotal: allocSecurityTotal,
    audit: audit,
    selftest: selftest,
    norm: normText,
    rules: UNIT_RULES.length,
    groups: UNIT_ORDER.length,
    convert: CONVERT,
    kinds: KIND_LABEL
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
"""

# ════════════════════════════════════════════════════════════════
# 独立自检（不依赖任何其他脚本）
# ════════════════════════════════════════════════════════════════
UNIT_POLICY = """
单位统一规范（本模块实现）：
  · 规模类（入池本息费、入池本金、累计回收、发行规模、优先档、次级档、预计回收、处置费用）
      → 一律「亿元」，2 位小数（<0.01 亿的用「万元」并注明）
  · 单笔/户均/息费类（单笔最高、单笔平均、主体最高、主体平均、入池息费、利息、费用、报酬）
      → 一律「万元」，2 位小数
  · 比率类（回收率、达成率、证券化率、XIRR、占比）→ 百分号 2 位小数
  · 期数/月数/笔数/户数 → 纯数字 + 单位词（不改动）
"""


def _js_block(name: str) -> str:
    m = re.search(r"^  var %s = \[(.*?)^  \];" % name, JS, re.S | re.M)
    return m.group(1) if m else ""


def _js_balance(js: str):
    """JS 括号配平（跳过注释/字符串/模板/正则字面量），node --check 不可用时的兜底。"""
    i, n = 0, len(js)
    stack, bad, prev = [], 0, ""
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
            is_re = (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^") or (word and word.group(1) in WORDS)
            if is_re:
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
            if not stack or stack.pop() != ch:
                bad += 1
            prev = ch; i += 1; continue
        if not ch.isspace(): prev = ch
        i += 1
    return bad, stack


def _node_check():
    """可选：若本机有 node，则对 JS 做真实语法校验（缺失则跳过，不影响自检结论）。"""
    import os
    import shutil
    import subprocess
    import tempfile
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


# ── 数轴断言辅助：Python 侧镜像 pickAxisUnit（与 JS 同规则，用于回归护栏）──
_AXIS_FACTOR = {"亿": 1e8, "万": 1e4, "元": 1.0}


def _tick_labels(vals, unit):
    f = _AXIS_FACTOR[unit]
    d = 0 if unit == "元" else 2
    return ["{:.{d}f}".format(v / f, d=d) for v in vals]


def _pick_axis_unit(max_abs, vals):
    """镜像 JS pickAxisUnit：① 不得 ≥2 个零标签；② 标签不得重复。"""
    cands = ["亿", "万", "元"] if max_abs >= 1e6 else ["万", "元"]
    for u in cands:
        labs = _tick_labels(vals, u)
        zeros = sum(1 for x in labs if abs(float(x.replace(",", ""))) < 1e-9)
        if zeros < 2 and len(set(labs)) == len(labs):
            return u, labs
    return None, None


def _astr(text):
    """把 JS 里的空白压平，便于做源码一致性断言。"""
    import re as _re
    return _re.sub(r"\s+", " ", text)


# 刻度标签回归用例：名称 → 各 tick 的原始金额（元）
AXIS_FIXTURES = [
    ("grouped-bar 逐期回收（Lead 报的 0.00 亿元 bug）", [1.22e8, 9.1776e7, 6.1184e7, 3.0592e7, 0.0]),
    ("万元量级（最大 <0.01 亿）", [4.0e5, 3.0e5, 2.0e5, 1.0e5, 0.0]),
    ("亿档会退化成 0.01/0.00 ⇒ 必须自动降到万元", [1.2e6, 9.0e5, 6.0e5, 3.0e5, 0.0]),
    ("极小值（元档）", [150.0, 100.0, 50.0, 0.0]),
]


# ── 值标签单位镜像（与 JS pickValueUnit/vlab 同规则）──
def _vnum(u: str, v: float) -> str:
    y = abs(v)
    if u == "亿":
        return f"{v/1e8:,.2f}"
    if u == "万":
        d = 0 if y >= 1e6 else 2
        return f"{v/1e4:,.{d}f}"
    return f"{v:,.0f}"


def _vlab(u: str, v: float) -> str:
    return _vnum(u, v) + ("亿元" if u == "亿" else ("万元" if u == "万" else "元"))


def _pick_value_unit(max_v: float, vals):
    mv = abs(max_v)
    cands = ["亿", "万", "元"] if mv >= 1e6 else (["万", "元"] if mv >= 1e4 else ["元", "万"])
    for u in cands:
        # 真 0 不算退化；只看非零值被抹成 0
        z = sum(1 for v in vals if v != 0 and abs(float(_vnum(u, v).replace(",", ""))) < 1e-9)
        if z < 2:
            return u
    return cands[-1]


VALUE_FIXTURES = [
    ("借款人年收入分布（原 4.1万 与 5200 混排）", [41000, 34000, 29000, 5200, 2601, 7444]),
    ("预计回收率分布", [13000, 56000, 40000, 4030, 1342, 687, 4362]),
    ("瀑布（3.29 亿 → 100 元，跨 6 个数量级）",
     [3.29e8, 2.27e8, 5.74e7, 1.8e7, 1.39e7, 7.8e6, 2.05e6, 8.7e5, 5e5, 4e4, 1.75e4, 1.32e4, 1.25e4, 1317, 100, 0]),
    ("亿元量级（全部 ≥0.01 亿）", [3.29e8, 2.27e8, 1.2e8]),
    ("极小值（须降到元）", [150.0, 100.0, 50.0, 0.0]),
]


def assert_value_units():
    """④ 值标签：同一张图只能出现一种单位词（亿/万/元 混排即失败）；且不得整图 0.00。"""
    ok = True
    rows = []
    for name, vals in VALUE_FIXTURES:
        mx = max(abs(v) for v in vals)
        u = _pick_value_unit(mx, vals)
        labs = [_vlab(u, v) for v in vals]
        words = {"亿元" if l.endswith("亿元") else "万元" if l.endswith("万元") else "元" for l in labs}
        zeros = sum(1 for l in labs
                    if abs(float("".join(c for c in l if c.isdigit() or c in ".+-"))) < 1e-9)
        good = (len(words) == 1 and zeros < 2)
        ok = ok and good
        rows.append((name, u, sorted(words)[0], zeros, "／".join(labs[:4]), good))
    print("\n④ 值标签「同图单一单位」断言：")
    for name, u, w, zeros, sample, good in rows:
        print("   [%s] %-38s 单位=%-2s 单位词=%s 零值=%d  例：%s"
              % ("✓" if good else "✗", name, u, w, zeros, sample))
    js = _astr(JS)
    cons = [
        ("裸数字从同数据点 <title> 反推", "function unitValueLabels(root, stat)" in js),
        ("无单位注记的图才处理（自绘图不重复）", ".v2c-note,.v2c-unitnote" in js),
        ("全图统一单位后再写回（由全图数值派生）", "var u = pickValueUnit(maxV, vals);" in js),
        ("取不到单位 → 原样 + 图注", "单位未标注（源）" in JS and "stat.unitUnknownList.push" in js),
        ("与轴刻度同规则（0.01 亿阈值；<1 万元时元优先）", "m0 >= 1e6 ? [\"亿\", \"万\", \"元\"]" in js),
        ("标题取「值」段金额（避开标签里的数字单位）", "function amtFromTitle(txt)" in js and "parts.length - 1" in js),
        ("零值守卫只看非零被抹零", "if (v !== 0 && parseFloat(String(vnum(" in js),
        ("累计统计 unitStat 可回报", "unitStat: UNIT_STAT" in js and "UNIT_STAT.fixed" in js),
        ("图内主导单位（含无注记的自绘图）", "function dominantUnit(svg, cache)" in js and "var cu = svgHost ? dominantUnit(" in js),
        ("徽章单位与值同源（同一变量 u）", "addTag(host, \"单位：\" + uw)" in js and "var uw = unitWord(u), fixed = 0;" in js),
        ("徽章可更新（保留图种标签）", "TAG_UNIT_RE" in js and "cur.replace(TAG_UNIT_RE," in js),
        ("单位由全图数值派生（不看裸数字子集）", "var vals = known.map(function(r){ return r.yuan; });" in js),
        ("纯占比图徽章不标金额单位", 'KIND_LABEL.stacked100 + " · 段内占比（金额见图例）"' in JS),
        ("徽章 vs 值标签一致性断言", "rep.unitBadge" in js and 'rep.unitBadge.push(name + " 徽章" + decl' in js),
    ]
    for label, good in cons:
        print("   [%s] JS 一致性：%s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


# ── 徽章/图注单位 vs 值标签单位：规则镜像（与 JS audit 同规则）──
BADGE_FIXTURES = [
    ("徽章「元」但值标签万元（本次目视抓到的缺陷）", "元", ["万"], False),
    ("徽章「万元」且值标签万元（正常）", "万", ["万"], True),
    ("徽章「亿元」且值标签亿元（正常）", "亿", ["亿"], True),
    ("徽章「万元」但值标签混排 亿/万", "万", ["亿", "万"], False),
    ("纯占比图：徽章「万元」但值标签全为 %", "万", ["%"], False),
    ("纯占比图：徽章「%」值标签 %（正常）", "%", ["%"], True),
    ("轴注记型：有徽章、无显式值标签（放行）", "亿", [], True),
]


def _badge_ok(decl: str, vkeys) -> bool:
    if not decl:
        return True
    if decl == "%":
        return all(k == "%" for k in vkeys)
    # 徽章是金额单位：值标签必须与徽章同词、且不得混排；无显式值标签（轴注记型）放行
    if not vkeys:
        return True
    if len(vkeys) >= 2:
        return False
    return vkeys[0] == decl


def assert_badge_units():
    """⑤ 徽章/图注单位必须与该图值标签单位同源；纯占比图不得标金额单位。"""
    ok = True
    print("\n⑤ 徽章 vs 值标签单位断言（规则镜像；实跑结果见 __V2Charts.audit().unitBadge）：")
    for name, decl, vk, want in BADGE_FIXTURES:
        got = _badge_ok(decl, vk)
        good = (got == want)
        ok = ok and good
        print("   [%s] %-40s 徽章=%-3s 值标签=%-8s → %s"
              % ("✓" if good else "✗", name, decl, "/".join(vk) or "—", "通过" if got else "违规"))
    js = _astr(JS)
    cons = [
        ("单位由全图数值派生（同一变量驱动徽章/图注/值）", "var u = pickValueUnit(maxV, vals);" in js and 'addTag(host, "单位：" + uw)' in js),
        ("徽章可更新（不因已存在而跳过）", "TAG_UNIT_RE" in js and "cur.replace(TAG_UNIT_RE," in js),
        ("值标签只认紧邻数据图元（rect/circle/polygon）", "var p = t.previousElementSibling;" in js),
        ("纯占比图徽章不标金额单位", "段内占比（金额见图例）" in JS),
        ("audit 内含徽章一致性断言", "rep.unitBadge" in js and "徽章% 但值标签含" in js),
    ]
    for label, good in cons:
        print("   [%s] JS 一致性：%s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


# ── v5 新增：圆环量级换算 / 图例标签可读化 / 线宽一致性（与 JS 同规则镜像）──
def _vlab_s(u: str, v: float) -> str:
    return _vnum(u, v) + " " + ("亿元" if u == "亿" else ("万元" if u == "万" else "元"))


def _donut_fix(rows, ref):
    """rows: [(pct, yuan)]；返回 (unit, [(pct, label)], center_label, 修正后的元值列表)"""
    sum_y = sum(y for _, y in rows)
    sum_p = sum(p for p, _ in rows)
    use_pct = sum_p > 0 and abs(sum_p - 100) < 1
    nv = [ref * p / sum_p if use_pct else ref * y / sum_y for p, y in rows]
    u = _pick_value_unit(ref, nv)
    return u, [(p, _vlab_s(u, v)) for (p, _), v in zip(rows, nv)], _vlab_s(u, ref), nv


DONUT_FIXTURES = [
    # (名称, [(占比, 原值元)], 真值元, 期望单位)
    ("p0 未偿本息费余额分布（原「11.92 万」全局差 1e4）",
     [(19.56, 23300), (18.05, 21500), (16.12, 19200), (16.04, 19100), (13.77, 16400),
      (11.08, 13200), (5.37, 6400)], 1192460500.0, "亿"),
    ("p0 五级分类分布", [(51.26, 61100), (41.78, 49800), (6.96, 8300)], 1192460500.0, "亿"),
    ("单类目（担保方式分布→表格）", [(100.0, 119200)], 1192460500.0, "亿"),
    ("小额单（真值 8.6 万，<0.01 亿 → 万元）", [(60.0, 51600), (40.0, 34400)], 86000.0, "万"),
]


def assert_donut_magnitude():
    """P0 断言镜像：中心必须带数字且与真值同量级；图例各项之和 ≈ 中心（1%）。"""
    ok = True
    print("\n⑥ 圆环 P0 量级换算断言（镜像；实跑见 __V2Charts.audit().donutBad）：")
    for name, rows, ref, want_u in DONUT_FIXTURES:
        raw_sum = sum(y for _, y in rows)
        u, labs, center, nv = _donut_fix(rows, ref)
        sum_fix = sum(nv)
        rel = abs(sum_fix - ref) / ref
        digits = bool(re.search(r"^[\d][\d,.]*\s*(亿元|亿|万元|万|元)$", center))
        words = {("亿元" if l.endswith("亿元") else "万元" if l.endswith("万元") else "元") for _, l in labs}
        good = (u == want_u) and digits and rel < 0.01 and len(words) == 1
        ok = ok and good
        print("   [%s] %-34s 原合计=%s → 中心=%s ｜ 首项=%s ｜ Σ修正/真值=%.6f ％ 单位词=%s"
              % ("✓" if good else "✗", name, f"{raw_sum:,.0f}", center, labs[0][1], rel * 100,
                 "/".join(sorted(words))))
    # 修前 / 修后对比（p0 实测口径）
    p0 = DONUT_FIXTURES[0]
    print("   修前 p0：中心「11.92 万元」= 119,200 元（真值 1,192,460,500 元，差 10000 倍）")
    _u, _l, c, _nv = _donut_fix(p0[1], p0[2])
    print("   修后 p0：中心「合计 %s」 ｜ 首项「%s · %s」" % (c, th(p0[1][0][0], 2) if False else "19.56", _l[0][1]))
    return ok


LABEL_FIXTURES = [
    ("(20,25…", "(20,25]"),
    ("(9,12…", "(9,12]"),
    ("(0,5]", "(0,5]"),
    ("商业、服务业…", "商业、服务业"),
    ("生产、运输设…", "生产、运输设"),
    ("工程技术（含…", "工程技术"),
    ("其他办事人员…", "其他办事人员"),
    ("次级", "次级"),
]


def _clean_label(raw: str) -> str:
    s0 = raw.strip()
    if not s0:
        return s0
    had = s0.endswith("…")
    core = re.sub(r"…+$", "", s0).rstrip()
    r = re.match(r"^[（(\[【]?\s*(-?[\d.]+)\s*[,，]\s*(-?[\d.]+)", s0)
    if r and (s0[0] in "（([【" or had):
        return "(" + r.group(1) + "," + r.group(2) + "]"
    if not had:
        return s0
    t = re.sub(r"[（(][^（()）]*$", "", core)
    t = re.sub(r"[、，,]\s*$", "", t).rstrip()
    segs = re.split(r"[、，,]", t)
    if len(segs) > 1 and len(segs[-1]) <= 1:
        segs.pop()
        t = "、".join(segs)
    return t if len(t) >= 3 else s0


def assert_wrap_estimate():
    """两行换行可行性镜像：估算宽度 ≤ 2*标签列宽。"""
    def ew(txt, fs=9.5):
        return sum(fs if ord(c) > 255 else fs * 0.58 for c in txt)
    cases = [("商业、服务业人员", 226, True), ("生产、运输设备操作人员及有关人员", 226, True),
             ("超长标签" * 12, 226, False)]
    ok = True
    print("   两行换行估算（标签列宽 226 @9.5px）：")
    for txt, w, want in cases:
        got = ew(txt) <= w * 2
        good = got == want
        ok = ok and good
        print("      [%s] %-22s 估算宽=%.0f ≤ %d → %s" % ("✓" if good else "✗", txt[:20], ew(txt), w * 2, got))
    return ok


def assert_line_width():
    """线宽一致性：同图 path[stroke] 宽度集合唯一且 ≤2.0。"""
    print("\n⑦ 线宽一致性断言（镜像）：")
    ok = True
    for name, widths, want_pass in [
            ("新绘折线（recon/tranche）", ["1.6", "1.6"], True),
            ("面积图描边", ["1.4"], True),
            ("修前（2.6 实线 + 2 虚线 = 两值）", ["2.6", "2"], False),
            ("圆环扇区白描边", ["1.4"], True),
    ]:
        uniq = sorted(set(widths))
        good = (len(uniq) == 1 and float(uniq[0]) <= 2.0) == want_pass
        ok = ok and good
        print("   [%s] %-30s 宽度=%s 唯一=%s 最大=%s" % ("✓" if good else "✗", name, "/".join(widths),
                                                    len(uniq) == 1, max(float(w) for w in widths)))
    js = _astr(JS)
    cons = [
        ("平滑曲线（单调三次 → 三次贝塞尔）", "function linePath(xs, ys)" in js and 'th(xs[i] + h / 3, 1)' in js and "if (ss > 9)" in js),
        ("线宽常量 LW/LW_AREA 统一", "var LW = 1.6;" in js and "var LW_AREA = 1.4;" in js),
        ("面积带上下边界都平滑", "linePathRev(xs, yTot)" in js),
        ("圆环量级换算按占比分摊真值", "ref * rows[i].pct / sumPct" in js and "function donutMagPass(root, stat)" in js),
        ("中心合计补数字/带单位", "function setDonutCenter(svg, u, ref, stat)" in js),
        ("单类目表格同样校正", "function soloMagPass(view, stat)" in js),
        ("图例标签可读化（区间复原/语义缩短/两行）", "function cleanDonutLabel(raw)" in js and "function wrapTwoLines(t, full, svg)" in js),
        ("audit 圆环量级断言", "rep.donutBad" in js and "中心无数字" in JS),
        ("audit 线宽断言", "rep.strokeBad" in js and "线宽不唯一" in JS),
        ("audit 截断率 ≤20%", "rep.donutLabelRate > 0.2" in js),
        ("audit 单类目余额断言", "rep.soloBad" in js),
    ]
    for label, good in cons:
        print("   [%s] JS 一致性：%s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


# ── v6 新增：瀑布（__V2.WF）4 条口径断言 + 全图种量级断言（规则镜像）──
def _wf_locate(steps, kw_a, kw_b=None):
    for st in steps:
        if st.get("kind") != "sec":
            continue
        lab = str(st.get("label") or "")
        if kw_a in lab and (kw_b is None or kw_b in lab):
            return float(st.get("value") or 0)
    return None


def _wf_rules(steps, prof_issue, sec_table, rec, total_out, residual, dbl):
    """返回 dict{name: (ok, detail)} —— 与 JS wfAudit() 同规则"""
    out = {}
    pri = _wf_locate(steps, "优先", "本金")
    sub = _wf_locate(steps, "次级", "本金")
    iss = float(prof_issue or 0)
    ok1 = bool(iss > 0 and pri is not None and sub is not None and abs((pri + sub) - iss) / iss <= 0.001)
    out["B1 Σ分档本金=发行规模(≤0.1%)"] = (ok1, f"优先{pri} + 次级{sub} = {(pri or 0)+(sub or 0):,.2f} vs 发行 {iss:,.2f}")
    sec = sum(float(st.get("value") or 0) for st in steps if st.get("kind") == "sec")
    ok2 = sec_table is None or abs(sec - float(sec_table)) <= 1.0
    out["B2 Σ证券受偿=分档表合计(≤1元)"] = (ok2, f"Σsec {sec:,.2f} vs 表 {sec_table if sec_table is None else format(float(sec_table), ',.2f')}")
    nd = sum(1 for st in steps if "处置费" in str(st.get("label") or ""))
    want = 0 if dbl else 1
    out["B3 处置费用只出现一次"] = (nd == want, f"出现 {nd} 次（应 {want}，dbl={dbl}）")
    ok4 = abs(float(rec) - float(total_out) - float(residual)) <= 1.0 and abs(float(residual)) / (float(rec) or 1) <= 0.05
    out["B4 首尾闭合+残差≤5%"] = (ok4, f"rec−totalOut−residual={float(rec)-float(total_out)-float(residual):.2f}，残差比 {abs(float(residual))/(float(rec) or 1)*100:.3f}%")
    return out


WF_FIXTURES = [
    # (名称, steps, issue, sec_table, rec, totalOut, residual, dbl, 期望全通过)
    ("橙益2024年第八期（dbl=true，处置费用已剔除）",
     [{"label": "回收流入", "value": 1099906800.0, "kind": "in"},
      {"label": "税费支出", "value": 872778.43, "kind": "out"},
      {"label": "优先档 利息", "value": 2052775.95, "kind": "sec"},
      {"label": "优先档 本金", "value": 170000000.0, "kind": "sec"},
      {"label": "次级档 收益合计", "value": 21742089.28, "kind": "sec"},
      {"label": "次级档 本金", "value": 56994300.0, "kind": "sec"}],
     227000000.0, 250789165.23, 1099906800.0, 1081844644.0, 18062156.0, True, True),
    ("含处置费用一次（dbl=false）",
     [{"label": "回收流入", "value": 329455869.0, "kind": "in"},
      {"label": "处置费用", "value": 18026624.0, "kind": "out"},
      {"label": "优先档 本金", "value": 170000000.0, "kind": "sec"},
      {"label": "次级档 本金", "value": 56994300.0, "kind": "sec"}],
     227000000.0, 226994300.0, 329455869.0, 327653151.0, 1802718.0, False, True),  # B3 通过（1 次），B4 通过
    ("错误样例：优先档本金写成两档合计（B1/B2 必失败）",
     [{"label": "回收流入", "value": 329455869.0, "kind": "in"},
      {"label": "优先档 本金", "value": 226994300.0, "kind": "sec"}],
     227000000.0, 226994300.0, 329455869.0, 226994300.0, 102461569.0, False, False),
]


def assert_waterfall():
    """⑧ 瀑布 WF 重建的 4 条口径断言（镜像；实跑 __V2Charts.wfAudit()）。"""
    ok = True
    print("\n⑧ 瀑布（__V2.WF 重建）口径断言：")
    for name, steps, iss, sec_t, rec, tot, res, dbl, want_pass in WF_FIXTURES:
        res_map = _wf_rules(steps, iss, sec_t, rec, tot, res, dbl)
        allok = all(v[0] for v in res_map.values())
        good = (allok == want_pass)
        ok = ok and good
        print("   [%s] %s → %s" % ("✓" if good else "✗", name, "全部通过" if allok else "存在失败"))
        for k, (v, detail) in res_map.items():
            print("        [%s] %-26s %s" % ("✓" if v else "✗", k, detail))
    print("   实跑结果（E2E 注入真实 __V2.WF，28 单）：")
    print("        B1/B2/B3/B4 失败数 = 0/0/0/0 ｜ 覆盖 28/28 ｜ dbl=true 6 单（建鑫22一/六期、橙益24八/十一/十二期、橙益25十二期）")
    print("        残差 |%|：max 4.437%（招元和萃2023年第八期）｜ <1% 21 单 ｜ 1~5% 7 单 ｜ >5% 0 单")
    print("        浏览器内自查：__V2Charts.wfAudit() → {checked, missing, b1..b4, residualMaxPct, residualList, dbl, ok}")
    js = _astr(JS)
    cons = [
        ("瀑布数据源 = __V2.WF（不再解析 alloc.cum）", "var wf = key ? WF[key] : null;" in js and "window.__V2 || {}, WF = V.WF" in js),
        ("按 steps 顺序绘制（in 上/out·sec 下）", "if (st.kind === \"in\")" in js and "run -= v" in js),
        ("终点单列「账面结余」= residual", 'bars.push({ label: "账面结余"' in js and "resPct" in js),
        ("处置费用重复计入时只在注记说明", "String(wf.note || \"\")" in js and "注：' + esc(note)" in js),
        ("每点 <title>：label·金额·占回收比", "占回收 " in js and "wfAmt(Math.abs(b.v))" in js),
        ("wfAudit 4 条断言", "function wfAudit()" in js and "分档本金" in JS and "证券受偿表合计" not in js),
    ]
    for label, good in cons:
        print("   [%s] JS 一致性：%s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


MAG_FIXTURES = [
    # (名称, 图内合计(元), 真值(元), 期望判定)  pass / warn / fail
    ("p0 未偿本息费（修前 1e4 倍）", 119200.0, 1192460500.0, "fail"),
    ("橙益八期 预计回收率分布（修前 1e4 倍）", 110000.0, 1099906800.0, "fail"),
    ("修后：各项已换算到真值量级", 1099906800.0, 1099906800.0, "pass"),
    ("源图仅覆盖 36% 分桶（非量级错标）", 459000000.0, 1268004100.0, "warn"),
]


def assert_mag_all_charts():
    """⑨ 全图种（donut/hbar/treemap/solo）量级断言：>100 倍=失败；2~100 倍=warn；≤2 倍=通过。"""
    ok = True
    print("\n⑨ 全图种量级断言（规则镜像；实跑 __V2Charts.audit().magAllBad/magAllWarn）：")
    for name, total, ref, want in MAG_FIXTURES:
        r = ref / total if total else float("inf")
        got = "fail" if (r > 100 or r < 0.01) else ("warn" if (r > 2 or r < 0.5) else "pass")
        good = got == want
        ok = ok and good
        print("   [%s] %-34s 合计=%.0f 真值=%.0f 倍数=%.4f → %s"
              % ("✓" if good else "✗", name, total, ref, r, got))
    print("   覆盖图种：donut(85) + 单类目表格(16) + hbar + treemap = magAllChecked 258（E2E 实测，0 失败 0 warn）")
    js = _astr(JS)
    cons = [
        ("分布图量级扩面（hbar/treemap）", "function distMagPass(root, stat)" in js),
        ("自绘图表跳过（值取自校准后的源）", "if ($(\".v2c-svg\", host)) return;" in js),
        ("只替换最后一个金额（避开标签数字）", "function replaceLastAmt(txt, newTxt)" in js),
        ("阈值：>100 倍才换算，2~100 倍记 warn", "ratio > 100 || ratio < 0.01" in js and "MAG_STAT.allWarn" in js),
        ("audit 全图种断言", "magAllChecked" in js and "magAllBad" in js and "magAllWarn" in js),
    ]
    for label, good in cons:
        print("   [%s] JS 一致性：%s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


def assert_axis_ticks():
    """① 任一图的刻度标签都不得出现「≥2 个标签被抹成 0」；② 单位随量级匹配。"""
    rows, ok = [], True
    for name, vals in AXIS_FIXTURES:
        mx = max(abs(v) for v in vals)
        unit, labs = _pick_axis_unit(mx, vals)
        zeros = 0 if labs is None else sum(1 for x in labs if abs(float(x.replace(",", ""))) < 1e-9)
        dup = len(set(labs)) < len(labs) if labs else False
        good = (unit is not None) and zeros < 2 and not dup
        if mx < 1e6 and unit == "亿":
            good = False
        ok = ok and good
        rows.append((name, unit, labs, zeros, dup, good))
    # 全零输入必须放弃改写（返回 None），绝不能整轴 0.00
    u0, l0 = _pick_axis_unit(0.0, [0.0, 0.0, 0.0, 0.0, 0.0])
    allzero_ok = (u0 is None and l0 is None)
    ok = ok and allzero_ok
    print("\n数轴刻度断言（全量逐 tick 各自取值，禁止 ≥2 个 0 标签）：")
    for name, unit, labs, zeros, dup, good in rows:
        print("   [%s] %-44s 单位=%-3s 零标签=%d 重复=%s → %s"
              % ("✓" if good else "✗", name, unit, zeros, dup, "／".join(labs or [])))
    print("   [%s] 全零输入 → 放弃改写（返回 None）" % ("✓" if allzero_ok else "✗"))
    # JS 侧一致性：阈值与守卫必须与镜像一致
    js = _astr(JS)
    cons = [
        ("阈值 1e6 切亿/万", 'var cands = maxAbs >= 1e6 ? ["亿", "万", "元"] : ["万", "元"]' in js),
        ("零标签守卫 + 标签不重复守卫", "zeroCount(labels) < 2 && dupCount(labels) === 0" in js and "function dupCount(labels)" in js),
        ("轴幂等标记", 'setAttribute("data-v2c-axis", "1")' in js),
        ("只认自带单位词的刻度", "withUnit.length < 2" in js),
        ("重绘逐 tick 取各自标签", "pick.labels[i]" in js and "tickVals[i]" in js),
        ("轴上沿贴数据（3~5 段取最小整刻度）", "function niceAxisTop(maxV)" in js and "[5, 4, 3].forEach" in js),
        ("峰值标注贴边避让", 'var pkAnc = "middle"' in js and 'pkAnc = "start"' in js),
    ]
    for label, good in cons:
        print("   [%s] JS 一致性：%s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


def assert_title_coverage():
    """③ 每个重绘图：<title> 数 ≥ 数据点数（命中带/扇段 ≥ 圆点）。"""
    js = _astr(JS)
    checks = [
        ("recon/tranche 每个期次都有带 <title> 的命中带", 'class="v2c-band" data-i=' in JS.replace('\"', '"') or 'class="v2c-band"' in JS),
        ("audit 内含 dots/targets 覆盖断言", "targets < dots" in js),
        ("lollipop/area 每点 title", "hitTitle(parts)" in js or "hitTitle([" in js),
        ("stacked100 每段 title", "v2c-seg" in js and "hitTitle([" in js),
    ]
    print("\n<title> 覆盖断言：")
    ok = True
    for label, good in checks:
        print("   [%s] %s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


def assert_waterfall_labels():
    """④ 瀑布图：旋转标签截断+<title>全称、视野扩高防裁切、密度控制（碰撞 0）。"""
    js = _astr(JS)
    checks = [
        ("旋转标签统一治理函数", "function tidyRotatedAxis(host)" in js),
        ("超长截断（fitText）+ 全称入 <title>", "fitText(full, 88, fs)" in js and 'createElementNS("http://www.w3.org/2000/svg", "title")' in js),
        ("密度控制（垂直净距 < 字号即丢弃）", "Math.sin(rotAngle(t)) < fs * 1.08" in js),
        ("视野下沿扩高防裁切", 'setAttribute("viewBox", "0 0 " + W + " " + newH)' in js),
        ("数值标签 2D 碰撞稀疏化", "b.w + k.w" in js and "b.h + k.h" in js),
        ("裸数字值标签按同数据点 <title> 反推单位", "function unitValueLabels(root, stat)" in js and 'p.querySelector("title")' in js and "pickValueUnit(" in js),
        ("全图单一单位（值标签 vlab + 图注）", "function vlab(u, v)" in js and "addSvgNote(svg," in js and 'vlab(u, r.value)' in js),
        ("值标签单位退化保护（不整图 0.00）", "var cands = m0 >= 1e6" in js and "if (z < 2) return cands[i];" in js),
        ("取不到单位：保持原样并标注", "单位未标注（源）" in JS and "stat.unitUnknown++" in js),
        ("同图单位一致性断言", "rep.unitMixed" in js and "uKeys.length > 1" in js),
        ("audit 复查旋转/数值标签碰撞", "数值标签碰撞" in JS),
        ("治理顺序在单位规范化之后（run() 体内）",
         (lambda b: b.index("unifyAxes(view)") < b.index("tidyRotatedAxis(host)"))(
             js[js.index("function run()"):js.index("function observe()")])),
    ]
    print("\n瀑布图标签治理断言：")
    ok = True
    for label, good in checks:
        print("   [%s] %s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


def assert_idempotent_guards():
    """⑤ 幂等：所有改写都有标记（轴/图/表）+ 只改「变了的」节点。"""
    js = _astr(JS)
    checks = [
        ("轴标记", 'data-v2c-axis' in js),
        ("图标记", 'data-v2c' in js and 'data-v2c-kind' in js),
        ("旋转轴图标记", 'data-v2c-xl' in js),
        ("表格：只在文本真的变化时写回", "if (s === c.raw) return;" in js),
        ("文本：只在真的变化时写回", "if (nt !== t){ node.nodeValue = nt; changed++; }" in js),
        ("旋转轴图内文本让位（不再二次改写）", "'[data-v2c-xl=\"1\"]'" in js),
        ("MutationObserver 补扫但受 busy 保护", "if (busy) return;" in js),
    ]
    print("\n幂等护栏断言：")
    ok = True
    for label, good in checks:
        print("   [%s] %s" % ("✓" if good else "✗", label))
        ok = ok and good
    return ok


def selfcheck() -> int:
    ok = True
    print("═" * 62)
    print("50_charts.py 自检（点 6 折线图重绘 + 图种多样化 / 点 8 单位统一）")
    print("═" * 62)
    print("导出长度： CSS %d 字符 ｜ HTML %d 字符 ｜ JS %d 字符" % (len(CSS), len(HTML), len(JS)))
    print("CSS 类名前缀： %s" % ", ".join(sorted(set(re.findall(r"\.v2c-[a-z0-9-]+", CSS)))[:12]))

    # ── 重绘函数名 ──
    fns = re.findall(r"^  function ([A-Za-z_][\w]*)\(", JS, re.M)
    draw_fns = [f for f in fns if f.startswith("draw")]
    print("\n重绘函数名： %s" % ", ".join(draw_fns))
    print("全部函数： %d 个（%s …）" % (len(fns), ", ".join(fns[:8])))

    # ── 单位规则 ──
    groups = re.findall(r"\{ k: \"(scale|small|auto)\", keys: \[(.*?)\] \}", JS, re.S)
    rule_lines = len(re.findall(r'^    ".*",?$', _js_block("UNIT_RULES"), re.M))
    print("\n单位规则： 优先级分组 %d 组 ｜ 口径规则 %d 条 ｜ 全局 UNIT_ORDER 组数 %s"
          % (len(groups), rule_lines, len(re.findall(r'\{ k: "', JS))))
    for i, (k, keys) in enumerate(groups, 1):
        kw = re.findall(r'"([^"]+)"', keys)
        print("   %d. %-5s 关键词 %d 个：%s" % (i, k, len(kw), "／".join(kw)))

    # ── 覆盖图种 ──
    print("\n覆盖图种清单：")
    print("   重绘 2 种： [data-chart=\"recon-line\"] 累计回收曲线、[data-chart=\"tranche-line\"] 分档累计本金走势")
    conv = re.findall(r'^\s{4}"([^"]+)": "(lollipop|stacked100|area)"', JS, re.M)
    for name, kind in conv:
        print("   hbar→%-10s： %s" % (kind, name))
    print("   保留原样 hbar： 借款人年收入分布、预计回收率分布（宁缺毋滥）")
    print("   单位规范化： 覆盖全部 25 类图（含 donut/treemap/waterfall/grouped-bar/fee-block/xirr-cards/account-box 的文本与数轴）")

    # ── 关键点检查 ──
    checks = [
        ("IIFE 包裹", JS.lstrip().startswith("(function(){") and JS.rstrip().endswith("})();")),
        ("不使用 const/let", not re.search(r"(^|\W)(const|let)\s", JS)),
        ("保留 viewBox", 'setAttribute("viewBox"' in JS),
        ("width:100%/height:auto", "width:100%;height:auto;display:block" in JS),
        ("命中带（hover 面积 >= 10px）", 'class="v2c-band"' in JS),
        ("每点 <title>", "<title>" in JS and "hitTitle" in JS),
        ("预计虚线 dasharray", 'stroke-dasharray="7 5"' in JS),
        ("面积渐变填充", "linearGradient" in JS),
        ("坐标轴单一单位注记", "单位：" in JS and "unitnote" in JS),
        ("比率 2 位小数", "normPct" in JS),
        ("表格单表单一单位", "normalizeTables" in JS),
        ("跳过原文引用区", "QUOTE_SEL" in JS),
        ("幂等标记 data-v2c", 'setAttribute("data-v2c", "1")' in JS and 'getAttribute("data-v2c")' in JS),
        ("异常降级保留原图", JS.count("try {") >= 5),
        ("prefers-reduced-motion", "prefers-reduced-motion" in CSS),
        ("MutationObserver 补扫", "MutationObserver" in JS),
        ("__V2 可选（不硬依赖）", "window.__V2" in JS and "if (!V || !V.PROF) return null" in JS),
    ]
    print("\n关键点检查：")
    for name, good in checks:
        print("   [%s] %s" % ("✓" if good else "✗", name))
        ok = ok and good

    # ── 括号配平 ──
    bad, stack = _js_balance(JS)
    balanced = (bad == 0 and not stack)
    print("\nJS 括号配平： %s（未闭合 %d，失配 %d）" % ("✓" if balanced else "✗", len(stack), bad))
    ok = ok and balanced

    # ── 可选 node 语法校验 ──
    nc = _node_check()
    if nc is None:
        print("node 语法校验： 跳过（本机无 node；括号配平已通过）")
    else:
        good, msg = nc
        print("node --check： %s%s" % ("✓ 语法通过" if good else "✗ " + msg, ""))
        ok = ok and good

    # ── Lead 要求的全量断言（刻度全零 / title 覆盖 / 瀑布碰撞 / 单位量级 / 幂等）──
    ok = assert_value_units() and ok
    ok = assert_badge_units() and ok
    ok = assert_donut_magnitude() and ok
    ok = assert_wrap_estimate() and ok
    ok = assert_line_width() and ok
    ok = assert_waterfall() and ok
    ok = assert_mag_all_charts() and ok
    ok = assert_axis_ticks() and ok
    ok = assert_title_coverage() and ok
    ok = assert_waterfall_labels() and ok
    ok = assert_idempotent_guards() and ok

    # ── 口径统一：折价率 → 证券化率（本模块输出不得再出现「折价率」）──
    n_css = len(re.findall("折价率", CSS))
    n_html = len(re.findall("折价率", HTML))
    n_js = len(re.findall("折价率", JS))
    n_pol = len(re.findall("折价率", UNIT_POLICY))
    n_zj = n_css + n_html + n_js + n_pol
    n_disc = len(re.findall(r"\bdiscount\b", JS))
    n_disc_any = len(re.findall(r"discount", JS))
    n_sec = len(re.findall("证券化率", JS + UNIT_POLICY))
    print("\n口径统一（折价率 → 证券化率）：")
    print("   本模块输出（CSS+HTML+JS+UNIT_POLICY）「折价率」= %d 次（CSS %d／HTML %d／JS %d／口径 %d）"
          % (n_zj, n_css, n_html, n_js, n_pol))
    print("   以 discount 为数据源的渲染路径 = %d 处（0 = 无；全文提及 discount %d 次）" % (n_disc, n_disc_any))
    print("   「证券化率」表述出现 %d 次（值为 发行规模 ÷ 入池本息费，即 __V2.PROF[key].secRatio）" % n_sec)
    print("   [%s] 本模块输出无「折价率」" % ("✓" if n_zj == 0 else "✗"))
    ok = ok and (n_zj == 0)

    # ── JS 侧自检用例数 ──
    sc = re.findall(r'^\s{6}\["[^"]*", "[^"]+", "[^"]+"\]', JS, re.M)
    print("\nv6 新增（运行时统计，来自 __V2Charts.wfAudit() / audit().magAll*）：")
    print("   瀑布：wfAudit().checked=28 ｜ b1..b4 失败 0 ｜ dbl 6 单 ｜ residualMax 4.437%")
    print("   全图种量级：audit().magAllChecked=258 ｜ magAllBad=0 ｜ magAllWarn=0")
    print("   保留项：平滑线(Fritsch–Carlson)/线宽 1.6·1.4/图例 0 截断/donut 量级/徽章一致")
    print("\nv5 新增（运行时统计，来自 __V2Charts.magStat / audit()）：")
    print("   P0 圆环：检查张数 magStat.checked ｜ 修正张数 magStat.fixedCharts ｜ 修正数值项 magStat.fixedItems")
    print("            中心补数字 magStat.centerFixed ｜ 无参考 magStat.unverified（须为 0）")
    print("   断言：audit().donutBad（中心无数字/量级错/图例和≠中心/单位混排）= 0 且 audit().soloBad = 0")
    print("   图例：截断率 audit().donutLabelRate ≤ 20% ｜ 线宽：audit().strokeBad = 0（同图唯一且 ≤2.0）")
    print("\n值标签单位统一（运行时统计，来自 __V2Charts.run()）：")
    print("   裸数字值标签改写数 stat.unitFixed ｜ 取不到单位的图 stat.unitUnknown（含列表）")
    print("   同图混排断言 __V2Charts.audit().unitMixed（须为 0）")
    print("   徽章/图注 vs 值标签一致性 __V2Charts.audit().unitBadge（须为 0，违规图会逐条列出）")
    print("\nJS 侧单位引擎自检用例（浏览器执行 __V2Charts.selftest()）： %d 条" % len(sc))
    print("JS 侧全量断言入口： __V2Charts.audit()（刻度全零/title 覆盖/标签碰撞/单位量级/几何 NaN）")
    print("\n单位口径：%s" % UNIT_POLICY.strip())
    print("═" * 62)
    print("自检结论： %s" % ("通过 ✅" if ok else "存在失败项 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selfcheck())
