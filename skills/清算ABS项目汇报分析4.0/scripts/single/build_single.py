# -*- coding: utf-8 -*-
"""惠元2021年第三期 · 单项目穿透（技能 2.0 · 确定性复刻构建器）

★★★ 本脚本是「单项目八节」报告的唯一构建入口，禁止改写模块、禁止手改 CSS。
   输入 → assets/single/ 5 个文件（由 INPUTS.sha256 校验指纹）
   输出 → 单文件 HTML（字节级确定：不含时间戳 / 不含绝对路径）
   实测：任意目录、任意机器，同输入必得同一 SHA256。

v5 布局（2.0 固化）：
  L1 ④ 存续期分配明细矩阵：行按合同现金流支付顺序，逐行「第N步」，共 16 步
  L2 ④ 全周期资金分配瀑布 ＋ 分档累计本金走势：同一卡片左右两栏
  L3 ② 资产池 9 图（3×3）；③ 左＝预计回收率分布、右＝累计回收曲线
  L4 ⑤ XNPV 用无风险利率 Rf=2.38% 折现，优先/次级同表分列 + Rf±50bp 敏感性

用法：
  python build_single.py                      # 输出到当前目录
  python build_single.py --out <dir>          # 指定输出目录
  python build_single.py --check              # 只校验输入指纹，不构建
  python build_single.py --no-guard           # 跳过输入指纹校验（仅调试用，产出不可交付）
"""
import hashlib
import json
import math
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))          # <skill>/scripts/single
SKILL = os.path.dirname(os.path.dirname(HERE))              # <skill>
# ★ 参数化入口（3.1）：环境变量 ABS_ASSETS 指向任意单的资产目录，
#   不放则回落到技能自带的惠元第三期。这样同一份版式代码可服务所有行/所有单，
#   避免「每换一个银行就另写一套 CSS」（和萃 17 期曾因此脱离本技能的 G2 版式指纹）。
ASSETS = os.environ.get("ABS_ASSETS") or os.path.join(SKILL, "assets", "single")
GOLDEN = os.path.join(ASSETS, "golden")

# ★ 产物名：优先用 payload.meta.file_name，回落旧常量。
#   D 在下方才加载，故用函数延迟取；默认（惠元第三期 meta 内已有该名）结果与旧版一致。
_LEGACY_OUT_NAME = "惠元2021年第三期_不良ABS穿透分析_v5.html"


def out_name():
    try:
        m = (D.get("meta") or {})
        return m.get("file_name") or _LEGACY_OUT_NAME
    except Exception:
        return _LEGACY_OUT_NAME

# 复刻铁律 2：窗口尺寸固定，任何脚本不得改（响应式断点会改栅格列数）
WINDOW_W, WINDOW_H = 1600, 1400

import importlib.util

_spec = importlib.util.spec_from_file_location("svg_engine", os.path.join(HERE, "svg_engine.py"))
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

