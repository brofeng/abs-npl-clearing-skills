# -*- coding: utf-8 -*-
"""建鑫（建鑫）发行说明书解析

与中信惠元的差异（都来自实测对比，不是猜的）：
1. 品牌三写法：`建鑫`（2016）→ `建鑫`（2021–2022）→ `建鑫`（2023 起）。
   取项目名时必须剥掉前缀。
2. **没有「加权平均账龄」**。说明书 p128 明确说明：单笔资产是「单个借款人信用卡账户下
   多笔刷卡消费或分期交易项下形成的逾期债务的合集」，无法统计传统账龄/期限，
   改用「加权平均逾期期限」替代。→ 3.0 技能里依赖账龄的断言要改为 SKIP 或换口径。
3. 受托机构是**华润深国投信托**（中信是中信信托），报告里「子账户」写作「**分账户**」。
4. 分配顺序终止于「次级档预期资金成本」之后，剩余金额 80% 作为超额奖励服务费。
5. 说明书章节与中信**完全对应**（第七章资产池、第八章分布、第九章证券信息），
   所以解析思路可直接复用，主要改字段名与机构名。

用法：
  python 02_parse_prospectus.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2021年第2期"
"""
import argparse
import glob
import json
import os
import re
import sys

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _numfix import money_at, split_money   # noqa: E402  带位置取数 + 粘连切分

# ── 数字清洗 ────────────────────────────────────────────────
FIX_NUM = re.compile(r"(?<=\d)[，､](?=\d)")
NUM = r"-?[\d,]+(?:\.\d+)?"


def fix(t):
    """全角逗号→半角；形近字符 Q/O→0（OCR 偶发）"""
    t = FIX_NUM.sub(",", t)
    t = re.sub(r"(?<=\d)[QOo](?=[\d.])", "0", t)
    return t


