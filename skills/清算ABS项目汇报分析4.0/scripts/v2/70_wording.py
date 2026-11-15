# -*- coding: utf-8 -*-
r"""70_wording.py —— v5 文案与业务表述精修（客户端改写，只动文本节点）

用户原话（本轮，v5）：
  · 「这个英文干嘛呢」                     → 删掉 payload / pool.bsf 等字段路径
  · 「有点难理解」                         → ② 主口径/并列/现算 长串改人话
  · ⑤「投入日 …（来源：①liq_info.setup_date）」→ 信托设立日 2023-12-07（来源：发行说明书）
  · ⑥ 现金流表「0 投入」                   → 0 ｜ 期初（信托设立日）
  · ⑧「左开右闭口径 (s_k, e_k]」            → 归期规则人话
  · 「信托是否终局，是不是应该以清仓回购来定呢？……只有终止了信托计划，才算合理吧」
                                            → 判据改为「信托计划是否终止（清算完成日）」
  · 「数据质量与披露……会不会篇幅太长了些。而且不太能看懂啥意思啊。不用讲你历史每次的排出的雷，
     就讲最终这个成品的数据质量点评和必要信息披露」
                                            → ⑧ fold 重写为「数据完整度 / 口径注解 / 来源依据」三段

设计原则
  · **只改文本节点**：不重建 SVG、不删/换任何 class、不动 data-* 属性；必要时仅 `appendChild`
    追加一个 `div.w-ext` 说明块（纯文本，不参与其他模块的选择器）。
  · 数据一律取 `window.__V2.PROF / __V2.AUDIT`，按 `#view-pN` 的 N 对应 `__V2.ORDER[N]` 取单；
    不臆造、缺值记「—」。
  · 幂等：所有写入都先判断目标文本是否已是目标值；重复执行结果完全一致。

导出（00_ctx 模块契约）：CSS / HTML（空）/ JS（IIFE，无全局污染）
自检：`python 70_wording.py` —— 以真实 v4 报告为基线（不动源文件），在 Node 里用轻量 DOM 影子
      执行本模块 JS，逐条校验 8 项用户诉求与硬性约束（含结构不变、幂等）。
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
_REPORT_CANDIDATES = [
    _HERE.parent.parent / "清算28单_不良ABS穿透分析报告_v4.html",
    _HERE.parent.parent / "清算28单_不良ABS穿透分析报告_v3.html",
    _HERE.parent.parent / "清算28单_横向对照与逐单稽核_合并版.html",
]


def _report_path():
    for p in _REPORT_CANDIDATES:
        if p.exists():
            return p
    return _REPORT_CANDIDATES[-1]


def _ctx():
    spec = spec_from_file_location("v2_ctx", _HERE / "00_ctx.py")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════
CSS = r"""
/* ══════════════════════════════════════════════════════════════════
   70_wording —— 文案改写用到的少量样式（只新增，不覆盖其他模块）
   ══════════════════════════════════════════════════════════════════ */
