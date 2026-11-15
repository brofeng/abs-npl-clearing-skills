# -*- coding: utf-8 -*-
r"""v2 · 第 1 项精修（v8）：总览看板 —— 筛选器（年份/机构/品种）+ 品种整行 + 28 单聚类。

用户原话（第二轮精修第 1 项）
----------------------------
「总览看板：品种分组色块（按基础资产类型），这里每个方框内容放多一些，有必要可以换行。
  他相当于对品种进行总结，可以每个品种一行，放上更多细节和总结，不要都凑到一行里，
  太拥挤了。这里的每期的项目看板，能不能按照条理归归类，比如按品种、银行聚类，
  进行简单区隔，不至于堆积。」

v8 用户/AI 点评 2 条（本轮）
---------------------------
  任务 A 筛选器（本轮最大件）：总览顶部加「年份 / 发起机构 / 品种切片」多选筛选条，
    选中集合变化 → 品种行（单数/发行合计/总结全文/16 项指标 + 4 项极值）、28 张卡片、
    数据质量热力格 全部按子集重算；空集显示「当前筛选无项目，请调整条件」。
    实现：状态 FLT{dim:{v:1}} + 统一入口 applyFilters()（O(28)，实测 ~37ms）；
         卡片/热力格用 data-key + .ov-flt-off 显隐（不重建节点，click 监听不丢）。
    维度来源：PROF 无 year/bank 字段 → year 由项目名「20xx 年」解析、bank 回退 PROF.issuer。
  任务 B 品种行版式：信息行四项（品种名/单数/发行合计/规模说明）同一水平线 →
    虚线 → 品种总结整行横排（100% 宽、行高 1.7）→ 关键指标 6 列 × 3 行。

v7 用户/AI 点评 2 条（已保留）
-----------------------------
  任务 1 关键指标下移、左贴框线；矩阵 3×i → 6 列 × j 行（16 项 → 6×3，末行 4 项）。
  任务 2 全文「简单平均」→「算术平均」。

v5 用户/AI 点评 5 条（已保留）
-----------------------------
  ① 首句「按品种分组、组内按发起机构归集」（一级分组是品种，银行是组内二级）。
  ② 每个均值标口径（算术平均 / 规模加权 / 笔均）+ 样本量 n；补中位数；
     全文不得出现不带口径的均值措辞（自检：去「算术平均」后无「平均」字样）。
  ③ 达成率歧义 加结论条「达成率＝资产池回收 ÷ 中债预测回收；与证券端本息兑付率不是一个口径，
     两者不矛盾」；达成率 <80% 且两档本金兑付率 ≥99.9% 的卡片加「证券端已兑付完毕」标记。
  ④ 数据质量 新增 28 单热力小格（缺项数 0/1/2/3 级 + tooltip 四列），数据从各 #view-pN
     的「⑦ 数据质量与风险提示」与「⑧ 数据质量与披露」fold 客户端提取（幂等）。
  ⑤ 语义色 品种色保持不变（不动全局配色），在提示条加「品种色为分类标识，不代表风险等级」。

已完成的历轮能力（须全部保留）
------------------------------
  · 品种分组色块 → 每个品种占一整行（子块顺序：.ov-bh → .ov-bsum → .ov-bk）
  · 28 单卡片按「品种 → 发起机构」聚类（3 品种组 + 14 银行小组），卡片 2 列 × 8 项
    （.ov-k 共 224）；移动 DOM 节点、不重建，click 监听完好
  · 折价率 → 证券化率（secRatio）；无「账户配平」；小数位 ≤4

实现要点
--------
  · **移动 DOM 节点，不重建**。宿主 select(view) 定义在其 IIFE 内部（window.select 不存在），
    重建 .ov-card 会丢失 click 监听；聚类只做 appendChild 搬运。
  · 幂等：.ov-grid[data-ov2=grouped]、.ov-dq 存在即跳过；提示条/数据质量块按存在性判断。
  · 补充块（提示条、数据质量块）用 createElement + innerHTML 注入，均在 #view-overview 内。

导出契约（见 00_ctx.py）
------------------------
    CSS  : str  —— 拼进 <style>（主题之后，靠 #view-overview 前缀压过主题 .ov-card/.vband）
    HTML : str  —— 空串（纯客户端增强，服务端无需渲染）
    JS   : str  —— 单个 IIFE，全部局部变量

单位规范（00_ctx.UNIT_POLICY）
------------------------------
    规模类 → 亿元 2 位（<0.01 亿用万元）；比率类 → 百分号 2 位；月数 1 位；缺失 → —
    期数 → 1 位（期数既可能是整数也可能是均值，统一 1 位；整数呈现为 x.0 期）
    小数位纪律：所有数值一律经 fmt()/_fmt() 单一入口，且任何数值小数位 ≤ 4（自检断言）

独立运行自检
------------
    python 10_overview.py        # 不依赖 build_v2.py；EXIT=0
"""
from __future__ import annotations

import json
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

# ── 路径（与 00_ctx 保持一致；不 import build_v2）──
_E = _HOME / "清算28单_不良ABS分析"
_V2 = _E / "脚本" / "v2"
_ASSET = _E / "设计资产"
_PAYLOAD = _ASSET / "payload_28.json"
# 客户端增强的宿主报告：build_v2.py 取 ORIG=单项目穿透报告（注意它在 _E 的**上一级**目录）；
# 合并版为历史宿主，兜底。
REPORTS = [
    _E.parent / "清算28单_单项目穿透" / "清算28单_单项目穿透_报告.html",
    _E / "清算28单_横向对照与逐单稽核_合并版.html",
]
REPORT = REPORTS[0]

# 可选的共享契约（仅自检用；缺失不影响导出）
_ctx = None
try:
    if str(_V2) not in sys.path:
        sys.path.insert(0, str(_V2))
    from importlib import import_module as _im

    _ctx = _im("00_ctx")
except Exception:  # pragma: no cover - 契约缺失时仍可独立运行
    _ctx = None


# ════════════════════════════════════════════════════════════════
# 口径表（Python 侧单一事实来源；JS 侧字段与之一致，自检时校验）
# ════════════════════════════════════════════════════════════════
FIELD_SPEC = [
    # (显示标签,  PROF 字段,      格式化,   是否关键指标(品种色强调))
    ("入池本息费", "poolTotal", "yi", False),
    ("累计回收", "recovered", "yi", False),
    ("回收率", "recRate", "pct", True),
    ("达成率", "vsForecast", "pct", False),
    ("发行规模", "issue", "yi", False),
    ("证券化率", "secRatio", "pct", False),
    ("优先档XIRR", "xirrSen", "pct", False),
    ("次级档XIRR", "xirrSub", "pct", True),
]
FOOT_SPEC = [
    ("支付期", "n_periods", "periods"),
    ("存续", "months", "months"),
    ("处置费率", "disposeFeeRate", "pct"),
]
FIELDS = [s[0] for s in FIELD_SPEC]
FOOT_FIELDS = [s[0] for s in FOOT_SPEC]
REMOVED = ["账户配平"]

# ── 任务 A：品种整行总结卡 ──
#   指标格 16 项（含 2 项中位数）+ 4 项点名格。
#   「平均」口径纪律：任何含「平均」的标签必须自带口径（算术平均 / 规模加权 / 笔均），
#   并在副行给出样本量 n；中位数单列一格。汇总只做客观统计，不写行业判断。
#   basis: sum=合计 | weighted=规模加权 | simple=算术平均 | median=中位数 | perdeal=笔均
BAND_METRICS = [
    # (显示标签,        格式化,  聚合取值键,        src,       品种色强调, basis)
    ("入池本息费", "yi", "poolSum", "sum", False, "sum"),
    ("累计回收", "yi", "recSum", "sum", False, "sum"),
    ("加权回收率", "pct", "recRate", "weighted", True, "weighted"),
    ("算术平均回收率", "pct", "recRate", "avg", False, "simple"),
    ("中位回收率", "pct", "recRate", "median", False, "median"),
    ("发行规模", "yi", "issueSum", "sum", False, "sum"),
    ("算术平均证券化率", "pct", "secRatio", "avg", False, "simple"),
    ("算术平均优先档XIRR", "pct", "xirrSen", "avg", False, "simple"),
    ("算术平均次级档XIRR", "pct", "xirrSub", "avg", True, "simple"),
    ("中位次级档XIRR", "pct", "xirrSub", "median", False, "median"),
    ("算术平均处置费率", "pct", "disposeFeeRate", "avg", False, "simple"),
    ("算术平均达成率", "pct", "vsForecast", "avg", False, "simple"),
    ("算术平均存续", "months", "months", "avg", False, "simple"),
    ("算术平均支付期数", "periods", "n_periods", "avg", False, "simple"),
    ("算术平均入池本息费", "yi", "poolTotal", "avg", False, "simple"),
    ("笔均发行规模", "yi", "issue", "avg", False, "perdeal"),
]
BAND_SPOT = [  # 组内极值（点名）
    ("回收率最高", "recRate", "max"),
    ("回收率最低", "recRate", "min"),
    ("次级档XIRR最高", "xirrSub", "max"),
    ("次级档XIRR最低", "xirrSub", "min"),
]
# 口径基中文说明（JS 侧 BASIS_TEXT 与之一致，自检时校验）
BASIS_TEXT = {
    "sum": "合计",
    "weighted": "规模加权",
    "simple": "算术平均",
    "median": "中位数",
    "perdeal": "笔均",
    "spot": "组内极值",
}
# 达成率与证券端兑付的口径提示（③）
VSF_NOTE = ("达成率＝资产池回收 ÷ 中债预测回收；与证券端本息兑付率不是一个口径，两者不矛盾。"
            "达成率低于 100% 仅表示资产池回收少于中债预测，不代表证券端本息未兑付。")
VSF_LOW = 0.8          # 达成率低于此值 → 卡片加「证券端已兑付完毕」标记
PAID_DONE = 0.999      # 优先档/次级档本金兑付率 ≥ 此值视为兑付完毕
# ① 总览首句（一级分组是品种，银行只是组内二级小组）
NOTE_TEXT = ("按品种分组、组内按发起机构归集的 28 单 KPI 速览"
             "（品种色仅作分类标识；卡片 chip 标注发起机构与品种）。"
             "点击任意卡片进入单项目八节穿透视图。")
# 语义色提示（⑤）
COLOR_NOTE = "品种色为分类标识，不代表风险等级。"
# 数据质量汇总脚注（④）
DQ_FOOT = ("缺项数取自各单「⑦ 核心结论·数据质量与风险提示」的披露项数；"
           "分级取自「⑧ 数据质量与披露」的 A 回源已补／B 报告确无／C 源文件缺失徽章。"
           "标记 * 表示该单披露涉及现金流补录或折现口径，可能影响 XIRR；悬停小格查看分项。")
# 数据质量热力分级（④）：缺项数 → 0/1/2/3 级
DQ_LEVELS = [(0, 0), (1, 1), (2, 1), (9, 2)]   # (缺项数上限, 级别)；>9 → 3
# 品种展示顺序（已知品种固定顺序，未知品种按 ORDER 首次出现追加）
CAT_ORDER = ["信用卡不良", "个人消费贷款", "个人经营贷款"]
CAT_COLOR = {"信用卡不良": "#A52524", "个人消费贷款": "#2D3955", "个人经营贷款": "#1F7A5C"}
ACC_FALLBACK = "#3B4A66"
# 汇总时视为「规模指标为空」的阈值：0 与 None 都排除，并在脚注里点名
POOL_EPS = 1.0


