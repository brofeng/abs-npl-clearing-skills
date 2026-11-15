# -*- coding: utf-8 -*-
r"""v2 组装器（Lead 维护）：把各 section 模块拼成新命名的交付版。

产出：E:\不良ABS穿透研究\清算28单_不良ABS分析\清算28单_不良ABS穿透分析报告_v2.html

组装顺序
  CSS : 基础主题(tooltip/donut/卡片) → 10_overview → 20_profile → 30_compare → 40_audit → 50_charts
  JS  : __V2 数据 → 基础主题 → 10_overview → 20_profile → 30_compare → 40_audit → 50_charts
  视图: 原报告 28 单面板 + #view-xcompare(30) + #view-audit(40)
"""
import importlib.util
import json
import re
import sys
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

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

E = _HOME / "清算28单_不良ABS分析"
V2DIR = E / "脚本" / "v2"
ORIG = _HOME / "清算28单_单项目穿透" / "清算28单_单项目穿透_报告.html"
OUT = E / "清算28单_不良ABS穿透分析报告_v11.html"   # 单一来源见 00_ctx.OUT_NAME

# ══════════════ 基础主题层（沿用已验证的 tooltip / donut 重绘 / 面板质感）══════════════
BASE_CSS = r"""
:root{
  --ease:cubic-bezier(.16,.68,.42,1);
  --grad-soft:linear-gradient(180deg,#fff,#FAFBFE 62%,#F5F8FC);
  --sh-lift:0 2px 4px rgba(16,24,40,.05),0 22px 38px -18px rgba(16,24,40,.22);
}
#xtTip{
  position:fixed;z-index:99999;pointer-events:none;opacity:0;
  transform:translateY(4px) scale(.98);transition:opacity .14s var(--ease), transform .14s var(--ease);
  max-width:360px;padding:9px 12px 10px;border-radius:11px;
  background:rgba(20,26,38,.96);color:#F2F5F9;font-size:12px;line-height:1.6;
  box-shadow:0 10px 30px -6px rgba(16,24,40,.55), 0 0 0 1px rgba(255,255,255,.07);
  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
}
#xtTip.on{opacity:1;transform:translateY(0) scale(1)}
#xtTip .t{font-weight:700;color:#fff;display:block;margin-bottom:3px;font-size:12.5px}
#xtTip .m{color:#C7D0DE;white-space:pre-line}
#xtTip .bar{height:2px;border-radius:2px;background:var(--accent,#2D3955);margin:6px 0 0;opacity:.9}
svg .xt-hit{filter:brightness(1.12)}
.xt-solo{display:flex;align-items:center;gap:10px;padding:14px 16px;border-radius:12px;
  background:var(--grad-soft);border:1px solid var(--line2);font-size:13px;color:var(--ink2,#38425A)}
.xt-solo b{color:var(--ink,#141A26);font-size:15px}
.xt-solo .dot{width:11px;height:11px;border-radius:3px;flex:0 0 auto}
"""

