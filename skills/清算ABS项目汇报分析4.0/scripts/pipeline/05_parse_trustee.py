# -*- coding: utf-8 -*-
"""建鑫 受托机构报告解析（华润深国投信托版）

★ 与中信（中信信托）的差异：
1. 「二、信托账户和**分账户**本期核算概况」——不是中信的「子账户」。
   账户层级更多：信托账户 / 1-信托收款账户 / 2-信托付款账户 /
   （1）信托分配（税收）/（2）信托分配（费用和开支）/（3）信托分配（证券）/
   3-信托（流动性）储备账户。
2. 「四、资产池表现情况（四）资产池现金流出情况」是**科目清单式**：
   税收 / 代理兑付费用 / 发行费用 / 受托机构报酬 / 资金保管机构报酬 /
   执行费用及执行费用利息 / 贷款服务机构报酬 / 审计费 / 跟踪评级服务费 /
   其他费用支出 / 证券利息总支出 / 证券本金总支出 / 次级档超额收益 / 转存下期金额
3. 「（五）资产池现金流回收预测表」单位是**万元**（中信是元）。
4. 证券本息兑付表：证券代码 / 发行总额 / 本期兑付前本金值 / 本期兑付本金额 /
   本期兑付本息总额 / 本息兑付后剩余本金值 / 付息金额。
   注意「本息兑付后剩余本金值」是**金额**（中信是元/百元面额），本文件直接给金额。

用法：
  python 05_parse_trustee.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2021年第2期"
"""
import argparse
import itertools
import json
import os
import re
import sys

NUM = r"-?[\d,]+(?:\.\d+)?"
FIX = re.compile(r"(?<=\d)[，､](?=\d)")
DASH = ("-", "—", "－", "‐", "--", "/")
# 正则里用的「破折号占位」：表格空格常写成连续两三个破折号，要整体匹配
DASH_PAT = r"[—－‐/\-]{1,4}"


def _is_blank_cell(v):
    """表格空格：1~4 个破折号/斜杠（`—` / `——` / `---` / `—— `）

    ★ 长度不定：建行 2023 二/六期、2022 四期写「——」（两个长破折号），
      而 DASH 元组只列了单字符与 `--`，`——` 落不进任何分支 → 被当成无值跳过。
    """
    return bool(re.fullmatch(r"\s*" + DASH_PAT + r"\s*", v or ""))


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _numfix import split_money, money_at   # noqa: E402  金额粘连切分/带位置取数


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


def pages_of(path):
    t = fix(open(path, encoding="utf-8").read())
    out = {}
    for m in re.finditer(r"<<<PAGE (\d+)>>>(.*?)(?=<<<PAGE|\Z)", t, re.S):
        out[int(m.group(1))] = m.group(2)
    return out


def _date_after(path, label):
    """取「标签+YYYY年M月D日」里的日期，返回 YYYY-MM-DD；取不到返回 None"""
    try:
        t = ns(open(path, encoding="utf-8").read())
    except OSError:
        return None
    m = re.search(re.escape(label) + r"(\d{4})年(\d{1,2})月(\d{1,2})日", t)
    if not m:
        return None
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))


def section(pages, start_kw, end_kw=None, span=3):
    """按关键词定位起始页，返回到 end_kw 或 span 页的合并文本"""
    ks = [k for k in pages if start_kw in ns(pages[k])]
    if not ks:
        return ""
    k0 = ks[0]
    buf = [pages[k0]]
    for k in range(k0 + 1, min(k0 + span + 1, max(pages) + 1)):
        if end_kw and end_kw in ns(pages.get(k, "")):
            break
        buf.append(pages.get(k, ""))
    return "\n".join(buf)


# ── 信托账户（分账户）────────────────────────────────────
def parse_account(pages):
    """返回 {period, begin, inflow, outflow, end, accounts:{名称:{...}}}"""
    txt = section(pages, "信托账户和分账户本期核算概况", "三、资产支持证券概况", span=2)
    if not txt:
        txt = section(pages, "信托账户和子账户本期核算概况", "三、", span=2)
    if not txt:
        return {}
    lines = [x.strip() for x in txt.splitlines() if x.strip()]

    def nums_after(label, take=4):
        """取标签行之后的 N 个数字

        ★ OCR 出来的表格，数值有时在标签**之前**（列顺序被打乱）：
          原文 `222,049,805.45 223,163,251.66 信托账户 1,113,446.21`
          即「流入/期末/标签/期初」——按 after 取只能拿到最后 1 个数。
          故：先按 after 取；不足 take 个时，改取标签行**之前**的数字（倒序补齐）。
        """
        for i, l in enumerate(lines):
            if ns(label) == ns(l) or ns(l).startswith(ns(label)):
                vals = []
                for j in range(i + 1, min(i + 12, len(lines))):
                    v = lines[j].strip()
                    if re.fullmatch(NUM, v) or v in DASH:
                        vals.append(fnum(v))
                    elif vals:
                        break
                    if len(vals) >= take:
                        break
                if len(vals) < take:
                    pre = []
                    for j in range(i - 1, max(i - 10, -1), -1):
                        v = lines[j].strip()
                        if re.fullmatch(NUM, v) or v in DASH:
                            pre.append(fnum(v))
                        elif pre:
                            break
                        if len(pre) + len(vals) >= take:
                            break
                    # 前置数字按原顺序（反转回来）拼在 vals 前面
                    vals = list(reversed(pre)) + vals
                return vals
        return []

    def _orient(v, prev_end=None):
        """按恒等式校验并纠正「流入/流出」列序

        ★ 为什么必须做：各受托人的表格列序不同，且中债文件里没有说明。
          招行（华润/金谷）：期初 | 流入 | 流出 | 期末
          建行（建信信托）：期初 | **流出** | **流入** | 期末   ← 顺序相反
          实测建鑫2021一期原文：
            `信托账户 — 76,454,602.48 84,315,066.38 7,860,463.90`
            0 + 84,315,066.38 − 76,454,602.48 = 7,860,463.90 ✓（流入在后）
          若按位置直读，会得到 inflow=76.45M / outflow=84.31M，方向颠倒，
          进而把「本期回收」和「本期流出」全部算反。
        做法：取到 begin/a/b/end 后两向验算，哪个方向成立用哪个；都不成立保持原样。
        """
        if len(v) < 4:
            return v
        b0 = v[0] if v[0] is not None else (prev_end or 0.0)
        a, b, e = v[1], v[2], v[3]
        if None in (a, b, e):
            return v
        # ★ 容差不能用「0.02 元」这种绝对阈值：源表本身就有分位级不符
        #   （2021九期第3期：两种列序下残差 826,244.19 / 958.81，后者才是真相，
        #    剩下 958.81 是报告自身的尾差），绝对阈值会让方向判断失效，
        #   于是把 82 万的差额当成"不平"。改为按交易额取 5bp。
        tol = max(1.0, max(abs(a), abs(b)) * 5e-4)
        f1 = abs(b0 + a - b - e)          # 原序：a=流入, b=流出
        f2 = abs(b0 + b - a - e)          # 反序：b=流入, a=流出
        if f2 < f1 and f2 <= tol:
            return [v[0], b, a, e]
        return v

    acc = {}
    # ── 前置：处理「整页压成一行」的极限情况 ─────────────────────
    #   有些 OCR 结果把整张表压成一行，标签与数字交错无换行，例如：
    #   `…222,049,805.45223,163,251.66信托账户1,113,446.211-信托收款账223,163,251.66…`
    #   按行解析完全失效。此时改用「按已知标签位置 + 相邻数字」的切分法。
    RAW = ns(txt)
    def _solve_account(raw, label, prev_end=None):
        """用会计恒等式定解账户四元组：期初 + 流入 − 流出 = 期末

        ★ 为什么必须这么做：OCR 压平表格后，数值顺序完全打乱，且常缺一个数。
          实测 2022 二期首期原文：`…本期收入金额222,049,805.45223,163,251.66
          信托账户1,113,446.21…`——3 个数，顺序是「流入/流出/期末」，期初缺失。
          按位置取值全错；但恒等式是强约束：
              0 + 223,163,251.66 − 222,049,805.45 = 1,113,446.21  ✓
          穷举排列即可唯一定解，不用猜。
        """
        start = 0
        while True:
            k = raw.find(label, start)
            if k < 0:
                return None
            tail = raw[k + len(label):k + len(label) + 8]
            if ("和子账户" in tail) or ("和分账户" in tail) or ("核算概况" in tail):
                start = k + len(label)     # 命中标题，跳过
                continue
            break
        # 取标签前 3 个、后 3 个数字作为候选池
        numre = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
        allnum = [(m.start(), m.end(), fnum(m.group(0))) for m in numre.finditer(raw)]
        pool = [n[2] for n in allnum if n[1] <= k][-3:] + \
               [n[2] for n in allnum if n[0] >= k + len(label)][:3]
        pool = [x for x in pool if x is not None]
        if len(pool) < 3:
            return None
        # 首期期初为 0 是常态；也允许 pool 里自带期初
        b0 = 0.0 if prev_end is None else prev_end
        # ★ 候选里补 0：首期/清仓后，某些格是空白或「-」，OCR 不产生数字，
        #   但恒等式要求期末可为 0。实测 2023 一期首期只识别到 3 个相同的
        #   222,973,624.30（流入=流出），期末实际是 0，不加 0 候选就定不了解。
        cand = list(dict.fromkeys(pool[:3] + [0.0]))
        # ① 期初(已知/0) + 3 个候选，穷举流入/流出/期末
        for inflow, outflow, end in itertools.permutations(cand, 3):
            if abs(b0 + inflow - outflow - end) < 0.02:
                return [b0, inflow, outflow, end]
        # ② pool 里自带期初的 4 元组
        if len(pool) >= 3:
            c4 = list(dict.fromkeys(pool[:4] + [0.0]))
            for a1, a2, a3, a4 in itertools.permutations(c4, 4):
                if abs(a1 + a2 - a3 - a4) < 0.02:
                    return [a1, a2, a3, a4]
        # ③ 定不了解：不强凑，返回 None（由上层如实留空）
        return None

    # 主信托账户    # 主信托账户
    # ★ 容差：OCR 来源的首期报告表格被压平，可能只取到 3 个数（缺期初或期末）。
    #   此时仍要保留，缺的位置填 None，不能整条丢弃——否则整个账户序列断掉，
    #   「信托账户配平」断言全部失效（实测 2022 二期首期只取到 3 个值）。
    v = nums_after("信托账户")
    if len(v) >= 3:
        v = (v + [None, None, None, None])[:4]
        v = _orient(v)
        acc["信托账户"] = {"begin": v[0], "inflow": v[1], "outflow": v[2], "end": v[3]}
    for name in ("1-信托收款账户", "1-信托收款账", "2-信托付款账户", "2-信托付款账",
                 "3-信托（流动性）储备账户", "3-信托流动性储备账户"):
        v = nums_after(name)
        if len(v) >= 3:
            v = (v + [None, None, None, None])[:4]
            v = _orient(v)
            acc[name] = {"begin": v[0], "inflow": v[1], "outflow": v[2], "end": v[3]}
    # ── 子账户合计校验：信托账户行应与 2 级子账户合计一致 ─────────────
    #   ★ 用途不是纠错，而是**标记源表缺陷**：建鑫2022一期第3期，信托账户行写着
    #     期初 326,775.43 / 流出 7.00 / 流入 11,627,014.73 / 期末 11,953,783.16
    #     （行内自洽），但三个子账户期末合计只有 341,047.91（下一期期初 341,020.91
    #     正好接上它）——即"信托账户"行的期末余额与明细不符，是报告自身的错行。
    #     不标记的话，跨期结转断言会报 135% 的伪差，看起来像我们算错了。
    if "信托账户" in acc:
        _sub_end = sum((acc[k]["end"] or 0.0) for k in acc
                       if k != "信托账户" and k[:1] in "123")
        _t_end = acc["信托账户"]["end"]
        # ★ 只标**重大**不符（> 当期流入的 5%）：子账户表本身也有解析不全的时候
        #   （2022一期 p1/p2 差 2.9% 属子表未取全，不是信托账户行错），
        #   门槛太松会把正常期次也标成"源表错行"，反而让跨期结转断言失去检查力。
        if _sub_end:
            # 子账户合计一律留档：跨期结转断点时要靠它做「独立锚点」——
            # 若下一期期初 ≈ 本期子账户合计（而不是本期期末），说明本期
            # "信托账户"行的期末余额写错了（建鑫2022一期 p3：行内 11,953,783.16，
            # 子账户合计 341,047.91，下一期期初 341,020.91）。断言据此跳过而非报错。
            acc["信托账户"]["sub_end_sum"] = round(_sub_end, 2)
            # ★ 另给「核心子账户」合计（收款账 ＋ 储备账，**不含**付款账）：
            #   信托付款账户是过账户，期内收进就付出、期末应≈0；它的"期末余额"
            #   在压平的表格里最容易被邻行数字污染（建鑫2022一期 p3 被填成
            #   11,612,735.25，而真值 0）。跨期衔接的锚点用核心合计更可靠：
            #   13,112.66 + 327,935.25 = 341,047.91 ≈ 下一期期初 341,020.91 ✓
            _core = sum((acc[k]["end"] or 0.0) for k in acc
                        if k != "信托账户" and k[:1] in "13")
            if _core:
                acc["信托账户"]["sub_end_core"] = round(_core, 2)
            _mat = max(1.0, (acc["信托账户"].get("inflow") or 0.0) * 0.05)
            if _t_end is not None and abs(_t_end - _sub_end) > _mat:
                acc["信托账户"]["note"] = (
                    f"信托账户行期末 {_t_end:,.2f} 与子账户合计 {_sub_end:,.2f} 不符"
                    f"（源表错行，按原样保留）")
    # 分配子账户（招行特有）
    for name in ("（1）信托分配（税收）账户", "（1）信托分配（税收)",
                 "（2）信托分配（费用和开支）账户", "（2）信托分配（费用和开支)",
                 "（3）信托分配（证券）账户", "（3）信托分配（证券)"):
        v = nums_after(name)
        if len(v) >= 3:
            v = (v + [None, None, None, None])[:4]
            v = _orient(v)
            acc[name] = {"begin": v[0], "inflow": v[1], "outflow": v[2], "end": v[3]}
    # ── 兜底：整页被压成一行时（OCR 常见），按行解析全失效，
    #   改用「标签位置 + 相邻数字」切分。仅当上面完全没取到主账户时启用。
    if "信托账户" not in acc and "信托账户" in RAW:
        for lab in ("信托账户", "1-信托收款账", "2-信托付款账",
                    "3-信托（流动性）储备账户"):
            v = _solve_account(RAW, lab)
            if v:
                acc[lab] = {"begin": v[0], "inflow": v[1], "outflow": v[2], "end": v[3]}
    main = acc.get("信托账户") or {}
    return {"period": None, "begin": main.get("begin"), "inflow": main.get("inflow"),
            "outflow": main.get("outflow"), "end": main.get("end"), "accounts": acc}