# ════════════════════════════════════════════════════════════════
# CSS
# ════════════════════════════════════════════════════════════════
CSS = r"""
/* ══════════ 10_overview · 总览看板（第二轮精修）══════════
   全部规则带 #view-overview 前缀（ID 特异性 > 主题 .ov-card/.vband/.ov-grid）。 */

/* ──────────────────────────────────────────────────────────────
   任务 A：.vbands 纵向堆叠，每个品种一整行（宽幅总结卡）
   ────────────────────────────────────────────────────────────── */
#view-overview .vbands{
  display:flex !important;
  flex-direction:column !important;
  gap:18px !important;
  grid-template-columns:none !important;
  margin:14px 0 6px !important;
}
#view-overview .vbands > .vband{
  position:relative;
  display:flex !important;
  flex-direction:column !important;
  gap:16px;
  width:100% !important;
  min-width:0 !important;
  padding:20px 24px 20px 26px !important;
  border:1px solid rgba(26,34,48,.08) !important;
  border-left:4px solid var(--ov-accent,#3B4A66) !important;
  border-radius:16px !important;
  background:
    radial-gradient(120% 160% at 0% 0%,
      color-mix(in srgb, var(--ov-accent,#3B4A66) 9%, transparent) 0%, transparent 58%),
    linear-gradient(180deg,#FFFFFF 0%,#FCFDFF 100%) !important;
  box-shadow:0 1px 2px rgba(16,24,40,.05), 0 14px 30px -22px rgba(16,24,40,.28) !important;
  overflow:hidden;
}
#view-overview .vbands > .vband.ov-v2::after{
  content:"";position:absolute;right:0;top:0;bottom:0;width:190px;pointer-events:none;
  background:linear-gradient(270deg,
    color-mix(in srgb, var(--ov-accent,#3B4A66) 7%, transparent) 0%, transparent 100%);
}
/* 顶行（v8）：品种名 │ 单数 │ 发行合计 │ 规模字段完整说明 —— 全部同一水平线 */
@media (max-width:820px){
  #view-overview .vbands > .vband{padding:18px !important;gap:14px}
}

/* A1 · 顶行：全部项目同一水平线（最后一项紧跟「发行合计」右侧） */
#view-overview .vband .ov-bh,
#view-overview .vband .ov-bk,
#view-overview .vband .ov-bsum{position:relative;z-index:1;min-width:0}
#view-overview .vband .ov-bh{
  display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;
  gap:0 12px;                /* 行间距 0，保证同一水平线 */
}
#view-overview .vband .ov-bname{
  font-family:var(--serif,Georgia,serif);
  font-size:20px;font-weight:700;line-height:1.24;letter-spacing:.4px;
  color:var(--ov-accent,#2A3446);overflow-wrap:anywhere;
}
#view-overview .vband .ov-bn{
  display:inline-block;font-size:12px;font-weight:700;line-height:1.7;
  padding:2px 12px;border-radius:999px;white-space:nowrap;
  color:var(--ov-accent,#3B4A66);
  background:color-mix(in srgb, var(--ov-accent,#3B4A66) 11%, #fff);
  border:1px solid color-mix(in srgb, var(--ov-accent,#3B4A66) 30%, transparent);
}
#view-overview .vband .ov-br{
  display:inline-block;font-size:11.5px;font-weight:600;line-height:1.7;
  padding:1px 10px;border-radius:999px;white-space:nowrap;
  color:var(--sub,#697487);background:var(--surface,#EDF1F6);
  border:1px solid rgba(26,34,48,.08);
}
/* 规模字段完整说明：紧跟「发行合计」右侧、同一行、字号更小、色更淡 */
#view-overview .vband .ov-bsub{
  display:inline-block;
  font-size:10.5px;line-height:1.7;letter-spacing:.1px;
  color:var(--mute,#98A2B3);white-space:nowrap;
}

/* A2 · 下移：关键指标区（左贴框线，6 列 × j 行） */
#view-overview .vband .ov-bk{
  display:flex;flex-direction:column;gap:9px;
  padding-left:0;            /* 与品种名/卡片左边框对齐，不留左侧空白 */
  align-self:stretch;
}
#view-overview .vband .ov-eyebrow{
  font-size:10.5px;font-weight:700;letter-spacing:1.1px;
  color:var(--mute,#98A2B3);text-transform:none;
  padding-left:2px;
}
/* 16 项指标 → 6 列 × 3 行（最后一行 4 项，grid 自动左对齐） */
#view-overview .vband .ov-bgrid{
  display:grid;
  grid-template-columns:repeat(6,minmax(0,1fr));
  gap:9px 10px;
}
/* 组内极值 4 格：沿用同一 6 列栅格，左对齐 */
#view-overview .vband .ov-bspot{
  display:grid;
  grid-template-columns:repeat(6,minmax(0,1fr));
  gap:9px 10px;
}
@media (max-width:1180px){
  #view-overview .vband .ov-bgrid,
  #view-overview .vband .ov-bspot{grid-template-columns:repeat(4,minmax(0,1fr)) !important}
}
@media (max-width:900px){
  #view-overview .vband .ov-bgrid,
  #view-overview .vband .ov-bspot{grid-template-columns:repeat(3,minmax(0,1fr)) !important}
}
@media (max-width:640px){
  #view-overview .vband .ov-bgrid,
  #view-overview .vband .ov-bspot{grid-template-columns:repeat(2,minmax(0,1fr)) !important}
}
#view-overview .vband .ov-bk-item{
  display:flex;flex-direction:column;gap:3px;min-width:0;
  padding:8px 10px 9px 11px;
  border-radius:11px;
  background:rgba(245,247,250,.72);
  border:1px solid rgba(26,34,48,.06);
  border-left:3px solid color-mix(in srgb, var(--ov-accent,#3B4A66) 34%, transparent);
}
#view-overview .vband .ov-bk-item .l{
  font-size:10.5px;letter-spacing:.2px;line-height:1.35;
  color:var(--sub,#79849A);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
/* 口径副行（算术平均 / 规模加权 / 中位数 / 合计 + 样本量 n） */
#view-overview .vband .ov-bk-item .b{
  font-size:9.5px;line-height:1.3;letter-spacing:.1px;
  color:var(--mute,#98A2B3);
  font-variant-numeric:tabular-nums;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;
}
#view-overview .vband .ov-bk-item.hi .b{color:var(--sub,#79849A)}
#view-overview .vband .ov-bk-item.spot .b{color:var(--mute,#98A2B3)}
#view-overview .vband .ov-bk-item .v{
  font-size:14px;font-weight:700;line-height:1.3;
  color:var(--ink,#1A2230);
  font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1;
  overflow-wrap:anywhere;
}
#view-overview .vband .ov-bk-item.hi{background:color-mix(in srgb, var(--ov-accent,#3B4A66) 8%, #fff)}
#view-overview .vband .ov-bk-item.hi .v{color:var(--ov-accent,#3B4A66)}
#view-overview .vband .ov-bk-item.spot{
  background:#fff;
  border-left-color:var(--ov-accent,#3B4A66);
}
#view-overview .vband .ov-bk-item.spot .v{font-size:12.5px;font-weight:600}
#view-overview .vband .ov-bk-item.spot .v em{font-style:normal;font-weight:700}

/* A3 · 虚线下方：品种总结（整行横排、不限宽、行高 1.7） */
#view-overview .vband .ov-bsum{
  display:flex;flex-direction:column;gap:6px;
  width:100%;max-width:100%;
  margin-top:2px;padding:11px 2px 2px 2px;
  border:0;border-top:1px dashed rgba(26,34,48,.16);
  border-radius:0;background:transparent;
}
#view-overview .vband .ov-bsum-h{
  font-size:10.5px;font-weight:700;letter-spacing:1.1px;
  color:var(--ov-accent,#3B4A66);
}
#view-overview .vband .ov-bsum p{
  margin:0;font-size:12.5px;line-height:1.7;
  color:var(--ink2,#38425A);text-align:justify;
  overflow-wrap:anywhere;
}
#view-overview .vband .ov-bsum b{
  font-weight:700;color:var(--ov-accent,#3B4A66);
  font-variant-numeric:tabular-nums;
}
#view-overview .vband .ov-bsum .nm{font-weight:700;color:var(--ink,#1A2230)}
#view-overview .vband .ov-bsum-note{
  margin:0;padding-top:8px;
  border-top:1px dashed color-mix(in srgb, var(--ov-accent,#3B4A66) 26%, transparent);
  font-size:10.5px;line-height:1.75;color:var(--mute,#98A2B3);
}

/* ──────────────────────────────────────────────────────────────
   任务 B：28 单卡片按「品种 → 银行」聚类，组间明显区隔
   ────────────────────────────────────────────────────────────── */
#view-overview .ov-grid{
  display:block !important;
  grid-template-columns:none !important;
  gap:0 !important;
  margin-top:22px !important;
}
#view-overview .ov-grid > .ov-cat-wrap{
  margin:0 0 34px 0;
  padding:0;
}
#view-overview .ov-grid > .ov-cat-wrap:last-child{margin-bottom:6px}
#view-overview .ov-grid > .ov-cat-wrap + .ov-cat-wrap{
  padding-top:26px;
  border-top:2px solid rgba(26,34,48,.09);
}

/* B1 · 品种组头 */
#view-overview .ov-cat-hd{
  display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;
  padding:13px 18px 13px 16px;
  border-radius:14px;
  border:1px solid color-mix(in srgb, var(--ov-accent,#3B4A66) 24%, transparent);
  border-left:5px solid var(--ov-accent,#3B4A66);
  background:linear-gradient(96deg,
    color-mix(in srgb, var(--ov-accent,#3B4A66) 13%, #fff) 0%,
    rgba(255,255,255,.94) 62%);
}
#view-overview .ov-cat-hd .ov-ch-t{
  font-family:var(--serif,Georgia,serif);
  font-size:17px;font-weight:700;letter-spacing:.4px;
  color:var(--ov-accent,#2A3446);
}
#view-overview .ov-cat-hd .ov-ch-n,
#view-overview .ov-cat-hd .ov-ch-s{
  display:inline-block;font-size:11.5px;font-weight:600;line-height:1.7;
  padding:2px 11px;border-radius:999px;white-space:nowrap;
  font-variant-numeric:tabular-nums;
}
#view-overview .ov-cat-hd .ov-ch-n{
  color:var(--ov-accent,#3B4A66);
  background:color-mix(in srgb, var(--ov-accent,#3B4A66) 12%, #fff);
  border:1px solid color-mix(in srgb, var(--ov-accent,#3B4A66) 30%, transparent);
}
#view-overview .ov-cat-hd .ov-ch-s{
  margin-left:auto;
  color:var(--ink2,#4B5566);background:rgba(255,255,255,.9);
  border:1px solid rgba(26,34,48,.1);
}
#view-overview .ov-cat-hd .ov-ch-s em{font-style:normal;color:var(--mute,#98A2B3);font-weight:600;margin-right:5px}

/* B2 · 银行小组分隔标签 */
#view-overview .ov-bank-hd{
  display:flex;align-items:center;gap:10px;
  margin:16px 0 11px 2px;
  font-size:12.5px;font-weight:700;letter-spacing:.3px;
  color:var(--ink2,#4B5566);
}
#view-overview .ov-bank-hd .ov-bh-bar{
  flex:0 0 16px;height:2px;border-radius:2px;
  background:color-mix(in srgb, var(--ov-accent,#3B4A66) 62%, transparent);
}
#view-overview .ov-bank-hd .ov-bh-n{
  font-size:11px;font-weight:600;color:var(--sub,#697487);
  padding:1px 9px;border-radius:999px;
  background:var(--surface,#EDF1F6);border:1px solid rgba(26,34,48,.07);
}
#view-overview .ov-bank-hd::after{
  content:"";flex:1 1 auto;height:1px;
  background:linear-gradient(90deg, rgba(26,34,48,.11) 0%, rgba(26,34,48,0) 100%);
}
#view-overview .ov-cat-wrap .ov-cat-hd + .ov-bank-hd{margin-top:15px}

/* B3 · 组内卡片栅格：保持每行 3 张 */
#view-overview .ov-cards{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:18px;
  align-items:stretch;
}
@media (max-width:1100px){
  #view-overview .ov-cards{grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:16px}
}
@media (max-width:700px){
  #view-overview .ov-cards{grid-template-columns:minmax(0,1fr) !important;gap:14px}
}

/* ──────────────────────────────────────────────────────────────
   第一轮卡片本体（保持不动；选择器由 .ov-grid > 放宽为 .ov-card，
   因为卡片现在嵌在 .ov-cards 里）
   ────────────────────────────────────────────────────────────── */
#view-overview .ov-card.ov-v2{
  position:relative;
  display:flex;
  flex-direction:column;
  padding:0 !important;
  border:1px solid rgba(26,34,48,.075) !important;
  border-top:1px solid rgba(26,34,48,.075) !important;
  border-radius:16px !important;
  background:
    radial-gradient(128% 92% at 100% 0%,
      color-mix(in srgb, var(--ov-accent) 12%, transparent) 0%, transparent 64%),
    linear-gradient(180deg,#FFFFFF 0%,#FDFEFF 100%);
  box-shadow:0 1px 2px rgba(16,24,40,.05), 0 10px 22px -16px rgba(16,24,40,.22);
  overflow:hidden;
  cursor:pointer;
  transition:transform .32s var(--ease,cubic-bezier(.16,.68,.42,1)),
             box-shadow .32s var(--ease,cubic-bezier(.16,.68,.42,1)),
             border-color .32s var(--ease,cubic-bezier(.16,.68,.42,1));
}
/* 左侧品种色边条 */
#view-overview .ov-card.ov-v2::before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:4px;z-index:2;
  background:linear-gradient(180deg,
    var(--ov-accent) 0%,
    color-mix(in srgb, var(--ov-accent) 40%, transparent) 100%);
}
/* 顶部渐隐品种色 */
#view-overview .ov-card.ov-v2::after{
  content:"";position:absolute;left:0;right:0;top:0;height:76px;pointer-events:none;
  background:linear-gradient(180deg,
    color-mix(in srgb, var(--ov-accent) 10%, transparent) 0%, transparent 100%);
}
#view-overview .ov-card.ov-v2:hover{
  transform:translateY(-2px);
  border-color:color-mix(in srgb, var(--ov-accent) 52%, transparent) !important;
  box-shadow:0 2px 4px rgba(16,24,40,.06),
             0 18px 34px -18px color-mix(in srgb, var(--ov-accent) 40%, rgba(16,24,40,.35));
}
#view-overview .ov-card.ov-v2:focus-visible{
  outline:2px solid color-mix(in srgb, var(--ov-accent) 62%, transparent);
  outline-offset:2px;
}

/* 卡片标题行 */
#view-overview .ov-v2 .ov-hd{
  position:relative;z-index:1;
  display:flex;gap:11px;align-items:stretch;
  padding:17px 18px 14px 21px;
  border-bottom:1px solid rgba(26,34,48,.055);
}
#view-overview .ov-v2 .ov-bar{
  flex:0 0 3px;border-radius:999px;min-height:38px;opacity:.95;
}
#view-overview .ov-v2 .ov-ht{flex:1 1 auto;min-width:0}
#view-overview .ov-v2 .oname{
  font-family:var(--serif,Georgia,serif);
  font-size:15.5px;font-weight:700;line-height:1.34;
  letter-spacing:.2px;color:var(--ink,#1A2230);
  overflow-wrap:anywhere;
}
#view-overview .ov-v2 .ov-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
#view-overview .ov-v2 .obank,
#view-overview .ov-v2 .vchip{
  display:inline-block;font-size:10.5px;font-weight:600;line-height:1.65;
  padding:1px 9px;border-radius:9px;white-space:nowrap;
}
#view-overview .ov-v2 .obank{
  color:var(--ink2,#4B5566) !important;
  background:var(--surface,#F5F7FA) !important;
  border:1px solid rgba(26,34,48,.09) !important;
  margin-top:0 !important;
}
#view-overview .ov-v2 .vchip{
  color:var(--ov-accent,#3B4A66) !important;
  background:color-mix(in srgb, var(--ov-accent,#3B4A66) 10%, #fff) !important;
  border:1px solid color-mix(in srgb, var(--ov-accent,#3B4A66) 26%, transparent) !important;
}
/* ③ 达成率 < 80% 的卡片：中性标记「证券端已兑付完毕」（避免被误读为未兑付） */
#view-overview .ov-v2 .obadge{
  display:inline-block;font-size:10px;font-weight:600;line-height:1.65;
  padding:1px 8px;border-radius:9px;white-space:nowrap;
  color:#31506B;background:#EDF3F8;border:1px dashed #B9CBDA;
  cursor:help;
}

/* 2 列 × 4 行 信息栅格 */
#view-overview .ov-v2 .ov-body{
  position:relative;z-index:1;
  flex:1 1 auto;
  display:grid;
  grid-template-columns:1fr 1fr;
  padding:6px 16px 4px 16px;
}
#view-overview .ov-v2 .ov-k{
  display:flex;align-items:baseline;justify-content:space-between;gap:9px;
  min-width:0;
  padding:9px 12px 8px 6px;
  border-bottom:1px dashed rgba(26,34,48,.07);
}
#view-overview .ov-v2 .ov-k:nth-child(even){
  padding-left:15px;
  border-left:1px solid rgba(26,34,48,.065);
}
#view-overview .ov-v2 .ov-k:nth-last-child(-n+2){border-bottom:none}
#view-overview .ov-v2 .ov-kl{
  font-size:11px;letter-spacing:.2px;white-space:nowrap;
  color:var(--sub,#79849A);
}
#view-overview .ov-v2 .ov-kv{
  font-size:13.5px;font-weight:600;white-space:nowrap;
  color:var(--ink,#1A2230);
  font-variant-numeric:tabular-nums;
  font-feature-settings:"tnum" 1;
}
#view-overview .ov-v2 .ov-k.hi .ov-kv{color:var(--ov-accent,#3B4A66)}
#view-overview .ov-v2 .ov-k.hi .ov-kl{color:var(--ink2,#4B5566)}

/* 底部 meta 条（支付期 / 存续 / 处置费率） */
#view-overview .ov-v2 .ov-foot{
  margin-top:auto;
  display:flex;flex-wrap:wrap;align-items:center;gap:5px 16px;
  padding:11px 18px 13px 21px;
  border-top:1px solid rgba(26,34,48,.06);
  background:linear-gradient(180deg, rgba(245,247,250,0) 0%, rgba(245,247,250,.72) 100%);
  font-size:11px;color:var(--ink3,#79849A);
  font-variant-numeric:tabular-nums;
}
#view-overview .ov-v2 .ov-foot .ov-fk{display:inline-flex;align-items:baseline;gap:5px;white-space:nowrap}
#view-overview .ov-v2 .ov-foot em{font-style:normal;color:var(--ink4,#A6AFBE)}
#view-overview .ov-v2 .ov-foot b{font-weight:600;color:var(--ink2,#4B5566)}

/* ──────────────────────────────────────────────────────────────
   v8 · 筛选条（年份 / 发起机构 / 品种切片，多选，选中即重算下方全部内容）
   风格：墨色 + 纸面 + 细线；与提示条同一视觉体系
   ────────────────────────────────────────────────────────────── */
#view-overview .ov-flt{
  display:flex;flex-direction:column;gap:7px;
  margin:14px 0 2px;padding:11px 14px 12px 14px;
  border:1px solid rgba(26,34,48,.1);border-radius:14px;
  background:linear-gradient(180deg,#FDFEFF 0%,#F7F9FC 100%);
}
#view-overview .ov-flt-hd{
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
}
#view-overview .ov-flt-t{
  font-size:11.5px;font-weight:700;letter-spacing:.8px;color:#4B5566;
  padding-left:1px;
}
#view-overview .ov-flt-hit{
  font-size:11.5px;font-weight:700;line-height:1.7;color:#2A3446;
  padding:0 10px;border-radius:999px;
  background:#EDF1F6;border:1px solid rgba(26,34,48,.09);
  font-variant-numeric:tabular-nums;
}
#view-overview .ov-flt-reset{
  margin-left:auto;
  font:inherit;font-size:11px;line-height:1.8;color:#697487;
  padding:0 11px;border-radius:999px;cursor:pointer;
  background:#fff;border:1px solid rgba(26,34,48,.14);
}
#view-overview .ov-flt-reset:hover{color:#2A3446;border-color:rgba(26,34,48,.3)}
#view-overview .ov-flt-row{
  display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding-top:6px;border-top:1px solid rgba(26,34,48,.055);
}
#view-overview .ov-flt-row:first-of-type{border-top:0;padding-top:2px}
#view-overview .ov-flt-lab{
  flex:0 0 58px;font-size:11px;font-weight:700;letter-spacing:.5px;color:#98A2B3;
}
#view-overview .ov-flt-chips{display:flex;flex-wrap:wrap;gap:6px;min-width:0}
#view-overview .ov-flt-c{
  font:inherit;font-size:11.5px;line-height:1.85;cursor:pointer;
  padding:0 9px;border-radius:999px;white-space:nowrap;
  color:#38425A;background:#fff;
  border:1px solid rgba(26,34,48,.13);
  transition:background .16s var(--ease,cubic-bezier(.16,.68,.42,1)),
             border-color .16s var(--ease,cubic-bezier(.16,.68,.42,1)),
             color .16s var(--ease,cubic-bezier(.16,.68,.42,1));
}
#view-overview .ov-flt-c:hover{border-color:rgba(26,34,48,.3)}
#view-overview .ov-flt-c .kc{
  font-size:10px;font-weight:600;color:#98A2B3;margin-left:4px;
  font-variant-numeric:tabular-nums;
}
#view-overview .ov-flt-c[aria-pressed="true"]{
  color:#fff;background:#2D3955;border-color:#2D3955;font-weight:700;
}
#view-overview .ov-flt-c[aria-pressed="true"] .kc{color:rgba(255,255,255,.72)}
#view-overview .ov-flt-c[aria-pressed="false"] .kc{color:#A6AFBE}
#view-overview .ov-flt-all{
  font:inherit;font-size:10.5px;line-height:1.8;cursor:pointer;
  padding:0 8px;border-radius:6px;color:#697487;
  background:transparent;border:1px dashed rgba(26,34,48,.2);
}
#view-overview .ov-flt-all:hover{color:#2A3446;border-color:rgba(26,34,48,.36)}
/* 清空：仅该维有选中时出现 */
#view-overview .ov-flt-clr{
  display:none;
  font:inherit;font-size:10.5px;line-height:1.8;cursor:pointer;
  padding:0 8px;border-radius:6px;color:#A52524;
  background:transparent;border:1px dashed rgba(165,37,36,.32);
}
#view-overview .ov-flt-clr.on{display:inline-block}
#view-overview .ov-flt-clr:hover{border-color:rgba(165,37,36,.6);background:rgba(165,37,36,.05)}
#view-overview .ov-flt-cnt{
  font-size:10.5px;color:#A6AFBE;letter-spacing:.2px;
  font-variant-numeric:tabular-nums;margin-left:2px;
}
#view-overview .ov-flt-cnt.on{color:#2D3955;font-weight:700}
#view-overview .ov-flt-tip{
  font-size:10.5px;line-height:1.7;color:#A6AFBE;
}
@media (prefers-reduced-motion: reduce){
  #view-overview .ov-flt-c{transition:none !important}
}

/* 筛选隐藏 / 空态 */
#view-overview .ov-flt-off{display:none !important}
#view-overview .ov-empty{
  margin:16px 0 6px;padding:26px 18px;text-align:center;
  border:1px dashed rgba(26,34,48,.18);border-radius:14px;
  background:#FBFCFE;color:#697487;font-size:12.5px;line-height:1.8;
}
#view-overview .ov-empty b{color:#2A3446;font-weight:700}

/* ──────────────────────────────────────────────────────────────
   口径提示条（③ 达成率≠证券兑付率 / ⑤ 语义色）
   ────────────────────────────────────────────────────────────── */
#view-overview .ov-ovnote{
  display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:12px;
  margin:14px 0 4px;
}
@media (max-width:900px){#view-overview .ov-ovnote{grid-template-columns:minmax(0,1fr)}}
#view-overview .ov-ovnote .ov-ni{
  display:flex;gap:10px;align-items:flex-start;
  padding:11px 15px 12px 14px;
  border-radius:12px;
  background:linear-gradient(180deg,#FBFCFE 0%,#F6F8FB 100%);
  border:1px solid rgba(26,34,48,.09);
  border-left:3px solid #8A94A6;
}
#view-overview .ov-ovnote .ov-ni:last-child{border-left-color:#A9B2C0}
#view-overview .ov-ovnote .ov-ntag{
  flex:0 0 auto;font-size:10px;font-weight:700;line-height:1.9;
  letter-spacing:.4px;color:#4B5566;
  padding:0 8px;border-radius:6px;white-space:nowrap;
  background:rgba(26,34,48,.07);
}
#view-overview .ov-ovnote p{
  margin:0;font-size:11.5px;line-height:1.78;color:var(--ink2,#4B5566);text-align:justify;
}

/* ──────────────────────────────────────────────────────────────
   ④ 数据质量汇总（28 单热力小格）
   ────────────────────────────────────────────────────────────── */
#view-overview .ov-dq{
  margin:26px 0 4px;
  padding:15px 17px 16px;
  border-radius:14px;
  border:1px solid rgba(26,34,48,.09);
  background:linear-gradient(180deg,#FDFEFF 0%,#F7F9FC 100%);
}
#view-overview .ov-dq-hd{
  display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:12px;
}
#view-overview .ov-dq-t{
  font-family:var(--serif,Georgia,serif);
  font-size:15px;font-weight:700;letter-spacing:.3px;color:var(--ink,#1A2230);
}
#view-overview .ov-dq-n{
  font-size:11px;font-weight:600;color:var(--sub,#697487);
  padding:1px 9px;border-radius:999px;
  background:var(--surface,#EDF1F6);border:1px solid rgba(26,34,48,.07);
  font-variant-numeric:tabular-nums;
}
#view-overview .ov-dq-sum{
  margin-left:auto;font-size:11px;color:var(--sub,#697487);line-height:1.7;
  font-variant-numeric:tabular-nums;
}
#view-overview .ov-dq-legend{
  display:flex;align-items:center;gap:6px;font-size:10px;color:var(--mute,#98A2B3);
}
#view-overview .ov-dq-legend i{
  font-style:normal;display:inline-block;width:11px;height:11px;border-radius:3px;
  border:1px solid rgba(26,34,48,.12);
}
#view-overview .ov-dq-legend i.lv0{background:#DFF0E6}
#view-overview .ov-dq-legend i.lv1{background:#F2EBD6}
#view-overview .ov-dq-legend i.lv2{background:#F6DCC9}
#view-overview .ov-dq-legend i.lv3{background:#EFC9C7}
#view-overview .ov-dq-grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(116px,1fr));gap:6px;
}
#view-overview .ov-dq-c{
  display:flex;align-items:baseline;justify-content:space-between;gap:6px;
  min-width:0;padding:6px 8px 7px 8px;border-radius:8px;
  border:1px solid rgba(26,34,48,.07);
  background:#fff;cursor:help;
  transition:transform .18s var(--ease,cubic-bezier(.16,.68,.42,1)),box-shadow .18s var(--ease);
}
#view-overview .ov-dq-c:hover{transform:translateY(-1px);box-shadow:0 3px 10px -4px rgba(16,24,40,.24)}
#view-overview .ov-dq-c .nm{
  font-size:10px;line-height:1.35;color:var(--ink2,#4B5566);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;
}
#view-overview .ov-dq-c .n{
  flex:0 0 auto;font-size:10px;font-weight:700;line-height:1.5;
  font-variant-numeric:tabular-nums;color:var(--ink,#1A2230);
}
#view-overview .ov-dq-c.lv0{background:#F1F8F4;border-color:#CDE6D8}
#view-overview .ov-dq-c.lv1{background:#FCF8EC;border-color:#EADFC2}
#view-overview .ov-dq-c.lv2{background:#FCF1E9;border-color:#EFD3BE}
#view-overview .ov-dq-c.lv3{background:#FBEBEA;border-color:#EDCFCC}
#view-overview .ov-dq-c.afx{box-shadow:inset 0 0 0 1px rgba(165,37,36,.32)}
#view-overview .ov-dq-c .fx{
  font-size:9px;font-weight:700;color:#A52524;letter-spacing:.2px;
}
#view-overview .ov-dq-foot{
  margin-top:9px;font-size:10px;line-height:1.7;color:var(--mute,#98A2B3);
}

@media (prefers-reduced-motion: reduce){
  #view-overview .ov-card.ov-v2{transition:none !important}
  #view-overview .ov-card.ov-v2:hover{transform:none !important}
  #view-overview .ov-dq-c{transition:none !important}
  #view-overview .ov-dq-c:hover{transform:none !important}
}
"""


# ════════════════════════════════════════════════════════════════
# HTML（纯客户端增强，服务端无需渲染）
# ════════════════════════════════════════════════════════════════
HTML = ""