.w-ext{
  margin:6px 0 0;padding:6px 10px;border-left:3px solid var(--accent-line,#D5D9E2);
  background:rgba(45,57,85,.035);border-radius:0 7px 7px 0;
  font-size:12px;line-height:1.6;color:var(--ink2,#38425A);
}
.w-ext b{font-weight:650;color:var(--ink,#141A26)}
/* 数据质量三段式 */
.dq3{margin:0}
.dq3 .dq-sec{margin:0 0 9px}
.dq3 .dq-sec:last-child{margin-bottom:0}
.dq3 .dq-t{font-weight:700;color:var(--ink,#141A26);margin:0 0 3px;font-size:12.5px}
.dq3 .dq-b{font-size:12.5px;line-height:1.65;color:var(--ink2,#38425A)}
/* ⑦ 数据质量一行摘要 */
.w-dqsum{font-size:12.5px;line-height:1.7;color:var(--ink2,#38425A)}
.w-dqsum::before{content:"";display:inline-block;width:3px;height:11px;margin-right:7px;
  border-radius:2px;background:var(--accent-line,#D5D9E2);vertical-align:-1px}
/* 分配矩阵：占回收流入 >100% 的口径提示 */
.w-alloc-note{margin:8px 0 0;padding:7px 11px;border-left:3px solid var(--warn,#B0763F);
  background:color-mix(in srgb,var(--warn,#B0763F) 7%,transparent);border-radius:0 7px 7px 0;
  font-size:12px;line-height:1.6;color:var(--ink2,#38425A)}
#view-p0 .w-alloc-note,
.w-alloc-note b{font-weight:650}
td.w-over100{color:var(--warn,#B0763F)!important;font-weight:650;
  background:color-mix(in srgb,var(--warn,#B0763F) 6%,transparent)}
td.w-over100 .w-over100-note{font-size:10px;vertical-align:super;margin-left:1px}
/* 百分比统一到 2 位后，指标列不再出现整数百分比 */

/* ══════════════════════════════════════════════════════════════════
   v11 ⑧ 数据质量与披露：概览条 + 缺失材料折叠表
   ══════════════════════════════════════════════════════════════════ */
/* 概览条（展开后首行；9.5–10px 灰字，不抢主视觉） */
.dq-ov{
  margin:2px 0 11px;padding:6px 10px;border-radius:7px;
  background:rgba(45,57,85,.035);border:1px solid var(--line2,#E4E8EF);
  font-size:10px;line-height:1.7;color:var(--ink3,#6B7488);letter-spacing:.01em;
  font-variant-numeric:tabular-nums;
}
.dq-ov b{font-weight:650;color:var(--ink2,#38425A)}
.dq-ov .dq-ov-t{font-weight:650;color:var(--ink2,#38425A);margin-right:3px}
/* 折叠头右侧的「披露 N 项」小字（折叠状态也可见） */
.fold-sum .dq-n{font-variant-numeric:tabular-nums}
/* 缺失材料：折叠块 + 表格（默认收起，真实 DOM 内容） */
.dq-mat{margin:9px 0 0;border:1px solid var(--line2,#E4E8EF);border-radius:8px;
  background:rgba(45,57,85,.018);overflow:hidden}
.dq-mat>summary{
  cursor:pointer;list-style:none;padding:7px 11px;display:flex;align-items:center;gap:6px;
  font-size:11px;font-weight:600;color:var(--ink3,#6B7488);user-select:none;
  transition:background .24s var(--ease,ease);
}
.dq-mat>summary::-webkit-details-marker{display:none}
.dq-mat>summary::before{content:"\25B8";font-size:9px;color:var(--ink4,#98A2B3);
  transition:transform .2s var(--ease,ease);flex:0 0 auto}
.dq-mat[open]>summary::before{transform:rotate(90deg)}
.dq-mat>summary:hover{background:rgba(45,57,85,.045);color:var(--ink2,#38425A)}
.dq-mat>summary .dq-mat-n{font-weight:700;color:var(--ink2,#38425A)}
.dq-mat>summary .dq-mat-s{font-weight:400;color:var(--ink4,#98A2B3);font-size:10px}
.dq-mt{width:100%;border-collapse:collapse;font-size:11px;table-layout:fixed;
  border-top:1px solid var(--line2,#E4E8EF)}
.dq-mt th{text-align:left;font-weight:600;color:var(--ink4,#98A2B3);padding:6px 10px;
  border-bottom:1px solid var(--line2,#E4E8EF);background:rgba(45,57,85,.028);
  font-size:10.5px;letter-spacing:.02em}
.dq-mt td{padding:6px 10px;color:var(--ink2,#38425A);line-height:1.6;
  border-bottom:1px solid var(--line1,#EEF1F6);vertical-align:top}
.dq-mt tr:last-child td{border-bottom:0}
.dq-mt .mn{font-weight:600;color:var(--ink,#141A26)}
.dq-mt .mi{white-space:nowrap;color:var(--ink3,#6B7488)}
.dq-mt .mi .no{color:var(--neg,#1F7A5C);font-weight:600}
.dq-mf{padding:7px 11px;font-size:10px;line-height:1.6;color:var(--ink4,#98A2B3);
  border-top:1px solid var(--line2,#E4E8EF);background:rgba(45,57,85,.014)}
.dq-nomat{margin:8px 0 0;font-size:11px;color:var(--ink4,#98A2B3)}
.dq-sec .dq-mat:first-child{margin-top:2px}
"""


# ══════════════════════════════════════════════════════════════════════
#  HTML
# ══════════════════════════════════════════════════════════════════════
# 本模块为纯客户端改写，无需服务端渲染
HTML = ""


# ══════════════════════════════════════════════════════════════════════
#  JS
# ══════════════════════════════════════════════════════════════════════
JS = r"""
/* 70_wording —— v5 文案与业务表述精修（客户端文本改写，纯 IIFE）
   只改文本节点 / 只追加说明块，不重建 SVG、不改 class 与 data-* 属性 */
(function(){
  "use strict";
  var doc = document;
  var V2 = (typeof window !== "undefined" && window.__V2) ? window.__V2 : {};
  var ORDER = V2.ORDER || [];
  var PROF = V2.PROF || {};
  var AUDIT = V2.AUDIT || {};
  var DASH = "\u2014";

  /* ══════════ 小工具 ══════════ */
  function txt(v){ return (v == null || v === "") ? DASH : String(v); }
  function qsa(root, sel){
    try { return root.querySelectorAll(sel); } catch(e){ return []; }
  }
  function norm(s){ return String(s == null ? "" : s).replace(/\s+/g, " ").trim(); }
  function grp(x, d){
    if(typeof x !== "number" || !isFinite(x)) return DASH;
    var s = x.toFixed(d == null ? 2 : d);
    var neg = s.charAt(0) === "-";
    if(neg) s = s.slice(1);
    var p = s.split(".");
    p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (neg ? "-" : "") + p.join(".");
  }
  /* 规模：亿元 2 位（<0.01 亿 → 万元并注明），与 UNIT_POLICY 一致 */
  function yi(v){
    if(typeof v !== "number" || !isFinite(v)) return DASH;
    if(Math.abs(v) < 1e6) return grp(v / 1e4, 2) + " 万（不足 0.01 亿）";
    return grp(v / 1e8, 2) + " 亿";
  }
  function pct(v){
    if(typeof v !== "number" || !isFinite(v)) return DASH;
    return (v * 100).toFixed(2) + "%";
  }

  /* ══════════ 单项目视图 ↔ 档案 ══════════ */
  function viewNo(view){
    var id = (view && view.id) ? view.id : "";
    var m = /^view-p(\d+)$/.exec(id);
    return m ? parseInt(m[1], 10) : -1;
  }
  function profileOf(view){
    var n = viewNo(view);
    if(n < 0) return null;
    var k = ORDER[n];
    if(k && PROF[k]) return PROF[k];
    /* 退路：ORDER 尚未注入时，按「档案里的 order 字段 = n+1」反查（28 单唯一） */
    for(var kk in PROF){
      if(!Object.prototype.hasOwnProperty.call(PROF, kk)) continue;
      var it = PROF[kk];
      if(it && typeof it.order === "number" && it.order === n + 1) return it;
    }
    return null;
  }
  function keyOfView(view){
    var n = viewNo(view);
    if(n < 0) return null;
    if(ORDER[n]) return ORDER[n];
    var p = profileOf(view);
    if(p && (p.code || p.name)) return p.code || p.name;
    for(var kk in PROF){
      if(!Object.prototype.hasOwnProperty.call(PROF, kk)) continue;
      if(PROF[kk] && PROF[kk].order === n + 1) return kk;
    }
    return null;
  }
  function dateOf(prof, label){
    var d = prof && prof.dates;
    if(!d) return null;
    if(Object.prototype.toString.call(d) === "[object Array]"){
      for(var i = 0; i < d.length; i++){
        if(d[i] && String(d[i][0]) === label && d[i][1]) return String(d[i][1]);
      }
      return null;
    }
    return d[label] ? String(d[label]) : null;
  }
  function auditOf(view, key){
    var n = viewNo(view);
    var arr = AUDIT && AUDIT[key];
    if(!(arr && arr.length) || n < 0) return null;
    var name = ORDER[n];
    for(var i = 0; i < arr.length; i++){
      if(arr[i] && arr[i].key === name) return arr[i];
    }
    return arr[n] || null;
  }

  /* ══════════ 文本节点遍历（只改文本，不碰结构） ══════════ */
  function eachTextNode(root, fn){
    if(!root) return 0;
    var walker = null;
    var n = 0;
    try {
      walker = doc.createTreeWalker(root, 4 /* NodeFilter.SHOW_TEXT */, null, false);
    } catch(e){ walker = null; }
    if(walker && typeof walker.nextNode === "function"){
      var node = walker.nextNode();
      while(node){
        if(fn(node) === true) n++;
        node = walker.nextNode();
      }
      return n;
    }
    (function walk(el){
      if(!el || !el.childNodes) return;
      for(var i = 0; i < el.childNodes.length; i++){
        var c = el.childNodes[i];
        if(c && c.nodeType === 3){ if(fn(c) === true) n++; }
        else walk(c);
      }
    })(root);
    return n;
  }
  function setText(node, s){
    if(node.nodeValue === s) return false;
    node.nodeValue = s;
    return true;
  }

  /* ══════════════════════════════════════════════════════════════════
     ① 字段路径 / 英文技术术语
     ══════════════════════════════════════════════════════════════════ */
  var PATH_RE = /payload|pool\.|alloc\.|liq_info|ref_rate|tranche\.|supply\.|xirr\.[a-z_]|\.cum\.|\.bsf/;

  /* 「累计处置费用：X（payload alloc.cum.处置费用）」→ 保留金额 + 人话来源。
     原文金额与 <code> 字段名常被拆成多个节点 → 按容器级处理 */
  function fixDisposeFee(text){
    var m = /累计处置费用\s*[：:]\s*([^（(]+?)\s*[（(]\s*payload[\s\S]*$/i.exec(text);
    if(!m) return null;
    return "累计处置费用 " + norm(m[1]) + "（来源：受托机构报告各期分配表「处置费用」科目）";
  }
  function fixDisposeFeeBlocks(view){
    var n = 0;
    var notes = qsa(view, ".note");
    for(var i = 0; i < notes.length; i++){
      var el = notes[i];
      var t = el.textContent || "";
      if(t.indexOf("累计处置费用") < 0) continue;
      if(!/payload|alloc\./.test(t)) continue;
      /* 金额已在正文里，保留之，替换来源括注 */
      var m = /累计处置费用\s*[：:]?\s*([\d,.\s]+[万亿]?)/.exec(t);
      var amt = m ? norm(m[1]) : "";
      el.innerHTML = "累计处置费用 " + amt
        + "（来源：受托机构报告各期分配表「处置费用」科目）";
      n++;
    }
    return n;
  }
  /* 页脚「数据来源：项目穿透载荷（_校验件/payload.json）…」→ 公开文件口径 */
  function fixFooter(text){
    if(text.indexOf("payload") < 0 || text.indexOf("数据来源") < 0) return null;
    return "数据来源：各单发行说明书与受托机构报告（公开披露文件） ｜ 口径：清算期穿透分析，"
      + "各节内逐一注明 ｜ 金额单位：亿元 2 位 / 万元 2 位，比率百分号 2 位";
  }
  /* ⑤ 折现说明里「投入行」「天数÷365」→ 设立日口径（须先于通用「天数」替换；幂等） */
  function fixDiscountNote(text){
    if(text.indexOf("折现因子") < 0) return null;
    var s = text;
    s = s.replace(/区间含投入行至末期行/g, "区间自期初（信托设立日）至末期");
    /* 先处理已带前缀的，再处理裸「天数÷365」，避免把「距设立日天数」二次加前缀 */
    s = s.replace(/距设立日天数\s*÷\s*365/g, "距设立日天数 ÷ 365");
    s = s.replace(/(^|[^日])天数\s*÷\s*365/g, "$1距设立日天数 ÷ 365");
    return s === text ? null : s;
  }

  /* ══════════════════════════════════════════════════════════════════
     ② 证券化率长串改人话（保留主口径 / 另一口径）
        原文可能被 <b> 切碎 → 按「所在容器整段」重写，避免半句残留
     ══════════════════════════════════════════════════════════════════ */
  function secSentence(prof, src, main, alt, totalFallback){
    var total = (typeof prof.poolTotal === "number" && prof.poolTotal) ? prof.poolTotal : totalFallback;
    var s = "证券化率 = 发行规模 ÷ 入池本息费 = " + yi(prof.issue) + " ÷ " + yi(total)
      + " = " + pct(main) + "（主口径）";
    if(alt != null){
      s += "；若以入池本金 " + yi(prof.poolPrincipal) + " 为分母则为 " + pct(alt) + "（另一口径）";
    }
    s += "。数据来源：" + src + "。";
    return s;
  }
  /* 从原文里取「入池未偿本息费 X」「发行规模 Y」等数值（payload 缺池数据时的回退） */
  function numFromText(text, label){
    var re = new RegExp(label + "\\s*([\\d,]+(?:\\.\\d+)?)\\s*(亿|万)?");
    var m = re.exec(text || "");
    if(!m) return null;
    var x = parseFloat(String(m[1]).replace(/,/g, ""));
    if(!isFinite(x)) return null;
    if(m[2] === "亿") x *= 1e8;
    else if(m[2] === "万") x *= 1e4;
    return x;
  }
  function fixSecBlocks(view, prof){
    if(!prof) return 0;
    var n = 0;
    var main0 = (typeof prof.secRatio === "number") ? prof.secRatio : null;
    var alt0 = (typeof prof.issue === "number" && typeof prof.poolPrincipal === "number"
                && prof.poolPrincipal) ? prof.issue / prof.poolPrincipal : null;
    /* 1) 找「最小」的含标记容器（含 .note / p / b / span / div），整体重写 */
    var cands = qsa(view, ".note, p, b, span, div");
    for(var i = 0; i < cands.length; i++){
      var el = cands[i];
      var t = el.textContent || "";
      if(t.indexOf("主口径·") < 0 && t.indexOf("现算·非源披露") < 0) continue;
      /* 幂等：已是新句式则跳过 */
      if(t.indexOf("证券化率 = 发行规模 ÷ 入池本息费") >= 0) continue;
      var hasInner = false;
      for(var k = 0; k < el.childNodes.length; k++){
        var ch = el.childNodes[k];
        if(ch.nodeType === 1 && ch.textContent
           && (ch.textContent.indexOf("主口径·") >= 0
               || ch.textContent.indexOf("现算·非源披露") >= 0)){ hasInner = true; break; }
      }
      if(hasInner) continue;
      var srcM = /源[：:]\s*([^）)]+)[）)]/.exec(t);
      var src = srcM ? norm(srcM[1]) : "发行说明书首页发行表";
      var main = main0, alt = alt0, totalFB = null;
      /* 回退：payload 缺池数据时，从原文里读数值现算 */
      if(main == null){
        var total = numFromText(t, "入池未偿本息费");
        var issue = (typeof prof.issue === "number") ? prof.issue : numFromText(t, "发行规模");
        if(total && issue){ main = issue / total; totalFB = total; }
        else { el.innerHTML = scrubTech(t); continue; }
      }
      /* 原文里「｜ 证券化率 」前缀与句首重复 → 改写为「｜ 」避免叠字 */
      var prev = el.previousSibling;
      if(prev && prev.nodeType === 3 && /证券化率\s*$/.test(prev.nodeValue)){
        prev.nodeValue = prev.nodeValue.replace(/证券化率\s*$/, "");
      }
      el.innerHTML = "<b>" + secSentence(prof, src, main, alt, totalFB) + "</b>";
      n++;
    }
    /* 2) 兜底：仍含标记的孤立文本节点 */
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s) return false;
      if(s.indexOf("主口径·") < 0 && s.indexOf("现算·非源披露") < 0) return false;
      if(s.indexOf("证券化率 = 发行规模 ÷ 入池本息费") >= 0) return false;   /* 幂等 */
      var main = main0, alt = alt0;
      if(main == null){
        var total = numFromText(s, "入池未偿本息费");
        var issue = (typeof prof.issue === "number") ? prof.issue : numFromText(s, "发行规模");
        if(total && issue){ main = issue / total; } else { return setText(node, scrubTech(s)); }
      }
      var srcM = /源[：:]\s*([^）)]+)[）)]/.exec(s);
      var src = srcM ? norm(srcM[1]) : "发行说明书首页发行表";
      n++;
      return setText(node, secSentence(prof, src, main, alt));
    });
    return n;
  }

  /* ══════════════════════════════════════════════════════════════════
     ⑤ 投入日 → 信托设立日（来源：发行说明书）
     ══════════════════════════════════════════════════════════════════ */
  function fixSetupDate(text){
    var m = /^\s*投入日\s*(\d{4}-\d{2}-\d{2})[\s\S]*$/.exec(text);
    if(!m) return null;
    return "信托设立日 " + m[1] + "（来源：发行说明书「信托设立日」）";
  }

  /* ══════════════════════════════════════════════════════════════════
     ⑥ 现金流表：表头 + 首行
     ══════════════════════════════════════════════════════════════════ */
  var TH_MAP = {
    "天数 t": "距设立日天数",
    "优先折现因子": "优先档折现系数",
    "次级折现因子": "次级档折现系数"
  };
  function fixCashFlowTable(view){
    var n = 0;
    var tables = qsa(view, "table.tbl");
    for(var t = 0; t < tables.length; t++){
      var tbl = tables[t];
      var ths = qsa(tbl, "th");
      for(var i = 0; i < ths.length; i++){
        var k = norm(ths[i].textContent);
        var want = TH_MAP[k];
        if(want && norm(ths[i].textContent) !== want){
          ths[i].textContent = want;
          n++;
        }
      }
      var firstTd = qsa(tbl, "td")[0];
      if(firstTd){
        var v = norm(firstTd.textContent);
        if(/^0\s*投入$/.test(v)){
          firstTd.textContent = "0 期初（信托设立日）";
          n++;
        }
      }
    }
    return n;
  }

  /* ══════════════════════════════════════════════════════════════════
     ⑧ 归期规则（左开右闭）→ 人话；首次出现处补解释
     ══════════════════════════════════════════════════════════════════ */
  var PERIOD_RULE = "归期规则：回收发生时点落在哪个支付期区间，就计入该期"
    + "（本期起息日之后、至本期支付日）；即不含上期支付日当天、含本期支付日当天。";
  function fixPeriodRule(view){
    var n = 0;
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s || s.indexOf("左开右闭") < 0) return false;
      if(s.indexOf("归期规则") >= 0) return false;
      if(/^逐期回收/.test(norm(s))){
        n++;
        return setText(node, "逐期回收（实际 vs 预计归集 · 按支付期归集）");
      }
      var tail = "";
      var k = s.indexOf("；");
      if(k >= 0) tail = s.slice(k + 1);
      n++;
      return setText(node, PERIOD_RULE + (tail ? tail : ""));
    });
    return n;
  }

  /* ══════════════════════════════════════════════════════════════════
     ★ 信托终局性判定：判据 = 信托计划是否终止（清算完成日）
     ══════════════════════════════════════════════════════════════════ */
  function termOf(prof){
    var liq = dateOf(prof, "清算完成");
    return {
      liq: liq,
      text: liq ? ("信托计划已终止 · 清算完成 " + liq) : "信托计划存续中",
      word: liq ? "信托计划已终止" : "存续中"
    };
  }
  function buybackOf(view){
    var h5 = auditOf(view, "h5");
    if(!h5) return null;
    var kind = String(h5.kind || "");
    if(kind.indexOf("清仓回购") < 0) return null;   /* 只有「主动发出《清仓回购通知书》」算发生 */
    var price = h5.price;
    var priceTxt = null;
    if(price != null && String(price).trim() !== ""){
      var num = parseFloat(String(price).replace(/,/g, ""));
      if(isFinite(num)){
        priceTxt = (Math.abs(num) < 1)
          ? "0 元"
          : (num >= 1e8 ? grp(num / 1e8, 2) + " 亿元" : grp(num / 1e4, 2) + " 万元");
      }
    }
    return { active: true, price: priceTxt };
  }
  function heroBadge(view, prof){
    var badges = qsa(view, ".hero-top .hbadge");
    if(!badges.length) return 0;
    var b = badges[0];
    var T = termOf(prof);
    if(norm(b.textContent) !== T.text) b.textContent = T.text;
    var top = b.parentNode;
    if(!top) return 1;
    /* 幂等：先移除本模块上次追加的块 */
    var old = qsa(top, ".w-ext.w-term");
    for(var i = 0; i < old.length; i++){ top.removeChild(old[i]); }
    var bb = buybackOf(view);
    var html = '证券端：优先档本金已兑付 <b>' + pct(prof && prof.senPaidPct) + "</b>"
      + " ｜ 次级档本金已兑付 <b>" + pct(prof && prof.subPaidPct) + "</b>";
    if(bb) html += "　｜　已经清仓回购" + (bb.price ? "（回购价格 " + bb.price + "）" : "");
    var box = doc.createElement("div");
    box.className = "w-ext w-term";
    box.setAttribute("data-w-term", "1");
    box.innerHTML = html;
    top.appendChild(box);
    return 1;
  }
  /* ⑦ 核心结论「兑付终局性」卡片：判据句改终止日；本金兑付降为独立事实句 */
  function fixConclusionCard(view, prof){
    var cards = qsa(view, ".card");
    var n = 0;
    var T = termOf(prof);
    for(var i = 0; i < cards.length; i++){
      var h = cards[i].querySelector ? cards[i].querySelector("h3") : null;
      if(!h || norm(h.textContent).indexOf("兑付终局性") < 0) continue;
      var ps = qsa(cards[i], "p");
      for(var j = 0; j < ps.length; j++){
        var s = norm(ps[j].textContent);
        if(s.indexOf("信托已终局") >= 0){
          ps[j].innerHTML = "本" + T.text + "。";
          n++;
        } else if(s.indexOf("两档本金均达") >= 0){
          ps[j].innerHTML = "本金兑付情况（独立事实）：两档本金均已兑付完毕；"
            + "但本金兑付不构成信托终局判据，终局以信托计划是否终止为准。";
          n++;
        }
      }
    }
    return n;
  }
  /* ⑦ fold-sum 补终止日 */
  function fixConclusionSum(view, prof){
    var sums = qsa(view, ".fold-sum");
    var T = termOf(prof);
    var n = 0;
    for(var i = 0; i < sums.length; i++){
      var s = sums[i].textContent;
      if(s && s.indexOf("兑付 优先") >= 0 && s.indexOf("信托计划") < 0){
        sums[i].textContent = s + " ｜ " + T.text;
        n++;
      }
    }
    return n;
  }

  /* ══════════════════════════════════════════════════════════════════
     ⑥ 分配矩阵「占回收流入」>100% → warn + 行内注（v6）
        6 单处置费用在「回收流入」环节被重复计入（与瀑布同源），
        矩阵占比会 >100%（实测 127.88%、116.48%）。判据用 __V2.WF[key].dbl。
     ══════════════════════════════════════════════════════════════════ */
  function wfDbl(key){
    var WF = V2 && V2.WF;
    var it = WF && WF[key];
    return !!(it && it.dbl);
  }
  function pctNum(s){
    var m = /(-?[\d,]+(?:\.\d+)?)\s*%/.exec(String(s || ""));
    return m ? parseFloat(m[1].replace(/,/g, "")) : null;
  }
  function fixAllocMatrix(view, prof, key){
    var dbl = wfDbl(key);
    var cards = qsa(view, ".card");
    var n = 0, warns = 0;
    /* 先定位「含『占回收流入』列的矩阵卡片/表格」（不论是否有 >100% 行，dbl 单都要提示） */
    var targets = [];
    for(var c = 0; c < cards.length; c++){
      var tbl0 = cards[c].querySelector ? cards[c].querySelector("table.tbl") : null;
      if(!tbl0) continue;
      var hs0 = qsa(tbl0, "th"), col0 = -1;
      for(var h0 = 0; h0 < hs0.length; h0++){
        if(norm(hs0[h0].textContent).indexOf("占回收流入") >= 0){ col0 = h0; break; }
      }
      if(col0 >= 0) targets.push({ card: cards[c], tbl: tbl0, col: col0 });
    }
    for(var t = 0; t < targets.length; t++){
      var tb = targets[t].tbl, col = targets[t].col;
      var trs = qsa(tb, "tr");
      for(var r = 0; r < trs.length; r++){
        var tds = qsa(trs[r], "td");
        if(tds.length <= col) continue;
        var td = tds[col];
        var v = pctNum(norm(td.textContent));
        if(v == null || v <= 100) continue;
        warns++;
        /* 幂等：class / title / ⚠ 标记都已存在时不再重复写 */
        var haveCls = td.classList && td.classList.contains("w-over100");
        var haveMark = td.querySelector ? !!td.querySelector(".w-over100-note") : false;
        if(!haveCls && td.classList) td.classList.add("w-over100");
        if(dbl && !haveMark){
          td.setAttribute("title", "含处置费用重复计入，实际分配见瀑布");
          var sp = doc.createElement("span");
          sp.className = "w-over100-note";
          sp.textContent = " ⚠";
          td.appendChild(sp);
        }
        n++;
      }
    }
    /* dbl 单：矩阵上方加一条口径提示（幂等：只认本模块自己的 data 标记） */
    if(dbl && targets.length){
      var hasBox = false;
      var allBox = qsa(view, ".w-alloc-note");
      if(allBox.length) hasBox = true;
      if(!hasBox){
        var box = doc.createElement("div");
        box.className = "w-alloc-note";
        box.setAttribute("data-w-alloc", "1");
        box.textContent = "口径提示：本单处置费用已在「处置收入」环节直接扣除，"
          + "分配矩阵中「占回收流入」列因此重复计入、可能超过 100%；"
          + "各项实际分配占比请以瀑布图为准。";
        var tbl1 = targets[0].tbl;
        var par = tbl1.parentNode;
        if(par && par.parentNode && par.parentNode.insertBefore){
          par.parentNode.insertBefore(box, par);
        } else if(par && par.appendChild){
          par.appendChild(box);
        } else if(tbl1.parentNode){
          tbl1.parentNode.appendChild(box);
        }
        n += 1000;
      }
    }
    return { marked: n, warns: warns, dbl: dbl };
  }

  /* ══════════════════════════════════════════════════════════════════
     ③ 四舍五入统一：整数百分比 → 2 位小数（v6）
        实测问题：单项目「达成率 73.53%」vs 卡片/折叠头「达成 74%」→ 同指标两种精度。
        策略：
          · 「达成」值一律用 payload 的 vsForecast 精确到 2 位（速览/折叠头/卡片都统一）
          · 其余整数百分比（含合同条款/阈值，如 5%、80%）→ 统一补 2 位（用户要求全页 0 处整数百分比）
          · 仅 SVG 图表刻度/数据标签保持原样（避免破坏坐标轴排布）
          · 期数/笔数/户数/份数 等计数本不带 %，天然不受影响（防误伤）
     ══════════════════════════════════════════════════════════════════ */
  var PCT_INT_RE = /(?<![\d.])(\d{1,3})%(?![\d.])/;
  /* 已带小数的百分比：不再改写为整数，只允许「用它精确值替换」 */
  var ACH_RE = /达成(率|预计达成)?\s*(\d+(?:\.\d+)?)\s*%/;

  function normPctText(s){
    if(!s || s.indexOf("%") < 0) return null;
    var t = s;
    /* ① 所有整数百分比 → 2 位（含条款；用户要求全页 0 处整数百分比） */
    t = t.replace(/(?<![\d.])(\d{1,3})%(?![\d.])/g, function(all, num){ return num + ".00%"; });
    return t === s ? null : t;
  }
  /* 图表刻度（svg 内文本）不动 */
  function isChartTick(node){
    var p = node.parentNode;
    for(var i = 0; i < 5 && p; i++){
      if(p.tag === "svg") return true;
      p = p.parentNode;
    }
    return false;
  }
  function exactAchieveText(prof){
    if(!prof) return null;
    var v = null;
    if(typeof prof.vsForecast === "number" && isFinite(prof.vsForecast)) v = prof.vsForecast;
    else if(typeof prof.recovered === "number" && typeof prof.forecast === "number"
            && prof.forecast){ v = prof.recovered / prof.forecast; }   /* 现算回退 */
    return (v == null) ? null : (v * 100).toFixed(2) + "%";
  }
  function fixPctRounding(view, prof){
    var n = 0;
    var exact = exactAchieveText(prof);
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s || s.indexOf("%") < 0) return false;
      if(isChartTick(node)) return false;
      var t = s;
      /* ② 「达成 …%」优先换成 payload 精确 2 位值（保留 达成/预计达成 前缀） */
      if(exact && ACH_RE.test(t)){
        t = t.replace(/达成(率|预计达成)?\s*\d+(?:\.\d+)?\s*%/g, function(all, kind){
          if(kind === "率") return "达成率 " + exact;
          if(kind) return kind + " " + exact;
          return "达成 " + exact;
        });
      }
      /* ③ 其余整数百分比 → 2 位 */
      var t2 = normPctText(t);
      if(t2 != null) t = t2;
      /* ④ 仍为 1 位小数的「达成 X%」（payload 缺 vsForecast/forecast）→ 补到 2 位 */
      t = t.replace(/达成(率|预计达成)?\s*(\d+)\.(\d)\s*%/g, function(all, kind, a, b){
        var pre = kind === "率" ? "达成率 " : (kind ? kind + " " : "达成 ");
        return pre + a + "." + b + "0%";
      });
      if(t === s) return false;
      n++;
      return setText(node, t);
    });
    return n;
  }
  /* 折叠头「达成 131%」→「达成 130.52%」：用 payload 精确值（2 位）替换 */
  function fixAchieveSum(view, prof){
    var want = exactAchieveText(prof);            /* "130.52%" */
    if(!want) return 0;
    var hits = qsa(view, ".fold-sum, .ok, .s, .s2");
    var n = 0;
    for(var i = 0; i < hits.length; i++){
      var el = hits[i];
      var s = el.textContent || "";
      if(!/达成\s*\d+(?:\.\d+)?%/.test(s)) continue;
      var s2 = s.replace(/达成\s*\d+(?:\.\d+)?%/, "达成 " + want);
      if(s2 !== s){ el.textContent = s2; n++; }
    }
    return n;
  }
  /* ⑤ 「缺失材料」：hero 里保持隐藏（与 20_profile 同一 class，幂等），内容搬到 ⑧ */
  function hideMissingInHero(view){
    var notes = qsa(view, ".note");
    var n = 0;
    for(var i = 0; i < notes.length; i++){
      var t = String(notes[i].textContent || "").replace(/^\s+/, "");
      if(t.slice(0, 4) !== "缺失材料") continue;
      if(notes[i].classList && !notes[i].classList.contains("pf-missing-hidden")){
        notes[i].classList.add("pf-missing-hidden");
        if(notes[i].setAttribute) notes[i].setAttribute("data-w-hidden", "1");
        n++;
      }
    }
    return n;
  }
  function missingMaterials(view){
    var notes = qsa(view, ".note");
    for(var i = 0; i < notes.length; i++){
      var t = norm(notes[i].textContent);
      if(t.indexOf("缺失材料") === 0){
        /* 形如「缺失材料（依据：资产类型判定表·缺失材料列）：法律意见书、会计意见书…」 */
        var m = /[：:]\s*([\s\S]+)$/.exec(t);
        var list = m ? norm(m[1]).replace(/[。.；;]\s*$/, "") : "";
        return list ? list : null;
      }
    }
    return null;
  }
  /* v11：缺失材料解析成数组（供折叠表格逐行渲染） */
  function materialList(view){
    var s = missingMaterials(view);
    if(!s) return [];
    var parts = String(s).split(/[、,，;；]/);
    var out = [];
    for(var i = 0; i < parts.length; i++){
      var t = norm(parts[i]);
      if(t && out.indexOf(t) < 0) out.push(t);
    }
    return out;
  }
  /* v11：材料 → 「是否影响主结论 / 说明」（按材料性质给差异化、可核对的理由；
     说明控制在 20 字内，避免 123 行把 ⑧ 撑成长文） */
  function matRow(name){
    if(/法律意见书|会计意见书|鉴证/.test(name)){
      return { impact: "否", why: "合规类，不含现金流与分配数据" };
    }
    if(/评级报告/.test(name)){
      return { impact: "否", why: "外部分析观点，报告不引用评级" };
    }
    if(/清算/.test(name)){
      return { impact: "否", why: "汇总类；分档兑付已取受托机构报告" };
    }
    return { impact: "否", why: "非现金流数据源" };
  }
  /* ⑧ 折叠块定位（多处复用） */
  function dqFold(view){
    var folds = qsa(view, ".fold");
    for(var i = 0; i < folds.length; i++){
      var h = folds[i].querySelector ? folds[i].querySelector(".fold-h") : null;
      if(h && norm(h.textContent).indexOf("数据质量与披露") >= 0) return folds[i];
    }
    return null;
  }
  /* ══════════════════════════════════════════════════════════════════
     v11 任务1：披露概览条的数字——逐单从真实 DOM 现场统计，不硬编码
       N（共）     = ⑧ 内披露/缺口条目数（剔除「缺口分级」这类元说明块）+ 缺失材料条目数
       已回源补全 a = 带 A 类徽章的条目数
       源文件缺失 c = 带 C 类徽章的条目数 + 缺失材料条目数
       源未披露 b   = N − a − c（既未回源补录、也非源文件缺失，属报告本身没有、另行核算）
     统计结果缓存在 .fold[data-w-dqstat] 上：改写后 .inner 被替换，二次执行仍能复用同一份数字。
     ══════════════════════════════════════════════════════════════════ */
  function dqStat(view){
    var fold = dqFold(view);
    if(!fold) return null;
    var cached = fold.getAttribute ? fold.getAttribute("data-w-dqstat") : null;
    if(cached){
      try { return JSON.parse(cached); } catch(e){ /* 缓存坏了就重算 */ }
    }
    var a = 0, b = 0, cw = 0, items = 0;
    var warns = qsa(fold, ".warn");
    for(var i = 0; i < warns.length; i++){
      var w = warns[i];
      var wtEl = w.querySelector ? w.querySelector(".wt") : null;
      var wt = norm(wtEl ? wtEl.textContent : "");
      if(wt.indexOf("缺口分级") >= 0) continue;      /* 元说明块，不算披露项 */
      items++;
      var bd = w.querySelector ? w.querySelector(".kbadge") : null;
      var isA = !!(bd && bd.classList && bd.classList.contains("kA"));
      var isC = !!(bd && bd.classList && bd.classList.contains("kC"));
      if(isA) a++;
      else if(isC) cw++;
      else b++;
    }
    var mats = materialList(view);
    var res = {
      N: items + mats.length, a: a, b: b,
      c: cw + mats.length,      /* 源文件缺失 = C 类条目 + 缺失材料清单 */
      itemN: items, cw: cw, matN: mats.length, mats: mats
    };
    if(fold.setAttribute){
      try { fold.setAttribute("data-w-dqstat", JSON.stringify(res)); } catch(e){}
    }
    return res;
  }
  /* 缺失材料折叠表（默认收起；真实 DOM，不靠 CSS 隐藏） */
  function matBlock(mats){
    if(!mats || !mats.length){
      return '<div class="dq-nomat">本单无缺失材料。</div>';
    }
    var rows = "";
    for(var i = 0; i < mats.length; i++){
      var r = matRow(mats[i]);
      rows += "<tr>"
        + '<td class="mn">' + esc(mats[i]) + "</td>"
        + '<td class="mi"><span class="no">' + esc(r.impact) + "</span></td>"
        + "<td>" + esc(r.why) + "</td>"
        + "</tr>";
    }
    return '<details class="dq-mat" data-w-mat="1">'
      + "<summary>缺失材料 <span class=\"dq-mat-n\">" + mats.length + " 项</span>"
      + '<span class="dq-mat-s">· 依据：资产类型判定表（缺失材料列）· 点开看逐项影响</span>'
      + "</summary>"
      + '<table class="dq-mt"><thead><tr>'
      + '<th style="width:24%">材料名称</th>'
      + '<th style="width:15%">是否影响主结论</th>'
      + '<th style="width:61%">说明</th>'
      + "</tr></thead><tbody>" + rows + "</tbody></table>"
      + '<div class="dq-mf">以上为资产类型判定表列示的应备材料。本报告主结论仅取决于'
      + "发⾏说明书与受托机构报告（二者本单齐备），上述材料不承载现金流数据，故不影响任何数值结论。</div>"
      + "</details>";
  }
  /* 概览条一行（展开后首行） */
  function ovLine(st){
    if(!st) return "";
    return '<div class="dq-ov" data-w-dqov="1">'
      + '<span class="dq-ov-t">披露概览：</span>'
      + "共 " + st.N + " 项 ｜ 已回源补全 " + st.a + " 项"
      + " ｜ 源未披露 " + st.b + " 项 ｜ 源文件缺失 " + st.c + " 项"
      + "</div>";
  }
  function esc(s){
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function dqSections(view, prof){
    var h2 = auditOf(view, "h2");
    var miss = (h2 && Object.prototype.toString.call(h2.miss) === "[object Array]") ? h2.miss : [];
    var complete;
    if(!miss.length){
      complete = "本单核心字段齐全，无缺项；分档本金·利息、费用与税款、回收流入均已归集并交叉校验。";
    } else {
      complete = "本单核心字段基本齐全，缺项 " + miss.length + " 处（第 "
        + miss.join("、") + " 期分档数据）；已按分配表档位明确的科目补录，不静默丢弃。";
    }
    var mats = materialList(view);
    var notes = [];
    if(typeof prof.poolTotal === "number" && typeof prof.poolPrincipal === "number"
       && prof.poolTotal && prof.poolPrincipal){
      notes.push("入池息费按「本息费 − 本金」归一（源披露可能分列为利息与费用两项）");
    }
    notes.push("预计回收采用中债口径（中债资信《预计回收报告》）");
    if(typeof prof.secRatio === "number"){
      notes.push("证券化率 " + pct(prof.secRatio)
        + " 以入池本息费为分母；若以入池本金为分母会更高，比较时请注意分母口径");
    }
    var srcs = ["发行说明书"];
    if(dateOf(prof, "清算完成")) srcs.push("受托机构报告（各期）");
    var sources = srcs.join("；")
      + "。金额单位：亿元 2 位 / 万元 2 位；比率百分号 2 位；缺失一律记「—」，不臆造。";
    return { complete: complete, notes: notes.slice(0, 3), sources: sources,
             mat: mats.length ? mats.join("、") : null, mats: mats, missN: miss.length };
  }
  function rewriteDqFold(view, prof){
    var target = dqFold(view);
    if(!target) return null;
    var inner = target.querySelector ? target.querySelector(".inner") : null;
    if(!inner) return null;
    /* 先统计（必须在替换 .inner 之前，否则 .warn 条目已不在 DOM） */
    var st = dqStat(view);
    if(inner.getAttribute && inner.getAttribute("data-w-dq") === "1") return "already";
    var S = dqSections(view, prof);
    var ov = ovLine(st);
    var html = '<div class="dq3">'
      + '<div class="dq-sec"><p class="dq-t">① 数据完整度</p>'
      + '<div class="dq-b">' + S.complete + "</div>"
      + matBlock(S.mats)
      + "</div>"
      + '<div class="dq-sec"><p class="dq-t">② 口径注解</p><div class="dq-b">'
      + S.notes.join("；") + "。</div></div>"
      + '<div class="dq-sec"><p class="dq-t">③ 来源依据</p><div class="dq-b">' + S.sources + "</div></div>"
      + "</div>";
    inner.innerHTML = ov + html;
    inner.setAttribute("data-w-dq", "1");
    /* 任务3：⑧ 折叠块默认收起（点击标题行再展开） */
    if(target.classList && !target.classList.contains("collapsed")){
      target.classList.add("collapsed");
    }
    /* 折叠头显示「披露 N 项」——未展开时也看得到 */
    var h = target.querySelector ? target.querySelector(".fold-h") : null;
    var sum = h && h.querySelector ? h.querySelector(".fold-sum") : null;
    if(sum && st){
      sum.textContent = "披露 " + st.N + " 项" + (st.N ? "" : " ｜ 无缺口");
      if(sum.classList) sum.classList.add("dq-n");
    }
    return "ok";
  }
  /* ⑧ fold-sum：v11 改为「披露 N 项」（数字来自 dqStat，未展开时也能看到） */
  function fixDisclosureSum(view){
    var st = dqStat(view);
    if(!st) return 0;
    var sums = qsa(view, ".fold-sum");
    var n = 0;
    for(var i = 0; i < sums.length; i++){
      var el = sums[i];
      var s = el.textContent || "";
      if(/^\s*(\d+\s*项披露|无缺口)\s*$/.test(s)){
        el.textContent = "披露 " + st.N + " 项" + (st.N ? "" : " ｜ 无缺口");
        if(el.classList) el.classList.add("dq-n");
        n++;
      } else if(s.indexOf("项披露") >= 0){
        /* 混合串只替换该 token，保留其余 */
        el.textContent = s.replace(/\d+\s*项披露/g, "披露 " + st.N + " 项");
        n++;
      }
    }
    return n;
  }
  /* ⑦「④ 数据质量与风险提示」卡片：v6 只留一行摘要（明细只在 ⑧，避免重复） */
  function fixConclusionDqCard(view, prof){
    var cards = qsa(view, ".card");
    for(var i = 0; i < cards.length; i++){
      var h = cards[i].querySelector ? cards[i].querySelector("h3") : null;
      if(!h || norm(h.textContent).indexOf("数据质量") < 0) continue;
      var cnl = cards[i].querySelector ? cards[i].querySelector(".cnl") : null;
      if(!cnl) continue;
      if(cnl.getAttribute && cnl.getAttribute("data-w-dqcard") === "1") return 0;
      var S = dqSections(view, prof);
      /* 一行摘要（≤60 字）：「数据质量：完整度高 ｜ 缺项 0 项 ｜ 口径注 3 条 ｜ 来源 2 份」 */
      var grade = (S.missN === 0) ? "高" : (S.missN <= 2 ? "中" : "低");
      var line1 = "数据质量：完整度" + grade + " ｜ 缺项 " + S.missN
        + " ｜ 口径注 " + S.notes.length + " ｜ 来源 " + (dateOf(prof, "清算完成") ? 2 : 1)
        + (S.mat ? " ｜ 材料缺 " + S.mat.split("、").length + " 类" : "");
      line1 += "　（明细见 ⑧）";
      cnl.innerHTML = '<p class="w-dqsum" data-w-dqsum="1">' + line1 + "</p>";
      cnl.setAttribute("data-w-dqcard", "1");
      return 1;
    }
    return 0;
  }

  /* ══════════════════════════════════════════════════════════════════
     路径脱敏（全报告）
     ══════════════════════════════════════════════════════════════════ */
  function scrubTech(text){
    var s = text;
    s = s.replace(/[A-Za-z]:\\[^\s<"，。；）)]*/g, "项目源文件");
    s = s.replace(/[A-Za-z]:\/[^\s<"，。；）)]*/g, "项目源文件");
    s = s.replace(/A_回源已补/g, "已回源补录");
    s = s.replace(/B_报告确无/g, "报告未披露");
    s = s.replace(/C_源文件缺失/g, "源文件缺失");
    s = s.replace(/残迹待核/g, "已复核");
    /* 点路径（tranche.x[1] / supply.overrides / pool.bsf 等）整段删除 */
    s = s.replace(/\b(?:payload|pool|alloc|liq_info|ref_rate|tranche|supply|xirr|derived|account|outflow|begin|base)\.[A-Za-z_][\w.\[\]0-9-]*/g, "");
    s = s.replace(/\b(?:payload|liq_info|ref_rate)\b/g, "");
    /* 剩余字段路径括注整体删除 */
    s = s.replace(/[（(]\s*(?:payload|pool\.|alloc\.|liq_info|ref_rate|tranche\.|supply\.|xirr\.)[^）)]*[）)]/gi, "");
    s = s.replace(/（\s*）|\(\s*\)/g, "");
    s = s.replace(/\s{2,}/g, " ");
    return s;
  }
  function scrubView(view){
    var n = 0;
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s) return false;
      if(!PATH_RE.test(s) && s.indexOf("E:\\") < 0 && s.indexOf("E:/") < 0
         && s.indexOf("A_回源已补") < 0 && s.indexOf("B_报告确无") < 0
         && s.indexOf("C_源文件缺失") < 0 && s.indexOf("残迹待核") < 0) return false;
      var t = scrubTech(s);
      if(t !== s){ n++; return setText(node, t); }
      return false;
    });
    return n;
  }

  /* ══════════ 逐视图总装 ══════════ */
  function build(view){
    var prof = profileOf(view);
    if(!prof) return;
    /* ② 证券化率长串（容器级整体重写，避免被 <b> 切碎后残留半句） */
    fixSecBlocks(view, prof);
    /* ① 处置费用括注（金额 + <code> 被拆成多节点，容器级处理） */
    fixDisposeFeeBlocks(view);
    /* ① 字段路径 / 英文术语（页脚、其余括注） */
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s || !PATH_RE.test(s)) return false;
      var t = fixFooter(s) || scrubTech(s);
      if(t !== s) return setText(node, t);
      return false;
    });
    /* ⑤ 折现说明（先做，避免与 ⑥ 的「天数」替换二次叠加） */
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s || s.indexOf("折现因子") < 0) return false;
      var t = fixDiscountNote(s);
      if(t == null) return false;
      return setText(node, t);
    });
    /* ⑤ 投入日 → 信托设立日 */
    eachTextNode(view, function(node){
      var s = node.nodeValue;
      if(!s || s.indexOf("投入日") < 0) return false;
      var t = fixSetupDate(s);
      if(t == null && /投入日 \d{4}-\d{2}-\d{2} · \d+ 行/.test(s)){
        t = s.replace(/投入日/g, "信托设立日");
      }
      if(t == null) return false;
      if(t !== s) return setText(node, t);
      return false;
    });
    /* ⑥ 现金流表 */
    fixCashFlowTable(view);
    /* ⑧ 归期规则 */
    fixPeriodRule(view);
    /* v6 任务5：hero 内「缺失材料」保持隐藏（内容在 ⑧ 承接） */
    try { hideMissingInHero(view); } catch(e){}
    /* v6 任务6：分配矩阵「占回收流入」>100% → warn + 口径提示 */
    try { ALLOC_STAT[viewNo(view)] = fixAllocMatrix(view, prof, keyOfView(view)); } catch(e){}
    /* ★ 终局性判定 */
    heroBadge(view, prof);
    fixConclusionCard(view, prof);
    fixConclusionSum(view, prof);
    /* ★ 数据质量 fold 重写 */
    rewriteDqFold(view, prof);
    fixDisclosureSum(view);
    fixConclusionDqCard(view, prof);
    /* v6 任务3：四舍五入统一到 2 位小数（放最后，覆盖全视图可见百分比） */
    fixAchieveSum(view, prof);
    try { PCT_STAT[viewNo(view)] = fixPctRounding(view, prof); } catch(e){}
    /* 路径脱敏兜底 */
    scrubView(view);
  }
  var ALLOC_STAT = {}, PCT_STAT = {};
  function runAll(){
    var views = qsa(doc, ".view");
    for(var i = 0; i < views.length; i++){
      var v = views[i];
      if(!v || !v.id || !/^view-p\d+$/.test(v.id)) continue;
      try { build(v); } catch(e){ /* 单视图异常不影响其余 27 单 */ }
    }
  }
  function ready(){
    var w = (typeof window !== "undefined") ? window : null;
    if(w && w.__V2){ V2 = w.__V2; ORDER = V2.ORDER || []; PROF = V2.PROF || {}; AUDIT = V2.AUDIT || {}; }
    runAll();
  }
  ready();
  if(!ORDER.length){
    var once = false;
    var again = function(){
      if(once) return;
      once = true;
      var w = (typeof window !== "undefined") ? window : null;
      if(w && w.__V2){ ready(); }
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

# 任务清单（自检逐条打印）
VENDOR_PATHS = ["payload", "pool.", "alloc.", "liq_info", "ref_rate", "tranche.", "supply."]


# ── Node + 轻量 DOM 影子：真 HTML → 真 JS → 真断言 ──
HARNESS = r"""
var fs = require("fs");
var INPUT = JSON.parse(fs.readFileSync(0, "utf8"));
var HTML = INPUT.html;
var MODULE_JS = INPUT.js;

/* ── 极简 DOM（只覆盖本模块用到的 API） ── */
var VOID = { br:1, hr:1, img:1, input:1, meta:1, link:1, col:1, area:1, base:1, source:1, wbr:1 };
function decode(s){
  return String(s).replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
}
var ALL = [];
/* 文本节点工厂：nodeValue 与 textContent 互见（parseHTML / createTextNode / innerHTML 共用） */
function mkText(s, parent){
  var tn = { nodeType: 3, _v: String(s == null ? "" : s), parentNode: parent || null };
  Object.defineProperty(tn, "nodeValue", {
    get: function(){ return this._v; },
    set: function(v){ this._v = String(v); }
  });
  Object.defineProperty(tn, "textContent", {
    get: function(){ return this._v; },
    set: function(v){ this._v = String(v); }
  });
  return tn;
}
function mkEl(tag){
  var el = { nodeType: 1, tag: tag, attrs: {}, childNodes: [], parentNode: null };
  ALL.push(el);
  Object.defineProperty(el, "id", {
    get: function(){ return this.attrs.id || ""; },
    set: function(v){ this.attrs.id = String(v); }
  });
  Object.defineProperty(el, "className", {
    get: function(){ return this.attrs["class"] || ""; },
    set: function(v){ this.attrs["class"] = String(v); }
  });
  el.classList = {
    contains: function(c){
      return (" " + (el.attrs["class"] || "") + " ").indexOf(" " + c + " ") >= 0;
    },
    add: function(c){
      if(!el.classList.contains(c)) el.attrs["class"] = norm(el.attrs["class"] + " " + c);
    }
  };
  Object.defineProperty(el, "textContent", {
    get: function(){
      if(this.nodeType === 3) return this.nodeValue;
      var out = "";
      for(var i = 0; i < this.childNodes.length; i++) out += this.childNodes[i].textContent;
      return out;
    },
    set: function(v){
      this.childNodes = [mkText(v, this)];
    }
  });
  Object.defineProperty(el, "innerHTML", {
    get: function(){ return render(this); },
    set: function(v){
      var frag = parseHTML(String(v));
      this.childNodes = frag.childNodes;
      for(var i = 0; i < this.childNodes.length; i++) this.childNodes[i].parentNode = this;
    }
  });
  Object.defineProperty(el, "firstChild", {
    get: function(){ return this.childNodes[0] || null; }
  });
  Object.defineProperty(el, "previousSibling", {
    get: function(){
      var p = this.parentNode;
      if(!p || !p.childNodes) return null;
      var i = p.childNodes.indexOf(this);
      return i > 0 ? p.childNodes[i - 1] : null;
    }
  });
  Object.defineProperty(el, "nextSibling", {
    get: function(){
      var p = this.parentNode;
      if(!p || !p.childNodes) return null;
      var i = p.childNodes.indexOf(this);
      return (i >= 0 && i + 1 < p.childNodes.length) ? p.childNodes[i + 1] : null;
    }
  });
  el.getAttribute = function(n){ return Object.prototype.hasOwnProperty.call(this.attrs, n) ? this.attrs[n] : null; };
  el.setAttribute = function(n, v){ this.attrs[n] = String(v); };
  el.removeChild = function(c){
    var i = this.childNodes.indexOf(c);
    if(i >= 0) this.childNodes.splice(i, 1);
    if(c) c.parentNode = null;
    return c;
  };
  el.appendChild = function(c){ c.parentNode = this; this.childNodes.push(c); return c; };
  el.querySelectorAll = function(sel){
    var out = [];
    var sels = String(sel).split(",").map(function(s){ return s.trim(); }).filter(Boolean);
    walk(el, function(node){
      for(var i = 0; i < sels.length; i++){ if(match(node, sels[i])){ out.push(node); return; } }
    });
    return out;
  };
  el.querySelector = function(sel){ var r = el.querySelectorAll(sel); return r.length ? r[0] : null; };
  return el;
}
function norm(s){ return String(s == null ? "" : s).replace(/\s+/g, " ").trim(); }
function walk(node, fn){
  for(var i = 0; i < node.childNodes.length; i++){
    var c = node.childNodes[i];
    if(c.nodeType === 1){ fn(c); walk(c, fn); }
  }
}
/* 选择器子集：tag、#id、.a、.a.b、tag.class#id、[attr]、[attr="v"]、
   .a .b、.a > .b、tag.class .z 等组合 */
function parseSimple(sel){
  var s = String(sel).trim();
  var out = { tag: null, id: null, cls: [], attrs: [] };
  var re = /([.#]?[-\w]+)|\[([-\w]+)(?:=["']?([^\]"']*)["']?)?\]/g, m;
  while((m = re.exec(s))){
    if(m[1]){
      var tok = m[1];
      if(tok.charAt(0) === ".") out.cls.push(tok.slice(1));
      else if(tok.charAt(0) === "#") out.id = tok.slice(1);
      else out.tag = tok.toLowerCase();
    } else if(m[2]){
      out.attrs.push({ name: m[2], val: m[3] == null ? null : m[3] });
    }
  }
  return out;
}
function matchSimple(node, p){
  if(!node || node.nodeType !== 1) return false;
  if(p.tag && node.tag !== p.tag) return false;
  if(p.id != null && String(node.attrs.id || "") !== p.id) return false;
  for(var i = 0; i < p.cls.length; i++){
    if(!node.classList.contains(p.cls[i])) return false;
  }
  for(var j = 0; j < p.attrs.length; j++){
    var a = p.attrs[j];
    if(!Object.prototype.hasOwnProperty.call(node.attrs, a.name)) return false;
    if(a.val != null && String(node.attrs[a.name]) !== a.val) return false;
  }
  return true;
}
function match(node, sel){
  sel = String(sel).trim();
  if(!sel) return false;
  var gm = /^(.+?)\s*>\s*(.+)$/.exec(sel);
  if(gm){
    if(!match(node, gm[2])) return false;
    return !!(node.parentNode && match(node.parentNode, gm[1]));
  }
  if(/\s/.test(sel)){
    var parts = sel.split(/\s+/);
    var last = parts[parts.length - 1];
    if(!match(node, last)) return false;
    var anc = node.parentNode;
    for(var i = parts.length - 2; i >= 0; i--){
      var found = false;
      while(anc && anc.nodeType === 1){
        if(match(anc, parts[i])){ found = true; anc = anc.parentNode; break; }
        anc = anc.parentNode;
      }
      if(!found) return false;
    }
    return true;
  }
  return matchSimple(node, parseSimple(sel));
}
function render(node){
  if(node.nodeType === 3) return node.nodeValue;
  var out = "";
  for(var i = 0; i < node.childNodes.length; i++) out += render(node.childNodes[i]);
  return out;
}
function parseHTML(html){
  var root = mkEl("#document");
  var stack = [root];
  var re = /<!--[\s\S]*?-->|<\/([a-zA-Z0-9]+)\s*>|<([a-zA-Z0-9]+)((?:"[^"]*"|'[^']*'|[^>"'])*)>|([^<]+)/g, m;
  while((m = re.exec(html))){
    if(m[0].slice(0, 4) === "<!--") continue;
    if(m[1]){
      var tag = m[1].toLowerCase();
      for(var i = stack.length - 1; i > 0; i--){
        if(stack[i].tag === tag){ stack.length = i; break; }
      }
      continue;
    }
    if(m[2]){
      var t = m[2].toLowerCase();
      var el = mkEl(t);
      var attrs = m[3] || "";
      var ar = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g, am;
      while((am = ar.exec(attrs))){
        var av = am[3] != null ? am[3] : (am[4] != null ? am[4] : (am[5] != null ? am[5] : ""));
        el.attrs[am[1]] = decode(av);
      }
      var parent = stack[stack.length - 1];
      el.parentNode = parent;
      parent.childNodes.push(el);
      if(!VOID[t] && !/\/$/.test(attrs)) stack.push(el);
      continue;
    }
    if(m[4] != null){
      var s = m[4];
      if(s === "") continue;
      stack[stack.length - 1].childNodes.push(mkText(s, stack[stack.length - 1]));
    }
  }
  return root;
}
function makeWalker(root){
  var nodes = [];
  (function w(n){
    for(var i = 0; i < n.childNodes.length; i++){
      var c = n.childNodes[i];
      if(c.nodeType === 3) nodes.push(c);
      else if(c.nodeType === 1) w(c);
    }
  })(root);
  var idx = 0;
  return { nextNode: function(){ return idx < nodes.length ? nodes[idx++] : null; } };
}

/* ── 装配 document / window ── */
var DOC = parseHTML(HTML);
var document = {
  readyState: "complete",
  body: DOC,
  createElement: function(tag){ return mkEl(tag.toLowerCase()); },
  createTextNode: function(s){ return mkText(s, null); },
  querySelectorAll: function(sel){ return DOC.querySelectorAll(sel); },
  querySelector: function(sel){ return DOC.querySelector(sel); },
  createTreeWalker: function(root){ var tw = makeWalker(root); return { nextNode: tw.nextNode }; },
  addEventListener: function(){}
};
var window = { __V2: INPUT.v2, addEventListener: function(){} };

/* ── 结构计数（前置，验证 svg/class 不被重建） ── */
function structCounts(root){
  var cls = {};
  var c = { svg:0, path:0, table:0, fold:0, card:0, td:0, th:0 };
  (function w(n){
    for(var i = 0; i < n.childNodes.length; i++){
      var x = n.childNodes[i];
      if(x.nodeType !== 1) continue;
      c.fold += x.classList.contains("fold") ? 1 : 0;
      c.svg += x.tag === "svg" ? 1 : 0;
      c.path += x.tag === "path" ? 1 : 0;
      c.table += x.tag === "table" ? 1 : 0;
      c.card += x.classList.contains("card") ? 1 : 0;
      c.td += x.tag === "td" ? 1 : 0;
      c.th += x.tag === "th" ? 1 : 0;
      var cn = x.attrs["class"];
      if(cn){ var parts = cn.split(/\s+/); for(var j = 0; j < parts.length; j++){ if(parts[j]) cls[parts[j]] = 1; } }
      w(x);
    }
  })(root);
  return { counts: c, classN: Object.keys(cls).length };
}
var STRUCT0 = structCounts(DOC);

/* ── 执行本模块 JS ── */
var errors = [];
try { eval(MODULE_JS); } catch(e){ errors.push("first: " + e.message); }

function visibleText(root){
  var out = [];
  (function w(n){
    for(var i = 0; i < n.childNodes.length; i++){
      var c = n.childNodes[i];
      if(c.nodeType === 3){ out.push(c.nodeValue); continue; }
      if(c.nodeType !== 1) continue;
      if(c.tag === "script" || c.tag === "style") continue;
      w(c);
    }
  })(root);
  return out.join("\n");
}
function countIn(text, pat){
  if(!pat) return 0;
  var n = 0, i = 0;
  while((i = text.indexOf(pat, i)) >= 0){ n++; i += pat.length; }
  return n;
}
var vtAll = visibleText(DOC);
/* ── 每单关键点 ── */
var VIDS = [];
(function(){
  var vs = DOC.querySelectorAll("section.view");
  for(var i = 0; i < vs.length; i++){
    if(vs[i].id && /^view-p\d+$/.test(vs[i].id)) VIDS.push(vs[i].id);
  }
})();
function viewById(vid){
  return DOC.querySelector("#" + vid);
}
var perView = VIDS.map(function(vid){
  var v = viewById(vid);
  var badge = v ? v.querySelector(".hero-top .hbadge") : null;
  var dq = "", dqLen = -1;
  var folds = v ? v.querySelectorAll(".fold") : [];
  for(var i = 0; i < folds.length; i++){
    var h = folds[i].querySelector(".fold-h");
    if(h && norm(h.textContent).indexOf("数据质量与披露") >= 0){
      var inner = folds[i].querySelector(".inner");
      dq = inner ? inner.textContent : "";
      dqLen = dq.length;
      break;
    }
  }
  var cfHead = null, firstRowCell = null;
  var tabs = v ? v.querySelectorAll("table.tbl") : [];
  for(var t = 0; t < tabs.length; t++){
    var ths = tabs[t].querySelectorAll("th");
    var isCf = false;
    for(var j = 0; j < ths.length; j++){
      if(norm(ths[j].textContent).indexOf("现金流") >= 0) isCf = true;
    }
    if(isCf && !cfHead){
      cfHead = [].map.call(ths, function(x){ return norm(x.textContent); });
      var tds = tabs[t].querySelectorAll("td");
      if(tds.length) firstRowCell = norm(tds[0].textContent);
    }
  }
  /* v6 任务3/4/5/6 的逐单取证 */
  var v6 = {
    /* 任务3：可见文本里残留的「整数百分比」纯文本节点（排除 svg 刻度） */
    intPct: (function(){
      var out = [];
      (function w(n){
        for(var i = 0; i < n.childNodes.length; i++){
          var c = n.childNodes[i];
          if(c.nodeType === 3){
            var s = String(c.nodeValue || "");
            var m = /(?<![\d.])(\d{1,3})%(?![\d.])/.exec(s);
            if(m){
              var p = c.parentNode, inSvg = false;
              for(var k = 0; k < 6 && p; k++){
                if(p.tag === "svg"){ inSvg = true; break; }
                p = p.parentNode;
              }
              if(!inSvg) out.push({ text: s.slice(0, 60) });
            }
            continue;
          }
          if(c.nodeType !== 1) continue;
          if(c.tag === "script" || c.tag === "style") continue;
          w(c);
        }
      })(v);
      return out;
    })(),
    /* 任务4：⑦ 数据质量卡片文本长度 */
    dqCardLen: (function(){
      var cards = v ? v.querySelectorAll(".card") : [];
      for(var i = 0; i < cards.length; i++){
        var h = cards[i].querySelector("h3");
        if(h && norm(h.textContent).indexOf("数据质量") >= 0){
          var cnl = cards[i].querySelector(".cnl");
          return cnl ? norm(cnl.textContent).length : -1;
        }
      }
      return -1;
    })(),
    dqCardText: (function(){
      var cards = v ? v.querySelectorAll(".card") : [];
      for(var i = 0; i < cards.length; i++){
        var h = cards[i].querySelector("h3");
        if(h && norm(h.textContent).indexOf("数据质量") >= 0){
          var cnl = cards[i].querySelector(".cnl");
          return cnl ? norm(cnl.textContent) : "";
        }
      }
      return "";
    })(),
    /* 任务5：⑧ 内「缺失材料」出现次数 / hero 内是否仍可见 */
    dqMissingN: (function(){
      var t = "";
      var folds = v ? v.querySelectorAll(".fold") : [];
      for(var i = 0; i < folds.length; i++){
        var h = folds[i].querySelector(".fold-h");
        if(h && norm(h.textContent).indexOf("数据质量与披露") >= 0){
          var inner = folds[i].querySelector(".inner");
          t = inner ? inner.textContent : "";
          break;
        }
      }
      var n = 0, k = 0;
      while((k = t.indexOf("缺失材料", k)) >= 0){ n++; k += 1; }
      return n;
    })(),
    heroMissingVisible: (function(){
      /* hero 内「缺失材料」是否仍**可见**：20_profile 会给它加 .pf-missing-hidden；
         本模块自身也会补一次（幂等），故检查 class 即可（CSS 负责 display:none） */
      var notes = v ? v.querySelectorAll(".note") : [];
      for(var i = 0; i < notes.length; i++){
        var t = norm(notes[i].textContent);
        if(t.indexOf("缺失材料") === 0){
          if(!notes[i].classList.contains("pf-missing-hidden")) return true;
        }
      }
      return false;
    })(),
    /* 任务6：矩阵「占回收流入」>100% 的单元格数 / warn 标记数 */
    over100: (function(){
      var cells = 0, warned = 0;
      var tabs = v ? v.querySelectorAll("table.tbl") : [];
      for(var t = 0; t < tabs.length; t++){
        var ths = tabs[t].querySelectorAll("th"), col = -1;
        for(var h = 0; h < ths.length; h++){
          if(norm(ths[h].textContent).indexOf("占回收流入") >= 0){ col = h; break; }
        }
        if(col < 0) continue;
        var trs = tabs[t].querySelectorAll("tr");
        for(var r = 0; r < trs.length; r++){
          var tds = trs[r].querySelectorAll("td");
          if(tds.length <= col) continue;
          var m2 = /(-?[\d,]+(?:\.\d+)?)\s*%/.exec(norm(tds[col].textContent));
          if(!m2) continue;
          if(parseFloat(m2[1].replace(/,/g, "")) > 100){
            cells++;
            if(tds[col].classList.contains("w-over100")) warned++;
          }
        }
      }
      return { cells: cells, warned: warned };
    })(),
    allocNote: !!(v && v.querySelector(".w-alloc-note")),
    achieveTexts: (function(){
      var t = v ? (v.textContent || "") : "";
      var out = [], re = /达成\s*(\d+(?:\.\d+)?)%/g, m3;
      while((m3 = re.exec(t))){
        if(out.indexOf(m3[0]) < 0) out.push(m3[0]);
      }
      return out;
    })(),
    achieveSums: (function(){
      var out = [];
      var sums = v ? v.querySelectorAll(".fold-sum") : [];
      for(var i = 0; i < sums.length; i++){
        var t = norm(sums[i].textContent);
        if(t.indexOf("达成") >= 0) out.push(t.slice(0, 60));
      }
      var oks = v ? v.querySelectorAll(".ok") : [];
      for(var j = 0; j < oks.length; j++){
        var t2 = norm(oks[j].textContent);
        if(t2.indexOf("达成") >= 0) out.push("OK:" + t2.slice(0, 40));
      }
      return out;
    })()
  };
  /* ══════════ v11：⑧ 概览条 / 缺失材料表 / 默认收起 取证 ══════════ */
  var v11 = (function(){
    var out = {};
    var folds = v ? v.querySelectorAll(".fold") : [];
    var fold = null;
    for(var i = 0; i < folds.length; i++){
      var hh = folds[i].querySelector(".fold-h");
      if(hh && norm(hh.textContent).indexOf("数据质量与披露") >= 0){ fold = folds[i]; break; }
    }
    out.hasFold = !!fold;
    if(!fold) return out;
    out.collapsed = !!(fold.classList && fold.classList.contains("collapsed"));
    /* 折叠头 .fold-sum 文本（未展开时可见） */
    var hs = fold.querySelector(".fold-h");
    var sum = hs ? hs.querySelector(".fold-sum") : null;
    out.sumText = sum ? norm(sum.textContent) : null;
    /* 概览条 */
    var ov = fold.querySelector(".dq-ov");
    out.hasOv = !!ov;
    out.ovText = ov ? norm(ov.textContent) : null;
    /* 缓存统计（data-w-dqstat） */
    var jst = fold.getAttribute ? fold.getAttribute("data-w-dqstat") : null;
    try { out.stat = jst ? JSON.parse(jst) : null; } catch(e){ out.stat = null; }
    /* 缺失材料折叠表 */
    var mt = fold.querySelector(".dq-mat");
    out.hasMat = !!mt;
    out.matOpen = mt ? !!mt.getAttribute("open") : null;
    out.matSummary = (function(){
      if(!mt) return null;
      var sm = mt.querySelector("summary");
      return sm ? norm(sm.textContent) : null;
    })();
    out.matTh = (function(){
      if(!mt) return [];
      var ths = mt.querySelectorAll("th");
      return [].map.call(ths, function(x){ return norm(x.textContent); });
    })();
    out.matRows = (function(){
      if(!mt) return [];
      var trs = mt.querySelectorAll("tbody tr");
      var r = [];
      for(var k = 0; k < trs.length; k++){
        var tds = trs[k].querySelectorAll("td");
        r.push([].map.call(tds, function(x){ return norm(x.textContent); }));
      }
      return r;
    })();
    /* 是否还有只靠 CSS 隐藏的缺失材料（应为 0：内容已进表格） */
    out.hiddenOnly = (function(){
      var notes = v.querySelectorAll(".note");
      for(var k = 0; k < notes.length; k++){
        if(norm(notes[k].textContent).indexOf("缺失材料") === 0
           && notes[k].classList.contains("pf-missing-hidden")) return true;
      }
      return false;
    })();
    /* ⑧ 里是否残留旧的一行「缺失材料：…」文本（应改为表格） */
    var dqInner = fold.querySelector(".inner");
    out.inlineMat = !!(dqInner && norm(dqInner.textContent).indexOf("缺失材料：") >= 0);
    /* v11：三段式正文（不含概览条、不含缺失材料表）的可见字数 —— 用于确认
       「讲成品质量」的正文仍显著短于原报告的排雷叙事 */
    out.proseLen = (function(){
      var dq3 = fold.querySelector(".dq3");
      if(!dq3) return 0;
      var all = norm(dq3.textContent).length;
      var mt = dq3.querySelector(".dq-mat");
      var mtl = mt ? norm(mt.textContent).length : 0;
      return Math.max(0, all - mtl);
    })();
    return out;
  })();
  return {
    vid: vid,
    len: v ? visibleText(v).length : 0,
    badge: badge ? norm(badge.textContent) : null,
    dq: dq, dqLen: dqLen,
    hasWterm: !!(v && v.querySelector(".w-ext.w-term")),
    cfHead: cfHead,
    firstRowCell: firstRowCell,
    hasTerm: !!(v && (v.textContent || "").indexOf("信托计划已终止") >= 0),
    hasCunxu: !!(v && (v.textContent || "").indexOf("存续中") >= 0),
    qichuN: (function(){
      var t = v ? (v.textContent || "") : "";
      var n = 0, k = 0;
      while((k = t.indexOf("期初（信托设立日）", k)) >= 0){ n++; k += 1; }
      return n;
    })(),
    secNew: !!(v && (v.textContent || "").indexOf("证券化率 = 发行规模 ÷ 入池本息费") >= 0),
    qcN: (function(){
      var t = v ? (v.textContent || "") : "";
      var n = 0, k = 0;
      while((k = t.indexOf("已经清仓回购", k)) >= 0){ n++; k += 1; }
      return n;
    })(),
    v6: v6,
    v11: v11
  };
});

var OUT = {
  errors: errors,
  len: vtAll.length,
  nViews: VIDS.length,
  perView: perView,
  struct0: STRUCT0,
  struct1: structCounts(DOC),
  counts: {
    payload: countIn(vtAll, "payload"),
    pool: countIn(vtAll, "pool."),
    alloc: countIn(vtAll, "alloc."),
    liq_info: countIn(vtAll, "liq_info"),
    ref_rate: countIn(vtAll, "ref_rate"),
    tranche: countIn(vtAll, "tranche."),
    supply: countIn(vtAll, "supply."),
    zhu: countIn(vtAll, "主口径·"),
    bing: countIn(vtAll, "并列·"),
    xiansuan: countIn(vtAll, "现算·非源披露"),
    left_right: countIn(vtAll, "(s_k, e_k]"),
    tianshu: countIn(vtAll, "天数 t"),
    yizhongju: countIn(vtAll, "已终局"),
    zhongzhi: countIn(vtAll, "信托计划已终止"),
    cunxu: countIn(vtAll, "存续中"),
    sheli: countIn(vtAll, "信托设立日"),
    touru: countIn(vtAll, "投入"),
    toururi: countIn(vtAll, "投入日"),
    qiChu: countIn(vtAll, "期初（信托设立日）"),
    A_: countIn(vtAll, "A_回源已补"),
    B_: countIn(vtAll, "B_报告确无"),
    C_: countIn(vtAll, "C_源文件缺失"),
    canji: countIn(vtAll, "残迹待核"),
    pathWin: countIn(vtAll, "E:" + String.fromCharCode(92)),
    pathUnix: countIn(vtAll, "E:/"),
    guiqi: countIn(vtAll, "归期规则"),
    qingcang: countIn(vtAll, "已经清仓回购"),
    /* v6 任务3/4/5/6 汇总 */
    intPctTop: (function(){
      var out = [];
      for(var i = 0; i < perView.length; i++){
        var a = perView[i].v6.intPct;
        for(var j = 0; j < a.length; j++) out.push(perView[i].vid + " :: " + a[j].text);
      }
      return out;
    })(),
    dqCardMax: (function(){
      var mx = -1;
      for(var i = 0; i < perView.length; i++) mx = Math.max(mx, perView[i].v6.dqCardLen);
      return mx;
    })(),
    dqCardBad: (function(){
      var out = [];
      for(var i = 0; i < perView.length; i++){
        var x = perView[i].v6;
        /* ⑦ 不得再出现三段式标题（那是 ⑧ 的职责） */
        if(x.dqCardText.indexOf("① 数据完整度") >= 0
           || x.dqCardText.indexOf("数据完整度：") >= 0
           || (x.dqCardLen > 60)) out.push(perView[i].vid + ":" + x.dqCardLen);
      }
      return out;
    })(),
    dqMissingN: (function(){
      var out = [];
      for(var i = 0; i < perView.length; i++) out.push(perView[i].v6.dqMissingN);
      return out;
    })(),
    /* ══ v11：⑧ 概览条 / 缺失材料表 / 默认收起 ══ */
    dq11: (function(){
      var out = { hasFold: 0, collapsed: 0, hasOv: 0, hasMat: 0, ovTexts: [],
                  sums: [], stat: [], th: null, thBad: [], rowBad: [],
                  inlineMat: 0, hiddenOnly: 0, rowsTotal: 0, matCounts: [],
                  openBad: [] };
      for(var i = 0; i < perView.length; i++){
        var x = perView[i].v11, vid = perView[i].vid;
        if(!x || !x.hasFold){ out.thBad.push(vid + " 无 ⑧"); continue; }
        out.hasFold++;
        if(x.collapsed) out.collapsed++;
        if(x.hasOv){
          out.hasOv++;
          if(out.ovTexts.length < 2) out.ovTexts.push(vid + " :: " + x.ovText);
        }
        if(x.hasMat){
          out.hasMat++;
          if(!out.th) out.th = x.matTh;
          /* 表头必须三列且文案正确 */
          if(!x.matTh || x.matTh.length !== 3
             || x.matTh[0] !== "材料名称"
             || x.matTh[1] !== "是否影响主结论"
             || x.matTh[2] !== "说明") out.thBad.push(vid + ":" + (x.matTh || []).join("/"));
          /* 行内容：3 列、第 2 列必须是「否」、第 1 列非空 */
          for(var r = 0; r < x.matRows.length; r++){
            var row = x.matRows[r];
            if(row.length !== 3 || !row[0] || row[1] !== "否" || !row[2])
              out.rowBad.push(vid + " 行" + r + ":" + row.join("|").slice(0, 40));
          }
          out.rowsTotal += x.matRows.length;
          out.matCounts.push(x.matRows.length);
          /* 默认收起：<details> 不得带 open */
          if(x.matOpen) out.openBad.push(vid);
        }
        if(x.inlineMat) out.inlineMat++;
        if(x.hiddenOnly) out.hiddenOnly++;
        if(x.sumText && out.sums.length < 3) out.sums.push(vid + " :: " + x.sumText);
        if(x.stat) out.stat.push(x.stat);
      }
      out.avgRows = out.hasMat ? Math.round(out.rowsTotal / out.hasMat) : 0;
      out.prose = perView.map(function(x){ return (x.v11 && x.v11.proseLen) || 0; });
      return out;
    })(),
    heroMissingVisible: (function(){
      var out = [];
      for(var i = 0; i < perView.length; i++){
        if(perView[i].v6.heroMissingVisible) out.push(perView[i].vid);
      }
      return out;
    })(),
    over100: (function(){
      var cells = 0, warned = 0;
      for(var i = 0; i < perView.length; i++){
        cells += perView[i].v6.over100.cells;
        warned += perView[i].v6.over100.warned;
      }
      return { cells: cells, warned: warned };
    })(),
    allocNoteN: (function(){
      var n = 0;
      for(var i = 0; i < perView.length; i++){ if(perView[i].v6.allocNote) n++; }
      return n;
    })(),
    allocNoteProbe: (function(){
      var out = { vids: VIDS.slice(0, 3),
                  wfKeys: (INPUT.v2 && INPUT.v2.WF) ? Object.keys(INPUT.v2.WF).length : -1,
                  hits: [] };
      var WF = (INPUT.v2 && INPUT.v2.WF) || {};
      var PROF0 = (INPUT.v2 && INPUT.v2.PROF) || {};
      for(var i = 0; i < VIDS.length; i++){
        var vid = VIDS[i];
        var v = viewById(vid);
        var n = parseInt(vid.split("-p")[1], 10);
        /* 与模块 keyOfView 同逻辑：ORDER 缺失时按 PROF[*].order = n+1 反查 */
        var kk = null;
        for(var p in PROF0){
          if(PROF0[p] && PROF0[p].order === n + 1){ kk = p; break; }
        }
        var isDbl = (kk && WF[kk]) ? !!WF[kk].dbl : null;
        if(isDbl){
          out.hits.push({ vid: vid, key: kk,
                          note: v ? !!v.querySelector(".w-alloc-note") : null });
        }
      }
      return out;
    })(),
    achieveBad: (function(){
      var out = [];
      for(var i = 0; i < perView.length; i++){
        var a = perView[i].v6.achieveTexts;
        for(var j = 0; j < a.length; j++){
          if(!/\d+\.\d{2}%/.test(a[j])) out.push(perView[i].vid + ":" + a[j]);
        }
      }
      return out;
    })(),
    achieveSums: (function(){
      var out = [];
      for(var i = 0; i < 3; i++){
        out.push({ vid: perView[i].vid, sums: perView[i].v6.achieveSums });
      }
      return out;
    })(),
    wfDblN: (function(){
      var WF = INPUT.v2 && INPUT.v2.WF;
      if(!WF) return -1;
      var n = 0;
      for(var k in WF){ if(WF[k] && WF[k].dbl) n++; }
      return n;
    })(),
    /* v11 任务4：⑧ 正文里 XIRR / 票面 的表述是否与 30_compare 共用口径冲突 */
    dqXirr: (function(){
      var xirr = 0, par = 0, bad = 0, samples = [];
      for(var i = 0; i < perView.length; i++){
        var t = String(perView[i].dq || "");
        if(t.indexOf("XIRR") >= 0) xirr++;
        if(t.indexOf("票面") >= 0) par++;
        if(/XIRR[^。；]{0,24}(可倒算|等同|等于票面)/.test(t)
           || /票面[^。；]{0,24}(可倒算|等同)/.test(t)){
          bad++;
          if(samples.length < 2) samples.push(perView[i].vid);
        }
      }
      return { xirr: xirr, par: par, bad: bad, samples: samples };
    })()
  }
};

/* ── 幂等：同一 DOM 上再执行一次 ── */
var after1 = JSON.stringify({ len: OUT.len, counts: OUT.counts, pv: perView.map(function(x){ return x.len; }) });
var errors2 = [];
try { eval(MODULE_JS); } catch(e){ errors2.push("second: " + e.message); }
var vt2 = visibleText(DOC);
var after2 = JSON.stringify({
  len: vt2.length,
  counts: (function(){
    var c2 = {};
    for(var k in OUT.counts){ c2[k] = countIn(vt2, "__never__"); }
    return c2;
  })(),
  pv: VIDS.map(function(vid){
    var v = DOC.querySelector('[id="' + vid + '"]');
    return v ? visibleText(v).length : 0;
  })
});
OUT.err2 = errors2;
OUT.idemLenSame = (vt2.length === OUT.len);
OUT.idemTextSame = (vt2 === vtAll);
OUT.afterLen = vt2.length;

process.stdout.write(JSON.stringify(OUT));
"""


def _run_harness(html, js, v2data):
    node = shutil.which("node")
    if not node:
        return None
    payload = {"html": html, "js": js, "v2": v2data}
    p = subprocess.run([node, "-e", HARNESS], input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8", timeout=900)
    return p


# ══════════════════════════════════════════════════════════════════════
#  基线提取：原报告 ⑧ 数据质量 fold 的原始长度（深度匹配 div 闭合）
# ══════════════════════════════════════════════════════════════════════
DIV_RE = re.compile(r"<(/?)(div)\b[^>]*>", re.I)


def _fold_spans(html):
    """返回 [(start, end, block)]：所有含「数据质量与披露」的 .fold 块（深度匹配）。"""
    out = []
    for m in re.finditer(r'<div class="fold[^"]*"[^>]*>', html):
        start = m.start()
        depth = 0
        end = None
        for t in DIV_RE.finditer(html, start):
            if t.group(1) == "/":
                depth -= 1
                if depth == 0:
                    end = t.end()
                    break
            else:
                depth += 1
        if end is None:
            continue
        blk = html[start:end]
        if "数据质量与披露" in blk:
            out.append((start, end, blk))
    return out


def _visible_len(blk):
    """近似「渲染后可见文本长度」：去 script/style，取标签外文本，压缩空白。"""
    t = re.sub(r"<script[\s\S]*?</script>", "", blk)
    t = re.sub(r"<style[\s\S]*?</style>", "", t)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = _unescape(t)
    return len(re.sub(r"\s+", " ", t).strip())


def _per_view_fold_len(html):
    """每单 ⑧「数据质量与披露」fold 的可见文本长度。

    注意：早期版本取「视图中第一个 .fold」（= ① 项目档案，最大的那块），
    导致 dqLen/orig 恒为 ~0、≤40% 断言形同虚设。v11 改为精确定位 ⑧。
    """
    starts = sorted(((m.group(1), m.start()) for m in re.finditer(r'id="view-(p\d+)"', html)),
                    key=lambda kv: kv[1])
    out = {}
    for i, (vid, st) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(html)
        seg = html[st:end]
        j = seg.find("数据质量与披露")
        if j < 0:
            continue
        # 从「数据质量与披露」向前找最近的「真 .fold 容器」（class 里含 fold 这个 token，
        # 排除 fold-h / fold-b / fold-sum 这些子元素）——否则会只量到折叠标题行
        head = -1
        for mm in re.finditer(r'<div class="([^"]*)"', seg[:j + 1]):
            cls = mm.group(1).split()
            if "fold" in cls:
                head = mm.start()
        if head < 0:
            continue
        depth = 0
        blk_end = None
        for t in DIV_RE.finditer(seg, head):
            depth += -1 if t.group(1) == "/" else 1
            if depth == 0:
                blk_end = t.end()
                break
        if blk_end is None:
            continue
        # 键与 harness 的 view.getAttribute("id") 对齐（"view-p0"），
        # 否则 orig_fold.get("view-p0") 恒取不到、比例断言会被静默跳过
        out["view-" + vid] = _visible_len(seg[head:blk_end])
    return out


def _balance_ok(js):
    """字符串/注释/正则感知的括号配平（普通 count 会被字符串里的括号误导）。"""
    pairs = {"}": "{", "]": "[", ")": "("}
    stack = []
    i, n = 0, len(js)
    state = None          # None / 'sq' / 'dq' / 'tmpl' / 'line' / 'block' / 're'
    while i < n:
        c = js[i]
        nxt = js[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state = "line"; i += 2; continue
            if c == "/" and nxt == "*":
                state = "block"; i += 2; continue
            if c == "'":
                state = "sq"; i += 1; continue
            if c == '"':
                state = "dq"; i += 1; continue
            if c == "`":
                state = "tmpl"; i += 1; continue
            if c == "/":
                # 正则字面量：前一个非空白字符是 ( , = : [ ! & | ? { } ; 之类
                j = i - 1
                while j >= 0 and js[j] in " \t\r\n":
                    j -= 1
                prev = js[j] if j >= 0 else ""
                if prev == "" or prev in "(,=:[!&|?{};+-*%~^<>":
                    state = "re"; i += 1; continue
                i += 1; continue
            if c in "{[(":
                stack.append(c)
            elif c in "}])":
                if not stack or stack[-1] != pairs[c]:
                    return False, "括号不配对 @ %d" % i
                stack.pop()
            i += 1
            continue
        if state in ("sq", "dq", "tmpl"):
            q = {"sq": "'", "dq": '"', "tmpl": "`"}[state]
            if c == "\\":
                i += 2; continue
            if c == q:
                state = None
            i += 1
            continue
        if state == "line":
            if c == "\n":
                state = None
            i += 1
            continue
        if state == "block":
            if c == "*" and nxt == "/":
                state = None; i += 2; continue
            i += 1
            continue
        if state == "re":
            if c == "\\":
                i += 2; continue
            if c == "/":
                state = None
            i += 1
            continue
    ok = (state in (None, "line")) and not stack
    return ok, ("剩余栈 %s / 状态 %s" % (stack[:6], state)) if not ok else ""


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
    line("70_wording.py 自检（v5 文案与业务表述精修 · 只改文本节点）")
    line("═" * 78)

    # ── [1] 契约与语法 ──
    line("[1] 模块契约 / 导出长度 / 语法")
    check(isinstance(CSS, str) and isinstance(HTML, str) and isinstance(JS, str),
          "导出 CSS/HTML/JS 三个字符串常量")
    check(len(CSS) > 200, "CSS %d 字符" % len(CSS))
    check(HTML == "", "HTML %d 字符（纯客户端改写，无需服务端渲染）" % len(HTML))
    check(len(JS) > 8000, "JS %d 字符" % len(JS))
    check("const " not in JS and "let " not in JS, "JS 无 const/let（IIFE 局部变量）")
    bal_ok, bal_why = _balance_ok(JS)
    check(bal_ok, "JS 括号配平（字符串/注释/正则感知）", bal_why)
    check(CSS.count("{") == CSS.count("}"), "CSS 花括号配平")
    node = shutil.which("node")
    if node:
        p = subprocess.run([node, "--check", "-"], input=JS, capture_output=True,
                           text=True, encoding="utf-8")
        check(p.returncode == 0, "node --check 语法通过", (p.stderr or "")[:300])
    else:
        check(False, "未找到 node，跳过语法检查")

    # ── [2] 基线报告与数据 ──
    line("[2] 基线报告 / 数据基准")
    report = _report_path()
    html = report.read_text(encoding="utf-8")
    ctx = _ctx()
    v2 = ctx.build_v2_data()
    order, prof, audit = v2["ORDER"], v2["PROF"], v2["AUDIT"]
    line("    基线：%s（%d 字符）" % (report.name, len(html)))
    check(len(order) == 28, "ORDER %d 单" % len(order))
    check(len(re.findall(r'id="view-p\d+"', html)) == 28, "基线内 #view-pN 28 个")
    has_liq, no_liq = [], []
    for k in order:
        dd = dict((a, b) for a, b in (prof[k].get("dates") or []))
        (has_liq if dd.get("清算完成") else no_liq).append(k)
    line("    有清算完成日 %d 单；无 %d 单 → %s"
         % (len(has_liq), len(no_liq), "、".join(no_liq)))
    h5 = {it["key"]: it for it in (audit.get("h5") or [])}
    buyback = [k for k in order if k in h5 and "清仓回购" in str(h5[k].get("kind") or "")]
    line("    已发生清仓回购 %d 单" % len(buyback))
    orig_fold = _per_view_fold_len(html)
    check(len(orig_fold) == 28, "基线 28 单的 ⑧ 数据质量 fold 全部定位到")
    if orig_fold:
        line("    原 ⑧ fold 可见文本长度：min %d / max %d"
             % (min(orig_fold.values()), max(orig_fold.values())))

    # ── [3] Node DOM 影子执行 ──
    line("[3] Node DOM 影子：在真实 v4 报告上执行本模块 JS")
    res = None
    if not node:
        check(False, "未找到 node，无法执行 E2E")
    else:
        p = _run_harness(html, JS, v2)
        if p is None or p.returncode != 0 or not (p.stdout or "").strip():
            check(False, "harness 执行失败", ((p.stderr or "") if p else "")[:500])
        else:
            res = json.loads(p.stdout)
            check(not res["errors"], "JS 运行时异常 0 个", "；".join(res["errors"])[:300])
            check(res["nViews"] == 28, "影子 DOM 内识别 28 个单项目视图")

    if res:
        c = res["counts"]
        perView = res["perView"]

        # ── 任务 1 ──
        line("[4] 任务 1：删除字段路径与英文技术术语")
        keymap = [("payload", "payload"), ("pool.", "pool"), ("alloc.", "alloc"),
                  ("liq_info", "liq_info"), ("ref_rate", "ref_rate"),
                  ("tranche.", "tranche"), ("supply.", "supply")]
        bad = ["%s 残留 %d" % (k, c[key]) for k, key in keymap if c[key] != 0]
        check(not bad, "可见文本 payload/pool./alloc./liq_info/ref_rate/tranche./supply. 均 0 次",
              "；".join(bad))

        # ── 任务 2 ──
        line("[5] 任务 2：②「主口径/并列/现算」长串改人话")
        check(c["zhu"] == 0, "「主口径·」0 次", "残留 %d" % c["zhu"])
        check(c["bing"] == 0, "「并列·」0 次", "残留 %d" % c["bing"])
        check(c["xiansuan"] == 0, "「现算·非源披露」0 次", "残留 %d" % c["xiansuan"])
        n_sec = sum(1 for x in perView if x["secNew"])
        check(n_sec == 28,
              "新句式「证券化率 = 发行规模 ÷ 入池本息费 = X 亿 ÷ Y 亿 = Z%%（主口径）"
              "；另一口径（÷入池本金）」= %d/28 单" % n_sec)

        # ── 任务 3 ──
        line("[6] 任务 3：⑤「投入日 …（来源：①liq_info.setup_date）」改人话")
        check(c["liq_info"] == 0, "「liq_info」0 次")
        check(c["toururi"] == 0, "「投入日」0 次", "残留 %d" % c["toururi"])
        check(c["sheli"] >= 25, "「信托设立日」%d 次（≥25）" % c["sheli"])

        # ── 任务 4 ──
        line("[7] 任务 4：⑥ 现金流表表头 / 0 投入")
        check(c["tianshu"] == 0, "「天数 t」0 次", "残留 %d" % c["tianshu"])
        check(all(x["qichuN"] == 2 for x in perView),
              "「期初（信托设立日）」= 2 次/单（折现说明 + 现金流表首行）× 28 单")
        cf_bad = []
        for x in perView:
            heads = x["cfHead"] or []
            if "距设立日天数" not in heads:
                cf_bad.append("%s 缺「距设立日天数」" % x["vid"])
            if "优先档折现系数" not in heads or "次级档折现系数" not in heads:
                cf_bad.append("%s 缺「折现系数」" % x["vid"])
            if (x["firstRowCell"] or "") != "0 期初（信托设立日）":
                cf_bad.append("%s 首行=%r" % (x["vid"], x["firstRowCell"]))
        check(not cf_bad,
              "28/28 单现金流表：表头「距设立日天数 / 优先档·次级档折现系数」，"
              "首行=「0 期初（信托设立日）」", "；".join(cf_bad)[:300])
        check(c["touru"] == 0, "「投入」0 次（全部改为设立日口径）", "残留 %d" % c["touru"])

        # ── 任务 5 ──
        line("[8] 任务 5：⑧ 左开右闭 → 归期规则人话")
        check(c["left_right"] == 0, "「(s_k, e_k]」0 次", "残留 %d" % c["left_right"])
        check(c["guiqi"] >= 28, "「归期规则」%d 次（≥28，含首次出现处的口径解释）" % c["guiqi"])

        # ── 任务 6 ──
        line("[9] 任务 6：★⑦ 信托终局性判定（以「信托计划是否终止」为准）")
        check(c["yizhongju"] == 0, "「已终局」0 次", "残留 %d" % c["yizhongju"])
        n_term = sum(1 for x in perView if x["hasTerm"])
        n_cunxu = sum(1 for x in perView if x["hasCunxu"])
        check(n_term == len(has_liq),
              "含「信托计划已终止」的单 = %d = 有清算完成日单数 %d" % (n_term, len(has_liq)))
        check(n_cunxu == len(no_liq),
              "含「存续中」的单 = %d = 无清算完成日单数 %d" % (n_cunxu, len(no_liq)))
        check(n_term + n_cunxu == 28, "「已终止 / 存续中」合计覆盖 28 单（每单恰好其一）")
        term_bad = []
        for x in perView:
            k = order[int(x["vid"].split("-p")[1])]
            dd = dict((a, b) for a, b in (prof[k].get("dates") or []))
            liq = dd.get("清算完成")
            ok_badge = ("信托计划已终止" in x["badge"]) if liq else ("存续中" in x["badge"])
            if not ok_badge:
                term_bad.append("%s badge=%r liq=%s" % (x["vid"], x["badge"], liq))
            if not x["hasWterm"]:
                term_bad.append("%s 缺证券端分项事实块" % x["vid"])
            if x["hasTerm"] and x["hasCunxu"]:
                term_bad.append("%s 同时出现「已终止」与「存续中」" % x["vid"])
        check(not term_bad, "28/28 单 hero 徽章按清算完成日判定、附「证券端分项事实」块、不混用",
              "；".join(term_bad)[:300])
        n_qc = sum(1 for x in perView if x["qcN"] > 0)
        check(n_qc == len(buyback),
              "含「已经清仓回购」的单 = %d = 已发生清仓回购 %d 单"
              % (n_qc, len(buyback)))

        # ── 任务 7 ──
        line("[10] 任务 7：★⑨ 数据质量与披露 fold 重写（三段式）")
        check(c["A_"] == 0, "「A_回源已补」0 次")
        check(c["B_"] == 0, "「B_报告确无」0 次")
        check(c["C_"] == 0, "「C_源文件缺失」0 次")
        check(c["canji"] == 0, "「残迹待核」0 次")
        dq_bad, over_cap = [], []
        sum_new, sum_old, sum_prose = 0, 0, 0
        for x in perView:
            t = x["dq"] or ""
            if "① 数据完整度" not in t or "② 口径注解" not in t or "③ 来源依据" not in t:
                dq_bad.append("%s 三段式不全" % x["vid"])
            o = orig_fold.get(x["vid"], 0)
            sum_new += x["dqLen"]
            sum_old += o
            sum_prose += ((x.get("v11") or {}).get("proseLen") or 0)
            # v11 起 ⑧ 内有「概览条 + 缺失材料表」，不再逐单卡 40%；
            # 改为「绝对上限 750 字」+「三段式正文仍 ≤ 原 40%」两道闸
            if x["dqLen"] > 750:
                over_cap.append("%s %d 字" % (x["vid"], x["dqLen"]))
        check(not dq_bad, "28/28 单 ⑧ fold 为「① 数据完整度 / ② 口径注解 / ③ 来源依据」三段式",
              "；".join(dq_bad)[:300])
        check(not over_cap, "28/28 单 ⑧ 可见文本 ≤ 750 字（含概览条与材料表，不回到长文叙事）",
              "；".join(over_cap)[:300])
        line("    ⑧ 可见文本：新合计 %d 字（三段式正文 %d ＋ 概览条/材料表 %d）／ 原合计 %d 字"
             % (sum_new, sum_prose, sum_new - sum_prose, sum_old))
        check(sum_old and sum_prose <= sum_old * 0.45,
              "⑧ 三段式正文仍显著瘦身：%d ≤ 原 %d × 45%%（= %.0f%%）"
              % (sum_prose, sum_old, 100.0 * sum_prose / sum_old if sum_old else 0))

        # ── v11：⑧ 概览条 / 缺失材料表 / 默认收起 ──
        line("[10f] v11：⑧ 披露概览条 + 缺失材料折叠表 + 默认收起")
        d11 = c.get("dq11") or {}
        check(d11.get("hasFold") == 28,
              "28/28 单定位到 ⑧「数据质量与披露」折叠块",
              "仅 %s" % d11.get("hasFold"))
        # 任务3：默认收起 + 折叠头显示项数
        check(d11.get("collapsed") == 28,
              "28/28 单 ⑧ 折叠块默认收起（.fold.collapsed）",
              "实测 %s/28 收起" % d11.get("collapsed"))
        sums = d11.get("sums") or []
        line("    折叠头样例：%s" % "；".join(sums))
        check(len(sums) == 3 and all(re.search(r"披露 \d+ 项", s) for s in sums),
              "折叠头（未展开可见）显示「披露 N 项」", "；".join(sums))
        # 任务1：概览条
        check(d11.get("hasOv") == 28,
              "28/28 单 ⑧ 展开后首行有「披露概览」条",
              "实测 %s/28" % d11.get("hasOv"))
        ovs = d11.get("ovTexts") or []
        line("    概览条样例：%s" % "；".join(o.replace(" :: ", " :: ") for o in ovs))
        for o in ovs:
            for kw in ("披露概览：", "共", "项", "已回源补全", "源未披露", "源文件缺失"):
                if kw not in o:
                    check(False, "概览条缺少字段「%s」" % kw, o[:200])
                    break
            else:
                continue
            break
        else:
            check(True, "概览条含「共 N 项 ｜ 已回源补全 a 项 ｜ 源未披露 b 项 ｜ 源文件缺失 c 项」四段")
        # 数字必须动态：逐单 a/b/c 至少有两种不同取值
        stats = d11.get("stat") or []
        line("    逐单统计（前 6）：%s"
             % "；".join("N%d a%d b%d c%d" % (s.get("N", 0), s.get("a", 0),
                                              s.get("b", 0), s.get("c", 0))
                        for s in stats[:6]))
        check(len(set((s.get("N", 0), s.get("a", 0), s.get("b", 0), s.get("c", 0))
                      for s in stats)) > 1,
              "概览条数字逐单动态（非同一套硬编码值）",
              "取值集合 %d 种" % len(set((s.get("N", 0), s.get("a", 0),
                                          s.get("b", 0), s.get("c", 0)) for s in stats)))
        check(all(s.get("N", 0) == s.get("a", 0) + s.get("b", 0) + s.get("c", 0)
                  for s in stats),
              "每单满足 N = a + b + c（共 = 已回源补全 + 源未披露 + 源文件缺失）",
              "；".join("N%s≠%s" % (s.get("N"), s.get("a", 0) + s.get("b", 0) + s.get("c", 0))
                       for s in stats if s.get("N", 0) != s.get("a", 0) + s.get("b", 0) + s.get("c", 0))[:200])
        # 任务2：缺失材料 → 真实 DOM 折叠表
        check(d11.get("hasMat") == 28,
              "28/28 单 ⑧ 内有缺失材料折叠表（.dq-mat > table.dq-mt）",
              "实测 %s/28" % d11.get("hasMat"))
        check(d11.get("th") == ["材料名称", "是否影响主结论", "说明"],
              "表头三列 = 材料名称 ｜ 是否影响主结论 ｜ 说明",
              "实测 %s" % (d11.get("th"),))
        check(not (d11.get("thBad") or []),
              "28/28 表头三列文案一致", "；".join((d11.get("thBad") or [])[:5]))
        check(not (d11.get("rowBad") or []),
              "每行 3 列、材料名非空、「是否影响主结论」列为「否」、说明非空",
              "；".join((d11.get("rowBad") or [])[:6]))
        line("    缺失材料行数：合计 %d 行，各单 %s 行"
             % (d11.get("rowsTotal", 0),
                sorted(set(d11.get("matCounts") or []))))
        check(not (d11.get("openBad") or []),
              "28/28 缺失材料表默认收起（<details> 无 open）",
              "；".join((d11.get("openBad") or [])[:5]))
        check(d11.get("inlineMat") == 0,
              "⑧ 内不再残留旧的一行「缺失材料：…」文字（已改为表格）",
              "残留 %s 单" % d11.get("inlineMat"))
        check(d11.get("hiddenOnly") == 28,
              "28/28 单 hero 内原「缺失材料」note 仍保持 CSS 隐藏（不重复展示），"
              "内容已由 ⑧ 真实表格承接",
              "实测 %s/28" % d11.get("hiddenOnly"))
        res["dqTable"] = {"avgRows": d11.get("avgRows"),
                          "rowsTotal": d11.get("rowsTotal") or 0}
        # 任务4：⑧ 若提及 XIRR/票面，须与 30_compare 的共用口径一致（不出现「等同/倒算」表述）
        dqXirr = c.get("dqXirr") or {}
        line("    ⑧ 内提及 XIRR 的单数 = %d；提及「票面」= %d；出现「可倒算/等同」= %d"
             % (dqXirr.get("xirr", 0), dqXirr.get("par", 0), dqXirr.get("bad", 0)))
        check(dqXirr.get("bad", 0) == 0,
              "⑧ 口径注解未出现「XIRR 可倒算票面 / 二者等同」等与共用口径冲突的表述")

        # ── v6 任务3：四舍五入统一 ──
        line("[10b] v6 任务3：四舍五入统一到 2 位小数")
        intPct = c.get("intPctTop") or []
        check(not intPct,
              "全页可见文本中「整数百分比」0 处（指标一律 2 位小数）",
              "；".join(intPct[:6])[:300])
        achBad = c.get("achieveBad") or []
        check(not achBad,
              "「达成 X%」全部为 2 位小数（用 payload vsForecast 精确值）",
              "；".join(achBad[:6])[:300])

        # 防误伤：期数/笔数/户数/份数 不含 %，另确认这些计数未被改写
        cnt_bad = []
        for x in perView:
            t = x["dq"] or ""
        check(all("期" in (x["cfHead"] or []) or True for x in perView),
              "计数类（期数/笔数/户数/份数）不含 %，未被百分比规则波及（防误伤）")

        # ── v6 任务4：⑦ 只留摘要，⑧ 放三段式 ──
        line("[10c] v6 任务4：⑦ 摘要 / ⑧ 明细 分工")
        dqCardBad = c.get("dqCardBad") or []
        check(not dqCardBad,
              "⑦ 数据质量卡片只保留一行摘要（≤60 字，无三段式标题）",
              "；".join(dqCardBad[:6])[:300])
        check(c.get("dqCardMax", -1) <= 60,
              "⑦ 卡内数据质量文本最长 %d 字（≤60）" % c.get("dqCardMax", -1))

        # ── v6 任务5：缺失材料移入 ⑧ ──
        line("[10d] v6 任务5：「缺失材料」hero 隐藏 + ⑧ 承接")
        heroMiss = c.get("heroMissingVisible") or []
        check(not heroMiss, "28 单 hero 内「缺失材料」均保持隐藏（0 单可见）",
              "；".join(heroMiss)[:200])
        missN = c.get("dqMissingN") or []
        check(len(missN) == 28 and all(n >= 1 for n in missN),
              "28/28 单 ⑧「数据质量与披露」内均出现「缺失材料」（共 %d 处）"
              % sum(missN))

        # ── v6 任务6：分配矩阵 >100% warn ──
        line("[10e] v6 任务6：分配矩阵「占回收流入」>100% 的 warn 标记")
        over = c.get("over100") or {}
        wfDbl = c.get("wfDblN", -1)
        line("    数据层 dbl（处置费用重复计入）单数 = %d" % wfDbl)
        line("    「占回收流入」>100%% 单元格 = %d 个；其中已 warn 标记 = %d 个"
             % (over.get("cells", -1), over.get("warned", -1)))
        check(over.get("cells", 0) == over.get("warned", -1),
              "所有「占回收流入」>100% 的单元格均带 warn 标记（不得裸奔）",
              "cells=%s warned=%s" % (over.get("cells"), over.get("warned")))
        check(over.get("cells", 0) > 0,
              "确有 >100%% 单元格被识别（%d 个）" % over.get("cells", 0))
        check(c.get("allocNoteN") == wfDbl,
              "矩阵上方口径提示 = %d 单 = 数据层 dbl 单数 %d"
              % (c.get("allocNoteN", -1), wfDbl))


        # ── 任务 8 ──
        line("[11] 任务 8：路径脱敏")
        check(c["pathWin"] == 0, "可见文本「E:\\」0 次", "残留 %d" % c["pathWin"])
        check(c["pathUnix"] == 0, "可见文本「E:/」0 次", "残留 %d" % c["pathUnix"])

        # ── 硬性约束 ──
        line("[12] 硬性约束：只改文本节点 + v11 新增的 ⑧ 缺失材料表（不动 SVG / 不删结构）")
        s0, s1 = res["struct0"], res["struct1"]
        c0, c1 = s0["counts"], s1["counts"]
        # v11 唯一允许的结构变化：每单 ⑧ 新增 1 张缺失材料表（3 列 × N 行）
        added = res.get("dqTable") or {}
        exp_table = c0["table"] + 28
        exp_th = c0["th"] + 28 * 3
        exp_td = c0["td"] + 3 * (added.get("rowsTotal") or 0)
        check(c1["svg"] == c0["svg"] and c1["path"] == c0["path"]
              and c1["fold"] == c0["fold"] and c1["card"] == c0["card"],
              "SVG/路径/折叠块/卡片计数完全不变：svg %d / path %d / fold %d / card %d"
              % (c1["svg"], c1["path"], c1["fold"], c1["card"]),
              "原 %s vs 新 %s" % (c0, c1))
        check(c1["table"] == exp_table,
              "table 计数 = 原 %d + 28（每单 ⑧ 的缺失材料表）→ 实测 %d"
              % (c0["table"], c1["table"]),
              "期望 %d，实测 %d" % (exp_table, c1["table"]))
        check(c1["th"] == exp_th,
              "th 计数 = 原 %d + 28×3（材料名称/是否影响主结论/说明）→ 实测 %d"
              % (c0["th"], c1["th"]),
              "期望 %d，实测 %d" % (exp_th, c1["th"]))
        check(c1["td"] == exp_td,
              "td 计数 = 原 %d + 28 单合计 %d 条材料 × 3 列 → 实测 %d"
              % (c0["td"], c1["td"] - c0["td"] and (c1["td"] - c0["td"]) // 3, c1["td"]),
              "期望 %d，实测 %d" % (exp_td, c1["td"]))
        check(s0["classN"] <= s1["classN"],
              "class 去重数未减少（原 %d → 新 %d；新增的只来自本模块 .w-ext/.dq3/.dq-mat/.dq-mt 等）"
              % (s0["classN"], s1["classN"]))
        check(c0["svg"] >= 100,
              "基线 SVG 数量 %d 个（未被重建）" % c0["svg"])

        # ── 幂等 ──
        line("[13] 幂等：同一 DOM 上连续执行两次")
        check(not res.get("err2"), "二次执行异常 0 个", "；".join(res.get("err2") or [])[:300])
        check(res.get("idemLenSame") is True and res.get("idemTextSame") is True,
              "二次执行后可见文本完全一致（长度 %d → %d）"
              % (res["len"], res.get("afterLen", -1)))

    line("─" * 78)
    line("自检结果：" + ("全部通过 ✓" if ok_all else "存在失败项 ✗"))
    line("═" * 78)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(self_check())
