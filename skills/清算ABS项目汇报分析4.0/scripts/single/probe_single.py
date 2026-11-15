# -*- coding: utf-8 -*-
"""单项目报告 · 版式与文案指纹（技能 2.0 · G2 门禁的采集器）

采集口径（**测量前统一置为：所有 .fold 展开 + 禁用过渡动画 + 视口 1600×1400**）：
  每节：标题 / 高度 / 卡片数 / KPI 格数 / 表格数与行数 / SVG 数 / 字号分布 / 渲染后全文
  全页：视图宽 / 侧栏宽 / 页高 / 横向滚动 / 溢出元素 / 零尺寸 SVG / <9.4px 小字

用法：
  python probe_single.py --html <产物.html> --out <spec.json>     # 采集
  python probe_single.py --html <产物.html> --verify <spec.json>   # 比对（G2）
退出码：0 通过；1 有差异。
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
WINDOW_W, WINDOW_H = 1600, 1400

PROBE = r"""
<script>
setTimeout(function(){
  var st=document.createElement('style');
  st.textContent='*,*::before,*::after{transition:none!important;animation:none!important}';
  document.head.appendChild(st);
  document.querySelectorAll('.fold').forEach(function(f){f.classList.remove('collapsed')});
  document.querySelectorAll('.rv').forEach(function(n){n.classList.add('in')});
  function R(e){return e.getBoundingClientRect();}
  var v=document.getElementById('view-p0'), o={};
  o.title=document.title;
  o.viewW=Math.round(R(v).width);
  o.sideW=Math.round(R(document.querySelector('.sidebar')).width);
  o.docH=Math.round(document.documentElement.scrollHeight);
  o.hScroll=document.documentElement.scrollWidth-document.documentElement.clientWidth;
  var over=[];
  [].slice.call(v.querySelectorAll('*')).forEach(function(e){
    if(e.closest&&e.closest('svg'))return;
    var ox=getComputedStyle(e).overflowX;
    if(ox==='auto'||ox==='scroll')return;
    if(e.scrollWidth-e.clientWidth>2) over.push(e.tagName+'.'+((typeof e.className==='string')?e.className:''));
  });
  o.overN=over.length; o.over=over.slice(0,8);
  o.svg=v.querySelectorAll('svg').length;
  o.svgZero=[].slice.call(v.querySelectorAll('svg')).filter(function(s){var r=R(s);return r.width<20||r.height<20;}).length;
  o.svgNoVB=[].slice.call(v.querySelectorAll('svg')).filter(function(s){return !s.getAttribute('viewBox');}).length;
  // 字号分布（非 SVG 文本）
  var small=0,total=0,fs={};
  var tw=document.createTreeWalker(v,NodeFilter.SHOW_TEXT),n;
  while(n=tw.nextNode()){
    if(!n.nodeValue.trim())continue;
    var e2=n.parentElement;if(!e2)continue;
    if(e2.closest&&e2.closest('svg'))continue;
    var s2=getComputedStyle(e2).fontSize;
    fs[s2]=(fs[s2]||0)+1; total++;
    if(parseFloat(s2)<9.4)small++;
  }
  o.small=small;o.textN=total;o.fonts=fs;
  // 逐节
  o.sections=[].slice.call(v.querySelectorAll(':scope > .fold')).map(function(f,i){
    var r=R(f);
    var txt=f.innerText.replace(/[ \t]+/g,' ').replace(/\n{2,}/g,'\n').trim();
    return {
      idx:i,
      id:f.id||('sec'+(i+1)),
      title:(f.querySelector('.ft')||{textContent:''}).textContent.replace(/\s+/g,' ').trim(),
      h:Math.round(r.height),
      cards:f.querySelectorAll('.card').length,
      charts:f.querySelectorAll('.chart').length,
      kpicells:f.querySelectorAll('.pf-c,.pf-row').length,
      tables:f.querySelectorAll('table').length,
      rows:f.querySelectorAll('tbody tr').length,
      svg:f.querySelectorAll('svg').length,
      details:f.querySelectorAll('details,.fold .fold').length,
      text:txt
    };
  });
  o.peerDots=v.querySelectorAll('[data-chart="peer-strip"] circle').length;
  o.navItems=document.querySelectorAll('.sb-item').length;
  o.sideTitle=(document.querySelector('.sb-title')||{textContent:''}).textContent.trim();
  o.sideSub=(document.querySelector('.sb-sub')||{textContent:''}).textContent.trim();
  o.crumb=(document.getElementById('crumb')||{textContent:''}).textContent.replace(/\s+/g,' ').trim();
  document.title='P:'+btoa(unescape(encodeURIComponent(JSON.stringify(o))));
},2200);
</script>
"""


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 Edge 无头浏览器，请安装 Microsoft Edge 或改 EDGE_CANDIDATES")


def collect(html):
    edge = find_edge()
    src = open(html, encoding="utf-8").read()
    tmp = os.path.join(os.path.dirname(os.path.abspath(html)), "_probe_%s.html"
                       % os.path.basename(html).split(".")[0][-8:])
    open(tmp, "w", encoding="utf-8", newline="").write(src.replace("</body>", PROBE + "</body>"))
    cp = subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                         f"--window-size={WINDOW_W},{WINDOW_H}", "--virtual-time-budget=15000",
                         "--dump-dom", "file:///" + tmp.replace("\\", "/")],
                        capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=300)
    try:
        os.remove(tmp)
    except OSError:
        pass
    m = re.search(r"P:([A-Za-z0-9+/=]{200,})", cp.stdout or "")
    if not m:
        raise SystemExit("探针失败：未取到结果。" + (cp.stdout or cp.stderr or "")[:400])
    return json.loads(base64.b64decode(m.group(1)).decode("utf-8"))


def diff_text(want, got, max_show=3):
    """逐行 diff，返回首个差异位置"""
    a = [x for x in want.split("\n") if x.strip()]
    b = [x for x in got.split("\n") if x.strip()]
    out = []
    for i in range(max(len(a), len(b))):
        ea = a[i] if i < len(a) else "<缺行>"
        eb = b[i] if i < len(b) else "<缺行>"
        if ea != eb:
            out.append((i + 1, ea[:90], eb[:90]))
            if len(out) >= max_show:
                break
    return out


def verify(spec_path, got):
    spec = json.load(open(spec_path, encoding="utf-8"))
    fails, res = [], []

    def chk(cat, desc, ok, detail=""):
        res.append((cat, desc, ok, detail))
        if not ok:
            fails.append((cat, desc, detail))

    # 页面级
    chk("页面", "视图宽", abs(got["viewW"] - spec["viewW"]) <= 2, f'{got["viewW"]} vs {spec["viewW"]}')
    chk("页面", "侧栏宽", abs(got["sideW"] - spec["sideW"]) <= 2, f'{got["sideW"]} vs {spec["sideW"]}')
    chk("页面", "页高（±12px）", abs(got["docH"] - spec["docH"]) <= 12, f'{got["docH"]} vs {spec["docH"]}')
    chk("页面", "无整页横向滚动", got["hScroll"] <= 0, got["hScroll"])
    chk("页面", "无元素横向溢出", got["overN"] == 0, got["over"])
    chk("页面", "SVG 数", got["svg"] == spec["svg"], f'{got["svg"]} vs {spec["svg"]}')
    chk("页面", "无零尺寸 SVG", got["svgZero"] == 0, got["svgZero"])
    chk("页面", "无缺 viewBox 的 SVG", got["svgNoVB"] == 0, got["svgNoVB"])
    chk("页面", "无 <9.4px 小字", got["small"] == 0, f'{got["small"]}/{got["textN"]}')
    chk("页面", "字号分布一致", got["fonts"] == spec["fonts"],
        f'实际 {got["fonts"]} vs 基线 {spec["fonts"]}')
    chk("页面", "侧栏条目数", got["navItems"] == spec["navItems"], f'{got["navItems"]} vs {spec["navItems"]}')
    chk("页面", "侧栏标题", got.get("sideTitle") == spec.get("sideTitle"),
        f'{got.get("sideTitle")} vs {spec.get("sideTitle")}')
    chk("页面", "侧栏副标题", got.get("sideSub") == spec.get("sideSub"),
        f'{got.get("sideSub")} vs {spec.get("sideSub")}')
    chk("页面", "面包屑", got.get("crumb") == spec.get("crumb"),
        f'{got.get("crumb")} vs {spec.get("crumb")}')
    chk("页面", "同业分位圆点数", got["peerDots"] == spec["peerDots"],
        f'{got["peerDots"]} vs {spec["peerDots"]}')

    # 逐节
    chk("节数", "顶层节数 = 8", len(got["sections"]) == len(spec["sections"]),
        f'{len(got["sections"])} vs {len(spec["sections"])}')
    for ws, gs in zip(spec["sections"], got["sections"]):
        tag = ws["title"][:12]
        chk("节标题", f'{ws["id"]} 标题', gs["title"] == ws["title"], f'{gs["title"]} vs {ws["title"]}')
        chk("节高度", f'{tag}（±3px）', abs(gs["h"] - ws["h"]) <= 3, f'{gs["h"]} vs {ws["h"]}')
        for k, label in (("cards", "卡片"), ("charts", "图块"), ("kpicells", "KPI 格"),
                         ("tables", "表格"), ("rows", "表行"), ("svg", "SVG"), ("details", "明细块")):
            chk("节结构", f'{tag} {label}数', gs[k] == ws[k], f'{gs[k]} vs {ws[k]}')
        d = diff_text(ws["text"], gs["text"])
        chk("节文案", f'{tag} 渲染后全文逐行一致', not d,
            "; ".join(f'行{a}: 期望「{x}」实得「{y}」' for a, x, y in d) if d else "")

    print(f'{"="*68}\nG2 版式+文案指纹：{len(res)} 项，PASS {len(res)-len(fails)}，FAIL {len(fails)}\n{"="*68}')
    for cat, desc, det in fails:
        print(f'  ✗ [{cat}] {desc}　{det}')
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--out")
    ap.add_argument("--verify")
    a = ap.parse_args()
    got = collect(a.html)
    if a.verify:
        ok = verify(a.verify, got)
        sys.exit(0 if ok else 1)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump(got, open(a.out, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)
        print(f'✓ 指纹已写入 {a.out}')
        print(f'  节数 {len(got["sections"])} ｜ SVG {got["svg"]} ｜ 页高 {got["docH"]} ｜ '
              f'字号分布 {got["fonts"]}')
    else:
        print(json.dumps({k: v for k, v in got.items() if k != "sections"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