# ════════════════════════════════════════════════════════════════
# JS（单个 IIFE：不向外部作用域声明任何变量）
#   · 分三段：① 数值/格式化工具与聚合  ② 品种整行总结卡重绘  ③ 28 单聚类搬运
#   · 全程只做 innerHTML 重绘（卡片自身内容）+ appendChild 搬运（聚类），
#     不重建 .ov-card 节点本身 → 原报告既有 click 监听完好。
# ════════════════════════════════════════════════════════════════
JS = r"""
(function(){
  var V = window.__V2;
  if (!V || !V.PROF || !V.ORDER) return;

  var ORDER = V.ORDER;
  var ACC_FALLBACK = '#3B4A66';
  var CAT_ORDER = ['信用卡不良', '个人消费贷款', '个人经营贷款'];
  var POOL_EPS = 1.0;

  /* ══════════ ① 工具 ══════════
     小数位纪律（依 00_ctx.UNIT_POLICY，单一入口 + 防御性四舍五入）：
       金额类 yi       → 2 位（万 / 亿）
       比率类 pct      → 2 位（百分号）
       月数   months   → 1 位
       期数   periods  → 1 位（期数既可能是整数也可能是均值，统一 1 位；
                                整数会呈现为 x.0 期，见模块说明）
     一律走 fmt(); fmt() 内部再按 kind 夹一次小数位，
     避免任何未格式化的原始浮点（如 12.26086956521739）漏进 DOM。 */
  var PRECISION = { yi: 2, pct: 2, months: 1, periods: 1 };
  var MAX_DECIMALS = 4;                                   /* 自检上限：任何数值小数位 ≤ 4 */

  /* ══════════ ⓪ 文案与阈值常量（与 Python 侧同名常量一致，自检时校验）══════════
     ① 首句更正：一级分组是「品种」，银行只是组内二级小组。
     ③ 达成率与证券端兑付率口径不同，需明示。
     ⑤ 品种色属分类标识，非风险等级。 */
  var NOTE_TEXT = '按品种分组、组内按发起机构归集的 28 单 KPI 速览' +
                  '（品种色仅作分类标识；卡片 chip 标注发起机构与品种）。' +
                  '点击任意卡片进入单项目八节穿透视图。';
  var VSF_NOTE = '达成率＝资产池回收 ÷ 中债预测回收；与证券端本息兑付率不是一个口径，两者不矛盾。' +
                 '达成率低于 100% 仅表示资产池回收少于中债预测，不代表证券端本息未兑付。';
  var COLOR_NOTE = '品种色为分类标识，不代表风险等级。';
  var VSF_LOW = 0.8;          /* 达成率低于此值 → 卡片加「证券端已兑付完毕」标记 */
  var PAID_DONE = 0.999;      /* 优先档 / 次级档本金兑付率 ≥ 此值视为兑付完毕 */
  var DQ_FOOT = '缺项数取自各单「⑦ 核心结论·数据质量与风险提示」的披露项数；' +
                '分级取自「⑧ 数据质量与披露」的 A 回源已补／B 报告确无／C 源文件缺失徽章。' +
                '标记 * 表示该单披露涉及现金流补录或折现口径，可能影响 XIRR；悬停小格查看分项。';
  function has(v){ return v !== null && v !== undefined && v !== '' && !(typeof v === 'number' && !isFinite(v)); }
  function num(v){ return has(v) ? +v : null; }
  function toFixedSafe(v, d){
    if (!has(v)) return '—';
    var x = +v;
    if (!isFinite(x)) return '—';
    var r = (+x).toFixed(d);
    return (parseFloat(r) === 0) ? (0).toFixed(d) : r;   /* 消除 -0.00 */
  }
  function yi(v){
    if (!has(v)) return '—';
    return toFixedSafe(+v / (Math.abs(+v) < 1e6 ? 1e4 : 1e8), PRECISION.yi) +
           (Math.abs(+v) < 1e6 ? ' 万' : ' 亿');
  }
  function pct(v){ return has(v) ? toFixedSafe(+v * 100, PRECISION.pct) + '%' : '—'; }
  function periods(v){ return has(v) ? toFixedSafe(v, PRECISION.periods) + ' 期' : '—'; }
  function months(v){ return has(v) ? toFixedSafe(v, PRECISION.months) + ' 个月' : '—'; }
  function fmt(kind, v){
    if (kind === 'yi') return yi(v);
    if (kind === 'pct') return pct(v);
    if (kind === 'months') return months(v);
    if (kind === 'periods') return periods(v);
    /* 兜底：未知 kind 也必须限位，绝不原样输出浮点 */
    return has(v) ? toFixedSafe(v, PRECISION.yi) : '—';
  }
  function esc(s){
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, function(c){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];
    });
  }
  function nameOf(p){ return p.short || p.name || p.code || '—'; }
  /* 归一化：去空白（品种行文本与 PROF.cat 同源，仅差空白） */
  function norm(s){ return String(s === null || s === undefined ? '' : s).replace(/\s+/g, ''); }

  /* ══════════ ② 聚合（口径：规模类加权、比率类算术平均，均跳过空值）═ */
  function sumOf(rows, key){
    var s = 0, n = 0;
    for (var i = 0; i < rows.length; i++){
      var v = num(rows[i][key]);
      if (v === null) continue;
      s += v; n++;
    }
    return { s: s, n: n };
  }
  function avgOf(rows, key){
    var t = sumOf(rows, key);
    return (t.n > 0) ? (t.s / t.n) : null;
  }
  /* 单项最大/最小：返回 {p, v}，入池规模缺失的样本不参与评选 */
  function extreme(rows, key, dir){
    var b = null, bv = null;
    for (var i = 0; i < rows.length; i++){
      var p = rows[i];
      var v = num(p[key]);
      if (v === null) continue;
      if (dir === 'max' && !(num(p.poolTotal) > POOL_EPS)) continue;
      if (bv === null || (dir === 'max' ? v > bv : v < bv)){ b = p; bv = v; }
    }
    return (b === null) ? null : { p: b, v: bv };
  }

  /* 中位数：返回 {v, n}；requirePool 时剔除入池规模缺失样本（回收率/证券化率派生自入池） */
  function medianOf(rows, key, requirePool){
    var xs = [];
    for (var i = 0; i < rows.length; i++){
      var p = rows[i];
      var v = num(p[key]);
      if (v === null) continue;
      if (requirePool && !(num(p.poolTotal) > POOL_EPS)) continue;
      xs.push(v);
    }
    if (!xs.length) return { v: null, n: 0 };
    xs.sort(function(a, b){ return a - b; });
    var m = xs.length >> 1;
    return { v: (xs.length % 2) ? xs[m] : (xs[m - 1] + xs[m]) / 2, n: xs.length };
  }

  /* 参与「算术平均」口径的字段（须与 Python 侧 AVG_KEYS 一致） */
  var AVG_KEYS = ['recRate', 'secRatio', 'xirrSen', 'xirrSub', 'vsForecast',
                  'disposeFeeRate', 'months', 'n_periods'];
  /* 参与「中位数」口径的字段 */
  var MEDIAN_KEYS = ['recRate', 'xirrSub'];

  function agg(rows){
    var issue = sumOf(rows, 'issue');
    var pool = sumOf(rows, 'poolTotal');
    var rec = sumOf(rows, 'recovered');
    var valid = 0, noPool = [], noSec = [], noMonths = [];
    for (var i = 0; i < rows.length; i++){
      var p = rows[i];
      var okPool = num(p.poolTotal) > POOL_EPS;
      if (okPool) valid++;
      else noPool.push(nameOf(p));
      if (num(p.secRatio) === null) noSec.push(nameOf(p));
      if (num(p.months) === null) noMonths.push(nameOf(p));
    }
    /* 算术平均 + 各指标有效样本数 n */
    var avg = {}, avgN = {};
    for (var ai = 0; ai < AVG_KEYS.length; ai++){
      var ak = AVG_KEYS[ai], t = sumOf(rows, ak);
      avg[ak] = (t.n > 0) ? (t.s / t.n) : null;
      avgN[ak] = t.n;
    }
    avg.poolTotal = (pool.n > 0) ? (pool.s / pool.n) : null;  avgN.poolTotal = pool.n;
    avg.issue     = (issue.n > 0) ? (issue.s / issue.n) : null; avgN.issue = issue.n;
    avg.recovered = (rec.n > 0) ? (rec.s / rec.n) : null;    avgN.recovered = rec.n;
    /* 中位数 */
    var med = {};
    for (var mi = 0; mi < MEDIAN_KEYS.length; mi++){
      med[MEDIAN_KEYS[mi]] = medianOf(rows, MEDIAN_KEYS[mi],
                                      MEDIAN_KEYS[mi] === 'recRate');
    }
    return {
      n: rows.length,
      valid: valid,
      issueSum: issue.s,
      poolSum: pool.s,
      recSum: rec.s,
      avg: avg,
      avgN: avgN,
      med: med,
      /* 加权回收率 = Σ累计回收 / Σ入池本息费；n = 有入池本息费的单数 */
      recWeighted: (pool.s > 0) ? (rec.s / pool.s) : null,
      recWeightedN: pool.n,
      recMax: extreme(rows, 'recRate', 'max'),
      recMin: extreme(rows, 'recRate', 'min'),
      subMax: extreme(rows, 'xirrSub', 'max'),
      subMin: extreme(rows, 'xirrSub', 'min'),
      noPool: noPool,
      noSec: noSec,
      noMonths: noMonths
    };
  }

  /* 口径副行：算术平均 / 规模加权 / 中位数 / 合计 / 笔均 + 样本量 */
  function basisText(basis, n){
    if (basis === 'sum') return '合计';
    var lab = BASIS_TEXT[basis] || '';
    return (n === null || n === undefined) ? lab : (lab + ' · n=' + n);
  }

  /* ══════════ ③ 品种整行总结卡：16 格指标 + 4 格点名 + 3 句总结 ══════════
     措辞纪律：均值一律写作「算术平均」或「规模加权」，并带样本量 n；
     不得出现不带口径的均值措辞（自检断言：去「算术平均」后全文无均值字样）。 */
  function summaryText(cat, a){
    var s1 = cat + '共 ' + a.n + ' 单，合计发行规模 ' + yi(a.issueSum) + '，' +
             '合计入池本息费 ' + yi(a.poolSum) + '，合计累计回收 ' + yi(a.recSum) + '；' +
             '规模加权回收率 ' + pct(a.recWeighted) + '（Σ回收÷Σ入池本息费，n=' + a.recWeightedN + '）、' +
             '算术平均回收率 ' + pct(a.avg.recRate) + '（n=' + a.avgN.recRate + '）、' +
             '中位回收率 ' + pct(a.med.recRate.v) + '（n=' + a.med.recRate.n + '）。';
    var s2 = '算术平均处置费率 ' + pct(a.avg.disposeFeeRate) + '（n=' + a.avgN.disposeFeeRate + '）、' +
             '算术平均证券化率 ' + pct(a.avg.secRatio) + '（n=' + a.avgN.secRatio + '）、' +
             '算术平均达成率 ' + pct(a.avg.vsForecast) + '（n=' + a.avgN.vsForecast + '）、' +
             '算术平均优先档XIRR ' + pct(a.avg.xirrSen) + '（n=' + a.avgN.xirrSen + '）、' +
             '算术平均次级档XIRR ' + pct(a.avg.xirrSub) + '（n=' + a.avgN.xirrSub + '）；' +
             '算术平均存续 ' + months(a.avg.months) + '（n=' + a.avgN.months + '）、' +
             '算术平均支付期数 ' + (a.avg.n_periods === null ? '—'
               : (+a.avg.n_periods).toFixed(1) + ' 期') + '（n=' + a.avgN.n_periods + '）。';
    var d1 = (a.recMax && a.recMin)
      ? ('组内回收率最高 ' + a.recMax.p.short + '（' + pct(a.recMax.v) + '），最低 ' +
         a.recMin.p.short + '（' + pct(a.recMin.v) + '）。')
      : '组内回收率最高/最低项：—。';
    var d2 = (a.subMax && a.subMin)
      ? ('次级档XIRR 最高 ' + a.subMax.p.short + '（' + pct(a.subMax.v) + '），最低 ' +
         a.subMin.p.short + '（' + pct(a.subMin.v) + '）。')
      : '次级档XIRR 最高/最低项：—。';
    return [s1, s2, d1 + d2];
  }

  function noteText(a){
    var xs = [];
    if (a.noPool.length) xs.push('本息费未披露 ' + a.noPool.length + ' 单（' + a.noPool.join('、') +
      '），其回收率与证券化率不计入算术平均与中位数');
    if (a.noSec.length) xs.push('证券化率未披露 ' + a.noSec.length + ' 单（' + a.noSec.join('、') + '）');
    if (a.noMonths.length) xs.push('存续月数未披露 ' + a.noMonths.length + ' 单（' + a.noMonths.join('、') + '）');
    return xs.length ? ('口径说明：' + xs.join('；') + '。') : '';
  }

  function bandInner(cat, rows){
    var a = agg(rows);
    var parts = summaryText(cat, a);
    var note = noteText(a);
    var out = [];

    /* 顶行（v8）：品种名 │ 单数 │ 发行合计 │ 规模字段完整说明 —— 全部同一水平线，
       最后一项紧跟「发行合计」右侧 */
    out.push('<div class="ov-bh">');
    out.push('<div class="ov-bname">' + esc(cat) + '</div>');
    out.push('<span class="ov-bn">' + a.n + ' 单</span>');
    out.push('<span class="ov-br">发行合计 ' + yi(a.issueSum) + '</span>');
    out.push('<span class="ov-bsub">' + a.valid + ' 单规模字段完整；比率口径见每格副行</span>');
    out.push('</div>');

    /* 虚线下方：品种总结整行横排（占满整行，行高 1.7） */
    out.push('<div class="ov-bsum">');
    out.push('<div class="ov-bsum-h">品种总结</div>');
    out.push('<p>' + parts.map(function(t){ return esc(t); }).join('') + '</p>');
    if (note) out.push('<p class="ov-bsum-note">' + esc(note) + '</p>');
    out.push('</div>');

    /* 关键指标区 6 列 × 3 行（16 项），左贴框线 */
    out.push('<div class="ov-bk">');
    out.push('<div class="ov-eyebrow">关键指标（每格标注口径与样本量）</div>');
    out.push('<div class="ov-bgrid">');
    for (var i = 0; i < METRICS.length; i++){
      var m = METRICS[i];                       /* [label, kind, key, src, hi, basis] */
      var v = metricValue(a, m[2], m[3]);
      var n = metricN(a, m[2], m[3]);
      out.push('<div class="ov-bk-item' + (m[4] || '') + '">' +
               '<span class="l">' + esc(m[0]) + '</span>' +
               '<span class="v">' + esc(fmt(m[1], v)) + '</span>' +
               '<span class="b">' + esc(basisText(m[5], n)) + '</span></div>');
    }
    out.push('</div>');
    /* 组内极值 4 格：同 6 列栅格，左对齐 */
    out.push('<div class="ov-bspot">');
    var spots = [a.recMax, a.recMin, a.subMax, a.subMin];
    for (var j = 0; j < SPOT.length; j++){
      var sp = spots[j];
      var txt = sp ? (esc(sp.p.short) + ' <em>' + esc(pct(sp.v)) + '</em>') : '—';
      out.push('<div class="ov-bk-item spot"><span class="l">' + esc(SPOT[j]) +
               '</span><span class="v">' + txt + '</span>' +
               '<span class="b">' + esc(BASIS_TEXT.spot) + '</span></div>');
    }
    out.push('</div>');
    out.push('</div>');   /* /ov-bk */
    return out.join('');
  }

  /* 指标格（16）与点名格（4）：与 Python 侧 BAND_METRICS / BAND_SPOT 一致
     [label, kind, key, src, hi, basis]
     src  : 'sum'=聚合字段 | 'avg'=a.avg[field] | 'weighted'=加权回收率 | 'median'=a.med[field]
     basis: sum / weighted / simple / median / perdeal → 副行显示口径 + 样本量 */
  var METRICS = [
    ['入池本息费',           'yi',      'poolSum',        'sum',      '',    'sum'],
    ['累计回收',             'yi',      'recSum',         'sum',      '',    'sum'],
    ['加权回收率',           'pct',     'recRate',        'weighted', ' hi', 'weighted'],
    ['算术平均回收率',       'pct',     'recRate',        'avg',      '',    'simple'],
    ['中位回收率',           'pct',     'recRate',        'median',   '',    'median'],
    ['发行规模',             'yi',      'issueSum',       'sum',      '',    'sum'],
    ['算术平均证券化率',     'pct',     'secRatio',       'avg',      '',    'simple'],
    ['算术平均优先档XIRR',   'pct',     'xirrSen',        'avg',      '',    'simple'],
    ['算术平均次级档XIRR',   'pct',     'xirrSub',        'avg',      ' hi', 'simple'],
    ['中位次级档XIRR',       'pct',     'xirrSub',        'median',   '',    'median'],
    ['算术平均处置费率',     'pct',     'disposeFeeRate', 'avg',      '',    'simple'],
    ['算术平均达成率',       'pct',     'vsForecast',     'avg',      '',    'simple'],
    ['算术平均存续',         'months',  'months',         'avg',      '',    'simple'],
    ['算术平均支付期数',     'periods', 'n_periods',      'avg',      '',    'simple'],
    ['算术平均入池本息费',   'yi',      'poolTotal',      'avg',      '',    'simple'],
    ['笔均发行规模',         'yi',      'issue',          'avg',      '',    'perdeal']
  ];
  var SPOT = ['回收率最高', '回收率最低', '次级档XIRR最高', '次级档XIRR最低'];
  /* 口径基中文（与 Python 侧 BASIS_TEXT 一致） */
  var BASIS_TEXT = { sum: '合计', weighted: '规模加权', simple: '算术平均',
                     median: '中位数', perdeal: '笔均', spot: '组内极值' };

  /* 取值：口径单一实现，避免字段名与聚合字段名撞名 */
  function metricValue(a, key, src){
    if (src === 'sum') return a[key];
    if (src === 'weighted') return a.recWeighted;
    if (src === 'median') return a.med[key] ? a.med[key].v : null;
    return a.avg[key];                 /* src === 'avg' */
  }
  /* 样本量：用于副行 n= 标注 */
  function metricN(a, key, src){
    if (src === 'weighted') return a.recWeightedN;
    if (src === 'median') return a.med[key] ? a.med[key].n : 0;
    if (src === 'sum') return null;
    return (a.avgN && a.avgN[key] !== undefined) ? a.avgN[key] : null;
  }

  /* ══════════ ④ 卡片内容（第一轮设计保持不动：2 列 × 8 项 + meta 条）══════════ */
  var ROWS = [
    ['入池本息费', function(p){ return yi(p.poolTotal); },   false],
    ['累计回收',   function(p){ return yi(p.recovered); },   false],
    ['回收率',     function(p){ return pct(p.recRate); },    true ],
    ['达成率',     function(p){ return pct(p.vsForecast); }, false],
    ['发行规模',   function(p){ return yi(p.issue); },       false],
    ['证券化率',   function(p){ return pct(p.secRatio); },   false],
    ['优先档XIRR', function(p){ return pct(p.xirrSen); },    false],
    ['次级档XIRR', function(p){ return pct(p.xirrSub); },    true ]
  ];
  var FOOT = [
    ['支付期',   function(p){ return periods(p.n_periods); }],
    ['存续',     function(p){ return months(p.months); }],
    ['处置费率', function(p){ return pct(p.disposeFeeRate); }]
  ];

  /* ③ 达成率 < 80% 但证券端两档本金均已兑付完毕 → 中性标记，避免误读为「未兑付」 */
  function paidBadge(p){
    var vf = num(p.vsForecast);
    if (vf === null || !(vf < VSF_LOW)) return '';
    var sen = num(p.senPaidPct), sub = num(p.subPaidPct);
    if (sen === null && sub === null) return '';
    if (sen !== null && sen < PAID_DONE) return '';
    if (sub !== null && sub < PAID_DONE) return '';
    return '<span class="obadge" title="达成率 ' + esc(pct(vf)) + ' < 80%，但优先档 ' +
           esc(pct(sen)) + '／次级档 ' + esc(pct(sub)) +
           ' 本金已兑付完毕；达成率与证券端兑付率不是同一口径">证券端已兑付完毕</span>';
  }

  function paint(p){
    var acc = esc(p.accent || ACC_FALLBACK);
    var out = [];
    out.push('<div class="ov-hd">');
    out.push('<span class="ov-bar" style="background:' + acc + '"></span>');
    out.push('<div class="ov-ht">');
    out.push('<div class="oname">' + esc(p.short || p.name || p.code || '') + '</div>');
    out.push('<div class="ov-chips">');
    out.push('<span class="obank">' + esc(p.issuer || '—') + '</span>');
    out.push('<span class="vchip">' + esc(p.cat || '—') + '</span>');
    out.push(paidBadge(p));
    out.push('</div></div></div>');
    out.push('<div class="ov-body">');
    for (var i = 0; i < ROWS.length; i++){
      out.push('<div class="ov-k' + (ROWS[i][2] ? ' hi' : '') + '">');
      out.push('<span class="ov-kl">' + esc(ROWS[i][0]) + '</span>');
      out.push('<span class="ov-kv">' + esc(ROWS[i][1](p)) + '</span>');
      out.push('</div>');
    }
    out.push('</div>');
    out.push('<div class="ov-foot">');
    for (var j = 0; j < FOOT.length; j++){
      out.push('<span class="ov-fk"><em>' + esc(FOOT[j][0]) + '</em><b>' +
               esc(FOOT[j][1](p)) + '</b></span>');
    }
    out.push('</div>');
    return out.join('');
  }

  /* ══════════ ⑤ 数据准备：key → profile、按品种/银行分桶 ══════════ */
  function keyOfCard(c){
    var dv = c.getAttribute('data-view') || '';
    var m = /^p(\d+)$/.exec(dv);
    var key = m ? ORDER[+m[1]] : dv;
    return (key && V.PROF[key]) ? key : (V.PROF[dv] ? dv : null);
  }

  /* 品种排序权重：CAT_ORDER 为数组（勿与此前误用的字符串 indexOf 混淆） */
  function catRank(cat){
    for (var i = 0; i < CAT_ORDER.length; i++){ if (CAT_ORDER[i] === cat) return i; }
    return 99;
  }

  /* ══════════ ⑤b 筛选维度：年份 / 发起机构 / 品种切片 ══════════
     宿主 PROF 未提供 year / bank 字段（已核对 28 单键集合），故：
       · year ← PROF.year（若存在）否则从项目名解析「20xx 年」
       · bank ← PROF.bank（若存在）否则用 PROF.issuer（发起机构）
       · cat  ← PROF.cat（品种）
     三者皆为空/解析失败时归入「未知」，仍可被筛选到，不丢数据。 */
  function yearOf(p, key){
    if (p && p.year !== null && p.year !== undefined && p.year !== '') return String(p.year);
    var s = (p && (p.short || p.name || p.code)) || key || '';
    var m = /(20\d{2})\s*年/.exec(s);
    return m ? m[1] : '未知';
  }
  function bankOf(p){ return (p && (p.bank || p.issuer)) || '未披露机构'; }
  function catOf(p){ return (p && p.cat) || '未分类'; }
  /* 维度取值表（首次出现序，保证跨浏览器确定性） */
  function dimValues(dim){
    var seen = {}, out = [];
    for (var i = 0; i < ORDER.length; i++){
      var p = V.PROF[ORDER[i]] || {};
      var v = dim === 'year' ? yearOf(p, ORDER[i])
            : dim === 'bank' ? bankOf(p)
            : catOf(p);
      if (!seen[v]){ seen[v] = 1; out.push(v); }
    }
    if (dim === 'year') out.sort();                 /* 年份按字典序即时间序 */
    if (dim === 'cat'){
      out.sort(function(a, b){ return catRank(a) - catRank(b); });
    }
    return out;
  }
  var DIM_LABEL = { year: '年份', bank: '发起机构', cat: '品种切片' };

  /* ══════════ ⑥ ① 文案更正：重写总览首句说明（一级分组是品种，不是银行）══════════ */
  function rewriteNote(host){
    var note = host.querySelector('.note');
    if (!note) return false;
    if (note.getAttribute('data-ov2') === '1') return false;   /* 幂等 */
    note.textContent = NOTE_TEXT;
    note.setAttribute('data-ov2', '1');
    return true;
  }

  /* ══════════ ⑦ 口径提示条（③ 达成率≠证券兑付率 / ⑤ 语义色）══════════ */
  function ensureNoteBar(host, vb){
    if (!host) return null;
    var exist = host.querySelector('.ov-ovnote');
    if (exist) return exist;
    var bar = document.createElement('div');
    bar.className = 'ov-ovnote';
    bar.innerHTML =
      '<div class="ov-ni"><span class="ov-ntag">口径提示</span><p>' + esc(VSF_NOTE) + '</p></div>' +
      '<div class="ov-ni"><span class="ov-ntag">语义色</span><p>' + esc(COLOR_NOTE) + '</p></div>';
    if (vb && vb.parentNode) vb.parentNode.insertBefore(bar, vb);
    else host.appendChild(bar);
    return bar;
  }

  /* ══════════ ⑧ ④ 数据质量汇总：从各 #view-pN 的「数据质量与披露」fold 读取 ══════════
     数据源在 DOM（__V2 未提供）：缺项数取「本单披露 N 项」，分级取 .kbadge.kA/kB/kC，
     影响 XIRR 判据 = XIRR 缺失 或 ⑧ 披露文本涉及 现金流/补录/折现/XNPV。
     只读不写源节点，幂等（已存在 .ov-dq 则跳过）。 */
  function dqLevel(n){
    if (n === null || n === undefined) return 0;
    if (n <= 0) return 0;
    if (n <= 2) return 1;
    if (n <= 9) return 2;
    return 3;
  }

  function foldBodyOf(sec){
    if (!sec) return { txt: '', found: false };
    var folds = sec.querySelectorAll('.fold');
    for (var i = 0; i < folds.length; i++){
      var fh = folds[i].querySelector('.fold-h');
      var ht = fh ? (fh.textContent || '') : '';
      if (ht.indexOf('数据质量与披露') >= 0){
        var fb = folds[i].querySelector('.fold-b');
        return { txt: ((fb || folds[i]).textContent || ''), found: true };
      }
    }
    return { txt: '', found: false };
  }

  function collectDQ(){
    var rows = [];
    for (var idx = 0; idx < ORDER.length; idx++){
      var key = ORDER[idx];
      var p = V.PROF[key] || {};
      var sec = document.querySelector('#view-p' + idx);
      var all = sec ? (sec.textContent || '') : '';
      var fb = foldBodyOf(sec);

      /* 缺项数：①「本单披露 N 项」②⑧ fold 的「N 项披露」③「无缺口」→ 0 */
      var nd = null, m = /本单披露\s*(\d+)\s*项/.exec(all);
      if (m) nd = +m[1];
      else {
        m = /(\d+)\s*项披露/.exec(fb.txt);
        if (m) nd = +m[1];
        else if (fb.txt.indexOf('无缺口') >= 0 || all.indexOf('未发现数据缺口') >= 0) nd = 0;
      }

      var kA = 0, kB = 0, kC = 0;
      if (sec){
        kA = sec.querySelectorAll('.kbadge.kA').length;
        kB = sec.querySelectorAll('.kbadge.kB').length;
        kC = sec.querySelectorAll('.kbadge.kC').length;
      }
      var afx = (num(p.xirrSen) === null || num(p.xirrSub) === null) ||
                /现金流|补录|折现|XNPV|口径不符/.test(fb.txt);
      rows.push({ key: key, p: p, nd: nd, kA: kA, kB: kB, kC: kC, afx: afx, found: fb.found });
    }
    return rows;
  }

  function buildDQ(host){
    if (!host) return null;
    var exist = host.querySelector('.ov-dq');
    if (exist) return exist;
    var rows = collectDQ();
    if (!rows.length) return null;

    /* 排序：品种序 → 发起机构首现序 → 项目序（与卡片聚类顺序一致） */
    var bankFirst = {};
    for (var i = 0; i < rows.length; i++){
      var bk = rows[i].p.cat + '\u0001' + rows[i].p.issuer;
      if (!(bk in bankFirst)) bankFirst[bk] = i;
    }
    rows.sort(function(x, y){
      var d = catRank(x.p.cat) - catRank(y.p.cat);
      if (d) return d;
      var bx = bankFirst[x.p.cat + '\u0001' + x.p.issuer];
      var by = bankFirst[y.p.cat + '\u0001' + y.p.issuer];
      return bx - by;
    });

    var lv = [0, 0, 0, 0], afxN = 0, miss = 0, cells = [];
    for (var j = 0; j < rows.length; j++){
      var r = rows[j];
      var lvl = dqLevel(r.nd);
      if (r.nd === null) miss++; else lv[lvl]++;
      if (r.afx) afxN++;
      var nm = r.p.short || r.p.name || r.key;
      var tip = '项目：' + nm +
                '｜品种：' + (r.p.cat || '—') +
                '｜发起机构：' + (r.p.issuer || '—') +
                '｜缺项/披露：' + (r.nd === null ? '—' : (r.nd + ' 项')) +
                '｜缺口分级：A 回源已补 ' + r.kA + ' · B 报告确无 ' + r.kB +
                ' · C 源文件缺失 ' + r.kC +
                '｜影响 XIRR：' + (r.afx ? '是' : '否');
      cells.push('<span class="ov-dq-c lv' + lvl + (r.afx ? ' afx' : '') +
                 '" data-key="' + esc(r.key) + '" title="' + esc(tip) + '">' +
                 '<span class="nm">' + esc(nm) + '</span>' +
                 '<span class="n">' + (r.nd === null ? '—' : r.nd) + (r.afx ? '*' : '') +
                 '</span></span>');
    }
    var sumTxt = lv[0] + ' 单无缺口 · ' + lv[1] + ' 单 1–2 项 · ' + lv[2] + ' 单 3–9 项 · ' +
                 lv[3] + ' 单 ≥10 项' + (miss ? ' · ' + miss + ' 单未取到披露数' : '') +
                 '；' + afxN + ' 单披露涉及现金流/折现口径';
    var dq = document.createElement('div');
    dq.className = 'ov-dq';
    dq.innerHTML =
      '<div class="ov-dq-hd">' +
        '<span class="ov-dq-t">数据质量汇总</span>' +
        '<span class="ov-dq-n">' + rows.length + ' 单</span>' +
        '<span class="ov-dq-legend">缺项数 ' +
          '<i class="lv0"></i>无缺口 ' +
          '<i class="lv1"></i>1–2 项 ' +
          '<i class="lv2"></i>3–9 项 ' +
          '<i class="lv3"></i>≥10 项' +
        '</span>' +
        '<span class="ov-dq-sum">' + esc(sumTxt) + '</span>' +
      '</div>' +
      '<div class="ov-dq-grid">' + cells.join('') + '</div>' +
      '<div class="ov-dq-foot">' + esc(DQ_FOOT) + '</div>';
    host.appendChild(dq);
    dq.setAttribute('data-ov2', 'dq');
    return dq;
  }

  /* ══════════ ⑨ 筛选器（年份 / 发起机构 / 品种切片）══════════
     状态：FLT[dim] = { 选中值: 1 }；空对象 = 全部。
     重算路径（applyFilters）：
       1) 按 FLT 过滤 ORDER → selKeys / selSet
       2) 3 个品种行重算并重写 innerHTML（数字、总结全文、指标 n 全部变）
       3) 28 张卡片 + 银行小组 + 品种组按命中情况显隐（不重建节点，监听不丢）
       4) 数据质量热力小格按命中显隐 + 汇总行重算
       5) 命中数 / 各维已选数 / 空态刷新
     复杂度 O(28)，实测远低于 300ms。 */
  var FLT = { year: {}, bank: {}, cat: {} };

  function fltActive(dim){ return Object.keys(FLT[dim]).length > 0; }
  function fltCount(dim){ return Object.keys(FLT[dim]).length; }
  /* 单条是否命中 */
  function rowHit(p, key){
    if (fltActive('year') && !FLT.year[yearOf(p, key)]) return false;
    if (fltActive('bank') && !FLT.bank[bankOf(p)]) return false;
    if (fltActive('cat') && !FLT.cat[catOf(p)]) return false;
    return true;
  }
  /* 分面计数：某维某值的可选单数（排除该维自身筛选，其它维生效） */
  function facetCount(dim, val){
    var n = 0;
    for (var i = 0; i < ORDER.length; i++){
      var key = ORDER[i], p = V.PROF[key] || {};
      var hit = true;
      if (dim !== 'year' && fltActive('year') && !FLT.year[yearOf(p, key)]) hit = false;
      if (hit && dim !== 'bank' && fltActive('bank') && !FLT.bank[bankOf(p)]) hit = false;
      if (hit && dim !== 'cat' && fltActive('cat') && !FLT.cat[catOf(p)]) hit = false;
      if (!hit) continue;
      var v = dim === 'year' ? yearOf(p, key) : dim === 'bank' ? bankOf(p) : catOf(p);
      if (v === val) n++;
    }
    return n;
  }
  function matchesDim(dim, p, key){
    var v = dim === 'year' ? yearOf(p, key) : dim === 'bank' ? bankOf(p) : catOf(p);
    return v;
  }

  function ensureFilterBar(host){
    if (!host) return null;
    var exist = host.querySelector('.ov-flt');
    if (exist) return exist;
    var bar = document.createElement('div');
    bar.className = 'ov-flt';
    bar.setAttribute('data-ov2', 'flt');
    var h = [];
    h.push('<div class="ov-flt-hd">');
    h.push('<span class="ov-flt-t">筛选</span>');
    h.push('<span class="ov-flt-hit" data-hit>命中 28 单</span>');
    h.push('<span class="ov-flt-tip">多选；未选=全部</span>');
    h.push('<button type="button" class="ov-flt-reset" data-reset>重置全部</button>');
    h.push('</div>');
    var dims = ['year', 'bank', 'cat'];
    for (var di = 0; di < dims.length; di++){
      var dim = dims[di], vals = dimValues(dim);
      h.push('<div class="ov-flt-row" data-dim="' + dim + '">');
      h.push('<span class="ov-flt-lab">' + esc(DIM_LABEL[dim]) + '</span>');
      h.push('<span class="ov-flt-chips">');
      for (var vi = 0; vi < vals.length; vi++){
        h.push('<button type="button" class="ov-flt-c" data-v="' + esc(vals[vi]) +
               '" aria-pressed="false">' + esc(vals[vi]) +
               '<span class="kc" data-kc="' + esc(vals[vi]) + '">' + facetCount(dim, vals[vi]) +
               '</span></button>');
      }
      h.push('</span>');
      h.push('<button type="button" class="ov-flt-all" data-all="' + dim + '">全部</button>');
      h.push('<button type="button" class="ov-flt-clr" data-all="' + dim +
             '" data-clr="' + dim + '">清空</button>');
      h.push('<span class="ov-flt-cnt" data-cnt="' + dim + '">全部</span>');
      h.push('</div>');
    }
    bar.innerHTML = h.join('');
    var anchor = host.querySelector('.ov-ovnote') || host.querySelector('.vbands');
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(bar, anchor);
    else host.appendChild(bar);

    /* 事件委托：一次绑定、永久有效（条永不重建 → 幂等） */
    bar.addEventListener('click', function(ev){
      var t = ev.target;
      if (!t || t.nodeType !== 1) return;
      var chip = upCls(t, 'ov-flt-c');
      if (chip){
        var dim0 = chip.parentNode.parentNode.getAttribute('data-dim');
        var v0 = chip.getAttribute('data-v');
        if (FLT[dim0][v0]) delete FLT[dim0][v0]; else FLT[dim0][v0] = 1;
        applyFilters();
        return;
      }
      var all = upAttr(t, 'data-all');
      if (all){ FLT[all] = {}; applyFilters(); return; }
      if (upAttr(t, 'data-reset') !== null){ FLT = { year: {}, bank: {}, cat: {} }; applyFilters(); return; }
    });
    return bar;
  }

  /* 从元素向上找带某 class 的祖先 */
  function upCls(el, cls){
    while (el && el.getAttribute){
      if (el.classList && el.classList.contains(cls)) return el;
      el = el.parentNode;
    }
    return null;
  }
  /* 从元素向上找带某 data-* 属性的祖先；返回属性值（无则 null） */
  function upAttr(el, attr){
    while (el && el.getAttribute){
      var v = el.getAttribute(attr);
      if (v !== null) return v;
      el = el.parentNode;
    }
    return null;
  }

  /* 空态提示 */
  function ensureEmpty(host){
    var el = host.querySelector('.ov-empty');
    if (!el){
      el = document.createElement('div');
      el.className = 'ov-empty';
      el.innerHTML = '<b>当前筛选无项目，请调整条件</b>' +
                     '<br>可点各维「全部」或右上「重置全部」恢复 28 单。';
      var vb = host.querySelector('.vbands');
      if (vb && vb.parentNode) vb.parentNode.insertBefore(el, vb);
      else host.appendChild(el);
    }
    return el;
  }

  /* 刷新筛选条自身（chip 选中态 / 计数 / 命中数） */
  function refreshFilterBar(host, total){
    var bar = host.querySelector('.ov-flt');
    if (!bar) return;
    var hit = bar.querySelector('[data-hit]');
    if (hit) hit.textContent = '命中 ' + total + ' 单';
    var dims = ['year', 'bank', 'cat'];
    for (var di = 0; di < dims.length; di++){
      var dim = dims[di];
      var row = bar.querySelector('.ov-flt-row[data-dim="' + dim + '"]');
      if (!row) continue;
      var chips = row.querySelectorAll('.ov-flt-c');
      for (var ci = 0; ci < chips.length; ci++){
        var chip = chips[ci], v = chip.getAttribute('data-v');
        chip.setAttribute('aria-pressed', FLT[dim][v] ? 'true' : 'false');
        var kc = chip.querySelector('[data-kc]');
        if (kc) kc.textContent = facetCount(dim, v);
      }
      var cnt = row.querySelector('[data-cnt]');
      if (cnt){
        var k = fltCount(dim);
        cnt.textContent = k ? ('已选 ' + k + ' / ' + dimValues(dim).length) : '全部';
        if (k) cnt.classList.add('on'); else cnt.classList.remove('on');
      }
      /* 清空按钮：仅在有选中时出现 */
      var clr = row.querySelector('[data-clr]');
      if (clr){
        if (fltCount(dim)) clr.classList.add('on'); else clr.classList.remove('on');
      }
    }
  }

  /* 主重算：筛选变化后调用（幂等，可重复调用） */
  function applyFilters(){
    var host = document.querySelector('#view-overview');
    if (!host) return 0;

    /* 1) 过滤 */
    var selKeys = [], selSet = {};
    for (var i = 0; i < ORDER.length; i++){
      var key = ORDER[i];
      if (rowHit(V.PROF[key] || {}, key)){ selKeys.push(key); selSet[key] = 1; }
    }

    /* 2) 品种行：重算数字 + 重写总结（命中 0 → 隐藏该行） */
    var bands = host.querySelectorAll('.vbands > .vband');
    var bandsInfo = [];
    Array.prototype.forEach.call(bands, function(b){
      var cat = b.getAttribute('data-cat');
      if (!cat) return;
      var rows = [];
      for (var k = 0; k < selKeys.length; k++){
        var pp = V.PROF[selKeys[k]];
        if (pp && pp.cat === cat) rows.push(pp);
      }
      if (!rows.length){ b.classList.add('ov-flt-off'); return; }
      b.classList.remove('ov-flt-off');
      b.innerHTML = bandInner(cat, rows);
      bandsInfo.push({ cat: cat, n: rows.length });
    });
    /* 行序对齐品种序（隐藏行不参与视觉顺序） */
    bandsInfo.sort(function(x, y){ return catRank(x.cat) - catRank(y.cat); });

    /* 3) 卡片：按 key 显隐；银行小组 / 品种组按命中显隐（不重建节点） */
    var grid = host.querySelector('.ov-grid');
    var cardsVisible = 0;
    if (grid){
      Array.prototype.forEach.call(grid.querySelectorAll('.ov-cat-wrap'), function(wrap){
        var wrapVisible = 0;
        Array.prototype.forEach.call(wrap.querySelectorAll('.ov-cards'), function(cont){
          var groupVisible = 0;
          Array.prototype.forEach.call(cont.querySelectorAll('.ov-card'), function(card){
            var key = card.getAttribute('data-key') || keyOfCard(card);
            if (key && selSet[key]){ card.classList.remove('ov-flt-off'); groupVisible++; }
            else card.classList.add('ov-flt-off');
          });
          var bankHd = cont.previousElementSibling;
          if (bankHd && bankHd.classList.contains('ov-bank-hd')){
            if (groupVisible) bankHd.classList.remove('ov-flt-off');
            else bankHd.classList.add('ov-flt-off');
          }
          if (groupVisible) cont.classList.remove('ov-flt-off');
          else cont.classList.add('ov-flt-off');
          wrapVisible += groupVisible;
        });
        if (wrapVisible) wrap.classList.remove('ov-flt-off');
        else wrap.classList.add('ov-flt-off');
        cardsVisible += wrapVisible;
      });
    }

    /* 4) 数据质量热力小格：按 key 显隐 + 汇总行重算 */
    var dq = host.querySelector('.ov-dq');
    var dqVisible = 0, dqAfx = 0, dqLv = [0, 0, 0, 0];
    if (dq){
      Array.prototype.forEach.call(dq.querySelectorAll('.ov-dq-c'), function(cell){
        var key = cell.getAttribute('data-key');
        if (key && selSet[key]){
          cell.classList.remove('ov-flt-off');
          dqVisible++;
          if (cell.classList.contains('afx')) dqAfx++;
          for (var l = 0; l < 4; l++){
            if (cell.classList.contains('lv' + l)){ dqLv[l]++; break; }
          }
        } else cell.classList.add('ov-flt-off');
      });
      var dqN = dq.querySelector('.ov-dq-n');
      if (dqN) dqN.textContent = dqVisible + ' 单';
      var dqSum = dq.querySelector('.ov-dq-sum');
      if (dqSum){
        dqSum.textContent = dqLv[0] + ' 单无缺口 · ' + dqLv[1] + ' 单 1–2 项 · ' +
                            dqLv[2] + ' 单 3–9 项 · ' + dqLv[3] + ' 单 ≥10 项' +
                            '；' + dqAfx + ' 单披露涉及现金流/折现口径';
      }
      var dqFoot = dq.querySelector('.ov-dq-foot');
      if (dqFoot) dqFoot.style.opacity = dqVisible ? '' : '0';
    }

    /* 5) 空态 + 筛选条刷新 */
    var empty = ensureEmpty(host);
    if (selKeys.length) empty.classList.add('ov-flt-off');
    else empty.classList.remove('ov-flt-off');
    refreshFilterBar(host, selKeys.length);

    /* 6) 探针发布（供自检与外部观测） */
    publishFilterState(selKeys, bandsInfo, cardsVisible, dqVisible, dqAfx);
    return selKeys.length;
  }

  function bandBasisN(b){
    var out = [];
    Array.prototype.forEach.call(b.querySelectorAll('.ov-bk-item .b'), function(x){
      out.push((x.textContent || '').replace(/\s+/g, ' '));
    });
    return out;
  }

  function publishFilterState(selKeys, bandsInfo, cardsVisible, dqVisible, dqAfx){
    var probe = window.__V2_10_overview;
    if (!probe) return;
    var host = document.querySelector('#view-overview');
    probe.total = selKeys.length;
    probe.selected = selKeys.slice();
    probe.bandCards = bandsInfo.map(function(x){ return x.n; });
    probe.bandNames = bandsInfo.map(function(x){ return x.cat; });
    probe.cardsVisible = cardsVisible;
    probe.dqVisible = dqVisible;
    probe.dqAfx = dqAfx;
    probe.filter = {
      year: Object.keys(FLT.year), bank: Object.keys(FLT.bank), cat: Object.keys(FLT.cat)
    };
    probe.filterActive = fltActive('year') || fltActive('bank') || fltActive('cat');
    probe.summaryChars = [];
    probe.summaryHeads = [];
    var bands = host.querySelectorAll('.vbands > .vband:not(.ov-flt-off)');
    Array.prototype.forEach.call(bands, function(b){
      var ps = b.querySelectorAll('.ov-bsum p');
      var txt = '';
      Array.prototype.forEach.call(ps, function(x){
        if (!(x.classList && x.classList.contains('ov-bsum-note'))) txt += (x.textContent || '');
      });
      probe.summaryChars.push(txt.replace(/\s+/g, '').length);
      probe.summaryHeads.push((txt.replace(/\s+/g, '') || '').slice(0, 44));
    });
    probe.bandBasisN = [];
    Array.prototype.forEach.call(bands, function(b){ probe.bandBasisN.push(bandBasisN(b)); });
    probe.emptyVisible = !!(host.querySelector('.ov-empty') &&
                            !host.querySelector('.ov-empty').classList.contains('ov-flt-off'));
  }

  function run(){
    var host = document.querySelector('#view-overview');
    if (!host) return 0;
    /* ① 文案更正：无论是否重绘都执行（自身幂等） */
    rewriteNote(host);

    var grid = host.querySelector('.ov-grid');
    if (!grid) return 0;

    /* 幂等：已聚类过就直接返回；仍确保提示条 / 数据质量块 / 筛选条存在并套用筛选 */
    if (grid.getAttribute('data-ov2') === 'grouped' && grid.querySelector('.ov-cat-wrap')){
      ensureNoteBar(host, host.querySelector('.vbands'));
      buildDQ(host);
      ensureFilterBar(host);
      ensureEmpty(host);
      if (window.__V2_10_overview) applyFilters();
      return 0;
    }

    var cards = grid.querySelectorAll('.ov-card');
    if (!cards.length) return 0;

    /* ── 5.1 逐卡重绘（内容），记录 key，保留节点（click 监听不动）── */
    var items = [], miss = [];
    Array.prototype.forEach.call(cards, function(c){
      var key = keyOfCard(c);
      if (!key){ miss.push(c.getAttribute('data-view')); return; }
      var p = V.PROF[key];
      c.setAttribute('data-ov2', '1');
      c.style.setProperty('--ov-accent', p.accent || ACC_FALLBACK);
      c.style.setProperty('--vc', p.accent || ACC_FALLBACK);
      c.innerHTML = paint(p);
      c.setAttribute('data-key', key);     /* v8 筛选：按 key 显隐 */
      c.classList.add('ov-v2');
      c.classList.add('in');         /* .rv 的显示态，防止重写后不可见 */
      items.push({ key: key, card: c, p: p });
    });
    if (!items.length) return 0;

    /* ── 5.2 品种整行总结卡（按 ORDER 顺序取品种，未知品种追加）── */
    var bands = document.querySelectorAll('#view-overview .vbands > .vband');
    var cats = [], seen = {};
    for (var i = 0; i < ORDER.length; i++){
      var cat = V.PROF[ORDER[i]] && V.PROF[ORDER[i]].cat;
      if (!cat || seen[cat]) continue;
      seen[cat] = 1; cats.push(cat);
    }
    cats.sort(function(a, b){ return catRank(a) - catRank(b); });
    /* 品种行匹配：优先用行内 .vt 文本（宿主与 PROF.cat 同源），
       文本缺失/被 DOM 解析破坏时按序号兜底，保证 3 行都能命中。 */
    var catSet = {};
    for (var ci0 = 0; ci0 < cats.length; ci0++) catSet[norm(cats[ci0])] = cats[ci0];
    var bandInfo = [];
    var painted = [];
    var used = {};
    Array.prototype.forEach.call(bands, function(b){
      var vt = b.querySelector('.vt');
      var wt = norm(vt ? vt.textContent : '');
      var cat = catSet[wt];
      if (!cat){
        /* 文本缺失/被破坏时按「尚未占用的品种 + DOM 序」兜底，保证不写错行 */
        for (var ci = 0; ci < cats.length; ci++){
          if (!used[cats[ci]]){ cat = cats[ci]; break; }
        }
      }
      if (!cat){ bandInfo.push({ cat: null, n: 0, accent: null }); return; }
      used[cat] = 1;
      var rows = [];
      for (var k = 0; k < ORDER.length; k++){
        var pp = V.PROF[ORDER[k]];
        if (pp && pp.cat === cat) rows.push(pp);
      }
      var acc = (V.CAT && V.CAT[cat]) || (rows[0] && rows[0].accent) || ACC_FALLBACK;
      b.style.setProperty('--ov-accent', acc);
      b.style.borderLeftColor = acc;
      b.setAttribute('data-cat', cat);
      b.classList.add('ov-v2');
      b.classList.add('in');
      b.innerHTML = bandInner(cat, rows);
      bandInfo.push({ cat: cat, n: rows.length, accent: acc });
      painted.push(b);
    });
    /* 行序对齐卡片分组序（信用卡不良 → 个人消费贷款 → 个人经营贷款）：
       品种行是独立容器，重排不会影响任何事件监听。 */
    var vbandsBox = document.querySelector('#view-overview .vbands');
    if (vbandsBox){
      painted.sort(function(x, y){ return catRank(x.getAttribute('data-cat')) - catRank(y.getAttribute('data-cat')); });
      for (var pz = 0; pz < painted.length; pz++) vbandsBox.appendChild(painted[pz]);
      /* 未重绘的残留 .vband（文本损坏且无品种可分配）统一沉到最后 */
      Array.prototype.forEach.call(bands, function(b2){ if (painted.indexOf(b2) < 0) vbandsBox.appendChild(b2); });
    }

    /* ── 5.3 聚类：品种 → 银行，移动节点（appendChild）── */
    var groups = {};                       /* cat → {bank: [item]} */
    var bankOrder = {};                    /* cat → [bank]（按 ORDER 首次出现）*/
    for (var q = 0; q < items.length; q++){
      var it = items[q];
      var c2 = it.p.cat || '未分类';
      var bk = it.p.issuer || '未披露机构';
      if (!groups[c2]){ groups[c2] = {}; bankOrder[c2] = []; }
      if (!groups[c2][bk]){ groups[c2][bk] = []; bankOrder[c2].push(bk); }
      groups[c2][bk].push(it);
    }
    var orderedCats = Object.keys(groups).sort(function(a, b){
      var d = catRank(a) - catRank(b);
      return d !== 0 ? d : 0;
    });

    var wrapCount = 0, bankCount = 0;
    for (var ci = 0; ci < orderedCats.length; ci++){
      var cat2 = orderedCats[ci];
      var acc2 = (V.CAT && V.CAT[cat2]) || ACC_FALLBACK;
      var rows2 = [];
      for (var k2 = 0; k2 < ORDER.length; k2++){
        if (V.PROF[ORDER[k2]] && V.PROF[ORDER[k2]].cat === cat2) rows2.push(V.PROF[ORDER[k2]]);
      }
      var a2 = agg(rows2);

      var sect = document.createElement('div');
      sect.className = 'ov-cat-wrap';
      sect.setAttribute('data-cat', cat2);
      sect.setAttribute('data-n', String(rows2.length));
      sect.style.setProperty('--ov-accent', acc2);

      var hd = document.createElement('div');
      hd.className = 'ov-cat-hd';
      hd.innerHTML =
        '<span class="ov-ch-t">' + esc(cat2) + '</span>' +
        '<span class="ov-ch-n">' + rows2.length + ' 单</span>' +
        '<span class="ov-ch-s"><em>发行规模合计</em>' + esc(yi(a2.issueSum)) + '</span>';
      sect.appendChild(hd);

      var banks = bankOrder[cat2];
      for (var bi = 0; bi < banks.length; bi++){
        var bank = banks[bi];
        var groupCards = groups[cat2][bank];

        var bhd = document.createElement('div');
        bhd.className = 'ov-bank-hd';
        bhd.setAttribute('data-bank', bank);
        bhd.innerHTML = '<span class="ov-bh-bar"></span><span class="ov-bh-t">' + esc(bank) +
                        '</span><span class="ov-bh-n">' + groupCards.length + ' 单</span>';
        sect.appendChild(bhd);

        var cont = document.createElement('div');
        cont.className = 'ov-cards';
        cont.setAttribute('data-bank', bank);
        for (var gi = 0; gi < groupCards.length; gi++){
          cont.appendChild(groupCards[gi].card);   /* 移动节点：不丢 click 监听 */
        }
        sect.appendChild(cont);
        bankCount++;
      }
      grid.appendChild(sect);
      wrapCount++;
    }
    grid.setAttribute('data-ov2', 'grouped');

    /* ⑤ 口径提示条 + ④ 数据质量汇总 + ⑨ 筛选条（三者各自幂等） */
    var vbandsEl = host.querySelector('.vbands');
    ensureNoteBar(host, vbandsEl);
    buildDQ(host);
    ensureFilterBar(host);
    ensureEmpty(host);

    /* 自检探针 */
    var sumLens = [];
    Array.prototype.forEach.call(document.querySelectorAll('#view-overview .ov-bsum p:not(.ov-bsum-note)'), function(n){
      sumLens.push((n.textContent || '').replace(/\s+/g, '').length);
    });
    var dqCells = host.querySelectorAll('.ov-dq-c');
    var dqLv = [0, 0, 0, 0];
    Array.prototype.forEach.call(dqCells, function(c){
      for (var l = 0; l < 4; l++){ if (c.className.indexOf('lv' + l) >= 0){ dqLv[l]++; return; } }
    });
    window.__V2_10_overview = {
      cards: cards.length,
      painted: items.length,
      missing: miss,
      bands: bandInfo.length,
      bandCards: bandInfo.map(function(b){ return b.n; }),
      catGroups: wrapCount,
      bankGroups: bankCount,
      rows: ROWS.length,
      cols: 2,
      foot: FOOT.length,
      removed: ['账户配平'],
      summaryChars: sumLens,
      moved: true,
      /* v5 新增探针 */
      noteText: (host.querySelector('.note') || {}).textContent || '',
      noteBar: host.querySelectorAll('.ov-ovnote .ov-ni').length,
      paidBadges: host.querySelectorAll('.ov-card .obadge').length,
      dqCells: dqCells.length,
      dqLevels: dqLv,
      dqAfx: host.querySelectorAll('.ov-dq-c.afx').length,
      basisCells: host.querySelectorAll('.ov-bk-item .b').length,
      metricCells: host.querySelectorAll('.ov-bk-item').length,
      /* v8 筛选：状态查询与编程式控制（自检/外部观测用） */
      filterDims: { year: dimValues('year'), bank: dimValues('bank'), cat: dimValues('cat') },
      setFilter: function(dim, vals){
        if (!FLT[dim]) return 0;
        FLT[dim] = {};
        if (vals) for (var i = 0; i < vals.length; i++) FLT[dim][String(vals[i])] = 1;
        return applyFilters();
      },
      toggleFilter: function(dim, val){
        if (!FLT[dim]) return 0;
        val = String(val);
        if (FLT[dim][val]) delete FLT[dim][val]; else FLT[dim][val] = 1;
        return applyFilters();
      },
      clearFilters: function(){
        FLT = { year: {}, bank: {}, cat: {} };
        return applyFilters();
      }
    };
    /* 首次渲染后立即套用（空筛选 = 全部 28 单），统一由 applyFilters 发布状态 */
    applyFilters();
    return items.length;
  }

  /* 尾部注入时立即执行；若脚本落在 <head>（DOM 未就绪）则等 DOMContentLoaded 重试 */
  var painted = run();
  if (!painted && document.readyState === 'loading' && document.addEventListener){
    document.addEventListener('DOMContentLoaded', run, false);
  }
})();
"""


