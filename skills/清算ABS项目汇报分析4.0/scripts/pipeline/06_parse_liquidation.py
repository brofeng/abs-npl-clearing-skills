# -*- coding: utf-8 -*-
"""建鑫 清算数据解析（清算报告 + 专项复核说明 + 末次受托报告）

★ 招行清算资料的形态与中信不同：
1. **没有独立的「清算审计报告」PDF**。清算时的做法是：德勤出一份《专项复核说明》，
   把受托人编制的《清算报告》作为附件一起披露 —— 所以 LQREVIEW 文件里
   前 3 页是复核函、后面才是清算报告正文。中信是「LQAUDIT + LQREVIEW」两份独立文件。
2. 清算报告中「二、信托账户和**子账户**本期核算概况」用的是「子账户」写法
   （正文复用了受托报告模板），与受托报告的「分账户」不一致，两种都要认。
3. 清仓回购价格可能为 **0 元**（剩余资产已无价值），不能用 price>0 判断是否回购。
4. 清算期「本期回收」应等于整个存续期累计回收（含其他收入）。

用法：
  python 06_parse_liquidation.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2021年第2期"
"""
import argparse
import json
import os
import re
import sys

NUM = r"-?[\d,]+(?:\.\d+)?"
FIX = re.compile(r"(?<=\d)[，､](?=\d)")
DASH = ("-", "—", "－", "‐", "--", "/")


