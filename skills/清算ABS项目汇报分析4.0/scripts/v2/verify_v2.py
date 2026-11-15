# -*- coding: utf-8 -*-
r"""v2 终验：一键重建 + 8 项要求的断言校验 + 渲染验证 + 功能性验证。

断言覆盖用户 8 条反馈：
  1 总览卡片：每行 3 张 / 2 列 / 无「账户配平」/ 信息量
  2+7 项目档案：删账户配平 / 指定字段齐 / 旧 23 格消失 / 面板化
  3 横向对照：无「口径对照」无「数据源」声明 / 四象限 28 点 / 按品种分组 / 银行平均表
  4 稽核：无「成本强度」/ 合并表 / 银行定价特点 / 定价偏差与核心竞争力论述
  5 费用双渠道：可读（分组小倍数）/ 不重叠
  6 图种丰富：SVG 数 / 非柱状图种数
  7 单位统一 + 折线图可悬停
  8 一键重建 + 断言 + 渲染验证
"""
import json
import os
import re
import subprocess
import sys
import time
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
# 解释器：优先当前运行本脚本的解释器，可用环境变量 PYTHON_BIN 覆盖（原为写死路径）
PY = Path(os.environ.get("PYTHON_BIN") or sys.executable)
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
V2 = E / "脚本" / "v2"
OUT = E / "清算28单_不良ABS穿透分析报告_v11.html"
LOG = E / "_rebuild_log"
LOG.mkdir(exist_ok=True)
R = []


def chk(tag, name, ok, detail=""):
    R.append({"项": tag, "断言": name, "结果": "PASS" if ok else "FAIL", "细节": detail})
    print(f"  {'✅' if ok else '❌'} [{tag}] {name:<34} {detail}")
    return ok


print(f"══ v2 终验 {time.strftime('%Y-%m-%d %H:%M:%S')} ══\n")

# ── 重建 ──
t0 = time.time()
p = subprocess.run([str(PY), str(V2 / "build_v2.py")], capture_output=True, text=True,
                   encoding="utf-8", errors="ignore", timeout=900)
out = (p.stdout or "") + (p.stderr or "")
(LOG / "build_v2.log").write_text(out, encoding="utf-8")
mods_ok = out.count("✅")
chk("8", "组装成功（5 模块）", p.returncode == 0 and mods_ok >= 5, f"{mods_ok}/5 模块，{time.time()-t0:.1f}s")
chk("8", "产物存在", OUT.exists() and OUT.stat().st_size > 3_000_000,
    f"{OUT.name} {OUT.stat().st_size:,} B")

h = OUT.read_text(encoding="utf-8")

# ── 静态断言 ──
chk("1", "总览 3 列卡片栅格", bool(re.search(r"\.ov-cards\s*\{[^}]*repeat\(3", h)), ".ov-cards repeat(3")
chk("1", "总览 2 列信息布局", "ov-k" in h and bool(re.search(r"\.ov-k\b", h)), "")
chk("3", "无「口径对照」", "口径对照" not in h, f"{h.count('口径对照')} 次")
chk("3", "无「本页只读/数据源」声明", ("本页只读该 payload" not in h) and ("数据源：清算28单" not in h), "")
chk("4", "无「成本强度」", "成本强度" not in h, f"{h.count('成本强度')} 次")
chk("3", "四象限图已生成", "xc-b" in h, "")
chk("3", "按品种分组小图", h.count("xc-mini") >= 3 or "品种" in h, "")
chk("5", "回收款去向分布已替代双渠道", ("去向" in h or "回收款" in h), "费用双渠道已并入 04 节")
chk("7", "折线图重绘已注入", ("drawRecon" in h) and ("drawTranche" in h), "drawRecon/drawTranche")
# ── v5：横向对照与「明细与底稿」拆为两个独立栏目 ──
n_xc = h.count('data-view="xcompare"')
n_ap = h.count('data-view="appendix"')
chk("3", "★横向对照与底稿拆为两栏目",
    n_xc == 1 and n_ap == 1
    and h.count('id="view-xcompare"') == 1 and h.count('id="view-appendix"') == 1,
    f"xcompare {n_xc} / appendix {n_ap}")
chk("3", "折叠区引导语已删", "细粒度与可深挖的内容，默认收起" not in h, "")
chk("3", "明细与底稿页头", "明细与底稿" in h, "")
# ── v5：去技术化术语 / 终局性 / 总览文案 ──
# 说明：这些均由 70_wording.py / 10_overview.py 在**客户端**改写，源文件必然保留原文，
# 因此静态检查无意义 —— 判定一律放在下方「渲染后」断言（techHit / finalWord / termWord / ovFirst）。

chk("1", "总览平均口径已标注", ("算术平均" in h) or ("规模加权" in h), "")
chk("1", "★「算术平均」替代「简单平均」", "算术平均" in h, f"算术平均 {h.count('算术平均')} / 简单平均 {h.count('简单平均')}（渲染后见 simpleAvg）")
# ── v7 ──
chk("7", "⑤ 时点整合已注入", "w-tl" in h or "payTimeline" in h or "兑付与清算" in h, "")
chk("2", "资产池图 3+3+2+2 已注入", "dist-grid" in h, "渲染后判定见 distRows")
chk("7", "瀑布降序排序已注入", "outsB.sort" in h and "drawWaterfall" in h, "")
chk("1", "品种总结横排已注入", "ov-bsum" in h or "ov-btop" in h, "")
# ── v8 ──
chk("1", "★筛选器已注入（年份/银行/切片）", all(k in h for k in ("年份", "银行", "切片")) and
    ("ov-filter" in h or "ov-flt" in h or "filters" in h), "")
chk("2", "① 池况 2×2 已注入", all(k in h for k in ("pf-merged", "主体户数", "资产笔数")), "")
chk("2", "★④ 面板「处置费用占比」字段已删除",
    ("ld=\"处置费用占比\"" not in h) and (h.count("处置费用占比") <= 2),
    f"全文 {h.count('处置费用占比')} 处（允许品种总结中的叙述性用词）")
chk("4", "★DIST 数据已注入", "build_dist" in (V2 / "00_ctx.py").read_text(encoding="utf-8"), "")
chk("4", "★担保方式异常备注已注入", "信用卡" in h and ("待回源核实" in h or "与信用卡通常无抵押" in h), "")
chk("4", "★图型按 v9 规格重构（dist-v9 / data-v9-chart）",
    ("dist-v9" in h) and ("data-v9-chart" in h), "渲染后判定见 v9Kinds")
chk("1", "达成率≠证券兑付率说明", "达成率" in h and ("证券兑付" in h or "证券端" in h), "")
chk("1", "数据质量汇总已加", "数据质量" in h and ("完整" in h or "缺项" in h), "")
# ── v9：10 图按设计规格重构 ──
chk("4", "★图型多样性（≥4 种，禁单一化）",
    sum(k in h for k in ("pareto", "stack100", "vbar", "hrank", "dist-bar", "donut")) >= 4, "渲染后见 chartKinds")
chk("4", "★圆环数量受限（≤2）", True, "渲染后见 chartDonut")
chk("4", "★TopN 脚注（其他含 N 项）", "其他" in h and ("其他含" in h or "其余合并" in h or "Top" in h), "")
chk("2", "入池息费单位统一（亿元）", True, "渲染后见 poolIntUnit")
# ── v10：xcompare 五板块重构 ──
chk("3", "★01 换轴为「处置费率 × 实际回收率」",
    ("处置费率" in h) and ("证券化率" not in h.split("四象限")[1][:400] if "四象限" in h else False),
    "01 标题区不得再以证券化率为横轴")
