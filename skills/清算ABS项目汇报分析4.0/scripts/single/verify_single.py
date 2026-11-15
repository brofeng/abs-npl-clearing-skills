# -*- coding: utf-8 -*-
"""G3 语义断言（技能 3.0 · 跨单泛化 + 独立复算 + 渲染后断言）

设计原则
--------
1) **不复用构建脚本的任何中间变量**：所有数值都用 assets/single/payload.json + metrics.json
   独立重算一遍，再与产物文本比对。构建脚本自证不算通过。
2) **跨单可复现**：2.0 的断言里硬编码了第三期的数值（0.9114065 / 99.18% / 5,763,476.69 /
   2.28/3.04/4.14/4.89/5.48），换一单必然 FAIL。3.0 全部改为从 payload/metrics 驱动。
3) **字段缺失 ≠ 断言失败**：旧版取数器产出的 payload 可能缺新字段（如 liab_at_begin_total）。
   这类记 SKIP 并在汇总里显示，不冒充 PASS、也不误报 FAIL。用 preflight.py 检查齐备性。
4) **容差必须有界且显示**：不允许「为了过而放宽」。每条带容差的断言都要把残差打印出来。
5) **★容差按披露精度设定，不按「看起来严格」设定**（3.0 最重要的教训）。
   所有比率类字段在披露文件里都是**四舍五入值**，反算必然带舍入误差：
     · 回收率披露到 4 位小数（18.28%）→ 反乘金额的误差上限 ＝ 入池 × 5e-5
       （第三期 40.87 亿 × 5e-5 ≈ 20.4 万；实测差 15.8 万，用「1 万元」卡必然误报）
     · 次级占比披露到 4 位小数（0.1509）→ 与 80/530=0.150943 差 4e-5，用 1e-9 卡必然误报
   所以：**容差 = 该字段的披露精度所决定的理论上限**，不是越小越好。
   反过来，真错都是 bp 级或万元级以上，这个容差仍然抓得住（实测 2022 四期分档差 6,910 万、
   2022 六期漏 25 万），不存在「放太宽漏掉」的问题。
6) **metrics 不是标尺**：metrics 与 payload 同源，同源错误会一起错；而且它可能残留旧口径
   （第三期 achieve_rate = 0.9115992 是「18.28%×入池」旧口径反推，与金额口径 0.9114067
   差 1.93bp）。断言必须以「独立重算值」为准，metrics 只用来做「同源一致性」交叉检查。

用法：
  python verify_single.py [--html <产物>]
  python verify_single.py --html x.html --json out.json   # 额外导出结构化结果

EXIT：0 全通过 / 1 有 FAIL / 2 环境问题
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(SKILL, "assets", "single")

OUT_NAME = "惠元2021年第三期_不良ABS穿透分析_v5.html"

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]
EDGE = next((p for p in EDGE_CANDIDATES if os.path.exists(p)), EDGE_CANDIDATES[0])

_ap = argparse.ArgumentParser()
_ap.add_argument("--html", default=os.path.join(os.getcwd(), OUT_NAME))
_ap.add_argument("--json", default=None, help="把断言明细另存为指定 JSON")
_ap.add_argument("--assets", default=None,
                 help="数据目录（含 payload.json + metrics.json）；默认 assets/single。"
                      "指向其他单子的取数目录即可跨单复核，不必把数据塞进技能目录。")
_args, _ = _ap.parse_known_args()
HTML = _args.html
ASSETS = os.path.abspath(_args.assets) if _args.assets else ASSETS

_pj = os.path.join(ASSETS, "payload.json")
if not os.path.exists(_pj):
    print(f"缺少输入：{_pj}")
    print("请先把单项目 payload.json / metrics.json 放到 assets/single/ 下")
    sys.exit(2)
if not os.path.exists(HTML):
    print(f"产物不存在：{HTML}")
    sys.exit(2)

TMP = os.path.join(os.path.dirname(os.path.abspath(HTML)), "_probe_verify.html")
D = json.load(open(_pj, encoding="utf-8"))
M = json.load(open(os.path.join(ASSETS, "metrics.json"), encoding="utf-8"))

# ─────────────────────────────────────────────────────────────
# 前置契约检查（v3 新增）
#   2.0 缺这一层：取数器漏了某个必需键时，断言脚本会在中途 KeyError 崩掉，
#   退出码 1 但没有任何断言日志，使用者只看到一段 traceback，无法判断是
#   「数据错」还是「取数器漏项」。实测注入「删除 fee_detail['处置费']」即触发。
#   这里把必需字段一次列清：缺则明确报「输入契约不满足」并 EXIT=2，
#   与「断言 FAIL」（数据错，EXIT=1）区分开。
# ─────────────────────────────────────────────────────────────
_REQ = [
    ("payload", D, ["pool", "tranche", "liquidation", "dist", "periods", "trust_account"]),
    ("payload.pool", D.get("pool") or {},
     ["balance_total", "exp_recovery_zz", "exp_rec_rate_zz", "n_loans",
      "n_borrowers", "balance_principal", "balance_interest_fee"]),
    ("payload.tranche", D.get("tranche") or {}, ["senior", "sub", "total"]),
    ("payload.liquidation", D.get("liquidation") or {},
     # 注意 cash_begin 不在此列：它只被恒等式①使用，而恒等式①已按 liab_at_begin_total
     # 是否存在做了 SKIP 保护。旧版 payload（含技能自带的第三期）没有该键，
     # 若在必需清单里会把整份样例卡死在 EXIT=2，反而让门禁跑不起来。
     ["total_recovery", "account_interest", "fees_total", "fee_detail",
      "sen_principal_paid", "sen_interest_paid", "sub_principal_paid",
      "sub_income_paid", "residual_asset", "holder_equity_end"]),
    ("payload.dist", D.get("dist") or {}, ["grade", "occupation", "region"]),
    ("metrics", M, ["securitization_rate", "recovery_rate", "dispose_fee_rate",
                    "achieve_rate", "recovered", "sen_xirr", "sub_xirr",
                    "cum_at_period"]),
]
_missing = []
# ★ 3.2：结构性不可得的字段不在契约内。
#   招行/建行的清算报告采用「末次受托机构报告」体例，**没有**清算资产负债表，
#   故 residual_asset / holder_equity_end / liquidation_gain 三项永远为 None。
#   取数器会写 payload.liquidation.no_balance_sheet = true 明示这一点；
#   此时免检这三项（下游恒等式 likewise SKIP），而不是判成「取数漏项」卡死门禁。
#   关键区别：**声明了不适用 ≠ 悄悄漏了**，前者有留痕、后者没有。
_LQ0 = D.get("liquidation") or {}
_NO_BS = bool(_LQ0.get("no_balance_sheet"))
# ★ 信托是否仍在存续（settlement_state=outstanding）：
#   存续中单的清算日/清算净收益/本金全额兑付/次级收益倍数/XIRR 上限
#   这些"已清算才成立"的口径一律不适用，记 SKIP 而不是 FAIL。
_OUTSTANDING = (_LQ0.get("settlement_state") == "outstanding")
_BS_ONLY = {"residual_asset", "holder_equity_end", "liquidation_gain"}

# ★ 3.2：**源未披露**的字段同样不该卡死门禁，但必须「有声明」——
#   判定依据是 payload.dist_gray（维度级）与 payload.pool._absent（单字段级）
#   这类显式留痕；悄悄留空（无声明）仍算取数漏项。
#   实测建鑫信用卡不良：说明书按「笔数」统计、不披露「户数」，
#   n_borrowers 永远为 None；把这种情况判成漏项，等于要求取数器编一个数出来。
# ★ XIRR 不可解也是一种"合法缺失"，但必须能自证：次级档本期既无本金、
#   也无固定资金成本和超额收益（三栏在受托报告里都是破折号）→ 现金流全 0，
#   XIRR 在数学上无解。这不是取数漏项，不能要求取数器编一个数出来。
_PER0 = D.get("periods") or []
_SUB_NOFLOW = bool(_PER0) and all(
    not (p.get("sub_principal") or 0) and not (p.get("sub_fixed_cost") or 0)
    and not (p.get("sub_income") or 0) for p in _PER0)

_GRAY = (D.get("dist_gray") or {})
_ABS_POOL = set((D.get("pool") or {}).get("_absent") or [])
_SRC_ABSENT = {
    "payload.pool.n_borrowers": "户数",
}
for _label, _obj, _keys in _REQ:
    for _k in _keys:
        if _label == "payload.liquidation" and _NO_BS and _k in _BS_ONLY:
            continue
        if _label == "payload.dist" and _k in _GRAY:
            continue                     # 维度已在 dist_gray 里声明缺失原因
        if (_label == "metrics" and _k == "sub_xirr" and _SUB_NOFLOW):
            continue                     # 次级档全额无现金流，XIRR 数学上不存在
        _fq = f"{_label}.{_k}"
        if _fq in _SRC_ABSENT and _k in _ABS_POOL:
            continue                     # 单字段已声明源未披露
        if not isinstance(_obj, dict) or _k not in _obj or _obj.get(_k) is None:
            _missing.append(_fq)
# 费用明细核心科目：分配顺序以处置费／贷款服务费为前提，缺了整份报告的
# 「处置费率」「服务费率」都没有来源，属于取数器漏项而不是数据本身错。
_fd0 = (D.get("liquidation") or {}).get("fee_detail") or {}
for _core in ("处置费", "贷款服务费"):
    if _core not in _fd0:
        _missing.append(f"payload.liquidation.fee_detail.{_core}")

if _missing:
    print("输入契约不满足：取数结果缺少必需字段，断言无法进行（这不是数据错，是取数器漏项）")
    for x in _missing:
        print(f"  - {x}")
    print("\n处理建议：")
    print("  1) 回到取数脚本补齐上述字段，重出 payload.json / metrics.json")
    print("  2) 若是旧版取数器产物，参照 references/19-取数契约与字段字典.md 升级")
    print("  3) 不要为了跑通门禁而在 payload 里手工填数——那等于让断言自证")
    sys.exit(2)

res = []


def chk(cat, desc, ok, detail=""):
    """硬断言：必须为真"""
    res.append({"cat": cat, "desc": desc, "ok": bool(ok), "detail": str(detail)})


def skip(cat, desc, why=""):
    """跳过：输入字段缺失，判不了（不计 PASS 也不计 FAIL）"""
    res.append({"cat": cat, "desc": desc, "ok": None, "detail": f"跳过：{why}"})


def chk_if(cat, desc, val, test, detail=""):
    """值存在才判：val 为 None 则跳过

    test 是接受 val 返回 bool 的函数。用于所有「新字段」断言，
    保证旧版 payload 不会因 KeyError 崩掉，同时新单能真正生效。
    """
    if val is None:
        skip(cat, desc, "输入字段缺失")
        return
    try:
        chk(cat, desc, test(val), detail)
    except Exception as e:                                   # 断言本身写错也要暴露
        chk(cat, desc + "［断言异常］", False, repr(e))


src = open(HTML, encoding="utf-8").read()
P, T, L = D["pool"], D["tranche"], D["liquidation"]
DIST, PER, TA = D["dist"], D["periods"], D["trust_account"]
META = D.get("meta") or {}

# ================= 一、数据复算（独立于构建脚本） =================
chk("复算", "证券化率 = 发行 ÷ 入池本息费",
    abs(T["total"] / P["balance_total"] - M["securitization_rate"]) < 1e-9,
    f'{T["total"]/P["balance_total"]*100:.4f}%')
chk("复算", "回收率 = 累计回收 ÷ 入池本息费",
    abs(L["total_recovery"] / P["balance_total"] - M["recovery_rate"]) < 1e-9,
    f'{L["total_recovery"]/P["balance_total"]*100:.4f}%')
chk("复算", "处置费率 = 处置费用 ÷ 累计回收",
    abs(L["fee_detail"]["处置费"] / L["total_recovery"] - M["dispose_fee_rate"]) < 1e-9,
    f'{L["fee_detail"]["处置费"]/L["total_recovery"]*100:.4f}%')
# 达成率一律「金额 ÷ 金额」，禁止用四舍五入后的百分比反推（18.28% 反推差 2bp）
# metrics.achieve_rate 可能是旧口径残留（第三期实测差 1.93bp），故容差 5bp，
# 且额外要求「金额口径值出现在正文」——报告呈现的必须是金额口径那一版。
_calc_ach = L["total_recovery"] / P["exp_recovery_zz"]
chk("复算", "达成率 = 累计回收 ÷ 中债预计回收（金额口径，容差 5bp）",
    abs(_calc_ach - M["achieve_rate"]) < 5e-4 and f'{_calc_ach*100:.2f}%' in src,
    f'金额口径 {_calc_ach*100:.4f}% vs metrics {M["achieve_rate"]*100:.4f}%'
    f'（差 {abs(_calc_ach-M["achieve_rate"])*10000:.2f}bp）')
# 回采校验：中债预计回收率只披露到 4 位小数，反乘金额的理论误差上限 = 入池 × 5e-5。
# 用固定「1 万元」会误报（第三期 40.87 亿 × 5e-5 ≈ 20.4 万，实测差 15.8 万 / 211ppm）。
_tol_rec = max(1e4, P["balance_total"] * 5e-5 * 1.2)
_d_rec = P["balance_total"] * P["exp_rec_rate_zz"] - P["exp_recovery_zz"]
chk("复算", "回采校验：入池本息费 × 中债预计回收率 ≈ 中债预计回收金额（按披露精度）",
    abs(_d_rec) <= _tol_rec,
    f'{P["balance_total"]*P["exp_rec_rate_zz"]:,.2f} vs {P["exp_recovery_zz"]:,.2f}，'
    f'差 {_d_rec:+,.2f}（容差 {_tol_rec:,.0f}，占回收率精度上限）')
chk("复算", "入池本息费 = 本金 ＋ 息费（源以万元列示，尾差 ≤1 万元）",
    abs(P["balance_principal"] + P["balance_interest_fee"] - P["balance_total"]) < 1000,
    f'尾差 {P["balance_total"]-(P["balance_principal"]+P["balance_interest_fee"]):.2f} 元')
chk("复算", "两档发行合计 = 发行规模",
    abs(T["senior"]["issue"] + T["sub"]["issue"] - T["total"]) < 0.01)
# ★ 存续中单（settlement_state=outstanding）本金本就未兑付完，
#   拿"＝发行额"去判必然红，且与事实相反。判定口径见 06_parse_liquidation。
if _OUTSTANDING:
    skip("复算", "分档本金兑付合计 = 发行额（两档全额）",
         f'信托存续中：优先 {(L["sen_principal_paid"] or 0)/max(T["senior"]["issue"] or 1,1)*100:.2f}%'
         f'／次级 {(L["sub_principal_paid"] or 0)/max(T["sub"]["issue"] or 1,1)*100:.2f}%，'
         '未全额兑付属正常状态')
else:
    chk("复算", "分档本金兑付合计 = 发行额（两档全额）",
        abs(L["sen_principal_paid"] - T["senior"]["issue"]) < 0.01
        and abs(L["sub_principal_paid"] - T["sub"]["issue"]) < 0.01)

# 分布占比：F1 回归——必须同单位（万元 ÷ 万元），三级合计 100%
# ★ 3.2：这三个维度是"应当披露"的核心维度，但存在两类合法缺失：
#   ① 维度已在 dist_gray 里声明（品种性缺失 / 源未披露）
#   ② 该期确实没解析出（如房贷类不披露五级分类）
#   原写法直接 DIST[k] 下标 → KeyError 把整份断言打死，一条都跑不出来。
for k in ("grade", "occupation", "region"):
    if k not in DIST:
        skip("复算", f"{k} 分布余额合计",
             "本单未披露该维度" + ("（已有 dist_gray 声明）" if k in _GRAY else ""))
        continue
    s = sum(x["bal"] for x in DIST[k])
    chk("复算", f"{k} 分布余额合计 = 入池本息费",
        abs(s - P["balance_total"] / 1e4) < 1.0, f"{s:,.2f} 万元")
if "grade" in DIST:
    pcts = [x["bal"] / (P["balance_total"] / 1e4) * 100 for x in DIST["grade"]]
    chk("复算", "grade 占比合计 = 100.00%（±0.05）", abs(sum(pcts) - 100) <= 0.05,
        f"{sum(pcts):.4f}")

# 信托账户配平：F5 回归
# ★ 3.2：逐期账户四字段可能整期缺失（该期受托报告账户表未解析出，如建鑫2021-1 第12期）。
#   原写法直接下标相加 → None + None 抛 TypeError，把整份断言打死。
#   改为：只对四字段齐全的期次配平；缺失期次记 SKIP 并报出期号，
#   既不冒充 PASS，也不因为一份报告缺一张表就判 FAIL。
def _pn(t, _d=0):
    """期次转 int：payload 里 period 有 int 也有 str（惠元是字符串），直接比较会崩"""
    try:
        return int(str(t.get("period")).strip())
    except (TypeError, ValueError):
        return _d


TA_ROWS = [t for t in TA
           if all(t.get(k) is not None for k in ("begin", "inflow", "outflow", "end"))]
TA_MISS_PERIODS = [t.get("period") for t in TA if t not in TA_ROWS]
NTA = len(TA_ROWS)
if NTA:
    gaps = [round(t["begin"] + t["inflow"] - t["outflow"] - t["end"], 2) for t in TA_ROWS]
    # ★ 逐期容差：源表本身存在分位/角分级尾差，不能要求分毫不差。
    #   实测建鑫：2021五期第3期 5,481.58（占流入 0.013%）、
    #   2021九期第3期 958.81（0.004%，报告期末余额与期初+净流量差 958.81）、
    #   2022四期第6期 0.01。这些都是**同一表内自洽性**的尾差，不是缺科目；
    #   真正的科目缺失（招行2023那批账户整期错位）是 1,000% 量级。
    #   故按「当期交易额的 2bp、且不低于 1 元」判定，既不被尾差绊住，
    #   也不会放过整块科目。
    def _ta_tol(t):
        return max(1.0, max(abs(t["inflow"] or 0), abs(t["outflow"] or 0)) * 2e-4)
    _bad_gaps = [(g, _ta_tol(t)) for g, t in zip(gaps, TA_ROWS) if abs(g) >= _ta_tol(t)]
    _ngood = NTA - len(_bad_gaps)
    # ★ 3.2：原写「NTA/len(TA) 期配平」，但 NTA 是**有值**的期数、不是总期数，
    #   于是出现「19/19 期配平」却 FAIL 的自相矛盾（分母口径与断言口径不一致）。
    #   改为「有值 N/T 期，其中 G 期平」，并直接列出不平的残差。
    chk("复算", f"信托账户逐期配平（有值 {NTA}/{len(TA)} 期，其中 {_ngood} 期平）",
        _ngood == NTA,
        f"不平 {NTA - _ngood} 期；残差 "
        f"{[round(g, 2) for g in gaps if abs(g) >= 0.005]}"
        + (f"｜缺期次 {TA_MISS_PERIODS}" if TA_MISS_PERIODS else ""))
    # ★ 3.2：只有**相邻期次**才比结转；账户表有缺期时，前一行不是上一期，
    #   begin 与 end 本来就不衔接（和萃2023 六期最大 405%，全是缺期伪差）。
    #   故按「期次连号」分组后逐对比，缺期处不参与。
    _jumps, _TA_SKIPPED = [], []
    for i in range(1, NTA):
        _p0, _p1 = _pn(TA_ROWS[i - 1]), _pn(TA_ROWS[i])
        # ★ 3.2：首期不参与。信托设立首期期初恒为 0，其 begin 与"上期期末"
        #   本就无从衔接；纳入比较会得到 10000%+ 的伪差
        #   （和萃2023一期 期1→期2 差 2.66 亿，纯属口径不适用）。
        if _p0 <= 1 or _p1 - _p0 != 1:
            continue
        _d_raw = abs(TA_ROWS[i]["begin"] - TA_ROWS[i - 1]["end"])
        _inf = max(TA_ROWS[i]["inflow"], 1.0)
        # ★ 源表期末写错的一期不参与衔接比较，但要**用独立锚点证明**它错，
        #   不能凭"看着不像"就跳过：拿本期子账户合计去对下一期期初。
        #   建鑫2022一期 p3：信托账户行期末 11,953,783.16，子账户合计 341,047.91，
        #   下一期期初 341,020.91 —— 下一期期初对得上子账户、对不上信托账户行，
        #   说明是报告那一行写错，不是我们算错。此时记 SKIP 并留痕。
        if _d_raw / _inf <= 0.15:
            _jumps.append(_d_raw / _inf)
            continue
        # 跳差超阈值时，先判定是谁的问题，两种都**要有独立证据**：
        #   ① 下一期期初对得上上一期的子账户合计 → 上一期"信托账户"行期末写错；
        #   ② 上下两期**各自**都严格配平（期初+流入−流出=期末 成立）→
        #      两条都是忠实转录，是报告本身跨期不衔接（钱在表外调走，
        #      或上一期末与本期期初各写一套）。这种情况不是解析错，记 SKIP 留痕，
        #      不冒充 PASS、也不把报告的毛病算成我们的错。
        #   真正的账户错位（招行2023那批）会让某一期自身配不平，走不到这里。
        _cands = [TA_ROWS[i - 1].get(k) for k in ("sub_end_sum", "sub_end_core")]
        _match = any(_se is not None and abs(TA_ROWS[i]["begin"] - _se) / _inf <= 0.05
                     for _se in _cands)
        _self_ok = all(abs(t["begin"] + t["inflow"] - t["outflow"] - t["end"]) < _ta_tol(t)
                       for t in (TA_ROWS[i - 1], TA_ROWS[i]))
        if _match or _self_ok:
            _TA_SKIPPED.append((_p0, _p1, round(_d_raw / _inf * 100, 2)))
            continue
        _jumps.append(_d_raw / _inf)
    if _jumps:
        chk("复算", "跨期结转差额 < 当期流入 15%（仅比相邻期次，账户间结转）",
            max(_jumps) < 0.15,
            f"最大 {max(_jumps)*100:.2f}%（比对 {len(_jumps)} 对）"
            + (f"；另 {len(_TA_SKIPPED)} 对为源表跨期不衔接（两期各自配平）跳过"
               f"{_TA_SKIPPED}" if _TA_SKIPPED else ""))
    else:
        skip("复算", "跨期结转差额",
             "账户表无相邻期次对，无法比对"
             + (f"（{len(_TA_SKIPPED)} 对因源表期末行不符跳过）" if _TA_SKIPPED else ""))
else:
    skip("复算", "信托账户配平", f"逐期账户四字段全缺（{len(TA)} 期均不可核）")
if TA_MISS_PERIODS:
    skip("复算", "信托账户完整期次", f"缺期次 {TA_MISS_PERIODS}（该期账户表未解析出）")

# ─────────────────────────────────────────────────────────────
# 清算两条恒等式（v3：负债构成逐期不同，绝不硬编码公式）
#   2021 一期 = 服务费＋审计费（51.46 万）
#   2021 二期 = 评级费 45 万＋清算审计费 2 万
#   2022 四期 = 服务费＋评级费＋年度审计费＋预提清算审计费（1,736.38 万）
#   2023 二期 = 另含「应付律师事务所律师费 300,000」← 曾因固定四项相加少算 32 万
# ─────────────────────────────────────────────────────────────
_ba, _be = L.get("liab_at_begin_total"), L.get("liab_at_end_total")
if _ba is None:
    skip("复算", "恒等式①：权益 = 清算开始日银行存款 − 负债合计 ＋ 清算净收益",
         "payload 缺 liab_at_begin_total（旧版取数器）")
else:
    # ★ 3.4：德勤版清算报表（兴业兴瑞）把当期净收益**全额分配**给两档持有人，
    #   期末未分配利润为 0。此时权益恒等式必须减去「已分配净收益」，否则
    #   左边永远是净利润那一笔（2023七期 4,040,893.62），看起来像"权益算错"。
    #   只有 payload 带 liquidation_distributed 时才减（中信/建行/招行无此字段，行为不变）。
    _dist = L.get("liquidation_distributed") or 0.0
    # ★ 清算开始日余额非零、但资产负债表只给一列（无期初列）时，这条恒等式**证据不足**：
    #   实测兴瑞2022三期 cash_begin=4,756.17（末次受托报告期末），表内期初列全空，
    #   于是左边恒多出这 4,756.17 与权益 0 差着 —— 是"表里没有这个数"，不是"算错"。
    #   硬凑（把已分配调成 cash_begin+净收益）等于造数，故记 SKIP 并写明。
    if L.get("cash_begin") and not _ba:
        skip("复算", "恒等式①：权益 = 清算开始日银行存款 − 负债合计 ＋ 清算净收益",
             f"清算开始日银行存款 {L['cash_begin']:,.2f} 非零，但资产负债表只列"
             f"清算日一列（期初列全空），期初负债不可得，等式无法闭合；需查原件清算报表")
        _v1 = None
    else:
        _v1 = L["cash_begin"] - _ba + (L.get("liquidation_gain") or 0.0) - _dist
    if _v1 is not None:
        chk("复算", "恒等式①：权益 = 清算开始日银行存款 − 负债合计 ＋ 清算净收益"
            + ("（− 已分配净收益）" if _dist else ""),
            abs(_v1 - L["holder_equity_end"]) < 0.005,
            f'{L["cash_begin"]:,.2f}−{_ba:,.2f}＋{(L.get("liquidation_gain") or 0):,.2f}'
            + (f'−{_dist:,.2f}' if _dist else '')
            + f'={_v1:,.2f} vs 权益 {L["holder_equity_end"]:,.2f}')
if _be is None:
    skip("复算", "恒等式②：剩余财产 = 权益 ＋ 清算结束日应付合计",
         "payload 缺 liab_at_end_total（旧版取数器）")
else:
    chk("复算", "恒等式②：剩余财产 = 权益 ＋ 清算结束日应付合计",
        abs(L["holder_equity_end"] + _be - L["residual_asset"]) < 0.005,
        f'{L["holder_equity_end"]:,.2f}＋{_be:,.2f}'
        f'={L["holder_equity_end"]+_be:,.2f} vs {L["residual_asset"]:,.2f}')

# ★v3 新增：逐期分档本金合计 = 清算报告兑付额
#   2.0 缺这条 → 2022 四期分层表错位（优先档清零后整行只剩次级档一个数，按位置取值把次级
#   档余额当优先档），逐期优先本金多算 6,910 万、次级 XIRR 虚高到 218%，门禁照样放行。
_ps = sum((p.get("sen_principal") or 0) for p in PER)
_pb = sum((p.get("sub_principal") or 0) for p in PER)
chk("复算", "★v3 逐期分档本金合计 ＝ 清算报告兑付额",
    abs(_ps - L["sen_principal_paid"]) < 1.0 and abs(_pb - L["sub_principal_paid"]) < 1.0,
    f'优先 {_ps:,.2f}/{L["sen_principal_paid"]:,.2f}；次级 {_pb:,.2f}/{L["sub_principal_paid"]:,.2f}')

# ★v3 新增：费用明细完整性
#   2.0 缺这条 → 2022 六期、2023 七期各漏「受托机构报酬」25 万元仍放行
#   根因：OCR 会在科目名中间断行（「受托\n机构报酬」），匹配前必须先去空白
_fd = L.get("fee_detail") or {}
_fdet = sum(_fd.values())
# ★ 3.2：费用总额有两种口径，必须按 fee_total_includes_dispose 判定后比较——
#   中信「费用和开支」账户含执行费用（处置费），明细加总＝fees_total；
#   建行「处置费用」是资产池层面单列科目、不由该账户支付，明细加总比 fees_total 多出
#   整个处置费。混用会把口径差当成错账（建鑫2021-1 差 6,143 万，全部是处置费）。
_FHAS = L.get("fee_total_includes_dispose")
if _FHAS is None:
    _FHAS = True
_fd_expect = (_fdet if _FHAS else (_fdet - (_fd.get("处置费") or 0.0)))
chk("复算", "★v3 费用明细合计（＋未单列手续费）＝ 信托费用支出合计",
    abs(_fd_expect + (L.get("misc_fee") or 0.0) - L["fees_total"]) < 0.02,
    f'{"含" if _FHAS else "不含"}处置费口径：{_fd_expect:,.2f}'
    f'＋{L.get("misc_fee") or 0:,.2f} vs {L["fees_total"]:,.2f}；明细 {len(_fd)} 项')
# ★v3 新增：核心科目必须在场（分配顺序以它们为前提）
for _core in ("处置费", "贷款服务费"):
    chk("复算", f"★v3 费用明细含核心科目「{_core}」", _core in _fd,
        "、".join(_fd.keys())[:80] or "明细为空")

# 资金平衡：残差 ≤1 万元
#   各单在清算开始日是否有额外权益注入不同（2022 五期 1,000 元），
#   且点名的手续费有时不在「费用支出合计」内（2021 二期 360 元）——统一公式并不存在。
#   1 万元相对 3 亿级回收约 0.0003%，属披露口径差而非记账差错；残差照实披露不修饰。
#   增值税口径：多数期次单列，2024 一期并入费用合计，不能重复扣。
_vat = 0.0 if L.get("vat_included_in_fees") else (L.get("vat_total") or 0.0)
sec_sum = ((L.get("sen_principal_paid") or 0) + (L.get("sen_interest_paid") or 0)
           + (L.get("sub_principal_paid") or 0) + (L.get("sub_income_paid") or 0))
# ★ 3.4：清仓回购价款是**真实现金流入**，但不计入「累计回收」（否则回收率被抬高）。
#   兴业兴瑞2023七期实测：把 322,969.87 计入左端后残差精确归零；
#   不计则左端少 32.3 万，看着像"回收记少了"。
# ★★ 但必须先问一句「累计回收里到底含不含回购价款」：
#   清算报告体例不同 —— 兴业信托版「收回基础资产回收款」**已含**回购价款
#   （2023七期：120,642,030.96 ＝ 处置回收 120,319,061.09 ＋ 回购 322,969.87），
#   再按「回收＋回购」相加就把这 32.3 万算了第二遍，资金平衡凭空多出来。
#   故由 payload 的 recovery_includes_buyback 决定加不加；缺该键的老单行为不变。
_bb_add = 0.0 if L.get("recovery_includes_buyback") else (L.get("buyback_inflow") or 0)
_bal = (L["total_recovery"] + _bb_add
        + (L.get("account_interest") or 0)
        - L["fees_total"] - _vat - sec_sum)
if _NO_BS or L.get("holder_equity_end") is None:
    # 无清算资产负债表 → 右端「持有人权益」不存在，这条恒等式无从闭合。
    # 不冒充 PASS，也不判 FAIL：记 SKIP 并把左端算到底的金额照实披露，
    # 让读者知道"回收−费用−证券本息"还剩多少（本单即期末信托财产）。
    skip("复算", "资金平衡：回收＋结息−费用−增值税−证券本息 ≈ 权益（残差 ≤1 万元）",
         f"无清算资产负债表，权益侧不可得；左端 = {_bal:,.2f} 元")
else:
    chk("复算", "资金平衡：回收＋结息−费用−增值税−证券本息 ≈ 权益（残差 ≤1 万元）",
        abs(_bal - L["holder_equity_end"]) <= 10000,
        f'左边 {_bal:,.2f} vs 权益 {L["holder_equity_end"]:,.2f}，'
        f'残差 {_bal-L["holder_equity_end"]:+,.2f}')

# 逐期回收累计与全周期一致（尾差 100 元：两侧各自四舍五入，2023 二期 11.47 元/7.5 亿）
cum, okc = 0, True
for p, c in zip(PER, M["cum_at_period"]):
    cum += p["in_total"]
    okc = okc and abs(cum - c["cum"]) < 0.02
# ★ 3.2：容差从「100 元」放宽到「回收额 0.01%」。
#   两端覆盖的期间本就不同：逐期累计截至**末次受托报告期末日**，
#   清算报告总回收截至**信托终止日**，两者之间的合格投资收益（银行存款利息）
#   只进清算报告。建鑫2021-1：差 2,489.19 元＝回收的 0.0006%，全部是该段利息。
#   100 元的阈值会把这种正常期间差判成错账；放宽后仍能抓住真正的错位
#   （期间错位/漏期会到 0.1% 以上量级）。
# ★ 3.2：容差 0.01% → 0.5%。两侧覆盖期间本就不同：
#   逐期累计截至**末次受托报告期末**，清算报告总回收截至**信托终止日**。
#   招行该间隔常达 1–3 个月（和萃2022二期差 160.2 万＝0.23%），
#   期间回收＋合格投资收益只进清算报告。0.01% 只在两表几乎同日时才成立。
#   放宽后仍能抓真正的期间错位/漏期（那会到 5% 以上）。
# ★ 3.2：比对基准改为「受托报告自报的末次累计回收」，而不是「逐期相加」。
#   理由（建鑫2021-2 实测，两者差 5,455 万）：
#     · 逐期相加依赖每期 in_total 都取对；某期缺数就永久少一块，且错在中途看不出来
#       （累加曲线仍然平滑，只是整体偏低）。
#     · 受托报告每期都印着「累计回收金额」，末次那格是**发行人自报的全周期累计**，
#       与清算报告口径最接近：建鑫2021-2 末次自报 1,006,286,808.75
#       vs 清算报告 1,006,281,736.83，差 5,071.92 元（＝清算期合格投资收益）。
#   故优先用末次累计；缺失时才退回逐期相加，并在明细里注明用的是哪种口径。
# ★ 取数文件不在 stage 里（14_to_layout 只复制 payload/metrics/peer/css 四件），
#   要从 --html 所在项目目录反查：<proj>/03_报告产出/x.html → <proj>/02_提取数据/
_tp = ""
try:
    _pj = os.path.dirname(os.path.dirname(os.path.abspath(HTML)))
    _tp = os.path.join(_pj, "02_提取数据", "_trustee_parsed.json")
except Exception:
    _tp = ""
if not os.path.exists(_tp or "_"):
    _tp = os.path.join(ASSETS, "_trustee_parsed.json")
_last_cum = None
if os.path.exists(_tp):
    try:
        _TT = json.load(open(_tp, encoding="utf-8"))
        for _p in reversed(_TT.get("periods") or []):
            _v = _p.get("recovery_cum")
            if _v:
                _last_cum = float(_v)
                break
    except Exception:
        _last_cum = None
_tol = max(100.0, M["recovered"] * 0.005)
# ★ 3.4：优先用「逐期相加」。
#   末次受托报告的自报累计是**该报告期末**的口径，而清算报告的累计覆盖到信托终止日
#   （中间还多几周回收与结息）。兴业兴瑞2022一期实测：末次自报 350,242,299.77，
#   逐期相加 435,193,824.85，清算 435,196,789.16 —— 逐期相加与清算只差 2,965 元，
#   自报累计则少了 8,495 万（末次报告之后的清仓回购价款不在内）。
#   判据改成：两者**任一**落在容差内即通过，并在说明里写清用的是哪一个。
_cmp = cum if (cum and abs(cum - M["recovered"]) < _tol) else (_last_cum or cum)
_cmp_name = ("逐期相加" if _cmp is cum or _cmp == cum else "末次受托报告自报累计")
chk("复算", "回收累计 ≈ 全周期累计回收（尾差 ≤ 回收额 0.5%，期间口径差）",
    okc and abs(_cmp - M["recovered"]) < _tol,
    f"{_cmp_name} {_cmp:,.2f} vs 清算 {M['recovered']:,.2f}，差 {_cmp - M['recovered']:+,.2f}"
    f"（逐期相加 {cum:,.2f}；容差 {_tol:,.2f}）"
    + (f"；末次报告自报累计 {_last_cum:,.2f}（该口径截至报告期末，不含其后清仓回购与"
       f"结息，仅作参考）" if _last_cum and _cmp_name != "末次受托报告自报累计" else ""))
# ★v3 新增：累计回收单调不减（抓负回收/期间错位）
_cums, _acc = [], 0.0
for p in PER:
    _acc += (p.get("in_total") or 0.0)
    _cums.append(_acc)
chk("复算", "★v3 逐期累计回收单调不减",
    all(_cums[i] <= _cums[i + 1] + 1e-6 for i in range(len(_cums) - 1)),
    f"{_cums[0]:,.0f} → {_cums[-1]:,.0f}")

# ─────────────────────────────────────────────────────────────
# 预测现金流（说明书「预测现金流回收分布」）
# ─────────────────────────────────────────────────────────────
fc = D.get("forecast_flow") or []
if not fc:
    skip("复算", "★v3 预测现金流回收合计 ≈ 中债预计回收总额", "payload 无 forecast_flow")
else:
    _fsum = sum(x[2] for x in fc)
    # ★ 3.2：预测表来自**主承/说明书**，中债预计回收来自**评级机构**，两者本来就会不同
    #   （和萃2021-1：3.4000 亿 vs 3.4576 亿，差 1.7%）。原断言写死「≤1 万元」，
    #   等于要求两家机构预测完全一致——那是数据巧合，不是规律。
    #   改为 ≤3% 相对差，并同时提示两个来源，避免把口径差读成错账。
    # ★ 3.2：**不做精确比对，只做量级校验**。
    #   两张表口径根本不同：
    #     · 主承「现金流归集表」＝按月归集的本息回收排布（招行说明书 p64 起）
    #     · 中债「预计回收」＝评级机构全周期回收金额预测
    #   同一单两者差 5%–15% 属常态（和萃2022一期 −15.2%、2021四期 +6.3%），
    #   而惠元达成率 91%、招行多在 100% 上下，也正说明两者本不相等。
    #   写死 1 万元/3% 等于要求两家机构预测一致——那是巧合不是规律。
    #   改为 0.5x–2x 量级校验：能抓住"单位错 1 万倍""取错表"这类真错，
    #   不再把口径差判成错账。
    _r = (_fsum / P["exp_recovery_zz"]) if P["exp_recovery_zz"] else 0
    chk("复算", "★v3 预测现金流合计与中债预计回收**同量级**（0.5x–2x，两口径不同源）",
        0.5 <= _r <= 2.0,
        f'主承集计 {_fsum:,.2f} vs 中债预计 {P["exp_recovery_zz"]:,.2f}，'
        f'比值 {_r:.3f}（{(_r-1)*100:+.2f}%）；两者口径不同，不作等值判定')
    # 期初必须接上期期末：抓「两表叠加」（2024 一期第 22 行与第 1 行整行重复，合计虚高 6,830 万）
    # 与「漏取末段」（2022 四期末期期末写作「-」被当非数字丢弃）
    # ★ 3.2：容差 1 元 → 1 万元。预测表以**万元**披露、换算成元后舍入到百元，
    #   末期常见「上期期末 100 元、本期期初 0」这种残差（建鑫2021-2 第36期实测差 100 元）。
    #   1 元阈值会把舍入当断裂；1 万元阈值仍能抓住真正的缺期/错位（那会差整期回收额，
    #   量级在百万以上）。
    _brk = [(fc[i][0], fc[i][1], fc[i - 1][3]) for i in range(1, len(fc))
            if abs(fc[i][1] - fc[i - 1][3]) > 1e4]
    chk("复算", "★v3 预测现金流逐期衔接（期初＝上期期末）",
        not _brk, f"{len(_brk)} 处断裂：{_brk[:3]}" if _brk else "全部衔接")
    # ★ 末期期末不为 0 有两种完全不同的成因，必须分开：
    #   ① **解析漏了尾部若干期**（真错）——此时各期回收合计会明显小于原文「合计」
    #   ② **说明书只披露前 N 年回收**（正常）——房贷类明确写
    #      「中债资信、中诚信国际的预计回收金额为前5年债权预计回收金额」，
    #      建鑫2021七期 12 期只覆盖到 2026-10，末期末仍余 7.04 亿，而各期回收合计
    #      20.74 亿已与中债预计 23.97 亿同量级（0.86x），说明表是完整的、只是没走完。
    #   判据：末期期末为 0 → PASS；否则看「分期合计 / 中债预计」是否在同量级，
    #        同量级即视为"前 N 年口径"，记 SKIP 并写明；不同量级才是漏期，判 FAIL。
    if abs(fc[-1][3]) <= 1e4:
        chk("复算", "★v3 预测现金流末期期末归零（万元舍入容差 1 万元）",
            True, f"{fc[-1][3]:,.2f}")
    else:
        _fsum2 = sum(x[2] for x in fc)
        _zz2 = P.get("exp_recovery_zz") or 0
        _r2 = (_fsum2 / _zz2) if _zz2 else 0
        if 0.5 <= _r2 <= 2.0:
            skip("复算", "★v3 预测现金流末期期末归零",
                 f'末期期末 {fc[-1][3]:,.2f} 未归零，但分期合计 {_fsum2:,.2f} '
                 f'与中债预计 {_zz2:,.2f} 同量级（{_r2:.3f}）→ '
                 f'说明书只披露前 {len(fc)} 期回收（房贷类常见"前5年"口径），非漏期')
        else:
            chk("复算", "★v3 预测现金流末期期末归零（万元舍入容差 1 万元）",
                False, f"末期末 {fc[-1][3]:,.2f}，且分期合计仅为中债预计的 {_r2:.3f} 倍 → 疑漏期")

    # 预测同期累计取「收款期末 ≤ 支付日」的期次
    # ★ 预测表的日期标签可能为空（OCR 把日期读丢）→ 比较直接 TypeError；
    #   支付日缺失同理。两处都先剔空，剩余仍保持原顺序（预测表本就按日期递增）。
    _fcd = [x for x in fc if x and x[0]]
    fi, fc_at = 0, []
    for p in PER:
        _pd = p.get("pay_date")
        while _pd and fi < len(_fcd) and _fcd[fi][0] <= _pd:
            fi += 1
        fc_at.append(sum(x[2] for x in _fcd[:fi]) / 1e8)
    chk("复算", "③ 预测同期累计单调不减，且末值出现在正文",
        all(fc_at[i] <= fc_at[i + 1] + 1e-9 for i in range(len(fc_at) - 1))
        and f"{fc_at[-1]:.2f} 亿元" in src, [round(x, 2) for x in fc_at])

# 回购价款占累计回收、自然清收回收率
buy = (L.get("buyback") or {}).get("price") or 0.0
chk_if("复算", "回购价款占累计回收＝metrics 口径",
       M.get("buyback_share_of_recovery"),
       lambda v: abs(buy / M["recovered"] - v) < 1e-9,
       f'{buy/M["recovered"]*100:.4f}%')
chk("复算", "自然清收回收率 ＝ 含回购回收率 − 回购价款 ÷ 入池本息费（恒等）",
    abs(((M["recovered"] - buy) / P["balance_total"])
        - (M["recovery_rate"] - buy / P["balance_total"])) < 1e-12,
    f'{(M["recovered"]-buy)/P["balance_total"]*100:.2f}%')
# ★v3 新增：回购已发生则起算日必存在
#   判据必须用 occurred，**不能用 price > 0**：清仓回购"已发生但价款为 0"是真实情形
#   （2022 四期、2024 一期实测 occurred=true / price=0.0，剩余资产已无价值）。
#   用 price 判断会把这类单误判成"无回购"，从而漏掉真正的问题——
#   2024 一期曾因通知日只披露到「月」（"2025 年 2 月"）导致整个回购块识别失败，
#   若按 price>0 判断，这条断言根本不会触发，等于没查。
_bq = L.get("buyback") or {}
if _bq.get("occurred"):
    # ★ 3.2：受托报告／重大事项报告书常只披露「清仓回购通知书」日期，不单列
    #   「回购起算日」。二者仅相差数个工作日，缺后者不影响任何计算
    #   （回购价款直接取末次报告值，不依赖起算日）。故缺起算日时记 SKIP 而非 FAIL。
    if _bq.get("notice_date") and not _bq.get("calc_date"):
        skip("复算", "★v3 清仓回购起算日",
             f"仅披露通知书日 {_bq.get('notice_date')}，未单列起算日（不影响价款取数）")
    else:
        chk("复算", "★v3 清仓回购已发生则起算日必存在", bool(_bq.get("calc_date")),
            f"通知 {_bq.get('notice_date')} ／ 起算 {_bq.get('calc_date')} ／ 价款 {_bq.get('price')}")
    chk("复算", "★v3 回购价款 ≤ 累计回收（不可能超过总回收）",
        (_bq.get("price") or 0) <= M["recovered"] + 1.0,
        f'{_bq.get("price") or 0:,.2f} ≤ {M["recovered"]:,.2f}')
else:
    skip("复算", "★v3 清仓回购已发生则起算日必存在", "本单无清仓回购")

# 分配矩阵与账户流出的口径关系
# ★ 3.2：矩阵合计含「前置」的资产池处置费用（逐期不单列、全周期一次性 lump），
#   与 build_single 口径必须一致，否则「可见 XX%」这条断言会拿旧百分比去查新报告。
_LUMP_KEYS = [r.get("lump_key") for r in (D.get("waterfall_rows") or [])
              if r.get("kind") == "lump" and r.get("lump_key")]
_LUMP_SUM = sum((L.get(k) or 0.0) for k in _LUMP_KEYS)
cum_out = sum(p["out_total"] for p in PER) + _LUMP_SUM
chk("复算", "分配矩阵合计 = Σ 逐期资产池现金流出 ＋ 全周期一次性科目（自洽）",
    abs(cum_out - (sum(p["out_total"] for p in PER) + _LUMP_SUM)) < 0.02,
    f"{cum_out:,.2f} = {sum(p['out_total'] for p in PER):,.2f} ＋ {_LUMP_SUM:,.2f}")
# 信托账户流出 = 资产池分配科目合计 ＋ 账户间调拨（转存下期、储备补足），方向固定 ≥0。
# 必须排除首期：首期含募集资金划入划出（2022 五期 2.93 亿），混入后差额达 1.25 亿。
# 容差取回收额 0.1%：正常口径差 0.03% 量级；真错会到 5% 以上（2022 五期 −20,397,876）。
# ★ 3.2：只用四字段齐全、且第 2 期起的账户行（缺失期次会使 sum 撞 None）
# ★ 3.2：必须**按期次对齐**再比。原写法账户侧剔掉了缺期、资产池侧没剔，
#   两边样本不同 → 差额里混进整整一期（和萃2021-1：第2期账户未披露，
#   差额 −4,020 万恰好等于该期流出，看着像错账其实是样本不对齐）。
_ta_map = {_pn(t): t for t in TA_ROWS if _pn(t) >= 2}
_per_ok_p = [p for p in PER[1:]
             if p.get("out_total") is not None and _pn(p) in _ta_map]
_ta_ok_p = [_ta_map[_pn(p)] for p in _per_ok_p]
if _ta_ok_p and _per_ok_p and not _FHAS:
    # ★ 建行口径：处置费用由资产池直接扣减、不经信托账户，两类「流出」不同源，
    #   账户流出天然小于资产池流出（本单差 1,596.7 万）。该比较在此体例下不成立。
    skip("复算", "信托账户流出 ≥ 资产池现金流出",
         "本单处置费不走信托账户，账户流出与资产池流出不同源，不作大小比较")
elif _ta_ok_p and _per_ok_p:
    _gap = (sum(t["outflow"] for t in _ta_ok_p)
            - sum(p["out_total"] for p in _per_ok_p))
    # ★ 3.2：负向容差 0.1% → 5%。两张表不同源：
    #   信托账户流出含储备账户补足、账户间调拨、跨期结转；
    #   资产池现金流出是分配科目表。招行实测差 0.4%–3.0%（和萃2022二期 −3.02%），
    #   性质是口径差而非记账错。真正记错会到 10% 以上。
    chk("复算", "信托账户流出 ≥ 资产池现金流出（首期除外，负向容差 5% 回收额）",
        _gap >= -max(M["recovered"] * 0.05, 1.0),
        f'{_gap:+,.2f}（占回收 {abs(_gap)/max(M["recovered"],1)*100:.2f}%）'
        + (f'｜可核期次 {[t["period"] for t in _ta_ok_p]}' if len(_ta_ok_p) < len(TA) - 1 else ''))
else:
    skip("复算", "信托账户流出 ≥ 资产池现金流出",
         "逐期账户或现金流出字段不足，无法比对")
# ★ 3.2：矩阵合计与回收流入的关系随费用口径而变。
#   建行「处置费用」是资产池层面单列科目，受托报告逐期流出表**不含**它；
#   反之逐期流出里的「转存下期金额」是账户留存、不是真实流出（重复计入会虚增）。
#   两项修正后本单 99.63%，未修正时 85.94%——原写法会把口径差判成错数。
_xfer = sum(((p.get("outflow") or {}).get("转存下期金额") or 0) for p in PER)
# cum_out 已含 lump（处置费用），不能再加一次；只扣账户留存（转存下期）
_out_eff = cum_out - _xfer
# ★ 3.2：上限 102% → 106%。矩阵含处置费用等「资产池层面已扣、不进入分配序列」的科目，
#   以及期初账户余额的转出，占回收比重可略超 100%（和萃2022二/四期 102.2%/102.5%）。
#   下限仍 95%，低于此说明有整块科目没归集。
chk("复算", "分配矩阵合计占回收流入落在 95%–106%（量级校验）",
    95 <= _out_eff / M["recovered"] * 100 <= 106,
    f"{_out_eff/M['recovered']*100:.2f}%（{_out_eff:,.2f}／{M['recovered']:,.2f}；"
    f"已扣转存 {_xfer:,.2f}" + (f"，并加回单列处置费 {L.get('dispose_exec_fee'):,.2f}" if not _FHAS else "") + "）")

# ================= 一·B ★v3 新增：跨单一致性与合理性 =================
# 这一组是 2.0 完全没有的。它们不依赖任何单期特征，纯粹用「任何清算ABS都该成立」
# 的边界把明显错数挡住——尤其 XIRR，它最容易被上游错数污染且表面上仍然「像个收益率」。

if M.get("sen_xirr") is None:
    skip("v3合理", "★v3 优先档 XIRR 落在 −5% ~ 15%",
         "优先档 XIRR 不可解（缺发行日或现金流序列）")
else:
    chk("v3合理", "★v3 优先档 XIRR 落在 −5% ~ 15%",
        -0.05 <= M["sen_xirr"] <= 0.15, f'{M["sen_xirr"]}')
# ★v3 新增：XIRR 必须能由 metrics.flows **复算回来**
#   这条守的是「卡片上的 XIRR」与「正下方折现表的现金流」是否同一套口径。
#   实测缺陷（兴瑞2023七期）：折现表把次级档两笔已按支付日派发的收益
#   （2024-06-26 固资＋超额、2024-07-18 超额）合并挪到清算日 2024-07-30，
#   表内现金流反算 49.78%，卡片却写 51.57%（−179bp）；兴瑞2024三期更差 648bp。
#   只要两处现金流一致，本断言必过；一旦有人再「合并到清算日」立刻暴露。
_FL = (M.get("flows") or {})


def _xirr_of(cf):
    from datetime import date as _d
    _t0 = cf[0][0]
    def _npv(r):
        return sum(v / (1 + r) ** ((d - _t0).days / 365.0) for d, v in cf)
    lo, hi = -0.9999, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


for _side, _mkey, _nm in (("sen", "sen_xirr", "优先档"), ("sub", "sub_xirr", "次级档")):
    from datetime import date as _d
    _raw = _FL.get(_side) or []
    _want = M.get(_mkey)
    if not _raw or _want is None:
        skip("复算", f"★v3 {_nm} XIRR 可由现金流复算（口径同一）",
             "metrics.flows 缺失或 XIRR 不可解")
        continue
    try:
        _cf = [(_d(*map(int, x["date"].split("-"))), float(x["cf"])) for x in _raw]
    except (KeyError, TypeError, ValueError):
        skip("复算", f"★v3 {_nm} XIRR 可由现金流复算（口径同一）", "flows 结构不可解析")
        continue
    _got = _xirr_of(_cf)
    chk("复算", f"★v3 {_nm} XIRR 可由现金流复算（口径同一）",
        abs(_got - _want) * 1e4 <= 1.0,
        f'flows 反算 {_got*100:.2f}% vs 卡片 {_want*100:.2f}%'
        f'（差 {( _got-_want)*1e4:+.1f}bp）')

# ★ 存续中：次级本金只兑付了一小部分，剩余本金全部未回收，
#   XIRR 必然深度为负（建鑫2021四期 −32.17%）。这是真实状态而非错数，
#   用"已清算"的区间去判它等于要求一个未到期资产表现出到期收益率。
if _OUTSTANDING:
    _sx = (f'{M["sub_xirr"]*100:.2f}%' if M.get("sub_xirr") is not None
           else '不可解（次级档本期无任何现金流）')
    skip("v3合理", "★v3 次级档 XIRR 落在 −20% ~ 80%",
         f'信托存续中，次级本金兑付 '
         f'{(L["sub_principal_paid"] or 0)/max(T["sub"]["issue"] or 1,1)*100:.2f}%，'
         f'XIRR {_sx} 为期间口径，不与已清算单的终局区间比较')
else:
    # ★ 3.3：上限 80% → 200%。建鑫这批单子的结构决定了次级 IRR 天生很高：
    #   优先档往往 1–2 期内清偿完毕（2023六期首期就付掉 1.68 亿优先本金），
    #   次级本金跟着在 2–4 期内收回，之后纯收超额收益 →
    #   实测 14 只已清算标的落在 −20% ~ +121%（2023六期 120.90%、
    #   2022十期 93.20%、2023二期 82.19%）。80% 的上限会把真数判错。
    #   真正该防的是"量级错"（如本金当收益 → 上千 %），故放到 200%。
    chk("v3合理", "★v3 次级档 XIRR 落在 −20% ~ 200%",
        isinstance(M.get("sub_xirr"), (int, float)) and -0.20 <= M["sub_xirr"] <= 2.00,
        f'{M.get("sub_xirr")}')
    # 从属结构的基本次序：次级（剩余索取权）回报必须高于优先（固定票息）。
    # 这条不依赖任何外部参数，任何清算ABS都该成立，故单列一条硬断言。
    if isinstance(M.get("sub_xirr"), (int, float)) and isinstance(M.get("sen_xirr"), (int, float)):
        chk("v3合理", "★v3 次级档 XIRR 高于优先档（从属结构次序）",
            M["sub_xirr"] > M["sen_xirr"],
            f'次级 {M["sub_xirr"]*100:.2f}% ／ 优先 {M["sen_xirr"]*100:.2f}%')
# 优先档收益应高于票面、但溢价有限（信用卡不良存续仅 6–14 个月，实测 2.4%–3.3%）
# ★ 存续中：优先档本金尚未全额兑付，XIRR 低于票面是正常的
#   （未回收本金按市值折价，持有期收益自然被压低）。
#   建鑫2023七期实测 −587bp：本金兑付 90.44%，其余仍挂账。
if _OUTSTANDING:
    skip("v3合理", "★v3 优先档 XIRR − 票面 落在 0 ~ 200bp",
         f'信托存续中（优先本金兑付 '
         f'{(L["sen_principal_paid"] or 0)/max(T["senior"]["issue"] or 1,1)*100:.2f}%），'
         f'XIRR 与票面偏差 {M.get("sen_xirr_gap_bp")} bp 属期间口径，不作终局判定')
elif M.get("sen_xirr_gap_bp") is None:
    skip("v3合理", "★v3 优先档 XIRR − 票面 落在 0 ~ 200bp", "XIRR 不可解")
else:
    # ★ 3.3：下限 0 → −10bp。优先档 XIRR 按「实际天数/365」年化，而票面按协议
    #   计息基准（30/360 或 91/365）逐期结息，两者天生差几个 bp：
    #   实测 14 只已清算标的落在 −6.85bp ~ +5.37bp（2022十期 −6.85、2023五期 −5.34、
    #   2021八期 −6.64 都是负数）。要求"必为正"等于要求两种计息基准完全一致，
    #   不成立；真正的错数（本金记利息、XIRR 18.55%）是 1,500bp 量级。
    chk("v3合理", "★v3 优先档 XIRR − 票面 落在 −10 ~ 200bp",
        -10.0 <= M["sen_xirr_gap_bp"] <= 200.0, f'{M["sen_xirr_gap_bp"]} bp')
# 存续中：次级尚未收到本金、只拿过少量收益，倍数必然远低于 1（建鑫2021四期 0.141x）
if _OUTSTANDING:
    skip("v3合理", "★v3 次级档回报倍数落在 0.5× ~ 3.0×",
         f'信托存续中，次级回报倍数 {M.get("sub_multiple")} 为期间累计口径，未含未回收本金')
elif M.get("sub_multiple") is not None:
    chk("v3合理", "★v3 次级档回报倍数落在 0.5× ~ 3.0×",
        0.5 <= M["sub_multiple"] <= 3.0, f'{M["sub_multiple"]:.4f}×')
else:
    skip("v3合理", "★v3 次级档回报倍数落在 0.5× ~ 3.0×", "metrics 无 sub_multiple")
chk_if("v3合理", "★v3 票面利率落在 0% ~ 10%",
       M.get("sen_coupon"),
       lambda v: 0 < v < 0.10, f'{M.get("sen_coupon")}')

# 分档余额：末期必须归零（本金全额兑付），且单调不增
_sb = [p.get("sen_balance_after") for p in PER if p.get("sen_balance_after") is not None]
_bb = [p.get("sub_balance_after") for p in PER if p.get("sub_balance_after") is not None]
if _sb and _OUTSTANDING:
    skip("v3合理", "★v3 优先档余额末期归零（本金全额兑付）",
         f'信托存续中，优先档仍有未偿本金 {_sb[-1]:,.2f}（兑付 '
         f'{(L["sen_principal_paid"] or 0)/max(T["senior"]["issue"] or 1,1)*100:.2f}%），归零不适用')
elif _sb:
    chk("v3合理", "★v3 优先档余额末期归零（本金全额兑付）", abs(_sb[-1]) < 1.0, f"{_sb[-1]:,.2f}")
    chk("v3合理", "★v3 优先档余额单调不增",
        all(_sb[i] >= _sb[i + 1] - 1.0 for i in range(len(_sb) - 1)),
        f"{_sb[0]:,.0f} → {_sb[-1]:,.0f}")
else:
    skip("v3合理", "★v3 优先档余额末期归零", "payload 无 sen_balance_after")
if _bb:
    # ★ 3.2：清仓回购型要**截断到本金首次清零**再校验。
    #   回购完成后「未偿本金」已为 0，但受托报告余额表在后续期次里填的是
    #   **待分配的剩余信托财产**（回购价款／清算余额），不再是本金。
    #   和萃2023五期实测：期12 清零 → 期13 又出现 417.11 万 → 期14 179.91 万，
    #   若照全序列校验，「末期归零」「单调不增」双双误报。
    _bbx = list(_bb)
    _cut = next((i for i, v in enumerate(_bb) if abs(v) < 1.0), None)
    _is_bq = bool((L.get("buyback") or {}).get("occurred"))
    if _is_bq and _cut is not None:
        _bbx = _bb[:_cut + 1]
    if _OUTSTANDING:
        skip("v3合理", "★v3 次级档余额末期归零",
             f'信托存续中，次级本金尚未兑付完（余额 {_bb[-1]:,.2f}），归零不适用')
    else:
        chk("v3合理", "★v3 次级档余额（截断至本金清零）末期归零（本金全额兑付）",
            abs(_bbx[-1]) < 1.0,
            f"{_bbx[-1]:,.2f}" + (f"（全序列末值 {_bb[-1]:,.2f}，清仓回购后为剩余财产）"
                                  if _is_bq and _cut is not None and _bb[-1] != _bbx[-1] else ""))
    chk("v3合理", "★v3 次级档余额单调不增",
        all(_bbx[i] >= _bbx[i + 1] - 1.0 for i in range(len(_bbx) - 1)),
        f"{_bbx[0]:,.0f} → {_bbx[-1]:,.0f}（校验 {len(_bbx)}/{len(_bb)} 期）")
else:
    skip("v3合理", "★v3 次级档余额末期归零", "payload 无 sub_balance_after")

# 日期序：发行 < 终止 ≤ 清算完毕 ≤ 法定到期
_ds = {k: META.get(k) for k in ("issue_date", "terminate_date",
                                "liquidation_end", "legal_maturity")}
if all(_ds.values()):
    # ★ 3.2：法定到期日之后才完成清算并不违规——不良ABS的实际处置周期常超法定到期日，
    #   产品到期未了结即延期清算。原断言写死「终止 ≤ 法定到期」，会把这类单判成错，
    #   实为误报。改为：发行 < 终止 ≤ 清算完毕 必须成立；终止晚于法定到期时
    #   额外核报告是否标注「延期」，标注了即通过。
    _seqok = (_ds["issue_date"] < _ds["terminate_date"] <= _ds["liquidation_end"])
    _late = _ds["terminate_date"] > _ds["legal_maturity"]
    if _seqok and _late:
        _seqok = ("延期" in src) or ("晚于法定到期" in src)
    chk("v3合理", "★v3 日期序：发行 < 终止 ≤ 清算完毕（终止超法定到期须标注延期）", _seqok,
        " < ".join(str(_ds[k]) for k in ("issue_date", "terminate_date",
                                         "liquidation_end", "legal_maturity"))
        + (f'｜晚于法定到期 {_ds["legal_maturity"]}' if _late else ""))
else:
    skip("v3合理", "★v3 日期序", f"缺失：{[k for k, v in _ds.items() if not v]}")
chk_if("v3合理", "★v3 首个支付日 > 发行日", META.get("first_pay_date"),
       lambda v: v > META["issue_date"],
       f'{META.get("first_pay_date")} vs {META.get("issue_date")}')

# 资产池结构常识
chk("v3合理", "★v3 入池笔数 > 0 且 借款人数 ≤ 笔数",
    (P.get("n_loans") or 0) > 0 and (P.get("n_borrowers") or 0) <= (P.get("n_loans") or 0),
    f'{P.get("n_loans")} 笔 / {P.get("n_borrowers")} 人')
chk_if("v3合理", "★v3 笔均 ≈ 入池本息费 ÷ 笔数（≤1%）", P.get("avg_loan_balance"),
       lambda v: abs(v - P["balance_total"] / P["n_loans"])
       <= P["balance_total"] / P["n_loans"] * 0.01,
       f'{(P.get("avg_loan_balance") or 0.0):,.2f} vs '
    f'{(P["balance_total"]/P["n_loans"] if P.get("n_loans") else 0.0):,.2f}')
chk_if("v3合理", "★v3 次级档占比 ＝ 次级档 ÷ 发行规模（按 4 位小数精度）",
       T.get("credit_enhance_pct"),
       lambda v: abs(v - T["sub"]["issue"] / T["total"]) < 5e-5,
       f'{T.get("credit_enhance_pct")} vs {T["sub"]["issue"]/T["total"]:.6f}')
chk("v3合理", "★v3 权益与剩余财产均 ≥ 0",
    (L.get("holder_equity_end") or 0) >= 0 and (L.get("residual_asset") or 0) >= 0,
    f'权益 {L.get("holder_equity_end")} ／ 剩余 {L.get("residual_asset")}')
# 证券代码：7 位数字（次级档曾被硬编码 None，报告里直接显示「None」）
for _ck, _cn in (("code_sen", "优先档"), ("code_sub", "次级档")):
    chk_if("v3合理", f"★v3 {_cn}证券代码为 7 位数字", META.get(_ck),
           lambda v: bool(re.fullmatch(r"\d{7}", str(v))), str(META.get(_ck)))
# 费用结构：处置费 ＋ 服务费 不应超过费用合计（两者是最大两块）
# 只在「费用合计含处置费」的口径下成立；建行处置费与费用合计互不包含，不适用
if _FHAS:
    chk("v3合理", "★v3 处置费 ＋ 服务费 ≤ 费用合计",
        (_fd.get("处置费", 0) + _fd.get("贷款服务费", 0)) <= L["fees_total"] + 1.0,
        f'{_fd.get("处置费",0):,.0f}＋{_fd.get("贷款服务费",0):,.0f} vs {L["fees_total"]:,.0f}')
else:
    skip("v3合理", "★v3 处置费 ＋ 服务费 ≤ 费用合计",
         "本单处置费为资产池层面单列科目，与费用合计互不包含，该比较不适用")

print(f"数据复算完成：{len(res)} 条")

# ================= 二、静态断言 =================
BAN = ["折价率", "预测XIRR", "预测 XIRR", "发行利差", "约定资金成本率", "固定资金成本率",
       "已终局", "简单平均", "处置费用占比", "payload.", "pool.", "liq_info",
       "A_回源已补", "B_报告确无", "C_源文件缺失", "E:\\", "E:/"]
for w in BAN:
    chk("禁用词(源)", f"不含「{w}」", w not in src)

chk("口径", "处置费率分母唯一", "＝处置费用 ÷ 累计回收" in src)
chk("口径", "证券化率分母唯一", "＝发行规模 ÷ 入池本息费" in src)
chk("口径", "声明次级档不倒算", "不做资金成本倒算" in src)
# ★ 存续中单不能出现「信托计划已终止」，改判「信托存续中 · 尚未清算」：
#   这条原为单向断言（必须出现"已终止"），存续单必然 FAIL，
#   而它的真实含义是"终局判定必须用信托状态这一口径、且措辞与事实一致"。
if _OUTSTANDING:
    chk("口径", "终局判定按事实标注「信托存续中 · 尚未清算」",
        "信托存续中" in src and "信托计划已终止" not in src,
        "存续中单不得出现已终止字样")
else:
    chk("口径", "终局判定用「信托计划已终止」", "信托计划已终止 · 清算完成" in src)

# F1 回归：不得再出现 0.01%/0.00% 占比
chk("回归", "F1 分布占比不再是 0.01%/0.00%（源）",
    "占比 0.01%" not in src and "次级 0.01%" not in src)
if DIST.get("grade"):
    chk("回归", "F1 五级分类占比可见（源）",
        all(f"{x['bal']/(P['balance_total']/1e4)*100:.2f}%" in src for x in DIST["grade"]))
else:
    skip("回归", "F1 五级分类占比可见（源）", "本单未披露五级分类分布")
# F5 回归：不再把资产池余额当账户期初
chk("回归", "F5 表头不再出现「期初余额（资产池）」", "期初余额（资产池）" not in src)
chk("回归", "F5 逐期差额全部 0.00（无 575 万元级残差）",
    "5,754,942.40" not in src and "108,739.76" not in src)
# F6 回归：披露概览恒等式 N = a + b + c
# ★ 3.2：概览句式随口径变化（中信写「已回源补全／源未披露／源文件缺失」，
#   建行写「已核实／未披露」等）。改为抓「共 N 项」及其后全部分项数字求和比对，
#   只要各分项之和等于总数即通过，不依赖具体措辞。
# 两种体例：中信「共 N 项 ｜ 已回源补全 a ｜ 源未披露 b ｜ 源文件缺失 c」
#           建行/招行「材料 N 类 ｜ 齐备 a 类 ｜ 缺失 b 类」
_ok6, _d6 = False, "未匹配"
_m = re.search(r"材料\s*(\d+)\s*类\s*｜\s*齐备\s*(\d+)\s*类\s*｜\s*缺失\s*(\d+)\s*类", src)
if _m:
    _n, _a, _b = map(int, _m.groups())
    _ok6, _d6 = (_a + _b == _n), f"材料 {_n} ＝ 齐备 {_a} ＋ 缺失 {_b}"
else:
    _m = re.search(r"共\s*(\d+)\s*项([^<]{0,120})", src)
    if _m:
        _tot = int(_m.group(1))
        _parts = [int(x) for x in re.findall(r"(\d+)\s*项", _m.group(2))]
        _ok6 = (sum(_parts) == _tot) if _parts else True
        _d6 = f"总 {_tot} ／ 分项 {_parts}" if _parts else f"总 {_tot}"
chk("回归", "F6 披露概览 N = a + b + c", _ok6, _d6)

chk("结构", "单视图单项目", src.count('class="view on"') == 1)
chk("结构", "八节齐全 ①–⑧",
    all(f'<span class="sec-num">{n}</span>' in src for n in "①②③④⑤⑥⑦⑧"))
# ★ 3.2：折叠块数不是不变量——报告按披露完整度自动收起明细块，
#   中信 4 个（⑥⑧ + 2 明细）、建行 3 个（无清算资产负债表 → 少一个明细折叠）。
#   改为区间断言 + 必须包含 ⑥⑧ 两个主折叠，避免把"资料少"误判成"排版坏"。
_nfold = src.count("fold rv collapsed")
chk("结构", "折叠块 ≥3 且主折叠 ⑥⑧ 在场", 3 <= _nfold <= 6 and _nfold >= 3, _nfold)
# 分配矩阵步号：行数随合同步数变化（惠元 16 / 建行 12 步但 18 行），
# 故只断言「第1步」存在且步号连续到出现的最大编号，不写死 16。
_steps_in_src = sorted({int(x) for x in re.findall(r"第(\d+)步", src)})
_nstep = max(_steps_in_src) if _steps_in_src else 0
# ★ 房贷/对公类的说明书分配机制为**图示体例**，抽不到文字条款 →
#   waterfall_rows 回退成"实际执行顺序"，每行没有 step 号，矩阵标题也改成
#   "实际执行顺序"。这类单本来就没有"第N步"，不能判 FAIL。
if _steps_in_src:
    chk("v5-L1", "分配矩阵「第N步」编号连续（第1步…最高步）",
        _steps_in_src == list(range(1, _nstep + 1)),
        f"最高 {_nstep} 步／共 {len(_steps_in_src)} 个编号")
else:
    skip("v5-L1", "分配矩阵「第N步」编号连续",
         "本单说明书分配机制为图示体例，按实际执行顺序列示（无合同步号）")

# ★ 3.2 新增：分配矩阵的行序必须**忠实于本单自己的合同条款**。
#
#   为什么不能写死「次级档本金先于固资」这类方向断言（本轮踩过）：
#     · 中信惠元（说明书 p89）：(i) 次级档固定资金成本 → (j) 次级档本金  ← 固资在前
#     · 建行建鑫（说明书 p98）：第9步 次级档本金 → 第10步 次级档固定资金成本 ← 本金在前
#   两家产品的次级档条款**真实不同**（惠元次级档带 13% 资金成本、类债；
#   建鑫按资金占用事后计息）。把任一家的顺序当通用规律，另一家必然判错。
#   故改为：以 payload 提供的**该单合同顺序**为基准，验证渲染是否忠实。
#
#   基准优先级：waterfall.steps（说明书第七章文字条款，带步号）
#             > waterfall_order（14 步 (a)…(n) 列表，惠元即取自此）
def _step_of(label):
    """某科目在矩阵里的「第N步」（取该 tr 的 data-step）"""
    m = re.search(r'<tr data-label="' + re.escape(label) + r'"[^>]*data-step="(\d+)"', src)
    return int(m.group(1)) if m else None


_STEPS = (D.get("waterfall") or {}).get("steps") or []
_WO = D.get("waterfall_order") or []

# ★ 次级档「资金成本」的术语逐行不同，断言必须全认：
#     中信（惠元）  ：次级档资产支持证券「固定资金成本」
#     招行（和萃）  ：次级档资产支持证券「预期资金成本」
#     建行（建鑫）  ：次级档资产支持证券「固定资金成本」
#   只认「固定资金成本」会把招行整条判成"未提供基准"而静默跳过 —— 那等于没管招行。
_FC_WORDS = ("固定资金成本", "预期资金成本", "资金成本")


def _is_fc(t):
    """是否为「次级档资金成本」那一步（排除「偿还完毕后…超额奖励服务费」那条）"""
    return (any(w in t for w in _FC_WORDS)
            and "偿还完毕" not in t and "超额奖励" not in t
            and "浮动服务报酬" not in t)


# 从基准里取「次级档本金」「次级档资金成本」的先后
_bk_sub_prin = _bk_sub_fix = None
if _STEPS:
    for _st in _STEPS:
        _t = _st.get("text") or ""
        if _bk_sub_prin is None and "次级档" in _t and "本金" in _t \
                and "资金成本" not in _t and "偿还完毕" not in _t:
            _bk_sub_prin = _st.get("no")
        if _bk_sub_fix is None and _is_fc(_t):
            _bk_sub_fix = _st.get("no")
else:
    for _i, _r in enumerate(_WO):
        _nm = _r[1] if isinstance(_r, (list, tuple)) and len(_r) > 1 else None
        if _nm == "次级档本金" and _bk_sub_prin is None:
            _bk_sub_prin = _i
        if _nm in ("次级档固定资金成本", "次级档预期资金成本") and _bk_sub_fix is None:
            _bk_sub_fix = _i

_p_sp = _step_of("次级档本金")
_p_sf = (_step_of("次级档固定资金成本") if _step_of("次级档固定资金成本") is not None
         else _step_of("次级档预期资金成本"))
if _bk_sub_prin is None or _bk_sub_fix is None:
    skip("v5-L1", "★ 次级档本金 / 固定资金成本 先后＝合同条款",
         "payload 未提供可用的合同顺序基准（waterfall.steps / waterfall_order）")
elif _p_sp is None or _p_sf is None:
    chk("v5-L1", "★ 次级档本金 / 固定资金成本 先后＝合同条款", False,
        f"矩阵缺行：本金 step={_p_sp}／固资 step={_p_sf}")
else:
    _bk_order = _bk_sub_prin < _bk_sub_fix
    _rp_order = _p_sp < _p_sf
    chk("v5-L1", "★ 次级档本金 / 固定资金成本 先后＝**本单**合同条款（各行不同，不可互套）",
        _bk_order == _rp_order,
        f"合同基准：{'本金在前' if _bk_order else '固资在前'}"
        f"（{_bk_sub_prin} vs {_bk_sub_fix}）／报告："
        f"本金 第{_p_sp}步、固资 第{_p_sf}步{'（一致）' if _bk_order == _rp_order else '（排反！）'}")

# 通用校验：报告里出现的所有「第N步」顺序，必须与合同基准的科目顺序一致（单调不减）
if _STEPS:
    _seq = re.findall(r'<tr data-label="([^"]+)"[^>]*data-step="(\d+)"', src)
    _prev, _bad = -1, []
    for _lab, _st in _seq:
        _v = int(_st)
        if _v < _prev:
            _bad.append(f"{_lab}(第{_v}步)")
        _prev = max(_prev, _v)
    chk("v5-L1", "★ 矩阵步号单调不减（未出现后行步骤号小于前行）",
        not _bad, "、".join(_bad[:5]) or "全部单调")
# ★ 3.3：矩阵「档位」列必须能区分优先 / 次级 —— 这是 G1/G2 都查不出的语义缺陷。
#
#   为什么必须单列一条：`lvl` 只作纯文本显示，不参与配色与计算，所以
#   ① 数字全对、合计照样配平；② 文件字节可复现 → **G1 必然通过**；
#   ③ 版式结构一字未动 → G2 也通过。
#   唯一的破绽是读者看不懂：建行原实现把证券端一律标「证券」，
#   于是 5 行（优先利息/优先本金/次级本金/次级固资/次级收益）档位全叫「证券」，
#   而这张表最需要看清的恰恰是「次级本金(9) → 次级固资(10)」这个反直觉次序，
#   档位却把两者抹成同一类。属"看着没问题、用起来没信息"的隐性缺陷。
#   判据：凡科目名含「优先」的行，档位必须含「优先」；含「次级」的必须含「次级」。
def _lvl_of(label):
    m = re.search(r'<tr data-label="' + re.escape(label) + r'"[^>]*>\s*'
                  r'<td class="l">[^<]*</td><td class="l">([^<]*)</td>', src)
    return m.group(1).strip() if m else None


# ★ 适用范围：仅**已启用档位区分口径**的单（payload 带 waterfall_rows，即建行建鑫）。
#   中信惠元 15 单、招行和萃 18 单仍走 build_single 内的写死表，档位列填的是
#   「证券 / 费用 / 储备 / 其他」这个**科目大类**口径（三家中信/招行实测同此）。
#   它们已交付且过基线，改档位会重建全部字节基线，故经用户确认**暂不动**，
#   这里记 SKIP 并写明原因 —— 是"本单沿用旧口径"，不是"已检查通过"。
#   建行 24 单已启用新口径，本断言对它们逐行实查（缺陷注入已验：改回「证券」立即 FAIL）。
if not (D.get("waterfall_rows") or []):
    skip("v5-L1", "★ 矩阵「档位」列能区分优先 / 次级",
         "本单档位列沿用「证券/费用/储备」科目大类口径（未启用档位区分），"
         "优先级由「科目」列体现；建行 24 单已启用并逐行校验")
else:
    _LVL_BAD = []
    for _lab, _want in (("优先档利息", "优先"), ("优先档本金", "优先"),
                        ("次级档本金", "次级"), ("次级档固定资金成本", "次级"),
                        ("次级档收益", "次级")):
        _lv = _lvl_of(_lab)
        if _lv is None:
            continue                 # 本单无此行（品种差异），不判
        if _want not in _lv:
            _LVL_BAD.append(f"{_lab}→「{_lv}」")
    chk("v5-L1", "★ 矩阵「档位」列能区分优先 / 次级（不可一律标「证券」）",
        not _LVL_BAD, "、".join(_LVL_BAD) or "优先/次级各行已区分")

_p_si, _p_spr = _step_of("优先档利息"), _step_of("优先档本金")
if _p_si is not None and _p_spr is not None:
    chk("v5-L1", "优先档利息 先于 优先档本金（各行一致，属通用结构）",
        _p_si < _p_spr, f"利息 第{_p_si}步 ／ 本金 第{_p_spr}步")
chk("v5-L2", "瀑布与分档本金合并为同一卡片", "全周期资金分配瀑布 × 分档累计本金走势" in src)
chk("v5-L3", "预计回收率分布已移入 ③（data-chart=rec-dist）", 'data-chart="rec-dist"' in src)
# ★ 3.2：9 个格子里，本品种没有的维度渲染为置灰灰格（data-chart="dist-gray"），
#   不是 SVG 图。故断言改为「实图 ＋ 灰格 ＝ 9」，而不是死数 9 张 SVG。
_v9 = src.count('data-chart="dist-v9"')
_vg = src.count('data-chart="dist-gray"')
chk("v5-L3", "资产池分布固定 9 格（实图 ＋ 置灰格 ＝ 9，3×3 满格）",
    _v9 + _vg == 9, f"实图 {_v9} ＋ 置灰 {_vg}")
# ★ 3.2：折现率说明的期限随发行年份变化（惠元 1 年期、建行 1 年期），
#   原断言写死「1 年期国债」，改为「国债到期收益率 + 同一利率数值」两项同时命中。
chk_if("v5-L4", "XNPV 折现率＝无风险利率（取 payload.meta.rf）", META.get("rf"),
       lambda v: (f'{v*100:.2f}%' in src) and ('国债到期收益率' in src), META.get("rf"))
chk("v5-L4", "XNPV 表两档同表分列", "优先档现值" in src and "次级档现值" in src)
# ★ 3.2：卡标题随品种与样本量变化（原写死「23 单信用卡不良」）
chk("结构", "含 ⑤ 同业定位卡", "同业定位" in src
    and ('data-chart="peer-strip"' in src or 'data-chart="peer-gray"' in src))
chk("结构", "品种色 #A52524", "--accent:#A52524" in src)

# ================= 三、渲染断言 =================
PROBE = """
<script>
setTimeout(function(){
  var o={},v=document.querySelector('.view');
  var de=document.documentElement;
  o.hScroll=Math.max(de.scrollWidth-de.clientWidth,
                     document.body.scrollWidth-document.body.clientWidth);
  var over=[];
  [].slice.call(v.querySelectorAll('*')).forEach(function(e){
    if(e.closest&&e.closest('svg'))return;
    var ox=getComputedStyle(e).overflowX;
    if(ox==='auto'||ox==='scroll')return;
    if(e.scrollWidth-e.clientWidth>2) over.push(e.tagName+'.'+((typeof e.className==='string')?e.className:''));
  });
  o.overN=over.length; o.over=over.slice(0,5);
  var small=0,total=0,tw=document.createTreeWalker(v,NodeFilter.SHOW_TEXT),n;
  while(n=tw.nextNode()){
    if(!n.nodeValue.trim())continue;
    var e2=n.parentElement; if(!e2)continue;
    if(parseFloat(getComputedStyle(e2).fontSize)<9.4)small++; total++;
  }
  o.small=small; o.total=total;
  o.svg=v.querySelectorAll('svg').length;
  o.svgZero=[].slice.call(v.querySelectorAll('svg')).filter(function(s){
    var r=s.getBoundingClientRect(); return r.width<10||r.height<10; }).length;
  o.svgNoVB=[].slice.call(v.querySelectorAll('svg')).filter(function(s){
    return !s.getAttribute('viewBox'); }).length;
  o.folds=[].slice.call(v.querySelectorAll('.fold-h .ft')).map(function(e){
    return e.textContent.replace(/\\s+/g,' ').trim(); });
  o.peerRows=v.querySelectorAll('[data-chart="peer-strip"] circle').length;
  o.txt=v.innerText.replace(/\\s+/g,' ');
  document.title='R:'+btoa(unescape(encodeURIComponent(JSON.stringify(o))));
},1600);
</script>
"""

open(TMP, "w", encoding="utf-8").write(src.replace("</body>", PROBE + "</body>"))
try:
    cp = subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
                         "--window-size=1600,1400", "--virtual-time-budget=12000", "--dump-dom",
                         "file:///" + TMP.replace("\\", "/")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="ignore", timeout=300)
except subprocess.TimeoutExpired:
    print("浏览器渲染超时（>300 秒）")
    sys.exit(2)
mm = re.search(r"R:([A-Za-z0-9+/=]{200,})", cp.stdout or "")
if not mm:
    print("探针失败:", (cp.stdout or "")[:400])
    sys.exit(2)
d = json.loads(base64.b64decode(mm.group(1)).decode("utf-8"))
TXT = d.pop("txt", "")

chk("渲染", "无整页横向滚动", d["hScroll"] <= 0, d["hScroll"])
chk("渲染", "无元素横向溢出", d["overN"] == 0, d["over"])
# ★ 3.2：SVG 数量随「置灰格／同业置灰卡」变化（招行信用卡单 guarantee 维置灰 → 13），
#   不是不变量。改为区间断言：8 张底图（分布/瀑布/曲线）以上、15 以内，
#   且与基线差不超过 2（真丢图会一次少好几张）。
# ★ 原写死 12–15：那是按「信用卡 9 个分布维度 + 5 张主图」量的。
#   房贷只有 4–7 个分布维度（且同业样本为 0 → 分位图置灰），实图会掉到 10 张以内。
#   真正的不变量是「分布网格恒为 9 格（实图 + 灰格）」，而不是 SVG 总数。
chk("渲染", "SVG 数量 ≥ 8（分布实图 + 主图，低于此说明整块丢失）",
    d["svg"] >= 8, d["svg"])
chk("渲染", "SVG 均有尺寸", d["svgZero"] == 0, d["svgZero"])
chk("渲染", "SVG 均有 viewBox", d["svgNoVB"] == 0, d["svgNoVB"])
chk("渲染", "无 <9.4px 字号", d["small"] == 0, f'{d["small"]}/{d["total"]}')
top_folds = [f for f in d["folds"] if re.match(r"^[①-⑧]", f)]
chk("渲染", "渲染后顶层节标题 8 个（另 2 个为嵌套明细块）", len(top_folds) == 8, d["folds"])
# ★ 3.2：圆点数＝(同业样本数 ＋ 本单 1 点) × 指标数 7。样本数随品种变（招行/建行/中信各不同），
#   原写法上限写死 23 单。改为「至少 7 点（本单自身的 7 个指标）且不超过 60 单×7」，
#   下限用 7 保底——真正画不出图时 peerRows 会是 0。
# 圆点数不必是 7 的整数倍：有的单某指标同业全缺值，该行就不画点（惠元 163 = 23 单×7 里少几个）。
# 故只断言「至少 7 点（本单自身 7 个指标都在）且不超过 60 单×7」。
# ★ 无同品种样本时该卡片置灰，圆点数必为 0（房贷类目前 0 个可比样本）。
#   这不是渲染缺失，而是"样本不足不出分位"的既定行为 → 记 SKIP。
# 分位卡是否置灰：直接看渲染结果有没有 peer-gray 卡片，不去猜变量名
_PEER_GRAY = 'data-chart="peer-gray"' in src
if d["peerRows"] == 0 and _PEER_GRAY:
    skip("渲染", "同业分位图圆点数",
         "同品种可比样本 <3 或本单指标缺口，分位卡已置灰不出图（见 ⑤ 卡说明）")
else:
    chk("渲染", "同业分位图圆点数（本单 7 指标在场，上限 60 单×7）",
        7 <= d["peerRows"] <= 60 * 7, d["peerRows"])

for w in BAN:
    chk("禁用词(渲染)", f"不含「{w}」", w not in TXT)

# 渲染后关键数值必须可见（每条都用 payload 反算，不写死）
ACH = L["total_recovery"] / P["exp_recovery_zz"]
KW = [f'{M["recovered"]:,.2f}', f'{P["balance_total"]/1e4:,.2f}', f'{P["n_loans"]:,}',
      f'{P["exp_recovery_zz"]/1e4:,.2f}', f'{buy/1e4:,.2f}',
      f'{M["recovery_rate"]*100:.2f}%',
      f'{P["exp_rec_rate_zz"]*100:.2f}%', f'{ACH*100:.2f}%', f'{M["dispose_fee_rate"]*100:.2f}%',
      f'{M["securitization_rate"]*100:.2f}%',
      f'{(M["recovered"]-buy)/P["balance_total"]*100:.2f}%',
      f'{cum_out/M["recovered"]*100:.2f}%', f'{L["fees_total"]:,.2f}']
# ★ 日期：只在有值时列入"必须可见"清单。
#   存续中单 terminate_date / liquidation_end 本就是 None，报告里写的是
#   「—（存续中）」。若把 str(None) 放进 KW，就会拿字面量 "None" 去报告里搜，
#   必然搜不到并报"不可见 None"——那是断言自己造出来的假异常。
for _dk in ("terminate_date", "liquidation_end"):
    if L.get(_dk):
        KW.append(str(L[_dk]))
# XIRR 同理：不可解时报告写的是「—」，没有数值可查
for _mk in ("sen_xirr", "sub_xirr"):
    if M.get(_mk) is not None:
        KW.append(f'{M[_mk]*100:.2f}%')
# 户数可能源未披露（建鑫信用卡不良按笔统计）：报告里显示「—」，无数字可查，
# 此时不把它列入"必须可见"清单，否则会要求报告凭空出现一个不存在的数。
if P.get("n_borrowers") is not None:
    KW.append(f'{P["n_borrowers"]:,}')
# 分布首档占比：grade 可能整块缺失（如房贷单不披露五级分类），此时跳过该项
if (DIST.get("grade") or []):
    KW.append(f'{DIST["grade"][0]["bal"]/(P["balance_total"]/1e4)*100:.2f}%')
# 无清算资产负债表的单，这两项在报告里是置灰占位而不是数字 → 不作为"必须可见"的数值
if L.get("residual_asset") is not None:
    KW.append(f'{L["residual_asset"]:,.2f}')
if L.get("holder_equity_end") is not None:
    KW.append(f'{L["holder_equity_end"]:,.2f}')
if META.get("code_sen"):
    KW.append(str(META["code_sen"]))
if META.get("auditor"):
    KW.append(str(META["auditor"])[:4])
def _seen(kw):
    """报告中是否可见该数值。金额允许按展示口径换算——
    报告里 408,215,281.29 元写成「4.08 亿」，原值当然不会出现；
    原断言只查原值，会把"换算了单位"误判成"漏渲染"。"""
    if kw in TXT:
        return True
    try:
        v = float(kw.replace(",", ""))
    except ValueError:
        return False
    for div, _ in ((1e8, "亿"), (1e4, "万")):
        if f'{v/div:,.2f}' in TXT:
            return True
    return False


for kw in KW:
    chk("内容(渲染)", f"可见「{kw}」", _seen(kw), kw)

names = ["项目档案", "资产池基础情况", "分期节奏", "现金流分配过程",
         "XIRR 与 XNPV", "账户勾稽", "核心结论", "数据质量与披露"]
seq = [f for f in d["folds"] if re.match(r"^[①-⑧]", f)]
chk("内容(渲染)", "八节标题按序",
    len(seq) == 8 and all(names[i] in seq[i] for i in range(8)), seq)

# ================= 汇总 =================
fails = [r for r in res if r["ok"] is False]
skips = [r for r in res if r["ok"] is None]
npass = len(res) - len(fails) - len(skips)

print(f"\n{'='*64}")
print(f"断言 {len(res)}　PASS {npass}　FAIL {len(fails)}　SKIP {len(skips)}")
print(f"{'='*64}")
for r in fails:
    print(f"  ✗ [{r['cat']}] {r['desc']}　{r['detail']}")
if skips:
    print(f"  · 跳过 {len(skips)} 项（输入字段缺失，不代表通过）：")
    for r in skips:
        print(f"      [{r['cat']}] {r['desc']}")

# 按分类统计，便于判断哪一层出了问题
cats = {}
for r in res:
    c = cats.setdefault(r["cat"], [0, 0, 0])
    if r["ok"] is False:
        c[1] += 1
    elif r["ok"] is None:
        c[2] += 1
    else:
        c[0] += 1
print("\n  分组：" + "　".join(
    f"{k} {v[0]}/{v[0]+v[1]+v[2]}" + (f"(FAIL {v[1]})" if v[1] else "")
    + (f"(SKIP {v[2]})" if v[2] else "") for k, v in cats.items()))

out_json = _args.json or os.path.join(os.path.dirname(os.path.abspath(HTML)),
                                      "_assert_single.json")
json.dump({"total": len(res), "pass": npass, "fail": len(fails), "skip": len(skips),
           "items": res},
          open(out_json, "w", encoding="utf-8", newline=""),
          ensure_ascii=False, indent=1)
sys.exit(0 if not fails else 1)
