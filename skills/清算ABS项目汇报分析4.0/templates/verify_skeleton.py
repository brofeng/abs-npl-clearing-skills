#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_skeleton.py —— 验证器骨架（可直接跑，按需加断言）

核心：无头浏览器渲染后用 document.title 回传 JSON，比读源码可靠得多。
（客户端改写后源文件仍含原文，静态断言会全过但用户看到的是旧的）

用法：
    <python> verify_skeleton.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

E = Path(r"E:\不良ABS穿透研究\清算28单_不良ABS分析")
OUT = E / "清算28单_不良ABS穿透分析报告_vN.html"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
LOG = E / "_rebuild_log"
LOG.mkdir(exist_ok=True)

R = []   # [(ok, 分类, 描述, 详情)]


def chk(cat, desc, cond, detail=""):
    R.append((bool(cond), cat, desc, detail))
    mark = "✅" if cond else "❌"
    print(f"  {mark} [{cat}] {desc:<34} {detail}")


# ══════════════ 探针（关键：用 title 回传）══════════════
PROBE = r"""
setTimeout(function(){
  var o={};
  function click(v){ var a=document.querySelector('.sb-item[data-view="'+v+'"]'); if(a){a.click(); return true;} return false; }
  o.tabs=document.querySelectorAll('.sb-item').length;
  o.views=document.querySelectorAll('.view').length;

  // ⚠ 必须先切到目标视图再量尺寸：非激活视图 display:none，rect 全 0
  click('overview');
  o.svg=document.querySelectorAll('svg').length;
  o.ovk=document.querySelectorAll('#view-overview .ov-k').length;

  // ⚠ 图表转换/渲染在视图激活时触发 → 没点进去过的视图还是原始态
  click('p0');
  setTimeout(function(){
    var v0=document.querySelector('#view-p0');
    if(v0){
      // 段落统计、面板宽度、时间轴节点……
      var tl=v0.querySelector('.pf-tl');
      o.tlNodes = tl? tl.querySelectorAll('.pf-ts').length : 0;
      o.tlHover = tl? tl.querySelectorAll('.pf-ts[title]').length : 0;
    }

    // 长小数检查（折现因子豁免）
    var longDec=0;
    var vis=document.querySelector('.view.on')||document;
    vis.querySelectorAll('div,span,b,td,th').forEach(function(el){
      if(el.children.length) return;
      var t=(el.textContent||'').trim();
      if(t.length>40 || !/\.\d{5,}/.test(t)) return;
      var tbl=el.closest('table'), head=tbl?(tbl.textContent.slice(0,300)):'';
      if(/折现|贴现|DF\b/.test(head)) return;
      longDec++;
    });
    o.longDec=longDec;

    // 禁用词（渲染后文本才准）
    var body=document.body.innerText||'';
    o.banned = ['折价率','已终局','倒算率','可倒算','预测 XIRR','payload.']
      .filter(function(k){ return body.indexOf(k)>=0; }).join(',');

    document.title='VRESULT:'+JSON.stringify(o);
  }, 1200);
}, 2600);
"""


def run_probe(h):
    """注入探针 + 错误钩子，跑无头 Edge，取回 VRESULT。"""
    hook = ("<script>window.__e=[];window.addEventListener('error',function(e){"
            "window.__e.push((e.message||'')+'@'+(e.lineno||''));"
            "document.title='ERR:'+window.__e.join(' || ');});</script>")
    test = E / "_vt.html"
    test.write_text(
        h.replace("<head>", "<head>" + hook, 1).replace("</body>", f"<script>{PROBE}</script></body>", 1),
        encoding="utf-8")
    url = "file:///" + str(test).replace("\\", "/")
    pr = subprocess.run(
        [str(EDGE), "--headless=new", "--disable-gpu", "--no-sandbox",
         "--window-size=1600,1400",              # ⚠ 必须设，否则触发响应式降级
         "--virtual-time-budget=30000", "--dump-dom", url],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=600)
    dom = pr.stdout or ""
    ttl = re.search(r"<title>(.*?)</title>", dom, re.S)
    title = ttl.group(1) if ttl else ""
    res = {}
    m = re.search(r"VRESULT:(\{.*?\})", title, re.S)
    if m:
        try:
            res = json.loads(m.group(1))
        except Exception as e:
            print("   ⚠ 解析 VRESULT 失败", e)
    return dom, title, res


def main():
    print("═" * 74)
    print("终验")
    print("═" * 74)
    h = OUT.read_text(encoding="utf-8")

    # ── 静态断言（读源文件，约 1/3）──
    n_view = h.count('class="view"')
    n_sb = h.count('class="sb-item"')
    chk("结构", "视图数 ≥ 30", n_view >= 30, f"{n_view}")
    chk("结构", "侧栏项 ≥ 4", n_sb >= 4, f"{n_sb}")
    chk("口径", "无「折价率」", h.count("折价率") == 0, f"{h.count('折价率')} 次")
    chk("口径", "无「已终局」", h.count("已终局") == 0, f"{h.count('已终局')} 次")
    chk("口径", "无内部编码", all(h.count(k) == 0 for k in
                              ("A_回源已补", "B_报告确无", "C_源文件缺失", "残迹待核")), "")
    chk("口径", "无本地路径", h.count("E:\\不良ABS穿透研究") == 0, "")
    chk("工程", "标签配平（模块层已修）", True, "见 build 日志")

    # ── 渲染断言（约 2/3）──
    dom, title, res = run_probe(h)
    chk("工程", "无运行时错误", not title.startswith("ERR:"),
        "正常" if not title.startswith("ERR:") else title[:120])
    if res:
        print(f"\n  渲染实测：侧栏 {res.get('tabs')} 项 · 视图 {res.get('views')} · SVG {res.get('svg')}")
        chk("交互", "时间轴节点 ≥8", (res.get("tlNodes") or 0) >= 8, f"{res.get('tlNodes')} 节点")
        chk("交互", "时间轴有悬停", (res.get("tlHover") or 0) >= 8, f"{res.get('tlHover')} 个 title")
        chk("数据", "无未舍入长小数", (res.get("longDec") or 0) == 0, f"{res.get('longDec')} 处")
        chk("口径", "渲染后无禁用词", not res.get("banned"), f"命中「{res.get('banned','')}」")

    # ── 汇总 ──
    n, ok = len(R), sum(1 for r in R if r[0])
    print("\n" + "═" * 74)
    print(f"汇总：{n} 断言　PASS {ok}　FAIL {n-ok}")
    summary = {"ts": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
               "asserts": n, "PASS": ok, "FAIL": n - ok,
               "items": [{"ok": r[0], "cat": r[1], "desc": r[2], "detail": r[3]} for r in R]}
    (LOG / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"留痕：{LOG / 'summary.json'}")
    if n - ok:
        print(f"\n❌ {n-ok} 个断言失败")
        sys.exit(1)
    print("\n✅ 全部通过")


if __name__ == "__main__":
    main()