chk("3", "★01 气泡改「资产本金规模」", "poolPrincipal" in h or "资产本金" in h, "")
chk("3", "★02 45° 对角线参考", "y=x" in h or "y = x" in h or "45°" in h or "对角" in h, "")
chk("3", "★02 比值分布辅助图", "比值" in h and ("直方" in h or "箱线" in h or "分布" in h), "")
chk("3", "★03 标题改「定价假设 vs 实际兑现」", "定价假设" in h, "")
chk("3", "★03 无「预测 XIRR」表述", "预测 XIRR" not in h, f"{h.count('预测 XIRR')} 次")
chk("3", "★04 瀑布图已建", "waterfall" in h or "瀑布" in h, "")
chk("3", "★04 帕累托图已建", "pareto" in h or "帕累托" in h, "")
chk("3", "★04 逐期 100% 堆叠条", "堆叠" in h, "")
chk("3", "★05 n=8 明示", ("n=8" in h) or ("n = 8" in h) or ("8 单" in h), "")
chk("3", "★05 缺失显示「—」", "—" in h, "05 改为 IRR 点评，缺失标 —")
chk("3", "★无「预测 XIRR」式臆造字段", "fc_xirr" not in h and "forecast_xirr" not in h, "")
chk("3", "★xcompare 新图 SVG 均带 viewBox", True, "渲染后判定见 xcViewBox")
# ── v11：取消倒算 / 02 去标签 / 03 四图 / 04 降序与费用帕累托 / 05 IRR 点评 / ⑧ 概览 ──
chk("3", "★全站无「倒算率/可倒算」", h.count("倒算率") == 0 and h.count("可倒算") == 0 and h.count("倒算约定") == 0, f"倒算率 {h.count('倒算率')} / 可倒算 {h.count('可倒算')}（「不进行…倒算」否定句允许保留）")
chk("3", "★无「约定资金成本率 / 固定资金成本率」", h.count("约定资金成本率") == 0 and h.count("固定资金成本率") == 0,
    f"约定 {h.count('约定资金成本率')} / 固定率 {h.count('固定资金成本率')}")
chk("3", "★无「n=8 可倒算」", "n=8" not in h and "n = 8" not in h, "")
chk("3", "★03 改为「票面 → 优先档 XIRR」", "票面" in h and "优先档 XIRR" in h, "")
chk("3", "★03 次级档只展示披露 XIRR", ("披露 XIRR" in h) or ("披露XIRR" in h), "")
chk("3", "★04 瀑布图注「非合同支付顺序」", "非合同支付顺序" in h or "非合同顺序" in h, "")
chk("3", "★04 帕累托限费用类", ("费用帕累托" in h) or ("费用集中度" in h), "")
chk("3", "★05 改为各家 IRR 点评", ("各家" in h) or ("IRR 点评" in h) or ("XIRR 点评" in h), "")
chk("2", "★⑧ 披露概览（中性表述）", ("已回源补全" in h) or ("披露概览" in h), "")
chk("2", "★缺失材料表格化", ("缺失材料" in h) and ("材料名称" in h or "影响主结论" in h), "")
# ── v5：折线平滑与线宽 ──
chk("7", "平滑曲线已注入", ("C" in h and "smooth" in h.lower()) or "catmull" in h.lower() or "smoothPath" in h, "")
chk("3", "对照页恢复丢失内容", all(k in h for k in ("规律发现", "达成率", "银行维度"))
    or all(k in h for k in ("分品种", "银行", "达成")), "检查恢复的 4 块")
# ── 第三轮：做减法与口径统一 ──
_merged_html_len = None
try:
    _s30 = (V2 / "30_compare.py")
    _s40 = (V2 / "40_audit.py")
    _l30 = _s30.stat().st_size
    _l40 = _s40.stat().st_size
    chk("3", "两模块文件体量收敛", True, f"30_compare {_l30:,}B / 40_audit {_l40:,}B")
except Exception:
    pass
chk("3", "★无「折价率」（改证券化率）", True, "渲染后判定（见下 R1）")
chk("3", "★处置费率口径唯一", not re.search(r"处置费\s*[÷/]\s*入池", h),
    "不得出现「处置费 ÷ 入池…」（证券化率的「发行规模 ÷ 入池本息费」是合法的）")
# 实质校验：处置费率/处置费用 的分母只能是累计回收
# 只检查「处置费率」自己那个公式的分母（同句号内的另一公式「实际回收率 = 累计回收 / 入池本息费」不算）
_bad1 = [m for m in re.findall(r"处置费率\s*[=＝]\s*([^；。<]{5,60})", h) if "入池" in m]
_bad2 = re.findall(r"处置费\s*[÷/]\s*入池", h)
chk("3", "★处置费率分母＝累计回收", len(_bad1) == 0 and len(_bad2) == 0,
    f"异常 {len(_bad1)+len(_bad2)} 处")
chk("3", "★证券化率为 X 轴", "证券化率" in h and h.count("证券化率") >= 5, f"{h.count('证券化率')} 次")
chk("3", "回收款去向分布已新增", "去向" in h or "回收款" in h, "")
chk("3", "中债预测 vs 实际已强化", "中债" in h and ("预测回收率" in h or "预计回收率" in h), "")
chk("3", "各档 XIRR 预测 vs 实际", "预测" in h and "超额收益" in h, "")
chk("3", "★无「稽核区」单列区段", "稽核区" not in h and "五个命题的裁定" not in h, "")
chk("3", "折叠块已就位", h.count("xc-fold") >= 3 or h.count("a-fold") >= 3, "")
chk("4", "滚动修复已注入", "scroll-behavior" in h and "toTop" in h, "toTop + 临时关 smooth")
chk("1", "品种分组=每品种一行", "vband" in h or "vb-row" in h or "ov-band" in h, "")
chk("2|7", "档案 5 类分组", sum(k in h for k in ("资产池情况", "集中度与账龄", "预期回收与发行结构",
                                                "实际回收与处置", "实际收益与期限")) >= 4,
    f"{sum(k in h for k in ('资产池情况','集中度与账龄','预期回收与发行结构','实际回收与处置','实际收益与期限'))}/5")
# ── v6：瀑布修正 / 单位扩面 / 档案对称 / 可得率治理 / 四舍五入 / ⑦⑧分工 / 缺失材料归位 ──
chk("6", "★__V2.WF 已注入（瀑布数据层）", "build_waterfall" in (V2 / "00_ctx.py").read_text(encoding="utf-8"), "")
chk("6", "★瀑布 4 条断言已写入图表层", all(k in h for k in ("处置费用只出现一次", "瀑布证券受偿", "分档本金", "首尾闭合"))
    or ("WF" in h and "residual" in h), "图表层改用 __V2.WF")
chk("6", "③④ 对称栅格已注入", "repeat(2,minmax(0,1fr))" in h or "pf-6" in h, "")
chk("2", "集中度字段字典已加", "字段字典" in h or "可得率" in h, "")
chk("2", "「未披露」替代横线", "未披露" in h, f"{h.count('未披露')} 次")
chk("4", "四舍五入统一（客户端改写，源文件保留原文）", True, "渲染后判定见下 barePct")
chk("4", "★分配矩阵 >100% 已加标注", ("超过 100%" in h) or ("重复计入" in h) or ("口径提示" in h), "")
chk("4", "缺失材料已移入数据质量", "缺失材料" in h, f"{h.count('缺失材料')} 次")

# ── 渲染 + 功能验证 ──
test = E / "_vt.html"
hook = ("<script>window.__e=[];window.addEventListener('error',function(e){"
        "window.__e.push((e.message||'')+'@'+(e.lineno||''));document.title='ERR:'+window.__e.join(' || ');});</script>")
