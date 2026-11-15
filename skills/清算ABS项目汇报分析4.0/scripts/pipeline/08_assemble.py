# -*- coding: utf-8 -*-
"""建鑫 payload 组装：把四类解析结果合成与中信兼容的 payload + metrics

数据来源与优先级（★ 定源铁律）：
  · 资产池结构、分布、预测现金流      → 发行说明书（唯一源）
  · **预计回收总额                    → 中债资信评级报告**（招行说明书披露的是主承销商值）
  · 发行规模分层、票面、证券代码      → 说明书 + 受托报告首期 交叉校验
  · 逐期回收、账户、分档兑付          → 受托机构报告
  · 清算日、回购、费用、期末账户      → 清算报告 + 末次受托报告

输出：
  <proj>/02_提取数据/payload.json
  <proj>/02_提取数据/metrics.json

用法：
  python 08_assemble.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2021年第2期"
"""
import argparse
import json
import os
import re
import sys
from datetime import date


def jload(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def safe_div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def months_between(d1, d2):
    """d1→d2 的月数（按日折算，保留 1 位）"""
    try:
        y1, m1, dd1 = map(int, str(d1)[:10].split("-"))
        y2, m2, dd2 = map(int, str(d2)[:10].split("-"))
        a = date(y1, m1, dd1)
        b = date(y2, m2, dd2)
        return round((b - a).days / 30.44, 1)
    except Exception:
        return None


def _d(s):
    try:
        y, m, dd = map(int, str(s)[:10].split("-"))
        return date(y, m, dd)
    except Exception:
        return None


def xirr(flows, lo=-0.9999, hi=10.0, it=200):
    """现金流内部收益率（年化）。flows = [(日期字符串, 金额)]

    ★ 口径：一律挂**真实支付日**，不用期末日、不用报告日。
      分母按 365 天折算，与中信那套 XNPV 的年化口径一致（可直接对比）。
    ★ 二分法解 NPV=0：区间 [-99.99%, 1000%]，200 次迭代到机器精度。
      无解（现金流同号 / 不满 2 笔 / 日期缺失）返回 None，不硬凑数。
    """
    fs = [(_d(d), a) for d, a in (flows or []) if d and a]
    if len(fs) < 2 or not (any(a > 0 for _, a in fs) and any(a < 0 for _, a in fs)):
        return None
    t0 = min(f for f, _ in fs)

    def npv(r):
        return sum(a / (1 + r) ** ((f - t0).days / 365.0) for f, a in fs)

    flo, fhi = npv(lo), npv(hi)
    if flo * fhi > 0:
        return None
    for _ in range(it):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-7:
            return mid
        if v * flo > 0:
            lo, flo = mid, v
        else:
            hi = mid
    return (lo + hi) / 2


def assemble(proj):
    D = os.path.join(proj, "02_提取数据")
    SM = jload(os.path.join(D, "_sm_parsed.json")) or {}
    DI = jload(os.path.join(D, "_dist_parsed.json")) or {}
    TR = jload(os.path.join(D, "_trustee_parsed.json")) or {}
    LQ = jload(os.path.join(D, "_liq_parsed.json")) or {}
    RT = jload(os.path.join(D, "_rating_parsed.json")) or {}

    meta = dict(SM.get("meta") or {})
    pool = dict(SM.get("pool") or {})
    # ★ 户数/笔数补充来源：说明书常只给笔数（甚至都不给），
    #   受托机构报告「四、资产池表现情况·资产池整体表现情况」表里有完整三列
    #   （户数 / 笔数 / 本息费余额），是权威且逐期一致的。
    #   只在说明书缺时才补，避免覆盖说明书的入池时点口径。
    _tp0 = os.path.join(os.path.dirname(os.path.abspath(proj)) if False else proj,
                        "02_提取数据", "_trustee_parsed.json")
    if os.path.exists(_tp0):
        _T0 = (jload(_tp0) or {}).get("first") or {}
        _pf = (_T0.get("pool_perf") or {}).get("end") or {}
        if pool.get("n_borrowers") is None and _pf.get("borrowers"):
            pool["n_borrowers"] = _pf["borrowers"]
            pool["n_borrowers_src"] = "受托机构报告·首期「资产池整体表现情况」"
        if pool.get("n_loans") is None and _pf.get("loans"):
            pool["n_loans"] = _pf["loans"]
            pool["n_loans_src"] = "受托机构报告·首期「资产池整体表现情况」"
    # ★ 说明书的入池要素表若因扫描/乱码取不全，退回**中债评级报告**的
    #   「初始基础资产特征」表 —— 该表逐字给出：贷款笔数 / 借款人户数 /
    #   资产池未偿本息费余额（万元）/ 未偿本金余额 / 未偿息费余额 / 预计回收总金额，
    #   而且它本来就是本口径的定源（评级只认中债）。实测兴瑞2021一期、
    #   2023四期的说明书是扫描件/字体乱码，02 只能取到零散几个字段。
    if not pool.get("balance_total"):
        _zzp = None
        for _sub, _fn in (("OCR", "ZZ.ocr.txt"), ("文本", "ZZ.txt")):
            _q = os.path.join(proj, "02_提取数据", _sub, _fn)
            if os.path.exists(_q):
                _zzp = _q
                break
        if _zzp:
            _zraw = open(_zzp, encoding="utf-8", errors="ignore").read()
            _zt = re.sub(r"\s+", "", _zraw)
            def _zw(pat):
                m = re.search(pat + r"[（(]?万元[）)]?[^\d]{0,8}([\d,]+\.?\d*)", _zt)
                return float(m.group(1).replace(",", "")) * 1e4 if m else None
            _bil = _zw(r"资产池未偿本息费余额")
            if _bil:
                pool["balance_total"] = round(_bil, 2)
                pool["balance_total_src"] = "中债资信评级报告·初始基础资产特征表"
            _bpr = _zw(r"资产池未偿本金余额")
            if _bpr and not pool.get("balance_principal"):
                pool["balance_principal"] = round(_bpr, 2)
            _bin = _zw(r"资产池未偿息费余额")
            if _bin and not pool.get("balance_interest_fee"):
                pool["balance_interest_fee"] = round(_bin, 2)
            # ★ 笔数/户数加合理性上限：OCR 会把相邻两格连成一串
            #   （兴瑞2021一期 02 取出 201,602,138,313,433,220,617 笔），
            #   大于 1 亿笔的"笔数"必是串行，按缺失处理并用评级口径覆盖。
            for _pat, _key in ((r"借款人户数", "n_borrowers"), (r"贷款笔数", "n_loans")):
                # ★ 用**保留换行**的原文：评级报告的初始特征表是「三列并排」
                #   （本期 / 历史两期），压平后三列数字会连成一串
                #   （贷款笔数变成 220,617123,289126,498 → 2.2e17 笔）。
                #   保留换行时 (\d[\d,]*) 只吃第一列。
                m = re.search(_pat + r"[^\d]{0,8}([\d,]+)", _zraw)
                _cur = pool.get(_key)
                if _cur is not None and _cur > 1e8:
                    pool[_key] = None
                    _cur = None
                if m and not _cur:
                    pool[_key] = int(m.group(1).replace(",", ""))
                    pool[_key + "_src"] = "中债资信评级报告·初始基础资产特征表"
            if not (SM.get("pool") or {}).get("exp_recovery"):
                _er = _zw(r"预计回收总金额")
                if _er:
                    pool["exp_recovery"] = round(_er, 2)

    # ★ 单字段级「源未披露」声明：写进 pool._absent，供 G3 输入契约放行。
    #   与 dist_gray（维度级）分工：dist_gray 管分布表，这里管资产池标量。
    #   实测建鑫信用卡不良说明书按「笔数」统计、**不披露户数**（全篇 0 处「户数」），
    #   n_borrowers 恒为 None；把这种情况判成"取数漏项"等于要求编一个数出来。
    _abs_pool = []
    if pool.get("n_borrowers") is None:
        _abs_pool.append("n_borrowers")
    pool["_absent"] = _abs_pool
    tranche = dict(SM.get("tranche") or {})

    # ── ★ 预计回收：以中债评级报告为准（定源铁律）────────────────
    exp_zz = RT.get("exp_recovery")
    exp_src = "中债资信评级报告·预计回收总金额"
    if not exp_zz:
        exp_zz = pool.get("exp_recovery")
        exp_src = "发行说明书第七章（★中债缺失，降级为主承销商口径，需在报告标注）"
    # ★ 合理性护栏：中债与主承销商估值通常相差 ±20% 以内。
    #   若偏差超过 1 倍，多半是评级报告解析抓到了**历史对比表**里别的项目的值
    #   （实测 2021-4 曾取成 2021-2 的 3.16 亿，是本期 6.11 亿的一半，达成率虚高到 191%）。
    #   此时丢弃中债值、降级用主承口径，并在 payload 留痕，绝不带病出报告。
    _uw = (SM.get("pool") or {}).get("exp_recovery")
    if exp_zz and _uw:
        _ratio = exp_zz / _uw
        if not (0.5 <= _ratio <= 2.0):
            pool["exp_recovery_zz_rejected"] = exp_zz
            pool["exp_recovery_zz_rejected_reason"] = (
                f"中债 {exp_zz:,.2f} 与主承 {_uw:,.2f} 相差 {_ratio:.2f} 倍，超出 ±100% 合理区间，"
                f"疑为评级报告对比表串列")
            exp_zz = _uw
            exp_src = "发行说明书·主承销商（★中债值被合理性护栏拒绝，需人工复核评级报告）"
            print(f"  ⚠ 中债预计回收 {pool['exp_recovery_zz_rejected']:,.2f} 与主承 {_uw:,.2f} "
                  f"相差 {_ratio:.2f} 倍 → 已拒绝，降级用主承口径")

    pool["exp_recovery_zz"] = exp_zz
    pool["exp_recovery_zz_src"] = exp_src
    # 说明书原披露值（主承销商口径）单独保留
    pool["exp_recovery_sm_underwriter"] = SM.get("pool", {}).get("exp_recovery")
    pool["exp_rec_rate_zz"] = safe_div(exp_zz, pool.get("balance_total"))
    if RT.get("exp_rec_rate"):
        pool["exp_rec_rate_zz_rating"] = RT["exp_rec_rate"]

    # ── 分档补齐 ────────────────────────────────────────────
    tf = (TR.get("first") or {}).get("tranche") or {}
    if not tranche.get("senior", {}).get("coupon") and tf.get("coupon"):
        tranche.setdefault("senior", {})["coupon"] = tf["coupon"]
    if not meta.get("code_sen") and tf.get("code"):
        meta["code_sen"] = tf["code"][0] if tf["code"] else None
        meta["code_sub"] = tf["code"][1] if len(tf["code"]) > 1 else None
    # ★ 发行日兜底：2021–2023 各期说明书写「信托财产交付日为X年X月X日」，
    #   但 2024 两期的说明书没有这句，发行日为空 → 存续月数也就空了。
    #   首期受托报告「信托生效日」与说明书发行日实测 14 期逐期一致，可作兜底。
    if not meta.get("issue_date"):
        _eff = (TR.get("first") or {}).get("trust_effective_date")
        if _eff:
            meta["issue_date"] = _eff
            meta["issue_date_src"] = "受托机构报告·信托生效日"

    # ── 逐期（受托报告）─────────────────────────────────────
    periods, cum = [], 0.0
    _sen_i = (tranche.get("senior") or {}).get("issue")
    _sen_cum = 0.0
    for p in TR.get("periods") or []:
        cum += (p.get("recovery_this") or 0.0)
        _sen_cum += (p.get("sen_principal") or 0.0)
        # ★ 优先档付清之后的期次：利息与剩余本金**真实值是 0**，不是「没披露」。
        #   受托报告那几期该格是空白/「-」，解析出来是 None，若照「缺失记—」
        #   会在一张表里出现 0.00 与 — 混排，看起来像数据不全。
        _sen_done = bool(_sen_i) and abs(_sen_cum - _sen_i) < 1.0
        _si = p.get("sen_interest")
        _sb = p.get("sen_balance_after")
        if _sen_done:
            _si = 0.0 if _si is None else _si
            _sb = 0.0 if _sb is None else _sb
        periods.append({
            "period": p["period"],
            "pay_date": p.get("pay_date"),
            "in_total": p.get("recovery_this"),
            "out_total": sum((v or 0) for v in (p.get("outflow") or {}).values()),
            "sen_principal": p.get("sen_principal"),
            "sen_interest": _si,
            "sub_principal": p.get("sub_principal"),
            # ★ 次级档两笔收益（05 已按「优先档是否付息」把证券利息总支出正确归属）：
            #   sub_fixed_cost ＝ 次级档固定资金成本（利率型，逐期或末期一次性）
            #   sub_income     ＝ 次级档超额收益（剩余收益，末期/清算时分配）
            #   两者合计才是次级档总收益；原实现只取超额收益，次级 XIRR 被严重低估。
            "sub_fixed_cost": p.get("sub_fixed_cost"),
            "sub_income": p.get("sub_income"),
            "sen_balance_after": _sb,
            "sub_balance_after": p.get("sub_balance_after"),
            "outflow": p.get("outflow") or {},
            "cum": round(cum, 2),
        })
    # ★ 支付日必须挂到账户行上：报告第 8 节的逐期勾稽表按「期次 / 支付日 / 期初 /
    #   流入 / 流出 / 期末」六列渲染，而受托报告的「信托账户核算概况」表本身没有日期列。
    #   原来不透传 pay_date，建行那批是因为老 payload 里带了这个键才没崩；
    #   兴业是全新解析，直接 KeyError: 'pay_date' 整单构建失败。
    _pay_of = {p["period"]: p.get("pay_date") for p in periods}
    CAL_FLAG = False
    # ── 费用科目逐期数按「清算报告审计口径」校准 ─────────────────────
    # ★ 扫描件的逐期「资产池现金流出」表会在某科目上整行读错
    #   （兴瑞2021二期：执行费用逐期合计 86,355,505.00，清算报告 58,900,608.71，
    #    偏高 46.6%；贷款服务机构报酬 22,432,870.96 vs 19,746,298.90 同样偏高）。
    #   清算报告经审计、且是**全周期**口径，逐期表是未审计过程稿 ——
    #   两者差超 2% 时按比例校准到审计合计（保留逐期分布形状，不改变合计），
    #   并在 fee_basis 里写明"已按清算报告校准"，否则矩阵合计会掉到 110%/172%。
    _FEE_TO_FD = {"执行费用": "处置费", "处置费用": "处置费",
                  "执行费用及执行费用利息": "处置费",
                  "贷款服务机构报酬": "贷款服务费", "受托机构报酬": "受托机构报酬",
                  "资金保管机构报酬": "资金保管机构报酬", "代理兑付费用": "代理兑付费",
                  "发行费用": "发行费", "税收": "税收", "审计费": "审计费",
                  "跟踪评级服务费": "跟踪评级费", "其他费用支出": "其他费用"}
    _cal = []
    # 清算报告科目名 → 逐期表可能用的写法（两家叫法不同，见 05 的 _ALIAS）
    _ALIAS_P = {"执行费用及执行费用利息": ("执行费用", "处置费用"),
                "贷款服务机构报酬": ("贷款服务机构报酬",),
                "受托机构报酬": ("受托机构报酬",),
                "资金保管机构报酬": ("资金保管机构报酬",),
                "代理兑付费用": ("代理兑付费用",),
                "发行费用": ("发行费用",),
                "税收": ("税收",),
                "审计费": ("审计费",),
                "跟踪评级服务费": ("跟踪评级服务费",),
                "其他费用支出": ("其他费用支出",)}
    # ★ 不能用后面的局部变量 fd：校准必须在 periods 的 out_total 计算**之前**完成，
    #   所以这里直接读一次 outflow_detail（与 fd 同源）。
    for _k, _want in (LQ.get("outflow_detail") or {}).items():
        if not _want:
            continue
        # ★ 候选里必须**含清算报告自己的科目名**：兴瑞2023 系列逐期表里
        #   「执行费用」与「执行费用及执行费用利息」两种写法并存，
        #   而 _ALIAS_P 只列了前两个别名，漏掉 _k 本身 → 合并漏掉一个键，
        #   执行费用仍被记两遍（矩阵 111%）。
        _cands_k = [_k] + [x for x in _ALIAS_P.get(_k, ()) if x != _k]
        # ★ 同一科目在不同期次用了不同写法时（兴瑞2023二期：前几期写「执行费用」、
        #   后几期写「执行费用及对应的执行费用利息」），必须先**合并成一个键**再校准，
        #   否则两个键各占一行、各自进合计，执行费用被记两遍
        #   （37,409,540.54 ＋ 31,999,724.40，矩阵合计 111%）。
        _hit = [x for x in _cands_k
                if any(((p.get("outflow") or {}).get(x) or 0.0) for p in periods)]
        if len(_hit) > 1:
            _keepk = _hit[0]
            for _p in periods:
                _o = _p.get("outflow") or {}
                for _x in _hit[1:]:
                    if _o.get(_x):
                        _o[_keepk] = round((_o.get(_keepk) or 0.0) + _o[_x], 2)
                        _o.pop(_x, None)
            _hit = [_keepk]
        for _pk in (_hit or _cands_k[:1]):
            _cur = sum(((p.get("outflow") or {}).get(_pk) or 0.0) for p in periods)
            if _cur <= 0 or abs(_cur - _want) <= max(1.0, abs(_want) * 0.02):
                continue
            _rate = _want / _cur
            for p in periods:
                _o = p.get("outflow") or {}
                if _o.get(_pk):
                    _o[_pk] = round(_o[_pk] * _rate, 2)
            _cal.append(f"{_pk} {_cur:,.2f}→{_want:,.2f}")
            break
    # ── 证券利息逐期数按清算报告口径校准 ───────────────────────────
    # ★ 同理：扫描件的「付息金额」格常把本息合计读成优先档利息
    #   （兴瑞2021二期逐期合计 7,615,994.48，清算报告 3,807,997.24，偏高 100%），
    #   直接导致优先档 XIRR 算出 6.05%（票面 2.99%），偏离 306bp。
    #   优先档按固定票面计息，实际付息总额是清算报告里**经审计**的一个数，
    #   用它校准逐期分布后 XIRR 才回到票面附近。
    #
    # ★★ 2026-10-30 修订：上面的"偏高 100%"其实是**混入年度受托机构报告期次**
    #   造成的（年度报告的「本期」= 自设立日累计，与季报重复），不是扫描件读错。
    #   05 已按「支付日缺失 + 付息＝前 k 期之和」剔除这类期次，剔除后逐期合计
    #   自动等于清算口径（三单实测差额 0.00），此处校准**不应再触发**。
    #   保留作最后一道保险，但触发时必须在 payload 留痕，供断言与报告脚注引用 ——
    #   等比例缩放会让每一期都错、而合计正确，是最难被发现的一类失真。
    _si_want = LQ.get("sen_interest_paid")
    if _si_want:
        _si_cur = sum((p.get("sen_interest") or 0.0) for p in periods)
        if _si_cur > 0 and abs(_si_cur - _si_want) > max(1.0, _si_want * 0.02):
            _r = _si_want / _si_cur
            for p in periods:
                if p.get("sen_interest"):
                    p["sen_interest"] = round(p["sen_interest"] * _r, 2)
            _cal.append(f"优先档利息 {_si_cur:,.2f}→{_si_want:,.2f}"
                        f"（缩放比 {_r:.4f}，逐期明细已失真）")
            print(f"  ★ 优先档利息按清算口径校准：{_si_cur:,.2f} → {_si_want:,.2f}"
                  f"（缩放比 {_r:.4f}）")

    if _cal:
        LQ["fee_calibrated"] = _cal
        # 顶层再标一次：build_single 是**跨行共用**的技能代码，
        # 平台侧的"按清算报告审计口径覆盖逐期费用"必须只看这一个开关，
        # 否则会改到惠元/建行/招行已过基线的交付件（本轮实测：惠元 G1 差 1 字节、
        # 审计费 49→47、未归集差额 -580.45→-531.45）。
        CAL_FLAG = True
        # ★ out_total 必须**同步重算**：它是在 periods.append 时算好的，
        #   校准后不改就会与明细自相矛盾（实测：明细合计 3.648 亿、out_total 合计 3.968 亿，
        #   而断言读的是 out_total，于是矩阵占比仍是 110%）。
        for p in periods:
            p["out_total"] = round(sum((v or 0) for v in (p.get("outflow") or {}).values()), 2)
        print("  费用按清算口径校准：", "；".join(_cal))

    # ── 次级档收益拆分口径判定（体例 A / B 自适应）────────────────────
    # ★ 「证券利息总支出」这一格里到底含不含「次级档超额收益」，各家各期不一致：
    #     体例 A（招行部分单）：int ＝ 优先息 ＋ 固资 ＋ 超额 → 固资＝int−优先−超额
    #     体例 B（兴业全部单）：int ＝ 优先息 ＋ 固资，超额**另起一行** → 固资＝int−优先
    #   单期看根本分不出来：2022三期 p6 的 exc 211 万 < int 413 万，两种都讲得通。
    #   必须用清算报告「归属于次级持有人收益」这个**总额**反推：
    #     Σ(int−优先) ＋ Σ超额 ≈ Sub  → B
    #     Σ(int−优先)          ≈ Sub  → A
    #   实测（兴业 10 单全部命中 B）：
    #     2023七期 747,945.21 ＋ 2,754,250.14 ＝ 3,502,195.35 ✓
    #     2022三期 4,129,457.09 ＋ 2,116,683.54 ＝ 6,246,140.63 ✓
    #     2021一期 6,032,689.30 ＋ 3,194,491.99 ＝ 9,227,181.29 ✓
    #   原先一律按 A 算，固资被系统性少记（少记额恰好等于超额），差额全落到
    #   sub_income_residual 里 —— 于是报告上"次级档资金成本"一栏大面积空缺，
    #   读者只看到一个叫"剩余"的数，无法分辨是合同约定收益还是清算偶然结余。
    _S_int = sum(max(0.0, ((p["outflow"] or {}).get("证券利息总支出") or 0.0)
                     - (p.get("sen_interest") or 0.0)) for p in periods)
    _S_exc = sum((p.get("sub_income") or 0.0) for p in periods)
    _Sub = LQ.get("sub_income_paid")
    SUB_STYLE = None
    if _Sub and _S_int > 0:
        _tolx = max(1.0, _Sub * 0.005)
        _dB = abs(_S_int + _S_exc - _Sub)
        _dA = abs(_S_int - _Sub)
        if _dB <= _tolx and _dB <= _dA:
            SUB_STYLE = "B"
        elif _dA <= _tolx:
            SUB_STYLE = "A"
        if SUB_STYLE:
            _fix = []
            for p in periods:
                _g = ((p["outflow"] or {}).get("证券利息总支出") or 0.0) \
                     - (p.get("sen_interest") or 0.0)
                if _g <= 0.05:
                    continue
                _new = round(_g, 2) if SUB_STYLE == "B" \
                    else round(_g - (p.get("sub_income") or 0.0), 2)
                if _new < -0.05:
                    continue          # 反解为负 → 保留原值，不臆造
                _old = p.get("sub_fixed_cost") or 0.0
                if abs(_old - _new) > 0.5:
                    _fix.append(f"p{p['period']} {_old:,.2f}→{_new:,.2f}")
                    p["sub_fixed_cost"] = _new
            if _fix:
                print(f"  次级固资口径判定为 {SUB_STYLE} 体例，重算："
                      + "；".join(_fix))
                LQ.setdefault("_notes", []).append(
                    f"次级档固定资金成本按 {SUB_STYLE} 体例重算（"
                    + "；".join(_fix) + "），判据："
                    + ("Σ(利息总支出−优先息)+Σ超额=清算归属次级收益"
                       if SUB_STYLE == "B" else "Σ(利息总支出−优先息)=清算归属次级收益"))

    trust_account = []
    for t in TR.get("trust_account") or []:
        trust_account.append({k: t.get(k) for k in
                              ("period", "begin", "inflow", "outflow", "end",
                               "note", "sub_end_sum", "sub_end_core")})
        trust_account[-1]["pay_date"] = t.get("pay_date") or _pay_of.get(t.get("period"))

    # ── 清算 ────────────────────────────────────────────────
    fd = LQ.get("outflow_detail") or {}
    # 处置费：中信/招行叫「执行费用及执行费用利息」，建行叫「处置费用」
    # ★ 处置环节成本三家三叫法：中信「执行费用及执行费用利息」/ 建行「处置费用」/
    #   兴业「执行费用」。少认一个，fee_detail["处置费"] 就是 None，
    #   进而 dispose_fee_rate 空 → G3 取数契约直接判「漏项」整单跑不动。
    dispose = fd.get("执行费用及执行费用利息")
    if dispose is None:
        dispose = fd.get("处置费用")
    if dispose is None:
        dispose = fd.get("执行费用")
    # ★ 建行口径：清算报告「资产池现金流出」里「处置费用」是**资产池层面**的独立科目，
    #   不由信托「费用和开支」账户支付 —— 建鑫2021-1 实测：
    #     费用和开支账户流出 53,580,575.26 + 税收 1,181,620.15 = 54,762,057.41
    #     恰等于「税收+代理兑付+发行+受托报酬+保管+贷款服务报酬+审计+跟踪评级」之和，
    #     **不含**处置费用 61,433,367.10。
    #   故本单 fee_total 与 dispose_fee 不构成加总关系（contains=False），
    #   否则费用率会被算成 28.5%（实际 13.4%）。
    _fee_keys = ["税收", "代理兑付费用", "发行费用", "受托机构报酬", "资金保管机构报酬",
                 "执行费用及执行费用利息", "处置费用", "贷款服务机构报酬", "审计费",
                 "跟踪评级服务费", "其他费用支出"]
    _rest = sum(fd.get(k) or 0.0 for k in _fee_keys
                if k not in ("执行费用及执行费用利息", "处置费用"))
    # 判据（确定性，不靠猜）：
    #   建行「处置费用」是资产池层面单列科目 → 与费用和开支账户不重叠 → contains=False
    #   中信/招行「执行费用及执行费用利息」计入费用和开支账户 → contains=True
    _contains = (fd.get("执行费用及执行费用利息") is not None)
    # 二次校验：若相加后超过累计回收的 30%，说明必然重复，强制改正
    _rec_chk = LQ.get("total_recovery") or 0
    if dispose is not None and _rec_chk and (_rest + dispose) > 0.30 * _rec_chk \
            and _rest <= 0.30 * _rec_chk:
        _contains = False
    fee_detail = {
        "处置费": dispose,
        "贷款服务费": fd.get("贷款服务机构报酬"),
        "受托机构报酬": fd.get("受托机构报酬"),
        "资金保管机构报酬": fd.get("资金保管机构报酬"),
        "代理兑付费": fd.get("代理兑付费用"),
        "发行费": fd.get("发行费用"),
        "税收": fd.get("税收"),
        "审计费": fd.get("审计费"),
        "跟踪评级费": fd.get("跟踪评级服务费"),
        "其他费用": fd.get("其他费用支出"),
    }
    fee_detail = {k: v for k, v in fee_detail.items() if v is not None}
    # ★ 费用总额口径：contains=True 时 fee_detail 已含处置费，直接加总；
    #   contains=False 时处置费在账户外，加总须剔除，否则费用率翻倍。
    fees_total = sum(v for k, v in fee_detail.items()
                     if not (k == "处置费" and not _contains))
    fees_with_dispose = sum(fee_detail.values())

    acc = LQ.get("accounts") or {}
    main_acc = acc.get("信托账户") or [None] * 4
    liquidation = {
        "terminal_kind": "A",
        "total_recovery": LQ.get("total_recovery"),
        # ★ 账户结息三个名字：中信/招行「其他收入 / 账户结息」、建行「合格投资」。
        #   06 已把三种来源统一归到 account_interest，这里直接取它；
        #   只有老数据没有该键时才退回 other_income。
        "account_interest": (LQ.get("account_interest")
                             if LQ.get("account_interest") is not None
                             else LQ.get("other_income")),
        "fees_total": round(fees_total, 2),
        "fees_total_with_dispose": round(fees_with_dispose, 2),
        "fee_total_includes_dispose": _contains,
        "dispose_fee_basis": LQ.get("dispose_fee_basis"),
        # ★ 增值税口径优先取 06 的判定：德勤版清算报表（兴业）里「税金及附加」只有
        #   附加税 6,645.04，增值税 55,375.40 是单列在「税项」文字说明里的，
        #   必须单独扣，否则资金平衡左端多出 5.5 万（120M 级项目约 4.6bp）。
        #   其余三家清算报告的「税收」科目本身已含增值税 → 保持原口径。
        "vat_total": (LQ.get("vat_total") if LQ.get("vat_total") is not None
                      else fd.get("税收")),
        "vat_included_in_fees": (LQ.get("vat_included_in_fees")
                                 if LQ.get("vat_included_in_fees") is not None
                                 else True),
        "fee_detail": fee_detail,
        "sen_principal_paid": LQ.get("sen_principal_paid"),
        "sen_interest_paid": LQ.get("sen_interest_paid"),
        "sub_principal_paid": LQ.get("sub_principal_paid"),
        "sub_income_paid": LQ.get("sub_income_paid"),
        "dispose_exec_fee": dispose,
        "servicer_fee": fd.get("贷款服务机构报酬"),
        "cash_begin": main_acc[0], "cash_inflow": main_acc[1],
        "cash_outflow": main_acc[2], "cash_end": main_acc[3],
        "liquidation_date": LQ.get("liquidation_date"),
        "liquidation_end": LQ.get("liquidation_date"),
        "buyback": LQ.get("buyback"),
        # 新体例（2023+）专有字段
        "outflow_total": LQ.get("outflow_total"),
        "cash_residual": LQ.get("cash_residual"),
        "total_recovery_basis": LQ.get("total_recovery_basis"),
        "audit_no": LQ.get("audit_no"), "review_no": LQ.get("review_no"),
        "auditor": LQ.get("auditor"),
        "principal_paid_note": LQ.get("principal_paid_note"),
        "account_source": LQ.get("account_source"),
        # ★ 降级补全的留痕（「清仓回购型」无清算报告时由 06 写入）
        #   total_recovery_basis / fee_basis 说明本单的回收与费用取自哪张表，
        #   与 17 期（取清算报告）口径不同，必须在报告里写明，否则读者会误以为同源。
        "fee_basis": LQ.get("fee_basis"),
        "degraded_note": LQ.get("_degraded"),
        "liq_date_basis": LQ.get("_liq_date_basis"),
        # 建行/招行清算报告为末次受托机构报告体例，**没有**清算资产负债表 →
        # 剩余资产、持有人权益、清算净收益三项结构性不可得，如实留空。
        # ★ no_balance_sheet=True 是给门禁用的一等字段：G3 据此对依赖这三项的
        #   恒等式做 SKIP（而不是当成取数漏项卡死），报告正文也据此置灰。
        # ★ 但有清算资产负债表时必须透传（兴业德勤版就有）：原来写死 None，
        #   于是明明取到了 560,000 应付/0 权益，报告仍说"不含资产负债表、置灰"，
        #   4 条恒等式断言全部 SKIP —— 等于把手上的证据扔掉。
        "residual_asset": LQ.get("residual_asset"),
        "holder_equity_end": LQ.get("holder_equity_end"),
        "liquidation_gain": LQ.get("liquidation_gain"),
        "liab_at_begin_total": LQ.get("liab_at_begin_total"),
        "liab_at_end_total": LQ.get("liab_at_end_total"),
        # 德勤版把净收益当期全额分配，权益恒等式需减此项才闭合
        "liquidation_distributed": LQ.get("liquidation_distributed"),
        # 清仓回购价款：真实现金流入，但不计入累计回收（回收率口径）
        "buyback_inflow": LQ.get("buyback_inflow"),
        "buyback_inflow_basis": LQ.get("buyback_inflow_basis"),
        # ★ 累计回收是否**已含**回购价款（清算报告体例差异）：
        #   兴业信托版「收回基础资产回收款」已含 → 资金平衡不得再加一次；
        #   其他行无此键 → verify 沿用旧公式（回收＋回购）。
        "recovery_includes_buyback": LQ.get("recovery_includes_buyback"),
        "interest_income": LQ.get("interest_income"),
        "cash_end_liq": LQ.get("cash_end_liq"),
        "no_balance_sheet": LQ.get("residual_asset") is None,
        "no_balance_sheet_note": (
            None if LQ.get("residual_asset") is not None else
            ("本单清算报告为末次受托机构报告体例，"
             "不含清算资产负债表／持有人权益／清算净收益；"
             "相关恒等式不适用，报告对应项置灰")),
        # ★ settlement_state 是「本单是否已清算完毕」的一等字段（06 判定）：
        #     settled     = 已取得清算文书，或两档本金已全额兑付（清仓回购型）
        #     outstanding = 无清算文书且本金未兑付完 → 信托仍在存续
        #   两类的报告形态完全不同：outstanding 不能写"信托计划已终止"，
        #   清算类指标（清算日/清算净收益/回收对账/本金全额兑付）一律置灰，
        #   指标改为存续期口径（累计回收率、存续进度、剩余本金）。
        "settlement_state": LQ.get("settlement_state") or "settled",
        "settlement_basis": LQ.get("settlement_basis"),
    }
    # 逐期与清算的回收对账（★ 招行特有口径）
    #   逐期「本期回收」含逐期「其他收入累计」，清算「总回收」含清算「其他收入」，
    #   两者差额 = 清算期末新增的其他收入（末次受托报告未体现，清算报告补记）。
    #   实测建鑫2021-2：278,127,994.00 − 121,606.32 + 130,151.61 = 278,136,539.29（差 0.00）
    _cum_period = round(sum((p.get("in_total") or 0) for p in periods), 2)
    _cum_other = None
    # 末次受托报告的「其他收入累计」
    _tdir = os.path.join(proj, "02_提取数据", "文本")
    _trs = sorted([f for f in os.listdir(_tdir) if re.match(r"^TR\d+\.txt$", f)],
                  key=lambda x: int(re.findall(r"\d+", x)[0]))
    if _trs:
        _t = open(os.path.join(_tdir, _trs[-1]), encoding="utf-8").read()
        _m = re.search(r"其他收入[\s\-]*(-|[\d,]+\.\d{2})[\s\-]*(-|[\d,]+\.\d{2})", _t)
        if _m and _m.group(2) not in ("-", "—"):
            _cum_other = float(_m.group(2).replace(",", ""))
    # ★ 完整对账公式（三项，实测建鑫2022-2 残差 0.00）：
    #   逐期本期回收累加
    #   + (末期账户流入 − 末期本期回收)   ← 末期把流动性储备账户余额转入，不算回收
    #   + (清算其他收入 − 逐期其他收入累计) ← 清算期末新增的结息
    #   = 清算报告总回收
    _last = periods[-1] if periods else {}
    _last_ta = (trust_account[-1] if trust_account else {}) or {}
    _last_inflow = _last_ta.get("inflow")
    _last_rec = _last.get("in_total")
    _reserve_in = (round((_last_inflow or 0) - (_last_rec or 0), 2)
                   if _last_inflow is not None and _last_rec is not None else 0.0)
    # ★ 清算报告未列「其他收入」项时（实测 2024 一/二期为 None），
    #   不能把逐期的其他收入累计当成"负的新增"减掉，否则会凭空造出 11 万差额。
    #   此时该项按 0 处理，差额由容差吸收（实测 <5bp）。
    _ai = liquidation.get("account_interest")
    _other_new = 0.0 if _ai is None else round(_ai - (_cum_other or 0), 2)
    # ★ 两种报告体例分开对账：
    #   旧体例（2021-2022，华润+德勤）：「清算报告」= 末次受托机构报告，
    #       总回收含「末期储备账户转入」和「清算新增结息」两项，需三项公式配平（残差 0）；
    #   新体例（2023 起，金谷+毕马威）：标准清算报告，
    #       总回收 = 费用明细合计 ＋ 剩余信托专户资金，已含全部流入，
    #       与逐期累加的差额是「清算期新增结息」，量级 0.01%，不再要求 0。
    _liq = liquidation.get("total_recovery")
    if liquidation.get("outflow_total") is not None:
        _resid = round((_liq or 0) - _cum_period, 2)
        liquidation["recovery_reconcile"] = {
            "style": "new(2023+)",
            "periods_cum": _cum_period,
            "liq_total": _liq,
            "formula": "清算总回收（费用明细合计＋剩余资金）− 逐期本期回收累加 = 清算期新增结息等其他流入",
            "residue": _resid,
            "residue_pct": (round(abs(_resid) / _liq * 1e4, 2) if _liq else None),
            "tolerance": "残差应为小额正值（新增结息），占清算回收 <0.5%",
            "note": "新体例总回收已含全部流入，不适用旧体例的三项补差公式。",
        }
    else:
        # ★ 第三体例（建行·建信信托）：清算报告「总计」＝
        #   「本期处置完毕」＋「合格投资」（清算期新增），
        #   **不含**流动性储备账户转入——储备账户余额本就在信托账户内，
        #   逐期回收累加已经把每期实际收到的现金算全了。
        #   实测建鑫2021一期：逐期累加 408,212,792.10 vs 清算总计 408,215,281.29，
        #   差 2,489.19 元（0.6bp，来自合格投资 44,429.86 的部分归属）。
        #   若硬套招行三项公式（再加末期储备转入 -1,734,758.38），残差被放大到
        #   42.6bp，成了假异常。
        _d_new = abs((_liq or 0) - _cum_period)
        _d_old = abs((_cum_period + _reserve_in + _other_new) - (_liq or 0))
        if _liq and _d_new <= _d_old:
            liquidation["recovery_reconcile"] = {
                "style": "old-direct(建行)",
                "periods_cum": _cum_period,
                "liq_total": _liq,
                "formula": "逐期本期回收累加 ＋ 清算期合格投资等新增流入 = 清算总回收",
                "residue": round(_cum_period - _liq, 2),
                "note": "建行清算报告的「总计」不含流动性储备账户转入（该余额本在信托账户内），"
                        "逐期累加与总计直接可比，无需两项补差。",
            }
        else:
            _calc = round(_cum_period + _reserve_in + _other_new, 2)
            liquidation["recovery_reconcile"] = {
                "style": "old(2021-2022)",
                "periods_cum": _cum_period,
                "last_period_reserve_in": _reserve_in,
                "other_income_new": round(_other_new, 2),
                "calculated": _calc,
                "liq_total": _liq,
                "formula": "逐期本期回收累加 ＋ 末期储备账户转入 ＋ 清算新增其他收入 = 清算总回收",
                "residue": round(_calc - (_liq or 0), 2),
                "note": "末期「账户流入」含流动性储备账户余额转入，不等于本期回收；"
                        "清算报告把该转入与其他收入一并计入总回收，故需两项补差。",
            }

    # ── 日期补齐 ────────────────────────────────────────────
    meta["terminate_date"] = LQ.get("liquidation_date")
    meta["liquidation_end"] = LQ.get("liquidation_date")

    # ── dist ───────────────────────────────────────────────
    dist = DI.get("dist") or {}
    # 本单没有的维度如实标注
    dist_absent = (DI.get("dist_meta") or {}).get("_absent") or {}
    # ★ 置灰清单：统一范本里有、本单没有的全部维度（含品种性缺失与未披露两类）。
    #   报告的分布区按**固定 10 块**排版，缺的块渲染为灰度占位并注明原因，
    #   不允许像 v1 那样整块消失 —— 否则跨行并排时块数不一致，无法判断是漏做还是没有。
    dist_gray = (DI.get("dist_meta") or {}).get("_gray") or {}

    # 清算数据来源描述：缺哪个就只说有哪个，不能拼出「清算报告（None）+ None」
    _liq_parts = []
    if LQ.get("_src"):
        _liq_parts.append(f"清算报告（{LQ['_src']}）")
    if LQ.get("account_source"):
        _liq_parts.append(str(LQ["account_source"]))
    _liq_src = " ＋ ".join(_liq_parts) or None

    out = {
        # ★ 合同分配顺序（说明书第七章文字条款）——矩阵行序的唯一依据。
        #   14_to_layout 据此建 waterfall_rows；缺则退回「按清算报告科目顺序」并声明。
        "waterfall": SM.get("waterfall"),
        "meta": meta, "pool": pool, "tranche": tranche,
        "periods": periods, "trust_account": trust_account,
        "liquidation": liquidation,
        # ★ 费用口径校准开关（只兴瑞开）：build_single 据此决定是否用
        #   清算报告审计值覆盖逐期费用行，其它行不带此键、行为完全不变。
        "fee_calibrated": CAL_FLAG,
        # ★ 被剔除的「年度受托机构报告」累计期次（05 判据：支付日缺失 ＋
        #   付息＝前 k 期之和）。报告脚注据此声明"期次已按单期口径剔除重复"，
        #   断言据此确认剔除后逐期合计与清算报告配平。
        "dropped_annual": TR.get("dropped") or [],
        "dist": dist, "dist_absent": dist_absent,
        # dist_gray 是维度级「源未披露」声明；单字段级声明在 pool._absent 里
        "dist_gray": dist_gray,
        "forecast_flow": DI.get("forecast_flow") or [],
        "recrate": DI.get("recrate") or [],
        "rating": {k: v for k, v in (RT or {}).items() if not k.startswith("_")},
        "_sources": {
            "资产池/分布/现金流": "发行说明书",
            "预计回收": exp_src,
            "逐期/账户/兑付": "受托机构报告",
            "清算": _liq_src,
            "评级交叉校验": RT.get("_src"),
        },
    }
    return out


def build_metrics(P):
    """派生指标（口径与中信一致）"""
    pool, T, L = P["pool"], P["tranche"], P["liquidation"]
    PER = P["periods"]
    bt = pool.get("balance_total")
    rec = L.get("total_recovery")
    M = {}
    M["pool_total"] = bt
    M["issue_total"] = T.get("total")
    M["recovered"] = rec
    M["securitization_rate"] = safe_div(T.get("total"), bt)
    M["recovery_rate"] = safe_div(rec, bt)
    M["exp_recovery"] = pool.get("exp_recovery_zz")
    M["exp_rec_rate"] = safe_div(pool.get("exp_recovery_zz"), bt)
    M["achieve_rate"] = safe_div(rec, pool.get("exp_recovery_zz"))
    fd = L.get("fee_detail") or {}
    M["dispose_fee"] = fd.get("处置费")
    M["dispose_fee_rate"] = safe_div(fd.get("处置费"), rec)
    M["servicer_fee"] = fd.get("贷款服务费")
    M["servicer_fee_rate"] = safe_div(fd.get("贷款服务费"), rec)
    M["fee_total"] = L.get("fees_total")
    M["fee_total_rate"] = safe_div(L.get("fees_total"), rec)
    M["sen_issue"] = (T.get("senior") or {}).get("issue")
    M["sub_issue"] = (T.get("sub") or {}).get("issue")
    M["sen_coupon"] = (T.get("senior") or {}).get("coupon")
    M["sen_principal_paid"] = L.get("sen_principal_paid")
    M["sen_interest_paid"] = L.get("sen_interest_paid")
    M["sub_principal_paid"] = L.get("sub_principal_paid")
    M["sub_income_paid"] = L.get("sub_income_paid")
    M["n_periods"] = len(PER)
    M["life_months"] = months_between(
        (P["meta"] or {}).get("issue_date"), L.get("liquidation_date"))
    M["buyback_price"] = (L.get("buyback") or {}).get("price")
    M["buyback_share_of_recovery"] = safe_div(M["buyback_price"], rec)
    M["cum_at_period"] = [{"period": p["period"], "cum": p["cum"]} for p in PER]

    # ── XIRR 与回报倍数（挂真实支付日）───────────────────────
    # ★ 优先档：认购日在发行日出一笔钱，此后每期收「本金＋利息」。
    # ★ 次级档：认购日出一笔钱，每期收本金，**次级收益在清算环节一次性分派**，
    #   所以挂清算日；没有清算日就退回最后一期支付日（并记在 _note 里备查）。
    _iss = (P["meta"] or {}).get("issue_date")
    _liq = L.get("liquidation_date")
    _last_pay = max([p["pay_date"] for p in PER if p.get("pay_date")], default=None)
    _tail = _liq or _last_pay

    def _flows(side):
        if not _iss:
            return []
        base = (T.get("senior") or {}).get("issue") if side == "sen" else (T.get("sub") or {}).get("issue")
        fs = [(_iss, -(base or 0.0))]
        for p in PER:
            amt = p.get(side + "_principal") or 0.0
            if side == "sen":
                amt += p.get("sen_interest") or 0.0
            else:
                # ★ 次级档两笔收益都挂**真实支付日**（不是清算日）：
                #   固资与超额收益在受托报告里都是某一期实际兑付的。
                #   原实现把收益一律挂清算日 → 现金流被整体后移，
                #   XIRR 被系统性低估（实测建鑫2021二期 2.51% vs 应为 6.9%）。
                amt += (p.get("sub_fixed_cost") or 0.0)
                amt += (p.get("sub_income") or 0.0)
            if amt:
                fs.append((p.get("pay_date") or _last_pay, amt))
        return fs

    _fs = _flows("sen")
    M["sen_xirr"] = xirr(_fs)
    M["sen_inflow"] = sum(a for _, a in _fs if a > 0) if _fs else None
    _fu = _flows("sub")
    # 清算环节若还有一次性分派（未被逐期覆盖的部分），才挂清算日
    _per_sum = sum((p.get("sub_fixed_cost") or 0.0) + (p.get("sub_income") or 0.0)
                   for p in PER)
    _inc = L.get("sub_income_paid") or 0.0
    _resid = round(_inc - _per_sum, 2)
    if _fu and _resid > 0.01 and _tail:
        _fu.append((_tail, _resid))
        M["sub_income_residual"] = _resid
    elif abs(_resid) > 1.0:
        # ★ 负残差（逐期合计 **大于**清算归属）不得挂清算日，否则重复计入。
        #   实测兴瑞2021二期：逐期 11,221,327.44 vs 清算 11,201,690.26，
        #   差 −19,637.18（0.18%）——末期「证券利息总支出」里混入了非证券项。
        #   如实记录差额、不臆造归属，也不为了"配平"去改逐期金额。
        M["sub_reconcile_gap"] = _resid
        print(f"  次级收益逐期合计 {_per_sum:,.2f} 与清算归属 {_inc:,.2f} "
              f"差 {_resid:,.2f}（不挂清算日、不调整逐期）")
    M["sub_xirr"] = xirr(_fu)
    M["sub_inflow"] = sum(a for _, a in _fu if a > 0) if _fu else None
    M["sub_multiple"] = safe_div(M["sub_inflow"], (T.get("sub") or {}).get("issue"))
    M["sub_fixed_total"] = sum((p.get("sub_fixed_cost") or 0.0) for p in PER) or None
    M["sub_excess_total"] = sum((p.get("sub_income") or 0.0) for p in PER) or None
    M["sub_income_date"] = _tail if _fu else None
    if M["sen_xirr"] is not None and (T.get("senior") or {}).get("coupon"):
        M["sen_xirr_gap_bp"] = (M["sen_xirr"] - T["senior"]["coupon"]) * 10000
    return M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    a = ap.parse_args()
    P = assemble(a.proj)
    M = build_metrics(P)
    D = os.path.join(a.proj, "02_提取数据")
    json.dump(P, open(os.path.join(D, "payload.json"), "w", encoding="utf-8", newline=""),
              ensure_ascii=False, indent=1)
    json.dump(M, open(os.path.join(D, "metrics.json"), "w", encoding="utf-8", newline=""),
              ensure_ascii=False, indent=1)

    pool, T, L, PER = P["pool"], P["tranche"], P["liquidation"], P["periods"]
    # ★ 打印全部走「先取值再格式化」并做 None 保护：
    #   各期数据完整度不一，直接对 None 用 :.4f 会崩（实测 3 期在打印阶段崩溃）。
    def _y(v):
        return "—" if v is None else f"{v/1e8:.4f}"

    def _p(v):
        return "—" if v is None else f"{v:.4%}"

    print(f"项目 {P['meta'].get('display_name')}")
    print(f"  入池 {pool.get('n_loans')} 笔 / {pool.get('n_borrowers')} 户"
          f"  本息费 {_y(pool.get('balance_total'))} 亿")
    print(f"  发行 {_y(T.get('total'))} 亿 = 优先 {_y(T['senior']['issue'])}"
          f" + 次级 {_y(T['sub']['issue'])}   票面 {T['senior'].get('coupon')}")
    print(f"  ★ 预计回收（中债） {_y(pool.get('exp_recovery_zz'))} 亿"
          f"（回收率 {_p(pool.get('exp_rec_rate_zz'))}）")
    print(f"     说明书披露（主承）{_y(pool.get('exp_recovery_sm_underwriter'))} 亿")
    print(f"  累计回收 {_y(L.get('total_recovery'))} 亿"
          f"  回收率 {_p(M.get('recovery_rate'))}  达成率 {_p(M.get('achieve_rate'))}")
    print(f"  处置费率 {_p(M.get('dispose_fee_rate'))}  费用率 {_p(M.get('fee_total_rate'))}")
    print(f"  期数 {M.get('n_periods')}  存续 {M.get('life_months')} 月")
    print(f"\n  分布维度 {len(P['dist'])} 个：{list(P['dist'].keys())}")
    print(f"  本品种无：{list(P['dist_absent'].keys())}")
    print(f"  预测现金流 {len(P['forecast_flow'])} 期")
    print("\n  数据源：")
    for k, v in P["_sources"].items():
        print(f"    {k:16s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