# ════════════════════════════════════════════════════════════════
# 自检（Python 侧镜像 JS 聚合口径，独立于 build_v2.py）
# ════════════════════════════════════════════════════════════════
# 小数位纪律（与 JS 侧 PRECISION 一致，单一入口 + 防御性四舍五入）：
#   金额类 2 位 / 比率类 2 位 / 月数 1 位 / 期数 1 位；任何数值小数位 ≤ MAX_DECIMALS
PRECISION = {"yi": 2, "pct": 2, "months": 1, "periods": 1}
MAX_DECIMALS = 4
LONG_DECIMAL_RE = __import__("re").compile(r"\d+\.\d{5,}")   # 小数位 ≥5 即违规


def _to_fixed_safe(v, d):
    """按 d 位小数格式化；非有限值返回 —；消除 -0.00。"""
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if x != x or x in (float("inf"), float("-inf")):
        return "—"
    r = f"{x:.{d}f}"
    return f"{0:.{d}f}" if float(r) == 0 else r


def _yi(v):
    if v is None:
        return "—"
    x = float(v)
    return (_to_fixed_safe(x / 1e4, 2) + " 万") if abs(x) < 1e6 else (_to_fixed_safe(x / 1e8, 2) + " 亿")


def _pct(v):
    return "—" if v is None else _to_fixed_safe(float(v) * 100, 2) + "%"