BASE_JS = r"""
/* ===== 全局样式化 tooltip（读最近祖先的 <title>） ===== */
(function(){
  var tip = document.createElement('div');
  tip.id='xtTip'; document.body.appendChild(tip);
  var cur=null, raf=null, mx=0, my=0;
  function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function place(){
    raf=null; var r=tip.getBoundingClientRect();
    var x=mx+16, y=my+14;
    if(x+r.width>window.innerWidth-10) x=mx-r.width-16;
    if(y+r.height>window.innerHeight-10) y=my-r.height-14;
    tip.style.left=Math.max(8,x)+'px'; tip.style.top=Math.max(8,y)+'px';
  }
  function show(el,txt){
    if(cur===el) return; cur=el;
    var p=String(txt).split('｜'), head=p.length>1?p[0]:'', rest=p.length>1?p.slice(1).join('｜'):String(txt);
    tip.innerHTML=(head?'<span class="t">'+esc(head)+'</span>':'')+'<span class="m">'+esc(rest)+'</span><div class="bar"></div>';
    tip.classList.add('on');
    if(el&&el.classList) el.classList.add('xt-hit');
  }
  function hide(){ if(cur&&cur.classList) cur.classList.remove('xt-hit'); cur=null; tip.classList.remove('on'); tip.innerHTML=''; }
  function titled(t){
    var n=0;
    while(t&&t!==document.body&&n<7){
      var tag=t.tagName?t.tagName.toLowerCase():'';
      if(tag&&tag!=='svg'&&tag!=='g'){
        for(var i=0;i<t.children.length;i++){
          var c=t.children[i];
          if(c.tagName&&c.tagName.toLowerCase()==='title') return t;
        }
      }
      t=t.parentNode; n++;
    }
    return null;
  }
  document.addEventListener('mousemove',function(e){
    mx=e.clientX; my=e.clientY;
    var t=e.target, svg=t&&t.closest?t.closest('svg'):null;
    if(!svg){ hide(); return; }
    var el=titled(t);
    if(!el){ if(t===svg){ var tt=svg.querySelector('title'); if(tt){ show(svg,tt.textContent); if(!raf) raf=requestAnimationFrame(place); return; } } hide(); return; }
    var ti=null;
    for(var i=0;i<el.children.length;i++){ var c=el.children[i]; if(c.tagName&&c.tagName.toLowerCase()==='title'){ ti=c; break; } }
    if(!ti){ hide(); return; }
    show(el,ti.textContent);
    if(!raf) raf=requestAnimationFrame(place);
  },{passive:true});
  document.addEventListener('mouseleave',hide);
  window.addEventListener('scroll',hide,{passive:true});
  window.addEventListener('blur',hide);

  /* ===== donut 重绘：解析图例 → 大圆环 + 大字号图例 ===== */
  var S='#1A2230', SUB='#79849A', LINE='rgba(26,34,48,.10)';
  function escH(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function redrawDonut(host){
    var svg=host.querySelector('svg'); if(!svg) return;
    if(svg.dataset.xdraw==='1') return;               // 幂等
    var rects=Array.prototype.slice.call(svg.querySelectorAll('rect')), items=[];
    rects.forEach(function(r){
      var sib=[], n=r.nextElementSibling;
      while(n&&sib.length<2){
        var tg=n.tagName?n.tagName.toLowerCase():'';
        if(tg==='text') sib.push(n.textContent);
        else if(tg==='rect') break;
        n=n.nextElementSibling;
      }
      if(sib.length>=1){
        var m=/([\d.]+)\s*%/.exec(sib[1]||'');
        items.push({fill:r.getAttribute('fill')||'#98A2B3', label:sib[0]||'',
                    pct:m?parseFloat(m[1]):0, val:((sib[1]||'').split('·')[1]||'').trim()});
      }
    });
    if(!items.length) return;
    if(items.length<2){
      var it=items[0];
      host.innerHTML='<div class="xt-solo"><span class="dot" style="background:'+it.fill+'"></span>全部为 <b>'
        +escH(it.label)+'</b>　'+(it.pct||100).toFixed(1)+'%　'+escH(it.val||'')+'</div>';
      return;
    }
    var tot=items.reduce(function(a,b){ return a+(b.pct||0); },0)||1;
    items.forEach(function(it){ it.a=(it.pct||(100/items.length))/tot*100; });
    var ctxt='';
    svg.querySelectorAll('text').forEach(function(t){ if(!ctxt&&/[\d.]+\s*[万亿]/.test(t.textContent)&&t.textContent.length<14) ctxt=t.textContent; });
    var W=560, H=Math.max(230,42+items.length*30);
    var cx=152, cy=H/2, R=Math.min(112,H/2-16), ri=R*0.60, g='', acc=0;
    items.forEach(function(it){
      var a0=-Math.PI/2+acc/100*Math.PI*2, acc2=acc+it.a;
      var a1=-Math.PI/2+acc2/100*Math.PI*2;
      var eps=it.a>99.9?0.001:0, large=(a1-a0)>Math.PI?1:0;
      var x0=cx+R*Math.cos(a0), y0=cy+R*Math.sin(a0);
      var x1=cx+R*Math.cos(a1-eps), y1=cy+R*Math.sin(a1-eps);
      var x2=cx+ri*Math.cos(a1-eps), y2=cy+ri*Math.sin(a1-eps);
      var x3=cx+ri*Math.cos(a0), y3=cy+ri*Math.sin(a0);
      var d='M'+x0.toFixed(1)+' '+y0.toFixed(1)+' A'+R+' '+R+' 0 '+large+' 1 '+x1.toFixed(1)+' '+y1.toFixed(1)
           +' L'+x2.toFixed(1)+' '+y2.toFixed(1)+' A'+ri.toFixed(1)+' '+ri.toFixed(1)+' 0 '+large+' 0 '+x3.toFixed(1)+' '+y3.toFixed(1)+' Z';
      g+='<path class="anr-o" d="'+d+'" fill="'+it.fill+'" stroke="#fff" stroke-width="1.5">'
        +'<title>'+escH(it.label+' · '+it.val+'（'+it.pct.toFixed(1)+'%）')+'</title></path>';
      acc=acc2;
    });
    g+='<text x="'+cx+'" y="'+(cy-2)+'" text-anchor="middle" font-size="11.5" fill="'+SUB+'">合计</text>';
    g+='<text x="'+cx+'" y="'+(cy+18)+'" text-anchor="middle" font-size="15" font-weight="700" fill="'+S+'">'+escH(ctxt)+'</text>';
    var lx=320, ly=26;
    items.forEach(function(it){
      g+='<rect x="'+lx+'" y="'+(ly-10)+'" width="12" height="12" rx="3" fill="'+it.fill+'"/>'
       + '<text x="'+(lx+18)+'" y="'+ly+'" font-size="12.5" fill="'+S+'">'+escH(it.label)+'</text>'
       + '<text x="'+(W-12)+'" y="'+ly+'" text-anchor="end" font-size="12" fill="'+SUB+'">'+it.pct.toFixed(1)+'% · '+escH(it.val)+'</text>'
       + '<line x1="'+lx+'" y1="'+(ly+9)+'" x2="'+(W-12)+'" y2="'+(ly+9)+'" stroke="'+LINE+'"/>';
      ly+=30;
    });
    svg.setAttribute('viewBox','0 0 '+W+' '+H);
    svg.setAttribute('width',W); svg.setAttribute('height',H);
    svg.removeAttribute('preserveAspectRatio');
    svg.innerHTML=g; svg.dataset.xdraw='1';
  }
  document.querySelectorAll('[data-chart="donut"]').forEach(redrawDonut);
  setTimeout(function(){ document.querySelectorAll('[data-chart="donut"]').forEach(redrawDonut); },400);
  window.addEventListener('resize',function(){
    clearTimeout(window.__xdr);
    window.__xdr=setTimeout(function(){
      document.querySelectorAll('[data-chart="donut"] svg').forEach(function(s){ s.dataset.xdraw=''; });
      document.querySelectorAll('[data-chart="donut"]').forEach(redrawDonut);
    },280);
  });

  /* ===== 切视图回到顶部 =====
     原报告 select() 里写的是 document.querySelector('.main').scrollTo(0,0)，
     但 .main{flex:1;...} 并没有 overflow，**不是滚动容器**；而任何元素都有 scrollTo 方法，
     所以这行静默无效 → 切视图时保留上一页的滚动位置（用户反映"进去直接到最底下"）。 */
  function toTop(){
    var de = document.documentElement, prev = de.style.scrollBehavior;
    de.style.scrollBehavior = 'auto';                 // 临时关掉 html{scroll-behavior:smooth}
    window.scrollTo(0, 0);
    if(document.body) document.body.scrollTop = 0;
    ['.main', '.sb-nav', '#root', '.wrap', '.app'].forEach(function(s){
      var e = document.querySelector(s);
      if(e) e.scrollTop = 0;
    });
    requestAnimationFrame(function(){ de.style.scrollBehavior = prev || ''; });
  }
  // 捕获阶段先于原报告 handler 注册；setTimeout 保证在原 handler 之后执行
  document.addEventListener('click', function(e){
    var t = (e.target && e.target.closest) ? e.target.closest('.sb-item, .ov-card') : null;
    if(!t) return;
    setTimeout(toTop, 0);      // 切视图后立刻回顶
    setTimeout(toTop, 220);    // 兜底：异步渲染撑高页面后再纠一次
  }, true);
})();
"""