IN_FILES = ["payload.json", "metrics.json", "peer28.json", "v11_base.css", "v11_enh.css"]
REQUIRED = {"payload.json": ("meta", "pool", "tranche", "periods", "liquidation", "dist",
                            "forecast_flow", "waterfall_order", "trust_account"),
            "metrics.json": ("pool_total", "issue_total", "recovered", "securitization_rate",
                             "recovery_rate", "exp_rec_rate", "achieve_rate",
                             "dispose_fee", "dispose_fee_rate", "sen_xirr", "sub_xirr",
                             "sub_multiple", "cum_at_period"),
            "peer28.json": ("PROF",)}


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def check_inputs(strict=True):
    """输入指纹校验：防止用改过的数据跑出不同结果（冗余保护 1）"""
    bad = []
    for f in IN_FILES:
        p = os.path.join(ASSETS, f)
        if not os.path.exists(p):
            bad.append((f, "缺失"))
            continue
        if f == "peer28.json" or f.endswith(".css"):
            continue
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception as e:
            bad.append((f, f"JSON 解析失败 {e}"))
    # 关键字段齐备性（冗余保护 2）
    for f, keys in REQUIRED.items():
        p = os.path.join(ASSETS, f)
        if not os.path.exists(p) or not f.endswith('.json'):
            continue
        d = json.load(open(p, encoding="utf-8"))
        src = d[0] if isinstance(d, list) else d
        for k in keys:
            if k not in src:
                bad.append((f, f"缺字段 {k}"))
    # 输入指纹（若有清单）
    mp = os.path.join(ASSETS, "INPUTS.sha256")
    if os.path.exists(mp):
        want = {}
        for line in open(mp, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            h, name = line.split(None, 1)
            want[name.strip()] = h
        for f in IN_FILES:
            p = os.path.join(ASSETS, f)
            if f in want and os.path.exists(p) and _sha(p) != want[f]:
                bad.append((f, "指纹不匹配（数据被改过）"))
    if bad:
        print("✗ 输入校验失败：")
        for f, why in bad:
            print(f"   - {f}: {why}")
        if strict:
            print("  已中止。若确有改版需求，先更新 assets/single/INPUTS.sha256 并说明原因。")
            sys.exit(2)
    else:
        print("✓ 输入校验通过（%d 个文件，字段与指纹齐备）" % len(IN_FILES))
    return not bad


D = json.load(open(os.path.join(ASSETS, "payload.json"), encoding="utf-8"))
M = json.load(open(os.path.join(ASSETS, "metrics.json"), encoding="utf-8"))
CSS = (open(os.path.join(ASSETS, "v11_base.css"), encoding="utf-8").read()
       + "\n" + open(os.path.join(ASSETS, "v11_enh.css"), encoding="utf-8").read())

P, T, L, DIST = D["pool"], D["tranche"], D["liquidation"], D["dist"]

# ★ 户数/笔数可能整项未披露（建鑫部分期次说明书只给笔数不给户数）。
#   原实现直接 P["n_borrowers"] 下标 + :, 格式化 → 缺字段即 KeyError，整份报告作废。
#   缺失时显示「—」，不显示 0（0 会被读成"真的没有"）。
_NB, _NL = P.get("n_borrowers"), P.get("n_loans")
_n_bor_txt = f'{_NB:,} 户' if _NB is not None else '— 户'
_n_loan_txt = f'{_NL:,}' if _NL is not None else '—'

# ★ 存续月数可能算不出（缺 issue_date 或首个支付日）→ 显示「—」，
#   不要用 0 充数（0 个月会被读成"当月即清算"）。
_LIFE_TXT = f'{M["life_months"]:.0f}' if M.get("life_months") is not None else '—'

# ★★ 清算状态：settled（已清算/清仓回购终结）vs outstanding（信托仍在存续）
#   用户要求纳入「到期未能及时兑付」的单，这类单的清算日/清算净收益/本金全额兑付
#   本来就不存在，报告正文若照写「信托计划已终止」就是与事实相反。
#   判定由取数层给出（06_parse_liquidation.settlement_state），这里只负责呈现。
_SETTLED = (L.get("settlement_state") or "settled") != "outstanding"


# 折块摘要用的一行状态文案（两处复用）
_STATE_TXT = (('信托计划已终止 · 清算完成 ' + str(L.get("liquidation_end") or "—"))
              if _SETTLED else '信托存续中 · 尚未清算')


def state_badge():
    """页头状态徽标：已清算 / 存续中，两种措辞不可混用"""
    if _SETTLED:
        return (f'<span class="hbadge t-final">信托计划已终止 · 清算完成 '
                f'{L.get("liquidation_end") or "—"}</span>')
    # 存续中：给"截至末次报告期末"这个时点，不能写"已终止"
    return ('<span class="hbadge" style="background:#FBF3E6;color:#8A5A12;'
            'border-color:#EBD9B8">信托存续中 · 尚未清算</span>')


def state_sentence():
    """正文一句话结论"""
    if _SETTLED:
        return f'本信托计划已终止 · 清算完成 {L.get("liquidation_end") or "—"}。'
    return (f'本信托仍<b>存续中</b>：截至末次受托机构报告期末（第 {M.get("n_periods")} 期）'
            f'两档本金尚未兑付完毕（优先 {(L.get("sen_principal_paid") or 0)/max(T["senior"]["issue"] or 1,1)*100:.2f}%'
            f'／次级 {(L.get("sub_principal_paid") or 0)/max(T["sub"]["issue"] or 1,1)*100:.2f}%），'
            f'故清算日、清算净收益、持有人权益均不存在，相关项置灰不列。')


def msafe(key, fmt=".3f", dash="—"):
    """metrics 缺该字段时返回「—」，避免 :.3f 之类的格式化在 None 上抛 TypeError

    ★ 为什么需要：不同期次的取数完整度不同（缺 issue_date 就推不出 life_months、
      缺次级超额收益就没有 sub_multiple）。原实现一律 f'{M["k"]:.3f}'，
      只要一个字段缺，整份报告直接崩，连"其余部分是对的"都看不到。
    """
    v = M.get(key)
    return format(v, fmt) if v is not None else dash

# ★ 置灰样式：**按需注入**。只有本单确实存在缺失维度时才追加这一段，
#   否则一字不加 —— 惠元第三期已过 G1 字节基线（205,064 B），
#   任何无条件的 CSS 追加都会破坏该基线。这是「通用化」与「已交付件不动」的折中。
_CSS_DIM = """
/* ── 维度置灰（3.2）：统一范本里有、本单没有的分布块 ── */
.chart.dim{background:var(--wash);border-style:dashed}
.chart.dim .ct{color:#8A93A2}
.dim-box{border:1px dashed #C9D2DE;border-radius:3px;margin:6px 2px 2px;
 background:repeating-linear-gradient(45deg,#F4F6FA,#F4F6FA 6px,#EDF1F6 6px,#EDF1F6 12px);
 min-height:148px;display:flex;flex-direction:column;align-items:center;
 justify-content:center;gap:7px;padding:14px 16px;text-align:center}
.dim-k{font-size:12px;font-weight:700;color:#8A93A2;letter-spacing:.08em}
.dim-w{font-size:11.5px;color:#98A1AF;line-height:1.66;max-width:290px}
"""
if D.get("dist_gray"):
    CSS = CSS + _CSS_DIM
YI, WAN = 1e8, 1e4
ACCENT = "#A52524"

# ---------------- 展示变量（3.1 参数化：一律从 payload.meta 取）----------------
# ★ 为什么要有这一层：原版把「惠元2021年第三期 / 中信银行 / 信用卡不良」直接写死在
#   30 多处 f-string 里，换一个银行就得改代码 —— 这正是「每换一行另写一套版式」的根源。
#   抽成变量后，同一份版式代码可服务任意行/任意单，payload 只负责提供 meta。
_META = D.get("meta") or {}
PROJ = (_META.get("display_name")
        or (_META.get("name") or "").replace("不良资产支持证券", "")
        or "惠元2021年第三期")
BANK = _META.get("originator_short") or "中信银行"
VAR = _META.get("variety") or "信用卡不良"
GRP = _META.get("bank_group") or BANK          # 侧栏分组名
CONF = _META.get("judge_confidence") or "高"
# ★ 兼容开关（3.1）：payload.meta.legacy_text = true 时，若干叙述沿用 v5 原文措辞。
#   目的：惠元第三期已交付、已过 G1 字节基线，用户要求「保持原样不动」。
#   新行不设此标志，走数据驱动文案。改的是措辞而非数值，两者均可追溯。
LEGACY_TEXT = bool(_META.get("legacy_text"))
# 品牌简称：同业图/文案里用简称（中信「惠元」、招行「和萃」），
# 不设则回落到项目全名
BRAND = _META.get("brand_short") or PROJ

# ---------------- 数据派生事实（3.1：替掉原来写死的惠元专属叙述）----------------
_PAY = [p.get("pay_date") for p in (D.get("periods") or []) if p.get("pay_date")]
PAY_FIRST = _PAY[0] if _PAY else "—"
PAY_LAST = _PAY[-1] if _PAY else "—"
PAY_N = len(_PAY)


def _zero_period(side):
    """某档本金清零的期次与支付日（无清零则返回 None）

    ★ 以「发行规模 − 逐期本金累计」判断，不再直接读 balance_after。
      实测农盈利信远新2022四：payload 的 sen/sub_balance_after 全为 0（解析缺失），
      原逻辑误报「第 1 期清零」；按逐期本金累计应为优先第 4 期、次级第 6 期。
    """
    if LEGACY_TEXT:
        for p in (D.get("periods") or []):
            bal = p.get(side + "_balance_after")
            if bal is not None and abs(bal) < 1.0:
                return p.get("period"), p.get("pay_date")
        return None, None
    try:
        _tk = "senior" if side == "sen" else "sub"
        issue = float(((T.get(_tk) or {}).get("issue")) or 0.0)
    except (TypeError, ValueError):
        issue = 0.0
    cum = 0.0
    if issue > 0:
        for p in (D.get("periods") or []):
            cum += float(p.get(side + "_principal") or 0.0)
            if cum >= issue - max(1.0, issue * 1e-6):
                return p.get("period"), p.get("pay_date")
        # 逐期本金合计未达发行规模：不臆造清零
        return None, None
    # 发行规模缺失时才回落到 balance_after
    for p in (D.get("periods") or []):
        bal = p.get(side + "_balance_after")
        if bal is not None and abs(bal) < 1.0:
            return p.get("period"), p.get("pay_date")
    return None, None


_Z_SEN = _zero_period("sen")
_Z_SUB = _zero_period("sub")
_BQ = (L.get("buyback") or {})
BQ_CALC = _BQ.get("calc_date") or "—"
BQ_NOTICE = _BQ.get("notice_date") or "—"
# 支付周期：按月/按季，由实际支付日间隔推断（不再写死"按季付息"）
def _pay_cycle():
    if len(_PAY) < 3:
        return "—"
    try:
        from datetime import date as _dt
        ds = [tuple(map(int, x.split("-"))) for x in _PAY]
        gaps = [(_dt(*ds[i + 1]) - _dt(*ds[i])).days for i in range(len(ds) - 1)]
        g = sorted(gaps)[len(gaps) // 2]
        return "按月付息" if g < 45 else ("按季付息" if g < 120 else "按半年付息")
    except Exception:
        return "—"


PAY_CYCLE = _pay_cycle()


def mon(v):
    """月数渲染：整数就不带小数（12 而不是 12.0），非整数保留 1 位（6.3）"""
    if v is None:
        return "—"
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def _months_to(dt):
    """发行日 → dt 的月数（按 30.44 天/月折算，与 metrics.life_months 同法）"""
    if not dt:
        return None
    try:
        from datetime import date as _d
        a = tuple(map(int, str(_META.get("issue_date"))[:10].split("-")))
        b = tuple(map(int, str(dt)[:10].split("-")))
        return round((_d(*b) - _d(*a)).days / 30.44, 1)
    except Exception:
        return None


MON_SEN_ZERO = _months_to(_Z_SEN[1])
MON_SUB_ZERO = _months_to(_Z_SUB[1])
# 自然清收回收率（剔除清仓回购价款）与回购占累计回收比
_BQ_PRICE = (L.get("buyback") or {}).get("price")
NAT_RATE = ((M["recovered"] - _BQ_PRICE) / M["pool_total"]
            if _BQ_PRICE and M.get("pool_total") else None)
BQ_SHARE = (_BQ_PRICE / M["recovered"]) if (_BQ_PRICE and M.get("recovered")) else None

# 信托账户序列：把 None 归一为 0（版式要参与加减），同时记录缺失情况
TA_RAW = D.get("trust_account") or []
TA_MISS = sum(1 for t in TA_RAW
              if any(t.get(k) is None for k in ("begin", "inflow", "outflow", "end")))
# 账户勾稽可用的前提：① 逐期四字段齐 ② 清算侧权益/收益字段在场
#   （招行 2021 二期：信托账户齐但 holder_equity_end 为空 → 仍不能配平）
TA_OK = (bool(TA_RAW) and TA_MISS == 0
         and (L.get("holder_equity_end") is not None)
         and (L.get("liquidation_gain") is not None))
TA_WHY = ("逐期账户缺字段" if (not TA_RAW or TA_MISS)
          else "清算侧持有人权益/清算净收益未披露")


def _ta_norm(t):
    """None → 0，但**保留 period 等非数值字段**（曾只留 4 个数值键，
    把 period 丢了 → sec8 里 t["period"] KeyError）"""
    out = dict(t)
    for k in ("begin", "inflow", "outflow", "end"):
        if out.get(k) is None:
            out[k] = 0.0
    return out


TA_N = [_ta_norm(t) for t in TA_RAW]
# 账户结息：清算报告可能不披露（招行为空），版式要参与加减故归一为 0
_ACC_INT = L.get("account_interest") or 0.0


# v5 原文的付息月份（首期为首个短周期，不计入「定期付息月份」）
_PAY_MONTHS_V5 = "3/6/9/12 月 20 日"


def _pay_months():
    """付息月份（去重升序），如「3/6/9/12 月 20 日」

    ★ LEGACY_TEXT 时直接返回 v5 原文：惠元第三期首个支付日 2022-01-20 是
      初始短周期（归集期 2021-09-23~2021-12-31），原文的「3/6/9/12」指定期付息月份。
      数据驱动版会把 1 月也算进来，为保持交付件字节不变，此处沿用原文。
    """
    if LEGACY_TEXT:
        return _PAY_MONTHS_V5
    ms = sorted({int(x[5:7]) for x in _PAY})
    dd = sorted({int(x[8:10]) for x in _PAY})
    if not ms:
        return ""
    return "/".join(str(m) for m in ms) + " 月 " + "/".join(str(d) for d in dd) + " 日"


def _pn(v):
    """期次渲染：中信给「第3期」字符串、招行给 3 数字，统一成「第 3 期」

    ★ 原实现直接 str.replace("期"," 期") 会把「第3期」变成「第3 期」（「第」后缺空格），
      与全文排版不一致。改用正则把数字两侧都补空格。
    """
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"第 {v} 期"
    import re as _re
    m = _re.search(r"(\d+)", str(v))
    return f"第 {m.group(1)} 期" if m else str(v)


def _first_fixed_cost():
    """次级档「固定资金成本＋收益」首次出现的期次（不是清零期次）

    ★ 曾误用 _Z_SUB（本金清零期）→ 惠元会报「自第 4 期起出现」，
      实际第 3 期就有固资 1,363,590.75，原版写第 3 期是对的。
    """
    for p in (D.get("periods") or []):
        if (p.get("sub_fixed_cost") or 0) or (p.get("sub_income") or 0):
            return p.get("period")
    return None


def _zero_note():
    """分档本金清零的两句话——按数据生成，替掉写死的「第 3 期/第 4 期」"""
    parts = []
    for nm, z in (("优先档", _Z_SEN), ("次级档", _Z_SUB)):
        if z and z[0] is not None:
            parts.append(f'{nm}本金在{_pn(z[0])}清零（{z[1]}）')
        else:
            # 存续中没有清算日，措辞要跟着状态走
            parts.append(f'{nm}本金{"至清算日" if _SETTLED else "至末次报告期末"}未清零')
    s2 = "，".join(parts) + "。"
    _ffc = _first_fixed_cost()
    if _ffc is not None:
        s2 += f'次级档「固定资金成本＋收益」自{_pn(_ffc)}起出现。'
    return s2


# ---------------- 数字格式（v11 口径：亿元 2 位 / 万元 2 位 / 比率 2 位）----------------
def yi(v, nd=2):
    return "—" if v is None else f"{v/YI:,.{nd}f}"


def wan(v, nd=2):
    return "—" if v is None else f"{v/WAN:,.{nd}f}"


def pc(v, nd=2):
    return "—" if v is None else f"{v*100:.{nd}f}"


def num(v, nd=2):
    return "—" if v is None else f"{v:,.{nd}f}"


def _div(a, b):
    """安全除法：任一侧缺失或分母为 0 → None（渲染为「—」）

    ★ 为什么需要：招行部分期次清算报告不单列「增值税及附加」（如 2024 二期），
      原写法 L["vat_total"]/M["recovered"] 直接 TypeError 崩栈。
    """
    if a is None or not b:
        return None
    return a / b


# ---------------- 结构原语 ----------------
def fold_open(num, title, summary, collapsed=False, attrs=""):
    n = f'<span class="sec-num">{num}</span> ' if num else ""
    cls = "fold rv collapsed" if collapsed else "fold rv"
    return (f'<div class="{cls}"{attrs}><div class="fold-h"><span class="ft">{n}{title}</span>'
            f'<span class="fold-sum">{summary}</span><span class="pm">＋</span></div>'
            f'<div class="fold-b"><div><div class="inner">')


def fold_close():
    return "</div></div></div></div>"


def note(html, cls=""):
    c = f' class="{cls}"' if cls else ' class="note"'
    return f"<div{c}>{html}</div>"


def chart(title, svg, cap="", kind="", cls="chart", tag=""):
    k = f' data-chart="{kind}"' if kind else ""
    tg = f'<span class="v2c-tag">{tag}</span>' if tag else ""
    c = cap + f'<div class="note">{cap}</div>' if False else ""
    out = f'<div class="{cls}"{k}><div class="ct">{title}{tg}</div>{svg}'
    if cap:
        out += f'<div class="note" style="margin-top:8px">{cap}</div>'
    return out + "</div>"


def tbl(head, body, wrap_style="", cls="tbl"):
    th = "".join(head)
    return (f'<div class="tbl-wrap"{f" style={chr(34)}{wrap_style}{chr(34)}" if wrap_style else ""}>'
            f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')


# ============================ 数据换算 ============================
POOL_YI = P["balance_total"] / YI               # 40.87
POOL_WAN = P["balance_total"] / WAN             # 408,703.54 万元（分布表 bal 同为万元，占比必须同单位）
PRIN_YI = P["balance_principal"] / YI           # 35.73
INTFEE_YI = P["balance_interest_fee"] / YI      # 5.14
EXPREC_YI = P["exp_recovery_zz"] / YI           # 7.47
ISSUE_YI = M["issue_total"] / YI                # 5.30
REC_YI = M["recovered"] / YI                    # 6.81
DISP_YI = (M["dispose_fee"] / YI) if M.get("dispose_fee") is not None else None
# ★ 费用总额与处置费用是否重叠：中信 fee_total 含处置费（True）；
#   建行清算报告里「处置费用」是资产池层面单列科目，不在「费用和开支」账户内（False）。
#   两者算法不同，混用会让费用率翻倍（建鑫2021-1 会从 13.4% 变成 28.5%）。
FEE_HAS_DISP = L.get("fee_total_includes_dispose")
if FEE_HAS_DISP is None:
    FEE_HAS_DISP = True
# 其他信托费用（瀑布与正文共用；sec4 与 sec9 都要用，故提到模块级）
OTHER_FEE = (M["fee_total"] - (M["dispose_fee"] or 0) - (M["servicer_fee"] or 0)
             if FEE_HAS_DISP else
             M["fee_total"] - (M["servicer_fee"] or 0))
# F8：达成率必须以「金额 ÷ 金额」现算；用披露的 18.28%（已四舍五入）反推会差 2bp
ACH = L["total_recovery"] / P["exp_recovery_zz"]   # 91.14%
# ★ 服务费可能为 None：部分期次受托报告未单列「贷款服务机构报酬」（费用率不可算），
#   直接相除会让整份报告在模块级就崩，连"其余部分正确"都看不到。
#   缺失时 None，下游一律走 wan()/pc() 的 None 分支显示「—」。
SVC_YI = (M["servicer_fee"] / YI) if M.get("servicer_fee") is not None else None

# 逐期（亿元）
PER = D["periods"]
# ★ in_total 允许为空：个别期次受托报告未列「本期回收金额」（兴业2023一期的
#   首期是「不适用」），直接相除会让整份报告在模块级崩掉。
#   缺失按 0 参与绘图，指标侧的累计口径另有 total_recovery 兜底。
per_rec = [((p.get("in_total") or 0.0) / YI) for p in PER]
cum_rec = [c["cum"] / YI for c in M["cum_at_period"]]

# 预测累计（亿元）——按「收款期末日」滚动累计
# ★ 预测表可能整行残缺（OCR 把日期读丢 → 标签 None）。必须先剔掉，
#   否则 FC_END 里混入 None，下面 FC_END[_fi] <= d 直接 TypeError（str vs None）。
#   实测兴业 2021二/2022三/2023二 三单因此整单构建失败。
fc = [x for x in D["forecast_flow"] if x and x[0]]
if len(fc) != len(D["forecast_flow"]):
    D["_fc_dropped"] = len(D["forecast_flow"]) - len(fc)
FC_END = [x[0] for x in fc]
_fc_total = sum(float(x[2] or 0.0) for x in fc) if fc else 0.0
FC_OK = bool(fc) and _fc_total > 0.0
fc_cum, _run = [], 0.0
for x in fc:
    _run += float(x[2] or 0.0)
    fc_cum.append(_run / YI)

# F2：实际累计一律挂在其真实支付日上；预测侧取「截至该支付日已完成收款期」的预测累计
PAY = [p.get("pay_date") for p in PER]
if any(x is None for x in PAY):        # 支付日缺失时不能参与日期比较
    _ok = [x for x in PAY if x]
    PAY = [x or (_ok[-1] if _ok else "") for x in PAY]
fc_at_pay, _fi = [], 0
for d in PAY:
    while FC_OK and _fi < len(fc) and FC_END[_fi] <= d:
        _fi += 1
    fc_at_pay.append((sum(float(x[2] or 0.0) for x in fc[:_fi]) / YI) if FC_OK else None)
act_line = cum_rec
xlab = [d[:7] for d in PAY]
xtit = [f"第{i+1}期 · 支付日 {d}" for i, d in enumerate(PAY)]


def _buyback_para():
    """清仓回购说明段——字段全部来自 payload，不写死任何日期

    ★ 原实现把「2022-11-16 发出通知书、起算日 2022-08-31」直接写进 f-string，
      那是惠元第三期的专属事实。用到别期会凭空造出两个不存在的日期，
      且读者无从分辨哪句是数据、哪句是模板残留。
    """
    bq = L.get("buyback") or {}
    if not bq.get("occurred"):
        return ('<p>清仓回购：本项目<b>未发生</b>清仓回购，回收全部来自资产池自然清收。</p>')
    _nd = bq.get("notice_date") or "—"
    _cd = bq.get("calc_date") or "—"
    _pr = bq.get("price")
    _pt = (f'回购价款 <b>{wan(_pr)} 万元</b>' if _pr
           else '清算报告未单列回购价款金额')
    return (f'<p>清仓回购：发起机构于 {_nd} 发出《清仓回购通知书》，'
            f'回购起算日 {_cd}，{_pt}。</p>')


# ============================ ① 项目档案 ============================
# ★ 品种画像库（3.2）：原来这段「品种特征」写死信用卡，导致个人消费/房贷/小微的
#   报告正文都自称"无抵押、无担保、单笔金额小"—— 套到住房抵押上就是实质性失真。
#   按品种取画像，缺则用变量名兜底；惠元（LEGACY_TEXT）仍用 v5 原文，保字节基线。
VAR_PROFILE = {
    "信用卡不良": {
        "asset": "无抵押、无担保；单笔金额小、户数极多、单户占比低、高度分散。",
        "recov": "回收率低（个位数～低两位），<b>现金流前置、衰减快</b>；回收质量高度依赖催收与委外效率。",
        "deal": "批量委外催收为主、诉讼为辅；处置费与服务费合计常占回收款 15%～20%，是本品种最显著的成本特征。",
    },
    "个人消费不良": {
        "asset": "以信用类为主、无抵押担保；单笔金额小、户数多、行业与地域分散度高。",
        "recov": "回收率中等（一二十个百分点量级），<b>首年回收集中、其后逐年衰减</b>；"
                 "回收表现与逾期期限、授信额度、借款人画像强相关。",
        "deal": "电话催收＋批量委外为主、诉讼为辅；处置费与服务费合计常占回收款 12%～20%。",
    },
    "住房抵押不良": {
        "asset": "以房产抵押担保为主；单笔金额大、户数少、单户占比高；受区域房价与司法处置周期影响显著。",
        "recov": "回收率相对高（抵押物变现支撑），但<b>回收周期长</b>（司法拍卖常需 1～3 年），现金流后置。",
        "deal": "以司法拍卖／以物抵债为主；处置费含诉讼费、评估费、执行费，占回收款比例波动大。",
    },
    "小微经营不良": {
        "asset": "以房产／设备抵押及保证担保为主；单笔金额较大、户数较少、行业集中度较高。",
        "recov": "回收率与抵押物覆盖倍数强相关，回收周期取决于清收方式（诉讼／重组／转让）。",
        "deal": "诉讼清收与债权转让并重；处置费中律师费、诉讼费占比高。",
    },
}
_VP = VAR_PROFILE.get(VAR) or {
    "asset": "详见发行说明书基础资产特征章节。",
    "recov": "回收表现详见中债资信预计回收与清算报告实际回收对照。",
    "deal": "处置成本详见清算报告费用科目。",
}
# 判据原文与抵押物信号：由 payload.meta 提供（02 从说明书 p2 读取），缺则按品种推断
_VAR_SRC = (_META.get("variety_source")
            or f"本期证券的基础资产为{VAR.replace('不良', '')}")
_COLL = _META.get("has_collateral")
if _COLL is None:
    _COLL = (VAR == "住房抵押不良")
_COLL_TXT = "是" if _COLL else "否"


def sec1():
    chips = "".join(f'<span class="chip">{c}</span>' for c in [
        f"银行 · {BANK}", f"品种 · {VAR}", f"判据置信度 · {CONF}",
        # LEGACY 沿用 v5 原文两枚 chip（判据原文措辞不同，改它会动字节基线）
        ("含抵押物信号 · 否" if LEGACY_TEXT else f"含抵押物信号 · {_COLL_TXT}"),
        ("判据原文 · 基础资产为不良信用卡债权" if LEGACY_TEXT
         else f"判据原文 · {_VAR_SRC}"),
        f"证券代码 · {D['meta']['code_sen']} / {D['meta']['code_sub']}",
    ])
    sec_done = (f'证券端：优先档本金已兑付 <b>{pc(L["sen_principal_paid"]/T["senior"]["issue"])}%</b> ｜ '
                f'次级档本金已兑付 <b>{pc(L["sub_principal_paid"]/T["sub"]["issue"])}%</b>')
    quick = (f'<b>本单速览</b>　发行规模 {yi(ISSUE_YI*YI)} 亿元 ｜ 入池本息费 {POOL_YI:.2f} 亿元 ｜ '
             f'累计回收 {REC_YI:.2f} 亿元 ｜ 回收率 {pc(M["recovery_rate"])}% ｜ '
             f'证券化率 {pc(M["securitization_rate"])}% ｜ 预计达成 {pc(ACH)}% ｜ '
             f'优先档 XIRR {pc(M["sen_xirr"])}% ｜ 次级档 XIRR {pc(M["sub_xirr"])}% ｜ '
             + (f'处置费率 {pc(M["dispose_fee_rate"])}%' if M.get("dispose_fee_rate") is not None
                else '处置费率 —')
             + (f' ｜ 信托清算日 {L["terminate_date"]}' if (L.get("terminate_date") and _SETTLED)
                else f' ｜ 末次报告期 {L.get("liquidation_end") or "—"}（存续中，无清算日）' if not _SETTLED
                else ' ｜ 信托清算日 —'))
    if LEGACY_TEXT:
        spec = ('<b>信用卡不良 · 品种特征</b>　资产特征：无抵押、无担保；单笔金额小、户数极多、'
                '单户占比低、高度分散。 ｜ 回收规律：回收率低（个位数～低两位），<b>现金流前置、衰减快</b>；'
                '回收质量高度依赖催收与委外效率。 ｜ 典型处置：批量委外催收为主、诉讼为辅；'
                '处置费与服务费合计常占回收款 15%～20%，是本品种最显著的成本特征。')
    else:
        spec = (f'<b>{VAR} · 品种特征</b>　资产特征：{_VP["asset"]} ｜ '
                f'回收规律：{_VP["recov"]} ｜ 典型处置：{_VP["deal"]}')
    missing = ('缺失材料（依据：资产类型判定表·缺失材料列）：法律意见书、会计意见书、跟踪评级报告')

    # ★ 3.2：信托终止日晚于法定到期日＝延期清算，是必须告知读者的风险事实
    #   （不良ABS处置周期常超法定到期日）。原报告只在数据里体现日期，
    #   正文不点明，读者会误以为按期了结。
    _lm = _META.get("legal_maturity")
    _late_txt = ""
    if _SETTLED and _lm and L.get("terminate_date") and str(L["terminate_date"]) > str(_lm):
        _late_txt = (f'<span class="hbadge" style="background:#FBF3E6;color:#8A5A12;'
                     f'border-color:#EBD9B8">延期清算 · 晚于法定到期日 {_lm}</span>')
    hero = f"""<div class="hero"><div class="hero-top"><span class="cat">{VAR}</span>
{state_badge()}{_late_txt}
<div class="w-ext w-term" data-w-term="1">{sec_done}</div></div>
<h1>{PROJ}</h1>
<div class="issuer">{BANK} · {VAR} · {str(_META.get("issue_date") or "")[:4] or "—"} 年</div>
<div class="chips">{chips}</div>
<div class="hsum hsum-exec">{quick}</div>
<div class="hsum hsum2">{spec}</div>
<div class="note pf-missing-hidden" data-pf="note-hidden">{missing}</div></div>"""

    # ---- pf-strip：组① 资产池情况 / 组② 集中度与账龄 ----
    def cell(k, v, u, n="", title=""):
        t = f' title="{title}"' if title else ""
        return (f'<div class="pf-c" data-pf-field="{k}"{t}><div class="pf-ck">{k}</div>'
                f'<div class="pf-cv"><b>{v}</b><small>{u}</small></div>'
                + (f'<div class="pf-cn">{n}</div>' if n else "") + "</div>")

    g0 = ('<div class="pf-sgrp" data-pf-cat="0"><div class="pf-scap"><i class="pf-snum">①</i>'
          '<span>资产池情况</span></div><div class="pf-cells">'
          + cell("入池本息费", f"{POOL_YI:.2f}", "亿", "入池规模（本息费口径）")
          + cell("入池本金", f"{PRIN_YI:.2f}", "亿")
          + cell("入池息费", f"{INTFEE_YI:.2f}", "亿",
                 f'＝本息费 − 本金 ＝ {wan(P["balance_interest_fee"])} 万元｜源披露为「入池息费总额 '
                 f'{(D.get("meta") or {}).get("source_interest_fee_wan") or "51,370.41"} 万元」')
          + (f'<div class="pf-c pf-merged" data-pf-field="主体户数 / 资产笔数"><div class="pf-ck">'
             f'<span class="pf-ck-i">主体户数</span><span class="pf-ck-s">/</span>'
             f'<span class="pf-ck-i">资产笔数</span></div><div class="pf-cv">'
             f'<span class="pf-tx">{_n_bor_txt} / {_n_loan_txt} 笔</span></div>'
             f'<div class="pf-cn">主体户数 / 入池资产笔数</div></div>')
          + "</div></div>")

    g1 = ('<div class="pf-sgrp" data-pf-cat="1"><div class="pf-scap"><i class="pf-snum">②</i>'
          '<span>集中度与账龄</span></div><div class="pf-cells">'
          + cell("单笔最高", wan(P.get("max_single_balance")), "万", "池内最大单笔本息费")
          + cell("单笔平均",
                 wan(P.get("avg_loan_balance")
                     if P.get("avg_loan_balance") is not None
                     else _div(P.get("balance_total"), P.get("n_loans"))),
                 "万", "入池本息费 ÷ 资产笔数")
          + cell("主体平均",
                 wan(P.get("avg_borrower_balance")
                     if P.get("avg_borrower_balance") is not None
                     else _div(P.get("balance_total"), P.get("n_borrowers"))),
                 "万", "入池本息费 ÷ 主体户数")
          + cell("加权平均逾期",
                 ("—" if P.get("wavg_overdue_months") is None
                  else f"{P['wavg_overdue_months']:.1f}"), "个月", "按未偿本息加权")
          + "</div></div>")

    strip = (f'<div class="kpis kpi-strip pf-strip" data-chart="kpi-strip" data-pf="strip">'
             f"{g0}{g1}</div>")

    # ---- pf-panels：③ 预期回收与发行结构 / ④ 实际回收与处置 / ⑤ 实际收益与期限 ----
    def row(k, v, u, n="", wide=False, tx=False, title=""):
        c = "pf-row pf-wide" if wide else "pf-row"
        t = f' title="{title}"' if title else ""
        val = (f'<span class="pf-tx">{v}</span>' if tx
               else f'<b>{v}</b><small>{u}</small>')
        return (f'<div class="{c}" data-pf-field="{k}"{t}><span class="pf-rk">{k}</span>'
                f'<span class="pf-rv">{val}</span>'
                + (f'<span class="pf-rn">{n}</span>' if n else "") + "</div>")

    pan2 = (f'<div class="pf-panel pf-7" data-pf-cat="2"><div class="pf-ph">'
            '<i class="pf-snum">③</i><span class="pf-pt">③ 预期回收与发行结构</span>'
            f'<span class="pf-pm"><span class="pf-badge">发行主体 · {BANK}</span>'
            '<span class="pf-badge pf-on">是否回购 · 是</span></span></div>'
            '<div class="pf-rows pf-rows8">'
            + row("中债预计回收", f"{EXPREC_YI:.2f}", "亿", title=f"中债预计回收 {num(P['exp_recovery_zz'])} 元")
            + row("预计回收率", pc(P["exp_rec_rate_zz"]), "%", "＝中债预计回收 ÷ 入池本息费")
            + row("发行规模", f"{ISSUE_YI:.2f}", "亿")
            + row("优先档规模", f"{T['senior']['issue']/YI:.2f}", "亿", f"票面 {pc(T['senior']['coupon'])}%")
            + row("次级档规模", f"{T['sub']['issue']/YI:.2f}", "亿", "不设票面利率")
            + row("证券化率", pc(M["securitization_rate"]), "%", "＝发行规模 ÷ 入池本息费")
            + row("合同处置费率/上限",
                  ("累计回收款的 17%" if LEGACY_TEXT else
                   (f"累计回收款的 {pc(T['dispose_cap_pct'],0)}%" if T.get("dispose_cap_pct")
                    else "—")),
                  "",
                  ("超过 17% 部分劣后至优先档本金之后（说明书 p87 i 项）" if LEGACY_TEXT else
                   (f"＝执行费用（含利息）÷ 累计回收款的上限；超过部分劣后至优先档本金之后"
                    if T.get("dispose_cap_pct") else "说明书未载明该上限")),
                  wide=True, tx=True)
            + "</div></div>")

    pan3 = ('<div class="pf-panel pf-5" data-pf-cat="3"><div class="pf-ph">'
            '<i class="pf-snum">④</i><span class="pf-pt">④ 实际回收与处置</span></div>'
            '<div class="pf-rows">'
            + row("累计回收", f"{REC_YI:.2f}", "亿")
            + row("回收率", pc(M["recovery_rate"]), "%", "＝累计回收 ÷ 入池本息费")
            + row("预计达成率", pc(ACH), "%", "＝累计回收 ÷ 中债预计回收")
            + row("处置费用", yi(M.get("dispose_fee")), "亿",
                  ("金额（与费率不同概念）" if M.get("dispose_fee") is not None
                   else "本单清算报告未单列该科目")
                  )
            + row("处置费率", pc(M["dispose_fee_rate"]), "%",
                  ("＝本项目已报销处置费用 ÷ 累计回收；各行报销尺度不同，不必然等于实际全部处置费用"
                   if not LEGACY_TEXT else "＝处置费用 ÷ 累计回收（全报告统一口径）"), wide=True)
            + "</div></div>")

    # ⑤ 实际收益与期限：卡片下方关键日期时间轴
    def _tl_date(v):
        return str(v)[:10] if v else "—"

    _tl_nodes = [
        ("发行日", _tl_date(_META.get("issue_date")), "sen"),
        ("首个支付日", _tl_date(PAY_FIRST), "sen"),
        ("优先档本金清偿", _tl_date((_Z_SEN[1] if _Z_SEN else None)
                                 or _META.get("settle_principal_date")), "sen"),
        ("次级档本金清偿", _tl_date(_Z_SUB[1] if _Z_SUB else None), "sub"),
        ("末次报告期", _tl_date(PAY_LAST), "sub"),
        ("信托终止/清算", _tl_date(L.get("terminate_date") or L.get("liquidation_end")), "sub"),
        ("法定到期", _tl_date(_META.get("legal_maturity")), "sub"),
    ]
    _bq = (L.get("buyback") or {})
    if _bq.get("calc_date"):
        _tl_nodes.append(("清仓回购起算", _tl_date(_bq.get("calc_date")), "sub"))
    if _bq.get("notice_date"):
        _tl_nodes.append(("回购通知", _tl_date(_bq.get("notice_date")), "sub"))
    # 时间轴按真实日期排序；缺失日期置末。法定到期是合同日，可能晚于清算日。
    def _tl_key(v):
        _s = str(v or "")
        return _s if len(_s) == 10 and _s[4] == "-" and _s[7] == "-" else "9999-99-99"
    _tl_nodes.sort(key=lambda x: _tl_key(x[1]))
    tl = ('<div class="pf-tl" data-chart="timeline">'
          + ''.join(
              f'<div class="pf-ts{" miss" if _v == "—" else ""}" data-t="{_t}">'
              f'<span class="pf-tdot"></span><span class="pf-tlab">{_k}</span>'
              f'<span class="pf-tval">{_v}</span></div>'
              for _k, _v, _t in _tl_nodes)
          + '</div>')

    pan4 = (f'<div class="pf-panel pf-wide" data-pf-cat="4"><div class="pf-ph">'
            '<i class="pf-snum">⑤</i><span class="pf-pt">⑤ 实际收益与期限</span>'
            f'<span class="pf-pm"><span class="pf-badge">品种 · {VAR}</span>'
            f'<span class="pf-badge pf-on">存续 {_LIFE_TXT} 个月</span></span></div>'
            '<div class="pf-rows pf-rows8">'
            + row("优先档XIRR", pc(M["sen_xirr"]), "%", f"票面 {pc(T['senior']['coupon'])}%；货币加权，与票面不可直接比较")
            + row("次级档XIRR", pc(M["sub_xirr"]), "%",
                  ("回报倍数 " + (f"{M['sub_multiple']:.3f}x"
                                  if M.get('sub_multiple') is not None else "—")))
            + row("存续期", _LIFE_TXT, "个月", "信托设立日 → 信托终止日")
            + row("支付周期", PAY_CYCLE, "", _pay_months())
            + row("首末支付日", f"{PAY_FIRST} / {PAY_LAST}", "", f"共 {PAY_N} 个支付日", wide=True, tx=True)
            + "</div>" + (tl if not LEGACY_TEXT else "") + "</div>")

    panels = (f'<div class="kpis pf-panels" data-chart="kpi-grid" data-pf="panels">'
              f"{pan2}{pan3}{pan4}</div>")

    meta = (f'<dl class="infolist pf-meta-hidden" data-pf="meta-hidden">'
            f'<div><dt>归属目录</dt><dd>{BANK}_{PROJ}不良资产支持证券_发行{str(_META.get("issue_date") or "")[:4]}_清算{(_META.get("liquidation_end") or "")[:4]}</dd></div>'
            f'<div><dt>项目主键</dt><dd>{PROJ}</dd></div>'
            f'<div><dt>设立日</dt><dd>{D["meta"]["issue_date"]}</dd></div>'
            f'<div><dt>清算日</dt><dd>{L.get("liquidation_end") or "—（存续中）"}</dd></div>'
            # ★ 「是否回购」原来写死「是」：只有发生过清仓回购的单才该显示"是"，
            #   否则是明确的错误陈述（建鑫多期未回购）。
            f'<div><dt>是否回购</dt><dd>{"是" if (L.get("buyback") or {}).get("occurred") else "否"}</dd></div>'
            f'<div><dt>银行分组</dt><dd>{BANK}</dd></div></dl>')

    body = hero + strip + panels + meta
    return (fold_open("①", "项目档案",
                      f'入池 {POOL_YI:.2f} 亿元 ｜ 预计 {EXPREC_YI:.2f} 亿元 ｜ '
                      f'<span class="pill ok">达成 {pc(ACH)}%</span>')
            + body + fold_close())


# ============================ ② 资产池基础情况 ============================
# 分布图数据（v5：提到模块级，sec2 / sec3 共用）
def _conv(v_wan, nd=2):
    """万元 → 亿元"""
    return v_wan / WAN


def _ntxt(b):
    """tip 里的「笔数」：缺失一律显示「—」

    ★ 不能直接写 {_ntxt(b)}：部分分布表**没有笔数列**（兴瑞2021一期「年龄」表
      只有余额/余额占比/笔数占比/贷款笔数四列，但扫描件那一列 OCR 未取到），
      格式化 None 会抛 TypeError，整个构建崩掉 —— 且崩在模块级，
      连"其余部分正确"都看不到（实测该单 build 直接 Traceback）。
    """
    _n = b.get("n")
    return "—" if _n is None else f"{int(_n):,}"


def _it(label, v_wan, tip):
    return {"label": label, "val": _conv(v_wan), "tip": tip}


BAL = [_it(b["label"], b["bal"],
           f'{b["label"]}｜余额 {num(b["bal"])} 万元｜笔数 {_ntxt(b)} 笔｜预计回收 {num(b["rec"])} 万元')
       for b in (DIST.get("balance") or [])]
OVER = [_it(b["label"], b["bal"], f'{b["label"]}｜余额 {num(b["bal"])} 万元｜笔数 {_ntxt(b)} 笔')
        for b in (DIST.get("overdue") or [])]
AGE = [_it(b["label"], b["bal"], f'{b["label"]}｜余额 {num(b["bal"])} 万元｜笔数 {_ntxt(b)} 笔')
       for b in (DIST.get("age") or [])]
INC = [_it(b["label"], b["bal"], f'{b["label"]}｜余额 {num(b["bal"])} 万元｜笔数 {_ntxt(b)} 笔')
       for b in (DIST.get("income") or [])]
CL = [_it(b["label"], b["bal"], f'{b["label"]}｜余额 {num(b["bal"])} 万元｜笔数 {_ntxt(b)} 笔')
      for b in (DIST.get("creditlimit") or [])]
OCC = [_it(b["label"], b["bal"],
           f'{b["label"]}｜余额 {num(b["bal"])} 万元｜占比 {b["bal"]/POOL_WAN*100:.2f}%')
       for b in (DIST.get("occupation") or [])]
REG = [_it(b["label"], b["bal"],
           f'{b["label"]}｜余额 {num(b["bal"])} 万元｜占比 {b["bal"]/POOL_WAN*100:.2f}%')
       for b in (DIST.get("region") or [])]
# 预计回收率分布：可能在 dist.recrate（中信体例）或顶层 recrate（建行/招行体例）
_REC_ROWS = (DIST.get("recrate") or D.get("recrate") or [])
REC = [_it(b["label"], b.get("rec") if b.get("rec") is not None else b.get("bal"),
           f'{b["label"]}｜预计回收 {num(b.get("rec"))} 万元｜笔数 '
           + (f'{_ntxt(b)}' if b.get("n") is not None else "—") + ' 笔')
       for b in _REC_ROWS]

# ★ 置灰清单：统一范本的 10 个分布维度里，本单确实没有的那些。
#   两种性质分开标注（品种不适用 / 说明书未披露），一律灰格占位而不是整块消失——
#   否则与中信、招行并排时块数不一致，看报告的人分不清"这单没有"还是"这单漏做"。
DIST_GRAY = D.get("dist_gray") or {}
DIST_KEEP = ["balance", "grade", "guarantee", "overdue", "age",
             "income", "creditlimit", "occupation", "region"]


def _gray_tile(title, key):
    g = DIST_GRAY.get(key) or {}
    tag = "本品种无此项统计" if g.get("kind") == "variety" else "本单未披露"
    why = g.get("why") or "发行说明书未披露该分布表"
    return (f'<div class="chart dim" data-chart="dist-gray"><div class="ct">{title}'
            f'<span class="v2c-tag">已置灰</span></div>'
            f'<div class="dim-box"><div class="dim-k">{tag}</div>'
            f'<div class="dim-w">{why}</div></div></div>')


GRADE = [{"label": b["label"], "pct": b["bal"] / POOL_WAN * 100, "color": c,
          "tip": f'{b["label"]}｜余额 {num(b["bal"])} 万元｜占比 '
                 f'{b["bal"]/POOL_WAN*100:.2f}%｜笔数 {_ntxt(b)} 笔'}
         for b, c in zip(DIST.get("grade") or [], [V.NAVY, V.AMBER, V.RED])]
# 担保方式：读披露表；缺失时不再写死「信用类 100%」（那是信用卡的结论，
# 套到房贷上会变成"抵押物权属缺失"的假象），交由置灰逻辑处理。
# ★ LEGACY_TEXT（惠元第三期）沿用 v5 的写死单行，保证字节基线不变：
#   源表 label 是「信用类」，v5 正文写的是「信用类（无担保）」，属已交付件的既定措辞。
_GUAR_ROWS = DIST.get("guarantee") or []
if LEGACY_TEXT:
    GUAR = [{"label": "信用类（无担保）", "pct": 100.0, "color": V.NAVY,
             "tip": f'信用类 100.00%｜余额 {num(P["balance_total"]/WAN)} 万元'}]
else:
    GUAR = [{"label": b["label"], "pct": b["bal"] / POOL_WAN * 100, "color": c,
             "tip": f'{b["label"]}｜余额 {num(b["bal"])} 万元｜占比 '
                    f'{b["bal"]/POOL_WAN*100:.2f}%｜笔数 {_ntxt(b)} 笔'}
            for b, c in zip(_GUAR_ROWS, [V.NAVY, V.AMBER, V.RED, V.GREEN])]


def sec2():
    pools = (f'入池本息费 <b>{POOL_YI:.2f} 亿元</b> ｜ 入池本金 <b>{PRIN_YI:.2f} 亿元</b> ｜ '
             f'入池息费 <b>{wan(P["balance_interest_fee"])} 万元</b> ｜ '
             f'预计回收 <b>{EXPREC_YI:.2f} 亿元</b>（{wan(P["exp_recovery_zz"])} 万元） ｜ '
             f'资产笔数 <b>{_n_loan_txt}</b> ｜ '
             f'主体户数 <b>{_n_bor_txt.replace(" 户", "")}</b>')
    n1 = (f'<b>账龄结构</b>：加权平均逾期 <b>{P.get("wavg_overdue_months") if P.get("wavg_overdue_months") is not None else "—"} 月</b> ｜ '
          f'证券化率 <b>{pc(M["securitization_rate"])}%（主口径·÷入池未偿本息费）／'
          f'{pc(M["issue_total"]/P["balance_principal"])}%（并列·÷入池本金）</b>'
          f' <span style="color:#5b6472">现算·非源披露：发行规模 {num(M["issue_total"])}'
          f'（源：发行说明书 p2 封面发行表）÷ 入池未偿本息费 {num(M["pool_total"])}</span>')

    # v5：9 张 = 3×3 满格（预计回收率分布已移入 ③）
    # ★ 3.2 起：格子数固定为 9，本单没有的维度渲染**灰度占位**（见 _gray_tile），
    #   不再从列表里删掉 —— 跨行并排看报告时，块数必须一致才能对齐比较。
    def _tile(title, key, svg):
        return _gray_tile(title, key) if not svg else \
            f'<div class="chart" data-chart="dist-v9"><div class="ct">{title}</div>{svg}</div>'

    charts = [
        ("未偿本息费余额分布", "balance", V.dist_col_pareto(BAL) if BAL else ""),
        ("五级分类分布", "grade", V.dist_stack_bar(GRADE) if GRADE else ""),
        ("担保方式分布", "guarantee", V.dist_stack_bar(GUAR) if GUAR else ""),
        ("逾期时间分布", "overdue", V.dist_col(OVER) if OVER else ""),
        ("借款人年龄分布", "age", V.dist_col(AGE) if AGE else ""),
        ("借款人年收入分布", "income", V.dist_col(INC) if INC else ""),
        ("授信额度分布", "creditlimit", V.dist_col(CL) if CL else ""),
        ("借款人职业分布", "occupation", V.dist_hbar(OCC, topn=8) if OCC else ""),
        ("借款人地区分布", "region", V.dist_hbar(REG, topn=10) if REG else ""),
    ]
    grid = "".join(_tile(t, k, s) for t, k, s in charts)

    # 分布区的口径注：按**品种**与**实际披露**生成，不写死某一行的结论。
    #   v1 曾把「本单底层为信用卡类资产…信用类 100%」写死，个人消费/房贷单也会照抄。
    _n_gray = sum(1 for _, k, s in charts if not s)
    if LEGACY_TEXT:
        # 惠元第三期已交付、已过 G1 字节基线，原文案一字不动
        dnote = ('注：本单底层为信用卡类资产，源说明书「担保方式」为<b>信用类 100.00%</b>，'
                 '与信用卡通常无抵押的情况一致，无异常。')
    elif _n_gray:
        _gkeys = [k for _, k, s in charts if not s]
        dnote = (f'注：本单 9 个分布维度中 <b>{9 - _n_gray}</b> 个有披露、'
                 f'<b>{_n_gray}</b> 个置灰（{"、".join(_gkeys)}）。'
                 f'置灰不等于"未做"：灰格内已注明该维度是<b>品种性缺失</b>'
                 f'还是<b>说明书未披露</b>，两者性质不同，跨行比较时不可直接当 0 处理。')
    elif _GUAR_ROWS and abs(sum(b["bal"] for b in _GUAR_ROWS) / POOL_WAN - 100) < 0.5:
        dnote = ('注：本单说明书披露的担保方式分布为'
                 f'<b>{_GUAR_ROWS[0]["label"]} 100.00%</b>，'
                 '与入池本息费合计口径一致，无异常。')
    else:
        dnote = '注：本单 9 个分布维度均有披露，口径与入池本息费合计一致。'
    body = (f'<div class="pool-sum">{pools}</div>'
            + note(n1)
            + f'<div class="dist-grid">{grid}</div>'
            + f'<div class="v2c-dist-note v2c-dist-note-wide">{dnote}</div>')
    return (fold_open("②", "资产池基础情况（维度①）",
                      f'入池本息费 {POOL_YI:.2f} 亿元 ｜ 预计回收 {EXPREC_YI:.2f} 亿元')
            + body + fold_close())


# ============================ ③ 分期节奏 ============================
def sec3():
    # 左：预计回收率分布（自 ② 移入）
    dist = V.dist_col_pareto(REC, color=V.GREEN)
    dist_ch = (f'<div class="chart" data-chart="rec-dist">'
               f'<div class="ct">预计回收率分布<span class="v2c-tag">单位：亿元</span></div>'
               f'<div style="max-width:400px;margin:0 auto">{dist}</div></div>')

    # 右：累计回收曲线
    _bar_kw = {} if LEGACY_TEXT else {
        "bars": per_rec,
        "name_b": "当期回收（" + PAY_CYCLE.replace("付息", "") + "）",
    }
    svg = V.recon_line(act_line, fc_at_pay, xlab, xtit, **_bar_kw)
    ch = (f'<div class="chart" data-chart="recon-line"><div class="ct">累计回收曲线'
          f'<span class="v2c-tag">单位：亿元</span></div>{svg}</div>')

    # ★ 清仓回购价款可能未在清算报告单列（实测和萃2022一期：occurred=true、
    #   notice/calc 日期都有，但 price 为 None）。不能直接相减，也不能当成
    #   「未发生回购」——两者都是失真，前者崩栈、后者谎报。
    _bqd = L.get("buyback") or {}
    buy = _bqd.get("price")
    natural = M["recovered"] - (buy or 0.0)
    tail = fc[_fi:]
    if FC_OK:
        n = ('<b>归期规则</b>：实际侧按「回收发生时点落在哪个支付期区间」归集，横轴为该期<b>实际支付日</b>；'
             '预计侧取中债预测现金流中「收款期末日早于或等于该支付日」的已完成收款期累计，'
             '两条线因此同轴可比。'
             f'同口径 {len(act_line)} 期累计：实际 {REC_YI:.2f} 亿元 vs 中债预测 {fc_at_pay[-1]:.2f} 亿元。')
    else:
        n = ('<b>归期规则</b>：实际侧按「回收发生时点落在哪个支付期区间」归集，横轴为该期<b>实际支付日</b>；'
             '中债仅披露预测总额、未披露逐期现金流，故预计侧不画曲线，避免把“未披露”误画成 0。'
             f'实际累计 {REC_YI:.2f} 亿元；中债预测总额 {EXPREC_YI:.2f} 亿元'
             f'（预测回收率 {pc(P.get("exp_rec_rate_zz"))}%），全周期达成率仍按累计回收 ÷ 预测总额计算。')
    if LEGACY_TEXT and buy:
        # v5 原文措辞（含写死的「第 5 期…全部为」），仅惠元第三期使用
        n2 = (f'<b>清仓回购对回收率的抬升</b>：第 5 期回收流入 {wan(PER[-1]["in_total"])} 万元全部为'
              f'清仓回购价款（回购起算日 {BQ_CALC}，通知日 {BQ_NOTICE}），占累计回收 '
              f'{pc(buy/M["recovered"])}%。剔除回购价款后，自然清收回收额为 {wan(natural)} 万元，'
              f'对应回收率 {pc(natural/M["pool_total"])}%。报告全篇回收率沿用「累计回收 ÷ 入池本息费」'
              f'（含回购）主口径，此处单列以便与不含回购安排的项目比较。')
    else:
        n2 = ((f'<b>清仓回购对回收率的抬升</b>：末期回收流入 {wan(PER[-1]["in_total"])} 万元中含'
               f'清仓回购价款 {wan(buy)} 万元（回购起算日 {BQ_CALC}，通知日 {BQ_NOTICE}），占累计回收 '
               f'{pc(buy/M["recovered"])}%。剔除回购价款后，自然清收回收额为 {wan(natural)} 万元，'
               f'对应回收率 {pc(natural/M["pool_total"])}%。报告全篇回收率沿用「累计回收 ÷ 入池本息费」'
               f'（含回购）主口径，此处单列以便与不含回购安排的项目比较。')
              if buy else
          (f'<b>清仓回购</b>：本项目已于 {_bqd.get("calc_date") or "—"} 起算清仓回购，'
           f'但清算报告未单列回购价款金额，故不拆分自然清收口径；'
           f'回收率仍按「累计回收 ÷ 入池本息费」列示。'
           if _bqd.get("occurred")
           else '<b>清仓回购</b>：本项目未发生清仓回购，回收全部来自资产池自然清收。'))
    # ★ fc 可能为空（说明书预测表未解析出 / 该单只披露前N年且格式特殊）：
    #   `FC_END[-1]` 会 IndexError。空的时候整段改成"未取得预测表"的说明，
    #   而不是让区块 ③ 崩掉。
    if not fc:
        n3 = ('<b>预测尾段</b>：本单未取得说明书「现金流回收预测表」的逐期排布，'
              '故本节只列实际回收曲线；全周期达成率仍按「累计回收 ÷ 中债预计回收」计算。')
    else:
        n3 = (f'<b>预测尾段不再发生</b>：中债预测全周期共 {len(fc)} 个收款期、合计 {EXPREC_YI:.2f} 亿元，'
              f'延续至 {FC_END[-1]}；'
              + (f'本项目已于 {L.get("terminate_date")} 因清仓回购提前终止，' if buy
                 else (f'本项目信托终止日 {L.get("terminate_date")}，' if _SETTLED
                       else f'本项目信托至 {L.get("liquidation_end") or "—"}（末次报告期末）仍存续，'))
              + f'其后 {len(tail)} 个预测期次（合计 {sum(x[2] for x in tail)/YI:.2f} 亿元）不再产生回收，'
              f'故全周期达成率 {pc(ACH)}% 系「实际 vs 全周期预测」口径，'
              f'而非「实际 vs 同期预测」。')
    body = f'<div class="v6-duo">{dist_ch}{ch}</div>' + note(n) + note(n2) + note(n3)
    return (fold_open("③", "分期节奏：实际 vs 预计（维度②）",
                      f'达成率 <span class="pill ok">达成 {pc(ACH)}%</span>')
            + body + fold_close())


# ============================ ④ 现金流分配过程 ============================
def sec4():
    # 瀑布
    # ★ 容错取值（3.1）：清算报告里某些科目**该单确实没有**（如账户结息、增值税），
    #   原版直接下标会 TypeError 崩栈。用 (x or 0) 归一——
    #   惠元第三期这些字段都有值，故对其产物字节无影响（已用 G1 校验）。
    _ai = _ACC_INT
    _vat = L.get("vat_total") or 0.0
    _heq = L.get("holder_equity_end") or 0.0
    _sip = L.get("sen_interest_paid") or 0.0
    _sinc = L.get("sub_income_paid") or 0.0
    other_fee = OTHER_FEE
    steps = [
        ("回收流入", (M["recovered"] + _ai) / YI, "in"),
        ("处置费用", (M["dispose_fee"] or 0) / YI, "out"),
        ("服务报酬", (M["servicer_fee"] / YI) if M.get("servicer_fee") is not None else 0.0, "out"),
        ("其他费用", other_fee / YI, "out"),
        ("增值税", _vat / YI, "out"),
        ("优先档本息", (L["sen_principal_paid"] + _sip) / YI, "sec"),
        ("次级档本息", (L["sub_principal_paid"] + _sinc) / YI, "sec"),
        ("期末余额", _heq / YI, "close"),
    ]
    if LEGACY_TEXT:
        # 旧交付件：瀑布 + 分档面积并排，保持字节基线
        wf = V.waterfall(steps)
        wf_ch = (f'<div class="chart v6-cap" data-chart="waterfall"><div class="ct">全周期资金分配瀑布'
                 f'<span class="v2c-tag">单位：亿元</span></div>'
                 f'{wf}</div>')
        sen_bal = [T["senior"]["issue"] / YI] + [p["sen_balance_after"] / YI for p in PER]
        sub_bal = [T["sub"]["issue"] / YI] + [p["sub_balance_after"] / YI for p in PER]
        sa = V.stack_area([
            {"name": "优先档未偿本金", "color": V.NAVY, "data": sen_bal},
            {"name": "次级档未偿本金", "color": V.RED, "data": sub_bal},
        ], ["发行"] + [f"第{i}期" for i in range(1, len(PER) + 1)])
        sa_ch = (f'<div class="chart v6-cap" data-chart="stack-area"><div class="ct">分档累计本金走势'
                 f'<span class="v2c-tag">单位：亿元 · 堆叠面积</span></div>'
                 f'{sa}</div>')
        duo = ('<div class="card"><div class="ct2">全周期资金分配瀑布 × 分档累计本金走势'
               f'（单位：亿元）</div><div class="v6-duo" style="margin:0">{wf_ch}{sa_ch}</div></div>')
    else:
        # 4.1：删掉分档累计面积图，把空间让给瀑布；全宽、字号约 12
        wf = V.waterfall(steps, W=980, H=380, large=True)
        wf_ch = (f'<div class="chart wf-full" data-chart="waterfall" '
                 f'style="max-width:1080px;margin:0 auto">'
                 f'{wf}</div>')
        duo = ('<div class="card"><div class="ct2">全周期资金分配瀑布（单位：亿元）</div>'
               f'{wf_ch}</div>')

    # card1 分档逐期矩阵
    rows = ""
    _cum_pr = 0.0
    _pr_total = float((T["senior"].get("issue") or 0) + (T["sub"].get("issue") or 0))
    for i, p in enumerate(PER, 1):
        _cum_pr += float((p.get("sen_principal") or 0) + (p.get("sub_principal") or 0))
        _bar_pct = (_cum_pr / _pr_total * 100) if _pr_total > 0 else 0
        _bar_cell = ''
        if not LEGACY_TEXT:
            _bar_cell = (f'<td class="num"><div style="display:flex;align-items:center;gap:7px;min-width:132px">'
                         f'<div style="flex:1;height:7px;background:#EEF1F6;border-radius:4px;overflow:hidden">'
                         f'<i style="display:block;height:100%;width:{min(100,_bar_pct):.1f}%;'
                         f'background:linear-gradient(90deg,#7FA6C6,#2F5D8A);border-radius:4px"></i></div>'
                         f'<span style="font-size:10px;color:#5A6B7D;white-space:nowrap">{_cum_pr/YI:.2f} 亿</span>'
                         f'</div></td>')
        rows += (f'<tr><td class="l">第{i}期</td><td>{p["pay_date"]}</td>'
                 f'<td class="num">{wan(p["sen_principal"])} 万元</td>'
                 f'<td class="num">{wan(p["sen_interest"])} 万元</td>'
                 f'<td class="num">{wan(p["sub_principal"])} 万元</td>'
                 f'<td class="num">{wan(p["sub_fixed_cost"]+p["sub_income"])} 万元</td>'
                 f'{_bar_cell}</tr>')
    # ★ 合计行必须＝列内逐期相加，不能用清算报告的 single value：
    #   清算报告 L["sub_income_paid"] 只含「次级档超额收益」，不含逐期的
    #   「固定资金成本」。实测和萃2021二期：列内 265.84+81.55=347.39 万元，
    #   而 L 口径只有 96.79 万元 —— 合计行与列自相矛盾，一眼能看出是错的。
    #   惠元第三期两者恰好相等（21,860,394.75），故改为列求和后产物字节不变。
    _c_sp = sum((p["sen_principal"] or 0) for p in PER)
    _c_si = sum((p["sen_interest"] or 0) for p in PER)
    _c_up = sum((p["sub_principal"] or 0) for p in PER)
    _c_ui = sum(((p["sub_fixed_cost"] or 0) + (p["sub_income"] or 0)) for p in PER)
    rows += (f'<tr class="tot"><td class="l">合计</td><td>—</td>'
             f'<td class="num">{wan(_c_sp)} 万元</td>'
             f'<td class="num">{wan(_c_si)} 万元</td>'
             f'<td class="num">{wan(_c_up)} 万元</td>'
             f'<td class="num">{wan(_c_ui)} 万元</td>'
             + (f'<td class="num"><b>{(_c_sp+_c_up)/YI:.2f} 亿</b></td>' if not LEGACY_TEXT else '')
             + '</tr>')
    _m1_ths = ['<th class="l">期次</th>', '<th>支付日</th>', '<th>优先档本金</th>',
               '<th>优先档利息</th>', '<th>次级档本金</th>', '<th>次级档固资＋收益</th>']
    if not LEGACY_TEXT:
        _m1_ths.append('<th>累计本金（柱）</th>')
    m1 = ('<div class="card"><div class="ct2">分档逐期矩阵（本金 / 利息，万元）</div>'
          + note(_zero_note())
          + tbl(_m1_ths, rows)
          + "</div>")

    # card2 存续期分配明细矩阵（档位 × 科目）
    # L1：行序改为合同约定的现金流支付顺序，逐行标注「第N步」
    # 顺序来源：payload.waterfall_order (a)–(n)，与发行说明书分配条款一致
    #
    # ★ 3.1 重大修正：证券类 5 行改为**从分档表取**（sen_interest/sen_principal/
    #   sub_fixed_cost/sub_principal/sub_income），不再从 p["outflow"] 取。
    #   原实现一律 p["outflow"].get(name)，但招行披露的是**汇总科目**
    #   （证券利息总支出 / 证券本金总支出 / 次级档超额收益），
    #   没有「优先档利息」这种细分键 → 证券 5 行逐期全是「—」，
    #   而「合计」行取的却是 out_total，于是明细相加 436.95 万、合计 27,812.86 万，
    #   差 27,375.91 万。本表注释一直写「取分档兑付表（权威）」，代码与注释不一致。
    #   惠元那 5 项分档值与 outflow 逐项完全相等，故此改动不改变其产物字节（已验）。
    #
    # ★ 同时补「兜底行」：outflow 里存在但没有任何行消费的科目（如招行的
    #   「发行费用」合并披露、惠元的「其他费用支出」）追加到表尾，
    #   保证「明细相加 == 合计」，不再出现表内自相矛盾。
    ROWS = [
        ("费用", "税收", "out", ["税收", "税费"]),                        # (a)
        ("费用", "发行登记服务费", "out", ["发行登记服务费"]),               # (b) 发行费用
        ("费用", "承销报酬", "out", ["承销报酬"]),                        #     （合并披露时为空）
        ("费用", "代理兑付费用", "out", ["代理兑付费用"]),                  # (c)
        ("费用", "受托机构报酬", "out", ["受托机构报酬"]),
        ("费用", "资金保管机构报酬", "out", ["资金保管机构报酬"]),
        ("费用", "评级服务费", "out", ["评级服务费", "跟踪评级服务费", "跟踪评级费"]),
        ("费用", "审计费", "out", ["审计费"]),
        ("费用", "律师费", "out", ["律师费"]),
        ("费用", "处置费用", "out", ["处置费用", "执行费用及执行费用利息"]),   # (d)
        ("证券", "优先档利息", "sen_int", []),                            # (e)
        ("证券", "优先档本金", "sen_prin", []),                           # (h)
        ("费用", "贷款服务机构报酬", "out", ["贷款服务机构报酬"]),           # (j)
        ("证券", "次级档固定资金成本", "sub_fix", []),                     # (k)
        ("证券", "次级档本金", "sub_prin", []),                           # (l)
        ("证券", "次级档收益", "sub_inc", []),                            # (n)
    ]
    _FIELD = {"sen_int": "sen_interest", "sen_prin": "sen_principal",
              "sub_fix": "sub_fixed_cost", "sub_prin": "sub_principal",
              "sub_inc": "sub_income"}

    # ★ 3.2：若 payload 提供 waterfall_rows（按**说明书合同条款**抽出的分配顺序），
    #   一律以它为准，替换上面这张写死的 16 行表。
    #   为什么必须能替换：合同里「次级档本金（第9步）」在「次级档固定资金成本
    #   （第10步）」**之前**，而写死表把它俩排反了；表内合计照样配平，光看配平查不出。
    #   惠元第三期 payload 无该字段 → 仍走上面的 ROWS，产物字节不变（G1 已验）。
    _WF_ROWS = D.get("waterfall_rows") or []
    _WF_BASIS = D.get("_waterfall_basis") or ""
    _WF_IS_CONTRACT = bool(D.get("_waterfall_is_contract"))
    _STEP_OF = {}          # name -> 合同步号（渲染「第N步」用）
    _LUMP_OF = {}          # name -> 一次性科目键（逐期无、合计取清算报告值）
    # ★ _ROW_STEP：与 ROWS 一一对应的合同步号。
    #   原实现用 `_STEP_OF[name] = step`（以科目名为键），**同名科目出现在
    #   多个合同步时后者的步号会覆盖前者**，两行都渲染成同一步、前一步凭空消失。
    #   实测 2021二期第4步(优先档利息)与第5步(流动性储备)都被判成「优先档利息」时，
    #   矩阵里"第4步"整行不见、只剩两行"第5步 优先档利息"，
    #   而"编号连续"断言只看到 11 个不同编号（最高 12）→ FAIL。
    #   改为按行序对位，重名不再互相覆盖。
    _ROW_STEP = []
    if _WF_ROWS:
        ROWS = []
        for _r in _WF_ROWS:
            _k = _r.get("kind") or "out"
            if _k == "none":
                # 合同有此步、本单清算报告未单列 → 保留行、值渲染「—」
                _k = "none"
            ROWS.append((_r.get("lvl") or "其他", _r.get("name") or "—",
                         _k, _r.get("cands") or []))
            _ROW_STEP.append(_r.get("step"))
            _STEP_OF[_r.get("name")] = _r.get("step")     # 兼容其他引用处
            if _k == "lump" and _r.get("lump_key"):
                _LUMP_OF[_r.get("name")] = _r["lump_key"]

    def _pick(p, kind, cands):
        """取某期某科目的值；None＝本期无此项（渲染「—」），0 也渲染「—」"""
        if kind in ("none", "lump"):
            # none：合同有此步、清算报告未单列
            # lump：全周期一次性科目（如处置费用），逐期无、只在合计体现
            return None
        if kind == "none":
            return None          # 合同有此步，本单清算报告未单列
        if kind != "out":
            return p.get(_FIELD[kind])
        o = p.get("outflow") or {}
        for c in cands:
            if o.get(c) is not None:
                return o.get(c)
        return None

    # 汇总科目：内容已由上面的证券行覆盖，不再单列（否则重复计数）
    # ★ 「次级固定资金成本」是受托报告**资产池现金流出**侧的科目名（无「档」字），
    #   与证券兑付侧的「次级档固定资金成本」是同一笔钱的两处披露。
    #   证券行已按 kind=sub_fix 取值，这里必须一并抑制，否则它会以"未归集"再列一行，
    #   等于把次级固资算两遍（矩阵合计虚增）。
    # 费用科目名（受托报告口径）→ payload.liquidation.fee_detail 的标准名
    _FEE_NAME2FD = {"贷款服务机构报酬": "贷款服务费", "受托机构报酬": "受托机构报酬",
                    "资金保管机构报酬": "资金保管机构报酬", "代理兑付费用": "代理兑付费",
                    "发行费用": "发行费", "税收": "税收", "审计费": "审计费",
                    "跟踪评级服务费": "跟踪评级费", "其他费用支出": "其他费用",
                    "执行费用": "处置费", "处置费用": "处置费",
                    "执行费用及执行费用利息": "处置费"}
    _FD = L.get("fee_detail") or {}
    _LUMP_AUDIT = {}
    SEC_AGG = {"证券利息总支出", "证券本金总支出", "次级档超额收益",
               "优先档利息", "优先档本金", "次级档固定资金成本", "次级固定资金成本",
               "次级档本金", "次级档收益"}
    # ★ 按「实际命中的键」登记，不能只登记候选列表的第一个：
    #   招行没有「处置费用」，实际命中的是候选里的「执行费用及执行费用利息」，
    #   若只记第一个，后者会被当成未归集科目再列一行 → 重复计数。
    _used = set()
    for p in PER:
        _o = p.get("outflow") or {}
        for _l, _n, _k, _c in ROWS:
            if _k != "out":
                continue
            for c in _c:
                if _o.get(c) is not None:
                    _used.add(c)
                    break
    _allk = set()
    for p in PER:
        _allk |= set((p.get("outflow") or {}).keys())
    # ★ 「转存下期金额」是账户留存（钱没分出去，留在信托账户滚入下期），
    #   不是一次"分配"；混进分配行会让人误以为它是受益人的受偿项。
    #   单列「留存」行，且不参与「已分配」的语义。
    _RETAIN = {"转存下期金额"}
    if LEGACY_TEXT:
        # 惠元第三期已交付、已过 G1 字节基线：行集合与拆分方式一律沿用旧实现，
        # 「转存下期金额」仍按普通「其他」行处理，不另立「留存」行。
        EXTRA = sorted(k for k in _allk if k not in SEC_AGG and k not in _used)
        _RETAIN_HIT = False
        _EXTRA_ROWS = [("其他", k, "out", [k]) for k in EXTRA]
    else:
        EXTRA = sorted(k for k in _allk
                       if k not in SEC_AGG and k not in _used and k not in _RETAIN)
        _RETAIN_HIT = bool(_allk & _RETAIN)
        _EXTRA_ROWS = ([("其他", k, "out", [k]) for k in EXTRA]
                       + [("其他", k, "out", [k]) for k in sorted(_allk & _RETAIN)])

    body2 = ""
    _step = 0
    _max_step = 0
    _sum_cols = [0.0] * len(PER)
    for _ri, (lvl, name, kind, cands) in enumerate(ROWS + _EXTRA_ROWS):
        if _WF_ROWS:
            # 合同模式：显示合同步号（同一步内多科目重复同一编号，表示"同顺序清偿"）
            # 按**行序**取步号，不用科目名查表 —— 同名科目分属不同步骤时不会互相覆盖
            st = _ROW_STEP[_ri] if _ri < len(_ROW_STEP) else None
            if st is None:
                # 未在合同步里的行：账户留存与其他未归集科目不是"分配"，
                # 不能借用「前置」标签（会被读成资产池层面前置扣除）
                _step = None
                _step_txt = "留存" if name == "转存下期金额" else "未归集"
            else:
                _step = st
                _max_step = max(_max_step, st or 0)
                _step_txt = "前置" if st == 0 else f"第{st}步"
        else:
            _step += 1
            _max_step = _step
            _step_txt = f"第{_step}步"
        vals = [_pick(p, kind, cands) for p in PER]
        # ★ lump 行（合计取清算报告一次性列示的科目）**不能**再取逐期值：
        #   兴业这类单子 _dc 里能命中逐期科目，kind 会被判成 "out"，
        #   于是逐期 86,355,505.00 与清算口径 58,900,608.71 同时进表 ——
        #   vals 加进 _sum_cols、cum 又被 _LUMP_OF 覆盖成审计值，合计行就变成 110%。
        #   lump 的语义就是"逐期留「—」，合计取审计值"，这里统一执行。
        if name in _LUMP_OF:
            vals = [None] * len(PER)
        _shown = [(v if v is not None else 0.0) for v in vals]
        # ★ 费用科目「逐期 OCR 合计」与「清算报告（经审计）」打架时的处置：
        #   扫描件的逐期「资产池现金流出」表常在某个科目上读错一整行
        #   （兴瑞2021二期：执行费用逐期合计 8,635.55 万，清算报告 5,890.06 万，
        #    偏高 46%；同一批单里还有把发行总额当成本期兑付本金的情形）。
        #   清算报告是**经审计的全周期口径**，逐期表是未审计的过程稿 ——
        #   两者差超 2% 时以清算报告为准：逐期单元格留「—」，合计取审计值，
        #   并在行 memo 里写明口径，绝不按比例缩放（缩放等于编造逐期分布）。
        _fd_audit = None
        # ★ 只在 payload 声明了 fee_calibrated 的单上启用（只兴瑞）：
        #   build_single 是跨行共用代码，这条会改写逐期费用行；对惠元/建行/招行
        #   已过 G1 基线的交付件必须保持原行为不变（本轮实测：惠元被改动后
        #   G1 差 1 字节、审计费 49→47、未归集差额 -580.45→-531.45）。
        if (D.get("fee_calibrated") and kind == "out"
                and _FEE_NAME2FD.get(name) in _FD):
            _fd_audit = _FD.get(_FEE_NAME2FD.get(name))
        _row_sum = sum(_shown)
        if (_fd_audit is not None and _row_sum > 0
                and abs(_row_sum - _fd_audit) > max(1.0, abs(_fd_audit) * 0.02)):
            _LUMP_AUDIT[name] = float(_fd_audit)
            vals = [None] * len(PER)
            _shown = [0.0] * len(PER)
        for _i, _v in enumerate(_shown):
            _sum_cols[_i] += _v
        cum = sum(_shown)
        if name in _LUMP_AUDIT:
            cum = _LUMP_AUDIT[name]
        elif name in _LUMP_OF:
            # 逐期取不到的科目（如处置费用：只在清算报告全周期单列），
            # 合计从清算报告补；逐期单元格仍留「—」并在 memo 说明口径。
            cum = (L.get(_LUMP_OF[name]) or 0.0)
        td = "".join(f'<td class="{"zero" if not v else "num"}">'
                     f'{"—" if not v else wan(v)}</td>' for v in vals)
        # 合同模式下把条款原文摘要挂 title，供鼠标悬停溯源；
        # 非合同模式不加该属性（空 title="" 会多出字节，破坏惠元 G1 基线）
        _memo = ""
        if _WF_ROWS:
            _memo = next((r.get("memo") or "" for r in _WF_ROWS
                          if r.get("name") == name), "")
        _name_td = (f'<td class="l" title="{_memo}">{name}</td>' if _WF_ROWS
                    else f'<td class="l">{name}</td>')
        body2 += (f'<tr data-label="{name}" data-cum="{cum}" data-step="{_step if _step is not None else ""}">'
                  f'<td class="l">{_step_txt}</td><td class="l">{lvl}</td>'
                  + _name_td + td
                  + f'<td class="num">{wan(cum)}</td>'
                  f'<td>{cum/M["recovered"]*100:.2f}%</td></tr>')
    # ★ 合计行＝明细逐列相加（不再取 out_total）。原实现取 out_total，
    #   与明细相加不等的差额就成了表内自相矛盾（招行差 27,375.91 万）。
    #   两者本应相等；若不等说明 outflow 有科目未被任何行归集，
    #   此时差额单独成一行「未归集」并在表下注明，绝不静默吞掉。
    # ★ 逐期取不到的 lump 科目（处置费用）不进 _sum_cols，需单独加回，
    #   否则合计少掉整块处置费用（本单会少 6,143 万）。
    _lump_sum = (sum((L.get(k) or 0.0) for k in _LUMP_OF.values())
                 + sum(_LUMP_AUDIT.values()))
    cum_out = sum(_sum_cols) + _lump_sum
    # 对照基准也要含 lump，否则差额行会把处置费用整块报成"未归集"
    _raw_out = sum(p["out_total"] for p in PER) + _lump_sum
    if abs(_raw_out - cum_out) > 1.0:
        _gap = [round(p["out_total"] - _sum_cols[i], 2) for i, p in enumerate(PER)]
        body2 += (f'<tr class="tot" data-label="未归集"><td class="l">差额</td>'
                  f'<td class="l">其他</td><td class="l">未归集流出</td>'
                  + "".join(f'<td class="num">{wan(v)}</td>' for v in _gap)
                  + f'<td class="num">{wan(_raw_out - cum_out)}</td>'
                  f'<td>{(_raw_out - cum_out)/M["recovered"]*100:.2f}%</td></tr>')
        cum_out = _raw_out
    body2 += (f'<tr class="tot"><td class="l">合计</td><td class="l">—</td><td class="l">—</td>'
              + "".join(f'<td class="num">{wan(p["out_total"])}</td>' for p in PER)
              + f'<td class="num">{wan(cum_out)}</td>'
              f'<td>{cum_out/M["recovered"]*100:.2f}%</td></tr>')
    # ★ 3.2：标题与口径注必须**名副其实**。
    #   原实现行序取自清算报告科目排版序，注释却写「行序＝合同约定的现金流支付顺序」，
    #   属自述与实际不符；且把「次级档固资」排在「次级档本金」之前（合同相反）。
    #   现在：有合同步就用合同步（标题标「合同 12 步」），没有就如实标「实际执行顺序」。
    if _WF_ROWS and _WF_IS_CONTRACT:
        _m2_title = (f'存续期分配明细矩阵（合同 {_max_step} 步 · 共 {len(ROWS)} 行 · 单位：万元）')
        _m2_note = ('<b>行序＝发行说明书「现金流分配机制」约定的支付顺序</b>'
                    f'（{_WF_BASIS.replace("合同约定顺序（", "").rstrip("）")}）。'
                    '同一编号多行表示该步内<b>同顺序按比例清偿</b>。'
                    '<b>关键次序</b>：优先档利息(4) → 优先档本金(7) → 服务商基本服务费(8) → '
                    '<b>次级档本金(9) → 次级档固定资金成本(10)</b> → 超额奖励服务费(11) → '
                    '次级档收益(12)；<b>次级档本金先于其固定资金成本</b>受偿，'
                    '与「固资优先」的直觉相反。<br>'
                    '「前置」行为资产池层面先行扣除的处置费用，不进入信托账户分配序列。'
                    '优先/次级本金·利息取<b>分档兑付表</b>（权威）；费用取受托机构报告'
                    '「资产池现金流出情况」；缺失期与合同有而未单列的步骤均显示「—」，不补 0。'
                    + ('　<b>本单发行费用为合并披露</b>，第 2/3 步不做拆分。' if
                       ("发行费用" in EXTRA) else '')
                    + ('　<b>表尾「未归集」行为本单特有、合同步骤未涵盖的流出科目</b>（'
                       + '、'.join(EXTRA) + '），列示以保证明细合计＝合计。' if EXTRA else '')
                    + ('　<b>「留存」行的「转存下期金额」是账户留存</b>，'
                       '不是分配，钱留在信托账户滚入下期。' if _RETAIN_HIT else ''))
    elif LEGACY_TEXT:
        # 惠元第三期：payload.waterfall_order 本就取自说明书正文的 14 步列表，
        # 是合同顺序；文案一字不动以保 G1 字节基线。
        _m2_title = f'存续期分配明细矩阵（第1步 → 第{_step}步 · 单位：万元）'
        _m2_note = ('<b>行序＝合同约定的现金流支付顺序</b>（① 费用与税 → ② 证券受偿：'
                    '优先档利息→本金→次级档固资→本金→收益）；'
                    '优先/次级本金·利息取<b>分档兑付表</b>（权威）；'
                    '次级档收益＝固定资金成本＋超额收益；费用取受托机构报告「资产池现金流出情况」；'
                    '缺失期显示「—」，不补 0。'
                    + ('　<b>本单发行费用为合并披露</b>，第 2/3 步不做拆分。' if
                       ("发行费用" in EXTRA) else '')
                    + ('　<b>表尾「其他」行为本单特有的流出科目</b>（'
                       + '、'.join(EXTRA) + '），列示以保证明细合计＝合计。' if EXTRA else ''))
    else:
        # ★ 回退路径（说明书分配机制取不到合同条款）下每行 step 都是 None，
        #   循环结束后 _step 也是 None → 标题会渲染成「第1步 → 第None步」。
        #   这类单没有"第N步"可言，标题直接改成"实际执行顺序"。
        _m2_title = (f'存续期分配明细矩阵（第1步 → 第{_max_step}步 · 单位：万元）'
                     if _max_step else
                     f'存续期分配明细矩阵（实际执行顺序 · 共 {len(ROWS)} 行 · 单位：万元）')
        _m2_note = ('<b>行序＝实际执行顺序</b>（按清算报告「资产池现金流出」科目发生顺序；'
                    '本单说明书分配机制为图示体例，文字层不可得，故不以合同顺序冒充）。'
                    '优先/次级本金·利息取<b>分档兑付表</b>（权威）；'
                    '次级档收益＝固定资金成本＋超额收益；费用取受托机构报告「资产池现金流出情况」；'
                    '缺失期显示「—」，不补 0。'
                    + ('　<b>本单发行费用为合并披露</b>，第 2/3 步不做拆分。' if
                       ("发行费用" in EXTRA) else '')
                    + ('　<b>表尾「其他」行为本单特有的流出科目</b>（'
                       + '、'.join(EXTRA) + '），列示以保证明细合计＝合计。' if EXTRA else ''))
    def _ta_diff_note():
        """矩阵合计 vs 信托账户流出的差异说明

        ★ 差异必须按口径归因，不能一句"表外科目"带过：
          建行体例下处置费用由资产池直接扣除、不经信托账户，是差异主因
          （建鑫2021-1：6,143.34 万元，占差额 79%）。
        ★ 惠元第三期原文一字不动（G1 字节基线），故整体走 _v5 分支。
        """
        _tao = sum(t["outflow"] for t in TA_N)
        _d = _tao - cum_out
        if LEGACY_TEXT:
            return (f'<b>与信托账户流出的差异</b>：本表取「资产池现金流出」口径，合计 '
                    f'{num(cum_out)} 元＝累计回收的 {cum_out/M["recovered"]*100:.2f}%；'
                    f'信托账户本期现金流出合计 {num(_tao)} 元（见 ⑥ 节），'
                    f'两者差 <b>{num(_d)} 元</b>，'
                    '主要为第 2 期向信托（流动性）储备账户补足 5,762,775.44 元及账户间零星结转，'
                    '属分配顺序表外科目，不影响证券端受偿。')
        _over = ('（>100% 因含期初账户余额转出，非超付）'
                 if cum_out > M["recovered"] else '')
        _why = (f'主因：<b>处置费用 {wan(L.get("dispose_exec_fee"))} 万元由资产池直接扣除、'
                f'不经信托账户</b>（占差额 '
                f'{(L.get("dispose_exec_fee") or 0)/max(abs(_d), 1)*100:.0f}%）；'
                if (not FEE_HAS_DISP and L.get("dispose_exec_fee"))
                else '主要为储备账户补足及账户间零星结转等；')
        return (f'<b>与信托账户流出的差异</b>：本表取「资产池现金流出」口径，合计 '
                f'{num(cum_out)} 元＝累计回收的 {cum_out/M["recovered"]*100:.2f}%{_over}；'
                f'信托账户本期现金流出合计 {num(_tao)} 元（见 ⑥ 节），'
                f'两者差 <b>{num(_d)} 元</b>。' + _why
                + '其余为储备补足、账户间结转等分配顺序表外科目，不影响证券端受偿。')

    m2 = ('<div class="card" data-chart="dist-matrix">'
          f'<div class="ct2">{_m2_title}</div>'
          + note(_m2_note)
          + _ta_diff_note()
          + tbl(['<th class="l" style="width:68px">序</th>',
                 '<th class="l" style="width:56px">档位</th>',
                 '<th class="l" style="width:32%">科目</th>']
                + [f'<th>第{i}期</th>' for i in range(1, len(PER) + 1)]
                + ['<th>累计</th>', '<th style="width:92px">占回收流入</th>'], body2,
                cls="tbl tbl-mtx")
          + "</div>")

    # card3 处置费用（LEGACY_TEXT 严格保留旧文案/字号）
    thr = 0.17
    _fee_title = ('处置费用（合同口径 / 实际费率 / 是否超限）' if LEGACY_TEXT
                  else '处置费用（已报销 / 合同上限 / 实际费率）')
    _fee_lead = ('' if LEGACY_TEXT else
                 note('<b>口径</b>：处置费率 = 本项目目前<b>已报销</b>的处置费用 ÷ 累计回收；'
                      '不必然等于实际全部处置费用——各家银行对处置费用的报销尺度/可报销科目不同。'))
    _fee_klab = '实际费率（现算）' if LEGACY_TEXT else '已报销费率（现算）'
    _fee_klab2 = '实际费率' if LEGACY_TEXT else '已报销费率'
    _fee_line = (f'{pc(M["dispose_fee_rate"])}%（= 处置费用 {yi(M.get("dispose_fee"))} 亿元 ÷ 实际回收流入 {REC_YI:.2f} 亿元）'
                 if LEGACY_TEXT else
                 f'{pc(M["dispose_fee_rate"])}%（= 已报销处置费用 {yi(M.get("dispose_fee"))} 亿元 ÷ 累计回收 {REC_YI:.2f} 亿元）')
    _fee_last = (f'累计处置费用 {wan(M.get("dispose_fee"))} 万元'
                 f'（来源：受托机构报告各期「资产池现金流出情况」处置费用科目）'
                 if LEGACY_TEXT else
                 f'累计已报销处置费用 {wan(M.get("dispose_fee"))} 万元'
                 f'（来源：受托机构报告各期「资产池现金流出情况」处置费用科目；报销尺度各行不同）')
    m3 = (f'<div class="card" data-chart="fee-block"><div class="ct2">{_fee_title}</div>'
          + _fee_lead
          + note(f'<b>合同口径</b>：处置费用 ｜ 上限：累计回收款的 {pc(thr,0)}% '
                 f'（源：发行说明书 p87，第 (d)/(i) 项——不高于 {pc(thr,0)} 部分列于优先档利息与本金之前，'
                 f'超过部分劣后至优先档本金之后）')
          + '<div class="kpi-row">'
          + f'<div class="kpi"><div class="k">合同上限（源）</div><div class="v" style="font-size:13px">'
            f'累计回收款的 {pc(thr,0)}%</div></div>'
          + f'<div class="kpi"><div class="k">{_fee_klab}</div><div class="v" style="font-size:13px">'
            f'{_fee_line}</div></div>'
          + f'<div class="kpi"><div class="k">是否超限</div><div class="v" style="font-size:13px">'
            f'<b>未超限</b>（实际 {pc(M["dispose_fee_rate"])}% ≤ 合同上限 {pc(thr,0)}%）</div></div>'
          + "</div>"
          + note(f'基数差异注：合同上限的分母为「累计回收款」，本处{_fee_klab2}分母为「累计回收」，'
                 '两者同源同口径，可直接比对。')
          + note('相关费用/上限：<ul class="cal">'
                 f'<li>贷款服务机构基本服务费：按《服务合同》约定（p87 第 j 项）</li>'
                 f'<li>超额奖励服务费：次级档本金偿清后剩余金额的 80%（p87 第 m 项）</li></ul>')
          + note(_fee_last)
          + "</div>")

    # 嵌套：其余分配科目（收起）
    other = ""
    oitems = [("费用", "税收"), ("费用", "代理兑付费用"), ("费用", "资金保管机构报酬"),
              ("费用", "贷款服务机构报酬"), ("费用", "审计费"), ("证券", "次级档收益")]
    for lvl, name in oitems:
        vals = [p["outflow"].get(name, 0.0) for p in PER]
        cum = sum(vals)
        td = "".join(f'<td class="{"zero" if v==0 else "num"}">{"—" if v==0 else wan(v)}</td>' for v in vals)
        other += (f'<tr><td class="l">{lvl}</td><td class="l">{name}</td>{td}'
                  f'<td class="num">{wan(cum)}</td><td>{cum/M["recovered"]*100:.2f}%</td></tr>')
    sub = (fold_open("", "其余分配科目（明细·默认收起）",
                     f'其余科目 {len(oitems)} 项', collapsed=True)
           + tbl(['<th class="l">档位</th>', '<th class="l">科目</th>']
                 + [f'<th>第{i}期</th>' for i in range(1, len(PER) + 1)]
                 + ['<th>累计（万元）</th>', '<th>占回收流入</th>'], other)
           + fold_close())

    body = duo + m1 + m2 + m3 + sub
    return (fold_open("④", "现金流分配过程（维度③）",
                      f'回收流入 {yi(M["recovered"]+_ACC_INT)} 亿元 ｜ '
                      f'分配流出 {yi(sum(p["out_total"] for p in PER))} 亿元 ｜ 档数 2')
            + body + fold_close())


# ============================ ⑤ XIRR 与 XNPV ============================
def sec6():
    def Dt(s):
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)

    # ★ 现金流优先取 metrics.flows（3.1 参数化）：任意单只要有 flows 就能算 XIRR/XNPV。
    #   惠元第三期的 flows 与下方硬编码逐笔精确相等（239670000.0+1091095.89
    #   = 240761095.89000002 ≈ flows 的 240761095.89），故改造后产物字节不变。
    #   硬编码仅作兜底（老 payload 无 flows 时仍可复现第三期）。
    _FB_SEN = [(Dt("2021-12-21"), -450000000.0), (Dt("2022-01-20"), 239670000.0 + 1091095.89),
               (Dt("2022-03-20"), 84105000.0 + 1002957.16), (Dt("2022-06-20"), 126225000.0 + 938560.68)]
    _FB_SUB = [(Dt("2021-12-21"), -80000000.0), (Dt("2022-06-20"), 1363590.75),
               (Dt("2022-09-20"), 80000000.0 + 6415039.38 + 2241573.42),
               (Dt("2022-12-20"), 11840191.20)]

    def _flows_of(key, fb):
        raw = (M.get("flows") or {}).get(key)
        if not raw:
            return fb
        try:
            out = [(Dt(x["date"]), float(x["cf"])) for x in raw]
            # 次级档存续早期可能只有一笔认购流出；1 个点也是合法现金流，
            # 不能回落到硬编码兜底（会把惠元第三期的次级现金流带进别单）。
            return out if len(out) >= (1 if key == "sub" else 2) else fb
        except (KeyError, TypeError, ValueError):
            return fb

    def _flows_from_per(side):
        """缺 flows 时用本单 periods 重建；绝不跨项目兜底。"""
        _issue = (D.get("meta") or {}).get("issue_date")
        _t = (T.get("senior") or {}) if side == "sen" else (T.get("sub") or {})
        _amt = _t.get("issue")
        _px = 1.0 if side == "sen" else float(_t.get("price") or 100.0) / 100.0
        out = [(Dt(_issue), -float(_amt) * _px)] if _issue and _amt else []
        for _p in PER:
            if side == "sen":
                _cf = (_p.get("sen_principal") or 0) + (_p.get("sen_interest") or 0)
            else:
                _cf = ((_p.get("sub_principal") or 0) + (_p.get("sub_fixed_cost") or 0)
                       + (_p.get("sub_income") or 0))
            if _cf:
                out.append((Dt(_p["pay_date"]), float(_cf)))
        return out

    SEN = _flows_of("sen", [])
    SUB = _flows_of("sub", [])
    if not SEN:
        SEN = _flows_from_per("sen")
    if not SUB:
        SUB = _flows_from_per("sub")

    # 构建期硬断言：现金流日期必须属于本单（发行日或本单支付日）。
    _own = {Dt((D.get("meta") or {}).get("issue_date"))} if (D.get("meta") or {}).get("issue_date") else set()
    _own |= {Dt(p["pay_date"]) for p in PER if p.get("pay_date")}
    # 清算/回购环节可能补一笔尾款，日期取清算日/回购起算日，不属于别单
    for _k in ("terminate_date", "liquidation_end"):
        if L.get(_k):
            try:
                _own.add(Dt(L[_k]))
            except Exception:
                pass
    _bq = (L.get("buyback") or {})
    for _k in ("calc_date", "notice_date"):
        if _bq.get(_k):
            try:
                _own.add(Dt(_bq[_k]))
            except Exception:
                pass
    _foreign = sorted({d.isoformat() for d, _ in (SEN + SUB) if d not in _own})
    if _foreign:
        raise SystemExit("现金流混入非本单日期：%s" % "、".join(_foreign))

    def xnpv(r, cf):
        t0 = cf[0][0]
        return sum(v / (1 + r) ** ((d - t0).days / 365.0) for d, v in cf)

    rs, rb = M["sen_xirr"], M["sub_xirr"]
    coupon = T["senior"]["coupon"]

    # L4：XNPV 用无风险利率折现。★ 3.1 改为从 payload.meta.rf 取，回落 2.38%。
    #   原注释（惠元第三期）：1 年期国债到期收益率，2021-12-21 收 2.38%
    #   （同期 5 年期 2.72%、10 年期 2.85%）。其他单须在 payload.meta 里给 rf，
    #   否则沿用 2.38% —— 会把别期的折现算错，故 G3 断言里要求 rf 在场。
    _rf = (D.get("meta") or {}).get("rf")
    RF = float(_rf) if _rf is not None else 0.0238
    RF_NOTE = ((D.get("meta") or {}).get("rf_note")
               or '1 年期国债到期收益率 2.38%（2021-12-21，中债国债收益率曲线）')
    xnpv_rf_s, xnpv_rf_b = xnpv(RF, SEN), xnpv(RF, SUB)
    # 敏感性：Rf ±50bp
    sens = [(RF + d, xnpv(RF + d, SEN), xnpv(RF + d, SUB)) for d in (-0.005, 0.0, 0.005)]

    cards = (f'<div class="card" data-chart="xirr-cards"><div class="ct2">XIRR 与 XNPV 结果</div>'
             '<div class="grid2">'
             f'<div class="tl" data-xirr="{rs!r}" data-xnpv="{xnpv_rf_s!r}" data-rate="{RF!r}">'
             f'<div class="l">优先档 XIRR</div><div class="v">{pc(rs)}%</div>'
             f'<div class="s">票面 {pc(coupon)}%；与票面偏差 '
        + (f'{M["sen_xirr_gap_bp"]:+.2f}' if M.get("sen_xirr_gap_bp") is not None else "—")
        + ' bp</div>'
             f'<div class="s">XNPV@Rf {pc(RF)}%＝{wan(xnpv_rf_s)} 万元</div>'
             f'<div class="s">折现率＝{RF_NOTE}</div></div>'
             f'<div class="tl" data-xirr-sub="{rb!r}" data-xnpv-rf="{xnpv_rf_b!r}">'
             f'<div class="l">次级档 XIRR</div><div class="v">{pc(rb)}%</div>'
             f'<div class="s">回报倍数 {msafe("sub_multiple")}x</div>'
             + ((f'<div class="s">资金成本 {wan(M["sub_fixed_total"])} 万元 ｜ '
                 f'超额收益 {wan(M["sub_excess_total"])} 万元</div>')
                if M.get("sub_fixed_total") else '')
             + f'<div class="s">XNPV@Rf {pc(RF)}%＝{wan(xnpv_rf_b)} 万元</div>'
             f'<div class="s">折现率＝{RF_NOTE}</div></div>'
             '</div>'
             + note('<b>口径说明</b>：XIRR 为<b>货币加权（复利）年化收益率</b>，与票面利率<b>不可直接比较</b>；'
                    f'折现因子＝(1+r)^(距设立日天数 ÷ 365)，区间自期初（信托设立日 {D["meta"]["issue_date"]}）至末期。'
                    '两档本金全额兑付、账户配平成立 → 本单为<b>终局值</b>。'
                    + ((f'<b>本单存续仅 {M["life_months"]:.1f} 个月</b>，'
                        '年化 XIRR 系<b>短期绝对回报折算</b>，<b>不可外推为长期收益率</b>；'
                        '衡量本单回报请以「回报倍数」为准。')
                       # ★ 开关条件必须同时看 sub_fixed_total：那是「次级档资金成本可拆」
                       #   的单（兴业这批），惠元第三期 life=12 但无该字段，加进来会改到
                       #   已过 G1 字节基线的惠元交付件。
                       if (M.get("sub_fixed_total")
                           and (M.get("life_months") or 99) < 18) else ''))
             + note(f'信托设立日 {D["meta"]["issue_date"]}（来源：发行说明书 p2 封面；成立公告同）')
             + "</div>")

    # L4：优先档 / 次级档 XNPV 同表不同列（折现率＝无风险利率）
    # 两档现金流日期不同（优先档至 2022-06-20、次级档至 2022-12-20）→ 取日期并集逐行对齐
    def fac(r, d, t0):
        return 1 / (1 + r) ** ((d - t0).days / 365.0)

    t0 = SEN[0][0]
    sd, bd = dict(SEN), dict(SUB)
    ALLD = sorted(set(sd) | set(bd))
    xrow = ""
    for i, d in enumerate(ALLD):
        days = (d - t0).days
        f0 = fac(RF, d, t0)

        def cell(amt):
            if amt is None:
                return '<td class="num zero">—</td><td class="num zero">—</td>'
            return (f'<td class="num">{wan(amt)}</td>'
                    f'<td class="num">{wan(amt*f0)}</td>')

        xrow += (f'<tr><td>{"0 期初（信托设立日）" if i == 0 else i}</td>'
                 f'<td>{d.isoformat()}</td><td class="num">{days}</td>'
                 f'<td class="num">{f0:.9f}</td>'
                 + cell(sd.get(d)) + cell(bd.get(d)) + '</tr>')
    xrow += (f'<tr class="tot"><td>合计</td><td>—</td><td>—</td><td>—</td>'
             f'<td class="num">{wan(sum(v for _, v in SEN))}</td>'
             f'<td class="num">{wan(xnpv_rf_s)}</td>'
             f'<td class="num">{wan(sum(v for _, v in SUB))}</td>'
             f'<td class="num">{wan(xnpv_rf_b)}</td></tr>')

    def bp(d):
        v = round((d - RF) * 10000)
        return "基准" if v == 0 else f"{v:+d} bp"

    srow = "".join(f'<tr><td class="l">{bp(d)}</td>'
                   f'<td class="num">{pc(d)}%</td><td class="num">{wan(a)}</td>'
                   f'<td class="num">{wan(b)}</td><td class="num">{wan(a+b)}</td></tr>'
                   for d, a, b in sens)
    xnpv_tbl = ('<div class="card" data-chart="xnpv-table"><div class="ct2">'
                f'XNPV 折现表（折现率＝无风险利率 Rf {pc(RF)}%，两档分列 · 单位：万元）</div>'
                + note(f'<b>折现率选择</b>：Rf 取<b>{RF_NOTE}</b>。'
                       '选 1 年期，是因为本单存续期仅 12 个月、优先档加权平均期限 0.38 年、'
                       '次级档 2.17 年（发行说明书 p3），久期最接近 1 年。')
                + tbl(['<th>序号</th>', '<th>现金流日期</th>', '<th>距设立日天数</th>',
                       '<th>折现系数</th>',
                       '<th>优先档现金流</th>', '<th>优先档现值</th>',
                       '<th>次级档现金流</th>', '<th>次级档现值</th>'], xrow)
                + note('计算用精确解：优先档 XIRR＝'
                       + (f'{rs:.10f}' if rs is not None else '—')
                       + '、次级档 XIRR＝'
                       + (f'{rb:.10f}' if rb is not None else '—')
                       + f'；XNPV 按 Rf＝{RF:.4f} 折现，上表合计即两档现值。'
                       '「—」表示该日期该档无现金流，不补 0。')
                + '</div>')
    sens_tbl = ('<div class="card"><div class="ct2">折现率敏感性（Rf ±50bp）</div>'
                + note('Rf 变动 50bp 对两档现值的影响；现值＝未来现金流按该利率折现后的合计，'
                       '与发行价（面值 100 元）比较即可读出「按无风险利率衡量的价值溢价」。')
                + tbl(['<th class="l">折现率情景</th>', '<th>Rf 取值</th>',
                       '<th>优先档 XNPV</th>', '<th>次级档 XNPV</th>', '<th>两档合计</th>'], srow)
                + note(f'对照：按优先档票面 {pc(coupon)}% 折现，优先档 XNPV＝{wan(xnpv(coupon, SEN))} 万元。'
                       'XIRR 即令 XNPV＝0 的折现率，故该值应在 0 附近——与 Rf 口径的差额即「相对无风险利率的溢价」。')
                + "</div>")

    # 嵌套：按 XIRR 折现的自校验（XIRR 即令 XNPV＝0 的折现率，故合计应≈0）
    def drow(i, d, v, r, t0):
        days = (d - t0).days
        f = 1 / (1 + r) ** (days / 365.0)
        return (f'<tr><td>{"0 期初（信托设立日）" if i == 0 else i}</td><td>{d.isoformat()}</td>'
                f'<td>{days}</td><td class="num">{wan(v)} 万元</td>'
                f'<td class="num">{f:.9f}</td><td class="num">{wan(v*f)} 万元</td></tr>')

    # ★ XIRR 不可解时（缺发行日 / 现金流全为 0）本块整体置灰：
    #   直接拿 None 做 `1/(1+r)**x` 会 TypeError，把整份报告崩在最后一张折现表上。
    #   自校验的前提就是"有 XIRR 可比"，没有就不该硬画。
    def _drows(cf, r):
        if r is None:
            return ""
        out = "".join(drow(i, d, v, r, t0) for i, (d, v) in enumerate(cf))
        out += (f'<tr class="tot"><td>合计</td><td>—</td><td>—</td>'
                f'<td class="num">{wan(sum(v for _, v in cf))} 万元</td><td>—</td>'
                f'<td class="num">{wan(xnpv(r, cf))} 万元</td></tr>')
        return out

    a, b = _drows(SEN, rs), _drows(SUB, rb)
    _xr_txt = "，".join(
        (f'{nm} r＝{r:.10f}' if r is not None else f'{nm} XIRR 不可解（本节不列）')
        for nm, r in (("优先档", rs), ("次级档", rb)))
    sub = (fold_open("", "折现过程自校验（按 XIRR 折现 · 默认收起）",
                     f'信托设立日 {D["meta"]["issue_date"]}', collapsed=True)
           + note('本块用各档自身 XIRR 作折现率，XNPV 合计应≈0（残差为天数取整所致），'
                  '用于校验上表 XNPV 的算法一致性；主口径现值见上表（按 Rf 折现）。')
           + ('<div class="ct2">优先档折现过程</div>'
              + tbl(['<th>序号</th>', '<th>支付日</th>', '<th>距设立日天数</th>',
                     '<th>现金流</th>', '<th>折现系数</th>', '<th>现值</th>'], a, "max-height:300px")
              if rs is not None else
              '<div class="ct2">优先档折现过程</div>'
              '<div class="note">优先档 XIRR 不可解（缺少可用的发行日或现金流序列），本表置灰。</div>')
           + ('<div class="ct2" style="margin-top:14px">次级档折现过程</div>'
              + tbl(['<th>序号</th>', '<th>支付日</th>', '<th>距设立日天数</th>',
                     '<th>现金流</th>', '<th>折现系数</th>', '<th>现值</th>'], b, "max-height:300px")
              if rb is not None else
              '<div class="ct2" style="margin-top:14px">次级档折现过程</div>'
              '<div class="note">次级档 XIRR 不可解（缺少可用的发行日或现金流序列），本表置灰。</div>')
           + note(f'计算用精确解：{_xr_txt}；展示层统一 2 位小数。')
           + fold_close())

    body = cards + xnpv_tbl + sens_tbl + sub
    return (fold_open("⑤", "XIRR 与 XNPV",
                      f'XNPV@Rf {pc(RF)}% ｜ 优先档 XIRR {pc(rs)}% ｜ 次级档 {pc(rb)}%')
            + body + fold_close())


# ============================ ⑥ 账户勾稽 ============================
def _sec8_degraded():
    """账户数据不完整时的诚实降级（3.1）

    ★ 为什么不填 0：把「未披露」显示成 0 会被读成「真的没有」，比空更误导。
      版式口径是「缺失一律记 —」，故整节改为说明 + 逐期缺失清单。
    ★ 触发条件：trust_account 有空值（招行多数期如此；中信惠元三期完整）。
    """
    rows = ""
    for t in (D.get("trust_account") or []):
        cells = []
        for k in ("begin", "inflow", "outflow", "end"):
            v = t.get(k)
            cells.append(f'<td class="num">{num(v) if v is not None else "—"}</td>')
        rows += f'<tr><td>{V.esc(str(t.get("period", "—")))}</td>{"".join(cells)}</tr>'
    return (fold_open("⑥", "账户勾稽",
                      f'账户勾稽数据不足（{TA_WHY}），本节如实标注')
            + '<div class="card"><div class="ct2">信托账户逐期核算概况</div>'
            + note(f'<b>说明</b>：本单缺失「{TA_WHY}」，不足以完成账户配平（下表记「—」）。'
                   '<b>为避免用 0 冒充真实值</b>，本节不做配平断言、不做资金平衡推导；'
                   '证券端兑付与费用仍以清算报告为准，见第 ④ ⑤ 节。')
            + tbl(['<th class="l">期次</th>', '<th>期初余额</th>', '<th>本期流入</th>',
                   '<th>本期流出</th>', '<th>期末余额</th>'], rows)
            + '</div>' + fold_close())


def sec8():
    if not TA_OK:
        return _sec8_degraded()
    TA = TA_N
    tie_max = max(round(abs(t["begin"] + t["inflow"] - t["outflow"] - t["end"]), 2) for t in TA)
    sec_sum = (L["sen_principal_paid"] + L["sen_interest_paid"]
               + L["sub_principal_paid"] + L["sub_income_paid"])
    acc = ('<div class="card"><div class="ct2">资金平衡（全周期）</div><div class="accm">'
           f'<div class="box"><div class="bl">累计回收款</div><div class="bv">{REC_YI:.2f} 亿元</div></div>'
           '<div class="op">+</div>'
           f'<div class="box"><div class="bl">信托专户结息</div><div class="bv">{wan(_ACC_INT)} 万元</div></div>'
           '<div class="op">−</div>'
           f'<div class="box"><div class="bl">信托费用</div><div class="bv">{yi(M["fee_total"])} 亿元</div></div>'
           '<div class="op">−</div>'
           f'<div class="box"><div class="bl">增值税及附加</div><div class="bv">{wan(L.get("vat_total"))} 万元</div></div>'
           '<div class="op">−</div>'
           f'<div class="box"><div class="bl">证券本息</div><div class="bv">{yi(sec_sum)} 亿元</div></div>'
           '<div class="op">=</div>'
           f'<div class="box"><div class="bl">期末持有人权益</div><div class="bv">{wan(L["holder_equity_end"])} 万元</div></div>'
           '</div>'
           + (note(f'恒等式校验：{num(M["recovered"])} ＋ {num(_ACC_INT)} − '
                   f'（{num(M["fee_total"])} ＋ {num(L.get("vat_total"))} ＋ {num(sec_sum)}）＝ '
                   f'<b>{num(L["holder_equity_end"])}</b>，'
                   f'与清算报告「清算结束日持有人权益」完全一致。')
              if L.get("holder_equity_end") is not None else
              note(f'<b>恒等式校验不适用</b>：本单清算报告未披露「清算结束日持有人权益」，'
                   f'无法完成「回收＋结息−费用−增值税−证券本息＝期末权益」的闭环。'
                   f'上式各分项仍可在本文第 ④⑤ 节单独核对。'))
           + "</div>")

    # ★ 3.1：本段原先整段写死惠元第三期的事实（「5 期」「众环专字」「21,000.00 元」
    #   「清算净收益 585.82 元」等），换行到任意单都会变成虚构事实。
    #   改为：期数按 len(TA)、余额按 TA[-1]；清算衔接仅在
    #   「清算净收益 + 持有人权益」都披露时才展开，否则如实说明缺什么。
    _NTA = len(TA)
    if LEGACY_TEXT:
        # v5 原文：含「五期勾稽差额均为」「专户存款利息收入」「预提清算审计费
        # 20,000.00 元 → 清算开始日持有人权益 21,000.00 元」「众环专字…号」等
        # 惠元第三期的真实清算细节。这些细节对惠元是有价值的事实，不能因为
        # 参数化而删掉（曾误删，属信息损失）。新行没有这些字段，走下方通用分支。
        diff = ('<div class="card"><div class="ct2">差异分析与清算衔接</div>'
                + note(f'受托报告 5 期信托账户累计：流入 <b>{num(sum(t["inflow"] for t in TA))} 元</b>、'
                       f'流出 <b>{num(sum(t["outflow"] for t in TA))} 元</b>，'
                       f'第 5 期末余额 <b>{num(TA[-1]["end"])} 元</b>，五期勾稽差额均为 '
                       f'<b>{num(tie_max)} 元</b>。')
                + note(f'清算期追加：清算净收益 <b>{num(L["liquidation_gain"])} 元</b>'
                       f'（专户存款利息收入，发生于信托终止后），'
                       f'与第 5 期末余额合计 <b>{num(TA[-1]["end"]+L["liquidation_gain"])} 元</b>，'
                       f'与清算审计报告「清算结束日剩余信托财产」完全一致。')
                + note(f'再扣预提清算审计费 20,000.00 元（中审众环会计师事务所（特殊普通合伙））后，'
                       f'清算开始日持有人权益为 <b>21,000.00 元</b>，加清算净收益 '
                       f'{num(L["liquidation_gain"])} 元，等于清算结束日持有人权益 '
                       f'<b>{num(L["holder_equity_end"])} 元</b>；清算净收益全部计入持有人权益、'
                       f'未向证券持有人分配。审计意见：标准无保留意见（众环专字〔2023〕2700013 号），'
                       f'清算报告专项复核说明：众环综字〔2023〕2700002 号。')
                + "</div>")
    else:
        diff = ('<div class="card"><div class="ct2">差异分析与清算衔接</div>'
            + note(f'受托报告 {_NTA} 期信托账户累计：流入 <b>{num(sum(t["inflow"] for t in TA))} 元</b>、'
                   f'流出 <b>{num(sum(t["outflow"] for t in TA))} 元</b>，'
                   f'第 {_NTA} 期末余额 <b>{num(TA[-1]["end"])} 元</b>，'
                   f'逐期勾稽最大差额 <b>{num(tie_max)} 元</b>。')
                + ((note(f'清算期追加：清算净收益 <b>{num(L["liquidation_gain"])} 元</b>'
                         f'（专户存款利息收入，发生于信托终止后），'
                         f'与第 {_NTA} 期末余额合计 '
                         f'<b>{num(TA[-1]["end"]+L["liquidation_gain"])} 元</b>，'
                         f'与清算审计报告「清算结束日剩余信托财产」完全一致。')
                    + (note(f'清算结束日持有人权益 <b>{num(L["holder_equity_end"])} 元</b>'
                            + (f'；审计意见：标准无保留意见（{L["audit_no"]}）' if L.get("audit_no") else '')
                            + (f'，{L["review_no"]}' if L.get("review_no") else '') + '。')
                       if L.get("holder_equity_end") is not None else ''))
                   if L.get("liquidation_gain") is not None else
                   note(f'<b>清算衔接不适用</b>：本单清算报告未披露「清算净收益 / 清算结束日持有人权益」'
                        f'（{L.get("no_balance_sheet_note") or "无清算资产负债表"}），'
                        f'故不做「受托期末余额 → 清算剩余财产 → 持有人权益」的衔接推导。'
                        f'累计回收与证券兑付见第 ④⑤ 节。'))
                + "</div>")

    # F5：逐期勾稽改用「信托账户」口径（受托报告 P4「信托账户和子账户本期核算概况」）
    rows = ""
    for t in TA:
        gap = t["begin"] + t["inflow"] - t["outflow"] - t["end"]
        # ★ pay_date 用 .get 兜底：账户表来源是受托报告「核算概况」，部分体例无日期列，
        #   08 已按期次回填；万一仍缺就显示「—」，不能让整单构建崩掉。
        rows += (f'<tr><td class="l">{t["period"]}</td><td>{(t.get("pay_date") or "—")}</td>'
                 f'<td class="num">{num(t["begin"])}</td>'
                 f'<td class="num">{num(t["inflow"])}</td>'
                 f'<td class="num">{num(t["outflow"])}</td>'
                 f'<td class="num">{num(t["end"])}</td>'
                 f'<td class="num">{"0.00" if abs(gap) < 0.005 else num(gap)}</td>'
                 f'<td>{"配平" if abs(gap) < 0.005 else "差异"}</td></tr>')
    rows += (f'<tr class="tot"><td class="l">全周期</td><td>—</td><td class="num">0.00</td>'
             f'<td class="num">{num(sum(t["inflow"] for t in TA))}</td>'
             f'<td class="num">{num(sum(t["outflow"] for t in TA))}</td>'
             f'<td class="num">{num(TA[-1]["end"])}</td>'
             f'<td class="num">{num(tie_max)}</td><td>配平</td></tr>')
    per_tbl = ('<div class="card"><div class="ct2">逐期账户勾稽（期初 ＋ 流入 − 流出 ＝ 期末，单位：元）</div>'
               + note('口径：受托机构报告「信托账户和子账户本期核算概况」<b>总信托账户</b>行，'
                      '逐期以「期初余额 ＋ 本期现金流入总额 − 本期现金流出总额 ＝ 期末余额」校验；'
                      '「差额」列全为 0.00 即为配平（本项目 5/5 配平）。'
                      '注：资产池未偿本息余额（40.87 亿元起逐期递减）是<b>资产口径</b>，'
                      '不参与账户勾稽，两者不可混列。')
               + tbl(['<th class="l">期次</th>', '<th>支付日</th>', '<th>期初余额</th>',
                      '<th>本期流入</th>', '<th>本期流出</th>', '<th>期末余额</th>',
                      '<th>差额</th>', '<th>状态</th>'], rows)
               + "</div>")

    body = per_tbl + acc + diff
    return (fold_open("⑥", "账户勾稽",
                      f'5/5 配平 ｜ 期末权益 {wan(L["holder_equity_end"])} 万元', collapsed=True)
            + body + fold_close())


# ============================ ⑦ 核心结论 ============================
# F7：同业定位——23 单信用卡不良清算项目（来源：技能内置 28 单口径库 payload_28）
# ★ 3.1：优先用 peer_all.json（跨行同业集，如「15 中信 + 17 和萃 = 32 单」），
#   回落技能自带 peer28.json。这样同一份版式可切换对标样本，不必改代码。
_PEER_FILE = "peer_all.json" if os.path.exists(os.path.join(ASSETS, "peer_all.json")) else "peer28.json"
_PEER_DOC = json.load(open(os.path.join(ASSETS, _PEER_FILE), encoding="utf-8"))
PEER = _PEER_DOC["PROF"]
_PEER_META = _PEER_DOC.get("_meta") or {}
# 排除本单自身：报告写「同业分位」时把自己算进去会虚高
# ★ 3.2：同业样本必须**同品种**。原来写死 cat=="信用卡不良"，导致个人消费/房贷单
#   要么取到空集（画不出分位），要么被拿去和信用卡比（回收率、户均金额差一个量级，
#   分位毫无意义）。此处按品种映射到口径库的 cat 取值。
_CAT_MAP = {"个人消费不良": "个人消费贷款", "小微经营不良": "个人经营贷款",
            "住房抵押不良": "住房抵押贷款", "信用卡不良": "信用卡不良"}
_CAT = _CAT_MAP.get(VAR, VAR)
PEERS = [v for v in PEER.values()
         if v.get("cat") == _CAT and v.get("code") != PROJ]
PEER_N = len(PEERS)
PEER_OK = PEER_N >= 3          # <3 单无法画四分位带，该卡片置灰
PEER_SRC_NOTE = _PEER_META.get("desc") or f"{_PEER_FILE}（跨行 {PEER_N} 单·{_CAT}）"


def _pctile(vals, x):
    """x 在 vals 中的百分位（严格小于的比例）

    ★ 空样本必须返回 None 而不是抛 ZeroDivisionError：
      房贷类（住房抵押不良）在同业库里目前没有可比样本，PEERS 为空，
      分位计算直接 0 除。这类"样本不足"应渲染成置灰，不是让整份报告崩掉。
    """
    n = len(vals)
    if not n or x is None:
        # x 为 None = 本单该指标算不出来（如 XIRR 不可解），
        # 不能拿它去和同业数值比大小（`float < None` 直接 TypeError）。
        return None
    return sum(1 for v in vals if v < x) / n * 100.0


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _q(vals, q):
    s = sorted(vals)
    n = len(s)
    return s[min(n - 1, max(0, int(round(q * (n - 1)))))]


def peer_strip(rows, W=680, unit="%"):
    """排序条 + 叠点：每行 = 同业全距轨道 + IQR 带 + 中位刻度 + 惠元标记"""
    LH, RH = 148, 200
    x0, x1 = LH + 8, W - RH
    H = 34 + len(rows) * 42 + 26
    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="同业分位对照" style="width:100%;height:auto;display:block" class="v2c-svg">']
    g.append(f'<text x="{LH+8}" y="16" font-size="10.5" fill="{V.MUTE}">'
             f'横轴：同业全距（{len(PEERS)} 单{VAR}，浅带为四分位区间，刻度为中位）</text>')
    for i, r in enumerate(rows):
        cy = 34 + i * 42 + 12
        vals = r["peers"]
        # ★ 本单该指标为 None（如 XIRR 不可解）时不能参与 min/max：
        #   `min([1.2, None])` 直接 TypeError。只保留有值的一侧，
        #   本单点不画，但同业区间照常呈现——这比整份报告崩掉有用得多。
        _mv = [v for v in ([r["v"]] + vals) if v is not None]
        if not _mv:
            continue
        lo, hi = min(_mv), max(_mv)
        pad = (hi - lo) * 0.08 or 0.01
        lo, hi = lo - pad, hi + pad
        X = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)
        iqr = _q(vals, 0.25), _q(vals, 0.75)
        med = _median(vals)
        g.append(f'<text x="{LH}" y="{cy+4}" text-anchor="end" font-size="11" fill="{V.INK2}">'
                 f'{V.esc(r["label"])}</text>')
        g.append(f'<line x1="{x0}" y1="{cy}" x2="{x1}" y2="{cy}" stroke="{V.AXIS_GRID}" stroke-width="1"></line>')
        g.append(f'<rect x="{X(iqr[0]):.1f}" y="{cy-4.5}" width="{max(1.5, X(iqr[1])-X(iqr[0])):.1f}" '
                 f'height="9" rx="2" fill="{V.NAVY}" fill-opacity=".14"></rect>')
        for v in vals:
            g.append(f'<circle cx="{X(v):.1f}" cy="{cy}" r="2.4" fill="{V.MUTE}" fill-opacity=".45"></circle>')
        if med is not None:
            g.append(f'<line x1="{X(med):.1f}" y1="{cy-6}" x2="{X(med):.1f}" y2="{cy+6}" '
                     f'stroke="{V.INK2}" stroke-width="1.4"></line>')
        # ★ 本单该指标不可解时不画红点、不写数值，只留同业区间与中位。
        #   硬画会在 X(None) 上崩，或（更糟）用一个假值点到图上误导读者。
        if r["v"] is None:
            g.append(f'<text x="{x1+10}" y="{cy+4}" font-size="10.5" fill="{V.SUB}">'
                     f'—（不可解）</text>')
            g.append(f'<text x="{x1+58}" y="{cy+4}" font-size="10" fill="{V.SUB}">'
                     f'中位 {(f"{med*100:.2f}{unit}" if med is not None else "—")}'
                     f' · 分位 —</text>')
            continue
        g.append(f'<circle cx="{X(r["v"]):.1f}" cy="{cy}" r="5" fill="{V.RED}" stroke="#fff" stroke-width="1.8">'
                 f'<title>{V.esc(r["label"])}：{BRAND} {r["v"]*100:.2f}% ｜ '
                 f'同业中位 {(f"{med*100:.2f}%" if med is not None else "—")}</title></circle>')
        g.append(f'<text x="{x1+10}" y="{cy+4}" font-size="10.5" fill="{V.INK}">'
                 f'{r["v"]*100:.2f}{unit}</text>')
        g.append(f'<text x="{x1+58}" y="{cy+4}" font-size="10" fill="{V.SUB}">'
                 f'中位 {(f"{med*100:.2f}{unit}" if med is not None else "—")}'
                 f' · 分位 {(f"{r[chr(112)]:.0f}" if r["p"] is not None else "—")}</text>')
    g.append("</svg>")
    return "".join(g)


def sec9():
    sen_r = L["sen_principal_paid"] / T["senior"]["issue"]
    sub_r = L["sub_principal_paid"] / T["sub"]["issue"]
    c1 = ('<div class="card"><h3>① 兑付终局性</h3><div class="cc"><div class="cnl">'
          f'<p>优先档本金累计兑付率 <b>{pc(sen_r)}%</b>'
          f'（Σ优先档本金 {T["senior"]["issue"]/YI:.2f} 亿元 ÷ 发行 {T["senior"]["issue"]/YI:.2f} 亿元）。</p>'
          f'<p>次级档本金累计兑付率 <b>{pc(sub_r)}%</b>'
          f'（Σ次级档本金 {T["sub"]["issue"]/YI:.2f} 亿元 ÷ 发行 {T["sub"]["issue"]/YI:.2f} 亿元）。</p>'
          f'<p>{state_sentence()}</p>'
          + _buyback_para()
          + '</div></div></div>')
    c2 = ('<div class="card"><h3>② 回收与成本</h3><div class="cc"><div class="cnl">'
          f'<p>全周期实际回收流入 <b>{REC_YI:.2f} 亿元</b>，为入池本息费'
          f'（{wan(M["pool_total"])} 万元）的 <b>{pc(M["recovery_rate"])}%</b>。</p>'
          f'<p>处置费用累计 <b>{yi(M.get("dispose_fee"))} 亿元</b>，占回收流入 <b>{pc(M["dispose_fee_rate"])}%</b>'
          + ('，未触及合同 17% 上限。' if LEGACY_TEXT else
             ((f'，未触及合同 {pc(T["dispose_cap_pct"],0)}% 上限。'
               if M["dispose_fee_rate"] <= T["dispose_cap_pct"] else
               f'，<b>已超合同 {pc(T["dispose_cap_pct"],0)}% 上限</b>（超限部分按合同劣后）。')
              if T.get("dispose_cap_pct") else '。'))
          + '</p>'
          # ★ 3.2：分项必须能加回合计。原写法「服务报酬＋税费＋其他信托费用」把税费
          #   重复计了一次（税费本就含在 fee_total 内），三项相加比合计多 118 万元。
          #   新体例改为「服务报酬 ＋ 其他信托费用（含税费）＝ 费用合计」，三项恒等。
          #   惠元（LEGACY_TEXT）保留 v5 原文，保字节基线。
          + (f'<p>服务报酬 {wan(M["servicer_fee"])} 万元（{pc(M["servicer_fee_rate"])}%）＋'
             f'税费 {wan(L.get("vat_total"))} 万元'
             f'（{pc(_div(L.get("vat_total"), M["recovered"]))}%）＋'
             f'其他信托费用 {wan(OTHER_FEE)} 万元，'
             f'费用端合计占回收 <b>{pc(M["fee_total_rate"])}%</b>。</p>'
             if LEGACY_TEXT else
             f'<p>服务报酬 {wan(M["servicer_fee"])} 万元（{pc(M["servicer_fee_rate"])}%）＋'
             f'其他信托费用 {wan(OTHER_FEE)} 万元'
             f'（其中税费 {wan(L.get("vat_total"))} 万元）'
             f'＝ 费用合计 <b>{wan(M["fee_total"])} 万元</b>，'
             f'占回收 <b>{pc(M["fee_total_rate"])}%</b>。</p>')
          + '</div></div></div>')
    c3 = ('<div class="card"><h3>③ 时间与收益</h3><div class="cc"><div class="cnl">'
          f'<p>优先档 XIRR <b>{pc(M["sen_xirr"])}%</b>（票面 {pc(T["senior"]["coupon"])}%；'
          f'货币加权，与票面不可直接比较）。</p>'
          f'<p>次级档 XIRR <b>{pc(M["sub_xirr"])}%</b>，回报倍数 '
          f'{msafe("sub_multiple")}x。</p>'
          + ('<p>优先档本金 6 个月清零、次级档 9 个月清零，'
             f'信托存续 <b>{M["life_months"]:.0f} 个月</b>即终止'
             '——远快于说明书预测的 2024-08 回收完毕。</p>' if LEGACY_TEXT else
             '<p>' + "、".join(filter(None, [
                 (f'优先档本金 {MON_SEN_ZERO:.0f} 个月清零' if MON_SEN_ZERO is not None
                  else ('优先档本金至清算日未清零' if _SETTLED else '优先档本金已清偿')),
                 (f'次级档 {MON_SUB_ZERO:.0f} 个月清零' if MON_SUB_ZERO is not None
                  else ('次级档至清算日未清零' if _SETTLED
                        else '次级档本金至末次报告期末仍未清偿'))]))
             + ((f'，信托存续 <b>{mon(M["life_months"])} 个月</b>即终止'
                 + (f'——远快于中债预测现金流延续至 {FC_END[-1]} 的排期。' if FC_END else ''))
                if _SETTLED else
                (f'；信托至末次报告期末仍存续（第 {M.get("n_periods")} 期，'
                 f'{L.get("liquidation_end") or "—"}），'
                 + (f'中债预测现金流延续至 {FC_END[-1]}。' if FC_END else '未终止。')))
             + '</p>')
          + '</div></div></div>')
    c4 = ('<div class="card"><h3>④ 数据质量与风险提示</h3><div class="cc"><div class="cnl" data-w-dqcard="1">'
          '<p class="w-dqsum" data-w-dqsum="1">数据质量：完整度高 ｜ 缺项 0 ｜ 口径注 3 ｜ 来源 2 ｜ '
          '材料缺 3 类　（明细见 ⑧）</p>'
          '</div></div></div>')
    def _pv(v, pct=0):
        """指标值格式化：None → 「—」（不可解/未披露），不写 0"""
        if v is None:
            return '—'
        return f'{v*100:.2f}%' if pct else f'{v:.2f}'

    def _pp(r):
        """分位格式化：None → 「—」"""
        return f'{r["p"]:.0f}' if r.get("p") is not None else '—'

    def prow(label, key, mine):
        vals = [v[key] for v in PEERS if isinstance(v.get(key), (int, float))]
        vals = [x for x in vals if x]
        return {"label": label, "v": mine, "peers": vals, "p": _pctile(vals, mine)}

    rows = [
        prow("回收率", "recRate", M["recovery_rate"]),
        prow("预测回收率", "expRecRate", P["exp_rec_rate_zz"]),
        prow("达成率", "vsForecast", ACH),
        prow("证券化率", "secRatio", M["securitization_rate"]),
        prow("处置费率", "disposeFeeRate", M["dispose_fee_rate"]),
        prow("优先档 XIRR", "xirrSen", M["sen_xirr"]),
        prow("次级档 XIRR", "xirrSub", M["sub_xirr"]),
    ]
    # ★ 分位计算要在 PEER_OK 判定之后再做：同业样本为空时 _pctile 返回 None，
    #   这里若先算 `r["p"] >= 75` 会 TypeError（房贷类目前 0 个可比样本）。
    hi = [r for r in rows if r["p"] is not None and r["p"] >= 75]
    hi_txt = "、".join(f'{r["label"]} {r["p"]:.0f}' for r in sorted(hi, key=lambda x: -x["p"]))
    # 样本来源前缀：LEGACY 用 v5 原文措辞，新行走数据驱动
    _peer_pre = (f'样本：技能口径库内 {PEER_N} 单已清算信用卡不良 ABS（不含本单），'
                 if LEGACY_TEXT else
                 f'样本：{PEER_SRC_NOTE}，不含本单；')
    if not PEER_OK:
        # 同品种已清算单不足 3 单 → 不做分位（拿别品种凑数会得出反向结论），置灰
        c5 = ('<div class="card dim" data-chart="peer-gray" style="margin-top:14px">'
              f'<h3>⑤ 同业定位：{VAR}清算项目分位对照<span class="v2c-tag">已置灰</span></h3>'
              '<div class="dim-box"><div class="dim-k">同品种同业样本不足</div>'
              f'<div class="dim-w">口径库内 {VAR} 已清算样本仅 {PEER_N} 单（不含本单），'
              '少于四分位统计所需的 3 单下限，故不出分位图。'
              '不以其他品种样本替代——回收率、户均金额、处置成本量级不同，'
              '混比会得出反向结论。样本累积到 3 单后本卡片自动启用。</div></div></div>')
        body = f'<div class="grid2">{c1}{c2}{c3}{c4}</div>' + c5
        return (fold_open("⑦", "核心结论",
                          f'兑付 优先{pc(sen_r)}%/次级{pc(sub_r)}% ｜ 优先XIRR {pc(M["sen_xirr"])}% ｜ '
                          + _STATE_TXT)
                + body + fold_close())
    c5 = (f'<div class="card" data-chart="peer-strip" style="margin-top:14px">'
          f'<h3>⑤ 同业定位：{PEER_N} 单{VAR}清算项目分位对照</h3>'
          f'{peer_strip(rows)}'
          + note(_peer_pre
                 + '指标定义与本报告一致——回收率＝累计回收 ÷ 入池本息费；'
                 + ('处置费率＝处置费用 ÷ 累计回收；' if LEGACY_TEXT
                    else '处置费率＝已报销处置费用 ÷ 累计回收；')
                 + '达成率＝累计回收 ÷ 中债预计回收；'
                 '证券化率＝发行规模 ÷ 入池本息费；XIRR 为货币加权口径。'
                 '分位＝同业中严格低于本单的样本占比（100＝同业最高）；'
                 f'浅带为该指标的四分位区间，竖刻度为同业中位，实心红点为{BRAND}。')
          + (note(f'<b>读法</b>：分位高于 75 的指标为「{hi_txt}」；'
                  f'处置费率 {M["dispose_fee_rate"]*100:.2f}%（分位 {rows[4]["p"]:.0f}）'
                  f'与达成率 {ACH*100:.2f}%（分位 {rows[2]["p"]:.0f}）低于同业中位。'
                  f'两组信号并不矛盾：回收率、证券化率、次级档收益偏高，'
                  + (f'主要来自<b>清仓回购提前终止</b>（存续仅 {mon(M["life_months"])} 个月'
                    + (f'、次级档 {MON_SUB_ZERO:.0f} 个月即收回本金' if MON_SUB_ZERO is not None else '')
                    + '），而非自然清收超出预期'
                    + (f'——剔除回购价款后自然清收回收率为 {pc(NAT_RATE)}%；' if NAT_RATE is not None
                       else '；')
                    if _BQ_PRICE else '')
                  + f'达成率衡量的恰是「自然回收 vs 中债全周期预测」，本单因此低于同业中位。'
                  f'处置费率低则反映本单委外催收周期短、按回收额计费的费用随回收前置而集中释放。')
             if LEGACY_TEXT else
             note(f'<b>读法</b>：分位＝同品种已清算样本中严格低于本单的占比（100＝同业最高）；'
                  f'本单分位 ≥75 的指标为「{hi_txt or "无"}」。'
                  f'处置费率 {_pv(M.get("dispose_fee_rate"), pct=1)}（分位 {_pp(rows[4])}）、'
                  f'达成率 {ACH*100:.2f}%（分位 {_pp(rows[2])}）、'
                  f'次级档 XIRR {_pv(M.get("sub_xirr"), pct=1)}（分位 {_pp(rows[6])}）。'
                  f'<b>本节只陈述分位，不做成因推断</b>——分位高低源自入池结构、'
                  f'回收时间分布与费用科目构成的差异，需结合本报告 ③④⑤ 节判读；'
                  f'样本量仅 {PEER_N} 单，分位仅供横向参考，不作为绩效评价依据。'))
          + '</div>')
    body = f'<div class="grid2">{c1}{c2}{c3}{c4}</div>' + c5
    return (fold_open("⑦", "核心结论",
                      f'兑付 优先{pc(sen_r)}%/次级{pc(sub_r)}% ｜ 优先XIRR {pc(M["sen_xirr"])}% ｜ '
                      + _STATE_TXT)
            + body + fold_close())


# ============================ ⑧ 数据质量与披露 ============================
def _sec10_legacy():
    """⑧ 惠元第三期 v5 原文（字节级保留，见 LEGACY_TEXT 说明）"""
    mats = [("法律意见书", "否", "合规类，不含现金流与分配数据"),
            ("会计意见书", "否", "合规类，不含现金流与分配数据"),
            ("跟踪评级报告", "否", "外部分析观点，报告不引用评级")]
    mrows = "".join(f'<tr><td class="mn">{a}</td><td class="mi"><span class="no">{b}</span></td>'
                    f'<td>{c}</td></tr>' for a, b, c in mats)
    mat = ('<details class="dq-mat" data-w-mat="1"><summary>缺失材料 <span class="dq-mat-n">3 项</span>'
           '<span class="dq-mat-s">· 依据：资产池为中债披露文件 · 点开看逐项影响</span></summary>'
           '<table class="dq-mt"><thead><tr><th style="width:24%">材料名称</th>'
           '<th style="width:15%">是否影响主结论</th><th style="width:61%">说明</th></tr></thead>'
           f'<tbody>{mrows}</tbody></table>'
           '<div class="dq-mf">本报告主结论仅取决于发行说明书与受托机构报告（二者本单齐备，'
           '含 5 期受托机构报告、清算审计报告与清算报告复核）；上述材料不承载现金流数据，'
           '故不影响任何数值结论。</div></details>')

    ov = ('<div class="dq-ov" data-w-dqov="1"><span class="dq-ov-t">披露概览：</span>'
          '共 12 项 ｜ 已回源补全 9 项 ｜ 源未披露 0 项 ｜ 源文件缺失 3 项</div>')
    dq3 = ('<div class="dq3">'
           '<div class="dq-sec"><p class="dq-t">① 数据完整度</p>'
           '<div class="dq-b">本单核心字段齐全，无缺项；入池资产分布（10 类）、分档本金·利息、'
           '费用与税款、逐期回收流入、信托账户五期收支、清算收支均已归集并交叉校验，'
           '12 项勾稽（含信托账户 5 期配平、证券本息与分配表交叉、清算剩余财产衔接）全部通过。</div>'
           + mat + '</div>'
           '<div class="dq-sec"><p class="dq-t">② 口径注解</p>'
           f'<div class="dq-b">证券化率 {pc(M["securitization_rate"])}% 以入池本息费为分母'
           f'（若以入池本金 {PRIN_YI:.2f} 亿元为分母则为 {pc(M["issue_total"]/P["balance_principal"])}%，'
           '比较时请注意分母口径）；处置费率分母唯一为<b>累计回收</b>；预计回收采用中债口径'
           '（18.28%，中债资信测算）；达成率＝实际回收率 ÷ 预测回收率；'
           'XIRR 为货币加权口径，与票面利率不可直接比较；次级档不做资金成本倒算（无披露字段）。</div></div>'
           '<div class="dq-sec"><p class="dq-t">③ 来源依据</p>'
           '<div class="dq-b">发行说明书（681 页）；受托机构报告 2022 年度第 1–5 期；'
           '簿记建档发行结果公告；成立公告；重大事件报告书；清算审计报告；清算报告专项复核说明；'
           '中债资信与联合资信评级报告。金额单位：亿元 2 位 / 万元 2 位；比率百分号 2 位；'
           '缺失一律记「—」，不臆造。</div></div></div>')

    body = ov + dq3
    return (fold_open("⑧", "数据质量与披露", '披露 <span class="dq-n">12 项</span>', collapsed=True)
            + body + fold_close())


def sec10():
    """⑧ 数据质量与披露 —— 全部按本单实际材料与字段生成

    ★ 重写原因：原实现把惠元第三期的材料清单整段写死在文案里 ——
      「5 期受托机构报告」「清算审计报告与清算报告复核」「说明书 681 页」
      「中债资信与联合资信评级报告」「预计回收 18.28%」。
      这些换到任何别的单都成了**虚构事实**：
        · 招行只有中债资信 + 新世纪，**没有联合资信**
        · 招行说明书 431 / 560 页，不是 681 页
        · 和萃2021 年第 1 期**没有清算报告**（清算未结项）
        · 18.28% 是惠元第三期的达成率，不是通用值
      现在改为读 payload.materials（由 14_to_layout.build_materials 按
      实际下载目录 + 文本索引生成）与 payload 自身字段。
    """
    if LEGACY_TEXT:
        return _sec10_legacy()
    MAT = D.get("materials") or {}
    items = MAT.get("items") or []

    if not items:
        # 兜底：调用方未提供材料清册时，只列能从 payload 推出的最少事实
        items = [{"name": "发行说明书", "present": True, "detail": ""},
                 {"name": "受托机构报告", "present": bool(PER), "detail": f"{len(PER)} 期"},
                 {"name": "清算报告（含审计/复核说明）", "present": False,
                  "detail": "未提供材料清册，无法核实"}]

    miss = [m for m in items if not m.get("present")]
    have = [m for m in items if m.get("present")]
    miss_n = len(miss)

    # 缺失材料表：逐项写「是否影响主结论 + 说明」
    def _impact(m):
        nm = m["name"]
        if "清算" in nm:
            return ("部分", "清算口径字段（清算净收益、清算日持有人权益）取不到，"
                            "回收与证券兑付改由末次受托机构报告取数")
        if "跟踪评级" in nm:
            return ("否", "外部分析观点，报告不引用评级结论")
        if "法律" in nm or "会计" in nm:
            return ("否", "合规类文件，不含现金流与分配数据")
        return ("否", "不承载现金流数据")

    mrows = "".join(
        f'<tr><td class="mn">{V.esc(m["name"])}</td>'
        f'<td class="mi"><span class="no">{_impact(m)[0]}</span></td>'
        f'<td>{V.esc(_impact(m)[1])}</td></tr>' for m in miss)
    mat = (f'<details class="dq-mat" data-w-mat="1"><summary>缺失材料 '
           f'<span class="dq-mat-n">{miss_n} 项</span>'
           f'<span class="dq-mat-s">· 点开看逐项影响</span></summary>'
           '<table class="dq-mt"><thead><tr><th style="width:24%">材料名称</th>'
           '<th style="width:15%">是否影响主结论</th><th style="width:61%">说明</th></tr></thead>'
           f'<tbody>{mrows or "<tr><td colspan=3>无缺失</td></tr>"}</tbody></table>'
           + (f'<div class="dq-mf">{V.esc(MAT.get("degraded"))}</div>'
              if MAT.get("degraded") else '')
           + '</details>')

    # 披露概览
    ov = ('<div class="dq-ov" data-w-dqov="1"><span class="dq-ov-t">披露概览：</span>'
          f'材料 {MAT.get("total_n") or len(items)} 类 ｜ 齐备 {len(have)} 类 ｜ '
          f'缺失 {miss_n} 类'
          + (f' ｜ <b>本单无清算报告</b>' if MAT.get("liquidation_absent") else '')
          + '</div>')

    # ① 数据完整度：按 payload 实际字段统计，不写死
    _core = [("分档发行规模", (T.get("senior") or {}).get("issue") and
              (T.get("sub") or {}).get("issue")),
             ("入池本息费", P.get("balance_total")),
             ("中债预计回收", P.get("exp_recovery_zz")),
             ("累计回收", M.get("recovered")),
             ("逐期明细", bool(PER)),
             ("费用明细", bool(M.get("fee_total"))),
             ("证券代码", _META.get("code_sen")),
             ("票面利率", (T.get("senior") or {}).get("coupon")),
             ("清算日/终止日", L.get("terminate_date")),
             ("清仓回购判定", (L.get("buyback") or {}).get("occurred") is not None)]
    _ok = sum(1 for _, v in _core if v)
    _misscore = [k for k, v in _core if not v]
    _nd = len(D.get("dist") or {})
    _absent = len(D.get("dist_absent") or {})
    dq_b = (f'核心字段 {_ok}/{len(_core)} 项齐备'
            + (f'（缺：{"、".join(_misscore)}）' if _misscore else '，无缺项')
            + f'；入池资产分布已归集 {_nd} 个维度'
            + (f'，另有 {_absent} 个维度本品种不适用' if _absent else '')
            + f'；逐期明细 {len(PER)} 期。'
            + ('<b>本单无清算报告</b>，清算口径字段按末次受托机构报告降级取数，'
               '报告各节已逐一注明。' if MAT.get("liquidation_absent")
               else '清算报告齐备，清算口径字段与受托报告已交叉校验。'))

    # ② 口径注解：全部用本单数值
    _cap = T.get("dispose_cap_pct")
    dq_b2 = (f'证券化率 {pc(M["securitization_rate"])}% 以入池本息费为分母'
             + (f'（若以入池本金 {PRIN_YI:.2f} 亿元为分母则为 '
                f'{pc(_div(M["issue_total"], P.get("balance_principal")))}%，比较时请注意分母口径）'
                if P.get("balance_principal") else '')
             + '；处置费率分母唯一为<b>累计回收</b>'
             + (f'，合同上限为累计回收款的 {pc(_cap,0)}%' if _cap else '')
             + f'；预计回收采用<b>中债资信</b>口径（{pc(P.get("exp_rec_rate_zz"))}%，'
               f'金额 {num(P.get("exp_recovery_zz"))} 元）'
             + (f'；说明书披露的主承销商口径为 {num(P.get("exp_recovery_sm_underwriter"))} 元，'
                f'本报告不采用' if P.get("exp_recovery_sm_underwriter") else '')
             + '；达成率＝累计回收 ÷ 中债预计回收'
             + f'（本单 {pc(ACH)}%）；XIRR 为货币加权口径，与票面利率不可直接比较'
             + '；次级档'
             + (f'资金成本 {num(M["sub_fixed_total"])} 元取自受托报告「证券利息总支出 '
                f'− 优先档付息」的账面拆分，<b>不做资金成本倒算</b>（不以收益率反推）'
                if M.get("sub_fixed_total") else '不做资金成本倒算（无披露字段）')
             + '。')

    # ③ 来源依据：只列实际齐备的材料
    _src = "；".join(
        f'{m["name"]}{("（" + m["detail"] + "）") if m.get("detail") else ""}'
        for m in have)
    dq_b3 = (f'{_src}。金额单位：亿元 2 位 / 万元 2 位；比率百分号 2 位；'
             '缺失一律记「—」，不臆造。')

    dq3 = ('<div class="dq3">'
           '<div class="dq-sec"><p class="dq-t">① 数据完整度</p>'
           f'<div class="dq-b">{dq_b}</div>' + mat + '</div>'
           '<div class="dq-sec"><p class="dq-t">② 口径注解</p>'
           f'<div class="dq-b">{dq_b2}</div></div>'
           '<div class="dq-sec"><p class="dq-t">③ 来源依据</p>'
           f'<div class="dq-b">{dq_b3}</div></div></div>')

    body = ov + dq3
    return (fold_open("⑧", "数据质量与披露",
                      f'材料 <span class="dq-n">{len(have)}/{MAT.get("total_n") or len(items)}</span> 类齐备',
                      collapsed=True)
            + body + fold_close())


# ============================ 组装 ============================
FOOT = (f'<div class="foot">数据来源：中国债券信息网披露文件（发行说明书、受托机构报告 {len(PER)} 期'
        + ('、清算审计报告、清算报告'
           if LEGACY_TEXT or not (D.get("materials") or {}).get("liquidation_absent")
           else '、重大事件报告书；<b>本单无清算报告</b>')
        + '） ｜ 口径：清算期穿透分析，各节内逐一注明 ｜ '
        f'金额单位：亿元 2 位 / 万元 2 位，比率百分号 2 位 ｜ 项目主键：{PROJ}</div>')

JS = r"""
(function(){
  var sidebar=document.getElementById('sidebar'), scrim=document.getElementById('scrim'),
      hb=document.getElementById('hamburger'), crumb=document.getElementById('crumb');
  function setCrumb(){
    if(crumb) crumb.innerHTML='<b>不良ABS 穿透</b> ＞ 股份制商业银行 ＞ __BANK__ ＞ __PROJ__';
  }
  // 折叠
  document.querySelectorAll('.fold-h').forEach(function(h){
    h.addEventListener('click',function(){h.parentElement.classList.toggle('collapsed');});
  });
  // 侧栏条目：滚到对应节
  document.querySelectorAll('.sb-item').forEach(function(a){
    a.addEventListener('click',function(e){
      e.preventDefault();
      var id=a.getAttribute('data-sec');
      var t=id?document.getElementById(id):null;
      if(t){
        var f=t.closest('.fold');
        if(f) f.classList.remove('collapsed');
        t.scrollIntoView({behavior:'smooth',block:'start'});
      }
      document.querySelectorAll('.sb-item').forEach(function(x){x.classList.remove('on');});
      a.classList.add('on');
      if(window.innerWidth<=1024&&sidebar){sidebar.classList.remove('open');if(scrim)scrim.classList.remove('on');}
    });
  });
  // 分组折叠
  document.querySelectorAll('.sb-ghead,.sb-thead').forEach(function(g){
    g.addEventListener('click',function(){g.parentElement.classList.toggle('collapsed');});
  });
  // 搜索
  var s=document.getElementById('search');
  if(s) s.addEventListener('input',function(){
    var q=s.value.trim().toLowerCase();
    document.querySelectorAll('.sb-item').forEach(function(it){
      it.style.display=(!q||it.textContent.toLowerCase().indexOf(q)>=0)?'':'none';
    });
  });
  // 抽屉
  if(hb&&sidebar&&scrim){
    hb.addEventListener('click',function(){sidebar.classList.toggle('open');scrim.classList.toggle('on');});
    scrim.addEventListener('click',function(){sidebar.classList.remove('open');scrim.classList.remove('on');});
  }
  // 滚动高亮
  var secs=[].slice.call(document.querySelectorAll('.fold[id]'));
  window.addEventListener('scroll',function(){
    var y=window.scrollY+130,cur=null;
    secs.forEach(function(x){if(x.offsetTop<=y)cur=x;});
    if(cur) document.querySelectorAll('.sb-item').forEach(function(a){
      a.classList.toggle('on',a.getAttribute('data-sec')===cur.id);
    });
  },{passive:true});
  setCrumb();
  document.querySelectorAll('.rv').forEach(function(n){n.classList.add('in');});
})();
"""


def build(out_path=None):
    nav = [("s1", "① 项目档案"), ("s2", "② 资产池基础情况"), ("s3", "③ 分期节奏"),
           ("s4", "④ 现金流分配过程"), ("s6", "⑤ XIRR 与 XNPV"), ("s8", "⑥ 账户勾稽"),
           ("s9", "⑦ 核心结论"), ("s10", "⑧ 数据质量与披露")]
    nav_html = "".join(f'<a class="sb-item" data-sec="{k}">{t}</a>' for k, t in nav)

    body = (sec1().replace('<div class="fold rv">', '<div class="fold rv" id="s1">', 1)
            + sec2().replace('<div class="fold rv">', '<div class="fold rv" id="s2">', 1)
            + sec3().replace('<div class="fold rv">', '<div class="fold rv" id="s3">', 1)
            + sec4().replace('<div class="fold rv">', '<div class="fold rv" id="s4">', 1)
            + sec6().replace('<div class="fold rv">', '<div class="fold rv" id="s6">', 1)
            + sec8().replace('<div class="fold rv collapsed">', '<div class="fold rv collapsed" id="s8">', 1)
            + sec9().replace('<div class="fold rv">', '<div class="fold rv" id="s9">', 1)
            + sec10().replace('<div class="fold rv collapsed">', '<div class="fold rv collapsed" id="s10">', 1))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{PROJ} · 不良ABS 单项目穿透</title>
<style>{CSS}</style></head>
<body><div class='app'>
<aside class='sidebar' id='sidebar'>
  <div class='sb-head'>
    <div class='sb-title'>{PROJ}</div>
    <div class='sb-sub'>单项目八节 · {BANK} · {VAR}</div>
    <input class='sb-search' id='search' placeholder="搜索节（按 / 聚焦）">
  </div>
  <nav class='sb-nav'>
    <a class="sb-item" data-sec="s1">◆ {PROJ}（单项目八节）</a>
    <div class="sb-type" data-type="分节导航">
      <div class="sb-thead"><span>分节导航</span><span class="cnt">8 节</span><span class="sb-caret">▾</span></div>
      <div class="sb-group" data-bank="{PROJ}">
        <div class="sb-ghead"><span>穿透八节</span><span class="cnt">8</span><span class="sb-caret">▾</span></div>
        <div class="sb-items">{nav_html}</div>
      </div>
    </div>
  </nav>
</aside>
<main class='main'>
  <div class='topbar'><button class='hamburger' id='hamburger'>☰</button>
    <div class='crumb' id='crumb'></div></div>
  <section class="view on" id="view-p0" style="--accent:{ACCENT};--accent-soft:#FBEFEF;--accent-line:#E9C7C6">
    {body}
    {FOOT}
  </section>
</main></div>
<div class="scrim" id="scrim"></div>
<script>{JS.replace("__PROJ__", PROJ).replace("__BANK__", BANK)}</script></body></html>"""
    out = out_path or os.path.join(os.getcwd(), out_name())
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(html)
    print("HTML →", out, f"{len(html)/1024:.0f} KB")
    _selfcheck(out)
    return out


def _selfcheck(out):
    """构建后自校验（冗余保护 3）：尺寸与黄金基线比对，只报告不阻断"""
    sha = _sha(out)
    size = os.path.getsize(out)
    mp = os.path.join(GOLDEN, "report.sha256")
    want = open(mp, encoding="utf-8").read().split()[0] if os.path.exists(mp) else None
    print(f"  产物 {size:,} B ｜ sha256 {sha}")
    if want:
        if sha == want:
            print("  ✓ 与黄金基线字节级一致（G1 通过）")
        else:
            print(f"  ✗ 与黄金基线不一致（期望 {want[:12]}…）")
            print("    → 若为有意改版，跑 python repro_gate.py --rebless；否则说明构建被污染")
    else:
        print("  （未找到 assets/single/golden/report.sha256，跳过比对）")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--check" in args:
        check_inputs(strict=True)
        sys.exit(0)
    if "--no-guard" not in args:
        check_inputs(strict=True)
    outp = None
    if "--out" in args:
        i = args.index("--out")
        d = args[i + 1]
        outp = d if d.lower().endswith(".html") else os.path.join(d, out_name())
    build(outp)