def fnum(s):
    if s is None:
        return None
    s = str(s).replace(",", "").replace("，", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


_PAGEMARK = re.compile(r"<<<PAGE\s*(\d+)>>>")


def strip_page_furniture(x):
    r"""剥掉分页标记与紧跟其后的页脚页码

    ★ 为什么必须在去空白**之前**剥：
      原文 `为\n\n<<<PAGE 146>>>\n146 \n\n267,000,000.00 元。`，
      `ns()` 一去空白就变成 `为<<<PAGE146>>>146267,000,000.00元`，
      正则 `发行总量（面值）为([\d,]+\.\d+)元` 于是读到 **146267,000,000.00**
      —— 页号 146 被当成金额的首 3 位，2.67 亿读成 1462.67 亿（建鑫2023十一期实测）。
      这类错误极其隐蔽：数字形态合法、量级也只差 3 个数量级，
      靠金额本身看不出，只能靠「发行规模 = 优先 + 次级」交叉校验才抓得住。
    """
    x = x or ""
    # ① 分页标记后的第一个纯数字行，若等于该页页号，即为页脚
    x = re.sub(r"<<<PAGE\s*(\d+)>>>[ \t]*\n[ \t]*(\d{1,4})[ \t]*(?=\n)",
               lambda m: ("" if m.group(1) == m.group(2) else m.group(0)), x)
    # ② 其余分页标记一律删掉（页号本身不属于正文）
    x = _PAGEMARK.sub("", x)
    # ③ PDF 直接取文本时**没有** <<<PAGE>>> 标记，页脚是「独占一行的 1–4 位数字」，
    #    紧跟在正文句尾之后（实测：`发行总量（面值）为\n\n146 \n\n267,000,000.00 元。`）。
    #    不删它，ns() 一去空白就变成 `为146267,000,000.00元`。
    #    安全性：真正的金额都带千分位或小数点，不会被这条删掉；
    #    删除量若超过 10%，说明原文形态异常（不是普通页脚），放弃删除并保留原样。
    x2 = re.sub(r"(?m)^[ \t]*\d{1,4}[ \t]*\n", "", x)
    if len(x2) > len(x) * 0.9:
        x = x2
    return x


def ns(t):
    """去空白，便于跨行匹配（PDF 表格常把标签与数值分行）"""
    return re.sub(r"[\s\u3000]+", "", strip_page_furniture(t))


def page_text(doc):
    return [fix(doc[i].get_text()) for i in range(doc.page_count)]


def find_page(pages, *kws, start=0):
    """返回第一个同时含全部关键词的页号（0-based）"""
    for i in range(start, len(pages)):
        if all(k in pages[i] for k in kws):
            return i
    return -1


def grab(pat, text, group=1, flags=re.S):
    m = re.search(pat, text, flags)
    return m.group(group).strip() if m else None


# ── 项目名 ────────────────────────────────────────────────
def project_name(pages):
    head = ns("".join(pages[:6]))
    # ★ 品牌名逐行不同，用**通用模式**而不是写死某一家：
    #   建鑫（建设银行）/ 兴瑞（兴业银行）/ 惠元（中信）/ 和萃（招行）…
    #   统一形态都是「<2~4字品牌>YYYY年第N期」，故只锚定年份+期号，
    #   品牌部分用 \S{2,4} 兜住，避免每换一家就改一次代码。
    # ★ 品牌长度必须固定 2 字。用 {2,4}? 惰性匹配时，正则从左往右扫，
    #   遇到 `5,500.00元兴瑞2023年第七期` 会先试「元兴」+ 需年份打在「瑞」上 → 失败，
    #   再试「元兴瑞」+ 年份成功 → 品牌变成「**元**兴瑞」，文件名随之错成
    #   「元兴瑞2023年第7期…」。建鑫/兴瑞/惠元/和萃 等系列名一律 2 字，取 {2} 即准。
    m = re.search(r"((?:招元|招银)?([\u4e00-\u9fa5]{2})(\d{4})年第"
                  r"([一二三四五六七八九十\d]+)期)", head)
    if not m:
        return None, None, None
    raw = m.group(1)
    brand = m.group(2)
    year = int(m.group(3))
    CN = "一二三四五六七八九十"

    def cv(s):
        if s.isdigit():
            return int(s)
        if s == "十":
            return 10
        if s.startswith("十") and len(s) > 1:
            return 10 + CN.index(s[1]) + 1
        if "十" in s:
            a, b = s.split("十")
            return (CN.index(a) + 1) * 10 + (CN.index(b) + 1 if b else 0)
        return CN.index(s) + 1

    q = cv(m.group(4))
    # 统一命名：品牌YYYY年第N期（阿拉伯数字，便于排序与目录名）
    return f"{brand}{year}年第{q}期", year, q


# ── 资产池总体（第七章）────────────────────────────────────
def parse_pool(pages):
    # ★ 建行写「入池本息费**和**（万元）」，招行写「总额」；两种都要认。
    i = find_page(pages, "基础资产总体信息")
    if i < 0:
        i = find_page(pages, "资产总笔数（笔）")
    if i < 0:
        i = find_page(pages, "入池本息费总额")
    if i < 0:
        i = find_page(pages, "入池本息费和")
    # ★ 目录页陷阱：各定位词在**目录**里也会出现（建鑫2023十一期：
    #   `基础资产总体信息` 目录命中 p5、正文在 p129），先到的目录页只有标题与页码，
    #   取出来的 t 全是省略号 → RULES 一条都匹配不上 → pool 为空 → 成稿 KeyError。
    #   解法：把所有候选页都试一遍，**谁能取出 balance_total 就用谁**，
    #   而不是「第一个命中的定位词」定生死。
    _CAND = ("入池资产笔数与金额特征", "资产池基本情况", "基础资产总体信息",
             "资产总笔数（笔）", "入池本息费总额", "入池本息费和", "入池资产笔数")
    _PG = []
    for _kw in _CAND:
        _i = find_page(pages, _kw)
        if _i >= 0 and _i not in _PG:
            _PG.append(_i)
    # ★ 第三种体例（小微/对公类，建鑫2021六期、2023十一期实测）：
    #   章节叫「一、入池资产笔数与金额特征」，表里不是分布表而是标签-数值对：
    #     `贷款笔数5,586 借款人数量4,279 资产池合同初始金额总额（万元）184,777.03
    #      资产池未偿本息费余额总额（万元）173,772.37 ... 预计可回收金额（万元）26,388.53`
    #   只认前两种定位词会让这一类整期 pool 为空（balance_total 缺失 → 成稿直接 KeyError）。
    if i < 0:
        i = find_page(pages, "入池资产笔数与金额特征")
    if i < 0:
        i = find_page(pages, "入池资产笔数")
    if _PG:
        i = _PG[0]
    if i < 0:
        return {}
    t = ns("".join(pages[i:i + 3]))
    P = {}
    # ★ 页定位不可靠时用全文兜底：建行说明书目录页也含「基础资产总体信息」，
    #   find_page 会先命中目录（只有页码没有数值）；且表头可能带空格/换行，
    #   `k in pages[i]` 精确匹配会失败。全文 ns 后搜「资产总笔数（笔）」最稳。
    if "资产总笔数" not in t and "贷款笔数" not in t:
        _full = ns("".join(pages))
        for _anchor in ("资产总笔数", "贷款笔数", "入池资产笔数与金额特征"):
            _j = _full.find(_anchor)
            if _j >= 0:
                t = _full[max(0, _j - 200):_j + 2500]
                break
    # 键值对形式：标签紧跟数值
    # ★ 每个字段两种体例并存：信用卡写「资产总笔数（笔）／入池本息费总额」，
    #   小微/对公写「贷款笔数／资产池未偿本息费余额总额」。用非捕获组并列，
    #   不要写成两个 RULES 条目（后者会被前者覆盖）。
    #   口径自证：168,892.48（未偿本金）+ 4,879.89（未偿息费）= 173,772.37（未偿本息费）✓
    RULES = {
        "n_loans": r"(?:资产总笔数（笔）|贷款笔数)([\d,]+)",
        "n_borrowers": r"借款人数量(?:（户）)?([\d,]+)",
        "contract_amount_w": r"(?:合同总金额\d?（万元）|资产池合同初始金额总额（万元）)([\d,]+\.\d+)",
        # ★ 三套术语，缺一套就整类期次 pool 为空（实测踩过两次）：
        #   信用卡：「入池本息费总额／入池本金总额／入池息费总额」
        #   小微  ：「资产池未偿本息费余额总额／…未偿本金余额总额／…未偿息费余额总额」
        #   房贷  ：「资产池未偿本息余额总额／…未偿本金余额总额／…未偿利息及罚息余额」
        #          ——注意房贷写「本息」不写「本息费」，息费用「利息及罚息」表述。
        "balance_total_w": r"(?:入池本息费(?:总额|和)（万元）|资产池未偿本息费?余额总额（万元）)([\d,]+\.\d+)",
        "balance_principal_w": r"(?:入池本金总额（万元）|资产池未偿本金余额总额（万元）)([\d,]+\.\d+)",
        "balance_interest_fee_w": r"(?:入池息费总额（万元）|资产池未偿息费余额总额（万元）|资产池未偿利息及罚息余额（万元）)([\d,]+\.\d+)",
        "exp_recovery_w": r"(?:预计回收总额（万元）|预计可回收金额（万元）)([\d,]+\.\d+)",
        "avg_borrower_balance_w": r"(?:借款人平均未偿本息费余额（万元）|单户平均未偿本息费余额（万元）)([\d,]+\.\d+)",
        "max_single_balance_w": r"(?:单笔贷款最高本息费余额（万元）|单笔最高未偿本息费余额（万元）|单笔最高本息余额（万元）)([\d,]+\.\d+)",
        "avg_loan_balance_w": r"(?:单笔贷款平均本息费余额（万元）|单笔平均未偿本息费余额（万元）|单笔平均本息余额（万元）)([\d,]+\.\d+)",
        "wavg_overdue_months": r"加权平均逾期(?:期限|时间)（月）([\d,]+\.\d+)",
        "wavg_age": r"借款人加权平均年龄（岁）([\d,]+\.\d+)",
        "wavg_income_w": r"借款人加权平均年收入（万元）([\d,]+\.\d+)",
        "wavg_credit_limit_w": r"借款人加权平均获得的授信额度（万元）([\d,]+\.\d+)",
    }
    for k, pat in RULES.items():
        v = grab(pat, t)
        if v is not None:
            P[k] = int(v.replace(",", "")) if k in ("n_loans", "n_borrowers") else fnum(v)
    # 万元 → 元
    for k in [x for x in P if x.endswith("_w")]:
        P[k[:-2]] = round(P.pop(k) * 1e4, 2)
    # ★ 本次没取到核心金额 → 换下一个候选页重试（目录页/封面页会命中但无数值）
    if not P.get("balance_total") and len(_PG) > 1:
        for _pi in _PG[1:]:
            _t2 = ns("".join(pages[_pi:_pi + 3]))
            P2 = {}
            for k, pat in RULES.items():
                v = grab(pat, _t2)
                if v is not None:
                    P2[k] = int(v.replace(",", "")) if k in ("n_loans", "n_borrowers") else fnum(v)
            for k in [x for x in P2 if x.endswith("_w")]:
                P2[k[:-2]] = round(P2.pop(k) * 1e4, 2)
            if P2.get("balance_total"):
                P2["_page"] = _pi + 1
                return P2
    return P


# ── 分档与证券信息（第九章）──────────────────────────────
def parse_tranche(pages, P):
    i = find_page(pages, "证券基本信息")
    t = ns("".join(pages[i:i + 30])) if i >= 0 else ns("".join(pages))
    T = {}
    # 发行总量
    m = re.search(r"发行总量（面值）为([\d,]+\.\d+)元", t)
    if not m:
        m = re.search(r"发行总规模（面值）：([\d,]+\.\d+)元", ns("".join(pages[:4])))
    # ★ 金额单位逐行不同：招行（和萃）说明书用**元**，建行（建鑫）用**万元**。
    #   建行封面：`发行票面总金额：26,900.00万元` + 表头`发行规模（票面/人民币万元）`。
    #   若不换算，2.69 亿会读成 2.69 万元，证券化率直接错 1 万倍。
    # ★ 封面不能用「前 N 页」硬切：建鑫2021年第八期的说明书 PDF **开头 4 页全是
    #   《更正说明》的盖章页**（每页只有一行"本页无正文"），真正的封面表在里面。
    #   写死 pages[:4] 会得到 45 个字符的空白 cover，于是 UNIT 判成 1.0、
    #   优先档/次级档金额全取不到（表现为"发行规模 None"）。
    #   改为：先按内容特征（「规模占比」＋「还本方式」同时出现）定位封面表所在页，
    #   取该页 ±1 页作为封面；找不到再退回前 4 页。
    # ★ 封面表头逐行不同，不能只认建行那套「规模占比＋还本方式」：
    #     建行：规模占比 | 还本方式 | 利率类型 | 预期到期日 | 法定到期日
    #     兴业：分层情况 | 发行规模（元）| 占比（%）| 发行利率 | 预期到期日 | 法定到期日
    #   只认前者会让兴业 10 单的 _cover 退回「前 4 页」猜测，
    #   而兴业第 2 页正文有「…优先档资产支持证券…2023年12月14日…」，
    #   优先档发行额被读成 **2023**（年份被当成金额）。实测兴瑞2023七期即如此。
    _COV_HINTS = (
        ("规模占比", "还本方式"),
        ("分层情况", "发行规模"),
        ("发行规模", "占比", "到期日"),
    )
    _cov_pg = -1
    for _i in range(min(15, len(pages))):
        _np = ns(pages[_i])
        if any(all(h in _np for h in _hints) for _hints in _COV_HINTS):
            _cov_pg = _i
            break
    if _cov_pg >= 0:
        _cover = ns("".join(pages[max(0, _cov_pg - 1):_cov_pg + 2]))
    else:
        _cover = ns("".join(pages[:4]))
    _full_all = ns("".join(pages[:max(15, _cov_pg + 3)]))
    if ("人民币万元" in _full_all) or re.search(r"发行票面总金额[：:]?[\d,\.]+万元", _full_all):
        UNIT = 1e4
    else:
        UNIT = 1.0
    T["_unit"] = UNIT
    # ★ 总额取数要按**该句自己的单位**换算，不能一律乘封面单位：
    #   建行说明书里同时存在两种表述——
    #     正文 `发行总量（面值）为269,000,000.00元`   → 已是元，不能再乘
    #     封面 `发行票面总金额：26,900.00万元`         → 需 ×1e4
    #   曾一律乘 UNIT，269,000,000 × 1e4 = 2.69 万亿，报表显示「26900 亿」。
    # ★ 表述第三种（建鑫2022年第四期实测）：`发行总量（面值）为 39,000.00 万元`
    #   —— 单位是**万元**且带空格；另有 `发行票面总金额：39,000 万元`（整数、无小数）。
    #   原实现只认 `([\d,]+\.\d+)元` 与 `([\d,]+\.\d+)万元` 两种，
    #   这一期两个都不中 → total=None → 后续 print 直接 TypeError 崩掉，
    #   整期解析全部作废（这也是它长期 "无 payload" 的真因）。
    #   改为「数值 + 单位」成组取，按捕获到的单位换算，不再假定是元还是万元。
    # 分档：优先档 / 次级档 发行规模
    # ★ 不能再用 `([\d,]+\.\d+)`：`\d+` 贪婪，会把紧跟的**占比数字**吃进来。
    #   原文（说明书第九章表格压平后）：
    #     `优先档资产支持证券185,000,000.0079.06固定利率2022/4/26…`
    #     `次级档资产支持证券49,000,000.0020.94…`
    #   旧正则读成 185,000,000.0079 / 49,000,000.002 —— 17 期全部带这种脏尾数，
    #   报表里会显示成「450,000,000.01」这种既不对也不好看的值。
    #   split_money 按「2 位小数 + 最少段数」定解，同时兼容 `.` 与 `,` 两种千分位。
    # ★ 还要跳过「优先档资产支持证券发行规模的5%」这类**非金额**表述：
    #   re.search 会命中全文第一个「标签+小数」，所以逐个出现位置试，取第一个
    #   金额像样的（发行规模都在千万以上）。
    def _issue_after(label):
        for m in re.finditer(re.escape(label), t):
            seg = t[m.end():m.end() + 60]
            for _pos, v in money_at(seg):
                if v >= 1e4:
                    return v
        return None

    # ★ 分档金额只在**封面页**取：封面 4 页内的表格才是权威发行结构。
    #   全文搜会先命中第 2 页正文的「…的优先档资产支持证券及次级档资产支持证券，
    #   并向发起机构支付…」，那里没有金额，split_money 会取到日期/比例碎片
    #   （实测建鑫2021一期：优先档被读成 21.5 万元、次级档 4.83 万元）。
    def _issue_of(*labels):
        """按多个标签依次尝试；返回金额已按 UNIT 换算为元

        ★ 建行说明书的封面表格压平后是 `优先档21,500.0079.93%过手固定利率…`，
          没有「资产支持证券」这四个字；招行则是 `优先档资产支持证券185,000,000.0079.06…`。
          两种都要认。阈值也不能用「≥1 万」（建行万元制下 21,500 才是 2.15 亿），
          改为「取 split_money 的第一段」，再用「发行总额×占比」反查校验。
        """
        for src in (_cover, t):          # 先封面，再兜底全文
            for lab in labels:
                for m in re.finditer(re.escape(lab), src):
                    seg = src[m.end():m.end() + 60]
                    vals = split_money(seg, 2)
                    if not vals:
                        continue
                    v = vals[0]
                    # 合理区间：换算成元后应在 **100 万元** ~ 200 亿之间。
                    # ★ 下限原来是「100×UNIT」，即万元制下 100 万元、元制下仅 100 元，
                    #   太松 —— 年份 2023、占比 83.91 都能通过，
                    #   实测兴瑞2023七期优先档发行额被读成 2023。
                    #   任一档 ABS 发行额不可能低于 100 万元，取下限 1e6。
                    if v and 1e6 <= v * UNIT <= 2e10:
                        return v * UNIT
        return None

    _sen = _issue_of("优先档资产支持证券", "优先档")
    _sub = _issue_of("次级档资产支持证券", "次级档")
    T["senior"] = {"issue": _sen}
    T["sub"] = {"issue": _sub}

    _UNIT_PAT = r"(?:人民币)?([\d,]+(?:\.\d+)?)(万元|元)"
    m = re.search(r"发行总量（面值）为" + _UNIT_PAT, t)
    if m:
        _v, _u = fnum(m.group(1)), m.group(2)
        T["total"] = (_v * 1e4) if (_v is not None and _u == "万元") else _v
        T["total_basis"] = f"发行总量（面值）为{m.group(1)}{_u}"
    else:
        m2 = re.search(r"发行票面总金额[：:]?" + _UNIT_PAT, _cover)
        if m2:
            _v, _u = fnum(m2.group(1)), m2.group(2)
            T["total"] = (_v * 1e4) if (_v is not None and _u == "万元") else _v
            T["total_basis"] = f"发行票面总金额：{m2.group(1)}{_u}"
        else:
            # ★ 兴业（兴瑞）封面没有「发行总量（面值）为…」也没有「发行票面总金额」，
            #   而是表格末行 `总计 87,000,000.00 100.00%`。
            #   取不到就 total=None，会让证券化率、次级占比整块空掉。
            #   判据：封面里「总计」后紧跟金额且随后出现 100.00% —— 这是发行额合计行。
            _tot = None
            for _m in re.finditer(r"总计", _cover):
                seg = _cover[_m.end():_m.end() + 60]
                _v = split_money(seg, 1)
                if _v and _v[0] >= 1e6 * UNIT and "100.00%" in seg:
                    _tot = _v[0] * UNIT
                    break
            # 兜底：两档相加（分档都取到且都合理时）
            if _tot is None and _sen and _sub:
                _tot = _sen + _sub
                T["total_basis"] = "优先档＋次级档发行额相加（封面未列合计行）"
            if _tot is not None:
                T["total"] = _tot
                if "total_basis" not in T:
                    T["total_basis"] = "封面表合计行「总计」"
            else:
                T["total"] = None
                T["total_basis"] = "未识别到发行规模表述"
    # 票面
    m = re.search(r"优先档资产支持证券的票面利率为([\d.]+)%", t) or \
        re.search(r"票面利率([\d.]+)%", t)
    T["senior"]["coupon"] = fnum(m.group(1)) / 100 if m else None
    # 次级占比
    if T["total"] and T["sub"]["issue"]:
        T["credit_enhance_pct"] = round(T["sub"]["issue"] / T["total"], 6)
    # 风险自留（招行持有各档 5%）
    m = re.search(r"持有各档?资产支持证券发行规模的(\d+)%", t) or \
        re.search(r"持有.{0,10}(\d+)%及持有", t)
    T["retention_pct"] = fnum(m.group(1)) / 100 if m else 0.05
    # 执行费用（＝处置费用）合同上限：占累计回收款的百分比
    # ★ 各单不同，不能写死：中信惠元第三期是 17%，招行建鑫是 **16%**
    #   （原文「…且以累计"回收款"金额的16%为限」）。
    #   取不到就留 None，报告里显示「—」，绝不套用别单的数。
    # ★ 必须在**全文**里搜：该表述在《信托合同》第 11.5 款（说明书后段），
    #   不在「证券基本信息」起 30 页的范围内（实测在 t 里搜不到）。
    cap = None
    _full = ns("".join(pages))
    for pat in (r"累计[“\"']?回收款[”\"']?金额的(\d+(?:\.\d+)?)%为限",
                r"累计[“\"']?回收款[”\"']?金额(\d+(?:\.\d+)?)%"):
        mm = re.search(pat, _full)
        if mm:
            cap = fnum(mm.group(1)) / 100
            break
    T["dispose_cap_pct"] = cap
    return T


# ── 日期与代码 ────────────────────────────────────────────
def parse_meta(pages, name):
    head = ns("".join(pages[:4]))
    body = ns("".join(pages))
    # ★ 品种必须从说明书第 2 页读，不能写死：
    #   建鑫同一系列下有 4 个品种（信用卡债权 / 个人消费类贷款 /
    #   小微企业经营类贷款 / 个人住房抵押贷款），写死「信用卡不良」会让
    #   个人消费、小微、房贷的报告全部错标品种 —— 属实质性失真。
    _var = None
    _var_src = None
    _mv = re.search(r"本期证券的基础资产为([^。]{4,30})", head) or \
          re.search(r"本期证券的基础资产为([^。]{4,30})", body)
    if _mv:
        _v = _mv.group(1)
        # 判据原文：原样保留说明书 p2 的表述，供报告 chip 显示（可追溯，不转述）
        _var_src = "本期证券的基础资产为" + _v.strip()
        _v = _v.replace("不良", "")
        # ★ 关键词语序：先判最具体的（住房抵押/小微），再判信用卡——
        #   否则「个人类信用卡不良贷款」这类含"个人"的表述会被误归到个人消费。
        #   兴业原文：「基础资产为个人信用卡不良贷款」。
        # ★ 顺序铁律：「信用卡」必须排在「个人消费」之前。
        #   兴业原文是「信用卡**个人消费类**不良贷款」（信用卡项下的消费类），
        #   先判个人消费就会把信用卡单误标成"个人消费不良"——品种错标是实质性失真
        #   （实测兴瑞2023七期被判成个人消费不良）。
        _MAP = (("住房抵押", "住房抵押不良"), ("小微企业经营", "小微经营不良"),
                ("企业经营", "企业经营不良"), ("信用卡", "信用卡不良"),
                ("消费", "个人消费不良"))
        for k, v in _MAP:
            if k in _v:
                _var = v
                break
        if _var is None:
            _var = _v + "（不良）"
    # 机构名：按名称形态取**最短的那个匹配**
    # ★ 不能直接 grab(第一个)：正则从左往右贪婪取，实测把
    #   `不良资产支持证券兴业银行股份有限公司` 整段当成了发起机构名。
    #   银行/信托的简称通常 2–6 字，故取候选里最短者，
    #   `证券兴业银行股份有限公司`(长) 与 `兴业银行股份有限公司`(短) 并存时取后者。
    def _shortest_org(text, kind):
        """取「机构简称 + 银行/信托 + 公司后缀」里**简称最短**的那个

        ★ 不能按整个匹配串取最短：`资产支持证券兴业银行股份有限公司` 与
          `兴业银行股份有限公司` 比，虽然前者更长，但正则左起匹配还会给出
          `支持证券兴业银行股份有限公司` 这种"简称 4 字"的候选，长度比正确名更短或相当，
          仍然选不准。真正的判据是 **kind 前面那几个字**（机构简称）要最短，
          银行/信托名称通常 2–4 字（兴业、建设、招商、中信）。
        """
        # ★ 必须用**后行断言**做可重叠匹配：普通 finditer 的匹配互不重叠，
        #   一旦先匹配上「支持证券兴业银行股份有限公司」，起点在「兴」的那个短匹配
        #   就落在已消费区间内、根本不会被枚举到，于是永远选不出「兴业银行股份有限公司」。
        pat = (r"(?=([\u4e00-\u9fa5]{2,8}?)(" + kind +
               r")(股份有限公司|有限责任公司|有限公司))")
        best = None
        for m in re.finditer(pat, text or ""):
            # ★ 后行断言是零宽匹配，m.group(0) 恒为空串，
            #   机构全名必须由 1+2+3 三段自己拼（踩过一次：拼不出→全部返回 None）。
            short = m.group(1)
            full = m.group(1) + m.group(2) + m.group(3)
            key = (len(short), -len(full))
            if best is None or key < best[0]:
                best = (key, full)
        return best[1] if best else None

    # ★ 首选**结构定位**（最确定）：封面把两个机构名与角色分行排列——
    #     `兴业银行股份有限公司 / 兴业国际信托有限公司 /
    #      作为发起机构/贷款服务机构/委托人 / 作为受托人/受托机构/发行人`
    #   取「作为发起机构」之前出现的那两个公司名，前者是发起机构、后者是受托人。
    #   比按名字猜可靠得多：按"最短简称"猜会把受托人取成「国际信托有限公司」，
    #   按"最长"猜又会把发起机构取成「资产支持证券兴业银行股份有限公司」。
    _iro = _itr = None
    # ★ 必须用**保留换行**的原文按行取，不能用 ns() 压平后的文本：
    #   压平后两个机构名与角色文字连成一串，正则无论取左取右都会多吃/少吃几个字
    #   （实测取成「年第七期不良资产支持证券兴业银行股份有限公司」）。
    #   封面这里是「名称一行、角色一行」的排版，按行切分天然对齐。
    _raw_head = "".join(pages[:4]) if pages else ""
    _lines = [x.strip() for x in _raw_head.splitlines() if x.strip()]
    _role_i = next((i for i, x in enumerate(_lines) if "作为发起机构" in x), -1)
    if _role_i >= 1:
        _ORG = re.compile(r"^[\u4e00-\u9fa5]{2,20}(?:银行|信托)"
                          r"(?:股份有限公司|有限责任公司|有限公司)$")
        _names = []
        j = _role_i - 1
        while j >= 0 and len(_names) < 4:
            if _ORG.match(_lines[j]):
                _names.append(_lines[j])
            elif _names:
                break
            j -= 1
        # _names 是**从近到远**：[受托人, 发起机构]
        if len(_names) >= 2:
            _itr, _iro = _names[0], _names[1]
        elif len(_names) == 1:
            _iro = _names[0]
    if not _iro:
        _iro = _shortest_org(head, "银行") or _shortest_org(body, "银行")
    if not _itr:
        _itr = _shortest_org(head, "信托") or _shortest_org(body, "信托")

    M = {"display_name": name, "variety": _var or "（品种未识别）",
         "variety_source": _var_src,
         # 含抵押物信号：说明书担保方式分布里出现「抵押」即判是（住房抵押单必为是）
         "has_collateral": ("抵押" in (_v if _mv else "")),
         # ★ 机构名不再写死（原为建行三件套），改为按机构名形态从封面/正文取：
         #   `XX银行股份有限公司` → 发起机构兼贷款服务机构；`XX信托有限公司` → 受托人。
         #   兴业实测：兴业银行股份有限公司 / 兴业国际信托有限公司。
         "originator": (_iro or "—"),
         "originator_short": ((_iro or "—").replace("股份有限公司", "")
                              .replace("有限公司", "")),
         "trustee": (_itr or "—"),
         "servicer": (_iro or "—")}
    # 机构
    for k, pat in (("custodian", r"资金保管机构\s*(中国[\u4e00-\u9fa5]+(?:省|市)?分行|中国[\u4e00-\u9fa5]+银行[\u4e00-\u9fa5]*公司)"),
                   ("underwriter", r"主承销商\s*([\u4e00-\u9fa5]+证券[\u4e00-\u9fa5]*公司)")):
        v = grab(pat, body)
        if v:
            M[k] = v
    # 日期
    # 初始起算日：正文有多种写法（「初始起算日（2021年3月31日）」「封池日，即2021年3月31日」），
    # 取第一个能匹配到年月日的位置。曾误用 group(0) 拿到整段「初始起算日（2021年3月31日」。
    _cut = re.search(r"(?:初始起算日|封池日)[^。]{0,40}?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", body)
    M["cutoff_date"] = (f"{_cut.group(1)}-{int(_cut.group(2)):02d}-{int(_cut.group(3)):02d}"
                        if _cut else None)
    # ★ 发行日（信托财产交付日）表述逐期不同，必须给 fallback 链：
    #   建鑫2021三期只写「资产支持证券于起息日2021年6月23日（含该日）开始计息」，
    #   全文没有「信托财产交付日」→ issue_date 为 None → 推不出 life_months
    #   → XIRR/XNPV 全链为空 → 成稿在折现系数处崩。
    #   起息日与交付日在本产品里是同一天（发行即计息），按 fallback 取并留痕。
    _ISSUE_PATS = (
        # ★ 「信托财产交付日（起息日）2023 年4 月4 日」——括号夹注把日期顶开了，
        #   原写法要求标签后紧跟数字，实测建鑫2023一期因此 issue_date=None，
        #   XIRR/XNPV 全链为空、契约缺 metrics.sen_xirr。
        (r"信托财产交付日\s*[（(]\s*起息日\s*[）)]\s*[为是：:]?\s*"
         r"(\d{4})年(\d{1,2})月(\d{1,2})日", "信托财产交付日（起息日）"),
        (r"信托财产交付日[为是]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日", "信托财产交付日"),
        (r"发行日[为是：:]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日", "发行日"),
        (r"起息日\s*(\d{4})年(\d{1,2})月(\d{1,2})日", "起息日（＝交付日，产品发行即计息）"),
    )
    _iv = None
    for _p, _basis in _ISSUE_PATS:
        _m = re.search(_p, body)
        if _m:
            _iv = f"{_m.group(1)}-{int(_m.group(2)):02d}-{int(_m.group(3)):02d}"
            M["issue_date_basis"] = _basis
            break
    M["issue_date"] = _iv
    for k, pat in (("first_pay_date", r"第一个支付日[是为]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日"),
                   ("legal_maturity", r"法定到期日[为是]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日")):
        m = re.search(pat, body)
        M[k] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    # 证券代码（7位，优先在前、次级在后）
    codes = []
    for c in re.findall(r"证券代码(\d{7})", body):
        if c not in codes:
            codes.append(c)
    M["code_sen"] = codes[0] if codes else None
    M["code_sub"] = codes[1] if len(codes) > 1 else None
    # 说明书页数
    M["sm_pages"] = len(pages)
    M["file_name"] = f"{name}_不良ABS穿透分析_v1.html"
    # 账龄披露：按**品种**给说明，不能一律写「信用卡不良」——
    #   建鑫同系列 4 个品种（信用卡债权/个人消费类/小微经营/住房抵押），
    #   写死会让消费、小微、房贷三类的报告正文出现「信用卡不良为多笔交易合集」这种
    #   与事实相反的描述（v1 实测已发生）。品种 → 措辞，一一对应。
    _AGE_NOTE = {
        "信用卡不良": "信用卡不良为多笔交易合集，说明书未披露加权平均账龄，以加权平均逾期期限替代",
        "个人消费不良": "个人消费不良单笔资产为多笔消费/分期交易的合集，说明书不披露贷款账龄分布，"
                        "以加权平均逾期期限替代",
        "小微经营不良": "小微经营不良说明书未披露加权平均贷款账龄，以加权平均逾期期限替代",
        "住房抵押不良": "个人住房抵押不良说明书未披露加权平均贷款账龄，以加权平均逾期期限替代",
    }
    _v = M.get("variety") or ""
    M["no_age_disclosure"] = True
    M["age_note"] = _AGE_NOTE.get(
        _v, f"{_v or '本品种'}说明书未披露加权平均贷款账龄，以加权平均逾期期限替代")
    return M


def fill_from_trustee(proj, M, T):
    """票面利率与证券代码在说明书里取不到，从受托机构报告第 1 期回补

    说明书只写「票面利率为固定利率，根据簿记建档结果确定」，没有数值；
    发行结果公告是扫描件（0 文本）；受托机构报告第 1 期的「三、资产支持证券概况」
    表格里有完整信息：证券代码 2189254/2189255、票面利率 3.30%。
    """
    tr = sorted(glob.glob(os.path.join(proj, "01_下载文档", "*受托机构报告*总第1期*.pdf")))
    if not tr:
        tr = sorted(glob.glob(os.path.join(proj, "01_下载文档", "*受托机构报告*.pdf")))[:1]
    if not tr:
        return M, T, "无受托机构报告可回补"
    doc = fitz.open(tr[0])
    t = ns("".join(fix(doc[i].get_text()) for i in range(min(10, doc.page_count))))
    note = []
    # 证券代码：表格里紧跟「证券代码」的两个 7 位数字
    k = t.find("证券代码")
    if k >= 0 and not (M.get("code_sen") and M.get("code_sub")):
        codes = re.findall(r"(\d{7})", t[k:k + 60])
        if codes:
            M["code_sen"] = M.get("code_sen") or codes[0]
            if len(codes) > 1:
                M["code_sub"] = M.get("code_sub") or codes[1]
            note.append(f"代码←受托报告 {codes[:2]}")
    # 票面利率：紧跟「票面利率」的百分比（次级为「不适用」）
    k = t.find("票面利率")
    if k >= 0 and T.get("senior", {}).get("coupon") is None:
        m = re.search(r"票面利率(\d+(?:\.\d+)?)%", t[k:k + 40])
        if m:
            T["senior"]["coupon"] = fnum(m.group(1)) / 100
            note.append(f"票面←受托报告 {m.group(1)}%")
    # 发行总额（优先/次级）交叉校验
    if T.get("senior", {}).get("issue") and T.get("sub", {}).get("issue"):
        tot = (T["senior"]["issue"] or 0) + (T["sub"]["issue"] or 0)
        if T.get("total") and abs(tot - T["total"]) > 1:
            T["total_check"] = round(tot, 2)
    return M, T, "；".join(note) if note else "无需回补"


# ── 合同约定的现金流分配顺序（说明书第七章）──────────────────
# ★ 为什么必须解析而不是写死模板
#   建鑫2021-1 的**次级档本金（第9步）先于次级档固定资金成本（第10步）**，
#   与"次固资在次级本金之前"的直觉相反；写死模板会让整张分配矩阵的顺序反掉，
#   而报表内合计仍然配平（自洽但错），门禁也查不出来。
#   三行（中信/招行/建行）原文条款均可用文字层抽取，故一律以原文为准。
_WS_ITEM = re.compile(r"(?m)^\s*(\d{1,2})[、.]\s*([^\n]{4,220})")


def _ws_kind(t):
    """把一步分配归到 费用 / 证券 / 储备 / 收益 四类（版式配色与断言依赖它）

    ★ 判断依据是**资金去向账户**，不是关键词命中：
      条款行文统一为「…记入/转入『信托分配（X）账户』」，X 即类别。
      曾按「含『固定资金成本』→ 证券」判断，把第11步「固资清偿完毕后…超额奖励
      服务费转入『费用和开支』账户」误判成证券；按账户判定才稳。
    """
    if "流动性" in t and "储备" in t:
        return "储备"
    if re.search(r"作为.{0,12}次级档.{0,6}(的)?收益", t):
        return "收益"
    if "费用和开支" in t or "税收）账户" in t or "信托分配（税收" in t:
        return "费用"
    if "信托分配（证券" in t or "证券）账户" in t:
        return "证券"
    # 兜底：看动作对象
    if re.search(r"(优先档|次级档).{0,8}(本金|利息|固定资金成本)", t):
        return "证券"
    return "费用"


def parse_waterfall(pages):
    """从说明书「现金流分配机制」抽合同约定的分配顺序

    优先取「（二）违约事件发生前的处置收入分配」（正常情景）；无则退到
    「（三）违约事件发生后」（顺序基本一致，仅费用是否受"优先支出上限"约束不同）。

    返回 {"basis": str, "page_hint": str, "steps": [{"no", "text", "kind"}]}
    """
    full = "".join(pages)

    # ★★ 章节标题逐期不同，这是 24 单里 20 单"合同步为空"的根因（重大）：
    #     · 2021一/三/八、2023三 写作「（二）违约事件发生前的**处置收入**分配」
    #     · 其余 20 单写作「（二）违约事件发生前**信托收款账户**的分配」
    #   原来按字面串精确匹配前一种，后一种全落空 → steps=[] →
    #   waterfall_rows 退化成"清算报告科目发生顺序"，矩阵整列标「未归集」，
    #   于是"次级档本金(9) 先于 次级档固定资金成本(10)"这个关键次序根本没进表。
    #   改成**正则**只锚定稳定部分（序号 + 违约事件发生时点 + "分配"），
    #   中间措辞（处置收入／信托收款账户／…）不限，且不跨括号。
    # ★ 编号也要放宽：兴业写「（一）违约事件发生前的**现金流分配机制**」——
    #   编号是"一"不是"二"，且尾词是"分配机制"。原来锚死「（二）…分配」，
    #   兴业 10 单的合同步全部抽不到 → 矩阵整列退化成"未归集"，
    #   「次级本金(9)→次级固资(10)」这条关键次序也就根本没进表。
    _H2 = re.compile(r"[（(][一二三][）)]\s*违约事件发生(?:前)[^（(\n]{0,26}?分配")
    _H3 = re.compile(r"[（(][二三四][）)]\s*违约事件发生(?:后|後)[^（(\n]{0,26}?分配")
    _H4 = re.compile(r"[（(][三四五][）)]\s*信托终止后[^（(\n]{0,26}?分配")

    def _find_head_body(hpat, tpat):
        """返回 [(head_start, head_text, body_end)]，目录条目（后跟省略号）自动跳过"""
        out = []
        for m in hpat.finditer(full):
            i = m.start()
            # ★ 目录条目的特征是「标题后跟一串点号」（`…… ...... 121`）；
            #   正文条目则是「标题 + 换行 + 正文」。原判据写成 [\s.]{4,}
            #   把正文里的换行空白也算进去 → 正文被误判成目录而跳过，
            #   5 单（2021四/七、2023四/七、2021六）因此整节丢失。
            #   现要求必须真的出现 4 个以上点号。
            if re.match(r"[ \t]*[.．]{4,}", full[m.end():m.end() + 60]):
                continue                       # 目录页条目
            t = tpat.search(full, m.end())
            out.append((i, m.group(0), t.start() if t else min(len(full), i + 6000)))
        return out

    _cands = [(_i, _h, _e, "发行说明书·七、现金流分配机制·" + _h.replace(" ", ""))
              for _i, _h, _e in _find_head_body(_H2, _H3)]
    _cands += [(_i, _h, _e, "发行说明书·七、现金流分配机制·" + _h.replace(" ", ""))
               for _i, _h, _e in _find_head_body(_H3, _H4)]
    for i, _head_txt, seg_end, basis in _cands:
        # 目录条目已在 _find_head_body 里过滤（紧随 4 个以上点号的跳过）。
        # 下面按「编号位置 → 下一个编号位置」整段收下每一条条款。
        # 起点必须用「编号后的正文起点」m.start(2)，不能用 m.end()——
        #   m.end() 已被同一行的 4–220 字前瞻吃掉，会截掉条款开头几个字。
        if True:
            seg = full[i:seg_end]
            marks = [(m.start(), m.start(2), int(m.group(1)))
                     for m in _WS_ITEM.finditer(seg)]
            steps = []
            for k, (a, b, no) in enumerate(marks):
                end = marks[k + 1][0] if k + 1 < len(marks) else min(len(seg), b + 400)
                raw = seg[b:end]
                # 去掉分页标记与页眉页码（PDF 每页都有「<<<PAGE n>>>」和页脚数字）
                raw = re.sub(r"<<<PAGE\s*\d+>>>", "", raw)
                txt = re.sub(r"[“”]", "", raw)
                txt = re.sub(r"[\s\u3000]+", "", txt)
                txt = re.sub(r"^\d{1,2}(?=[^\d])", "", txt)      # 页脚页码
                txt = re.sub(r"\d{1,2}$", "", txt)                 # 下一页页码尾巴
                if steps and no != steps[-1]["no"] + 1:
                    continue
                if not steps and no != 1:
                    continue
                if len(txt) < 4:
                    continue
                steps.append({"no": no, "text": txt, "kind": _ws_kind(txt)})
            if len(steps) >= 6:
                # 页码：page_text 直接把各页文本拼接成 full，故用累计长度反查字符位置所在页
                _acc, pg = 0, -1
                for _i, _t in enumerate(pages):
                    _acc += len(_t)
                    if _acc > i:
                        pg = _i
                        break
                return {"basis": basis,
                        "page_hint": (f"p{pg + 1}" if pg >= 0 else "分配机制章节"),
                        "steps": steps}
    return None


def iso(s):
    return s


# ★ 文件名含「发行说明书」的不一定是说明书本身：
#   建鑫2021年第八期同时有
#     `关于建鑫2021年第八期…发行说明书的更正说明.pdf`（2 页盖章页）
#     `建鑫2021年第八期…发行说明书.pdf`（正文）
#   glob 按字典序取第一个 → 命中「关于…更正说明」，只有 2 页，
#   于是 units/发行规模/入池全部取不到（表现为"发行 None、入池 0 亿"）。
#   排除规则：更正/复核/变更/补充说明一律不是正本。
_SM_EXCL = ("更正", "复核", "变更", "补充说明", "关于《", "关于建")


def find_prospectus(proj):
    """在下载目录里挑出**说明书正本**（排除更正说明等衍生件）"""
    d = os.path.join(proj, "01_下载文档")
    cands = glob.glob(os.path.join(d, "*发行说明书*.pdf"))
    good = [f for f in cands if not any(k in os.path.basename(f) for k in _SM_EXCL)]
    if not good:
        return None
    # 多份时取页数最多的那份（正本必然最厚），避免再被薄薄的附件抢走
    def _npage(f):
        try:
            with fitz.open(f) as _d:
                return _d.page_count
        except Exception:
            return 0
    return max(good, key=_npage)


def parse(proj):
    _sm = find_prospectus(proj)
    sm = [_sm] if _sm else []
    if not sm:
        return None, "缺发行说明书"
    # ★ 优先用 OCR 结果：部分说明书是**扫描件**（0 字）或**字体编码错乱**
    #   （文本层能抽出 16.5 万字，但全是「ᒪㅢжᵕу㢥」这种乱码 —— 兴瑞2021一期 186 页即如此）。
    #   两种情形都只能读 OCR；产物在 02_提取数据/OCR/SM.ocr.txt。
    #   不先读它 → 封面认不出项目名，整单在 02 就中止，后面全部空跑。
    _opp = os.path.join(proj, "02_提取数据", "OCR", "SM.ocr.txt")
    pages = None
    if os.path.exists(_opp) and os.path.getsize(_opp) > 5000:
        _txt = open(_opp, encoding="utf-8", errors="ignore").read()
        _p = {int(a): fix(b) for a, b in
              re.findall(r"<<<PAGE (\d+)>>>(.*?)(?=<<<PAGE|\Z)", _txt, re.S)}
        if _p:
            pages = [_p.get(i + 1, "") for i in range(max(_p))]
    doc = fitz.open(sm[0])
    if pages is None:
        pages = page_text(doc)
    name, year, q = project_name(pages)
    if not name:
        return None, "无法从封面识别项目名"
    P = parse_pool(pages)
    T = parse_tranche(pages, P)
    M = parse_meta(pages, name)
    M, T, note = fill_from_trustee(proj, M, T)
    W = parse_waterfall(pages)
    out = {"meta": M, "pool": P, "tranche": T, "waterfall": W,
           "_src": {"prospectus": os.path.basename(sm[0]), "pages": doc.page_count,
                    "fill": note}}
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r, err = parse(a.proj)
    if err:
        print("失败:", err)
        sys.exit(1)
    out = a.out or os.path.join(a.proj, "02_提取数据", "_sm_parsed.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(r, open(out, "w", encoding="utf-8", newline=""),
              ensure_ascii=False, indent=1)
    P, T, M = r["pool"], r["tranche"], r["meta"]
    print(f"项目 {M['display_name']}  （说明书 {r['_src']['pages']} 页）")
    print(f"  起算日 {M['cutoff_date']} ／ 发行 {M['issue_date']} ／ 首付 {M['first_pay_date']}"
          f" ／ 法定到期 {M['legal_maturity']}")
    print(f"  代码 优先 {M['code_sen']} ／ 次级 {M['code_sub']}")
    print(f"  入池 {P.get('n_loans')} 笔 / {P.get('n_borrowers')} 户"
          f"  本息费 {P.get('balance_total',0)/1e8:.4f} 亿"
          f"  预计回收 {P.get('exp_recovery',0)/1e8:.4f} 亿")
    print(f"  加权逾期 {P.get('wavg_overdue_months')} 月  年龄 {P.get('wavg_age')} 岁"
          f"  收入 {P.get('wavg_income')} 元  授信 {P.get('wavg_credit_limit')} 元")
    # 取数失败时打印不能崩：total 可能为 None（个别期次表述不同），
    # 直接 None/1e8 会抛 TypeError 把整轮解析打断，前面的解析成果全白跑。
    _tot_y = (T.get("total") or 0) / 1e8
    print(f"  发行 {_tot_y:.4f} 亿 = 优先 {((T['senior']['issue'] or 0)/1e8):.4f}"
          f" + 次级 {((T['sub']['issue'] or 0)/1e8):.4f}  次级占比 {T.get('credit_enhance_pct')}")
    print(f"  票面 {T['senior'].get('coupon')}  自留 {T.get('retention_pct')}")
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