# ══════════════ 模块加载 ══════════════
SECTIONS = ["10_overview", "20_profile", "30_compare", "40_audit", "50_charts", "60_assets"]


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
    # 兼容：模块把 HTML 放在 build_all()/build_html() 里而没导出常量
    if "HTML" in missing:
        try:
            if hasattr(m, "build_all"):
                r = m.build_all()
                m.HTML = r[1] if isinstance(r, (tuple, list)) and len(r) > 1 else str(r)
            elif hasattr(m, "build_html"):
                m.HTML = m.build_html()
            if hasattr(m, "HTML") and m.HTML:
                missing = [a for a in missing if a != "HTML"]
        except Exception as e:
            return None, f"{name} 的 build_all/build_html 调用失败: {type(e).__name__}: {e}"
    if missing:
        return None, f"{name} 缺属性 {missing}"
    # ── 标签配平校验与自动修复 ──
    # 踩过的坑：30_compare 的 HTML 多一个 </div>，把宿主 .main 提前闭合，
    # 导致后续 section（明细与底稿）掉到 .app 外面、被挤到页面最底部（看似"空白"）。
    div_o = len(re.findall(r"<div\b", m.HTML))
    div_c = len(re.findall(r"</div>", m.HTML))
    fix_note = ""
    if div_o != div_c:
        delta = div_c - div_o          # >0 表示多闭合
        if delta > 0:
            # 从尾部剥掉多余的 </div>（只动结尾连续的）
            for _ in range(delta):
                m.HTML = re.sub(r"</div>\s*$", "", m.HTML, count=1)
            fix_note = f"｜⚠ div 不配平(开{div_o}/闭{div_c})，已从尾部剥除 {delta} 个 </div>"
        else:
            m.HTML = m.HTML + "</div>" * (-delta)
            fix_note = f"｜⚠ div 不配平(开{div_o}/闭{div_c})，已在尾部补 {-delta} 个 </div>"
        div_o2 = len(re.findall(r"<div\b", m.HTML))
        div_c2 = len(re.findall(r"</div>", m.HTML))
        fix_note += f" → 修复后 开{div_o2}/闭{div_c2}"
    return m, f"CSS {len(m.CSS):,} / HTML {len(m.HTML):,} / JS {len(m.JS):,}{fix_note}"


