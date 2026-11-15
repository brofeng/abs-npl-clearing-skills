#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""probe_report.py —— 提取 / 校验报告的「版式 + 文案」指纹

背景：本技能的视觉正确性不能靠"读源码猜"，必须可机器比对。
本脚本用无头浏览器**逐个激活 31 个视图**，采集每视图的：
  · 视图 id / 标题 / 侧栏菜单文案
  · 每个区块(h2/h3)的标题与顺序
  · 卡片数、KPI 格数、表格行数、SVG 数
  · 栅格列数、卡片高度、字号分布
  · **渲染后可见全文**（客户端改写后的真值）
存成 spec JSON，供 verify 模式逐字段比对。

用法：
    # 生成基线（改版后重新生成一次）
    <python> probe_report.py --html <报告.html> --mode extract --out <spec.json>

    # 校验（DoD 门禁；不一致则 EXIT=1）
    <python> probe_report.py --html <报告.html> --mode verify --spec <spec.json>

    # 只校验文案（快）
    <python> probe_report.py --html ... --mode verify --spec ... --only text
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

VIEW_WAIT_MS = 700          # 每视图激活后等待渲染
TOTAL_BUDGET_MS = 240000    # 无头浏览器虚拟时间预算


def find_edge():
    for p in EDGE_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit("未找到 Edge，请用 --edge 指定")


PROBE = r"""
<script>
(function(){
  var VIEW_WAIT = %(wait)d;
  var out = {views: [], meta: {}};
  var items = Array.from(document.querySelectorAll('.sb-item[data-view]'));
  out.meta.viewCount = document.querySelectorAll('.view').length;
  out.meta.navCount = items.length;
  out.meta.navText = items.map(function(a){ return (a.textContent||'').trim(); });
  out.meta.title = document.title;
  out.meta.svgTotal = document.querySelectorAll('svg').length;

  function norm(s){
    return (s||'').replace(/\u00a0/g,' ')
                   .replace(/[ \t]+/g,' ')
                   .replace(/\s*\n\s*/g,'\n')
                   .trim();
  }
  function gridCols(el){
    var cs = getComputedStyle(el), t = cs.gridTemplateColumns||'';
    var m = t.match(/repeat\(\s*(\d+)/);
    if (m) return parseInt(m[1],10);
    if (!t || t === 'none') return 0;
    return t.trim().split(/\s+/).length;
  }
  function fsStat(scope){
    var map = {};
    (scope||document).querySelectorAll('svg text, svg tspan').forEach(function(t){
      var fs = getComputedStyle(t).fontSize; map[fs] = (map[fs]||0)+1;
    });
    return map;
  }

  var i = 0;
  function step(){
    if (i >= items.length) {
      var el = document.createElement('script');
      el.type = 'application/json'; el.id = '__SPEC__';
      el.textContent = JSON.stringify(out);
      document.body.appendChild(el);
      document.title = 'SPEC_DONE';
      return;
    }
    var a = items[i++];
    var vid = a.getAttribute('data-view');
    try { a.click(); } catch(e) {}
    setTimeout(function(){
      var v = document.getElementById('view-' + vid);
      var rec = { vid: vid, nav: (a.textContent||'').trim(),
                  on: !!(v && v.classList.contains('on')) };
      if (v) {
        rec.sections = Array.from(v.querySelectorAll('h2, h3'))
          .map(function(h){ return norm(h.textContent); })
          .filter(function(s){ return s; }).slice(0, 40);
        rec.cards = v.querySelectorAll('.card, .xc-card, .pf-panel, .a-fold, .ov-cat-wrap').length;
        rec.kpis = v.querySelectorAll('.ov-k, .pf-row, .kpi, .xc-kpi').length;
        rec.tr = v.querySelectorAll('tr').length;
        rec.svg = v.querySelectorAll('svg').length;
        rec.details = v.querySelectorAll('details').length;
        rec.detailsOpen = v.querySelectorAll('details[open]').length;
        var bg = v.querySelector('.ov-bgrid, .pf-rows, .dist-grid, .v6-row, .xc-cb');
        rec.gridCols = bg ? gridCols(bg) : 0;
        // 卡片高度签名（前 12 个）
        rec.heights = Array.from(v.querySelectorAll('.card, .xc-card, .v6-row > *'))
          .slice(0,12).map(function(c){ return Math.round(c.getBoundingClientRect().height); });
        rec.fonts = fsStat(v);
        rec.text = norm(v.innerText).slice(0, 60000);
      }
      out.views.push(rec);
      step();
    }, VIEW_WAIT);
  }
  step();
})();
</script>
"""