def _fmt(kind, v):
    if kind == "yi":
        return _yi(v)
    if kind == "pct":
        return _pct(v)
    if kind == "periods":
        return "—" if v is None else _to_fixed_safe(v, PRECISION["periods"]) + " 期"
    if kind == "months":
        return "—" if v is None else _to_fixed_safe(v, PRECISION["months"]) + " 个月"
    # 兜底：未知 kind 也必须限位，绝不原样输出浮点
    return "—" if v is None else _to_fixed_safe(v, 2)


def _has(v):
    return v is not None and not (isinstance(v, float) and v != v)


def _sum(rows, key):
    s, n = 0.0, 0
    for r in rows:
        v = r.get(key)
        if not _has(v):
            continue
        s += float(v)
        n += 1
    return s, n


def _avg(rows, key):
    s, n = _sum(rows, key)
    return (s / n) if n else None


def _extreme(rows, key, direction):
    best, bv = None, None
    for r in rows:
        v = r.get(key)
        if not _has(v):
            continue
        if direction == "max" and not ((r.get("poolTotal") or 0) > 1.0):
            continue
        v = float(v)
        if bv is None or (v > bv if direction == "max" else v < bv):
            best, bv = r, v
    return None if best is None else (best, bv)


def _name(p):
    return p.get("short") or p.get("name") or p.get("code") or "—"


def _median(rows, key, require_pool=False):
    """中位数：返回 (值, n)。require_pool 时剔除入池规模缺失样本。"""
    xs = []
    for r in rows:
        v = r.get(key)
        if not _has(v):
            continue
        if require_pool and not ((r.get("poolTotal") or 0) > POOL_EPS):
            continue
        xs.append(float(v))
    if not xs:
        return None, 0
    xs.sort()
    m = len(xs) // 2
    val = xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2
    return val, len(xs)


# 参与「算术平均」口径的字段（须与 JS 侧 AVG_KEYS 一致）
AVG_KEYS = ["recRate", "secRatio", "xirrSen", "xirrSub", "vsForecast",
            "disposeFeeRate", "months", "n_periods"]
# 参与「中位数」口径的字段（须与 JS 侧 MEDIAN_KEYS 一致）
MEDIAN_KEYS = ["recRate", "xirrSub"]


def _aggregate(rows):
    iss, issn = _sum(rows, "issue")
    pool, pooln = _sum(rows, "poolTotal")
    rec, recn = _sum(rows, "recovered")
    no_pool = [_name(r) for r in rows if not ((r.get("poolTotal") or 0) > POOL_EPS)]
    no_sec = [_name(r) for r in rows if not _has(r.get("secRatio"))]
    no_months = [_name(r) for r in rows if not _has(r.get("months"))]
    avg, avg_n = {}, {}
    for k in AVG_KEYS:
        s, n = _sum(rows, k)
        avg[k] = (s / n) if n else None
        avg_n[k] = n
    avg["poolTotal"], avg_n["poolTotal"] = ((pool / pooln) if pooln else None), pooln
    avg["issue"], avg_n["issue"] = ((iss / issn) if issn else None), issn
    avg["recovered"], avg_n["recovered"] = ((rec / recn) if recn else None), recn
    med = {}
    for k in MEDIAN_KEYS:
        v, n = _median(rows, k, require_pool=(k == "recRate"))
        med[k] = {"v": v, "n": n}
    return {
        "n": len(rows),
        "valid": len(rows) - len(no_pool),
        "issueSum": iss,
        "poolSum": pool,
        "recSum": rec,
        "avg": avg,
        "avgN": avg_n,
        "med": med,
        "recWeighted": (rec / pool) if pool > 0 else None,
        "recWeightedN": pooln,
        "recMax": _extreme(rows, "recRate", "max"),
        "recMin": _extreme(rows, "recRate", "min"),
        "subMax": _extreme(rows, "xirrSub", "max"),
        "subMin": _extreme(rows, "xirrSub", "min"),
        "noPool": no_pool,
        "noSec": no_sec,
        "noMonths": no_months,
    }


def _summary_parts(cat, a):
    av, an, med = a["avg"], a["avgN"], a["med"]
    s1 = (f"{cat}共 {a['n']} 单，合计发行规模 {_yi(a['issueSum'])}，"
          f"合计入池本息费 {_yi(a['poolSum'])}，合计累计回收 {_yi(a['recSum'])}；"
          f"规模加权回收率 {_pct(a['recWeighted'])}（Σ回收÷Σ入池本息费，n={a['recWeightedN']}）、"
          f"算术平均回收率 {_pct(av['recRate'])}（n={an['recRate']}）、"
          f"中位回收率 {_pct(med['recRate']['v'])}（n={med['recRate']['n']}）。")
    s2 = (f"算术平均处置费率 {_pct(av['disposeFeeRate'])}（n={an['disposeFeeRate']}）、"
          f"算术平均证券化率 {_pct(av['secRatio'])}（n={an['secRatio']}）、"
          f"算术平均达成率 {_pct(av['vsForecast'])}（n={an['vsForecast']}）、"
          f"算术平均优先档XIRR {_pct(av['xirrSen'])}（n={an['xirrSen']}）、"
          f"算术平均次级档XIRR {_pct(av['xirrSub'])}（n={an['xirrSub']}）；"
          f"算术平均存续 {_fmt('months', av['months'])}（n={an['months']}）、"
          f"算术平均支付期数 {_fmt('periods', av['n_periods'])}（n={an['n_periods']}）。")
    d1 = (f"组内回收率最高 {_name(a['recMax'][0])}（{_pct(a['recMax'][1])}），"
          f"最低 {_name(a['recMin'][0])}（{_pct(a['recMin'][1])}）。") if (a["recMax"] and a["recMin"]) \
        else "组内回收率最高/最低项：—。"
    d2 = (f"次级档XIRR 最高 {_name(a['subMax'][0])}（{_pct(a['subMax'][1])}），"
          f"最低 {_name(a['subMin'][0])}（{_pct(a['subMin'][1])}）。") if (a["subMax"] and a["subMin"]) \
        else "次级档XIRR 最高/最低项：—。"
    return [s1, s2, d1 + d2]


def _band_value(a, key, src):
    """镜像 JS metricValue()：按取数来源取值，避免字段名撞名。"""
    if src == "sum":
        return a.get(key)
    if src == "weighted":
        return a["recWeighted"]
    if src == "avg":
        return a["avg"].get(key)
    if src == "median":
        e = (a.get("med") or {}).get(key)
        return None if e is None else e["v"]
    raise ValueError(src)


def _metric_n(a, key, src):
    """样本量：mirror JS metricN()。"""
    if src == "weighted":
        return a["recWeightedN"]
    if src == "median":
        e = (a.get("med") or {}).get(key)
        return 0 if e is None else e["n"]
    if src == "sum":
        return None
    return (a.get("avgN") or {}).get(key)


def _basis_text(basis, n):
    """mirror JS basisText()。"""
    if basis == "sum":
        return BASIS_TEXT["sum"]
    lab = BASIS_TEXT.get(basis, "")
    return lab if n is None else f"{lab} · n={n}"


def _spot_of(a, key, direction):
    return {"recRate": {"max": a["recMax"], "min": a["recMin"]},
            "xirrSub": {"max": a["subMax"], "min": a["subMin"]}}[key][direction]


def _metric_rows(rows):
    """复现 JS bandInner() 的 16 指标 + 4 点名格 → (标签, 渲染值, 口径副行)。"""
    a = _aggregate(rows)
    out = []
    for lab, kind, key, src, _hi, basis in BAND_METRICS:
        out.append((lab, _fmt(kind, _band_value(a, key, src)),
                    _basis_text(basis, _metric_n(a, key, src))))
    for lab, key, direction in BAND_SPOT:
        e = _spot_of(a, key, direction)
        out.append((lab, "—" if e is None else f"{_name(e[0])} {_pct(e[1])}",
                    BASIS_TEXT["spot"]))
    return out


def _card_rows(rows):
    """复现 JS paint() 的 8 项 + 底部 3 项（卡片文本同样纳入精度扫描）。"""
    out = []
    for p in rows:
        out += [(lbl, _fmt(kind, p.get(key))) for lbl, key, kind, _hi in FIELD_SPEC]
        out += [(lbl, _fmt(kind, p.get(key))) for lbl, key, kind in FOOT_SPEC]
    return out


def _long_decimals(text):
    """返回文本中所有小数位 ≥ MAX_DECIMALS+1 的数值 token。"""
    return LONG_DECIMAL_RE.findall(text or "")


def _max_decimals(text):
    best = 0
    for m in __import__("re").finditer(r"\d+\.(\d+)", text or ""):
        best = max(best, len(m.group(1)))
    return best


def _note_text(a):
    xs = []
    if a["noPool"]:
        xs.append(f"本息费未披露 {len(a['noPool'])} 单（{'、'.join(a['noPool'])}），"
                  f"其回收率与证券化率不计入算术平均与中位数")
    if a["noSec"]:
        xs.append(f"证券化率未披露 {len(a['noSec'])} 单（{'、'.join(a['noSec'])}）")
    if a["noMonths"]:
        xs.append(f"存续月数未披露 {len(a['noMonths'])} 单（{'、'.join(a['noMonths'])}）")
    return ("口径说明：" + "；".join(xs) + "。") if xs else ""


def _bands(prof, order):
    """按品种分桶（品种顺序：CAT_ORDER 优先，其余按 ORDER 首次出现）。"""
    rows = {}
    first = []
    for k in order:
        cat = prof[k].get("cat")
        if cat is None:
            continue
        if cat not in rows:
            rows[cat] = []
            first.append(cat)
        rows[cat].append(prof[k])

    def rank(c):
        return CAT_ORDER.index(c) if c in CAT_ORDER else 99

    cats = sorted(rows, key=lambda c: (rank(c), first.index(c)))
    return [(c, rows[c]) for c in cats]


def _groups(prof, order):
    """品种 → 银行 → [key]，银行按 ORDER 首次出现；返回 (组列表, 银行组数)。"""
    out, banks = [], 0
    for cat, _rows in _bands(prof, order):
        keys = [k for k in order if prof[k].get("cat") == cat]
        bk, seen = [], set()
        for k in keys:
            b = prof[k].get("issuer") or "未披露机构"
            if b not in seen:
                seen.add(b)
                bk.append((b, [k2 for k2 in keys if (prof[k2].get("issuer") or "未披露机构") == b]))
        banks += len(bk)
        out.append((cat, keys, bk))
    return out, banks


def _probe_dq_from_host(n_expect: int = 28):
    """从宿主报告各 #view-pN 提取数据质量信息（④ 的数据源）。

    与 JS collectDQ() 同口径：缺项数 ←「本单披露 N 项」，分级 ← .kbadge kA/kB/kC，
    影响 XIRR ← ⑧ 正文含 现金流/补录/折现/XNPV/口径不符。
    返回 list[dict]（与 ORDER 同序）或 None。
    """
    import re as _re

    for path in REPORTS:
        try:
            h = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if 'id="view-p0"' not in h:
            continue
        rows = []
        for idx in range(n_expect):
            i = h.find(f'id="view-p{idx}"')
            if i < 0:
                rows.append({"idx": idx, "nd": 0, "kA": 0, "kB": 0, "kC": 0, "afx": False})
                continue
            nxt = h.find(f'id="view-p{idx + 1}"', i)
            seg = h[i: nxt if nxt > 0 else i + 120000]
            # ⑧ fold 边界：从「数据质量与披露」到本节的 .foot（数据来源）
            j = seg.find("数据质量与披露")
            if j >= 0:
                k = seg.find('class="foot"', j)
                block = seg[j: k if k > j else j + 14000]
            else:
                block = ""
            m = _re.search(r"本单披露\s*<b>(\d+)</b>\s*项", seg)
            if m:
                nd = int(m.group(1))
            else:
                m2 = _re.search(r"(\d+)\s*项披露", block)
                if m2:
                    nd = int(m2.group(1))
                else:
                    nd = 0
            rows.append({
                "idx": idx,
                "nd": nd,
                "kA": len(_re.findall(r"kbadge kA", block)),
                "kB": len(_re.findall(r"kbadge kB", block)),
                "kC": len(_re.findall(r"kbadge kC", block)),
                "afx": bool(_re.search(r"现金流|补录|折现|XNPV|口径不符", block)),
            })
        return rows
    return None


def _find_browser():
    """找一个可用于 --headless --dump-dom 的 Chromium 内核浏览器（Edge/Chrome）。"""
    import os

    cands = [
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     r"Google\Chrome\Application\chrome.exe"),
    ]
    for p in cands:
        if p and Path(p).exists():
            return p
    return None


def _build_layout_html() -> str:
    """构造与宿主同构的独立页面：主题 .view 宽度 + 宿主 .vbands/.vband 规则
    + 本模块 CSS + __V2 数据 + 本模块 JS + 末尾量测脚本。"""
    payload = json.loads(_PAYLOAD.read_text(encoding="utf-8"))
    v2 = {"PROF": payload["PROF"], "ORDER": payload["ORDER"], "CAT": CAT_COLOR}
    n = len(payload["ORDER"])
    # 宿主主题中与本模块相关的少量规则（.view 宽度 / .vbands / .vband），
    # 用于验证样式覆盖是否真的生效
    host_css = """
    *,*::before,*::after{box-sizing:border-box}
    html,body{margin:0;padding:0;background:#F2F5F9;
      font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
    .layout{display:flex;min-height:100vh}
    .sidebar{flex:0 0 248px;background:#fff;border-right:1px solid #E5E9F0}
    .main{flex:1;min-width:0}
    .view{display:block;width:100%;max-width:1280px;margin:0 auto;
      padding:26px 28px 80px;background:#fff}
    .vbands{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
      gap:14px;margin:12px 0 4px}
    .vband{border:1px solid #E5E9F0;border-left:3px solid #ccc;border-radius:9px;
      background:#fff;padding:13px 15px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
    .vband .vt{font-weight:700;font-size:13.5px}
    .vband .vk{font-size:11.5px;color:#8A94A6}
    .ov-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:16px}
    .ov-card{border:1px solid #E5E9F0;border-radius:9px;background:#fff;padding:15px;cursor:pointer}
    .note{font-size:12px;color:#8A94A6;margin:6px 0}
    """
    bands = "".join(
        f'<div class="vband"><div class="vt">{c}</div><div class="vn">—</div></div>'
        for c in ["个人消费贷款", "个人经营贷款", "信用卡不良"])
    cards = "".join(
        f'<div class="ov-card rv" data-view="p{i}"></div>' for i in range(n))
    views = "".join(
        f'<section class="view" id="view-p{i}"><div class="card"><div class="cnl">'
        f'<p>本单披露 0 项。</p></div></div></section>' for i in range(n))
    measure = r"""
(function(){
  function q(s, r){ return (r||document).querySelector(s); }
  function qa(s, r){ return Array.prototype.slice.call((r||document).querySelectorAll(s)); }
  function top(e){ return e.getBoundingClientRect().top; }
  function bottom(e){ return e.getBoundingClientRect().bottom; }
  function w(e){ return e.getBoundingClientRect().width; }
  var res = { ok: false };
  try {
    var band = qa('#view-overview .vbands > .vband')[0];
    var bh = q('#view-overview .vbands > .vband .ov-bh');
    var br = q('#view-overview .vbands > .vband .ov-br');
    var bsub = q('#view-overview .vbands > .vband .ov-bsub');
    var bsum = q('#view-overview .vbands > .vband .ov-bsum');
    var bgrid = q('#view-overview .vbands > .vband .ov-bgrid');
    var flt = q('#view-overview .ov-flt');
    var noteBar = q('#view-overview .ov-ovnote');
    var vb = band, cs = getComputedStyle(vb);
    var padL = parseFloat(cs.paddingLeft) || 0, padR = parseFloat(cs.paddingRight) || 0;
    var innerW = vb.clientWidth - padL - padR;
    var cols = getComputedStyle(bgrid).gridTemplateColumns.split(' ').filter(Boolean);
    /* 指标网格实际行数 = 去重后的 top 值个数 */
    var tops = {};
    qa('#view-overview .ov-bgrid .ov-bk-item', band).forEach(function(x){
      tops[Math.round(top(x))] = 1;
    });
    res.ok = true;
    res.issueTop = +top(br).toFixed(2);
    res.subTop = +top(bsub).toFixed(2);
    res.topDiff = +Math.abs(top(br) - top(bsub)).toFixed(2);
    res.bhBottom = +bottom(bh).toFixed(2);
    res.bsumTop = +top(bsum).toFixed(2);
    res.bsumBelow = top(bsum) >= bottom(bh) - 0.5;
    res.bsumW = +w(bsum).toFixed(2);
    res.innerW = +innerW.toFixed(2);
    res.bsumRatio = +(w(bsum) / innerW * 100).toFixed(2);
    res.gridCols = cols.length;
    res.gridColW = cols.length ? +parseFloat(cols[0]).toFixed(2) : 0;
    res.metricItems = qa('#view-overview .ov-bgrid .ov-bk-item', band).length;
    res.metricRows = Object.keys(tops).length;
    res.filterBar = !!flt;
    res.filterAboveNoteBar = !!(flt && noteBar &&
      (flt.compareDocumentPosition(noteBar) & Node.DOCUMENT_POSITION_FOLLOWING));
    res.filterRows = qa('#view-overview .ov-flt-row').length;
    res.chips = qa('#view-overview .ov-flt-c').length;
    res.bandH = +band.getBoundingClientRect().height.toFixed(2);
    res.viewW = +q('#view-overview').clientWidth.toFixed(2);
    /* 6 列降级验证：@media(max-width:1180px) 时应为 4 列 */
    res.innerWidthPx = window.innerWidth;

    /* 真实点击驱动（验证事件委托，而非仅编程 API） */
    function hitTxt(){ var h = q('#view-overview .ov-flt [data-hit]'); return h ? h.textContent : ''; }
    function visCards(){
      return qa('#view-overview .ov-card').filter(function(c){
        return !c.classList.contains('ov-flt-off'); }).length;
    }
    function visDq(){
      return qa('#view-overview .ov-dq-c').filter(function(c){
        return !c.classList.contains('ov-flt-off'); }).length;
    }
    function emptyVisible(){
      var e = q('#view-overview .ov-empty');
      return !!e && !e.classList.contains('ov-flt-off');
    }
    function chipEl(dim, val){
      return q('#view-overview .ov-flt-row[data-dim="' + dim + '"] .ov-flt-c[data-v="' + val + '"]');
    }
    function clickChip(dim, val){
      var c = chipEl(dim, val);
      if (!c) return false;
      c.click();
      return true;
    }
    var C = {};
    /* 真机耗时：点击 → 重算 → 强制回流（含样式/布局） */
    var _t0 = performance.now();
    C.has2024 = clickChip('year', '2024');
    void document.body.offsetHeight;
    C.msToggle = +(performance.now() - _t0).toFixed(2);
    C.hit2024 = hitTxt();
    C.cards2024 = visCards();
    C.dq2024 = visDq();
    C.pressed2024 = chipEl('year', '2024') ? chipEl('year', '2024').getAttribute('aria-pressed') : null;
    C.clearOn = qa('#view-overview .ov-flt-clr.on').length;
    C.cntTxt = (q('#view-overview .ov-flt-row[data-dim="year"] [data-cnt]') || {}).textContent || '';
    C.bandTxt2024 = (q('#view-overview .vbands > .vband:not(.ov-flt-off) .ov-bn') || {}).textContent || '';
    C.summary2024 = ((q('#view-overview .vbands > .vband:not(.ov-flt-off) .ov-bsum p') || {})
                     .textContent || '').slice(0, 26);
    C.hasBOC = clickChip('bank', '中国银行');
    C.hitCombo = hitTxt();
    C.hasOp = clickChip('cat', '个人经营贷款');
    C.hitZero = hitTxt();
    C.emptyZero = emptyVisible();
    C.bandsZero = qa('#view-overview .vbands > .vband').filter(function(b){
      return !b.classList.contains('ov-flt-off'); }).length;
    var rb = q('#view-overview .ov-flt [data-reset]');
    C.hasReset = !!rb;
    if (rb) rb.click();
    C.hitReset = hitTxt();
    C.cardsReset = visCards();
    C.dqReset = visDq();
    C.emptyReset = emptyVisible();
    C.pressedReset = qa('#view-overview .ov-flt-c[aria-pressed="true"]').length;
    res.click = C;
  } catch (e) { res.err = String(e); }
  var pre = document.createElement('pre');
  pre.id = 'RESULT';
  pre.textContent = JSON.stringify(res);
  document.body.appendChild(pre);
})();
"""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>layout probe</title>
<style>{host_css}
{CSS}
</style></head><body>
<div class="layout"><div class="sidebar"></div><div class="main">
<section class="view" id="view-overview">
  <div class="ov-head">清算 28 单 · 单项目穿透分析 · 总览看板</div>
  <div class="note">按银行分组的 28 单 KPI 速览。</div>
  <div class="vbands">{bands}</div>
  <div class="ov-grid" data-chart="kpi-grid">{cards}</div>