# ── 证券本息兑付 ────────────────────────────────────────
def parse_tranche(pages, sen_done=False, sen_issue=None, sub_issue=None):
    txt = section(pages, "资产支持证券本息兑付情况", "四、", span=2)
    if not txt:
        return {}
    t = ns(txt)

    # ★ 标签异写归一：受托报告的「本息兑付后剩余本金值」有两种写法——
    #   早期写「本**息**兑付后剩余本金值」，2022 二期起部分报告写「本**期**兑付后剩余本金值」。
    #   实测分布（17 期共 118 处）：本息 62 处、本期 56 处，其中
    #     2022二期(12/12)、2024一期(18/18)、2024二期(18/18) 全用「本期」，
    #     2022三/四期混用。
    #   只认其中一种，会让整期分档余额（含次级档）全变 None →
    #   报告矩阵大片空白、次级 XIRR 也失去现金流支撑。
    t = t.replace("本期兑付后剩余本", "本息兑付后剩余本")

    def after(label, n=2):
        i = t.find(label)
        if i < 0:
            return []
        return split_money(t[i + len(label):i + len(label) + 120], n)

    # ★ 关键：OCR 把表格压平后，**某档为空时该格直接消失**，两档只剩一个数。
    #   例（2022 二期 TR01）：`本期兑付本金额216,250,760.00本期兑付本息总额217,234,431.23`
    #   —— 次级档本期兑付本金为空，若按「取 2 个值」就会把本息总额当成次级本金
    #      （实测得到 sub_principal=217,234,431.23，而次级发行额才 1.36 亿）。
    #   解法：不看位置，用**标签边界**切段——每个字段只在自己标签到下一个标签之间取数，
    #        取到 1 个就是只有优先档有值，次级按 0 处理（或按发行额判断是否清零）。
    # ★ 标签要用**短前缀**：OCR 会把「本息兑付后剩余本金值」拆成
    #   「本息兑付后剩余本」+「金值」（表格换行），用全称 find 不到，
    #   导致余额取不到、逐期分档校验失效（实测 2023 一期全部期次余额为 None）。
    LABELS = ["证券代码", "发行总额", "是否按时兑付", "票面利率", "本期兑付前本金值",
              "本期兑付本金额",
              # ★ 兴业（兴瑞）写的是「本期兑付**本金**总额」——语义是**本金合计**，
              #   不是「本息总额」。建行/招行/中信都写「本期兑付本息总额」。
              #   直接把两者当同一个字段会得出「本息 = 本金」的错误关系，
              #   进而把「本息−本金−付息」恒等式判成不成立、每期都记一条假矛盾。
              #   故这里把两个标签都收进边界表（切段用），但取值时分开处理。
              "本期兑付本息总额", "本期兑付本金总额",
              "本息兑付后剩余本",
              "付息金额", "本期利息是否延迟支付"]

    def seg_of(label):
        i = t.find(label)
        if i < 0:
            return ""
        j = len(t)
        for lb in LABELS:
            k = t.find(lb, i + len(label))
            if k > i:
                j = min(j, k)
        return t[i + len(label):j]

    def nums_of(label, maxn=2):
        """取本字段段内的前 maxn 个金额

        ★ 必须用 split_money 而不是 `[\\d,]+\\.\\d{2}`：OCR 会把相邻两格连成一串。
          实测 2023 四期第 8 期：
            `本期兑付本金额5.310.800.002,411,200.00`（= 5,310,800.00 + 2,411,200.00）
          旧正则只认「不含点的千分位」，于是切成
            [5.31, 0.8, 0.0, 241.0, 120.0, 0.0]
          ——两档本金全错。split_money 用「最少段数 + 无前导零」定解。
        """
        return split_money(seg_of(label), maxn)

    def two(label):
        """返回 (优先, 次级)；只有一个值时次级记 0（该档本期无发生）"""
        v = nums_of(label, 2)
        if not v:
            return [None, None]
        if len(v) == 1:
            return [v[0], 0.0]
        return v

    R = {}
    # 证券代码的 seg 内含「优先档资产支持证券次级档资产支持证券」等文字，
    # 直接对全文取前两个 7 位数字更可靠（证券代码在本表最前，不会被别处干扰）。
    # ★ 原文两个代码是**连写**的：`证券代码23892672389268`——「证券代码」只出现一次，
    #   用 `证券代码(\d{7})` 逐个 findall 只能拿到第一个，次级档代码会丢。
    #   改为先取「证券代码」后连续的 7 位码串，再按 7 位切。
    _codes = []
    m = re.search(r"证券代码((?:\d{7}){1,3})", t)
    if m:
        _s = m.group(1)
        _codes = [_s[i:i + 7] for i in range(0, len(_s), 7)][:2]
    R["code"] = _codes
    issue = nums_of("发行总额", 2)
    R["issue_total"] = issue
    # ★ 列序可能反：末期报告的「证券分层」表有时把次级档排在左边，
    #   实测 2023 五期 TR14 是 `130,000,000.00 / 450,000,000.00`（次级在前）。
    #   若照搬「第 2 个数是次级」，sub_issue 会取成 450,000,000，后续归属判断全错。
    #   用已知发行额（来自说明书）比对，必要时交换两列。
    flipped = False
    if len(issue) >= 2 and sen_issue and sub_issue:
        if (abs(issue[0] - sub_issue) < 1.0 and abs(issue[1] - sen_issue) < 1.0):
            flipped = True
    R["_flipped"] = flipped
    if flipped:
        issue = [issue[1], issue[0]]
        R["issue_total"] = issue
    _sub_from_issue = issue[1] if len(issue) > 1 else sub_issue

    # ★ 关键：优先档清零后，「本期兑付前本金值」等行只剩一个数（次级档），
    #   若简单地当"优先档有值、次级为0"，就会把次级本金算进优先档。
    #   实测 2023 一期：第 8-11 期优先档已于第 7 期清零，剩余本金兑付
    #   14,836,284 / 28,782,012 / 29,805,204 / 21,316,500 全被错记成优先档，
    #   导致"逐期优先本金合计 568,440,000"比发行额 473,700,000 多出 94,740,000
    #   ——恰好等于次级发行额，是一眼能看出的破绽。
    #   判据：某行只有 1 个数时，若它≈次级档发行额，则该行属次级档；否则属优先档。
    # 先用「本期兑付前本金值」判定**本期动的是哪一档**，再让同表其余行沿用：
    #   只有 1 个数时，若它≈次级发行额 → 本期动的是次级档（优先已清零）；
    #   否则动的是优先档。这样「本期兑付本金额 14,836,284」这类
    #   本身不等于任何发行额的值，也能正确归到次级档。
    _bp = nums_of("本期兑付前本金值", 2)
    if flipped and len(_bp) >= 2:
        _bp = [_bp[1], _bp[0]]
    if len(_bp) >= 2:
        side = "both"
    elif sen_done:
        # 优先档已在此前某期清零 → 之后所有单值行都属次级档。
        # 不能只看「≈次级发行额」：第 9/10 期该行是次级的**剩余本金**
        # （51,121,704 / 21,316,500），不等于发行额 94,740,000，会被误判成优先。
        side = "sub"
    elif len(_bp) == 1:
        side = "sub" if (_sub_from_issue and abs(_bp[0] - _sub_from_issue) < 1.0) else "sen"
    else:
        side = "both"

    def assign(label):
        v = nums_of(label, 2)
        if not v:
            return [None, None]
        if len(v) >= 2:
            v = v[:2]
            return [v[1], v[0]] if flipped else v
        one = v[0]
        # ★ 粘连零值必须先判：`付息金额（元）0.009,207,243.86`
        #   —— 优先档 0.00 与次级档 9,207,243.86 首尾相接，split_money 会把
        #   前缀 0.00 吞掉只留 1 个值。此时若按 side 归集，side="both"（因为
        #   兑付前本金值那行两档都有数）→ 默认归**优先档**，于是次级档利息
        #   被记成优先档利息（实测建鑫2021-2 第6期：优先档本金已为 0 却记
        #   920.72 万利息，优先档 XIRR 被抬到 18.55%、票面仅 3.30%）。
        #   判据：段文本以 "0.00" 紧跟数字开头 → 左（优先）格是 0，该值属次级。
        # seg_of 返回的是「标签 + 该段内容」，要先剥掉标签与紧随的单位括号，
        # 否则永远看着不是以 0.00 开头（实测踩过：正则对着含标签的整段判，恒不匹配）。
        _seg = re.sub(r"[\s\u3000]+", "", seg_of(label) or "")
        _seg = re.sub(r"^" + re.escape(label), "", _seg)
        # 标签后面常跟单位「（元）」或项目符号，直接跳到第一个数字再判，
        # 比逐个枚举括号形态稳（实测「（元）」用字符类没剥掉，白排查一轮）
        _seg = re.sub(r"^[^\d]*", "", _seg)
        if re.match(r"^0\.00\d", _seg):
            return [0.0, one]
        return [0.0, one] if side == "sub" else [one, 0.0]

    R["_side"] = side
    R["before_principal"] = assign("本期兑付前本金值")
    R["pay_principal"] = assign("本期兑付本金额")
    R["pay_total"] = assign("本期兑付本息总额")
    R["after_principal"] = assign("本息兑付后剩余本")   # 短前缀，与 LABELS 一致
    R["pay_interest"] = assign("付息金额")
    # ★ 兴业体例补正：报告只有「本期兑付本金总额」= 本金合计，没有「本息总额」。
    #   此时 pay_total 全为 None，用 本金总额 ＋ 付息 合成。
    #   必须放在 pay_interest 之后 —— 早一步读它会是 KeyError（本轮踩过）。
    if all(x is None for x in (R["pay_total"] or [None, None])):
        _pt = assign("本期兑付本金总额")
        if any(x is not None for x in (_pt or [])):
            _it0 = R["pay_interest"] or [None, None]
            R["pay_total"] = [
                (None if (_pt[i] is None and (_it0[i] if len(_it0) > i else None) is None)
                 else round((_pt[i] or 0.0) + ((_it0[i] if len(_it0) > i else 0) or 0.0), 2))
                for i in (0, 1)]
            R["_total_basis"] = "本金总额＋付息（报告未列本息总额）"

    # ── 恒等式救援：数值跑到标签左边时的定解 ────────────────────
    def _rescue():
        """用「兑付前本金 − 兑付本金 = 剩余本金」「兑付本息 − 本金 = 付息」定解

        ★ 触发场景（建鑫2023五期 TR06 原文）：
            `是否按时兑付票面利率2.56%67.455.000.00本期兑付前本金值130,000,000.00`
          优先档兑付前本金 67,455,000 落在标签**左侧**，按标签右切只得到
          130,000,000（恰好等于次级发行额）→ side 被判成 sub →
          优先档本期 35,145,000 的兑付本金记进了次级档（合计少 3,514.5 万）。
        ★ 做法：取「发行总额」之后的**有序金额流**，穷举切成 5 段
          （兑付前本金 / 兑付本金 / 兑付本息 / 剩余本金 / 付息），
          用恒等式筛选；**只有唯一解才采用**，多解或无解一律放弃（不猜）。
        """
        p0 = t.find("发行总额")
        if p0 < 0:
            return None
        seq = [v for pos, v in money_at(t) if pos > p0]
        # 去掉开头的两档发行额（表格首格，已由 issue 逻辑处理）
        for _ in range(2):
            if seq and sub_issue and abs(seq[0] - sub_issue) < 1.0:
                seq.pop(0)
            elif seq and sen_issue and abs(seq[0] - sen_issue) < 1.0:
                seq.pop(0)
        n = len(seq)
        if n < 5:
            return None

        def ok(g1, g2, g3, g4, g5):
            if len(g4) != len(g1) or not g2 or not g5:
                return False
            for i in range(len(g2)):
                if i >= len(g1) or abs(g1[i] - g2[i] - g4[i]) > 0.05:
                    return False
            for i in range(len(g3)):
                if i >= len(g2):
                    return False
                extra = g5[i] if i < len(g5) else 0.0
                if abs(g3[i] - g2[i] - extra) > 0.05:
                    return False
            return True

        sols = []
        for c1 in range(1, n - 3):
            for c2 in range(c1 + 1, n - 2):
                for c3 in range(c2 + 1, n - 1):
                    for c4 in range(c3 + 1, n):
                        g1, g2, g3 = seq[:c1], seq[c1:c2], seq[c2:c3]
                        g4, g5 = seq[c3:c4], seq[c4:]
                        if ok(g1, g2, g3, g4, g5):
                            sols.append((g1, g2, g3, g4, g5))
        if len(sols) != 1:
            return None
        return sols[0]

    def _two(g):
        g = list(g) + [0.0, 0.0]
        return g[:2]

    # ── 原文错值识别①：兑付前本金 ≠ 兑付 ＋ 剩余 ────────────────────
    # ★ 只有「兑付 ＋ 剩余 恰好等于该档发行额」时才动手，判据很硬：
    #   建鑫2021五期 TR01 次级档原文把「发行总额」和「本期兑付前本金值」
    #   都写成 9,600,000（应为 96,000,000，少一位 0），而
    #   兑付 12,672,000 ＋ 剩余 83,328,000 ＝ 96,000,000 ＝ 说明书发行额 ✓
    #   —— 两格少写一位是 OCR/原文的错，另两格是对的，故按后两者校正前两格。
    #   不校正也不会污染成稿（发行额另取说明书），但会让"逐档恒等式"这条
    #   自检在源头就含一个假差，后续任何以它为基准的校验都会被误导。
    for _i, _side in ((0, "sen"), (1, "sub")):
        _b = R["before_principal"][_i] if len(R["before_principal"]) > _i else None
        _p = R["pay_principal"][_i] if len(R["pay_principal"]) > _i else None
        _a = R["after_principal"][_i] if len(R["after_principal"]) > _i else None
        _iss = sen_issue if _side == "sen" else sub_issue
        if None in (_b, _p, _a) or not _iss:
            continue
        if abs(_b - (_p + _a)) < 0.05:
            continue
        if abs((_p + _a) - _iss) < 1.0 and abs(_b - _iss) > 1.0:
            R["before_principal"][_i] = round(_p + _a, 2)
            R.setdefault("_issue_typo", []).append(
                f"{_side}@p: 兑付前本金 {_b:,.2f}→{_p + _a:,.2f}"
                f"（兑付{_p:,.2f}＋剩余{_a:,.2f}＝发行额{_iss:,.2f}）")

    # ── 原文错值识别②：本息总额 ≠ 本金 ＋ 付息（仅留痕，不改数）─────────
    # ★ 建鑫2022四期 TR04：本息 26,945,807.71 ≠ 26,784,000.00 ＋ 161,804.71
    #   ＝ 26,945,804.71，差 3.00 元。本金与利息各自都能被恒等式/票面校验住，
    #   所以是本息总额那一格印错。**不自动改**：本息总额是发行人自报数，
    #   XIRR 用的也是本金＋利息分项，改动自报数等于篡改；只留痕备查。
    for _i, _side in ((0, "sen"), (1, "sub")):
        _p = R["pay_principal"][_i] if len(R["pay_principal"]) > _i else None
        _t = R["pay_total"][_i] if len(R["pay_total"]) > _i else None
        _it = R["pay_interest"][_i] if len(R["pay_interest"]) > _i else None
        if None in (_p, _t, _it):
            continue
        if abs(_t - (_p + _it)) > 0.05:
            R.setdefault("_total_mismatch", []).append(
                f"{_side}@p: 本息 {_t:,.2f} ≠ 本金 {_p:,.2f} ＋ 付息 {_it:,.2f}"
                f"（差 {_t - _p - _it:+,.2f}，源表自报数与分项不符，按原样保留）")

    # ── 恒等式逐档定解：兑付本金 ＝ 兑付前本金 − 剩余本金 ──────────────
    # ★ 为什么必须逐档解，而不是靠 _rescue 的全局 DP：
    #   粘连串被切错时（把下一格的首位数吞进上一格的小数位），这一行的三个数
    #   仍然各自"像"合法金额，DP 往往有多解 → _rescue 按设计一律放弃（不猜）。
    #   但同一张表内「兑付前 − 兑付 = 剩余」是硬约束，**逐档**就能把兑付本金
    #   直接解出来，不需要猜位置。实测建鑫2021一期 TR05：
    #     `本期兑付本金额10,492,000.003,115,800.00` → 次级被切成 5,800.00，
    #     而 54,000,000.00 − 50,884,200.00 = 3,115,800.00 恰好是真值。
    #   同类错在 24 期里命中 7 期（2021一/三/九、2022五/八、2023三/六），
    #   表现为"逐期次级本金合计 < 清算报告兑付额"，逐期余额行却完全自洽。
    _IDFIX = []
    for i in (0, 1):
        b = R["before_principal"][i] if len(R["before_principal"]) > i else None
        p = R["pay_principal"][i] if len(R["pay_principal"]) > i else None
        a = R["after_principal"][i] if len(R["after_principal"]) > i else None
        if b is None or a is None:
            continue
        if abs(b - (p or 0) - a) <= 0.05:
            continue
        _d = round(b - a, 2)
        if _d < 0:
            continue
        R["pay_principal"][i] = _d
        _IDFIX.append(("优先档" if i == 0 else "次级档", p, _d))
    if _IDFIX:
        # ★ 格式化要 None-safe：原实现直接 {o:,.2f}，而 o 就是"原来那个没取到的值"，
        #   它完全可能是 None（兴业首期优先档兑付前/剩余有一格空）→ TypeError 整单崩。
        def _fmt(v):
            return "—" if v is None else f"{v:,.2f}"
        R["_identity_fix"] = "；".join(
            f"{t}兑付本金 {_fmt(o)}→{_fmt(n)}（按「兑付前 − 剩余」定解）"
            for t, o, n in _IDFIX)
        # 兑付本息总额同理：本息 = 本金 + 付息
        for i in (0, 1):
            _p = R["pay_principal"][i] if len(R["pay_principal"]) > i else None
            _it = R["pay_interest"][i] if len(R["pay_interest"]) > i else None
            _tt = R["pay_total"][i] if len(R["pay_total"]) > i else None
            if _p is None or _it is None or _tt is None:
                continue
            if abs(_tt - (_p + _it)) > 0.05:
                R["pay_total"][i] = round(_p + _it, 2)

    _bad = False
    for i in (0, 1):
        b = R["before_principal"][i] if len(R["before_principal"]) > i else None
        p = R["pay_principal"][i] if len(R["pay_principal"]) > i else None
        a = R["after_principal"][i] if len(R["after_principal"]) > i else None
        if b is not None and a is not None and abs(b - (p or 0) - a) > 0.05:
            _bad = True
    if _bad:
        sol = _rescue()
        if sol:
            g1, g2, g3, g4, g5 = sol
            R["before_principal"] = _two(g1)
            R["pay_principal"] = _two(g2)
            R["pay_total"] = _two(g3)
            R["after_principal"] = _two(g4)
            R["pay_interest"] = _two(g5)
            R["_side"] = "both" if len(g2) >= 2 else "sen"
            R["_rescue"] = True

    coup = re.search(r"票面利率([\d.]+)%", t)
    R["coupon"] = fnum(coup.group(1)) / 100 if coup else None
    return R


