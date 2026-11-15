# -*- coding: utf-8 -*-
"""分节黄金截图（技能 2.0 · 视觉证据，不进门禁）

用法：
  python shots_single.py --html <产物> --out <目录>
固定 1600×1400（复刻铁律 2）。逐节截图法：展开全部 fold → 隐藏目标节之前的同级节点 → 截图。
"""
import argparse
import os
import subprocess

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
WINDOW = "1600,1400"

NAMES = ["01_项目档案", "02_资产池", "03_分期节奏", "04_现金流分配过程",
         "05_XIRR与XNPV", "06_账户勾稽", "07_核心结论", "08_数据质量与披露"]

PROBE = """
<script>
setTimeout(function(){
  var st=document.createElement('style');
  st.textContent='*,*::before,*::after{transition:none!important;animation:none!important}';
  document.head.appendChild(st);
  document.querySelectorAll('.fold').forEach(function(f){f.classList.remove('collapsed')});
  document.querySelectorAll('.rv').forEach(function(n){n.classList.add('in')});
  var v=document.getElementById('view-p0');
  var kids=[].slice.call(v.children);
  var folds=kids.filter(function(e){return e.classList&&e.classList.contains('fold')});
  var target=folds[%d];
  var seen=false;
  kids.forEach(function(e){
    if(e===target){seen=true;return;}
    if(!seen)e.style.display='none';
  });
  window.scrollTo(0,0);
},1800);
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    edge = next((p for p in EDGE_CANDIDATES if os.path.exists(p)), EDGE_CANDIDATES[0])
    os.makedirs(a.out, exist_ok=True)
    src = open(a.html, encoding="utf-8").read()
    tmp = os.path.join(a.out, "_shot_tmp.html")
    for i, name in enumerate(NAMES):
        open(tmp, "w", encoding="utf-8", newline="").write(src.replace("</body>", PROBE % i + "</body>"))
        png = os.path.join(a.out, f"{name}.png")
        subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                        f"--window-size={WINDOW}", "--virtual-time-budget=15000",
                        f"--screenshot={png}", "file:///" + tmp.replace("\\", "/")],
                       capture_output=True, timeout=300)
        print(f"  {name}.png  {os.path.getsize(png)//1024 if os.path.exists(png) else 0} KB")
    try:
        os.remove(tmp)
    except OSError:
        pass
    print("→", a.out)


if __name__ == "__main__":
    main()