</section></div></div>
{views}
<script>window.__V2 = {json.dumps(v2, ensure_ascii=False)};</script>
<script>{JS}</script>
<script>{measure}</script>
</body></html>"""


def _browser_layout_probe(viewport=(1500, 1700)):
    """用 Edge/Chrome headless 真机量测版式，返回 dict；无浏览器时返回 None。"""
    import os
    import re as _re
    import subprocess as _sp
    import tempfile as _tf

    exe = _find_browser()
    if not exe:
        return None
    html = _build_layout_html()
    fd, html_path = _tf.mkstemp(suffix=".html")
    os.close(fd)
    Path(html_path).write_text(html, encoding="utf-8")
    prof_dir = Path(_tf.mkdtemp(prefix="dsh_v8_prof_"))
    try:
        cmd = [
            exe, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            f"--user-data-dir={prof_dir}",
            f"--window-size={viewport[0]},{viewport[1]}",
            "--virtual-time-budget=4000", "--dump-dom",
            Path(html_path).as_uri(),
        ]
        r = _sp.run(cmd, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120)
        m = _re.search(r'<pre id="RESULT">(\{.*?\})</pre>', r.stdout or "", _re.S)
        if not m:
            return {"ok": False, "err": "no RESULT marker", "rc": r.returncode,
                    "stderr": (r.stderr or "")[:400]}
        return json.loads(m.group(1))
    except Exception as e:  # pragma: no cover
        return {"ok": False, "err": f"{type(e).__name__}: {e}"}
    finally:
        try:
            Path(html_path).unlink()
        except OSError:
            pass
        try:
            import shutil as _sh2
            _sh2.rmtree(prof_dir, ignore_errors=True)
        except Exception:
            pass


def _target_card_count():
    """在宿主报告里数 #view-overview 的 .ov-card 张数。返回 (张数, 命中路径)。"""
    for path in REPORTS:
        try:
            h = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        i = h.find('class="ov-grid"')          # DOM 元素（非 CSS 规则）
        if i < 0:
            continue
        seg = h[i:]
        j = seg.find("</section>")
        if j > 0:
            seg = seg[:j]
        return seg.count('class="ov-card'), path
    return None, None


def _target_band_count():
    """数宿主报告 #view-overview 里的 .vband 色块数（期望 3）。"""
    for path in REPORTS:
        try:
            h = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        i = h.find('class="vbands"')
        if i < 0:
            continue
        seg = h[i:]
        j = seg.find('class="ov-grid"')
        if j > 0:
            seg = seg[:j]
        return seg.count('class="vband"'), path
    return None, None