def fix(t):
    """统一走 _numfix：千分位点/逗号混用、形近字符等清洗只维护一份

    曾经每个脚本各写一套 fix，导致 06 里的 \\b 问题没跟着修（中文字符算 \\w，
    「证券450.000,000.00」里 450 前不是词边界 → 整段跳过清洗 → 本金取不到）。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _numfix import fix as _f
    return _f(t)

def ns(t):
    return re.sub(r"[\s\u3000]+", "", t or "")


def fnum(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in DASH:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def load(proj, key):
    """优先 OCR，其次直取文本"""
    od = os.path.join(proj, "02_提取数据", "OCR", f"{key}.ocr.txt")
    td = os.path.join(proj, "02_提取数据", "文本", f"{key}.txt")
    for p in (od, td):
        if os.path.exists(p) and os.path.getsize(p) > 100:
            return fix(open(p, encoding="utf-8").read()), p
    return "", None


def _money_after(t, label, span=90, idx=0):
    """取「标签 + 金额」里的第 idx 个金额（相对稳健的一招）

    ★ 为什么要单独写：OCR 会把金额的空格留在数字中间（2022四期
      `合格投资45, 081. 22`），直接把整段喂给 split_money 会被切成
      [45, 81.22] 这种碎片。做法是先把「数字之间的空格」抹掉再切。
    ★ 只取标签**右侧** span 字符，避免吃到下一行的数；`——`/`-` 视作 0。
    """
    i = (t or "").find(label)
    if i < 0:
        return None
    seg = t[i + len(label): i + len(label) + span]
    seg = re.sub(r"(?<=[\d,])\s+(?=[\d.])", "", seg)
    if re.match(r"\s*(?:[—－‐]{1,2}|--|-)\s*(?:[—－‐]{1,2}|--|-)", seg):
        return 0.0
    from _numfix import split_money
    vals = split_money(seg, idx + 1, strict=True)
    if not vals:
        vals = split_money(seg, idx + 1)
    return vals[idx] if len(vals) > idx else None


def pages_of(txt):
    out = {}
    for m in re.finditer(r"<<<PAGE (\d+)>>>(.*?)(?=<<<PAGE|\Z)", txt, re.S):
        out[int(m.group(1))] = m.group(2)
    # 有些文件没有 PAGE 标记
    if not out:
        out = {1: txt}
    return out


def parse_liquidation(proj, sen_issue=None, sub_issue=None):
    # ★ 清算文书的键位逐家不同：
    #   中信 = LQAUDIT + LQREVIEW 两份；招行 = LQREVIEW（复核函前 3 页 + 报告正文）；
    #   建行 = LQREVIEW/LQAUDIT；**兴业 = LQAUDIT（德勤版《清算财务报表及审计报告》）**。
    #   原来只找 LQREVIEW / LQ，兴业 9 单全部落空 → 直接进"降级：无清算报告"分支，
    #   清算日、资产负债表、费用明细、清算净收益全部拿不到，
    #   4 条恒等式断言只能 SKIP（而原件明明在手上）。
    txt, src = load(proj, "LQREVIEW")
    if not txt:
        txt, src = load(proj, "LQAUDIT")
    if not txt:
        txt, src = load(proj, "LQ")
    L = {"_src": os.path.basename(src) if src else None,
         "_sen_issue": sen_issue, "_sub_issue": sub_issue}
    if not txt:
        return L
    t = ns(txt)

    # ★ 体例分派：德勤版《清算财务报表及审计报告》（兴业兴瑞）与通用「清算报告」完全不同，
    #   走通用解析器会把清算日银行存款当成累计回收、费用明细只认出 3 项。
    #   ① 兴业信托版《清算报告》—— 十单都有，最稳，优先
    #   ② 只有审计报表、没有清算报告正文的（早期个别单）→ 退回德勤附注解析
    if "信托税费支出情况" in t and "证券本息兑付情况" in t:
        L["_tr_path"] = os.path.join(proj, "02_提取数据", "_trustee_parsed.json")
        L["_sen_issue"], L["_sub_issue"] = sen_issue, sub_issue
        return parse_xy_liq(t, L)
    if "清算资产负债表" in t and "业务及管理费" in t and "贷款服务报酬" in t:
        L["_tr_path"] = os.path.join(proj, "02_提取数据", "_trustee_parsed.json")
        return parse_deloitte(t, L)

    # 信托清算日 / 报告日
    # ★ 招行各期清算报告体例不统一，清算日的写法有三种：
    #   ① 「YYYY年M月D日（信托清算日）」        —— 2021 二期
    #   ② 「报告期间为：…（含该日）至 YYYY年M月D日（不含该日）」 —— 2022 一期（无"清算日"字样）
    #   ③ 只有「报告日期：YYYY年M月D日」
    #   只认①会让②③整期拿不到清算日（实测 2022 一期 liquidation_date=None）。
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(]信托清算日[）)]", t)
    if m:
        L["liquidation_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        L["liquidation_date_src"] = "信托清算日"
    else:
        m2 = re.search(r"报告期间为[：:][^。]{0,40}?至\s*(\d{4})年(\d{1,2})月(\d{1,2})日", t)
        if m2:
            L["liquidation_date"] = f"{m2.group(1)}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}"
            L["liquidation_date_src"] = "报告期间结束日"
        else:
            m3 = re.search(r"报告日期[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日", t)
            if m3:
                L["liquidation_date"] = f"{m3.group(1)}-{int(m3.group(2)):02d}-{int(m3.group(3)):02d}"
                L["liquidation_date_src"] = "报告日期"
            else:
                # ④ 末法：新体例有些不写清算日，只在正文里说
                #   「截至 YYYY年M月D日，信托账户共收到回收款…」——该日即清算基准日。
                m4 = re.search(r"截至\s*(\d{4})年(\d{1,2})月(\d{1,2})日[，,]?\s*信托账户共收到回收款", t)
                if m4:
                    L["liquidation_date"] = (f"{m4.group(1)}-{int(m4.group(2)):02d}-"
                                             f"{int(m4.group(3)):02d}")
                    L["liquidation_date_src"] = "截至日·信托账户收到回收款"
                else:
                    L["liquidation_date"] = None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(]信托设立日[）)]", t)
    L["inception_date"] = (f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                           if m else None)
    # 审计报告号 / 复核报告号
    L["review_no"] = grab(t, r"(德师报[（(]函[）)]字[（(]\d+[）)]第[A-Z0-9]+号)")
    L["audit_no"] = grab(t, r"(德师报[（(]审[）)]字[（(]\d+[）)]第[A-Z0-9]+号)")
    L["auditor"] = "德勤华永会计师事务所（特殊普通合伙）" if "德勤" in t else None

    # 清仓回购（价格可能 0 元）
    bq = {"occurred": False, "notice_date": None, "calc_date": None, "price": None}
    if "清仓回购" in t:
        bq["occurred"] = True
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[0:.：]*向受托人发送《清仓回购", t)
        bq["notice_date"] = (f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                             if m else None)
        m = re.search(r"回购起算日[为]?(\d{4})年(\d{1,2})月(\d{1,2})日", t) or \
            re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日为回购起算日", t)
        bq["calc_date"] = (f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                           if m else None)
        # ★ 两种写法：
        #   旧：「清仓回购价格为 X 元」
        #   新（2024 起）：「本信托收到发起机构转付的清仓回购价款 X 元」
        #   只认前者会让 2024 两期的回购价变成空值。
        m = re.search(r"清仓回购(?:价格|价款)(?:为)?\s*([\d,]+\.?\d*)\s*元", t) or \
            re.search(r"清仓回购价款([\d,]+\.\d{2})", t)
        bq["price"] = fnum(m.group(1)) if m else None
    L["buyback"] = bq

    # ── 体例判断：新体例（2023 起）有「费用明细」表，旧体例有「资金池现金流流入」
    if ("费用明细" in t or "信托专户剩余资金" in t) and "资金池现金流流入" not in t:
        L = parse_new_style(t, L)
        L["_style"] = "new(2023+)"
        return L

    # 清算期资金池流入：总计 本期/累计
    # ★ 这行 OCR 极易出错，原文形如 `总计350.997,548.71350,997,548.71`
    #   （两个 350,997,548.71 粘连，且第一个的千分位逗号被读成点）。
    #   只用 ([\d,]+\.\d{2}) 会先匹配到「350.99」就停，得到 350.99 而不是 3.5 亿。
    #   改用：允许数字段内含 [.,]，并要求至少 7 位数字，最后按 fix 规则归一。
    #   精确约束：千分位分组必然 ≤3 位，故用「1-3位数字 + (分隔符 + 3位数字)* + 分隔符 + 2位小数」
    #   这样 `350.997,548.71350,997,548.71` 只会吃到 `350.997,548.71`，不会把两个数连起来。
    NUMGRP = r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"
    m = re.search(r"总计\s*(" + NUMGRP + ")", t)
    if m:
        raw = m.group(1)
        L["_total_recovery_raw"] = raw
        L["total_recovery"] = fnum(fix(raw))
    if not L.get("total_recovery"):
        m = re.search(r"总计([\d,]+\.\d{2})([\d,]+\.\d{2})", t)
        if m:
            L["total_recovery"] = fnum(m.group(1))
    # ★ 建行清算报告体例：**没有「总计」这一行**，回收由三块累计相加而成。
    #   表被 OCR 压平成一行（2021年第二期实测）：
    #     `(三）资金池现金流流入 1-处置状态分布
    #      本期回收金额 累计回收金额 预计回收金额 回收率
    #      处置中资产 0.00 0.00 不适用
    #      本期处置完毕资产 1,005,994,370.28 1,005,994,370.28 不适用
    #      2-其他现金流流入 本期回收金额 累计回收金额
    #      其他收入 0.00 0.00
    #      合格投资 287,366.55 287,366.55
    #      本 1,006,281,736.83 1,006,281,736.83`      ← 合计行，"合计"被 OCR 成"本"
    #   三块相加 = 1,006,281,736.83，与合计行精确相等，故用相加而不是猜位置。
    #   招行/中信有「总计」，走上面的分支，不受影响。
    if not L.get("total_recovery"):
        # ★ 主判据：合计行。清算报告「(三)资金池现金流流入」的表尾是
        #   `本1,006,281,736.83 1,006,281,736.83`（"合计"两字被 OCR 读成"本"），
        #   本期列与累计列在清算报告里**必然相等**（一次结清），故「两个相同的数」
        #   是极强的形态特征：全表只有这一处满足。
        _tot = None
        # ★ 合计行标签的 OCR 变体：`合计`→`本`（第二期）、`本地`（第五期）。
        #   只认「本|合计」时第五期认不出合计行，连带后面的合格投资也一起丢
        #   （原实现把账户结息嵌在 `if _tot:` 里，合计缺失＝结息静默为 None）。
        for _mm in re.finditer(r"(?:本|合计|本地|总计)\s*(" + NUMGRP + r")\s*(\1)", t):
            _tot = fnum(fix(_mm.group(1)))
            break
        # ★ 校验：三项累计相加（处置完毕资产 ＋ 其他收入 ＋ 合格投资）
        #   注意标签要写成 `资(?:产)?`：OCR 会把「本期处置完毕资产」的"产"字
        #   连同下一行一并吃掉，实测只剩「本期处置完毕资」。
        #   另外 `0.000.00` 这种粘连两列会被 NUMGRP 整体吃掉，故只作校验不作主判据。
        def _cum(label):
            mm = re.search(re.escape(label) + r"\s*(-|-?[\d,]+\.\d{2})", t)
            if not mm:
                return None
            v = mm.group(1)
            return 0.0 if v.strip() == "-" else fnum(v)
        _parts = {}
        for _lab in ("本期处置完毕资", "其他收入", "合格投资"):
            _v = _cum(_lab)
            if _v is not None:
                _parts[_lab] = _v
        _sum3 = round(sum(_parts.values()), 2) if _parts else None
        if _tot:
            L["total_recovery"] = _tot
            L["total_recovery_basis"] = (
                "清算报告「资金池现金流流入」合计行（本期＝累计，一次结清）")
            if _sum3:
                L["total_recovery_check"] = {
                    "合计行": _tot, "分项相加": _sum3, "差": round(_tot - _sum3, 2),
                    "分项": {k: round(v, 2) for k, v in _parts.items()}}
        elif _sum3:
            L["total_recovery"] = _sum3
            L["total_recovery_basis"] = (
                "清算报告「资金池现金流流入」分项累计相加（合计行未识别）："
                + " ＋ ".join(f"{k} {v:,.2f}" for k, v in _parts.items()))
        # ★ 账户结息：建行清算报告叫「合格投资」（存放在银行的合格投资收益），
        #   中信/招行叫「其他收入 / 账户结息」。同一样东西三个名字，
        #   不映射就会让资金平衡恒等式缺一块，也让契约判成"取数漏项"。
        # ★ 位置很关键：**不能**嵌在 `if _tot:` 里。合计行 OCR 认不出时
        #   （第五期读成「本地」），结息会跟着一起丢，表现为契约缺
        #   payload.liquidation.account_interest，而金额其实在原文里明明白白。
        if L.get("account_interest") is None:
            _inv = _parts.get("合格投资")
            if _inv is None:
                _inv = _cum("合格投资")
            if _inv is not None:
                L["account_interest"] = _inv
                L["account_interest_basis"] = "清算报告「资金池现金流流入·合格投资」（账户结息）"
    # ★★ 账户结息兜底：**无条件执行**。
    #   上面那段三块相加只在「总计」缺位时才走，而带「总计」的清算报告
    #   （2021八期 300,118,030.12 / 2022四期 633,228,130.82 / 2023一期
    #   755,514,677.12）根本进不去 → account_interest 一直为 None，
    #   契约判成"取数漏项"，而原文「合格投资 143,861.99」明明就在表里。
    if L.get("account_interest") is None:
        _inv2 = _money_after(t, "合格投资")
        if _inv2 is not None:
            L["account_interest"] = _inv2
            L["account_interest_basis"] = "清算报告「资金池现金流流入·合格投资」（账户结息）"
    # 其他收入
    m = re.search(r"其他收入(-|[\d,]+\.\d{2})(-|[\d,]+\.\d{2})", t)
    if m:
        L["other_income"] = fnum(m.group(2))
    # 证券本金/利息支出
    # 本金兑付：清算报告的「本期兑付本金额」即末次（全额）兑付
    # ★ 该页 OCR 质量差，两档金额会**粘连成一串**：
    #   `本期兑付本金额185,000.000.0049,000.000.00` 实为
    #   185,000,000.00 与 49,000,000.00 两个数首尾相接（第一数的 ".00" 与第二数的 "49"
    #   之间丢了逗号）。用正则直接切必然错。
    #   改用**已知发行规模**做锚：从说明书/受托报告拿到两档发行额，若兑付额约等于其中之一，
    #   就认定"全额兑付"——清算报告本质上就是确认全额兑付，不必逐字抠 OCR。
    _sen_issue = L.get("_sen_issue")
    _sub_issue = L.get("_sub_issue")
    L["sen_principal_paid"] = round(_sen_issue, 2) if _sen_issue else None
    L["sub_principal_paid"] = round(_sub_issue, 2) if _sub_issue else None
    L["principal_paid_note"] = ("清算报告全文确认末次兑付后两档剩余本金值均为 0，"
                                "即全额兑付；金额取发行规模（同一交易文件，口径一致）")
    # ★ 付息金额两档并排，中间可能夹「（元）」：付息金额（元）3,159,328.36  18,357,911.23
    #   原正则要求两个数字紧邻，遇到「（元）」就整项取不到 → G3 输入契约报缺
    #   sen_interest_paid，清算报告的「证券利息总支出」恒等式也就无法配平。
    L["sen_interest_paid"] = pick(
        t, r"付息金额\s*(?:（元）|\(元\))?\s*([\d,]+\.\d{2})\s*([\d,]+\.\d{2})", 0)
    # ★ 账户数据不从清算报告取：该页 OCR 把表格压成连续文本，标签与数值粘连、
    #   还有单元格缺失（「信托账户」只识别到 3 个数），实测会算出 2.78e+27 这种数。
    #   改由 last_trustee_account() 从**末次受托报告**（文本层直取）取，可靠得多。
    L["accounts"] = None
    # 各项费用
    # ★ 科目名跨行不一致：中信叫「执行费用及执行费用利息」，建行叫「处置费用」。
    #   两者是同一位置（费用和开支大类下的一方），必须都认，否则处置费率永远为空。
    FEE = ["税收", "代理兑付费用", "发行费用", "受托机构报酬", "资金保管机构报酬",
           "执行费用及执行费用利息", "处置费用", "执行费用",
           "贷款服务机构报酬", "审计费", "跟踪评级服务费",
           "其他费用支出", "证券利息总支出", "证券本金总支出", "次级档超额收益"]
    fd = {}
    for f in FEE:
        # ★ 逐次出现试，取第一个「标签后面紧跟金额」的位置。
        #   只取 t.find(f)（第一次出现）会踩空：正文前段常先出现一次不带金额的表述
        #   （如「审计费由受托人承担」），后面 40 字不是数字 → 该科目被整项丢掉。
        #   实测 建鑫2021年第二期 审计费 200,000.00 因此缺失。
        key = ns(f)
        start = 0
        while True:
            i = t.find(key, start)
            if i < 0:
                break
            seg = t[i + len(key):i + len(key) + 40]
            m = re.match(r"(-|—|[\d,]+\.\d{2})", seg)
            if m:
                # ★ 破折号 = 该科目本期为 0，**不是"未披露"**。
                #   受托报告把零值科目写成「贷款服务机构报酬—」，
                #   原实现 fnum("-") 返回 None → 该科目从 fd 里消失 →
                #   下游 fee_detail 缺「贷款服务费」→ G3 输入契约判成取数漏项，
                #   整份断言跑不起来（建鑫2023四期实测）。
                _g = m.group(1)
                fd[f] = 0.0 if _g.strip() in DASH else fnum(_g)
                break
            start = i + len(key)
    L["outflow_detail"] = fd
    # 次级档收益 = 次级档超额收益（清算报告「资产池现金流出」科目）
    L["sub_income_paid"] = fd.get("次级档超额收益")
    # ★ 优先档利息兜底（与 2023+ 新体例那段同一条规则）：
    #   「付息金额（元）」那行两档并排，OCR 常只识出一个数 → sen_interest_paid 为 None。
    #   同一页的「证券利息总支出」就是这笔钱，直接补上；
    #   否则契约缺 payload.liquidation.sen_interest_paid（建鑫2021八期实测）。
    if L.get("sen_interest_paid") is None and fd.get("证券利息总支出") is not None:
        L["sen_interest_paid"] = fd["证券利息总支出"]
        L["sen_interest_basis"] = "清算报告「资产池现金流出·证券利息总支出」（付息金额行未识别）"
    # 处置费率分子：执行费用（中信口径）/ 处置费用（建行口径）
    #   ★ 两行名称不同但同位：都是「费用和开支」大类下的处置环节成本。
    #   建行清算报告的「处置费用」是单列科目（不等于贷款服务报酬之和，
    #   建鑫2021-1：处置费用 61,433,367.10 ≠ 贷款服务报酬 49,235,988.79），
    #   故直接取该科目值，不做加总。
    # ★ 三家叫法不同：中信「执行费用及执行费用利息」/ 建行「处置费用」/
    #   兴业「执行费用」。三选一，缺一个处置费率就恒为 None。
    L["dispose_exec_fee"] = (fd.get("执行费用及执行费用利息")
                             if fd.get("执行费用及执行费用利息") is not None
                             else (fd.get("处置费用")
                                   if fd.get("处置费用") is not None
                                   else fd.get("执行费用")))
    if L["dispose_exec_fee"] is not None and "处置费用" in fd \
            and "执行费用及执行费用利息" not in fd:
        L["dispose_fee_basis"] = ("清算报告「资产池现金流出」单列科目「处置费用」"
                                  "（含贷款服务机构报酬/审计费等处置环节支出，"
                                  "与中信「执行费用及执行费用利息」为不同科目的同名口径）")
    L["servicer_fee"] = fd.get("贷款服务机构报酬")
    return L


def last_trustee_account(proj):
    """从末次受托机构报告取清算前账户状况（文本层直取，比清算报告 OCR 可靠）

    清算报告里同一张表被 OCR 压成连续文本，标签与数值粘连，无法可靠切分；
    末次受托报告的同一张表有文本层，逐行清晰。
    """
    tdir = os.path.join(proj, "02_提取数据", "文本")
    idxp = os.path.join(proj, "02_提取数据", "_text_index.json")
    if not os.path.exists(idxp):
        return None
    idx = json.load(open(idxp, encoding="utf-8"))
    trs = sorted([r for r in idx if re.match(r"^TR\d+$", r["key"])],
                 key=lambda r: int(r["key"][2:]))
    if not trs:
        return None
    last = trs[-1]["key"]
    p = os.path.join(tdir, f"{last}.txt")
    if not os.path.exists(p):
        return None
    txt = fix(open(p, encoding="utf-8").read())
    pages = pages_of(txt)
    # ★ 定位**正文页**而不是目录页：
    #   受托报告的 p2 是目录，同样含「信托账户和分账户本期核算概况」字样，
    #   直接按关键词找页会命中目录（实测 accounts={}），必须叠加「账户名称」表头才认。
    pg = None
    for k in sorted(pages):
        v = ns(pages[k])
        if (("信托账户和分账户本期核算概况" in v or "信托账户和子账户本期核算概况" in v)
                and "账户名称" in v):
            pg = k
            break
    if pg is None:
        return None
    lines = [x.strip() for x in pages[pg].splitlines() if x.strip()]
    acc = {}
    LABELS = ("信托账户", "1-信托收款账", "2-信托付款账",
              "3-信托（流动性）储备账户")
    # ★ 只认「行内容与标签完全相等」的行，不能用 startswith：
    #   「二、信托账户和分账户本期核算概况：」「总信托账户本期现金流入」都以「信托账户」开头，
    #   用 startswith 会取到表头行，导致账户数据全空（实测 accounts={}）。
    for lab in LABELS:
        key = ns(lab)
        for i, l in enumerate(lines):
            if ns(l) != key:
                continue
            vals = []
            for j in range(i + 1, min(i + 12, len(lines))):
                v = lines[j].strip()
                if re.fullmatch(NUM, v) or v in DASH:
                    vals.append(fnum(v))
                elif vals:                     # 已取到数又遇到非数 → 本行结束
                    break
                else:
                    continue                   # 还没取到数，跳过页眉页脚等噪声
                if len(vals) >= 4:
                    break
            if len(vals) >= 4:
                acc[lab] = vals
            break
    return {"source": f"{last}（末次受托机构报告）", "accounts": acc,
            "main": acc.get("信托账户")}


def _last_trustee_text(proj):
    """末次受托机构报告的合并文本（去空白），用于取表下注释类信息"""
    idxp = os.path.join(proj, "02_提取数据", "_text_index.json")
    if not os.path.exists(idxp):
        return ""
    idx = json.load(open(idxp, encoding="utf-8"))
    trs = sorted([r for r in idx if re.match(r"^TR\d+$", r.get("key", ""))],
                 key=lambda r: int(r["key"][2:]))
    if not trs:
        return ""
    last = trs[-1]["key"]
    for sub, fn in (("文本", last + ".txt"), ("OCR", last + ".ocr.txt")):
        p = os.path.join(proj, "02_提取数据", sub, fn)
        if os.path.exists(p):
            return ns(fix(open(p, encoding="utf-8").read()))
    return ""


def fill_from_trustee_and_events(proj, L, sen_i=None, sub_i=None):
    """无清算报告时的降级补全（「清仓回购型」）

    ★ 适用场景（实测建鑫2021年第1期）：
      该项目 2021-09-26 已清仓回购、两档本金全部兑付完毕，但中债官网
      **至今没有清算报告**（清算文书 0 份）。第 6 期末信托付款账户仍挂
      19,500,000.00 元预留款，附注「预留执行费用及清算审计费，
      **将于收到收费文件后支付**」→ 清算未结账，故无清算报告。

    ★ 补什么、不补什么：
      可补（有据）：清算/终止日、累计回收、两档本金与利息兑付、费用明细、清仓回购
      不补（真缺）：清算日持有人权益、增值税总额、清算期结息/其他收入
      这三项在报告里一律显示「—」，不填 0 —— 0 会被读成「真的没有」。

    ★ 口径差异必须落痕（写进 total_recovery_basis）：
      17 期的累计回收取自**清算报告**（含清算期结息）；本期取自
      **受托机构报告逐期「本期回收金额」累加**，口径略窄，但可交叉验证：
      逐期累加 = 末次受托报告「总计·累计回收金额」，两者精确相等。
    """
    tp = os.path.join(proj, "02_提取数据", "_trustee_parsed.json")
    if not os.path.exists(tp):
        return L
    T = json.load(open(tp, encoding="utf-8"))
    PER = T.get("periods") or []
    if not PER:
        return L

    # ① 证券终结日 = 两档本金都归零的那一期支付日（优先取最早满足的）
    zero_dt = None
    for p in PER:
        if (p.get("sen_balance_after") is not None
                and p.get("sub_balance_after") is not None
                and abs(p["sen_balance_after"]) < 1.0
                and abs(p["sub_balance_after"]) < 1.0):
            zero_dt = p.get("pay_date")
            break
    if L.get("liquidation_date") is None and zero_dt:
        L["liquidation_date"] = zero_dt
        L["_liq_date_basis"] = "两档本金同时归零的支付日（受托机构报告）"

    # ② 累计回收：**优先末次报告的「总计·累计回收金额」**，逐期累加只作校验
    #
    #   ★ 为什么不用逐期累加（建鑫2021-1 实测）：
    #     末期「本期回收金额」被 OCR 多读了 50,000（11,567,078.89 应为 11,517,078.89），
    #     而末次「累计」与各期增量完全自洽（逐期差 0.00）。累加会把这一笔错误放大进合计。
    #     累计列是发行人自报的权威值，逐期只是它的分解。
    rec = round(sum((p.get("recovery_this") or 0.0) for p in PER), 2)
    rep_cum = PER[-1].get("recovery_cum")
    if L.get("total_recovery") is None and (rep_cum or rec):
        L["total_recovery"] = round(rep_cum, 2) if rep_cum else rec
        L["total_recovery_basis"] = (
            ("受托机构报告·末次「总计·累计回收金额」（权威）"
             if rep_cum else "受托机构报告逐期「本期回收金额」累加")
            + (f"；逐期累加 {rec:,.2f}，差 {rec - rep_cum:+,.2f}"
               + ("（OCR 末期本期数偏差，以累计为准）" if abs(rec - rep_cum) >= 1 else "（一致）")
               if rep_cum else ""))
    # ③ 账户结息（合格投资 / 其他收入）：存续中单没有清算报告，只能从受托报告取
    if L.get("account_interest") is None:
        _qi = PER[-1].get("qualified_inv_cum")
        if _qi:
            L["account_interest"] = round(_qi, 2)
            L["account_interest_basis"] = (
                "末次受托机构报告「资金池现金流流入·合格投资·累计」（账户结息）")

    # ③ 两档本息兑付累计
    if L.get("sen_principal_paid") is None:
        L["sen_principal_paid"] = round(sum((p.get("sen_principal") or 0.0) for p in PER), 2)
    if L.get("sub_principal_paid") is None:
        L["sub_principal_paid"] = round(sum((p.get("sub_principal") or 0.0) for p in PER), 2)
    if L.get("sen_interest_paid") is None:
        L["sen_interest_paid"] = round(sum((p.get("sen_interest") or 0.0) for p in PER), 2)
    # 清算报告的 sub_income_paid 是「次级档超额收益」，不含固定资金成本；
    # 这里同样只取超额收益，保证与 17 期同口径
    if L.get("sub_income_paid") is None:
        L["sub_income_paid"] = round(sum((p.get("sub_income") or 0.0) for p in PER), 2)

    # ④ 费用明细：逐期「资产池现金流出」费用科目累加
    #    ★ 与 17 期口径不同（17 期取清算报告的费用明细，本期取受托报告逐期），
    #      已在 fee_basis 写明；处置费率的分子仍是「执行费用及执行费用利息」，可比。
    FEE = ["税收", "代理兑付费用", "发行费用", "受托机构报酬", "资金保管机构报酬",
           "执行费用及执行费用利息", "处置费用", "执行费用",
           "贷款服务机构报酬", "审计费", "跟踪评级服务费",
           "其他费用支出", "律师费", "评级服务费", "承销报酬", "发行登记服务费"]
    if not (L.get("outflow_detail")):
        fd = {}
        for f in FEE:
            # ★ 「披露了但金额为 0」与「没这一项」必须区分：
            #   受托报告该格写「—」（本期无发生），parse_outflow 记 0.0；
            #   若按 `if v:` 过滤，0 会被丢掉，fee_detail 里就没有「贷款服务费」，
            #   契约判成取数漏项（建鑫2023四期实测：8 期该科目全是「—」，
            #   合计 0.00 被丢 → payload.liquidation.fee_detail.贷款服务费 缺失）。
            _present = any(f in (p.get("outflow") or {}) for p in PER)
            v = sum(((p.get("outflow") or {}).get(f) or 0.0) for p in PER)
            if v or _present:
                fd[f] = round(v, 2)
        if fd:
            L["outflow_detail"] = fd
            L["fee_basis"] = "受托机构报告逐期「资产池现金流出」费用科目累加"
            L["dispose_exec_fee"] = (fd.get("执行费用及执行费用利息")
                                     if fd.get("执行费用及执行费用利息") is not None
                                     else (fd.get("处置费用")
                                           if fd.get("处置费用") is not None
                                           else fd.get("执行费用")))

    # ⑤ 清仓回购：从「重大事件报告书」（ZDSJ）取事实，价款取末期末期回收
    if not (L.get("buyback") or {}).get("occurred"):
        bq = {"occurred": False}
        zp = os.path.join(proj, "02_提取数据", "文本", "ZDSJ.txt")
        if os.path.exists(zp):
            z = ns(fix(open(zp, encoding="utf-8").read()))
            if "清仓回购" in z:
                # 只有「6.清仓回购 / 是」这种勾选才算发生；正文提及不算
                if re.search(r"6\.清仓回购\s*是", z) or "清仓回购事宜" in z:
                    bq["occurred"] = True
                    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日向受托人发送《清仓回购通知书》", z)
                    if m:
                        bq["notice_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    m = re.search(r"确认(\d{4})年(\d{1,2})月(\d{1,2})日为(?:清仓)?回购起算日", z)
                    if m:
                        bq["calc_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日将清仓回购价款转付", z)
                    if m:
                        bq["pay_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    bq["_src"] = "重大事件报告书"
                    # 回购起算日**不在**重大事件报告书里，只在末次受托报告
                    # 「资产池现金流出情况」表下的注里（实测原句：
                    #  「注：发起机构于2021年9月7日…确认2021年9月1日为回购起算日。」）
                    if not bq.get("calc_date"):
                        z2 = _last_trustee_text(proj)
                        m = re.search(r"确认(\d{4})年(\d{1,2})月(\d{1,2})日为(?:清仓)?回购起算日", z2)
                        if m:
                            bq["calc_date"] = (f"{m.group(1)}-{int(m.group(2)):02d}-"
                                               f"{int(m.group(3)):02d}")
                            bq["_src"] = "重大事件报告书 + 末次受托机构报告附注"
                    # 回购价款：清仓回购当期（末期）的「本期回收金额」
                    #   末期「处置中」为 -、「本期处置完毕」= 本期回收全額，
                    #   即回购价款；与「累计回收」差额 58,723.20 是其他收入（结息），不属回购
                    # ★ 优先取报告**明示**的价款：兴业（兴瑞）末次受托报告写
                    #   「确认清仓回购价款为322,969.87元」，而末期「处置完毕·本期回收」
                    #   是 9,151,130.07（含回购后继续清收的部分），两者不是一回事。
                    #   用后者会把回购价款放大 28 倍。
                    _z2 = _last_trustee_text(proj)
                    _m = re.search(r"清仓回购价款为([\d,\.]+)元", _z2)
                    if _m:
                        bq["price"] = fnum(fix(_m.group(1)))
                        bq["price_basis"] = "末次受托报告「确认清仓回购价款为…元」"
                    elif PER:
                        bq["price"] = round(PER[-1].get("recovery_this") or 0.0, 2)
                        bq["price_basis"] = "末次受托报告「本期处置完毕·本期回收金额」"
        L["buyback"] = bq

    # ★ 只有「真的没有清算文书」才标降级。兴业有德勤版清算报告，
    #   若照原样无条件打标，报告会写成"无清算报告，按末次受托机构报告降级补全"，
    #   与事实相反（原件就在手上）。
    if not L.get("_has_liq_doc"):
        L["_degraded"] = "无清算报告，按末次受托机构报告 + 重大事件报告书降级补全"
    return L


def _amt_after(t, label, span=60):
    """取「标签后紧跟的第一个金额」。

    ★ 与 _money_after 的区别：_money_after 用 split_money 做「粘连串切分」，
      适合一格里有多个数要按位置取的场景；这里是「标签唯一、只要紧邻那个数」，
      用最朴素的匹配反而不容易吃到下一行的数（附注表是「科目名一行、金额一行」）。
    """
    i = (t or "").find(label)
    if i < 0:
        return None
    seg = t[i + len(label): i + len(label) + span]
    m = re.match(r"[^\d]{0,8}?(\d[\d,]*\.\d{2})", seg)
    if not m:
        return None
    return fnum(fix(m.group(1)))


def parse_deloitte(t, L):
    """德勤版《清算财务报表及审计报告》—— 兴业（兴瑞）专用体例

    ★ 为什么必须单独写一套：兴瑞 10 单的清算文书是**德勤出的清算财务报表及审计报告**
      （审计报告 3 页 + 清算资产负债表 + 清算利润及利润分配表 + 清算事项说明），
      与中信/建行/招行的「清算报告」体例逐项不同：

      | 项 | 通用清算报告 | 德勤版 |
      |---|---|---|
      | 累计回收 | 「资金池现金流流入·总计」 | **没有这张表** → 只能取末次受托报告 |
      | 费用 | 「费用和开支」账户逐项 | 「业务及管理费」附注 9 项 + 「税金及附加」附注 |
      | 权益 | 清算净收益留存为权益 | 净收益**当期全额分配**给两档持有人，期末权益 = 0 |
      | 科目名 | 执行费用及执行费用利息 / 处置费用 | **执行费用 / 贷款服务报酬 / 托管费 / 代理机构报酬 / 发行费** |

    ★ 三处会让通用解析器算出\"看着对其实错\"的数（实测兴瑞2023七期）：
      ① total_recovery 取成 560,000（那是清算日银行存款，被当成「合计」）；
      ② sen_interest_paid / sub_income_paid / fees_total 全空；
      ③ fee_detail 只认出 3 项且「审计费」取成 110,000（那是应付未付额，不是发生额）。
    """
    # ── ⓿ 清算日 ────────────────────────────────────────────────────
    # ★ 必须在这里定死：否则 main 会退回「两档本金同时归零的支付日」（2024-06-26），
    #   而德勤报告的信托清算日是 **2024-07-30**（多出 5 周的清算期费用与计息）。
    #   两者差 34 天，XIRR 与费用率都会跟着漂。
    _m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(]信托清算日", t)
    if _m:
        L["liquidation_date"] = (f"{_m.group(1)}-{int(_m.group(2)):02d}-"
                                 f"{int(_m.group(3)):02d}")
        L["liquidation_date_src"] = "德勤清算报告「YYYY年M月D日（信托清算日）」"
    L["liquidation_end"] = L.get("liquidation_date")

    # ── ① 清算资产负债表（期末列；清算开始日列为空 ⇒ 0）───────────────
    _res = _amt_after(t, "负债及净资产总计")
    if _res is not None:
        L["residual_asset"] = _res
        L["residual_asset_basis"] = "清算资产负债表「负债及净资产总计」"
    _cash_end = _amt_after(t, "银行存款")
    if _cash_end is not None:
        L["cash_end_liq"] = _cash_end
    # 权益：德勤表里「未分配利润」期末为空（净收益已全额分配）→ 0
    L["holder_equity_end"] = 0.0
    L["holder_equity_basis"] = ("清算资产负债表「净资产合计」为空（清算净收益已全额分配给"
                                "两档持有人），按 0 记；与「净收益−已分配=0」互相印证")
    L["cash_begin"] = 0.0
    L["liab_at_begin_total"] = 0.0
    L["liab_at_begin_basis"] = ("清算资产负债表「清算开始日」列全部为空"
                                "（信托设立日无银行存款、无应付款项），按 0 记")
    # 期末应付：优先取附注 1「应付款项」合计，取不到退回资产负债表「负债合计」
    _liab = _amt_after(t, "应付评级费") if "应付评级费" in t else None
    if _liab is not None:
        # 附注顺序是 应付审计费 → 应付评级费 → 合计，取「合计」那格
        _i = t.find("应付评级费")
        m = re.search(r"合计(\d[\d,]*\.\d{2})", t[_i:_i + 120])
        if m:
            _liab = fnum(fix(m.group(1)))
    if _liab is None:
        _liab = _amt_after(t, "负债合计")
    L["liab_at_end_total"] = _liab
    L["liab_at_end_basis"] = "清算事项说明五·1 应付款项合计（应付审计费＋应付评级费）"

    # ── ② 清算利润及利润分配表 ────────────────────────────────────────
    _gain = _amt_after(t, "净利润")
    if _gain is not None:
        L["liquidation_gain"] = _gain
    _dist = 0.0
    for _lb in ("归属于优先级资产支持证券持有人收益", "归属于次级资产支持证券持有人收益"):
        _v = _amt_after(t, _lb)
        if _v:
            _dist += _v
    L["liquidation_distributed"] = round(_dist, 2)
    L["liquidation_distributed_basis"] = ("清算利润及利润分配表「利润分配」：归属于优先档＋"
                                          "次级档持有人收益，当期全额分配，故期末未分配利润为 0")

    # ── ③ 业务及管理费 9 项（附注 3）────────────────────────────────
    _bi = t.find("贷款服务报酬")
    fee, _tot_bm = {}, None
    if _bi >= 0:
        blk = t[_bi - 60:_bi + 520]
        for _lb in ("贷款服务报酬", "执行费用", "评级费", "审计费", "律师费",
                    "受托机构报酬", "发行费", "代理机构报酬", "托管费"):
            _v = _amt_after(blk, _lb)
            if _v is not None:
                fee[_lb] = _v
        _tot_bm = _amt_after(blk, "合计")
    # 税金及附加（附注 4）
    _tax = None
    if "城建税" in t:
        _ti = t.find("城建税")
        _tax = _amt_after(t[_ti - 40:_ti + 260], "合计")

    # 映射到 08 认得的**标准科目名**（多一层不认，fee_detail["处置费"] 就会是 None）
    od = {}
    if fee:
        od["执行费用及执行费用利息"] = fee.get("执行费用")
        od["贷款服务机构报酬"] = fee.get("贷款服务报酬")
        od["受托机构报酬"] = fee.get("受托机构报酬")
        od["资金保管机构报酬"] = fee.get("托管费")
        od["代理兑付费用"] = fee.get("代理机构报酬")
        od["发行费用"] = fee.get("发行费")
        od["审计费"] = fee.get("审计费")
        # 评级费＋律师费在德勤表里分列，通用口径并入「其他费用支出」
        _other = (fee.get("评级费") or 0.0) + (fee.get("律师费") or 0.0)
        od["其他费用支出"] = round(_other, 2) if _other else None
    if _tax is not None:
        od["税收"] = _tax
    od = {k: v for k, v in od.items() if v is not None}
    if od:
        L["outflow_detail"] = od
        L["fee_basis"] = "清算事项说明五·3 业务及管理费（9 项）＋ 五·4 税金及附加"
    if _tot_bm is not None:
        L["fees_total"] = round(_tot_bm + (_tax or 0.0), 2)
        L["fee_total_includes_dispose"] = True
    L["dispose_exec_fee"] = fee.get("执行费用")
    L["dispose_fee_basis"] = "业务及管理费·执行费用"

    # ── ④ 增值税：受托报告「税收」科目 = 增值税 ＋ 税金及附加 ─────────────
    #   德勤表把增值税单列在「税项」文字说明里（按 3% 征收率），金额只能由
    #   逐期受托报告的「税收」减去「税金及附加」反推。不单列的话，
    #   资金平衡左端会整整多出增值税那 5 万多（120M 级项目约占 4.6bp）。
    _vat = None
    try:
        _tp = os.path.join(os.path.dirname(os.path.abspath(L.get("_proj") or "")),
                           "_trustee_parsed.json")
        _tp = L.get("_tr_path") or _tp
        if os.path.exists(_tp):
            _T = json.load(open(_tp, encoding="utf-8"))
            _tax_all = sum(((p.get("outflow") or {}).get("税收") or 0.0)
                           for p in (_T.get("periods") or []))
            if _tax_all and _tax is not None and _tax_all - _tax > 0.5:
                _vat = round(_tax_all - _tax, 2)
    except Exception:
        _vat = None
    if _vat is not None:
        L["vat_total"] = _vat
        L["vat_included_in_fees"] = False
        L["vat_basis"] = ("逐期受托报告「税收」合计 − 清算报告「税金及附加」合计"
                          "（差额为增值税，按 3% 征收率）")

    # ── ⑤ 两档本金与收益（六、资产支持证券持有人本金和收益的清偿说明）──────
    _pi = t.find("优先档资产支持证券持有人本金和收益")
    if _pi >= 0:
        from _numfix import split_money
        _vals = split_money(t[_pi:_pi + 260], 6)
        if len(_vals) >= 5:
            L["sen_principal_paid"] = _vals[0]
            L["sen_interest_paid"] = _vals[1]
            L["sub_principal_paid"] = _vals[2]
            L["sub_income_paid"] = _vals[3]
            L["principal_paid_basis"] = ("清算报告「六、持有人本金和收益的清偿说明」"
                                         "（本金/收益分列，按档分列）")

    # ── ⑥ 账户结息：德勤「利息收入」是信托账户资金孳息，**不是独立现金流入**
    #   ★ 实测：把 58,888.75 计入资金平衡左端，残差就正好多出 58,888.75；
    #     因为这笔利息对应的现金本金已经包含在「回收」里。
    #     故 account_interest 记 0 并单列 interest_income 披露金额。
    # ★ 不能用 _amt_after：会计政策段有一句「利息收入 银行存款利息收入按照实际
    #   利率法逐日计提」，标签后面跟的是正文不是金额，取到的会是下一个数（None）。
    #   改用「标签紧跟金额」的正则直接定位到附注 2 那一行。
    _m = re.search(r"银行存款利息收入(\d[\d,]*\.\d{2})", t)
    if _m:
        L["interest_income"] = fnum(fix(_m.group(1)))
    L["account_interest"] = 0.0
    L["account_interest_basis"] = (
        "德勤版「利息收入」系信托账户资金孳息，对应现金已含在回收中，"
        "非独立流入；金额另见 interest_income，不计入资金平衡左端")

    # ── ⑦ 清仓回购价款（清算说明正文）──────────────────────────────
    m = re.search(r"清仓回购价格为人民币([\d,\.]+)元", t)
    if m:
        _raw = m.group(1)
        # OCR 会把千分位写成点号（322.969.87），先按「三位一组」还原
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+\.\d{2}", _raw):
            _raw = _raw.replace(".", "")[:-2] + "." + _raw[-2:]
        _p = fnum(fix(_raw))
        if _p:
            L["buyback_inflow"] = _p
            L["buyback_inflow_basis"] = "清算事项说明六·清仓回购价格"
    L["_has_liq_doc"] = True
    return L


def _norm_amount(raw):
    r"""把 OCR 出来的金额串归一成 float

    ★ OCR 的千分位符号是**乱的**：同一个文件里同时出现
        `285，522,082.71`（全角逗号）
        `37.409,540.54`（点号当千分位、逗号当小数点）
        `223.000.000,00`（点号千分位）
        `53，753,995.89`
      规则只有一条靠得住：**最后一个分隔符后面若正好两位数字，那就是小数点**，
      其余分隔符一律是千分位。按这条规则全部能对上（已逐笔核对到分）。
    """
    if raw is None:
        return None
    raw = str(raw).replace("，", ",").replace("．", ".").replace("。", ".")
    raw = re.sub(r"[^\d.,]", "", raw)
    if not raw:
        return None
    i = max(raw.rfind("."), raw.rfind(","))
    if i > 0 and len(raw) - i - 1 == 2:
        ip, dp = raw[:i], raw[i + 1:]
    else:
        ip, dp = raw, None
    digits = re.sub(r"\D", "", ip)
    if not digits:
        return None
    return float(digits + ("." + dp if dp else ""))


def _grab_amt(t, pat):
    m = re.search(pat + r"[^\d]{0,10}([\d,.\uff0c]+)", t)
    return _norm_amount(m.group(1)) if m else None


def parse_xy_liq(t, L):
    """兴业信托版《清算报告》（十单通用骨架）

    ★ 十单的清算文书里**都有**这一份，《兴瑞…不良资产证券化信托清算报告》，
      由兴业国际信托编制，体例固定：

        二、信托财产收益情况  收回基础资产回收款 X ＋ 投资净收益 Y ＝ 信托收入合计 Z
        三、信托税费支出情况  税费/资产服务机构报酬/受托机构报酬/资金保管机构保管费/
                              执行费用及执行费用利息/代理兑付费/其他费用 ＝ 合计
        四、证券本息兑付情况  各档本金 X 全部偿付；优先档利息 Y；次级利息 Z；合计本息 W
        五、剩余信托财产及返还情况

      这几段是**散文式行文**（不是表格），OCR 后依然可读，比表格式的资产负债表稳得多。
      德勤/毕马威两家的审计报表只是附件，附注科目名逐家不同（「业务及管理费」vs
      「营业费用」），拿它当主取数源会一单一个写法；本函数以清算报告为主动脉。

    ★ 资金平衡在这里能精确闭合到 0.00（实测 2023七期、2023二期）：
        回收 ＋ 投资净收益 − 费用合计 − 证券本息 ＝ 权益
      因为清算报告是**收付实现**口径，费用合计已含全部税费（含增值税），不再另行扣减。
    """
    # 清掉页标记，否则「合计…026.093<<<PAGE 23>>>元」会把页码吃进金额
    t = re.sub(r"<<<PAGE \d+>>>", "", t)

    # 清算日 / 报告期（清算报告正文首页写「YYYY年MM月DD日（信托清算日）」）
    _m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(]信托清算日", t)
    if _m:
        L["liquidation_date"] = (f"{_m.group(1)}-{int(_m.group(2)):02d}-"
                                 f"{int(_m.group(3)):02d}")
        L["liquidation_date_src"] = "兴业信托《清算报告》「YYYY年MM月DD日（信托清算日）」"
        L["liquidation_end"] = L["liquidation_date"]

    rec = _grab_amt(t, r"基础资产回收款[^\d]{0,10}")
    if not rec:
        rec = _grab_amt(t, r"收回基础资产回收款[^\d]{0,10}")
    net_inv = _grab_amt(t, r"投资净收益")
    tot_inc = _grab_amt(t, r"信托收入合计")
    if rec is not None:
        L["total_recovery"] = rec
        L["total_recovery_basis"] = ("清算报告「二、信托财产收益情况·收回基础资产回收款」"
                                     "（收付实现口径，已含清仓回购价款）")
    if net_inv is not None:
        L["account_interest"] = net_inv
        L["account_interest_basis"] = "清算报告「二、信托财产收益情况·投资净收益」"
    if tot_inc is not None:
        L["income_total_liq"] = tot_inc
        if rec is not None and net_inv is not None:
            L["income_check"] = {"合计": tot_inc, "回收": rec, "投资净收益": net_inv,
                                 "差": round(tot_inc - rec - net_inv, 2)}

    # ── 三、信托税费支出情况（8 项散文，逐项取名）────────────────────
    ITEMS = [("税费", r"支付税费"), ("资产服务机构报酬", r"资产服务机构报酬"),
             ("受托机构报酬", r"受托机构报酬"),
             ("资金保管机构保管费", r"资金保管机构保管费"),
             ("执行费用及执行费用利息", r"执行费用及执行费用利息"),
             ("代理兑付费", r"代理兑付费"), ("其他费用", r"其他费用"),
             ("发行费", r"发行费")]
    # ★ 必须限定在这两段之间取数：同一份文件后面的审计附注里也有「发行费20,000.00」
    #   「执行费用」等字样，全文搜索会把附注的数也算进清算报告的费用里
    #   （实测 2023七期多算 20,000，合计从 29,660,026.09 变 29,680,026.09）。
    # ★ 必须用 rfind：审计意见段会把「三、信托税费支出情况」「四、证券本息兑付情况」
    #   作为**章节名清单**先引一遍，find 会命中那处引用，取数窗口里一个金额都没有
    #   （实测 2021二期 / 2022一期 因此整单费用为空 → 契约判漏项、断言跑不起来）。
    #   真正的正文段一定在附件清算报告里，即在引用之后。
    _i0 = t.rfind("信托税费支出情况")
    _i1 = t.find("证券本息兑付情况", _i0)
    seg = t[_i0:_i1 if _i1 > _i0 else _i0 + 1200] if _i0 >= 0 else t
    fee = {}
    for name, pat in ITEMS:
        v = _grab_amt(seg, pat)
        if v is not None:
            fee[name] = v
    # ★ 执行费用的两种写法并存：「执行费用及执行费用利息」（多数）/
    #   「执行费用」（2021二期实测）。只认前者会让处置费整项为空 →
    #   fee_detail 缺「处置费」→ 契约判漏项，断言整单跑不起来。
    #   负向断言保证不会把「执行费用及执行费用利息」的前半截当独立科目。
    if "执行费用及执行费用利息" not in fee:
        v = _grab_amt(seg, r"执行费用(?!及)")
        if v is not None:
            fee["执行费用及执行费用利息"] = v
    tot_fee = None
    if "其他费用" in fee:
        i = seg.find("其他费用")
        tot_fee = _grab_amt(seg[i:i + 200], r"合计")
    _sum_items = round(sum(fee.values()), 2) if fee else None
    # ★ 合计行 OCR 偶把页码并进数字（「29，660，026.093」），与分项相加对不上时
    #   以**分项之和**为准并留痕 —— 8 个分项各自都带「人民币…元」边界，比合计行稳。
    if _sum_items and tot_fee is not None and abs(tot_fee - _sum_items) > 0.5:
        # ★ 先试「某一项多读了位数」：清算报告的合计是**独立给出**的，
        #   拿它做闭合就能反解出最可疑那一项的正确值。
        #   实测兴瑞2024三期原文 `资金保管机构保管费人民4，704.635`（跨页断在「元」前），
        #   OCR 读成 4,704,635.00 —— 比真值 4,704.63 大 1000 倍；
        #   差额 4,704.63 与该项正好差 3 个数量级，一眼可辨。
        _diff = round(tot_fee - _sum_items, 2)
        _fix = None
        for _nm, _v in fee.items():
            _new = round(_v + _diff, 2)
            if _v > 1 and _new > 0 and 100 <= _v / _new <= 10000:
                _fix = (_nm, _v, _new)
                break
        if _fix:
            fee[_fix[0]] = _fix[2]
            _sum_items = round(sum(fee.values()), 2)
            L["fee_total_note"] = (f"{_fix[0]} {_fix[1]:,.2f}→{_fix[2]:,.2f}"
                                   f"（按「合计 − 其余分项」校正，OCR 多读位数）")
        elif abs(tot_fee - _sum_items) > 0.5:
            L["fee_total_note"] = (f"清算报告合计行 {tot_fee:,.2f}，"
                                   f"分项相加 {_sum_items:,.2f}，以分项为准")
            tot_fee = _sum_items
    if _sum_items and abs((tot_fee or 0) - _sum_items) > 0.5:
        tot_fee = _sum_items
    if tot_fee is not None:
        L["fees_total"] = tot_fee
        L["fee_total_includes_dispose"] = True
        L["fee_basis"] = "清算报告「三、信托税费支出情况」（收付实现，含税费与全部费用）"

    # 映射成 08 认的标准科目名
    MAP = {"执行费用及执行费用利息": "执行费用及执行费用利息",
           "资产服务机构报酬": "贷款服务机构报酬",
           "受托机构报酬": "受托机构报酬",
           "资金保管机构保管费": "资金保管机构报酬",
           "代理兑付费": "代理兑付费用",
           "其他费用": "其他费用支出",
           "税费": "税收",
           "发行费": "发行费用"}
    od = {MAP[k]: v for k, v in fee.items() if k in MAP}
    if od:
        L["outflow_detail"] = od
    L["dispose_exec_fee"] = fee.get("执行费用及执行费用利息")
    L["dispose_fee_basis"] = "清算报告「三、信托税费支出情况·执行费用及执行费用利息」"

    # ── 四、证券本息兑付情况 ───────────────────────────────────────
    prin = _grab_amt(t, r"各档证券本金")
    if prin is None:
        prin = _grab_amt(t, r"证券本金[^\d]{0,10}")
    sen_int = _grab_amt(t, r"优先档资产支持证券利息")
    sub_int = _grab_amt(t, r"次级资产支持证券利息")
    if sub_int is None:
        sub_int = _grab_amt(t, r"次级资产支持证券[^\d]{0,6}利息")
    tot_pay = _grab_amt(t, r"合计兑付本息")
    # 本金按说明书发行额拆档；两者之和必须等于清算报告口径的「各档本金」
    _si, _bi = L.get("_sen_issue"), L.get("_sub_issue")
    if _si and _bi and prin and abs((_si + _bi) - prin) <= 1.0:
        L["sen_principal_paid"] = round(_si, 2)
        L["sub_principal_paid"] = round(_bi, 2)
    elif prin:
        L["principal_paid_note"] = (f"清算报告「各档证券本金合计」{prin:,.2f} 元"
                                    f"与两档发行额之和 {(_si or 0)+(_bi or 0):,.2f} 不等，"
                                    f"不按比例拆分，逐档本金取受托报告逐期数据")
    if sen_int is not None:
        L["sen_interest_paid"] = sen_int
    if sub_int is not None:
        L["sub_income_paid"] = sub_int
    if tot_pay is not None:
        L["total_paid_liq"] = tot_pay
        _chk = ((L.get("sen_principal_paid") or 0) + (L.get("sub_principal_paid") or 0)
                + (sen_int or 0) + (sub_int or 0))
        if _chk:
            L["total_paid_check"] = {"合计兑付本息": tot_pay, "分项相加": round(_chk, 2),
                                     "差": round(tot_pay - _chk, 2)}
    if prin or sen_int is not None:
        L["principal_paid_basis"] = "清算报告「四、证券本息兑付情况」"

    # ── 资产负债表（德勤「清算资产负债表」/ 毕马威「资产负债表」两种抬头）──
    _res = (_grab_amt(t, r"负债及应付信托受益人权益合计")
            or _grab_amt(t, r"负债及净资产总计"))
    # ★ 顺序必须是「负债合计」优先：
    #   资产负债表里「其他应付款」后面紧跟**附注号**，OCR 会把两者粘成一串 ——
    #   实测兴瑞2023二期 `其他应付款 9 60,000.00` → 读成 960,000.00（大 16 倍）、
    #   2024三期 `其他应付款 6 60,000.00` → 660,000.00。
    #   「负债合计」那一行后面没有附注号，且与「负债及…权益合计」天然相等，
    #   拿它做校验基准最稳；两项不等时宁可不落数（恒等式记 SKIP），
    #   也绝不带着错位数去过恒等式。
    _liab = (_grab_amt(t, r"负债合计") or _grab_amt(t, r"应付款项")
             or _grab_amt(t, r"其他应付款"))
    if _res is not None and _liab is not None and abs(_res - _liab) <= 1.0:
        # 两者相等 ⇒ 期末权益为 0（净收益已全额分配），三项互相印证，可以落数
        L["residual_asset"] = _res
        L["liab_at_end_total"] = _liab
        L["cash_end_liq"] = _res
        L["holder_equity_end"] = 0.0
        L["cash_begin"] = 0.0
        L["liab_at_begin_total"] = 0.0
        L["liab_at_begin_basis"] = "资产负债表「信托清算日」列为唯一列，无期初列 ⇒ 0"
        L["holder_equity_basis"] = ("资产负债表「未分配利润 / 应付信托受益人权益合计」为空，"
                                    "净收益已全额分配 ⇒ 权益 0")
        L["residual_asset_basis"] = "资产负债表「负债及（应付信托受益人权益 / 净资产）合计」"
    elif _res is not None:
        # 两处数字对不上（OCR 噪声）→ 不硬填，恒等式记 SKIP 而不是 FAIL
        L["balance_sheet_note"] = (
            f"资产负债表两处数字不一致（合计 {_res:,.2f} / 应付款 {(_liab or 0):,.2f}），"
            f"按 OCR 噪声处理，权益类恒等式记 SKIP")

    _gain = (_grab_amt(t, r"可供分配信托利润") or _grab_amt(t, r"净利润"))
    if _gain is not None:
        L["liquidation_gain"] = _gain
    _dist = _grab_amt(t, r"已分配信托利润")
    if _dist is None:
        _d1 = _grab_amt(t, r"归属于优先级资产支持证券持有人收益")
        _d2 = _grab_amt(t, r"归属于次级资产支持证券持有人收益")
        if _d1 is not None or _d2 is not None:
            _dist = round((_d1 or 0.0) + (_d2 or 0.0), 2)
    # ★ 「已分配信托利润」同样会被附注号粘连：2024三期原文是
    #   `减：已分配信托利润 9 12,426,608.99`（9 是附注号）→ 读成 912,426,608.99。
    #   判据很简单且硬：当期分配额不可能超过可供分配利润（利润表结构决定的），
    #   超出即视为粘连，直接用可供分配利润（这两种体例都是全额分配、期末未分配为 0）。
    if _dist is not None and _gain is not None and _dist > _gain * 1.05:
        L.setdefault("_notes", []).append(
            f"已分配信托利润 {_dist:,.2f} 超过可供分配 {_gain:,.2f}，"
            f"按 OCR 附注号粘连处理，改用可供分配利润")
        _dist = _gain
    elif _dist is not None and _gain is not None and _dist < _gain * 0.5:
        # 反过来太小（如误取到个位数附注号），同样不可信
        L.setdefault("_notes", []).append(
            f"已分配信托利润 {_dist:,.2f} 明显小于可供分配 {_gain:,.2f}，按粘连处理")
        _dist = _gain
    if _dist is not None:
        L["liquidation_distributed"] = _dist
        L["liquidation_distributed_basis"] = ("利润及利润分配表「已分配信托利润」"
                                              "（当期净收益全额分配，期末未分配利润 0）")

    # 增值税：本口径「税费」已是收付实现的全部税金（含增值税），不再单列扣减
    L["vat_included_in_fees"] = True
    L["vat_total"] = fee.get("税费")

    # ── 清仓回购价款（清算报告正文）────────────────────────────────
    # ★ 兴业清算报告原句（2023七期）：
    #   「发起机构兴业银行于2024年7月8日完成清仓回购，清仓回购价格为人民币
    #     322.969.87元」——OCR 把千分位逗号读成点号（三个点号）。
    #   原先只有 parse_deloitte 解析这一段，而兴业 **10 单全部**走 parse_xy_liq，
    #   于是 buyback 一律为空：累计回收里明明含了回购价款（第七期实测
    #   120,642,030.96 ＝ 逐期回收 120,319,061.09 ＋ 回购 322,969.87），
    #   报告却无法单列"自然清收回收率"，读数的人会把回购价当成清收能力。
    def _d3(_m):
        return (f"{_m.group(1)}-{int(_m.group(2)):02d}-{int(_m.group(3)):02d}"
                if _m else None)

    _bb = re.search(r"清仓回购(?:价格|价款)(?:为)?[人民币]*\s*([\d,\.]+)\s*元", t)
    # 起算日 / 通知书日 / 价款支付日：三者在原文里各占一句，不能混用
    _bc = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*为本信托的(?:清仓)?回购日?起算日", t) or \
          re.search(r"确认(\d{4})年(\d{1,2})月(\d{1,2})日为(?:清仓)?回购日?起算日", t)
    _bn = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[^。]{0,20}《清仓回购通知书》", t)
    _bp = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*支付清仓回购价款", t) or \
          re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[^。]{0,10}完成清仓回购", t)
    if _bb:
        _raw = _bb.group(1)
        # OCR 千分位还原：322.969.87 → 322969.87
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+\.\d{2}", _raw):
            _raw = _raw.replace(".", "")[:-2] + "." + _raw[-2:]
        _bv = fnum(fix(_raw))
        if _bv is not None:
            L["buyback_inflow"] = _bv
            L["buyback_inflow_basis"] = "清算报告正文「清仓回购价格为人民币…元」"
            L["buyback_date"] = _d3(_bp)
            L["buyback"] = {"occurred": True, "price": _bv,
                            "notice_date": _d3(_bn), "calc_date": _d3(_bc),
                            "date": _d3(_bp)}
    elif "清仓回购" in t and (_bp or _bc):
        # ★ 多数单只写"发起机构于 YYYY年MM月DD日支付清仓回购价款，本信托终止"，
        #   **不写金额**（2021二期、2024三期实测如此）。此事必须记录但不得编造数字：
        #   回收率里确实含回购价款、却无法拆分，报告要如实写"金额未披露"，
        #   而不是把差额倒推成回购价（倒推会把投资收益、账户结息一并算进去）。
        # ★ 必须有「支付日或起算日」才认：正文里"含提前终止时清仓回购资产"这类
        #   泛指不算发生（2021一期实测），否则会记出一个没有任何日期的空回购块，
        #   把「起算日必存在」这条断言逼成 FAIL。
        L["buyback"] = {
            "occurred": True, "price": None,
            "notice_date": _d3(_bn), "calc_date": _d3(_bc),
            "date": _d3(_bp),
            "price_basis": "清算报告披露回购已完成，但未披露价款金额",
        }
        L["buyback_inflow_basis"] = "清算报告仅披露回购完成日，未披露价款金额（不作倒推）"

    # ★ 「累计回收」是否已含回购价款 —— 决定资金平衡公式加不加 buyback_inflow。
    #   兴业信托版清算报告的「收回基础资产回收款」**已含**回购价款
    #   （2023七期实证：120,642,030.96 ＝ 逐期处置回收 120,319,061.09 ＋ 322,969.87，
    #    且 120,642,030.96 − 逐期累计 120,377,949.84 ＝ 322,969.87 − 58,888.75 投资收益）。
    #   若再按"回收＋回购"相加，就等于把回购价款算两遍，资金平衡凭空多 32.3 万。
    L["recovery_includes_buyback"] = True

    L["_has_liq_doc"] = True
    return L
    """2023 年起体例：金谷信托 + 毕马威

    ★ 与 2021-2022（华润信托 + 德勤）完全不同：
      旧体例 = 「末次受托机构报告」，数据在「资金池现金流流入/总计」；
      新体例 = 标准清算报告，数据在「费用明细表 + 合计」与「证券本息兑付情况」段落。
      实测 2023 一期：费用明细 14 项、合计 694,697,165.46、剩余资金 2,838,474.39。
    """
    NUM2 = r"\d[\d,]*\.\d{2}"
    # ① 费用明细：科目名紧跟金额（表中无分隔）
    #   注意「执行费用」不能吃掉「执行费用利息」的数字 → 用负向断言
    FEE = ["税费", "代理兑付费用", "发行费用", "受托机构报酬", "资金保管机构报酬",
           "执行费用利息", "执行费用", "贷款服务机构报酬", "审计费",
           "跟踪评级服务费", "其他费用支出", "证券利息总支出", "证券本金总支出",
           "次级档超额收益"]
    fd = {}
    for f in FEE:
        pat = re.escape(f) + (r"(?<!利息)" if f == "执行费用" else "") + r"(" + NUM2 + r")"
        m = re.search(pat, t)
        if m:
            fd[f] = fnum(fix(m.group(1)))
    # 明细里「执行费用」与「执行费用利息」合并为「执行费用及执行费用利息」（对齐旧体例口径）
    if "执行费用" in fd or "执行费用利息" in fd:
        fd["执行费用及执行费用利息"] = round((fd.pop("执行费用", 0.0)
                                             + fd.pop("执行费用利息", 0.0)), 2)
    if "税费" in fd:
        fd["税收"] = fd.pop("税费")
    L["outflow_detail"] = fd

    # ④ 证券兑付：逐句取（新体例是叙述式）
    m = re.search(r"优先档资产支持证券(" + NUM2 + r")元.*?次级档资产支持证券(" + NUM2 + r")元", t)
    if m:
        L["sen_principal_paid"] = fnum(fix(m.group(1)))
        L["sub_principal_paid"] = fnum(fix(m.group(2)))
    m = re.search(r"兑付优先档资产支持证券利息(" + NUM2 + r")元", t)
    if m:
        L["sen_interest_paid"] = fnum(fix(m.group(1)))
    # 次级档收益：原文「…兑付次级档资产支持证券收益 6,020,541.22 元」
    #   早期正则写成「兑付次级档…本金 NUM 元，以现金形式兑付次级档…NUM 元」，
    #   因 OCR 把次级本金读成 `67.000,000.00`（千分位点）导致整段匹配失败，
    #   次级收益丢失 602 万 → 对账残差 565 万。改为直接匹配「次级档…收益…元」。
    m = (re.search(r"兑付次级档资产支持证券收益(" + NUM2 + r")元", t)
         or re.search(r"次级档资产支持证券收益(" + NUM2 + r")元", t))
    if m:
        L["sub_income_paid"] = fnum(fix(m.group(1)))
    if L.get("sub_income_paid") is None:
        L["sub_income_paid"] = fd.get("次级档超额收益")
    # ★ 优先档利息兜底：清算报告里「证券利息总支出」与「付息金额（优先档）」
    #   是同一笔钱的两个位置。付息金额那行的两档金额在 OCR 里常只剩一个
    #   （2021八期整行只识出 1 个数），取不到时用现金流出表的科目补，
    #   否则契约缺 payload.liquidation.sen_interest_paid，
    #   而「证券利息总支出 1,091,238.85」就在同一页。
    if L.get("sen_interest_paid") is None and fd.get("证券利息总支出") is not None:
        L["sen_interest_paid"] = fd["证券利息总支出"]
        L["sen_interest_basis"] = "清算报告「资产池现金流出·证券利息总支出」（付息金额行未识别）"

    # ② 费用合计（支出总额）
    m = re.search(r"合计(" + NUM2 + r")", t)
    if m:
        L["outflow_total"] = fnum(fix(m.group(1)))

    # ③ 剩余信托专户资金 → 加上支出合计 = 清算期流入
    m = re.search(r"信托专户剩余资金为(" + NUM2 + r")元", t)
    if m:
        L["cash_residual"] = fnum(fix(m.group(1)))
    # ★ 「合计」的含义逐期不同，必须区分：
    #   2023 一期：明细表 14 项，**含**「证券本金总支出 568,440,000」「证券利息总支出」，
    #              所以「合计」＝全部流出，总回收 = 合计 + 剩余资金；
    #   2023 二期：明细表 11 项，**只有费用**（税费…其他费用），
    #              合计 79,569,761.14 不含证券本息，若直接当总回收会少 3.39 亿
    #              （正好是本金+利息+次级收益之和）。
    #   判据：明细里有没有「证券本金总支出」。
    _has_sec_in_fee = "证券本金总支出" in fd
    if L.get("outflow_total") is not None:
        _base = L["outflow_total"]
        if not _has_sec_in_fee:
            _sec = sum((L.get(k) or 0.0) for k in
                       ("sen_principal_paid", "sen_interest_paid",
                        "sub_principal_paid", "sub_income_paid"))
            _base = round(_base + _sec, 2)
            L["sec_paid_added"] = round(_sec, 2)
        L["outflow_total_all"] = _base
        L["total_recovery"] = round(_base + (L.get("cash_residual") or 0.0), 2)
        L["total_recovery_basis"] = (
            ("费用明细合计 ＋ 剩余信托专户资金" if _has_sec_in_fee
             else "费用明细合计 ＋ 证券本息兑付 ＋ 剩余信托专户资金"))


    # ⑤ 费用合计 = 各项支出之和（含证券本息、次级收益）
    if fd:
        L["fees_total"] = round(sum(v for k, v in fd.items()
                                    if k not in ("证券利息总支出", "证券本金总支出",
                                                 "次级档超额收益")), 2)
    return L


def grab(t, pat):
    m = re.search(pat, t)
    return m.group(1) if m else None


def pick(t, pat, idx):
    m = re.search(pat, t)
    if not m:
        return None
    g = m.groups()
    return fnum(g[idx]) if idx < len(g) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    a = ap.parse_args()
    # 先拿到两档发行规模，再解析清算报告（本金兑付要锚定它）
    sen_i = sub_i = None
    smp = os.path.join(a.proj, "02_提取数据", "_sm_parsed.json")
    if os.path.exists(smp):
        T = json.load(open(smp, encoding="utf-8")).get("tranche") or {}
        sen_i = (T.get("senior") or {}).get("issue")
        sub_i = (T.get("sub") or {}).get("issue")
    tp = os.path.join(a.proj, "02_提取数据", "_trustee_parsed.json")
    if os.path.exists(tp) and not sen_i:
        F = json.load(open(tp, encoding="utf-8")).get("first") or {}
        it = ((F.get("tranche") or {}).get("issue_total") or [None, None])
        sen_i, sub_i = (it + [None, None])[:2]
    L = parse_liquidation(a.proj, sen_i, sub_i)
    # ★ 无清算报告（清算文书 0 份）时降级补全：见 fill_from_trustee_and_events 的说明
    # ★ 判据改为「累计回收是否取到」：德勤版清算报告里**没有**资金池现金流表，
    #   累计回收只能来自末次受托报告；原来还要「liquidation_date 为 None」才进这段，
    #   于是兴业 10 单（清算日有值、回收无值）永远补不上，契约直接判漏项。
    #   fill_from_trustee_and_events 只填 None 的字段，已有值不会被覆盖。
    if not L.get("total_recovery"):
        L = fill_from_trustee_and_events(a.proj, L, sen_i, sub_i)
    # ★★ settlement_state：本单到底"清算完毕"还是"仍在存续"
    #
    #   为什么必须单列这个一等字段（用户要求纳入"到期未能及时兑付的"单之后暴露）：
    #   建行 24 期里，4 期根本没有清算文书（2021四/七、2023四/七），
    #   信托仍在收，次级本金兑付比例是 14.11% / 2.75% / 0% / 0%。
    #   它们的 liquidation_date / terminate_date 为 None 是**事实**，不是取数漏项；
    #   而清算类恒等式（回收对账、本金全额兑付、清算净收益）在这些单上根本不成立。
    #   若不区分，自洽检查会把"存续中"整批判成错账，报告也会写出
    #   "信托计划已终止"这种与事实相反的话。
    #
    #   判据（两条取或，都不依赖文件名）：
    #     ① 取到了清算文书（audit_no/review_no 或 liquidation_date 有值）
    #     ② 两档本金兑付比例均 ≥99.5%（清仓回购型：本金已全付、仅清算审计未结）
    _paid_ok = True
    for _cfg, _t in (("sen_principal_paid", sen_i), ("sub_principal_paid", sub_i)):
        _got = L.get(_cfg) or 0.0
        if not _t or _got < _t * 0.995:
            _paid_ok = False
    _has_doc = bool(L.get("audit_no") or L.get("review_no")
                    or L.get("liquidation_date"))
    if _has_doc or _paid_ok:
        L["settlement_state"] = "settled"
        L["settlement_basis"] = ("已取得清算文书" if _has_doc
                                 else "无清算文书，但两档本金已全额兑付（清仓回购型）")
    else:
        L["settlement_state"] = "outstanding"
        L["settlement_basis"] = (
            f"无清算文书，且本金未全额兑付（优先 {(L.get('sen_principal_paid') or 0)/max(sen_i or 1,1)*100:.2f}%"
            f"／次级 {(L.get('sub_principal_paid') or 0)/max(sub_i or 1,1)*100:.2f}%）"
            "→ 信托仍在存续，与清算期口径的恒等式不适用")
    ta = last_trustee_account(a.proj)
    if ta:
        L["accounts"] = ta["accounts"]
        L["account_source"] = ta["source"]
        if ta["main"]:
            L["cash_begin"], L["total_inflow"], L["total_outflow"], L["cash_end"] = ta["main"]
    p = os.path.join(a.proj, "02_提取数据", "_liq_parsed.json")
    # ★ 下划线开头的是内部留痕，默认不落盘；但「降级补全」的两项要留给 08 写进报告，
    #   否则报告无法说明「本单的回收/费用取自受托报告而非清算报告」。
    _keep = {"_degraded", "_liq_date_basis"}
    out = {k: v for k, v in L.items()
           if not k.startswith("_") or k in _keep}
    json.dump(out, open(p, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)
    print(f"清算日 {L.get('liquidation_date')}  设立日 {L.get('inception_date')}")
    print(f"审计 {L.get('audit_no')}  复核 {L.get('review_no')}")
    print(f"回购: {L.get('buyback')}")
    print(f"清算期回收 {L.get('total_recovery')}  其他收入 {L.get('other_income')}")
    print(f"本金兑付 优先 {L.get('sen_principal_paid')} / 次级 {L.get('sub_principal_paid')}")
    print(f"利息兑付 优先 {L.get('sen_interest_paid')}  次级超额 {L.get('sub_income_paid')}")
    print(f"账户（源：{L.get('account_source')}）:")
    for k, v in (L.get("accounts") or {}).items():
        print(f"   {k:24s} {v}")
    print(f"费用明细 {len(L.get('outflow_detail') or {})} 项：")
    for k, v in (L.get("outflow_detail") or {}).items():
        print(f"   {k:24s} {v}")
    print(f"\n→ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
