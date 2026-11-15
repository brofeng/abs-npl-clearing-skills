#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_skeleton.py —— 组装器骨架（可直接跑，按需改 MODULES / OUT）

核心三件事，每一件都是踩坑换来的：
  ① scope_css：把模块 CSS 限定到某个视图根下（三个坑已处理）
  ② 标签配平校验与自动修复：模块 HTML 多一个 </div> 会把宿主 .main 提前闭合，
     导致后续 section 掉到 .app 外、被挤到页面最底部（表现为「空白视图」）
  ③ 视图装配 + 侧栏注入 + toTop 滚动修复

用法：
    <python> build_skeleton.py
"""
import importlib.util
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ══════════════ 配置（按项目改）══════════════
E = Path(r"E:\不良ABS穿透研究\清算28单_不良ABS分析")
V2DIR = E / "脚本" / "v2"
ORIG = Path(r"E:\不良ABS穿透研究\清算28单_单项目穿透\清算28单_单项目穿透_报告.html")
OUT = E / "清算28单_不良ABS穿透分析报告_vN.html"

# 全局增强模块（按顺序注入；70_wording 必须最后，文案改写优先级最高）
GLOBAL_MODULES = ["10_overview", "20_profile", "50_charts", "60_assets", "70_wording"]
# 独立视图模块：(模块名, 视图 id, 侧栏文字)
VIEW_MODULES = [
    ("30_compare", "view-xcompare", "► 横向对照"),
    ("40_audit",   "view-appendix", "► 明细与底稿"),
]


# ══════════════ ① scope_css ══════════════
def scope_css(css: str, root: str) -> str:
    """把一段独立 CSS 限定到 root 下。

    三个坑（都踩过）：
      ⓐ CSS 注释里可能含 {} → 先剥离所有注释，否则括号匹配错乱
      ⓑ 选择器已含 root → 原样保留，不要重复前缀（否则 #root #root .x 永远不命中）
      ⓒ :root / html / body / * → 映射为 root 本身
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)          # ⓐ

    def fix(block: str) -> str:
        out, i = [], 0
        while i < len(block):
            j = block.find("{", i)
            if j < 0:
                break
            sel = block[i:j].strip()
            depth, k = 1, j + 1
            while k < len(block) and depth:
                if block[k] == "{":
                    depth += 1
                elif block[k] == "}":
                    depth -= 1
                k += 1
            body = block[j + 1:k - 1]
            if sel.startswith("@media") or sel.startswith("@supports"):
                out.append(f"{sel}{{{fix(body)}}}")
            elif sel in (":root", "html", "body", "*"):
                out.append(f"{root}{{{body}}}")
            else:
                parts = []
                for s in sel.split(","):
                    s = s.strip()
                    if not s:
                        continue
                    parts.append(s if root in s else f"{root} {s}")   # ⓑ
                if parts:
                    out.append(",".join(parts) + "{" + body + "}")
            i = k
        return "".join(out)

    return fix(css)


# ══════════════ ② 标签配平校验与自动修复 ══════════════
def balance_html(html: str, name: str = "") -> str:
    """修复 div 不配平。多闭合从尾部剥；少闭合在尾部补。"""
    o, c = len(re.findall(r"<div\b", html)), len(re.findall(r"</div>", html))
    if o == c:
        return html
    delta = c - o
    if delta > 0:
        for _ in range(delta):
            html = re.sub(r"</div>\s*$", "", html, count=1)
        note = f"⚠ {name} div 不配平(开{o}/闭{c})，已从尾部剥除 {delta} 个 </div>"
    else:
        html += "</div>" * (-delta)
        note = f"⚠ {name} div 不配平(开{o}/闭{c})，已在尾部补 {-delta} 个 </div>"
    print("  " + note, "→ 修复后",
          len(re.findall(r"<div\b", html)), "/", len(re.findall(r"</div>", html)))
    return html