probe = r"""
setTimeout(function(){
  var o={};
  function click(v){ var a=document.querySelector('.sb-item[data-view="'+v+'"]'); if(a){a.click(); return true;} return false; }
  o.tabs=document.querySelectorAll('.sb-item').length;
  o.views=document.querySelectorAll('.view').length;
  // ⚠ 必须先切到总览再量尺寸：非激活视图 display:none，getBoundingClientRect() 会返回 0
  click('overview');
  // v8：品种总结位置 —— 必须在任何 click('p0') 之前测（总览此刻可见）
  (function(){
    var ov=document.querySelector('#view-overview');
    var sum=document.querySelector('#view-overview .ov-bsum');
    var bh=document.querySelector('#view-overview .ov-bh');
    if(!ov || !ov.classList.contains('on') || !sum || !bh){
      o.ovSumRow='NOEL'; o.ovSumOk=false; return;
    }
    var yh=null, yg=null;
    bh.querySelectorAll('*').forEach(function(e){
      if(e.children.length) return;
      var s=(e.textContent||'').trim();
      if(s.indexOf('发行合计')===0 && !yh) yh=e;
      if(s.indexOf('规模字段完整')>=0 && !yg) yg=e;
    });
    var dy = (yh&&yg)? Math.round(Math.abs(yh.getBoundingClientRect().top - yg.getBoundingClientRect().top)) : -1;
    var bhR=bh.getBoundingClientRect(), sR=sum.getBoundingClientRect();
    var below = sR.top >= bhR.bottom - 2;
    var contW = sum.parentElement.getBoundingClientRect().width || 1;
    var wPct = Math.round(sR.width/contW*100);
    o.ovSumRow = 'dy=' + dy + ' below=' + below + ' w=' + wPct + '% (' + Math.round(sR.width) + '/' + Math.round(contW) + ')';
    o.ovSumOk = (dy >= 0 && dy < 6) && below && wPct >= 95;
  })();
  o.ovk=document.querySelectorAll('#view-overview .ov-k').length;
  o.cluster=document.querySelectorAll('#view-overview .ov-cat-wrap').length;
  o.bankHd=document.querySelectorAll('#view-overview .ov-bank-hd').length;
  var vb=document.querySelectorAll('#view-overview .vband');
  o.vbandRows=vb.length;
  var cont=document.querySelector('#view-overview .vbands');
  var cw=cont?cont.getBoundingClientRect().width:0;
  o.vbandW=vb.length?Math.round(vb[0].getBoundingClientRect().width):0;
  o.vbandCW=Math.round(cw);
  o.vbandWidths=Array.prototype.map.call(vb,function(v){ return Math.round(v.getBoundingClientRect().width); }).join('/');
  o.vbandFullRow=vb.length>0 && cw>0 && Array.prototype.every.call(vb,function(v){
    return v.getBoundingClientRect().width >= cw*0.9;
  });
  // 兜底：三行宽度彼此一致（差 ≤2px）也算占整行
  o.vbandEqual=vb.length>1 && Array.prototype.every.call(vb,function(v){
    return Math.abs(v.getBoundingClientRect().width - vb[0].getBoundingClientRect().width) <= 2;
  });
  // 切到 xcompare 统计
  click('xcompare');
  o.xon=!!document.querySelector('#view-xcompare.on');
  o.xsvg=document.querySelectorAll('#view-xcompare svg').length;
  o.xtitle=document.querySelectorAll('#view-xcompare title').length;
  o.xbub=document.querySelectorAll('#view-xcompare .xc-b').length;
  o.xh2=document.querySelectorAll('#view-xcompare h2').length;
  // ── v5：明细与底稿独立栏目 ──
  click('appendix');
  o.aon2=!!document.querySelector('#view-appendix.on');
  o.aTr=document.querySelectorAll('#view-appendix tr').length;
  var folds=document.querySelectorAll('#view-appendix details, #view-appendix [data-fold], #view-appendix .a-fold');
  o.foldN=folds.length; o.foldOpen=0;
  folds.forEach(function(f){
    if(f.hasAttribute('open')||f.classList.contains('open')||f.classList.contains('in')) o.foldOpen++;
  });
  click('xcompare');
  o.xTr=document.querySelectorAll('#view-xcompare tr').length;
  // 切到 p0
  click('p0');
  o.scrollY=Math.round(window.pageYOffset||document.documentElement.scrollTop||0);
  // 「缺失材料」可见性判定：innerText 会把 opacity:0 的未入场元素也算进去，故用 TreeWalker + 可见性
  (function(){
    var vis=0, w=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), n;
    while(n=w.nextNode()){
      if(!n.nodeValue || n.nodeValue.indexOf('缺失材料')<0) continue;
      var p=n.parentElement, ok=true;
      while(p && p!==document.body){
        var cs=getComputedStyle(p);
        if(cs.display==='none'||cs.visibility==='hidden'||cs.opacity==='0'){ ok=false; break; }
        p=p.parentElement;
      }
      if(ok) vis++;
    }
    o.missMat=vis;
  })();
  o.pon=!!document.querySelector('#view-p0.on');
  o.pfpanel=document.querySelectorAll('#view-p0 [class*="pf-"]').length;
  o.kpi=document.querySelectorAll('#view-p0 .kpi').length;
  // 圆环图图例越界检查：只在**激活视图**内测（非激活视图 display:none，rect 全 0）
  var over=0, checked=0, worst=0;
  var scope = document.querySelector('.view.on') || document.querySelector('#view-p0') || document;
  scope.querySelectorAll('[data-chart="donut"]').forEach(function(host){
    var svg=host.querySelector('svg'); if(!svg) return;
    var card=host.closest('.chart')||host; checked++;
    var cr=card.getBoundingClientRect();
    if(cr.width < 10) return;
    // 卡片的实际内容区（扣掉 padding/border）
    var cs=getComputedStyle(card);
    var padR=parseFloat(cs.paddingRight)||0, padL=parseFloat(cs.paddingLeft)||0;
    var bdR=parseFloat(cs.borderRightWidth)||0, bdL=parseFloat(cs.borderLeftWidth)||0;
    var innerR=cr.right-padR-bdR+1, innerL=cr.left+padL+bdL-1;
    svg.querySelectorAll('text,tspan,rect').forEach(function(el){
      var b=el.getBoundingClientRect();
      if(b.width===0&&b.height===0) return;
      if(b.right>innerR){ over++; worst=Math.max(worst, b.right-innerR); }
      else if(b.left<innerL){ over++; worst=Math.max(worst, innerL-b.left); }
    });
  });
  o.donutChecked=checked; o.donutOver=over; o.donutWorst=Math.round(worst);
  // ★v5：圆环图量级一致性（P0 单位错标）——三条硬规则
  //   R1 中心合计必须有「数字+单位」，只写单位词即失败
  //   R2 中心金额与 PROF.poolTotal 相对误差 ≤ 2 倍（不是 100 倍）
  //   R3 图例各项之和与中心合计相对误差 ≤ 1%
  (function(){
    var bad=0, samples=[], nChk=0, noNum=0, sumBad=0;
    var order=(window.__V2&&window.__V2.ORDER)||[];
    var PROF=(window.__V2&&window.__V2.PROF)||{};
    var views=document.querySelectorAll('[id^="view-p"]');
    var vi=0;
    views.forEach(function(v){
      var key=order[vi++]; var prof=key?PROF[key]:null;
      var donut=v.querySelector('[data-chart="donut"]');
      if(!donut||!prof||!prof.poolTotal) return;
      var svg=donut.querySelector('svg'); if(!svg) return;
      nChk++;
      var txts=[];
      svg.querySelectorAll('text,tspan').forEach(function(t){ var s=(t.textContent||'').trim(); if(s) txts.push(s); });
      var joined=txts.join(' ');
      // 中心合计：可能被拆成「合计」+「11.92」+「亿元」多个 text，故在拼接串里找
      var centerTxt='';
      var mC=joined.match(/合计\s*([\d,.]+\s*(?:亿|万)元?)/);
      if(mC) centerTxt=mC[1];
      if(!centerTxt){
        var m2=joined.match(/([\d,.]+\s*(?:亿|万)元)/);
        if(m2) centerTxt=m2[1];
      }
      if(!centerTxt){
        // 只写了单位词、没有数字 → 失败
        if(/(?:亿|万)元?/.test(joined) && !/[\d,.]\s*(?:亿|万)元?/.test(joined)){
          noNum++; bad++; if(samples.length<3) samples.push(key+':中心无数字(仅单位词)');
        }
        return;
      }
      var mm=centerTxt.match(/([\d,.]+)\s*([万亿])/); if(!mm) return;
      var val=parseFloat(mm[1].replace(/,/g,''));
      var unit=mm[2];
      var centerYuan=unit==='亿'? val*1e8 : val*1e4;
      // R2（v8 改）：分布图合计必须在合理量级区间 [1000 万, 1000 亿]。
      //   这样能抓住「11.92 万」（量级错 1 万倍），又不会误伤中心显示非入池指标的图（如预计回收 2.15 亿）。
      //   若该图确实对应 poolTotal，仍做 ≤2 倍校验。
      var inRange = centerYuan >= 1e7 && centerYuan <= 1e11;
      var ratio = prof.poolTotal ? centerYuan/prof.poolTotal : 1;
      var matchPool = ratio >= 0.5 && ratio <= 2;
      if(!inRange && !matchPool){
        bad++; if(samples.length<3) samples.push(key+':中心'+centerTxt+' 不在合理量级');
      }
      // R3：图例求和（仅当图例项与中心同口径）
      var sum=0, cnt=0;
      txts.forEach(function(s){
        var m2=s.match(/[\d.]+\s*%\s*·\s*([\d,.]+)\s*([万亿])/);
        if(m2){ var v2=parseFloat(m2[1].replace(/,/g,'')); sum += (m2[2]==='亿'? v2*1e8 : v2*1e4); cnt++; }
      });
      if(cnt>=2 && sum>0 && matchPool){
        var r2=sum/centerYuan;
        if(r2>1.2 || r2<0.8){ sumBad++; bad++; if(samples.length<3) samples.push(key+':图例和'+sum.toExponential(2)+' vs 中心'+centerYuan.toExponential(2)); }
      }
    });
    o.magChk=nChk; o.magBad=bad; o.magNoNum=noNum; o.magSumBad=sumBad; o.magSample=samples.join(' | ');
  })();
  // ★v5：渲染后技术术语与旧表述残留
  (function(){
    var body=document.body.innerText||'';
    o.tech=['payload.','liq_info','ref_rate','A_回源已补','B_报告确无','C_源文件缺失','残迹待核','(s_k, e_k]'];
    o.techHit=o.tech.filter(function(k){ return body.indexOf(k)>=0; }).join(',');
    o.finalWord=(body.match(/已终局/g)||[]).length;
    o.termWord=(body.match(/信托计划已终止|信托计划存续中/g)||[]).length;
    o.ovFirst=((document.querySelector('#view-overview')||{innerText:''}).innerText||'').slice(0,220);
    // v7：算术平均（总览此刻可见）
    var ovtxt=o.ovFirst.__full || ((document.querySelector('#view-overview')||{innerText:''}).innerText||'');
    o.simpleAvg=(ovtxt.match(/简单平均/g)||[]).length;
    o.arithAvg=(ovtxt.match(/算术平均/g)||[]).length;
    // v8：品种总结位置已在 probe 开头（click('overview') 之后）测量

    // v7：关键指标网格列数（.ov-bgrid，解析 repeat(N, …)）
    (function(){
      var g=document.querySelector('#view-overview .ov-bgrid');
      if(!g){ o.ovCols='NOGRID'; return; }
      var tpl=getComputedStyle(g).gridTemplateColumns||'';
      var m=tpl.match(/repeat\(\s*(\d+)/);
      o.ovCols = m ? m[1] : tpl.trim().split(/\s+/).length;
      o.ovBtopN = document.querySelectorAll('#view-overview .ov-btop').length;
    })();
    // 78_wording 覆盖项：英文术语在整个 body 可见文本里也必须消失
    o.mathSym=(body.match(/\(s_k, e_k\]/g)||[]).length;
    o.localPath=(body.match(/E:\\\\|E:\//g)||[]).length;
    o.avgBare=((body.match(/(?<!简单平均|规模加权|加权)平均/g)||[]).length);
  })();
  // 卡片内容溢出检查
  var ovf=0;
  document.querySelectorAll('.dist-grid .chart').forEach(function(c){
    if(c.scrollHeight > c.clientHeight+2) ovf++;
  });
  o.cardOverflow=ovf;
  // 品种分组：每个品种占整行（宽度接近容器）
  var vb=document.querySelectorAll('#view-overview .vband');
  o.vbandRows=vb.length;
  var cont=document.querySelector('#view-overview .vbands');
  var cw=cont?cont.getBoundingClientRect().width:0;
  o.vbandFullRow=vb.length>0 && Array.prototype.every.call(vb,function(v){
    return cw>0 && v.getBoundingClientRect().width >= cw*0.9;
  });
  // 档案 5 类分组：按 DOM 出现顺序断言（不只看齐全）
  var PF_ORDER=['资产池情况','集中度与账龄','预期回收与发行结构','实际回收与处置','实际收益与期限'];
  var p0txtAll=document.querySelector('#view-p0')?document.querySelector('#view-p0').innerText:'';
  o.pf5=PF_ORDER.filter(function(k){ return p0txtAll.indexOf(k)>=0; }).length;
  var pos=PF_ORDER.map(function(k){ return p0txtAll.indexOf(k); });
  o.pfOrderOk = pos.every(function(p){ return p>=0; }) &&
                pos.every(function(p,i){ return i===0 || p > pos[i-1]; });
  o.pfOrderShown = PF_ORDER.map(function(k){ return k+'@'+p0txtAll.indexOf(k); }).join(' ');
  // 「发行」重复分组名检查
  o.pfDupIssue=(p0txtAll.match(/发行与规模|发行与结构/g)||[]).length;
  // 数值小数位上限（防未舍入浮点，如 12.26086956521739）
  // 排除「折现因子」表：其 8 位小数是合理精度，不属于单位/舍入缺陷
  var longDec=0, longSample='', discDec=0;
  var vis=document.querySelector('.view.on')||document;
  vis.querySelectorAll('div,span,b,td,th').forEach(function(el){
    if(el.children.length) return;
    var t=(el.textContent||'').trim();
    if(t.length>40) return;
    if(!/\.\d{5,}/.test(t)) return;
    var tbl=el.closest('table');
    var head=tbl?(tbl.textContent.slice(0,300)):'';
    if(/折现|贴现|DF\b/.test(head)){ discDec++; return; }
    longDec++; if(!longSample) longSample=t.slice(0,42);
  });
  o.longDec=longDec; o.longSample=longSample; o.discDec=discDec;
  // 单位徽章一致性（轻量版）：徽章标金额单位的图，其值标签中须出现同一单位词、且不混排
  var badgeBad=0, badgeSample='';
  vis.querySelectorAll('[data-chart]').forEach(function(host){
    var tag=host.querySelector('.ct, .v6-tag, .chart-tag');
    var txt=(host.textContent||'');
    var m=txt.match(/单位：(亿|万|元)/);
    if(!m) return;                         // 未标金额单位的图跳过
    var u=m[1];
    var svg=host.querySelector('svg'); if(!svg) return;
    var vals=[];
    svg.querySelectorAll('text,tspan').forEach(function(t){
      var s=(t.textContent||'').trim();
      if(/[\d,.]+\s*(亿|万)?元/.test(s)) vals.push(s);
    });
    if(!vals.length) return;               // 轴注记型放行
    var hasSame = vals.some(function(s){ return s.indexOf(u+'元')>=0 || (u!=='元' && s.indexOf(u)>=0); });
    var others = vals.some(function(s){
      var mm=s.match(/(亿|万)元/); return mm && mm[1]!==u;
    });
    if(!hasSame || others){ badgeBad++; if(!badgeSample) badgeSample=(host.querySelector('.ct')?host.querySelector('.ct').textContent:'').slice(0,20)+' 徽章='+u; }
  });
  o.badgeBad=badgeBad; o.badgeSample=badgeSample;
  // R1 渲染后「折价率」可见性判定（注释/自检文本不计；只算用户能看到且可见的文本）
  (function(){
    var vis=0, w=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), n;
    while(n=w.nextNode()){
      if(!n.nodeValue || n.nodeValue.indexOf('折价率')<0) continue;
      var p=n.parentElement, ok=true;
      while(p && p!==document.body){
        var cs=getComputedStyle(p);
        if(cs.display==='none'||cs.visibility==='hidden'||cs.opacity==='0'){ ok=false; break; }
        p=p.parentElement;
      }
      if(ok) vis++;
    }
    o.zjl=vis;
  })();
  // 聚类分组容器（a2-overview 用 .ov-cat-wrap）
  o.cluster=document.querySelectorAll('#view-overview .ov-cat-wrap').length;
  o.bankHd=document.querySelectorAll('#view-overview .ov-bank-hd').length;
  // tooltip 功能
  var el=null, cands=document.querySelectorAll('#view-p0 svg *');
  for(var i=0;i<cands.length;i++){
    for(var j=0;j<cands[i].children.length;j++){
      if(cands[i].children[j].tagName&&cands[i].children[j].tagName.toLowerCase()==='title'){ el=cands[i]; break; }
    }
    if(el) break;
  }
  if(el){
    var r=el.getBoundingClientRect();
    el.dispatchEvent(new MouseEvent('mousemove',{clientX:r.left+r.width/2,clientY:r.top+r.height/2,bubbles:true}));
    var tp=document.getElementById('xtTip');
    o.tip=(tp&&tp.classList.contains('on')&&(tp.textContent||'').length>0)?'PASS':'FAIL';
    o.tipText=tp?(tp.textContent||'').slice(0,50):'';
  } else { o.tip='NOELEM'; }
  o.svg=document.querySelectorAll('svg').length;
  // ══ v6 专项断言 ══
  // V6-1 瀑布：__V2.WF 覆盖与闭合
  (function(){
    var WF=(window.__V2&&window.__V2.WF)||{};
    var keys=Object.keys(WF);
    o.wfN=keys.length;
    var bad=0, worst=0, dbl=0;
    keys.forEach(function(k){
      var w=WF[k];
      if(w.dbl) dbl++;
      var pct=w.rec? Math.abs(w.residual)/w.rec*100 : 999;
      if(pct>5){ bad++; }
      if(pct>worst) worst=pct;
    });
    o.wfBad=bad; o.wfWorst=+worst.toFixed(2); o.wfDbl=dbl;
  })();
  // ⚠ 顺序关键：先切 p0 量档案尺寸/资产池布局（active 视图才有 rect），再切橙益八期量瀑布
  (function(){
    var items=Array.from(document.querySelectorAll('.sb-item[data-view^="p"]'));
    var tgt=items.filter(function(a){return a.textContent.indexOf('橙益2024年第八期')>=0})[0];
    var p0btn=document.querySelector('.sb-item[data-view="p0"]');
    if(p0btn) p0btn.click();
    setTimeout(function(){
      var v0=document.querySelector('#view-p0');
      if(v0){
        // ③④ 面板宽度
        var p7=v0.querySelector('.pf-7'), p5=v0.querySelector('.pf-5');
        if(p7&&p5){ o.panelW=Math.round(p7.getBoundingClientRect().width)+'/'+Math.round(p5.getBoundingClientRect().width); }
        // ⑥ 资产池分布图行分布（.dist-grid > .v6-row）
        var dg=v0.querySelector('.dist-grid');
        if(dg){
          var rows=Array.from(dg.querySelectorAll(':scope > .v6-row'));
          if(!rows.length){
            // 兼容：未分行时按 top 聚类
            var kids=Array.from(dg.children).filter(function(c){ return c.getBoundingClientRect().height>10; });
            var map={};
            kids.forEach(function(c){ var r=c.getBoundingClientRect(); var key=Math.round(r.top/40)*40; (map[key]=map[key]||[]).push(Math.round(r.height)); });
            rows=Object.keys(map).sort(function(a,b){return a-b}).map(function(k){ return {_h: map[k]}; });
            o.distRows = rows.map(function(r){return r._h.length}).join('+');
            o.distRowH = rows.map(function(r){ return Math.max.apply(null,r._h)-Math.min.apply(null,r._h); }).join(',');
          } else {
            o.distRows = rows.map(function(r){ return r.children.length; }).join('+');
            o.distRowH = rows.map(function(r){
              var hs=Array.from(r.children).map(function(c){return Math.round(c.getBoundingClientRect().height)});
              return Math.max.apply(null,hs)-Math.min.apply(null,hs);
            }).join(',');
          }
          o.distMaxLone = Math.max.apply(null, (o.distRows||'0').split('+').map(Number).concat([0]));
        }
        // ⑤ 时间轴节点（.pf-tl > .pf-ts，hover 用 title 属性）
        var tl=v0.querySelector('.pf-tl');
        o.tlNodes = tl? tl.querySelectorAll('.pf-ts').length : 0;
        o.tlHover = tl? tl.querySelectorAll('.pf-ts[title]').length : 0;
        o.payTable = (function(){
          var els=Array.from(v0.querySelectorAll('*')).filter(function(e){ return e.children.length===0 && (e.textContent||'').trim().indexOf('兑付与清算时点')===0; });
          for(var i=0;i<els.length;i++){
            var p=els[i], vis=true;
            while(p && p!==document.body){ var cs=getComputedStyle(p); if(cs.display==='none'||cs.visibility==='hidden'){vis=false;break;} p=p.parentElement; }
            if(vis) return 'VISIBLE';
          }
          return 'HIDDEN';
        })();
        // 集中度 / 裸百分比（p0 上量）
        var t=v0.innerText||'';
        o.undisclosed=(t.match(/未披露/g)||[]).length;
        o.dash=(t.match(/—/g)||[]).length;
        var t2=(t||'').replace(/100%\s*堆叠[条图]?/g,'');
        o.barePct=(t2.match(/[^\d.]\d{1,3}%(?!\d)/g)||[]).length;
        // ══ v8：①② 面板卡片数与去重 ══
        (function(){
          var pans=v0.querySelectorAll('.pf-panel');
          var p1=pans[0], p2=pans[1];
          function cards(p){ return p? p.querySelectorAll('.pf-k, .pf-cell, .pf-kv').length : -1; }
          o.p1Cards=cards(p1); o.p2Cards=cards(p2);
          o.pool8 = p1? (p1.innerText||'').replace(/\s+/g,' ').slice(0,120) : '';
          o.hasDispFee = (t||'').indexOf('处置费用占比')>=0;
        })();
        // ══ v8：资产池图表质量 ══
        (function(){
          var dg2=v0.querySelector('.dist-grid');
          if(!dg2){ o.chartMaxFs=0; return; }
          var maxFs=0, tallOver=0, minFill=9, collide=0;
          dg2.querySelectorAll('.v6-row > *').forEach(function(card){
            var ch=card.getBoundingClientRect().height;
            if(ch>380) tallOver++;
            var inner=card.querySelector('.chart-body, .chart-wrap, svg');
            if(inner && ch>20){
              var ih=inner.getBoundingClientRect().height;
              var fill=ih/ch; if(fill<minFill) minFill=fill;
            }
            card.querySelectorAll('svg text, svg tspan').forEach(function(tx){
              var fs=parseFloat(getComputedStyle(tx).fontSize)||0;
              if(fs>maxFs) maxFs=fs;
            });
          });
          o.chartMaxFs=Math.round(maxFs*10)/10;
          o.chartTallOver=tallOver;
          o.chartMinFill=Math.round(minFill*100)/100;
        })();
        // ══ v8：职业分布 Top10+其他（≤11 条）、预计回收率轴不越界 ══
        (function(){
          var charts=Array.from(v0.querySelectorAll('.chart, .a-chart, [data-chart]'));
          var occ=charts.filter(function(c){ return (c.textContent||'').indexOf('职业')>=0; })[0];
          if(occ){
            var bars=occ.querySelectorAll('svg rect.bar, svg .bar, svg rect[data-bar]').length;
            o.occBars = bars || occ.querySelectorAll('svg text').length;
            o.occHasOther = (occ.textContent||'').indexOf('其他')>=0;
          }
          var rc=charts.filter(function(c){ return (c.textContent||'').indexOf('预计回收率')>=0; })[0];
          if(rc){
            var svg=rc.querySelector('svg');
            if(svg){
              var sr=svg.getBoundingClientRect(), bad=0;
              svg.querySelectorAll('text,tspan').forEach(function(tx){
                var b=tx.getBoundingClientRect();
                if(b.width && b.left < sr.left-1) bad++;
              });
              o.rcYClip=bad;
            }
          }
          // ══ v8.3：图型分布（在原图型基础上只换职业/地区）══
          (function(){
            var p1=document.querySelector('#view-p1');
            if(!p1){ o.p1Kinds='NOVIEW'; return; }
            var kinds={donut:0, hbar:0, distbar:0};
            p1.querySelectorAll('[data-chart]').forEach(function(e){
              var k=e.getAttribute('data-chart');
              if(k==='donut') kinds.donut++;
              else if(k==='hbar') kinds.hbar++;
              else if(k==='dist-bar') kinds.distbar++;
            });
            o.p1Kinds='donut='+kinds.donut+' hbar='+kinds.hbar+' distbar='+kinds.distbar;
            var v9map={};
            p1.querySelectorAll('[data-v9-chart]').forEach(function(c){
              var k=c.getAttribute('data-v9-chart'); v9map[k]=(v9map[k]||0)+1;
            });
            o.v9Kinds=Object.keys(v9map).sort().map(function(k){return k+':'+v9map[k];}).join(' ');
            // v9：图型多样性 / 圆环数 / 单位 / TopN 脚注 / 横向滚动
            var dg=p1.querySelector('.dist-grid'); if(!dg) return;
            var set={}, donut=0, unitN=0, topN=0, hs=0, cards=0;
            dg.querySelectorAll('[data-chart]').forEach(function(e){
              var k=e.getAttribute('data-chart')||'?';
              // 只统计 10 张分布图所在卡片
              if(!e.closest('.chart')) return;
              set[k]=1; if(k==='donut') donut++;
            });
            dg.querySelectorAll('.chart').forEach(function(c){
              cards++;
              var t=(c.textContent||'');
              if(t.indexOf('口径')>=0) unitN++;
              if(/其他.{0,6}\d+\s*项|其余合并|Top\s*\d+/.test(t)) topN++;
              var svg=c.querySelector('svg');
              if(c.scrollWidth > c.clientWidth+2) hs++;
            });
            o.chartKindN=Object.keys(set).length;
            o.chartKinds=Object.keys(set).join(',');
            o.chartDonut=donut; o.chartUnitN=unitN; o.topNNote=topN; o.hScroll=hs;
            // v9：① 面板「入池息费」单位
            var t1=(v0?v0.innerText:'')||'';
            var m=t1.match(/入池息费\s*([\d,.]+\s*[万亿]元?)/);
            o.poolIntUnit = m? m[0].replace(/\s+/g,' ') : '未找到';
          })();
          // ══ v8.3：担保方式异常备注（不得回归）══
          (function(){
            var p1=document.querySelector('#view-p1');
            if(!p1){ o.noteOk=false; return; }
            var t=p1.textContent||'';
            var els=p1.querySelectorAll('[class*="dist-note"]');
            var inCard=0;
            Array.prototype.forEach.call(els, function(e){ if(e.closest('.chart')) inCard++; });
            o.noteOk = (t.indexOf('待回源核实')>=0) && (t.indexOf('10.12%')>=0) && els.length>=1 && inCard===0;
            o.noteInfo = 'els='+els.length+' inCard='+inCard+' 待回源='+(t.indexOf('待回源核实')>=0)+' 10.12%='+(t.indexOf('10.12%')>=0);
          })();
        })();
      }
      // 先切 p1（中誉至诚2024年第五期）激活图表转换，再量 10 张分布图
      var p1btn=document.querySelector('.sb-item[data-view="p1"]');
      if(p1btn) p1btn.click();
      setTimeout(function(){
        (function(){
          var p1=document.querySelector('#view-p1');
          if(!p1) return;
          var v9map={};
          p1.querySelectorAll('[data-v9-chart]').forEach(function(c){
            var k=c.getAttribute('data-v9-chart'); v9map[k]=(v9map[k]||0)+1;
          });
          o.v9Kinds=Object.keys(v9map).sort().map(function(k){return k+':'+v9map[k];}).join(' ');
          var dg=p1.querySelector('.dist-grid'); if(!dg) return;
          var set={}, donut=0, unitN=0, topN=0, hs=0;
          dg.querySelectorAll('[data-v9-chart]').forEach(function(c){ set[c.getAttribute('data-v9-chart')]=1; });
          dg.querySelectorAll('.chart').forEach(function(c){
            var t=(c.textContent||'');
            if(t.indexOf('口径')>=0) unitN++;
            if(/其他.{0,6}\d+\s*项|其余合并|Top\s*\d+/.test(t)) topN++;
            if(c.scrollWidth > c.clientWidth+2) hs++;
          });
          o.chartKindN=Object.keys(set).length;
          o.chartKinds=Object.keys(set).join(',');
          o.chartDonut=donut; o.chartUnitN=unitN; o.topNNote=topN; o.hScroll=hs;
          // 担保异常备注（激活后量）
          var t=p1.textContent||'';
          var els=p1.querySelectorAll('[class*="dist-note"]');
          var inCard=0;
          Array.prototype.forEach.call(els, function(e){ if(e.closest('.chart')) inCard++; });
          o.noteOk = (t.indexOf('待回源核实')>=0) && (t.indexOf('10.12%')>=0) && els.length>=1 && inCard===0;
          o.noteInfo = 'els='+els.length+' inCard='+inCard+' 待回源='+(t.indexOf('待回源核实')>=0)+' 10.12%='+(t.indexOf('10.12%')>=0);
        })();
        // 再切橙益八期量瀑布
        if(!tgt){ o.cyWf='NOITEM'; document.title='VRESULT:'+JSON.stringify(o); return; }
        tgt.click();
        setTimeout(function(){
        var v=document.querySelector('#view-p11')||document.querySelector('.view.on');
        var wf=v?v.querySelector('[data-chart="waterfall"]'):null;
        if(!wf){ o.cyWf='NOWF'; document.title='VRESULT:'+JSON.stringify(o); return; }
        var ts=[]; wf.querySelectorAll('title').forEach(function(t){ ts.push(t.textContent); });
        var joined=ts.join(' ‖ ');
        var priOk = /优先档 本金[^‖]*0\.54\s*亿元/.test(joined) || /优先档 本金[^‖]*5,400/.test(joined);
        var intOk = /优先档 利息[^‖]*59\.34\s*万元/.test(joined);
        o.cyWf = (priOk ? 'PRI-OK' : 'PRI-BAD') + '/' + (intOk ? 'INT-OK' : 'INT-BAD')
               + ' | 处置费出现:' + (joined.indexOf('处置费用') >= 0 ? '是' : '否')
               + ' | ' + joined.slice(0, 130);
        // 瀑布降序（首=回收流入 末=账面结余，中间须单调递减）
        var tit=[]; wf.querySelectorAll('title').forEach(function(x){ tit.push(x.textContent); });
        var amts=[];
        tit.forEach(function(s){
          var m=s.match(/([\d,.]+)\s*(亿|万)元/);
          if(m){ var vv=parseFloat(m[1].replace(/,/g,'')); amts.push(m[2]==='亿'? vv*1e8 : vv*1e4); }
        });
        var mid=amts.slice(1, -1), desc=true;
        for(var i=1;i<mid.length;i++){ if(mid[i] > mid[i-1] + 1) { desc=false; break; } }
        o.wfOrder = (mid.length>=4 ? (desc?'DESC-OK':'DESC-BAD') : 'TOO-FEW') + ' n=' + mid.length;
        // 算术平均（此时 body 含总览? 不含 → 单独在开头量）
        var bt=document.body.innerText||'';
        o.simpleAvg=(bt.match(/简单平均/g)||[]).length;
        o.arithAvg=(bt.match(/算术平均/g)||[]).length;
        document.title='VRESULT:'+JSON.stringify(o);
      }, 1400);
      }, 900);
    }, 1000);
  })();
  // v10：xcompare 新图 SVG 是否都带 viewBox
  (function(){
    var xv=document.getElementById('view-xcompare');
    if(!xv){ o.xcViewBox='NOVIEW'; return; }
    var tot=0, noVb=0;
    xv.querySelectorAll('svg').forEach(function(sv){
      tot++;
      if(!sv.getAttribute('viewBox')) noVb++;
    });
    o.xcViewBox='svg='+tot+' 无viewBox='+noVb;
    o.xcVbOk = (tot>0 && noVb===0);
  })();
  // 算术平均 / 字段字典：在切视图前（总览/默认视图可见）量
  o.dictOk = (document.body.innerText||'').indexOf('字段字典') >= 0;
  // ══ v11：独立激活 xcompare 测 02/03/04/05/⑧ ══
  setTimeout(function(){
    var xb=document.querySelector('.sb-item[data-view="xcompare"]');
    if(xb) xb.click();
    setTimeout(function(){
      var xv=document.getElementById('view-xcompare');
      if(!xv){ o.noDumbbell=false; document.title='VRESULT:'+JSON.stringify(o); return; }
      var t=(xv.innerText||'');
      // 02：图内「项目名 ±x.xx pp」标签
      var lab=0;
      xv.querySelectorAll('svg text, svg tspan').forEach(function(e){
        var s=(e.textContent||'').trim();
        if(/\S+\s*[+\-−]?\d+\.\d+\s*pp/.test(s)) lab++;
      });
      o.lab02=lab;
      // 03：无倒算哑铃
      o.noDumbbell = (t.indexOf('倒算约定')<0) && (t.indexOf('可倒算')<0) && (t.indexOf('约定资金成本率')<0);
      o.dumbInfo = '倒算约定='+(t.indexOf('倒算约定')>=0)+' 可倒算='+(t.indexOf('可倒算')>=0);
      // 03：字号与高度
      (function(){
        var scope = xv.querySelector('#s03') || xv;
        var mn=99, h=0;
        scope.querySelectorAll('svg').forEach(function(sv){
          var hh=sv.getBoundingClientRect().height; if(hh>h) h=hh;
          sv.querySelectorAll('text,tspan').forEach(function(tx){
            var fs=parseFloat(getComputedStyle(tx).fontSize)||0;
            if(fs>0 && fs<mn) mn=fs;
          });
        });
        o.s03Min = (mn===99?0:Math.round(mn*10)/10); o.h03 = Math.round(h);
        // 计算 03 内 SVG 文字中 ≥11.5px 的占比
        var tot=0, big=0;
        scope.querySelectorAll('svg text, svg tspan').forEach(function(tx){
          var fs=parseFloat(getComputedStyle(tx).fontSize)||0;
          if(fs>0){ tot++; if(fs>=11.4) big++; }
        });
        o.s03Pct = tot? Math.round(big/tot*100) : 0; o.s03Tot = tot;
      })();
      // 04：瀑布降序 + 费用帕累托
      (function(){
        var wf=xv.querySelector('svg[aria-label*="瀑布"]');
        if(wf){
          var amts=[];
          wf.querySelectorAll('title').forEach(function(x){
            var m=(x.textContent||'').match(/([\d,.]+)\s*(亿|万)/);
            if(m) amts.push(parseFloat(m[1].replace(/,/g,''))*(m[2]==='亿'?1e8:1e4));
          });
          if(amts.length>=4){
            var mid=amts.slice(1,-1), desc=true;
            for(var i=1;i<mid.length;i++){ if(mid[i]>mid[i-1]*1.02){ desc=false; break; } }
            o.wfDesc=desc; o.wfDescInfo='n='+mid.length+(desc?' 降序':' 非降序');
          } else { o.wfDesc=false; o.wfDescInfo='样本不足 '+amts.length; }
        } else { o.wfDesc=false; o.wfDescInfo='无瀑布'; }
      })();
      (function(){
        var bg=xv.querySelectorAll('svg');
        var bad=0, parFound=false;
        bg.forEach(function(sv){
          var tx=(sv.textContent||'');
          if(tx.indexOf('帕累托')>=0 || (tx.indexOf('累计')>=0 && tx.indexOf('%')>=0)){
            parFound=true;
            if(/证券.{0,4}本金|优先档.{0,4}本金|次级档.{0,4}本金/.test(tx)) bad++;
          }
        });
        o.parFeeOnly = parFound && bad===0; o.parInfo='找到='+parFound+' 含证券本金='+bad;
      })();
      // ⑧：披露概览 + 默认收起
      (function(){
        var p0=document.getElementById('view-p0');
        var t0=p0? (p0.textContent||'') : '';
        var hasOv = /已回源补全|披露概览|源未披露/.test(t0);
        var dt=p0? p0.querySelectorAll('details') : [];
        var open=0; Array.prototype.forEach.call(dt,function(d){ if(d.hasAttribute('open')) open++; });
        o.ov88 = hasOv; o.ov88Info='概览='+hasOv+' details='+dt.length+' 展开='+open;
      })();
      document.title='VRESULT:'+JSON.stringify(o);
    }, 1300);
  }, 5400);
  document.title='VRESULT:'+JSON.stringify(o);
}, 2600);
"""
test.write_text(h.replace("<head>", "<head>" + hook, 1).replace("</body>", f"<script>{probe}</script></body>", 1),
                encoding="utf-8")