# ── 资产池现金流出（科目式）─────────────────────────────
# ★ 科目名逐品种不同，这份清单是**逐期现金流出表的全部取数入口**，
#   漏一个科目就等于该品种少一整块费用：
#     信用卡：「执行费用及执行费用利息」
#     建行小微/房贷：「处置费用」（原文见建鑫2021四期 TR05：`处置费用6,960,684.70`）
#     房贷另有：「流动性支持承诺费」
#   实测踩过：房贷 4 期因缺「处置费用」导致处置费率全年为 None、
#   fee_detail 缺核心科目、契约直接把整份断言卡死（判成取数漏项）。
# ★ 3.3 补两项（建鑫 2021+ 报告里明确单列，之前整列丢失）：
#   超额奖励服务费：合同第 11 步的科目。报告在「费用和开支」里与贷款服务机构报酬
#     并列单列（2021八期 p5/p6 分别 1,560 万 / 1,229 万），漏了就有一整块流出没归集，
#     分配矩阵合计掉到 92%（实测）。
#   次级固定资金成本：证券兑付侧科目（不等于「证券利息总支出」——后者是固资＋超额
#     收益的合计）。有它就能直接取真值，不必用减法倒算。
# ★ 兴业（兴瑞）的处置环节成本叫「执行费用」（不带"及执行费用利息"，
#   也不叫"处置费用"）。受托报告 p8 实测：`执行费用 3,642,565.21`。
#   不收它 → 处置费率恒为 None、fee_detail 缺核心科目、契约判取数漏项。
OUT_ITEMS = ["税收", "代理兑付费用", "发行费用", "受托机构报酬", "资金保管机构报酬",
             "执行费用及执行费用利息", "处置费用", "执行费用",
             "贷款服务机构报酬", "审计费",
             "跟踪评级服务费", "流动性支持承诺费", "律师费", "其他费用支出",
             "超额奖励服务费",
             "证券利息总支出", "证券本金总支出", "次级档超额收益",
             "次级固定资金成本",
             "转存下期金额"]