def _selfcheck():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ok = True

    def chk(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
        print(f"    {'✓' if cond else '✗'} {msg}")

    print("10_overview.py · 第 1 项精修·第二轮（品种整行总结卡 + 28 单聚类）自检")
    print("═" * 76)

    # ── 1. 导出长度 ──
    print("  一、导出常量（契约：CSS / HTML / JS 三个字符串）")
    print(f"    CSS {len(CSS):,} 字符 / {CSS.count(chr(10)) + 1} 行")
    print(f"    HTML {len(HTML)} 字符（纯客户端增强，服务端不渲染）")
    print(f"    JS   {len(JS):,} 字符 / {JS.count(chr(10)) + 1} 行")
    print(f"    导出合计 {len(CSS) + len(HTML) + len(JS):,} 字符")
    chk(bool(CSS) and bool(JS), "CSS / JS 均非空")
    chk(HTML == "", "HTML 为空串（服务端不渲染）")
    chk("(function(){" in JS and JS.rstrip().endswith("})();"), "JS 为单个 IIFE 且正确收口")
    chk("window.select" not in JS, "未依赖 window.select（宿主 select() 为 IIFE 私有，已核实）")
    chk("import" not in JS and "export " not in JS, "JS 无模块语法，可安全内联")
    # JS 语法门禁：有 node 就真解析一遍（new Function 等价于脚本级解析），
    # 无 node 则退化为括号/引号配平检查，避免把语法错误带进产物。
    import shutil as _sh
    import subprocess as _sp
    import tempfile as _tf
    import re as _re2

    _node = _sh.which("node")
    if _node:
        with _tf.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as _f:
            _f.write(JS)
            _tmp = _f.name
        try:
            _r = _sp.run([_node, "--check", _tmp], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
            _err = (_r.stderr or "").strip().splitlines()
            chk(_r.returncode == 0,
                f"node --check 语法解析通过{' → ' + _err[-1] if _r.returncode else ''}")
        except Exception as _e:  # pragma: no cover
            print(f"    · node --check 未能执行：{_e}")
        finally:
            try:
                Path(_tmp).unlink()
            except OSError:
                pass
    else:
        _bal = JS.count("(") == JS.count(")") and JS.count("{") == JS.count("}")
        chk(_bal, f"括号配平（无 node，降级检查）( / )={JS.count('(')}/{JS.count(')')}")

    # JS 运行时门禁：语法正确 ≠ 没有未定义引用（曾因删函数漏掉 has()/num() 而只在
    # 真机执行时暴露）。这里用最小 DOM 桩真跑一遍：能跑通且产出探针即算通过。
    if _node:
        _stub = r"""
const V2 = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const JS = require('fs').readFileSync(process.argv[3], 'utf8');
class CL{constructor(){this.s=new Set();}add(...c){c.forEach(x=>x&&this.s.add(x));}
 remove(...c){c.forEach(x=>this.s.delete(x));}contains(c){return this.s.has(c);}}
/* 极简 HTML 片段解析：让 innerHTML 生成可查询的节点树（供结构断言） */
const VOID=new Set(['br','img','input','hr','meta','link']);
function _parse(src){
  src=String(src).replace(/'([^']*)'/g,(m,i)=>'"'+i.replace(/"/g,'&quot;')+'"');
  const nodes=[],st=[{el:null,kids:nodes}];
  const re=/<!--[\s\S]*?-->|<\/?[a-zA-Z][^>]*>/g;let last=0,m;
  const pt=t=>{if(t)st[st.length-1].kids.push({_t:String(t),children:[]});};
  while((m=re.exec(src))){
    pt(src.slice(last,m.index));last=re.lastIndex;
    const tag=m[0];if(tag.startsWith('<!--'))continue;
    const close=tag.startsWith('</');
    const nm=(/^<\/?\s*([a-zA-Z][\w-]*)/.exec(tag)||[,''])[1].toLowerCase();
    if(close){for(let i=st.length-1;i>=1;i--){if(st[i].el&&st[i].el.tagName===nm.toUpperCase()){st.length=i;break;}}continue;}
    const el=new El(nm);
    const at=tag.replace(/^<\s*[a-zA-Z][\w-]*/,'').replace(/\/?>$/,'');
    const ar=/([\w:-]+)(?:\s*=\s*("([^"]*)"|([^\s"'>]+)))?/g;let a;
    while((a=ar.exec(at)))el.setAttribute(a[1],a[3]!==undefined?a[3]:(a[4]!==undefined?a[4]:''));
    st[st.length-1].kids.push(el);el.parent=st[st.length-1].el;
    if(!VOID.has(nm))st.push({el,kids:el.children});
  }
  pt(src.slice(last));return nodes;
}
class El{constructor(t){this.tagName=(t||'div').toUpperCase();this.attrs={};this.children=[];
 this.parent=null;this._c='';this._h='';this._t='';this.listeners=[];
 this.style={props:{},setProperty(k,v){this.props[k]=v;}};this.classList=new CL();}
 get className(){return this._c;}set className(v){this._c=String(v);
  this.classList.s=new Set(String(v).split(/\s+/).filter(Boolean));}
 get previousElementSibling(){const p=this.parent;if(!p)return null;
  const i=p.children.indexOf(this);for(let j=i-1;j>=0;j--){const c=p.children[j];if(c&&c.tagName)return c;}return null;}
 getAttribute(k){return k in this.attrs?this.attrs[k]:null;}
 setAttribute(k,v){this.attrs[k]=String(v);if(k==='class')this.className=v;}
 appendChild(c){if(c.parent){const i=c.parent.children.indexOf(c);if(i>=0)c.parent.children.splice(i,1);}
  c.parent=this;this.children.push(c);return c;}
 addEventListener(t,f){this.listeners.push({type:t,fn:f});}
 get innerHTML(){return this._h;}
 set innerHTML(v){this._h=String(v);this.children=_parse(this._h);
  for(const c of this.children)c.parent=this;}
 get textContent(){const w=n=>((n._t||'')+n.children.map(w).join(''));return w(this);}
 set textContent(v){this._t=String(v);this.children=[];}
 _desc(o){for(const c of this.children){if(!c||!c.tagName)continue;o.push(c);c._desc(o);}return o;}
 /* 复合简单选择器顺序解析：tag / #id / .cls / [attr=val] 可混写（如 .ov-flt-row[data-dim="year"]） */
 _msSimple(t){const s=String(t||'');if(!s)return true;let i=0;
  const attrOk=(at)=>{const eq=at.indexOf('=');if(eq<0)return at in this.attrs;
   const n=at.slice(0,eq).trim();let v=at.slice(eq+1).trim();
   if((v[0]==='"'&&v.slice(-1)==='"')||(v[0]==="'"&&v.slice(-1)==="'"))v=v.slice(1,-1);
   return n in this.attrs&&String(this.attrs[n])===v;};
  while(i<s.length){const ch=s[i];
   if(ch==='.'){let j=i+1;while(j<s.length&&/[\w-]/.test(s[j]))j++;
    if(!this.classList.contains(s.slice(i+1,j)))return false;i=j;}
   else if(ch==='#'){let j=i+1;while(j<s.length&&/[\w-]/.test(s[j]))j++;
    if(this.attrs.id!==s.slice(i+1,j))return false;i=j;}
   else if(ch==='['){const j=s.indexOf(']',i);if(j<0)return false;
    if(!attrOk(s.slice(i+1,j)))return false;i=j+1;}
   else if(/[a-zA-Z]/.test(ch)){let j=i;while(j<s.length&&/[\w-]/.test(s[j]))j++;
    if(this.tagName!==s.slice(i,j).toUpperCase())return false;i=j;}
   else return false;}
  return true;}
 _ms(tok){const nots=[];const base=String(tok).replace(/:not\(([^)]*)\)/g,(m,i)=>{nots.push(i.trim());return '';});
  for(const n of nots){ if(this._msSimple(n)) return false; }
  return base.trim().split(/\s+/).filter(Boolean).every(p=>this._msSimple(p));}
 querySelectorAll(sel){
  const toks=[];let buf='';
  for(const ch of String(sel)){if(ch===' '||ch==='>'||ch==='\t'||ch==='\n'){
    if(buf.trim()){toks.push(buf.trim());buf='';}if(ch==='>')toks.push('>');continue;}buf+=ch;}
  if(buf.trim())toks.push(buf.trim());
  const chain=[];for(const t of toks){if(t==='>')chain[chain.length-1].comb='>';
   else chain.push({sel:t,comb:' '});}
  if(!chain.length)return[];
  const tg=chain[chain.length-1];
  let pool=this._desc([]).filter(n=>n._ms(tg.sel));
  if(chain.length>1)pool=pool.filter(n=>{let cur=n,idx=chain.length-2;
   while(idx>=0){const st=chain[idx+1].comb,wt=chain[idx].sel;
    if(st==='>'){cur=cur.parent;if(!cur||!cur._ms(wt))return false;}
    else{let p=cur.parent,f=null;while(p){if(p._ms(wt)){f=p;break;}p=p.parent;}
     if(!f)return false;cur=f;}idx--;}return true;});
  return pool;}
 querySelector(s){return this.querySelectorAll(s)[0]||null;}}
const ORDER=V2.ORDER, PROF=V2.PROF;
const root=new El('body');
const sec=new El('section'); sec.setAttribute('id','view-overview'); root.appendChild(sec);
const vb=new El('div'); vb.className='vbands'; sec.appendChild(vb);
['个人消费贷款','个人经营贷款','信用卡不良'].forEach(c=>{
  const b=new El('div'); b.className='vband';
  const vt=new El('div'); vt.className='vt'; vt.textContent=c; b.appendChild(vt); vb.appendChild(b);});
const grid=new El('div'); grid.className='ov-grid'; sec.appendChild(grid);
/* ① 宿主 .note（服务端渲染的旧文案，JS 应改写它） */
const noteEl=new El('div'); noteEl.className='note';
noteEl.textContent='按银行分组的 28 单 KPI 速览（卡片顶条＝银行配色，品种 chip＝品种配色）。点击任意卡片进入单项目八节穿透视图。';
sec.children.unshift(noteEl); noteEl.parent=sec;
const cards=[];
for(let i=0;i<ORDER.length;i++){const c=new El('div');c.className='ov-card rv';
  c.setAttribute('data-view','p'+i);c.addEventListener('click',()=>{});grid.appendChild(c);cards.push(c);}
/* ④ 用 Python 从真实宿主提取的数据质量分布，构造等价的 #view-pN 结构，
   以端到端验证 JS 的 DOM 提取逻辑（缺项数 / A·B·C 分级 / 现金流口径）。 */
const DQ=JSON.parse(require('fs').readFileSync(process.argv[4],'utf8'));
ORDER.forEach((key,i)=>{
  const s=new El('section'); s.setAttribute('id','view-p'+i);
  const card7=new El('div'); card7.className='card';
  const cnl=new El('div'); cnl.className='cnl';
  const p7=new El('p'); p7.textContent='本单披露 '+(DQ[i].nd===null?0:DQ[i].nd)+' 项。';
  cnl.appendChild(p7); card7.appendChild(cnl); s.appendChild(card7);
  const fold=new El('div'); fold.className='fold';
  const fh=new El('div'); fh.className='fold-h';
  const ft=new El('span'); ft.className='ft'; ft.textContent='⑧ 数据质量与披露'; fh.appendChild(ft);
  const fsum=new El('span'); fsum.className='fold-sum';
  fsum.textContent=(DQ[i].nd===0?'无缺口':(DQ[i].nd+' 项披露')); fh.appendChild(fsum);
  fold.appendChild(fh);
  const fb=new El('div'); fb.className='fold-b';
  const addWarn=(cls)=>{const w=new El('div'); w.className='warn';
    const b=new El('span'); b.className='kbadge '+cls; w.appendChild(b); fb.appendChild(w);};
  for(let x=0;x<DQ[i].kA;x++) addWarn('kA');
  for(let x=0;x<DQ[i].kB;x++) addWarn('kB');
  for(let x=0;x<DQ[i].kC;x++) addWarn('kC');
  if(DQ[i].afx){const d=new El('div'); d.textContent='已按该金额补录该期次级档现金流'; fb.appendChild(d);}
  fold.appendChild(fb); s.appendChild(fold);
  root.appendChild(s);
});
/* 记录所有 innerHTML 与 createElement，供结构断言与小数位扫描 */
const seen={html:[],created:[],setterHits:0};
global.window={__V2:V2,innerWidth:1440,matchMedia:()=>({matches:false}),addEventListener(){}};
global.document={
  readyState:'complete', addEventListener(){},
  querySelector:s=>root.querySelector(s), querySelectorAll:s=>root.querySelectorAll(s),
  createElement:t=>{const e=new El(t);
    /* 记录 createElement 生成的容器与其 innerHTML，供结构/精度断言 */
    Object.defineProperty(e,'innerHTML',{
      configurable:true,
      get:function(){return this._h;},
      set:function(v){seen.setterHits++;seen.html.push(String(v));
        this._h=String(v);this.children=_parse(this._h);
        for(const c of this.children)c.parent=this;}});
    seen.created.push(e); return e;}};
try{
  new Function(JS)();
  new Function(JS)();   /* 幂等：第二次执行不应重复建块 */
  const p=global.window.__V2_10_overview;
  /* 品种行是宿主既有节点（非 createElement），需直接读取其 innerHTML */
  const bandEls=root.querySelectorAll('#view-overview .vbands > .vband');
  const bandHtml=bandEls.map(b=>String(b._h||''));
  console.log(JSON.stringify({ok:true,
    painted:p?p.painted:0, bands:p?p.bands:0, bandCards:p?p.bandCards:[], catGroups:p?p.catGroups:0,
    wraps:root.querySelectorAll('#view-overview .ov-grid > .ov-cat-wrap').length,
    banks:root.querySelectorAll('#view-overview .ov-bank-hd').length,
    moved:root.querySelectorAll('#view-overview .ov-cards .ov-card').length,
    wrapsCreated:seen.created.filter(e=>e._c==='ov-cat-wrap').length,
    banksCreated:seen.created.filter(e=>e._c==='ov-bank-hd').length,
    setterHits:seen.setterHits,
    bankHdHtmlFragments:seen.html.filter(h=>h.indexOf('ov-bh-t')>=0).length,
    bandHtmlLens:bandHtml.map(h=>h.length),
    bandHtmlHasBsum:bandHtml.map(h=>h.indexOf('ov-bsum')>=0),
    /* v8：品种行内部结构（信息行 → 虚线总结 → 指标区） */
    bandChildClasses:bandEls.map(b=>b.children.map(c=>c._c).join('|')),
    bgridCounts:bandEls.map(b=>b.querySelectorAll('.ov-bgrid > .ov-bk-item').length),
    bspotCounts:bandEls.map(b=>b.querySelectorAll('.ov-bspot > .ov-bk-item').length),
    btopLeftItems:bandEls.map((b)=>{const h=b.querySelector('.ov-bh');return h?h.children.length:0;}),
    listeners:cards.reduce((n,c)=>n+c.listeners.length,0),
    /* v5 新增：文案 / 提示条 / 达成率标记 / 数据质量块 / 口径副行 */
    noteText:(sec.querySelector('.note')||{})._t||'',
    noteBar:root.querySelectorAll('#view-overview .ov-ovnote .ov-ni').length,
    paidBadges:root.querySelectorAll('#view-overview .ov-card .obadge').length,
    dqCells:root.querySelectorAll('#view-overview .ov-dq-c').length,
    dqAfx:root.querySelectorAll('#view-overview .ov-dq-c.afx').length,
    dqLevels:(()=>{const a=[0,0,0,0];root.querySelectorAll('#view-overview .ov-dq-c').forEach(c=>{
      for(let l=0;l<4;l++){if(c._c.indexOf('lv'+l)>=0){a[l]++;return;}}});return a;})(),
    dqGridCols:root.querySelectorAll('#view-overview .ov-dq').length,
    metricCells:root.querySelectorAll('#view-overview .ov-bk-item').length,
    basisCells:root.querySelectorAll('#view-overview .ov-bk-item .b').length,
    ovk:root.querySelectorAll('#view-overview .ov-card .ov-k').length,
    bandTexts:bandHtml.map(h=>h.replace(/<[^>]+>/g,'|')),
    /* 全部渲染可见文本（卡片 + 品种行 + createElement 生成块 + 首句）：去标签后拼接 */
    renderText:(function(){const ps=[];
      root.querySelectorAll('#view-overview .ov-card').forEach(c=>ps.push(String(c._h||'')));
      bandHtml.forEach(h=>ps.push(h));
      seen.html.forEach(h=>ps.push(String(h)));
      const nt=sec.querySelector('.note'); if(nt)ps.push(String(nt._t||''));
      return ps.join('\n').replace(/<[^>]+>/g,'|');})(),
    dqFirstTitle:(root.querySelector('#view-overview .ov-dq-c')||{}).attrs
      ?((root.querySelector('#view-overview .ov-dq-c')||{}).attrs.title||''):'',
    /* v8：筛选器维度与逐场景重算结果 */
    filterDims:p?p.filterDims:null,
    fltBar:root.querySelectorAll('#view-overview .ov-flt').length,
    fltRows:root.querySelectorAll('#view-overview .ov-flt-row').length,
    fltChips:root.querySelectorAll('#view-overview .ov-flt-c').length,
    fltChipCounts:root.querySelectorAll('#view-overview .ov-flt-c .kc').length,
    fltAll:root.querySelectorAll('#view-overview .ov-flt-all').length,
    fltClr:root.querySelectorAll('#view-overview .ov-flt-clr').length,
    fltClrOn:root.querySelectorAll('#view-overview .ov-flt-clr.on').length,
    fltHit:(root.querySelector('#view-overview .ov-flt [data-hit]')||{})._t||'',
    emptyEl:root.querySelectorAll('#view-overview .ov-empty').length,
    filters:(function(){
      if(!p||!p.setFilter) return {err:'no filter api'};
      const snap=()=>({total:p.total,bands:p.bandCards.slice(),names:p.bandNames.slice(),
        cards:p.cardsVisible,dq:p.dqVisible,empty:p.emptyVisible,
        sum:p.summaryChars.slice(),
        heads:(p.summaryHeads||[]).slice(),
        basisN:(p.bandBasisN||[]).map(a=>a.join('|')),filter:p.filter,active:p.filterActive});
      const S={};
      const ms=fn=>{const t0=Date.now();fn();return Date.now()-t0;};
      S.all=snap();
      S.tAll=ms(()=>p.clearFilters());
      S.year2024=null; S.tYear=ms(()=>{p.setFilter('year',['2024']);}); S.year2024=snap();
      p.clearFilters(); S.bankBOC=snapAfter(p,'bank',['中国银行']);
      p.clearFilters(); S.catOp=snapAfter(p,'cat',['个人经营贷款']);
      p.clearFilters(); S.catCC=snapAfter(p,'cat',['信用卡不良']);
      p.clearFilters(); p.setFilter('year',['2024']); p.setFilter('bank',['平安银行']);
      S.combo=snap();
      p.clearFilters(); p.setFilter('year',['1999']); S.none=snap();
      p.clearFilters(); S.reset=snap();
      p.setFilter('year',['2024']); const once=snap(); p.setFilter('year',['2024']); S.idem=snap(); S.idemSame=JSON.stringify(once)===JSON.stringify(S.idem);
      p.clearFilters();
      return S;
      function snapAfter(pp,dim,vals){ pp.setFilter(dim,vals); return snap(); }
    })(),
    /* 运行时生成的全部文本（分组容器 + 品种行）统一做小数位扫描 */
    runtimeLongDecimals:seen.html.concat(bandHtml).join('\n').match(/\d+\.\d{5,}/g)||[]}));
}catch(e){ console.log(JSON.stringify({ok:false, error:String(e)})); process.exit(0); }
"""
        _jsf = _tmp_js = _stubf = _dqf = None
        try:
            _payload = _ASSET / "payload_28.json"
            _dq_rows = _probe_dq_from_host()
            if _dq_rows is None:
                _dq_rows = [{"idx": i, "nd": 0, "kA": 0, "kB": 0, "kC": 0, "afx": False}
                            for i in range(28)]
            _jsf = Path(_tf.mkstemp(suffix=".js")[1])
            _jsf.write_text(JS, encoding="utf-8")
            _stubf = Path(_tf.mkstemp(suffix=".js")[1])
            _stubf.write_text(_stub, encoding="utf-8")
            _dqf = Path(_tf.mkstemp(suffix=".json")[1])
            _dqf.write_text(json.dumps(_dq_rows, ensure_ascii=False), encoding="utf-8")
            # 注意：必须显式 utf-8 解码。Windows 默认 GBK，node 输出含中文时
            # subprocess 的读取线程会 UnicodeDecodeError 并静默返回 stdout=None。
            _r2 = _sp.run([_node, str(_stubf), str(_payload), str(_jsf), str(_dqf)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90)
            _line = [ln for ln in (_r2.stdout or "").splitlines() if ln.strip().startswith("{")]
            if not _line:
                ok = False
                print(f"    ✗ JS 运行时门禁无输出（rc={_r2.returncode}）")
                print(f"      argv={_r2.args}")
                print(f"      stdout={(_r2.stdout or '')[:300]!r}")
                print(f"      stderr={(_r2.stderr or '')[:300]!r}")
                print(f"      js={_jsf}(exists={_jsf.exists()}) stub={_stubf}(exists={_stubf.exists()})")
                _res = {}
            else:
                _res = json.loads(_line[-1])
            if _line and not _res.get("ok"):
                ok = False
                print(f"    ✗ JS 真机执行抛错：{_res.get('error')}")
                print(f"      （node --check 只验语法，未定义引用必须真跑才暴露）")
            elif _line:
                _p = _res
                chk(True, "JS 真机执行无异常（含未定义引用检查）")
                chk(_p.get("painted") == 28, f"执行产出 28 张卡（painted={_p.get('painted')}）")
                chk(_res.get("wraps") == 3 and _res.get("banks") == 14 and _res.get("moved") == 28,
                    f"执行后结构 品种组 {_res.get('wraps')} / 银行小组 {_res.get('banks')} / 搬运卡片 {_res.get('moved')}")
                chk(_res.get("banksCreated") == 14, f"createElement 生成 14 个银行小组容器（{_res.get('banksCreated')}）")
                chk(_res.get("listeners") == 28, f"28 个 click 监听未被破坏（{_res.get('listeners')}）")
                _lens = _res.get("bandHtmlLens") or []
                _has_bsum = _res.get("bandHtmlHasBsum") or []
                chk(len(_lens) == 3, f"3 个品种行均被重绘（{len(_lens)}）")
                chk(all(n > 500 for n in _lens) and all(_has_bsum),
                    f"品种行 HTML 非空且含 .ov-bsum：len={_lens} hasBsum={_has_bsum}")
                chk(_res.get("setterHits") == 21,
                    f"createElement 容器填充 = 21（14 银行 + 3 品种组 + 提示条 + 数据质量块 + 筛选条 + 空态，实际 {_res.get('setterHits')}）")
                chk(_res.get("bankHdHtmlFragments") == 14,
                    f"银行小组分隔标签片段 = 14（实际 {_res.get('bankHdHtmlFragments')}）")
                _ld = _res.get("runtimeLongDecimals") or []
                chk(not _ld, f"运行时生成文本（含 3 个品种行）无小数位 ≥5 的数值"
                             f"{'' if not _ld else ' → ' + str(_ld[:5])}")
                # ── v8 运行时门禁：品种行内部结构（信息行 → 虚线总结 → 指标区）──
                _bcc = _res.get("bandChildClasses") or []
                chk(all(c == "ov-bh|ov-bsum|ov-bk" for c in _bcc),
                    f"品种行子块顺序 = 信息行 → 虚线总结 → 指标区：{_bcc}")
                chk(_res.get("btopLeftItems") == [4, 4, 4],
                    f"信息行 4 项同排（品种名/单数/发行合计/规模说明）：{_res.get('btopLeftItems')}")
                chk(_res.get("bgridCounts") == [16, 16, 16],
                    f"每行指标 16 项（实际 {_res.get('bgridCounts')}）")
                chk(_res.get("bspotCounts") == [4, 4, 4],
                    f"每行点名格 4 项独立栅格（实际 {_res.get('bspotCounts')}）")
                # ── v8 运行时门禁：筛选器 ──
                _fd = _res.get("filterDims") or {}
                chk(_res.get("fltBar") == 1 and _res.get("fltRows") == 3,
                    f"筛选条唯一、3 行维度（bar={_res.get('fltBar')} rows={_res.get('fltRows')}）")
                chk(len(_fd.get("year") or []) == 4 and len(_fd.get("bank") or []) == 9
                    and len(_fd.get("cat") or []) == 3,
                    f"维度取值 年份{len(_fd.get('year') or [])} / 机构{len(_fd.get('bank') or [])} / 品种{len(_fd.get('cat') or [])}")
                chk(_res.get("fltChips") == 16 and _res.get("fltChipCounts") == 16,
                    f"芯片 4+9+3=16 且每个带计数（{_res.get('fltChips')}/{_res.get('fltChipCounts')}）")
                chk(_res.get("fltAll") == 3 and _res.get("fltClr") == 3
                    and _res.get("fltClrOn") == 0,
                    f"每维「全部」「清空」各 3 个，未选时清空隐藏"
                    f"（{_res.get('fltAll')}/{_res.get('fltClr')}/{_res.get('fltClrOn')}）")
                chk(_res.get("emptyEl") == 1, f"空态容器已就位（{_res.get('emptyEl')}）")
                _F = _res.get("filters") or {}
                if _F.get("err"):
                    ok = False
                    print(f"    ✗ 筛选 API 不可用：{_F.get('err')}")
                else:
                    def _fget(k):
                        return _F.get(k) or {}
                    _all, _y24 = _fget("all"), _fget("year2024")
                    _boc, _op = _fget("bankBOC"), _fget("catOp")
                    _cc, _cb = _fget("catCC"), _fget("combo")
                    _none, _rst, _idem = _fget("none"), _fget("reset"), _fget("idem")
                    chk(_all.get("total") == 28 and _all.get("bands") == [23, 3, 2],
                        f"默认全量 28 单 / 品种行 [23,3,2]（{_all.get('total')} / {_all.get('bands')}）")
                    chk(_all.get("cards") == 28 and _all.get("dq") == 28,
                        f"默认卡片与热力格均 28（{_all.get('cards')} / {_all.get('dq')}）")
                    chk(_y24.get("total") == 17, f"筛年份 2024 → 17 单（实际 {_y24.get('total')}）")
                    chk(_y24.get("bands") == [13, 2, 2],
                        f"2024 品种分布 [13,2,2]（实际 {_y24.get('bands')}）")
                    chk(_boc.get("total") == 2 and _boc.get("bands") == [1, 1],
                        f"筛中国银行 → 2 单 / 分布 [1,1]（{_boc.get('total')} / {_boc.get('bands')}）")
                    chk(_op.get("total") == 2 and _op.get("bands") == [2],
                        f"筛个人经营贷款 → 2 单 / 单品种行（{_op.get('total')} / {_op.get('bands')}）")
                    chk(_cc.get("total") == 23, f"筛信用卡不良 → 23 单（{_cc.get('total')}）")
                    chk(_cb.get("total") == 5, f"组合筛选 2024+平安银行 → 5 单（{_cb.get('total')}）")
                    chk(_none.get("total") == 0 and _none.get("empty") is True,
                        f"无命中 → 0 单且空态可见（{_none.get('total')} / {_none.get('empty')}）")
                    chk(_rst.get("total") == 28 and _rst.get("bands") == [23, 3, 2],
                        f"清空筛选 → 恢复 28 单（{_rst.get('total')}）")
                    chk(_F.get("idemSame") is True and _idem.get("total") == 17,
                        f"同条件重复触发结果一致（idemSame={_F.get('idemSame')}）")
                    # 总结文字随筛选变化（不是写死）
                    _h_all = _all.get("heads") or []
                    _h_y = _y24.get("heads") or []
                    chk(bool(_h_all) and bool(_h_y) and _h_all[0] != _h_y[0],
                        f"总结文字随筛选变化：全量「{(_h_all or [''])[0][:18]}…」vs 2024「{(_h_y or [''])[0][:18]}…」")
                    chk(_y24.get("sum") != _all.get("sum"),
                        f"总结字数随筛选变化：{_all.get('sum')} → {_y24.get('sum')}")
                    # 指标 n 与筛选后单数一致（个人经营贷款 2 单）
                    _b_all = _all.get("basisN") or []
                    _b_op = _op.get("basisN") or []
                    _opn = [x for x in (_b_op[0].split("|") if _b_op else []) if "n=" in x]
                    chk(_opn and all(x.endswith("n=2") for x in _opn),
                        f"筛品种后各口径 n 与单数一致（{set(_opn)}）")
                    # 性能
                    _t = max(_F.get("tAll") or 0, _F.get("tYear") or 0)
                    chk(_t < 300, f"单次筛选重算 {_t}ms < 300ms")
                    # 筛选条命中数实时更新
                    chk(_res.get("fltHit") == "命中 28 单",
                        f"筛选条显示命中数（{_res.get('fltHit')}）")
                # ── v5 运行时门禁 ──
                chk((_res.get("noteText") or "").startswith("按品种分组、组内按发起机构归集"),
                    f"① 运行时已改写首句：{(_res.get('noteText') or '')[:24]}…")
                chk(_res.get("noteBar") == 2, f"③⑤ 口径提示条 2 条（实际 {_res.get('noteBar')}）")
                chk(_res.get("paidBadges") == 6,
                    f"③ 达成率<80% 卡片标记 = 6（实际 {_res.get('paidBadges')}）")
                chk(_res.get("dqCells") == 28, f"④ 数据质量热力小格 = 28（实际 {_res.get('dqCells')}）")
                chk(_res.get("dqGridCols") == 1, f"④ 数据质量块唯一（实际 {_res.get('dqGridCols')}，幂等）")
                chk(_res.get("metricCells") == 60,
                    f"② 指标格 16+4 点名为 20/行 × 3 = 60（实际 {_res.get('metricCells')}）")
                chk(_res.get("basisCells") == 60,
                    f"② 每格均有口径副行 = 60（实际 {_res.get('basisCells')}）")
                chk(_res.get("ovk") == 224,
                    f"回归保持：.ov-k = 224（28 卡 × 8 项，实际 {_res.get('ovk')}）")
                _bt = "\n".join(_res.get("bandTexts") or [])
                _bare = _bt.replace("算术平均", "").count("平均")
                chk(_bare == 0, f"② 品种行内无裸「平均」（去「算术平均」后仍余 {_bare} 处）")
                # 全量渲染文本（含 28 卡 + 3 品种行 + 提示条 + 数据质量块 + 首句）
                _rt = _res.get("renderText") or ""
                _rt_bare = _rt.replace("算术平均", "").count("平均")
                chk(_rt_bare == 0, f"② 全量渲染文本无裸「平均」（仍余 {_rt_bare} 处）")
                chk("折价率" not in _rt, "回归保持：渲染文本无「折价率」")
                chk("账户配平" not in _rt, "回归保持：渲染文本无「账户配平」")
                chk("按银行分组" not in _rt, "① 渲染文本无「按银行分组」")
                chk("品种色为分类标识，不代表风险等级" in _rt, "⑤ 画面上可见「品种色为分类标识，不代表风险等级」")
                chk("与证券端本息兑付率不是一个口径" in _rt, "③ 画面上可见达成率口径提示")
                chk("证券端已兑付完毕" in _rt, "③ 画面上可见「证券端已兑付完毕」标记")
                chk("算术平均" in _rt and "规模加权" in _rt and "中位数" in _rt,
                    "② 画面上可见「算术平均 / 规模加权 / 中位数」三种口径字样")
                _dq1 = _res.get("dqFirstTitle") or ""
                chk(all(k in _dq1 for k in ("项目：", "缺项/披露：", "缺口分级：", "影响 XIRR：")),
                    f"④ 热力小格 tooltip 含四列（{_dq1[:40]}…）")
                # ④ 提取结果应与 Python 从宿主解析出的分布一致
                if _dq_rows:
                    _lv_exp = [0, 0, 0, 0]
                    for _r in _dq_rows:
                        _n = _r["nd"]
                        _lv_exp[0 if _n <= 0 else (1 if _n <= 2 else (2 if _n <= 9 else 3))] += 1
                    chk(_res.get("dqLevels") == _lv_exp,
                        f"④ 热力分级 JS 提取 {_res.get('dqLevels')} = 宿主解析 {_lv_exp}")
                    _afx_exp = sum(1 for _r in _dq_rows if _r["afx"])
                    chk(_res.get("dqAfx") == _afx_exp,
                        f"④ 涉及现金流口径 {_res.get('dqAfx')} = 宿主解析 {_afx_exp}")
        except Exception as _e:  # pragma: no cover
            ok = False
            print(f"    ✗ JS 运行时门禁未能执行：{type(_e).__name__}: {_e}")
        finally:
            for _p0 in (_jsf, _stubf, _dqf):
                if _p0 is not None:
                    try:
                        _p0.unlink()
                    except OSError:
                        pass

    # ── 2. 任务 A 布局（v8：信息行横排 + 虚线下方整行总结 + 指标 6 列）──
    print("─" * 76)
    print("  二、任务 A：品种分组色块 → 每个品种一整行（v8 版式）")
    chk("flex-direction:column !important" in CSS, ".vbands 纵向堆叠（每个品种一整行）")
    chk("grid-template-columns:none !important" in CSS, "覆盖主题 .vbands 的 auto-fill 栅格")
    # v8-B1 信息行：品种名/单数/发行合计/规模说明 全部同一水平线
    chk(".ov-bh{" in CSS and "flex-direction:row" in CSS and "align-items:center" in CSS,
        "信息行 .ov-bh 为水平 flex + 垂直居中（保证同一水平线）")
    chk("gap:0 12px" in CSS, "信息行行间距 0（不换行、不产生上下错位）")
    chk("flex:0 0 100%" not in CSS and ".ov-bsub" in CSS,
        "规模说明不再独占一行（去掉 flex:0 0 100%），改为紧跟发行合计")
    chk("white-space:nowrap" in CSS, "规模说明不折行（同一行内）")
    # v8-B2 虚线下方：整行横排总结
    chk("border-top:1px dashed rgba(26,34,48,.16)" in CSS,
        "品种总结以虚线分隔（虚线下方）")
    chk("width:100%;max-width:100%" in CSS, "品种总结占满整行（≥95% 容器宽）")
    chk(".ov-btop" not in CSS and ".ov-btop" not in JS,
        "旧 .ov-btop 两栏结构已移除（总结不再限宽 56%）")
    chk("line-height:1.7" in CSS, "总结文字行高 1.7")
    # v8-B3 指标 6 列（左贴框线）
    chk("align-self:stretch" in CSS and "padding-left:0" in CSS,
        "指标区下移为整行、左贴框线（padding-left:0）")
    chk("grid-template-columns:repeat(6,minmax(0,1fr))" in CSS,
        "指标网格 6 列（repeat(6,minmax(0,1fr))）")
    chk("#view-overview .vband .ov-bspot" in CSS, "点名格独立 6 列栅格（左对齐）")
    chk("max-width:1180px" in CSS and "max-width:900px" in CSS and "max-width:640px" in CSS,
        "6→4/3/2 列响应式降级齐备（≥1180px 保持 6 列）")
    _mrows_cnt = len(BAND_METRICS)
    _cols = 6
    _rows_n = -(-_mrows_cnt // _cols)
    print(f"    6×j 实测：{_mrows_cnt} 项 ÷ {_cols} 列 = {_rows_n} 行"
          f"（末行 {_mrows_cnt - _cols * (_rows_n - 1)} 项，grid 自动左对齐）")
    chk(_rows_n == 3 and (_mrows_cnt - _cols * (_rows_n - 1)) == 4,
        f"16 项 → 6 列 × 3 行，末行 4 项（实际 {_rows_n} 行 / 末行 {_mrows_cnt - _cols * (_rows_n - 1)} 项）")
    import re as _re3
    _rule = _re3.search(r"#view-overview \.vband \.ov-bgrid\{\s*display:grid;\s*"
                        r"grid-template-columns:repeat\((\d+),minmax\(0,1fr\)\)", CSS)
    _cols_eff = int(_rule.group(1)) if _rule else 0
    chk(_cols_eff == 6, f"CSS 实测 .ov-bgrid 列数 = {_cols_eff}（期望 6）")
    chk(".ov-bk-item" in CSS and ".ov-bk-item.spot" in CSS, "指标格 + 点名格样式齐备")
    chk(len(BAND_METRICS) == 16, f"关键指标 16 项（实际 {len(BAND_METRICS)}）")
    chk(len(BAND_SPOT) == 4, f"点名格 4 项（实际 {len(BAND_SPOT)}）")
    # bandInner 渲染顺序：信息行 → 总结 → 指标区
    _bh_at = JS.find("ov-bh\">'")
    _bsum_at = JS.find("ov-bsum\">'")
    _bk_at = JS.find("ov-eyebrow")
    chk(0 < _bh_at < _bsum_at < _bk_at,
        "bandInner 渲染顺序：信息行 → 品种总结 → 指标区")
    for lab, _kind, _key, _src, _hi, _basis in BAND_METRICS:
        if lab not in JS:
            ok = False
            print(f"    ✗ 指标『{lab}』未出现在 JS")
        if lab.count("平均") and "算术平均" not in lab and "加权" not in lab:
            ok = False
            print(f"    ✗ 指标『{lab}』含裸「平均」")
        if _basis not in BASIS_TEXT:
            ok = False
            print(f"    ✗ 指标『{lab}』口径 {_basis} 不在 BASIS_TEXT")
    for lab, _key, _dir in BAND_SPOT:
        if lab not in JS:
            ok = False
            print(f"    ✗ 点名格『{lab}』未出现在 JS")
    print(f"    指标/点名标签在 JS 中全部命中：{'✓' if ok else '（见上）'}")
    # 中位数与样本量
    chk(len(MEDIAN_KEYS) == 2 and all(k in JS for k in MEDIAN_KEYS),
        f"中位数口径字段 {MEDIAN_KEYS} 已在 JS 实现")
    chk("medianOf" in JS and "avgN" in JS, "JS 具备 medianOf() 与 avgN（样本量）")
    # 取值来源与聚合结构必须对得上（防止字段名撞名导致渲染成 —）
    chk("function metricValue" in JS and "a.avg[key]" in JS,
        "JS 取值走 metricValue()：sum→聚合字段 / avg→a.avg[字段] / weighted→recWeighted")
    chk(": src === 'sum'" in JS or "src === 'sum'" in JS, "JS 区分 sum 与 avg 取数来源")
    chk("a.avg.recRate" in JS and "a.avg.n_periods" in JS, "总结文字同样取 a.avg.*")

    # ── 2b. 措辞：简单平均 → 算术平均（v7 任务 2）──
    print("─" * 76)
    print("  二·B 措辞统一：「简单平均」→「算术平均」")
    _all_src = CSS + HTML + JS
    chk(_all_src.count("简单平均") == 0,
        f"模块输出「简单平均」= {_all_src.count('简单平均')} 次（期望 0）")
    _n_arith = _all_src.count("算术平均")
    chk(_n_arith > 0, f"「算术平均」出现 {_n_arith} 次")
    chk(BASIS_TEXT["simple"] == "算术平均", f"BASIS_TEXT['simple'] = {BASIS_TEXT['simple']}")
    chk("simple: '算术平均'" in JS, "JS BASIS_TEXT.simple = 算术平均")
    _labels = [m[0] for m in BAND_METRICS]
    chk(all("简单平均" not in x for x in _labels), "16 项指标标签无「简单平均」")
    chk(any(x.startswith("算术平均") for x in _labels),
        f"指标标签使用「算术平均」前缀（如 {[x for x in _labels if x.startswith('算术平均')][:2]}）")

    # ── 2c. 筛选器（静态契约）──
    print("─" * 76)
    print("  二·C 筛选器（年份 / 发起机构 / 品种切片，多选、自动重算）")
    chk("ov-flt" in CSS and "ov-flt" in JS, "筛选条样式与构建逻辑齐备")
    chk("data-dim" in JS and "aria-pressed" in JS, "芯片带 data-dim / aria-pressed（可多选）")
    chk("FLT = { year: {}, bank: {}, cat: {} }" in JS, "筛选状态三维护（year/bank/cat）")
    chk("function applyFilters" in JS and "applyFilters()" in JS,
        "存在统一重算入口 applyFilters()")
    chk("yearOf" in JS and "bankOf" in JS and "catOf" in JS,
        "维度取值 yearOf / bankOf / catOf 齐备（字段缺失有回退）")
    chk(r"(20\d{2})\s*年" in JS, "年份从项目名解析（PROF 无 year 字段）")
    chk("p.bank || p.issuer" in JS or "p.bank||p.issuer" in JS,
        "机构取 PROF.bank 否则回退 issuer")
    chk("当前筛选无项目，请调整条件" in JS, "空态文案「当前筛选无项目，请调整条件」")
    chk("setFilter" in JS and "clearFilters" in JS, "编程式筛选 API（自检/外部观测）")
    chk("ov-flt-off" in CSS, "筛选隐藏样式 .ov-flt-off")
    chk("ov-empty" in CSS and "ov-empty" in JS, "空态样式与容器齐备")
    chk("facetCount" in JS, "分面计数（chip 上实时显示可选单数）")
    chk("data-key" in JS, "卡片/热力格带 data-key（按 key 显隐，不重建节点）")
    chk('data-all="' in JS and ">全部</button>" in JS and ">清空</button>" in JS,
        "每维均带「全部 / 清空」按钮")
    chk(".ov-flt-clr" in CSS and "flt-clr" in JS,
        "清空按钮按需显示（有选中才出现）")
    chk("ov-flt-cnt" in CSS and "已选 ' + k + ' / '" in JS,
        "已选数量实时显示（已选 N / M）")

    # ── 2d. 真机版式实测（Edge/Chrome headless，量 getBoundingClientRect）──
    print("─" * 76)
    print("  二·D 真机版式实测（headless 浏览器量 getBoundingClientRect）")
    _lay = _browser_layout_probe()
    if _lay is None:
        print("    · 未找到 Edge/Chrome，跳过真机量测（不影响静态断言）")
    elif not _lay.get("ok"):
        ok = False
        print(f"    ✗ 真机量测失败：{_lay.get('err')}")
    else:
        print(f"    视口 {_lay.get('innerWidthPx')}px · #view-overview 宽 {_lay.get('viewW')}px"
              f" · 品种行高 {_lay.get('bandH')}px")
        print(f"    发行合计 top={_lay.get('issueTop')} ｜ 规模说明 top={_lay.get('subTop')}"
              f" ｜ 差值={_lay.get('topDiff')}px")
        print(f"    信息行 bottom={_lay.get('bhBottom')} ｜ 总结 top={_lay.get('bsumTop')}"
              f" ｜ 总结在下={_lay.get('bsumBelow')}")
        print(f"    总结宽 {_lay.get('bsumW')}px / 行内宽 {_lay.get('innerW')}px"
              f" = {_lay.get('bsumRatio')}%")
        print(f"    指标网格 {_lay.get('gridCols')} 列 × {_lay.get('metricRows')} 行"
              f"（{_lay.get('metricItems')} 项，首列 {_lay.get('gridColW')}px）")
        chk((_lay.get("topDiff") or 99) < 6,
            f"B-1 发行合计 与 规模说明 同一水平线：top 差 {_lay.get('topDiff')}px < 6px")
        chk(_lay.get("bsumBelow") is True,
            f"B-2 品种总结在信息行下方：bsumTop {_lay.get('bsumTop')} > bhBottom {_lay.get('bhBottom')}")
        chk((_lay.get("bsumRatio") or 0) >= 95,
            f"B-2 品种总结占满整行：{_lay.get('bsumRatio')}% ≥ 95%")
        chk(_lay.get("gridCols") == 6,
            f"B-3 指标网格实测算出 {_lay.get('gridCols')} 列（期望 6）")
        chk(_lay.get("metricRows") == 3 and _lay.get("metricItems") == 16,
            f"B-3 16 项 → {_lay.get('metricRows')} 行（期望 3）")
        chk(_lay.get("filterBar") is True and _lay.get("filterAboveNoteBar") is True,
            "筛选条存在且位于口径提示条之上")
        chk(_lay.get("filterRows") == 3 and _lay.get("chips") == 16,
            f"筛选条 3 行 / {_lay.get('chips')} 个芯片")
        # 真实点击驱动（事件委托路径，非编程 API）
        _ck = _lay.get("click") or {}
        print(f"    点击「2024」→ {_ck.get('hit2024')}；可见卡 {_ck.get('cards2024')}；"
              f"热力格 {_ck.get('dq2024')}；aria-pressed={_ck.get('pressed2024')}")
        print(f"    叠加「中国银行」→ {_ck.get('hitCombo')}；再加「个人经营贷款」→ "
              f"{_ck.get('hitZero')}，空态={_ck.get('emptyZero')}")
        print(f"    点「重置全部」→ {_ck.get('hitReset')}；可见卡 {_ck.get('cardsReset')}；"
              f"选中芯片 {_ck.get('pressedReset')}")
        chk(_ck.get("has2024") is True and _ck.get("hit2024") == "命中 17 单",
            f"C-1 点击年份 2024 → 命中 17 单（{_ck.get('hit2024')}）")
        chk(_ck.get("cards2024") == 17 and _ck.get("dq2024") == 17,
            f"C-2 卡片与热力格同步收敛到 17（{_ck.get('cards2024')} / {_ck.get('dq2024')}）")
        chk(_ck.get("pressed2024") == "true", "C-3 选中态 aria-pressed=true（视觉反馈）")
        chk(_ck.get("clearOn") == 1 and "已选 1 / 4" in (_ck.get("cntTxt") or ""),
            f"C-3b 选中后出现「清空」且计数显示已选 1 / 4（clearOn={_ck.get('clearOn')} cnt={_ck.get('cntTxt')}）")
        chk("13 单" in (_ck.get("bandTxt2024") or ""),
            f"C-4 品种行单数随筛选刷新（{_ck.get('bandTxt2024')}）")
        chk("共13单" in (_ck.get("summary2024") or "").replace(" ", ""),
            f"C-5 品种总结文字随点击刷新（{_ck.get('summary2024')}…）")
        chk(_ck.get("hitCombo") == "命中 1 单",
            f"C-6 叠加银行筛选（2024+中国银行）→ 1 单（{_ck.get('hitCombo')}）")
        chk(_ck.get("hitZero") == "命中 0 单" and _ck.get("emptyZero") is True
            and _ck.get("bandsZero") == 0,
            f"C-7 无命中 → 0 单 / 空态显示 / 品种行全隐（{_ck.get('hitZero')}）")
        chk((_ck.get("msToggle") or 999) < 300,
            f"C-9 真机单次筛选重算（点击→重算→回流）{_ck.get('msToggle')}ms < 300ms")
        chk(_ck.get("hitReset") == "命中 28 单" and _ck.get("cardsReset") == 28
            and _ck.get("dqReset") == 28 and _ck.get("emptyReset") is False
            and _ck.get("pressedReset") == 0,
            f"C-8 重置全部 → 恢复 28 单、选中态清空（{_ck.get('hitReset')}）")

    # ── 3. 任务 B 布局 ──
    print("─" * 76)
    print("  三、任务 B：28 单卡片按品种/银行聚类 + 区隔")
    chk(".ov-cat-wrap" in CSS and ".ov-cat-hd" in CSS, "品种组容器 + 组头样式")
    chk(".ov-bank-hd" in CSS, "银行小组分隔标签样式")
    chk("repeat(3,minmax(0,1fr))" in CSS, "组内卡片仍每行 3 张")
    chk("border-top:2px solid rgba(26,34,48,.09)" in CSS, "品种组之间分隔线")
    chk("margin:0 0 34px 0" in CSS, "品种组之间 34px 间距")
    chk("appendChild" in JS, "聚类用 appendChild 移动 DOM 节点（不重建）")
    chk("innerHTML = paint(p)" in JS, "卡片内容重绘（第一轮设计保持）")
    chk("grid-template-columns:1fr 1fr" in CSS and "nth-child(even)" in CSS, "卡片 2 列 × 8 项布局未改")
    chk("data-ov2" in JS and "grouped" in JS, "幂等标记 data-ov2=grouped")
    chk("querySelector('.ov-grid')" in JS or "querySelector('#view-overview .ov-grid')" in JS,
        "以 #view-overview（或其 .ov-grid）为定位根")
    chk("removed: ['账户配平']" in JS, "「账户配平」仍在移除清单")
    chk("账户配平" not in JS.replace("账户配平", "", 1), "「账户配平」仅出现在 removed 标记")

    # ── 3b. 口径统一：折价率 → 证券化率（全模块零残留）──
    print("─" * 76)
    print("  三·B 口径统一：折价率 → 证券化率")
    _all_out = CSS + HTML + JS
    chk(_all_out.count("折价率") == 0,
        f"本模块输出（CSS+HTML+JS）中「折价率」出现 {_all_out.count('折价率')} 次（期望 0）")
    chk(_all_out.count("证券化率") > 0,
        f"「证券化率」已出现 {_all_out.count('证券化率')} 次")
    # 渲染路径不得再读 discount（数据字段可留在 __V2，但不得被读取）
    _render_path = JS + CSS  # JS 即渲染路径；CSS 不含字段名
    _disc_hits = [s for s in ("discount", "p.discount", "avg.discount", '"discount"', "'discount'")
                  if s in _render_path]
    chk(not _disc_hits, f"渲染路径（JS/CSS）中 discount 出现 0 次{'' if not _disc_hits else ' → ' + str(_disc_hits)}")
    chk("secRatio" in JS and "p.secRatio" in JS and "a.avg.secRatio" in JS,
        "渲染路径改用 secRatio（PROF.secRatio / a.avg.secRatio）")
    chk("1 − 证券化率" not in _all_out and "1-证券化率" not in _all_out and "1 − 折价率" not in _all_out,
        "不含「＝1 − 证券化率」类换算提示")
    # 14/16 项指标里含证券化率格，且不再引用 discount
    _sec_m = [m for m in BAND_METRICS if m[2] == "secRatio" and m[3] == "avg"]
    chk(bool(_sec_m) and _sec_m[0][0] == "算术平均证券化率",
        f"BAND_METRICS 含证券化率格 ← {_sec_m[0][2] if _sec_m else '缺失'}")
    chk(FIELD_SPEC[5][0] == "证券化率" and FIELD_SPEC[5][1] == "secRatio",
        f"卡片 FIELD_SPEC[5] = 「{FIELD_SPEC[5][0]}」← {FIELD_SPEC[5][1]}")

    # ── 4. 拼接安全 / 特异性 ──
    print("─" * 76)
    print("  四、拼接安全与覆盖强度")
    chk(CSS.count("{") == CSS.count("}"), f"CSS 花括号配平 {CSS.count('{')}/{CSS.count('}')}")
    chk("</style" not in CSS.lower() and "</script" not in JS.lower(), "无提前闭合标签")
    import re as _re

    css_nc = _re.sub(r"/\*.*?\*/", "", CSS, flags=_re.S)
    weak = [ln.strip() for ln in css_nc.splitlines()
            if _re.search(r"\.(?:ov|vband|vbands)(?:-|[\s,{:.\[])", ln)
            and "{" in ln and not ln.lstrip().startswith("@")
            and "#view-overview" not in ln]
    chk(not weak, f"全部 .ov-*/.vband* 规则带 #view-overview 前缀{'' if not weak else ' → ' + str(weak)}")
    chk("!important" in CSS, "关键字号属性带 !important（压过主题同名规则）")

    # ── 5. 数据侧镜像核对 ──
    print("─" * 76)
    print("  五、数据侧镜像核对（payload_28.json）")
    data = None
    try:
        data = json.loads(_PAYLOAD.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover
        ok = False
        print(f"    ✗ payload 读取失败：{e}")

    if data:
        prof, order = data["PROF"], data["ORDER"]
        print(f"    数据源 payload_28.json · ORDER {len(order)} 单 · PROF {len(prof)} 键")
        # 只校验真正来自 PROF 的字段（src=sum 的 key 是聚合字段名，不在 PROF 里）
        allkeys = [s[1] for s in FIELD_SPEC] + [s[1] for s in FOOT_SPEC] + \
                  ["cat", "issuer", "accent"] + \
                  [m[2] for m in BAND_METRICS if m[3] != "sum"] + \
                  ["recRate", "xirrSub"]
        absent = sorted({k for k in allkeys if k not in prof[order[0]]})
        chk(not absent, f"所需字段全部存在{'' if not absent else ' → 缺 ' + str(absent)}")

        bands = _bands(prof, order)
        chk(len(bands) == 3, f"品种行数 = {len(bands)}（期望 3）")

        groups, bank_groups = _groups(prof, order)
        cat_keys = [c for c, _, _ in groups]
        print(f"    聚类组数：{len(groups)} 个品种 × 各自银行小组，银行小组合计 {bank_groups}")
        for cat, keys, bk in groups:
            print(f"      · {cat:<8} {len(keys):>2} 单 · 银行小组 {len(bk):>2} 个 → " +
                  "、".join(f"{b}({len(ks)})" for b, ks in bk))
        chk(len(groups) == 3, "品种聚类 = 3 组")
        chk(sum(len(keys) for _, keys, _ in groups) == 28, "聚类覆盖 28 单，无遗漏无重复")

        # 幂等：同一数据跑两次，聚合与总结逐字节一致
        r1 = [(_aggregate(rows), _summary_parts(c, _aggregate(rows)), _note_text(_aggregate(rows)))
              for c, rows in bands]
        r2 = [(_aggregate(rows), _summary_parts(c, _aggregate(rows)), _note_text(_aggregate(rows)))
              for c, rows in bands]
        chk(r1 == r2, "幂等：聚合/总结两次计算结果完全一致")

        print("─" * 76)
        print("  六、品种整行总结卡渲染（Python 镜像 JS 口径）")
        lens = []
        scanned = []          # (品种, 文本来源, 文本) —— 供小数位纪律全量扫描
        for cat, rows in bands:
            a = _aggregate(rows)
            parts = _summary_parts(cat, a)
            note = _note_text(a)
            txt = "".join(parts)
            lens.append(len(txt))
            print(f"    ── {cat}（{a['n']} 单，规模字段完整 {a['valid']} 单，色 "
                  f"{(CAT_COLOR.get(cat) or (rows[0].get('accent') or ''))}）")
            # 指标/点名/总结/卡片文本统一取自共享行构造器与总结函数，
            # 保证「打印出来的」＝「实际渲染的」，精度断言才有意义
            mrows = _metric_rows(rows)
            for lab, v, basis in mrows:
                if v == "—" and lab not in ("算术平均存续", "算术平均支付期数"):
                    ok = False
                    print(f"        ✗ {lab:<20}{v}  ← 取值失败（键名/聚合结构不一致）")
                else:
                    print(f"        {lab:<20}{v:<12}（{basis}）")
            print(f"        总结文字 {len(txt)} 字：")
            for s in parts:
                print(f"          {s}")
            if note:
                print(f"        脚注：{note}")

            scanned.append((cat, "指标/点名", "\n".join(v for _l, v, _b in mrows)))
            scanned.append((cat, "口径副行", "\n".join(b for _l, _v, b in mrows)))
            scanned.append((cat, "总结文字", txt))
            scanned.append((cat, "脚注", note))
            scanned.append((cat, "卡片文本",
                            "\n".join(v for _l, v in _card_rows(rows))))

            mx = max([_max_decimals(v) for _l, v, _b in mrows] + [_max_decimals(txt)] or [0])
            print(f"        本行最大小数位 {mx}（上限 {MAX_DECIMALS}）")

        chk(all(n > 100 for n in lens),
            f"品种总结文字字数 {lens}（均 > 100 字）")

        # ── 六·A0 v5 需求校验：①文案 ②平均口径 ③达成率 ④数据质量 ⑤语义色 ──
        print("─" * 76)
        print("  六·A0 v5 需求校验（①文案 ②平均口径 ③达成率 ④数据质量 ⑤语义色）")
        # ① 首句
        chk("按品种分组、组内按发起机构归集" in JS, "① JS 已改为「按品种分组、组内按发起机构归集」")
        chk("按银行分组" not in JS and "按银行分组" not in CSS,
            "① 不再出现「按银行分组」")
        chk("点击任意卡片进入单项目八节穿透视图" in JS, "① 首句保留进入路径说明（NOTE_TEXT 常量）")
        # ② 平均口径：标签带口径 + 副行样例量 + 中位数 + 无裸「平均」
        _bare_all = "\n".join(_summary_parts(c, _aggregate(rows))[0] +
                              _summary_parts(c, _aggregate(rows))[1]
                              for c, rows in bands)
        _bare_n = _bare_all.replace("算术平均", "").count("平均")
        chk(_bare_n == 0, f"② 总结文字无裸「平均」（去「算术平均」后仍余 {_bare_n} 处）")
        _mrows_all = "\n".join(lab + str(v) for c, rows in bands
                               for lab, v, _b in _metric_rows(rows))
        _bare_m = _mrows_all.replace("算术平均", "").count("平均")
        chk(_bare_m == 0, f"② 指标标签无裸「平均」（仍余 {_bare_m} 处）")
        # 模块输出（CSS+HTML+JS）全量：去「算术平均」后不得残留「平均」
        _bare_out = (CSS + HTML + JS).replace("算术平均", "").count("平均")
        chk(_bare_out == 0,
            f"② 模块输出（CSS+HTML+JS）无裸「平均」（去「算术平均」后仍余 {_bare_out} 处）")
        chk(all(("· n=" in b) or b == BASIS_TEXT["sum"] or b == BASIS_TEXT["spot"]
                for c, rows in bands for _l, _v, b in _metric_rows(rows)),
            "② 每个 算术平均/规模加权/中位数 副行都带样本量 n")
        # 中位数：信用卡不良 中位回收率 10.05%（Lead 给的示例值）
        _ccb = [r for r in bands if r[0] == "信用卡不良"]
        if _ccb:
            _med = _aggregate(_ccb[0][1])["med"]["recRate"]
            chk(_pct(_med["v"]) == "10.05%" and _med["n"] == 22,
                f"② 信用卡不良 中位回收率 = {_pct(_med['v'])}（n={_med['n']}）")
        # ③ 达成率口径
        chk("与证券端本息兑付率不是一个口径，两者不矛盾" in JS,
            "③ 达成率≠证券兑付率 结论条文案已注入")
        _low = [k for k in order
                if prof[k].get("vsForecast") is not None and float(prof[k]["vsForecast"]) < VSF_LOW]
        _paid = [k for k in _low
                 if (prof[k].get("senPaidPct") or 0) >= PAID_DONE
                 and (prof[k].get("subPaidPct") or 0) >= PAID_DONE]
        chk(len(_low) == 6, f"③ 达成率<80% 的卡片 = {len(_low)} 单")
        chk(len(_paid) == len(_low),
            f"③ 上述 {len(_low)} 单优先档/次级档本金均已兑付完毕（{len(_paid)} 单）→ 全打标记")
        chk("证券端已兑付完毕" in JS, "③ 卡片标记文案「证券端已兑付完毕」已实现")
        # ④ 数据质量
        _dq = _probe_dq_from_host()
        chk(_dq is not None, "④ 可从宿主各 #view-pN 提取数据质量信息")
        if _dq:
            chk(len(_dq) == 28, f"④ 提取覆盖 28 单（{len(_dq)}）")
            _zeros = [r["idx"] for r in _dq if r["nd"] == 0]
            chk(len(_zeros) == 3, f"④ 无缺口单 = 3（p{_zeros}）")
            _afx_idx = [r["idx"] for r in _dq if r["afx"]]
            chk(0 < len(_afx_idx) < 28,
                f"④ 披露涉及现金流/折现口径 = {len(_afx_idx)} 单（p{_afx_idx}）")
            _lv = [0, 0, 0, 0]
            for r in _dq:
                n = r["nd"]
                _lv[0 if n <= 0 else (1 if n <= 2 else (2 if n <= 9 else 3))] += 1
            chk(sum(_lv) == 28, f"④ 热力分级分布 {_lv}（0/1-2/3-9/≥10 项）")
            chk(max(r["kA"] for r in _dq) > 0, "④ A/B/C 缺口分级徽章可提取")
        chk("ov-dq" in CSS and "ov-dq" in JS, "④ 数据质量块样式与构建逻辑齐备")
        chk("data-ov2" in JS and "'dq'" in JS, "④ 数据质量块幂等标记")
        # ⑤ 语义色
        chk(COLOR_NOTE in JS, "⑤ 语义色提示「品种色为分类标识，不代表风险等级」已注入")
        chk("ov-ovnote" in CSS and "ov-ovnote" in JS, "⑤ 提示条样式与构建逻辑齐备")
        chk(CAT_COLOR["信用卡不良"] == "#A52524", "⑤ 品种色保持不变（未动全局配色）")

        # ── 六·A 口径校验：平均证券化率 + 平均折价率 ≈ 100%（同一数据子集）──
        print("─" * 76)
        print("  六·A 证券化率口径校验（同一子集内 算术平均证券化率 + 算术平均折价率 ≈ 100%，容差 0.02pp）")
        print("    品种              样本    算术平均证券化率  算术平均折价率    合计")
        for cat, rows in bands:
            both = [r for r in rows
                    if _has(r.get("secRatio")) and _has(r.get("discount"))]
            a_sr = (sum(float(r["secRatio"]) for r in both) / len(both)) if both else None
            a_dc = (sum(float(r["discount"]) for r in both) / len(both)) if both else None
            tot = (a_sr + a_dc) if (a_sr is not None and a_dc is not None) else None
            print(f"    {cat:<14}{len(both):>4} 单  "
                  f"{_pct(a_sr):>11}  {_pct(a_dc):>11}  {_pct(tot):>10}")
            chk(tot is not None and abs(tot - 1.0) <= 0.0002,
                f"{cat}：算术平均证券化率 {_pct(a_sr)} + 算术平均折价率 {_pct(a_dc)} = {_pct(tot)}（≈100%）")
            chk(a_sr is not None and abs(a_sr - (1.0 - a_dc)) <= 0.0002,
                f"{cat}：算术平均证券化率 = 1 − 算术平均折价率（同为 {_pct(a_sr)}）")
        # 逐单恒等：secRatio + discount == 1（有值样本）
        _bad_id = [k for k in order
                   if _has(prof[k].get("secRatio")) and _has(prof[k].get("discount"))
                   and abs(float(prof[k]["secRatio"]) + float(prof[k]["discount"]) - 1.0) > 1e-9]
        chk(not _bad_id, f"逐单 secRatio + discount = 1 全部成立{'' if not _bad_id else ' → 例外 ' + str(_bad_id)}")
        # secRatio 与 issue÷poolTotal 一致
        _bad_comp = [k for k in order
                     if prof[k].get("secRatio") is not None and (prof[k].get("poolTotal") or 0)
                     and abs(float(prof[k]["secRatio"]) - float(prof[k]["issue"]) / float(prof[k]["poolTotal"])) > 1e-12]
        chk(not _bad_comp, f"secRatio = 发行规模 ÷ 入池本息费 全部成立{'' if not _bad_comp else ' → 例外 ' + str(_bad_comp)}")
        # 信用卡不良基准（Lead 校验用）：8.48% 左右
        _cc = [r for r in bands if r[0] == "信用卡不良"]
        if _cc:
            _ccr = [r for r in _cc[0][1] if _has(r.get("secRatio"))]
            _cca = sum(float(r["secRatio"]) for r in _ccr) / len(_ccr)
            chk(abs(_cca - 0.0848) < 0.0005,
                f"信用卡不良 平均证券化率 = {_pct(_cca)}（基准 ≈8.48%）")
        _noSec = [k for k in order if not _has(prof[k].get("secRatio"))]
        chk(all(prof[k].get("secRatio") is None for k in _noSec),
            f"缺 secRatio 的单渲染为 —：{_noSec}")

        # ── 小数位纪律：全量扫描所有渲染数值文本 ──
        print("─" * 76)
        print("  六·B 小数位纪律（全量扫描渲染数值，上限 ≤ "
              f"{MAX_DECIMALS} 位；正则 \\d+\\.\\d{{5,}} 命中即失败）")
        bad, all_tokens = [], 0
        for cat, where, text in scanned:
            hits = _long_decimals(text)
            all_tokens += len(__import__("re").findall(r"\d", text))
            if hits:
                bad.append((cat, where, sorted(set(hits))[:6]))
        total_txt = "\n".join(t for _c, _w, t in scanned)
        print(f"    扫描范围 {len(scanned)} 段文本（3 品种 × 指标/点名·总结·脚注·28 单卡片文本）")
        print(f"    全书最大小数位 = {_max_decimals(total_txt)}")
        maxp = _max_decimals(total_txt)
        longest = sorted(set(__import__("re").findall(r"\d+\.\d+", total_txt)),
                         key=lambda s: -len(s.split(".")[1]))[:6]
        if bad:
            ok = False
            for cat, where, hits in bad:
                print(f"    ✗ {cat} · {where}：{hits}")
        chk(not bad, f"无小数位 ≥{MAX_DECIMALS + 1} 的数值（违规 {len(bad)} 段）")
        chk(maxp <= MAX_DECIMALS, f"全书最大小数位 {maxp} ≤ {MAX_DECIMALS}；样例 {longest}")
        chk("平均支付期数 " + _fmt("periods", 12.26086956521739) in
            "\n".join(t for _c, _w, t in scanned if _w == "总结文字"),
            f"平均支付期已限位（样例 12.26086956521739 → {_fmt('periods', 12.26086956521739)}）")
        # 逐项确认四类数值的小数位纪律
        chk(_fmt("periods", 12.26086956521739) == "12.3 期",
            f"期数 1 位：{_fmt('periods', 12.26086956521739)}")
        chk(_fmt("months", 23.194444) == "23.2 个月", f"月数 1 位：{_fmt('months', 23.194444)}")
        chk(_fmt("yi", 2575371857.0) == "25.75 亿", f"金额 2 位：{_fmt('yi', 2575371857.0)}")
        chk(_fmt("pct", 0.11643456) == "11.64%", f"比率 2 位：{_fmt('pct', 0.11643456)}")
        chk(_fmt("未知", 1.0 / 3) == "0.33", f"未知 kind 兜底限位：{_fmt('未知', 1.0 / 3)}")
        chk(_to_fixed_safe(-1e-9, 2) == "0.00", f"消除 -0.00：{_to_fixed_safe(-1e-9, 2)}")
        need_note = {c for c, rows in bands
                     if _aggregate(rows)["noPool"] or _aggregate(rows)["noSec"]
                     or _aggregate(rows)["noMonths"]}
        has_note = {c for c, rows in bands if _note_text(_aggregate(rows))}
        chk(has_note == need_note,
            f"口径脚注按需生成：需脚注品种 {sorted(need_note)} / 实际生成 {sorted(has_note)}")

        if _ctx is not None:
            full = _ctx.build_v2_data()
            p0 = full["PROF"][full["ORDER"][0]]
            _iss, _pool = p0.get("issue"), p0.get("poolTotal")
            _comp = (_iss / _pool) if (_iss and _pool) else None
            print(f"    （00_ctx 契约可用；secRatio 与 发行规模÷入池本息费 一致="
                  f"{_comp is not None and abs((p0.get('secRatio') or 0) - _comp) < 1e-12}）")

    # ── 6. 宿主 DOM ──
    print("─" * 76)
    print("  七、宿主报告 DOM 核对")
    n_card, hit = _target_card_count()
    if n_card is None:
        ok = False
        print(f"    ✗ 未找到宿主报告：{[p.name for p in REPORTS]}")
    else:
        print(f"    宿主 {hit.name}")
        chk(n_card == 28, f"#view-overview .ov-card 计数 = {n_card}（期望 28）")
    n_band, hit2 = _target_band_count()
    if n_band is None:
        ok = False
        print("    ✗ 未找到 .vbands 色块")
    else:
        chk(n_band == 3, f"#view-overview .vbands > .vband 计数 = {n_band}（期望 3）")

    print("═" * 76)
    print(f"  自检结论：{'通过（EXIT=0）' if ok else '存在问题（EXIT=1）'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_selfcheck())