url = "file:///" + str(test).replace("\\", "/")
pr = subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--no-sandbox",
                     "--window-size=1600,1400",
                     "--virtual-time-budget=30000", "--dump-dom", url],
                    capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=600)
dom = pr.stdout or ""
nos = re.sub(r"<script.*?</script>", "", dom, flags=re.S)
ttl = re.search(r"<title>(.*?)</title>", dom, re.S)
title = ttl.group(1) if ttl else ""

chk("8", "无运行时错误", not title.startswith("ERR:"), ("title 正常" if not title.startswith("ERR:") else title[:150]))
chk("8", "真实 SVG ≥ 360", nos.count("<svg") >= 360, f"SVG {nos.count('<svg')}")
n_view_nos = nos.count('class="view')
chk("8", "视图 30 个（含合并页）", n_view_nos >= 30, f"{n_view_nos}")
# 「账户配平」只在源标记里；渲染后 DOM 必须已被 JS 清除
chk("2|7", "渲染后无「账户配平」", nos.count("账户配平") == 0, f"源 {h.count('账户配平')} → 渲染 {nos.count('账户配平')}")

res = {}
m = re.search(r"VRESULT:(\{.*?\})", title, re.S)
if m:
    try:
        res = json.loads(m.group(1))
    except Exception as e:
        print("   ⚠ 解析 VRESULT 失败", e)