def parse_outflow(pages, coord=None):
    """资产池现金流出（科目式）

    ★ 优先用坐标解析结果（16_fetch_outflow_coord.py 产出）：
      招行 2023 年 8 期共 117 份受托报告全是扫描件，rapidocr 的**纯文本输出
      把两列压平**，金额与科目名错位、且方向逐期不同：
        四期 `9,422.21税费支税费1,178.31出代理兑付费用…`（金额在科目上方 18-24px）
        六期 `税费支税费4,134.1337.68出代理兑付费用…`（金额与科目同行）
        八期 `13,056.42税费1,035.88代理兑付费用…`（上方 13px，且「证券兑付」被拆开）
      靠压平文本，`753,502.90` 归「证券本金总支出」还是「次级档超额收益」定不了；
      坐标法按 y 还原行后唯一确定，并用分档表交叉验证过
      （2023四期 23,288,000.00、2023八期 20,717,600.00 与该期本金合计完全相等）。
    """
    if coord:
        return dict(coord)
    txt = section(pages, "资产池现金流出情况", "资产池现金流回收预测表", span=2)
    if not txt:
        return {}
    # ★ 科目名**异写归一**：兴业（兴瑞）逐期报告用的是下面这套叫法，与建行/中信/招行
    #   都不同，不归一就会被整块漏掉。实测兴瑞2023七期：
    #     期3 少「执行费用」468.65 万 + 「贷款服务机构报酬」837.74 万
    #     期4 少「执行费用」121.03 万 + 「贷款服务机构报酬」692.43 万 + 其他费用 56 万
    #   → 逐期流出合计比累计回收少 2,142 万，分配矩阵合计只占回收 87%（断言 FAIL）。
    #   注意：这里必须按**整行等值**替换，不能用 startswith —— 「执行费用及对应的
    #   执行费用利息」若被截成「执行费用」，金额会挂到错科目上（矩阵里会多一行同名）。
    _ALIAS = {
        "执行费用及对应的执行费用利息": "执行费用及执行费用利息",
        "执行费用及对应执行费用利息": "执行费用及执行费用利息",
        "贷款服务机构资产管理服务费": "贷款服务机构报酬",
        "资产管理服务费": "贷款服务机构报酬",
        "其他费用": "其他费用支出",
    }
    lines = [x.strip() for x in txt.splitlines() if x.strip()]
    out = {}
    for i, l in enumerate(lines):
        key = ns(l)
        key = _ALIAS.get(key, key)
        for item in OUT_ITEMS:
            if key == ns(item) or (key.startswith(ns(item)) and len(key) <= len(item) + 6):
                for j in range(i + 1, min(i + 6, len(lines))):
                    v = lines[j].strip()
                    if _is_blank_cell(v):
                        # ★ 「——」必须先判成 0，否则会被当成"本格无值"继续往下找，
                        #   把**下一个科目的金额**当成自己的。实测建鑫2023二/六期、
                        #   2022四期共 21 个期次整列错位：受托机构报酬/资金保管机构报酬
                        #   （原文「——」）都吃到了处置费用 1,427,151.28，
                        #   证券本金总支出（原文「——」）吃到证券利息 2,007,972.25，
                        #   逐期流出合计虚增到 3.87 亿（真实 3.13 亿），
                        #   分配矩阵合计占回收 123%，而每期表内仍自洽。
                        out[item] = 0.0
                        break
                    if re.fullmatch(NUM, v) or v in DASH:
                        out[item] = fnum(v)
                        break
                break
    return out