# ══════════════ 模块加载 ══════════════
def load_module(name):
    p = V2DIR / f"{name}.py"
    if not p.exists():
        return None, f"缺失 {name}.py"
    spec = importlib.util.spec_from_file_location(f"v2_{name}", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return None, f"加载失败 {name}: {type(e).__name__}: {e}"
    missing = [a for a in ("CSS", "HTML", "JS") if not hasattr(m, a)]
    if "HTML" in missing:                     # 兼容 build_all()/build_html()
        try:
            if hasattr(m, "build_all"):
                r = m.build_all()
                m.HTML = r[1] if isinstance(r, (tuple, list)) and len(r) > 1 else str(r)
            elif hasattr(m, "build_html"):
                m.HTML = m.build_html()
            if getattr(m, "HTML", ""):
                missing = [a for a in missing if a != "HTML"]
        except Exception as e:
            return None, f"{name}.build_all 失败: {e}"
    if missing:
        return None, f"{name} 缺属性 {missing}"
    m.HTML = balance_html(m.HTML, name)        # ②
    return m, f"CSS {len(m.CSS):,} / HTML {len(m.HTML):,} / JS {len(m.JS):,}"


# ══════════════ ③ toTop 滚动修复 ══════════════
# 原报告写 document.querySelector('.main').scrollTo(0,0) —— 但 .main{flex:1}
# 没有 overflow，不是滚动容器；任何元素都有 scrollTo 方法，所以这行**静默无效**
# → 切视图时保留上一页的滚动位置（用户反映「进去直接到最底下」）
TOPO_JS = r"""
  function toTop(){
    var de = document.documentElement, prev = de.style.scrollBehavior;
    de.style.scrollBehavior = 'auto';
    window.scrollTo(0, 0);
    if(document.body) document.body.scrollTop = 0;
    ['.main', '.sb-nav', '#root', '.wrap', '.app'].forEach(function(s){
      var e = document.querySelector(s); if(e) e.scrollTop = 0;
    });
    requestAnimationFrame(function(){ de.style.scrollBehavior = prev || ''; });
  }
  document.addEventListener('click', function(e){
    var t = (e.target && e.target.closest) ? e.target.closest('.sb-item, .ov-card') : null;
    if(!t) return;
    setTimeout(toTop, 0);
  }, true);
"""


def main():
    print("═" * 74)
    print("组装")
    print("═" * 74)

    mods, report = {}, []
    for name in GLOBAL_MODULES + [m[0] for m in VIEW_MODULES]:
        m, info = load_module(name)
        mods[name] = m
        report.append((name, "✅" if m else "❌", info))
    for n, s, i in report:
        print(f"  {s} {n:<14} {i}")

    # 数据契约（00_ctx 提供 __V2）
    import json
    spec = importlib.util.spec_from_file_location("v2_ctx", V2DIR / "00_ctx.py")
    ctx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctx)
    V2DATA = json.dumps(ctx.build_v2_data(), ensure_ascii=False, separators=(",", ":"))

    css_parts, js_parts, views, nav = [], [f"window.__V2 = {V2DATA};", TOPO_JS], [], []

    # 独立视图
    for name, vid, label in VIEW_MODULES:
        m = mods.get(name)
        if not m:
            continue
        css_parts.append(scope_css(m.CSS, f"#{vid}"))
        js_parts.append(f"/* ===== {name} ===== */\n(function(){{\n{m.JS}\n}})();")
        views.append(f'<section class="view" id="{vid}">' + m.HTML + "</section>")
        nav.append(f'<a class="sb-item" data-view="{vid.replace("view-","")}">{label}</a>')

    # 全局增强模块
    for name in GLOBAL_MODULES:
        m = mods.get(name)
        if not m:
            continue
        css_parts.append(m.CSS)
        js_parts.append(f"/* ===== {name} ===== */\n(function(){{\n{m.JS}\n}})();")

    # 装配
    orig = ORIG.read_text(encoding="utf-8")
    ANCHOR = '<a class="sb-item" data-view="overview">◆ 全部项目（28）</a>'
    assert ANCHOR in orig, "侧栏锚点未找到，请改 ANCHOR"
    h = orig.replace(ANCHOR, ANCHOR + "".join(nav), 1)
    if views:
        h = h.replace("</main>", "".join(views) + "</main>", 1)
    h = h.replace("</head>", "<style>" + "\n".join(css_parts) + "</style></head>", 1)
    h = h.replace("</body>", "<script>\n" + "\n".join(js_parts) + "\n</script></body>", 1)

    OUT.write_text(h, encoding="utf-8")
    print(f"\n已生成：{OUT.name}  {OUT.stat().st_size:,} B")
    n_view = h.count('class="view"')
    n_orig = orig.count('class="view"')
    print(f"  视图 {n_view} 个（原 {n_orig} + 新增 {len(views)}）")
    print(f"  CSS {len(''.join(css_parts)):,} 字符  JS {len(''.join(js_parts)):,} 字符")
    print(f"  侧栏新增 {len(nav)} 项：{nav}")


if __name__ == "__main__":
    main()