def run_probe(html_path: Path, edge: str) -> dict:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    probe = PROBE % {"wait": VIEW_WAIT_MS}
    tmp = Path(tempfile.mkdtemp(prefix="spec_")) / "probe.html"
    tmp.write_text(html.replace("</body>", probe + "</body>", 1), encoding="utf-8")

    url = "file:///" + str(tmp).replace("\\", "/")
    pr = subprocess.run(
        [edge, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--window-size=1600,1400",
         f"--virtual-time-budget={TOTAL_BUDGET_MS}", "--dump-dom", url],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=600)
    dom = pr.stdout or ""
    m = re.search(r'<script type="application/json" id="__SPEC__">(.*?)</script>', dom, re.S)
    if not m:
        raise SystemExit("提取失败：页面未输出 __SPEC__（可能脚本报错）。\n可先用 --keep 保留临时文件检查。")
    return json.loads(m.group(1))


# ── 校验 ───────────────────────────────────────────────────────
def cmp_view(exp, got, only=None):
    diffs = []
    def d(field, e, g):
        diffs.append({"view": exp["vid"], "field": field, "expect": e, "got": g})

    if only in (None, "layout"):
        for f in ("sections", "cards", "kpis", "tr", "svg", "details",
                  "detailsOpen", "gridCols", "heights"):
            if exp.get(f) != got.get(f):
                d(f, exp.get(f), got.get(f))
    if only in (None, "text"):
        if exp.get("text") != got.get("text"):
            e = (exp.get("text") or "").split("\n")
            g = (got.get("text") or "").split("\n")
            first = next((i for i in range(min(len(e), len(g))) if e[i] != g[i]), None)
            diffs.append({"view": exp["vid"], "field": "text",
                          "expect": f"{len(e)} 行", "got": f"{len(g)} 行",
                          "firstDiffLine": first,
                          "expectLine": (e[first][:160] if first is not None else ""),
                          "gotLine": (g[first][:160] if first is not None else "")})
    if only in (None, "fonts") and exp.get("fonts") != got.get("fonts"):
        d("fonts", exp.get("fonts"), got.get("fonts"))
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--mode", choices=["extract", "verify"], required=True)
    ap.add_argument("--out", help="extract 模式输出 spec 路径")
    ap.add_argument("--spec", help="verify 模式输入的 spec 路径")
    ap.add_argument("--only", choices=["layout", "text", "fonts"], help="只校验某一类")
    ap.add_argument("--edge", default=None)
    ap.add_argument("--max-diff", type=int, default=40, help="最多打印多少条差异")
    args = ap.parse_args()

    edge = args.edge or find_edge()
    html = Path(args.html).resolve()
    if not html.exists():
        raise SystemExit(f"报告不存在: {html}")

    print(f"采集 {html.name} …（{VIEW_WAIT_MS}ms/视图）")
    got = run_probe(html, edge)
    print(f"  视图 {len(got['views'])} 个 ｜ SVG {got['meta']['svgTotal']} 张 ｜ 侧栏 {got['meta']['navCount']} 项")

    if args.mode == "extract":
        out = Path(args.out) if args.out else html.with_suffix(".spec.json")
        out.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 基线已写入 {out}  ({out.stat().st_size:,} B)")
        return

    if not args.spec:
        raise SystemExit("verify 模式必须给 --spec")
    exp = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))

    # meta
    bad = 0
    for f in ("viewCount", "navCount", "navText"):
        if exp["meta"].get(f) != got["meta"].get(f):
            print(f"❌ meta.{f} 期望 {exp['meta'].get(f)} 实得 {got['meta'].get(f)}")
            bad += 1
    # 视图集合
    ev = [x["vid"] for x in exp["views"]]
    gv = [x["vid"] for x in got["views"]]
    if ev != gv:
        print(f"❌ 视图集合不一致\n   期望 {ev}\n   实得 {gv}")
        bad += 1
    gmap = {x["vid"]: x for x in got["views"]}
    all_diffs = []
    for x in exp["views"]:
        g = gmap.get(x["vid"])
        if not g:
            continue
        all_diffs += cmp_view(x, g, args.only)
    if all_diffs:
        bad += len(all_diffs)
        print(f"\n❌ 差异 {len(all_diffs)} 处（显示前 {args.max_diff}）：")
        for d in all_diffs[: args.max_diff]:
            print(f"   [{d['view']}] {d['field']}")
            if "firstDiffLine" in d:
                print(f"      期望行#{d['firstDiffLine']}: {d['expectLine']}")
                print(f"      实得行#{d['firstDiffLine']}: {d['gotLine']}")
            else:
                print(f"      期望: {str(d['expect'])[:200]}")
                print(f"      实得: {str(d['got'])[:200]}")
    else:
        print("✅ 版式 + 文案 + 字号 指纹完全一致")

    if bad:
        print(f"\n合计 {bad} 处不一致 → 未通过")
        sys.exit(1)
    print("\n✅ 复刻验收通过")


if __name__ == "__main__":
    main()