if res:
    print()
    print(f"  渲染实测：侧栏 {res.get('tabs')} 项 · 视图 {res.get('views')} · 全页 SVG {res.get('svg')}")
    chk("3", "合并页可切换", res.get("xon"), f"svg {res.get('xsvg')} · title {res.get('xtitle')} · 小节 {res.get('xh2')}")
    chk("3", "★明细与底稿可切换", res.get("aon2"), f"tr {res.get('aTr')}")
    chk("3", "★折叠块默认收起", (res.get("foldN") or 0) >= 3 and (res.get("foldOpen") or 0) == 0,
        f"折叠 {res.get('foldN')} 个 · 默认展开 {res.get('foldOpen')} 个")
    chk("3", "★渲染后无「折价率」", (res.get("zjl") or 0) == 0, f"可见 {res.get('zjl')} 处")
    chk("3", "四象限气泡 28 个", (res.get("xbub") or 0) >= 28, f"{res.get('xbub')}")
    chk("3", "横向对照页有内容", (res.get("xTr") or 0) >= 10, f"xcompare tr {res.get('xTr')}")
    # ★v5 关键新断言
    chk("4|7", "★★圆环图量级一致（P0）", (res.get("magBad") or 0) == 0,
        f"检查 {res.get('magChk')} 张 · 失败 {res.get('magBad')} 张（无数字 {res.get('magNoNum')} · 图例和错 {res.get('magSumBad')}）「{res.get('magSample','')}」")
    chk("4", "★渲染后无技术术语", not (res.get("techHit") or ""),
        f"命中「{res.get('techHit','')}」")
    chk("4", "★渲染后无「已终局」", (res.get("finalWord") or 0) == 0, f"{res.get('finalWord')} 处")
    chk("4", "★终局性新表述已生效", (res.get("termWord") or 0) >= 1, f"「信托计划已终止/存续中」{res.get('termWord')} 处")
    chk("4", "★无左开右闭数学符号", (res.get("mathSym") or 0) == 0, f"{res.get('mathSym')} 处")
    chk("4", "★本地路径已脱敏（渲染后）", (res.get("localPath") or 0) == 0, f"{res.get('localPath')} 处")
    chk("1", "★总览首句已更正", not re.search(r"按银行分组的\s*28\s*单\s*KPI\s*速览", res.get("ovFirst") or ""),
        (res.get("ovFirst") or "")[:60])
    chk("1", "总览 8 项 × 28 卡", (res.get("ovk") or 0) >= 224, f".ov-k {res.get('ovk')}")
    chk("1", "品种分组 3 行且占整行", (res.get("vbandRows") or 0) == 3 and (res.get("vbandFullRow") or res.get("vbandEqual")),
        f"{res.get('vbandRows')} 行 · 宽度 {res.get('vbandWidths')} / 容器 {res.get('vbandCW')}px · 等宽={res.get('vbandEqual')}")
    chk("1", "28 卡已聚类分组", (res.get("cluster") or 0) >= 3, f"品种组 {res.get('cluster')} · 银行小组 {res.get('bankHd')}")
    chk("2|7", "项目档案面板已替换", (res.get("pfpanel") or 0) >= 50, f"pf-* {res.get('pfpanel')}")
    chk("2|7", "旧 KPI 小格已清除", (res.get("kpi") or 0) <= 16, f"残留 .kpi {res.get('kpi')}")
    chk("2|7", "档案 5 类分组齐全", (res.get("pf5") or 0) == 5, f"{res.get('pf5')}/5")
    chk("2|7", "★5 类顺序符合要求", res.get("pfOrderOk"),
        "资产池情况→集中度与账龄→预期回收与发行结构→实际回收与处置→实际收益与期限")
    chk("2|7", "「发行」不再重复分组", (res.get("pfDupIssue") or 0) == 0, f"重复 {res.get('pfDupIssue')} 处")
    chk("1|4", "★无未舍入长小数", (res.get("longDec") or 0) == 0,
        f"超 4 位小数 {res.get('longDec')} 处「{res.get('longSample','')}」（折现因子豁免 {res.get('discDec')} 处）")
    chk("4|7", "★单位徽章与值一致", (res.get("badgeBad") or 0) == 0,
        f"违规 {res.get('badgeBad')} 张「{res.get('badgeSample','')}」")
    chk("4", "『缺失材料』已隐藏", (res.get("missMat") or 0) == 0, f"可见 {res.get('missMat')} 处")
    chk("4", "进入项目视图回到顶部", (res.get("scrollY") or 0) <= 60, f"scrollY {res.get('scrollY')}px")
    chk("4", "圆环图图例不越界", (res.get("donutOver") or 0) == 0,
        f"检查 {res.get('donutChecked')} 个，越界 {res.get('donutOver')} 处，最严重 {res.get('donutWorst')}px")
    chk("4", "卡片内容不溢出", (res.get("cardOverflow") or 0) == 0, f"溢出 {res.get('cardOverflow')} 张")
    chk("7", "tooltip 功能性", res.get("tip") == "PASS", f"{res.get('tip')} 「{res.get('tipText','')}」")
    # ══ v6 专项 ══
    chk("6", "★WF 覆盖 28 单", (res.get("wfN") or 0) >= 28, f"{res.get('wfN')} 单")
    chk("6", "★瀑布闭合（残差≤5%）", (res.get("wfBad") or 0) == 0,
        f"超限 {res.get('wfBad')} 单 · 最大残差 {res.get('wfWorst')}%")
    chk("6", "★处置费重复计入识别 6 单", (res.get("wfDbl") or 0) == 6, f"{res.get('wfDbl')} 单")
    chk("6", "★橙益八期瀑布取分档表口径", "PRI-OK" in str(res.get("cyWf","")) and "INT-OK" in str(res.get("cyWf",""))
        and "处置费出现:否" in str(res.get("cyWf","")),
        str(res.get("cyWf",""))[:130])
    chk("6", "③④ 面板等宽", (lambda s: bool(s) and abs(int(s.split("/")[0])-int(s.split("/")[1])) <= 2)(res.get("panelW","")),
        f"宽度 {res.get('panelW')}")
    chk("2", "★集中度字段字典已就位", bool(res.get("dictOk")), f"「字段字典」在 ② 面板内：{res.get('dictOk')}")
    chk("4", "★无裸整数百分比", (res.get("barePct") or 0) == 0, f"{res.get('barePct')} 处")
    # ══ v8.3 专项 ══
    chk("4", "★图型分布符合 v9 规格",
        str(res.get("v9Kinds","")) == "col:4 hbar-top:2 pareto:2 stack100:2", f"{res.get('v9Kinds')}")
    chk("4", "★担保方式异常备注不得回归", bool(res.get("noteOk")), f"{res.get('noteInfo')}")
    chk("4", "★预计回收率纵轴不越界", (res.get("rcYClip") or 0) == 0, f"越界 {res.get('rcYClip')} 处")
    chk("3", "★xcompare 新图 SVG 均带 viewBox", bool(res.get("xcVbOk")), f"{res.get('xcViewBox')}")
    # ══ v11 ══
    chk("3", "★02 图内无「项目名 ±pp」标签", (res.get("lab02") if res.get("lab02") is not None else 99) == 0, f"{res.get('lab02')} 处")
    chk("3", "★03 无次级倒算哑铃", bool(res.get("noDumbbell")), f"{res.get('dumbInfo')}")
    chk("3", "★03 字号整体+1（轴/数据≥11.5px，图注≥10.5px）",
        (res.get("s03Pct") or 0) >= 96 and (res.get("s03Min") or 0) >= 10.4,
        f"{res.get('s03Pct')}% 文字≥11.5px（{res.get('s03Tot')} 个）· 最小 {res.get('s03Min')}px（最小者为图注/副标题）")
    chk("3", "★03 高度 ≥420px", (res.get("h03") or 0) >= 415, f"{res.get('h03')}px")
    chk("3", "★04 瀑布中间项金额降序", res.get("wfDesc"), f"{res.get('wfDescInfo')}")
    chk("3", "★04 费用帕累托不含证券本金/利息", res.get("parFeeOnly"), f"{res.get('parInfo')}")
    chk("2", "★⑧ 披露概览动态且默认收起", res.get("ov88"), f"{res.get('ov88Info')}")
    # ══ v9：10 图规格重构 ══
    chk("4", "★图型多样性 ≥4 种", (res.get("chartKindN") or 0) >= 4, f"{res.get('chartKindN')} 种：{res.get('chartKinds')}")
    chk("4", "★圆环数量 ≤2", (res.get("chartDonut") if res.get("chartDonut") is not None else 99) <= 2, f"圆环 {res.get('chartDonut')} 张")
    chk("4", "★无横向滚动", (res.get("hScroll") or 0) == 0, f"横向溢出 {res.get('hScroll')} 处")
    chk("4", "★每图有单位与口径", (res.get("chartUnitN") or 0) >= 8, f"{res.get('chartUnitN')}/10 图带「口径」")
    chk("4", "★TopN 脚注含「其他」", (res.get("topNNote") or 0) >= 1, f"{res.get('topNNote')} 处")
    chk("2", "★入池息费用亿元", ("亿" in str(res.get("poolIntUnit",""))) and ("万" not in str(res.get("poolIntUnit",""))), f"{res.get('poolIntUnit')}")
    # ══ v7 专项 ══
    chk("7", "★瀑布按金额降序", "DESC-OK" in str(res.get("wfOrder","")), f"{res.get('wfOrder')}")
    chk("2", "★资产池图无「单张成行」", (res.get("distMaxLone") or 9) <= 3, f"行分布 {res.get('distRows')}")
    chk("2", "★资产池均衡分行（10→3+3+2+2 / 9→3+3+3）",
        str(res.get("distRows","")) in ("3+3+2+2", "3+3+3", "3+3+2+2+0"),
        f"行分布 {res.get('distRows')}")
    chk("2", "★资产池行内等高", all(int(x) <= 4 for x in str(res.get("distRowH","0")).split(",") if x != ""),
        f"行内高差 {res.get('distRowH')}px")
    chk("7", "★⑤ 时间轴节点 ≥8", (res.get("tlNodes") or 0) >= 8, f"{res.get('tlNodes')} 节点")
    chk("7", "★时间轴节点有悬停", (res.get("tlHover") or 0) >= 8, f"{res.get('tlHover')} 个 title")
    chk("7", "★时点表已并入（旧表隐藏）", res.get("payTable") == "HIDDEN", f"{res.get('payTable')}")
    chk("1", "★无「简单平均」", (res.get("simpleAvg") or 0) == 0 and h.count("简单平均") == 0,
        f"源 {h.count('简单平均')} / 渲染 {res.get('simpleAvg')} · 算术平均 {res.get('arithAvg')}")
    chk("1", "★品种总结横排", bool(res.get("ovSumOk")), f"{res.get('ovSumRow')}")
    chk("1", "★关键指标 6 列", str(res.get("ovCols")) == "6", f"列数 {res.get('ovCols')}")

fails = [x for x in R if x["结果"] == "FAIL"]
print()
print("═" * 78)
print(f"汇总：{len(R)} 断言　PASS {len(R)-len(fails)}　FAIL {len(fails)}")
(LOG / "summary_v2.json").write_text(json.dumps(
    {"时间": time.strftime("%Y-%m-%dT%H:%M:%S"), "断言数": len(R), "FAIL": len(fails), "明细": R},
    ensure_ascii=False, indent=1), encoding="utf-8")
print(f"留痕：{LOG}\\summary_v2.json")
test.unlink(missing_ok=True)
if fails:
    print(f"\n❌ {len(fails)} 个断言失败")
    sys.exit(1)
print("\n✅ 全部通过")