# ── 资产池整体表现 ──────────────────────────────────────
def parse_pool_perf(pages):
    """资产池整体表现：基准日 / 本期报告期末 的 户数、笔数、本息余额

    ★ 必须在**带换行的原始文本**上按行取，不能先去空白：
    「68,995 / 71,141 / 2,561,820,637.69」去空白后粘成
    「68995711412561820637.69」，整段数字全毁。
    """
    txt = section(pages, "资产池整体表现情况", "处置状态分布", span=2)
    R = {}
    if not txt:
        return R
    lines = [x.strip() for x in txt.splitlines() if x.strip()]
    for tag, key in (("基准日", "base"), ("本期报告期末", "end")):
        for i, l in enumerate(lines):
            if l.startswith(tag):
                vals = []
                for j in range(i + 1, min(i + 10, len(lines))):
                    v = lines[j].strip()
                    if re.fullmatch(NUM, v):
                        vals.append(v)
                    elif v in DASH:
                        vals.append("0")
                    elif vals:
                        break
                    if len(vals) >= 3:
                        break
                if len(vals) >= 3:
                    R[key] = {"borrowers": int(float(vals[0].replace(",", ""))),
                              "loans": int(float(vals[1].replace(",", ""))),
                              "balance": fnum(vals[2])}
                break
    return R


# ── 回收与累计 ──────────────────────────────────────────
def parse_recovery(pages):
    txt = section(pages, "资金池现金流流入", "资产池现金流出", span=2)
    R = {"items": {}, "total_in": None}
    if not txt:
        # ★ 兜底：section 靠页内关键词定位，OCR 压平后标题可能被拆散。
        #   直接全页扫描「总计」后的两个金额（本期/累计），这在所有期次都成立。
        RAW = ns("".join(pages.values()))
        _ng = r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"
        m = re.search(r"总计\s*(" + _ng + r")\s*(" + _ng + r")", RAW)
        if m:
            R["items"]["总计"] = {"this": fnum(m.group(1)), "cum": fnum(m.group(2))}
            R["total_in"] = fnum(m.group(2))
            R["_fallback"] = "全页扫总计"
        return R
    # ★ 原文留档：_qi（合格投资/其他收入）要用正则精确定位，
    #   走 items 字典会被「其他收入————」的破折号解析成 0 抢先命中。
    R["_raw"] = ns(txt)
    lines = [x.strip() for x in txt.splitlines() if x.strip()]
    for i, l in enumerate(lines):
        k = ns(l)
        # ★ 标签要用前缀匹配：OCR 后是「处置中（截至本期125,524,767.13…」，
        #   精确等于「处置中」永远匹配不到，导致逐期回收全部 None。
        # ★ 「合格投资」= 存放在银行的合格投资收益，即账户结息。
        #   中信/招行叫「其他收入」，建行叫「合格投资」，同一科目的三个名字。
        #   不在这里取，存续中单（无清算报告）就拿不到 account_interest，
        #   契约会判成取数漏项，整份断言跑不起来。
        if k.startswith(("处置中", "本期处置完毕", "总计", "合格投资", "其他收入")):
            vals = []
            for j in range(i + 1, min(i + 8, len(lines))):
                v = lines[j].strip()
                if re.fullmatch(NUM, v):
                    vals.append(fnum(v))
                elif v in DASH:
                    vals.append(0.0)
                elif vals:
                    break
            if len(vals) >= 2:
                R["items"][k] = {"this": vals[0], "cum": vals[1]}
                if k == "总计":
                    R["total_in"] = vals[1]
    if not R["total_in"]:
        RAW = ns("".join(pages.values()))
        _ng = r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"
        m = re.search(r"总计\s*(" + _ng + r")\s*(" + _ng + r")", RAW)
        if m:
            R["items"].setdefault("总计", {"this": fnum(m.group(1)), "cum": fnum(m.group(2))})
            R["total_in"] = fnum(m.group(2))
            R["_fallback"] = "全页扫总计"
    return R


_COORD_CACHE = {}


def _load_coord(path):
    """读扫描件期次的坐标解析结果（按 TR 编号取）

    ★ 只对 mode=ocr-needed 的期次有用；有文本层的期次走原来的文本流解析，
      那条路径已实测 14/14 期可解析（2021-2022、2024）。
    """
    dat = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    p = os.path.join(dat, "_outflow_coord.json")
    if not os.path.exists(p):
        return None
    if p not in _COORD_CACHE:
        try:
            _COORD_CACHE[p] = json.load(open(p, encoding="utf-8"))
        except Exception:
            _COORD_CACHE[p] = {}
    m = re.match(r"(TR\d+)", os.path.basename(path))
    if not m:
        return None
    rec = _COORD_CACHE[p].get(m.group(1))
    if not rec:
        return None
    items = rec.get("items") or None
    return items if items else None


def parse_one(path, sen_done=False, sen_issue=None, sub_issue=None):
    pages = pages_of(path)
    acc = parse_account(pages)
    return {
        "account": acc,
        "tranche": parse_tranche(pages, sen_done, sen_issue, sub_issue),
        "outflow": parse_outflow(pages, _load_coord(path)),
        "pool_perf": parse_pool_perf(pages),
        "recovery": parse_recovery(pages),
        "forecast": parse_forecast(pages),
        "pages": max(pages) if pages else 0,
    }