def scope_css(css: str, root: str) -> str:
    """把一段独立 CSS 限定到 root 下。

    注意两个坑（agent-audit 实测踩到）：
      ① CSS 注释里可能含 {} → 先剥离所有注释，否则括号匹配错乱
      ② 选择器若已以 root 开头 → 不能再加前缀，否则变成 #view-x #view-x 而静默失效
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)      # ① 去注释

    def fix(block):
        out, i, n = [], 0, len(block)
        while i < n:
            j = block.find("{", i)
            if j < 0:
                out.append(block[i:]); break
            sel = block[i:j].strip()
            depth, k = 1, j + 1
            while k < n and depth:
                if block[k] == "{": depth += 1
                elif block[k] == "}": depth -= 1
                k += 1
            body = block[j+1:k-1]
            if sel.startswith("@media") or sel.startswith("@supports"):
                out.append(f"{sel}{{{fix(body)}}}")
            elif sel in (":root", "html", "body") or sel == "*":
                out.append(f"{root}{{{body}}}")
            else:
                parts = []
                for s in sel.split(","):
                    s = s.strip()
                    if not s:
                        continue
                    # ② 已含目标根 → 原样保留
                    parts.append(s if root in s else f"{root} {s}")
                if parts:
                    out.append(",".join(parts) + "{" + body + "}")
            i = k
        return "".join(out)
    return fix(css)


print("═" * 74)
print("v2 组装")
print("═" * 74)

mods, report = {}, []
for name in ("10_overview", "20_profile", "50_charts", "60_assets", "70_wording"):
    m, info = load_module(name)
    mods[name] = m
    report.append((name, "✅" if m else "❌", info))
for name in ("30_compare", "40_audit"):
    m, info = load_module(name)
    mods[name] = m
    report.append((name, "✅" if m else "❌", info))

for n, s, i in report:
    print(f"  {s} {n:<14} {i}")

# ══════════════ 组装 ══════════════
ctx_spec = importlib.util.spec_from_file_location("v2_ctx", V2DIR / "00_ctx.py")
ctx = importlib.util.module_from_spec(ctx_spec)
ctx_spec.loader.exec_module(ctx)
V2DATA = json.dumps(ctx.build_v2_data(), ensure_ascii=False, separators=(",", ":"))

css_parts = [BASE_CSS]
js_parts = [f"window.__V2 = {V2DATA};", BASE_JS]
views = []
nav = []

# ── 视图 A：横向对照（30_compare 独占一页）──
m30 = mods.get("30_compare")
if m30:
    css_parts.append(scope_css(m30.CSS, "#view-xcompare"))
    js_parts.append(f"/* ===== 30_compare ===== */\n(function(){{\n{m30.JS}\n}})();")
    views.append('<section class="view" id="view-xcompare">' + m30.HTML + "</section>")
    nav.append('<a class="sb-item" data-view="xcompare">► 横向对照</a>')

# ── 视图 B：明细与底稿（40_audit 的折叠区独立成栏目，v5 新增）──
m40 = mods.get("40_audit")
if m40:
    css_parts.append(scope_css(m40.CSS, "#view-appendix"))
    js_parts.append(f"/* ===== 40_audit ===== */\n(function(){{\n{m40.JS}\n}})();")
    views.append('<section class="view" id="view-appendix">' + m40.HTML + "</section>")
    nav.append('<a class="sb-item" data-view="appendix">► 明细与底稿</a>')

# ── 全局增强模块（70_wording 必须最后跑，文案改写优先级最高）──
for name, key in (("10_overview", "overview"), ("20_profile", "profile"),
                  ("50_charts", "charts"), ("60_assets", "assets"), ("70_wording", "wording")):
    m = mods.get(name)
    if not m:
        continue
    css_parts.append(m.CSS)
    js_parts.append(f"/* ===== {name} ===== */\n(function(){{\n{m.JS}\n}})();")

orig = ORIG.read_text(encoding="utf-8")
ANCHOR = '<a class="sb-item" data-view="overview">◆ 全部项目（28）</a>'
assert ANCHOR in orig, "侧栏锚点未找到"
h = orig.replace(ANCHOR, ANCHOR + "".join(nav), 1)
if views:
    h = h.replace("</main>", "".join(views) + "</main>", 1)
h = h.replace("</head>", "<style>" + "\n".join(css_parts) + "</style></head>", 1)
h = h.replace("</body>", "<script>\n" + "\n".join(js_parts) + "\n</script></body>", 1)

OUT.write_text(h, encoding="utf-8")
print()
print(f"已生成：{OUT.name}  {OUT.stat().st_size:,} B")
print(f"  视图 {h.count('class=\"view\"')} 个（原报告 {orig.count('class=\"view\"')} + 新增 {len(views)}）")
print(f"  CSS {len(''.join(css_parts)):,} 字符   JS {len(''.join(js_parts)):,} 字符")
print(f"  侧栏新增 {len(nav)} 项：{nav}")