def parse_forecast(pages):
    """（五）资产池现金流回收预测表：单位万元"""
    DATE = re.compile(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$")
    txt = section(pages, "资产池现金流回收预测表", None, span=2)
    if not txt:
        return []
    lines = [x.strip() for x in txt.splitlines() if x.strip()]
    out, j = [], 0
    while j < len(lines):
        m = DATE.match(lines[j])
        if m and j + 3 < len(lines):
            a, b, c = lines[j + 1], lines[j + 2], lines[j + 3]
            if all(re.fullmatch(NUM, x) for x in (a, b, c)):
                out.append([f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
                            fnum(a), fnum(b), fnum(c)])
                j += 4
                continue
        j += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    tdir = os.path.join(a.proj, "02_提取数据", "文本")
    idx = json.load(open(os.path.join(a.proj, "02_提取数据", "_text_index.json"),
                        encoding="utf-8"))
    trs = sorted([r for r in idx if re.match(r"^TR\d+$", r["key"])],
                 key=lambda r: int(r["key"][2:]))
    if not trs:
        print("无受托机构报告")
        return 1

    # ★★ 期次顺序必须按**报告内容里的支付日**排，不能按文件名日期/下载序号排。
    #   兴业这批 TR 的文件名带的是**下载日**，与报告所属收款期不一致：
    #     `受托机构报告_兴瑞2021年第二期_20220429.pdf` 里写的是
    #     「本期期初日 2021年8月10日 / 本期结息日 2021年12月26日」——
    #     它是第 1 期（2021-12-31 期末）的报告，只是补下载于 2022-04-29。
    #   按文件名排会把这个"第 4 期"插到 2022-03 之后，于是逐期余额出现
    #   「91,170,000 → 225,000,000」这种反向跳升，矩阵合计被算成 188%。
    def _tr_period_date(r):
        for sub, fn in (("文本", r["key"] + ".txt"),
                        ("OCR", r["key"] + ".ocr.txt")):
            p = os.path.join(a.proj, "02_提取数据", sub, fn)
            if os.path.exists(p):
                z = ns(fix(open(p, encoding="utf-8", errors="ignore").read()))
                # ★ 排序键用「本期期末日」而不是「本期支付日」：
                #   兴业是**月度报告 + 季度报告混合**，同一支付日可能有两份报告
                #   （2021二期：TR02 期末 2021-11-30，TR04 期末 2021-12-31，两者结息日
                #     都写 2021-12-26），按支付日排会把顺序搞乱、还会误判成"重复期次"。
                #   期末日在同一项目内唯一且单调，是最稳的期次键。
                for lbl in ("本期期末日", "本期结息日", "本期支付日"):
                    m = re.search(lbl + r"[^\d]{0,14}(\d{4})年(\d{1,2})月(\d{1,2})日", z)
                    if m:
                        return (f"{m.group(1)}-{int(m.group(2)):02d}-"
                                f"{int(m.group(3)):02d}")
        return None

    _dated, _undated = [], []
    for _i, r in enumerate(trs):
        _d = _tr_period_date(r)
        (dated_ok := _dated if _d else _undated).append((_d or "", _i, r))
    if _dated:
        _seen = set()
        _uniq = []
        for _d, _i, _r in sorted(_dated):
            if _d in _seen:            # 同一收款期末的重复报告，只留第一份
                print(f"  合并重复期次报告 {_r['key']}（期末日 {_d}）")
                continue
            _seen.add(_d)
            _uniq.append(_r)
        trs = _uniq + [_r for _, _, _r in _undated]
        print(f"期次按报告内期末日排序：{len(trs)} 期")
    sen_done = False
    eff_date = None       # 信托生效日（= 发行日），仅用于兜底
    _sen_cum = 0.0        # 优先档累计兑付，用来判断"是否已付清"
    _sub_cum = 0.0        # 次级档累计兑付，用来卡住"本金不得超过发行额"
    _prev_bal = [None, None]   # 上期两档剩余本金，用于「本期不还本」时结转
    # 从说明书取两档发行额，用于判定兑付表的列序是否反转
    _sen_i = _sub_i = None
    _smp = os.path.join(a.proj, "02_提取数据", "_sm_parsed.json")
    if os.path.exists(_smp):
        _T = json.load(open(_smp, encoding="utf-8")).get("tranche") or {}
        _sen_i = (_T.get("senior") or {}).get("issue")
        _sub_i = (_T.get("sub") or {}).get("issue")
    out = {"periods": [], "trust_account": [], "recovery_note":
           "累计回收一律用「本期回收金额」逐期累加，不用报告里的「累计回收金额」："
           "招行早期报告（第2–7期）的累计口径只统计在册资产、不含已处置完毕部分，"
           "与末期完整累计不一致（实测第2期报告累计 7,753万 < 首期 1.21亿，明显倒退）；"
           "逐期累加合计与第14期报告累计 278,127,994.00 完全相等，故以累加为准。"}
    print(f"{'期':>4}{'账户':>5}{'流入':>16}{'流出':>16}{'期末':>14}{'回收累计':>16}")
    for r in trs:
        n = int(r["key"][2:])
        # ★ 首期受托报告可能是**扫描件**（2022 二期 TR01 就是），此时 文本/ 下没有它，
        #   必须回落到 OCR/。只读文本目录会 FileNotFoundError，整期数据全丢。
        tp = os.path.join(tdir, f"{r['key']}.txt")
        if not os.path.exists(tp):
            tp = os.path.join(a.proj, "02_提取数据", "OCR", f"{r['key']}.ocr.txt")
        if not os.path.exists(tp):
            print(f"  跳过 {r['key']}：文本与 OCR 均不存在")
            continue
        d = parse_one(tp, sen_done, _sen_i, _sub_i)
        acc, tf = d["account"], d["tranche"]
        # ★ 信托生效日：2024 两期的说明书没有「信托财产交付日为…」这种句式，
        #   发行日取不到，存续月数就成了空值。首期受托报告「资产支持证券日期概况」
        #   里必有「信托生效日YYYY年M月D日」，且实测 14 期与说明书发行日**逐期一致**，
        #   作为发行日的兜底来源可靠。
        if n == 1:
            # ★ 「信托生效日」并非每期都有；2021–2022 那批报告写的是「信托设立日」
            #   （日期概况表里与「本期期初日」并列）。只认前者会漏掉一半单子，
            #   发行日随之缺失 → XIRR 无解（建鑫2022二期实测）。
            eff_date = (_date_after(tp, "信托生效日")
                        or _date_after(tp, "信托设立日"))
        # ★ 本期支付日：受托报告「资产支持证券日期概况」里的真实付款日。
        #   实测有用：XIRR/现金流行必须挂真实支付日，不能用「期末日」或报告日，
        #   否则同一年内多期挤在一天，年化会被抹平。
        _pay_date = _date_after(tp, "本期支付日")
        rec = d["recovery"]

        def _qi(_r, _which):
            """取「合格投资／其他收入」的本期或累计值（三种科目名都认）

            ★ 建行叫「合格投资」，中信/招行叫「其他收入」，同一科目，即账户结息。
            ★ 不能走 items 字典：原文形如
                `其他收入————合格投资102,966.30431,785.27——总计…`
              「其他收入」后面四个破折号会被 DASH 规则解析成 4 个 0，
              先命中「其他收入」就永远得 0（实测得到 0.0 而真值是 431,785.27）。
              故直接用正则取「标签后紧跟的两个金额」，取不到才算 0。
            """
            _txt = (_r or {}).get("_raw") or ""
            # ★ 顺序：先「合格投资」，再「其他收入」。
            #   建行表里两个科目**同时出现**且「其他收入」在前（`其他收入————合格投资102,966.30…`），
            #   先命中「其他收入」会因为其后全是破折号而污染取值。
            for _lab in ("合格投资", "其他收入"):
                _i = _txt.find(_lab)
                if _i < 0:
                    continue
                # 该标签后面紧跟破折号 → 本科目本期为空，换下一个标签
                if re.match(r"[—－‐/\-]{2,}", _txt[_i + len(_lab):_i + len(_lab) + 6]):
                    continue
                # ★ 必须用 split_money 而不是裸正则：原文是
                #   `合格投资102,966.30431,785.27`——两格首尾粘连，
                #   贪婪的 [\d,]+ 会把两个数吃成一个（得到 102,966.30431785.27）。
                # split_money 按「2 位小数 + 最少段数」定解，是项目里专治这毛病的工具。
                _vals = split_money(_txt[_i + len(_lab):_i + len(_lab) + 60], 2)
                if len(_vals) >= 2:
                    return _vals[0] if _which == "this" else _vals[1]
                if len(_vals) == 1:
                    # 只有一格（另一格是破折号）：本期/累计同名同值，取它
                    return _vals[0]
                return 0.0
            return None
        cum = rec.get("total_in")
        print(f"{n:>4}{len(acc.get('accounts', {})):>5}"
              f"{(acc.get('inflow') or 0):>16,.2f}{(acc.get('outflow') or 0):>16,.2f}"
              f"{(acc.get('end') or 0):>14,.2f}{(cum or 0):>16,.2f}")
        _tacc = (acc.get("accounts") or {}).get("信托账户") or {}
        out["trust_account"].append({"period": n,
                                     **{k: acc.get(k) for k in
                                        ("begin", "inflow", "outflow", "end")},
                                     # 源表错行标记（见 parse_account 的子账户合计校验）
                                     # ★ acc 是 parse_account 的外层结构（含 accounts），
                                     #   账户明细在 acc["accounts"] 里，不能直接 acc["信托账户"]。
                                     **({"note": _tacc["note"]} if _tacc.get("note") else {}),
                                     **({"sub_end_sum": _tacc["sub_end_sum"]}
                                        if _tacc.get("sub_end_sum") is not None else {}),
                                     **({"sub_end_core": _tacc["sub_end_core"]}
                                        if _tacc.get("sub_end_core") is not None else {})})
        # 分档兑付
        pi = tf.get("pay_interest") or [None]
        _pp = tf.get("pay_principal") or [0, 0]
        # ★ 硬约束：两档本金累计兑付都**不可能超过各自发行额**。
        #   末期常见「次级收益」被 OCR 认成「本金」（2023 六期第 17 期多出 753,503），
        #   超过发行额的部分一律改判为收益，保证分档合计与清算报告一致。
        if _sub_i and ((_sub_cum + (_pp[1] or 0.0)) > _sub_i + 1.0):
            _over = (_sub_cum + (_pp[1] or 0.0)) - _sub_i
            _allow = max(0.0, (_pp[1] or 0.0) - _over)
            tf["pay_principal"] = [(_pp[0] or 0.0), round(_allow, 2)]
            tf["sub_income_adjust"] = round(_over, 2)
            _pp = tf["pay_principal"]
        if _sen_i and ((_sen_cum + (_pp[0] or 0.0)) > _sen_i + 1.0):
            _over2 = (_sen_cum + (_pp[0] or 0.0)) - _sen_i
            _allow2 = max(0.0, (_pp[0] or 0.0) - _over2)
            tf["pay_principal"] = [round(_allow2, 2), (_pp[1] or 0.0)]
            _pp = tf["pay_principal"]
        _sen_cum += (_pp[0] or 0.0)
        _sub_cum += (_pp[1] or 0.0)
        _af = tf.get("after_principal") or [None, None]
        if _sen_i and abs(_sen_cum - _sen_i) < 1.0:
            # 本期正好付清优先档：把剩余值改判给次级
            if _af[0] is not None and _af[0] > 0 and not _af[1]:
                tf["after_principal"] = [0.0, _af[0]]
            sen_done = True
        elif _af[0] is not None and abs(_af[0]) < 1.0:
            sen_done = True

        # ★ 状态与约束都处理完，再刷新并落库：
        #   若先 append 再调整，写进 payload 的仍是原始（未截断）值。
        af = tf.get("after_principal") or [None, None]
        pp = tf.get("pay_principal") or [None, None]

        # ── 补零与余额结转：只付息、不还本的期次 ──────────────────────
        # ★ 场景（实测 2023 一期 TR12）：受托报告该期
        #     本期兑付前本金值 / 本期兑付本金额 / 剩余本金值  三格全空，
        #     只有「本期兑付本息总额 2,795,035.34 ＝ 付息金额 2,795,035.34」。
        #   含义明确：本期只付息、不还本 → 本金 0、余额不变。
        #   原实现留 None，报告矩阵大片空白（用户反馈的「证券本金为空」）。
        # ★ 只在**自洽证据充分**时补零，避免把 OCR 失败当 0：
        #   条件 = 本息总额与付息金额相等（容差 0.05）→ 本金必为 0。
        _tot = tf.get("pay_total") or [None, None]
        _int = tf.get("pay_interest") or [None, None]
        _t1 = (_tot[0] if _tot else None) or (_tot[1] if len(_tot) > 1 else None)
        _i1 = (_int[0] if _int else None) or (_int[1] if len(_int) > 1 else None)
        _interest_only = (_t1 is not None and _i1 is not None
                          and abs(_t1 - _i1) < 0.05)
        if _interest_only and (pp[0] is None and (len(pp) < 2 or pp[1] is None)):
            pp = [0.0, 0.0]
            tf["pay_principal_note"] = "本期只付息不还本（本息总额＝付息金额），本金记 0"
        # 余额结转 / 恒等式推算（都不是估算，是会计恒等式）
        #   ① 本期未还本 → 余额 ＝ 上期余额
        #   ② 本期还本但「剩余本金值」格空 → 余额 ＝ 上期余额 − 本期本金
        #   实测建鑫2023一期 p11：还本 21,316,500、剩余本金值格空，
        #   上期余额 21,316,500 → 推算 0，与 p12/p13 结转 0 完全自洽。
        for _i, _side in ((0, "sen"), (1, "sub")):
            if af[_i] is not None:
                continue
            _pb = _prev_bal[_i]
            _pp = pp[_i] if len(pp) > _i else None
            if _pb is None or _pp is None:
                continue
            _calc = round(_pb - _pp, 2)
            if _calc < -0.05:
                continue            # 还本超过上期余额 → 数据有问题，不推算
            af[_i] = 0.0 if abs(_calc) < 0.005 else _calc
            tf.setdefault("balance_derived", []).append(
                f"{_side}@p{n}={af[_i]:.2f}(上期{_pb:.2f}-本金{_pp:.2f})")

        # ── 次级档收益归属：证券利息总支出 / 次级档超额收益 ──────────
        # ★ 关键口径（招行早期产品的结构）：
        #   优先档本金清偿完毕后，「证券利息总支出」这一科目里装的**是次级档的
        #   固定资金成本**，不是优先档利息。原实现整列都当优先档利息，导致：
        #     · 次级档固定资金成本恒为 None（报告矩阵大片空白）
        #     · 次级档收益只剩「次级档超额收益」，漏掉固资
        #       （实测建鑫2021二期漏 2,648,734.74，次级 XIRR 由 6.9% 被压到 2.5%）
        #   判据：本期「付息金额」优先档为 0/空、而证券利息总支出 > 0 → 归次级档。
        #   第13期原文自证：次级档付息 2,658,420.09
        #     ＝ 证券利息总支出 2,648,734.74 ＋ 次级档超额收益 9,685.35 ✓
        _of = d["outflow"] or {}
        _int_all = _of.get("证券利息总支出")
        _exc = _of.get("次级档超额收益")
        _sen_int = pi[0] if pi else None
        # 默认 0.0（＝「本期无此项」），不是 None（＝「未披露」）：
        #   受托报告该格写的是「-」，含义明确是"本期没有"，矩阵里应显示 0.00。
        #   原实现留 None，导致报告里大片空白，看起来像数据缺失。
        _sub_exc = _exc if _exc is not None else 0.0
        _sub_fix = 0.0
        _fix_exp = _of.get("次级固定资金成本")
        if _fix_exp is not None:
            # ★ 报告**单列**「次级固定资金成本」时直接用它（权威，不再倒算）。
            _sub_fix = round(_fix_exp, 2)
        elif _int_all:
            # ★ 倒算公式必须是「证券利息总支出 − 优先档付息 − 次级超额收益」。
            #   原实现漏减超额收益，于是把「次级档超额收益」又算了一遍固资：
            #   2021八期 p5/p6 固资被记成 390 万 / 307 万（原文固资 0.00，
            #   证券利息总支出恰好等于超额收益），次级收益虚增 697 万，
            #   矩阵合计与清算报告对不上。
            #   实测校验：p4 3,784,321.67 − 0 − 644,080.66 = 3,140,241.01，
            #   与报告单列的固资 3,140,241.01 精确相等。
            #
            # ★★ 但有两种体例，必须分开（否则一种必错）：
            #   A「超额并入利息」：证券利息总支出 = 优先息 ＋ 次级固资 ＋ 超额
            #      → 固资 = 总支出 − 优先息 − 超额（上面这条，8 单如此）
            #   B「超额单列」  ：证券利息总支出 = 优先息 ＋ 次级固资，超额另起一行
            #      → 固资 = 总支出 − 优先息（不得再减超额，否则算成负数丢掉）
            #   判据：超额 > (总支出 − 优先息) 时只能是 B（A 里超额是其中一部分，
            #   不可能大于整体）。
            #   实证（兴瑞2023七期 p3）：总支出 829,351.96 − 优先 81,406.75
            #   = 747,945.21，而超额单列 1,995,030.49 > 747,945.21 → 判为 B。
            #   交叉验证：747,945.21 ÷ 14,000,000 × 365/195 天 = **10.00%**，
            #   正好是次级档合同约定的年化资金成本，反证拆分正确。
            _gap = _int_all - (_sen_int or 0)
            if _gap > 0.05:
                if _sub_exc > _gap + 0.05:
                    _sub_fix = round(_gap, 2)          # 体例 B：超额单列
                else:
                    _d = _gap - _sub_exc               # 体例 A：超额并入
                    if _d > 0.05:
                        _sub_fix = round(_d, 2)
            # 余量 ≤ 0 时不记负值：该期证券利息总支出已被优先档/超额解释完

        # ★ 支付日缺失（扫描件的「日期概况」表常把这一格留空/OCR 读丢）时，
        #   退回收款期末日 —— 两者相差不超过一个月，且**顺序一定正确**；
        #   留 None 会让后续所有日期比较、图表横轴、实际累计挂点全部失效。
        _pay_from_end = False
        if _pay_date is None:
            _pay_date = _tr_period_date(r)
            _pay_from_end = bool(_pay_date)

        out["periods"].append({
            "period": n,
            "pay_date": _pay_date,
            "sen_principal": pp[0] if pp else None,
            "sub_principal": pp[1] if len(pp) > 1 else None,
            "sen_interest": _sen_int,
            "sub_fixed_cost": _sub_fix,
            "sub_income": _sub_exc,
            "sub_balance_after": af[1] if len(af) > 1 else None,
            "sen_balance_after": af[0] if af else None,
            "outflow": d["outflow"],
            **({"pay_date_basis": "支付日未披露，按收款期末日标注"}
               if _pay_from_end else {}),
            "recovery_this": (rec.get("items", {}).get("总计") or {}).get("this"),
            "recovery_cum": cum,
            # ★ 账户结息（合格投资 / 其他收入）逐期留档：存续中单没有清算报告，
            #   account_interest 只能从这里取。三种叫法统一归到 qualified_inv。
            "qualified_inv_this": _qi(rec, "this"),
            "qualified_inv_cum": _qi(rec, "cum"),
            # 原文错值留痕（供报告脚注与断言说明，不参与计算）
            **({"src_note": "；".join(tf.get("_issue_typo", [])
                                      + tf.get("_total_mismatch", []))}
               if (tf.get("_issue_typo") or tf.get("_total_mismatch")) else {}),
        })
        _prev_bal = [(af[0] if len(af) > 0 else None),
                     (af[1] if len(af) > 1 else None)]
        if n == 1:
            # 首期留档：证券要素、资产池表现、账户明细、现金流预测
            out["first"] = {"tranche": tf, "pool_perf": d["pool_perf"],
                            "accounts": acc.get("accounts"), "forecast": d["forecast"],
                            "trust_effective_date": eff_date}

    # ── 账户行"期末"错行的跨期修正（用下一期期初做锚）─────────────────
    # ★ 判据很窄，只在**有确凿反证**时动手：
    #   ① 本期"信托账户"行几乎没流出（< 流入的 1%，即本期未做分配）；
    #   ② 但本期期末与下一期期初相差超过下一期流入的 15%。
    #   两条同时成立 ⇒ 本期期末余额那一格写错（建鑫2022一期 p3：期末 11,953,783.16
    #   而下一期期初 341,020.91，本期流出只记了 7.00 元）。
    #   修正方式不猜数字：期末 := 下一期期初，流出 := 期初+流入−期末（恒等式倒推），
    #   并写进 note 留痕。逐期"期初+流入−流出=期末"仍严格成立。
    _ta = out["trust_account"]
    for _i in range(len(_ta) - 1):
        _c, _nx = _ta[_i], _ta[_i + 1]
        if None in (_c.get("begin"), _c.get("inflow"), _c.get("outflow"),
                    _c.get("end"), _nx.get("begin"), _nx.get("inflow")):
            continue
        _inf = max(_c["inflow"], 1.0)
        if _c["outflow"] > _inf * 0.01:
            continue
        _d = abs(_nx["begin"] - _c["end"])
        if _d <= max(_nx["inflow"], 1.0) * 0.15:
            continue
        _old_end = _c["end"]
        _c["end"] = round(_nx["begin"], 2)
        _c["outflow"] = round(_c["begin"] + _c["inflow"] - _c["end"], 2)
        _c["note"] = (f"期末余额按下一期期初修正 {_old_end:,.2f}→{_c['end']:,.2f}"
                      f"（本期流出仅 {_c['outflow']:,.2f}，原值使账户无法衔接）")

    # ── 剔除「年度/期间财务报表」体例的重复期次 ──────────────────────
    # ★ 兴业的"受托机构报告"文件里混着**年度审计报告**（毕马威/德勤出具的
    #   财务报表及审计报告，附「年度受托机构报告」），它的「本期」是**自信托
    #   设立日起至年末的累计**，不是单期。原实现把它当成一个独立支付日收录，
    #   同一笔回收/利息就被算了两次：
    #     兴瑞2021二期 p3 付息 1,538,017.09 ＝ p1+p2 之和（精确到分）
    #     兴瑞2021二期 p8 付息 2,269,980.15 ＝ p4+p5+p6+p7 之和
    #     兴瑞2022三期 p3 付息 1,640,140.06 ＝ p1+p2 之和
    #     兴瑞2023四期 p3 付息 677,374.18   ＝ p1+p2 之和
    #   连带后果：逐期回收/利息合计虚增，优先档 XIRR 被压到票面以下（实测
    #   2022三期 2.51% vs 票面 2.99%），08 只好用「按清算口径等比例缩放」去配平，
    #   于是**每一期**的利息都被改错（实测缩放比 0.500 / 0.604 / 0.745），
    #   总额对而明细全错 —— 比不配平更难发现。
    #   判据只认两条同时成立（不依赖文件头 OCR 文字，防错字）：
    #     ① 该期「本期支付日」缺失（年度报告没有支付日）；
    #     ② 该期付息 ≈ **前面连续 k 期**付息之和（k≥1，容差 0.05 元）；
    #        付息为 0 时退用「本期兑付本金」做同一判据。
    #   命中即整期剔除，理由写进 out["dropped"] 供报告脚注引用。
    def _cum_matches(_p, _prevs):
        if not _p.get("pay_date_basis") or not _prevs:
            return None                      # 有支付日 → 正常期次
        _ti = _p.get("sen_interest") or 0.0
        _tp = _p.get("sen_principal") or 0.0
        if _ti > 0.05:
            _s = 0.0
            for _k in range(1, len(_prevs) + 1):
                _s += _prevs[-_k].get("sen_interest") or 0.0
                if abs(_s - _ti) <= 0.05:
                    return ("利息", _k, _s)
        elif _tp > 0.05:
            _s = 0.0
            for _k in range(1, len(_prevs) + 1):
                _s += _prevs[-_k].get("sen_principal") or 0.0
                if abs(_s - _tp) <= 0.05:
                    return ("本金", _k, _s)
        return None

    _keep, _dropped = [], []
    for _p in out["periods"]:
        _hit = _cum_matches(_p, _keep)
        if _hit:
            _kind, _k, _amt = _hit
            _dropped.append({
                "pay_date": _p.get("pay_date"),
                "period_in_file": _p.get("period"),
                "reason": (f"年度受托机构报告：本期{_kind} {_amt:,.2f}"
                           f"＝前 {_k} 期之和，属累计口径，已剔除"),
                "sen_interest": _p.get("sen_interest"),
                "sen_principal": _p.get("sen_principal"),
                "in_total": _p.get("recovery_this"),
            })
            print(f"  剔除年度累计期次 期末{_p.get('pay_date')}"
                  f"（{_kind} {_amt:,.2f} = 前 {_k} 期之和）")
            continue
        _keep.append(_p)
    out["periods"] = _keep
    if _dropped:
        out["dropped"] = _dropped

    # 期次重编号：上面的排序是按报告内期末日，文件序号已经不再单调（如 8、9 互换），
    # 报告里出现「第 9 期 → 第 8 期」会被读成倒序。统一按列表顺序重编 1..N。
    for _k, _p in enumerate(out["periods"], 1):
        _p["period"] = _k
    for _k, _t in enumerate(out["trust_account"], 1):
        _t.setdefault("period", _k)

    # ── 余额链自洽校正（以「剩余本金」为锚，重建逐期兑付额）─────────────
    # ★ 为什么必须这么做：扫描件的兑付表常在**「本期兑付前本金值」那一格出错**
    #   （兴瑞2021二期 TR04 把它印成 225,000,000 ＝ 发行总额，而上一期期末只剩
    #    136,147,500）。单看这一期，它自己"兑付前−兑付=剩余"是自洽的，查不出来；
    #   而把 12 期串起来看，余额链只有一种走法能收敛到 0：
    #     225,000,000 →153,337,500 →136,147,500 →(44,977,500)→91,170,000→…
    #   剩余本金是**余额型**数据（每期直接印一次，且必须接得上），
    #   兑付额是余额的差 —— 用"上期剩余 − 本期剩余"重算，比单期读数稳得多。
    #   重算后若与原读数不同，写进 src_note 留痕；总额再与清算报告对账
    #   （verify 的「逐期分档本金合计 ＝ 清算报告兑付额」就是这条的守门员）。
    _prev = [_sen_i, _sub_i]
    for _p in out["periods"]:
        _notes = []
        for _i, (_kp, _kb, _nm) in enumerate((("sen_principal", "sen_balance_after", "优先档"),
                                              ("sub_principal", "sub_balance_after", "次级档"))):
            _bal = _p.get(_kb)
            _base = _prev[_i]
            if _bal is None or _base is None:
                continue
            _pay = round(_base - _bal, 2)
            _old = _p.get(_kp)
            if _pay < -0.5:
                # 余额反而变大 → 源表这一格不可信，保持原样并留痕
                _notes.append(f"{_nm}余额由 {_base:,.2f} 增至 {_bal:,.2f}（源表异常，未校正）")
                _prev[_i] = _bal
                continue
            if _old is None or abs((_old or 0.0) - _pay) > 0.5:
                _notes.append(f"{_nm}兑付 {('—' if _old is None else format(_old, ',.2f'))}"
                              f"→{_pay:,.2f}（按「上期剩余−本期剩余」重算）")
                _p[_kp] = _pay
            _prev[_i] = _bal
        # ★ 资产池现金流出侧的「证券本金总支出」必须与分档表对齐：
        #   扫描件里这一格常被印成「发行总额」（兴瑞2021二期 TR04 记 88,852,500、
        #   TR09 记 136,147,500，两期合计恰好把本金总额顶到 490,000,000 —— 比
        #   发行额 265,000,000 多出 225,000,000，矩阵合计直接飙到 172%）。
        #   分档表（优先/次级逐档本金）已经过余额链校正，是权威值；
        #   汇总格只是它的加总，用分档值覆盖即可，无需另找证据。
        _o = _p.get("outflow") or {}
        _sum_prin = ( _p.get("sen_principal") or 0.0) + (_p.get("sub_principal") or 0.0)
        if "证券本金总支出" in _o and abs((_o.get("证券本金总支出") or 0.0) - _sum_prin) > 0.5:
            _n0 = _o.get("证券本金总支出")
            _o["证券本金总支出"] = round(_sum_prin, 2)
            _notes.append(f"证券本金总支出 {_n0:,.2f}→{_sum_prin:,.2f}"
                          f"（与分档表逐档本金不一致，按分档值覆盖）")
        if _notes:
            _p["src_note"] = ("；".join(_notes) + ("；" + _p["src_note"]
                                                   if _p.get("src_note") else ""))

    p = a.out or os.path.join(a.proj, "02_提取数据", "_trustee_parsed.json")
    json.dump(out, open(p, "w", encoding="utf-8", newline=""),
              ensure_ascii=False, indent=1)
    print(f"\n→ {p}")
    print(f"期数 {len(out['periods'])}")
    f = out.get("first", {})
    print(f"首期证券信息: 代码 {f.get('tranche',{}).get('code')}  "
          f"票面 {f.get('tranche',{}).get('coupon')}  "
          f"发行 {f.get('tranche',{}).get('issue_total')}")
    print(f"首期资产池: {f.get('pool_perf')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
