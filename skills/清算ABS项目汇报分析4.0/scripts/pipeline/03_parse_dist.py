# -*- coding: utf-8 -*-
"""建鑫 发行说明书 · 分布表 / 预测回收率 / 预测现金流 / 分配顺序

★ 最容易踩的坑：**分布表的列顺序与中信惠元不同**

  中信惠元：余额 | 余额占比 | 预计回收 | 回收占比 | 笔数 | 笔数占比 | 笔均
  招行建鑫：余额 | 余额占比 | 笔数 | 笔数占比 | 预计回收 | 回收占比 | 笔均

  直接套用中信的列位，会把「笔数」当成「预计回收金额」，占比错到荒唐，
  而且图内还自洽（因为整体一起错）——这正是跨单复用最危险的地方。
  所以本模块**一律按表头关键词动态定位列序**，不写死。

★ 第二个坑：信用卡不良**没有加权平均账龄**，说明书 p128 明确说明单笔资产是
  「多笔刷卡消费/分期交易的合集」，只能披露「加权平均逾期期限」。

用法：
  python 03_parse_dist.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2021年第2期"
"""
import argparse
import glob
import json
import os
import re
import sys

import fitz

NUM = r"-?[\d,]+(?:\.\d+)?"
FIX_NUM = re.compile(r"(?<=\d)[，､](?=\d)")


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
    s = str(s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def pages_of(proj):
    """读发行说明书正文

    ★ 必须排除「更正说明 / 更正公告」：这类函件 1–2 页、文件名同样含「发行说明书」，
      glob 顺序不确定 —— 实测建鑫2021八期 glob[0] 就是《关于…发行说明书的更正说明》
      （2 页 / 49 字），整册因此读成空白，9 个分布维度全空、还被置灰成
      「说明书未披露」，属于拿解析失败去证明"原文没有"的自证式误判。
    ★ 同一本有「更正版」时优先，其次取体积最大的（多出来的往往是完整版）。
    """
    sm = glob.glob(os.path.join(proj, "01_下载文档", "*发行说明书*.pdf"))
    sm = [f for f in sm
          if "更正说明" not in os.path.basename(f) and "更正公告" not in os.path.basename(f)]
    if not sm:
        raise SystemExit("缺发行说明书")
    sm.sort(key=lambda f: ("更正版" not in os.path.basename(f), -os.path.getsize(f)))
    # ★ 优先用 OCR 版：说明书是扫描件或字体编码错乱（抽出 16 万字全是乱码）时，
    #   直接读 PDF 会得到 0 个分布维度，而且会被置灰成「说明书未披露」——
    #   等于拿解析失败去证明原文没有。OCR 产物在 02_提取数据/OCR/SM.ocr.txt。
    _op = os.path.join(proj, "02_提取数据", "OCR", "SM.ocr.txt")
    if os.path.exists(_op) and os.path.getsize(_op) > 5000:
        _t = open(_op, encoding="utf-8", errors="ignore").read()
        _pp = {int(a): fix(b) for a, b in
               re.findall(r"<<<PAGE (\d+)>>>(.*?)(?=<<<PAGE|\Z)", _t, re.S)}
        if _pp:
            return [_pp.get(i + 1, "") for i in range(max(_pp))]
    doc = fitz.open(sm[0])
    return [fix(doc[i].get_text()) for i in range(doc.page_count)]


# ── 表头 → 列序 ─────────────────────────────────────────────
# 表头可能出现的写法（去空白后）与对应字段
# ★ 表头写作逐品种不同，缺一条就整类期次的分布全空（房贷踩过）：
#   信用卡：「未偿本息费余额 / 资产笔数（笔） / 预计回收金额 / 平均每笔余额」
#   房贷  ：「本息余额（万元） / **贷款**笔数 / 预计**可**回收金额 / 平均每笔**本息**余额」
#   ——「预计可回收金额」比「预计回收金额」多一个"可"字，精确 find 完全不中。
HDR_MAP = [
    ("bal_pct", ("未偿本息费余额占比", "未偿本息余额占比", "本息余额占比", "余额占比")),
    # ★ 兴业（兴瑞）余额分布表把余额列写作「**贷款余额（万元）**」，
    #   上面五种写法全不中 → bal 列取不到，整表列序错位：
    #   余额被当成"余额占比"、占比被当成"预计回收"（实测兴瑞2023七期）。
    ("bal", ("未偿本息费余额", "未偿本息余额", "未偿本金余额", "本息余额（万元）",
             "本息余额", "贷款余额（万元）", "贷款余额")),
    ("n_pct", ("资产笔数占比", "贷款笔数占比", "笔数占比")),
    ("n", ("资产笔数（笔）", "资产笔数", "贷款笔数", "贷款笔数（笔）")),
    ("rec_pct", ("预计可回收金额占比", "预计回收金额占比", "预计回收金额（占比）")),
    ("rec", ("预计可回收金额", "预计回收金额")),
    ("avg", ("平均每笔本息余额", "平均每笔待偿余额", "平均每笔余额")),
    # ★ 房贷/对公表比信用卡**多两列**（`平均每笔预计可回收金额`、`加权平均初始抵押率`）。
    #   只认 7 列会让每行剩 2 个数值溢出到下一行：
    #   下一行开头被当成数值续接、标签错位，整段 6 行被丢弃且合计少 27,192 万元
    #   （建鑫2021四期 occupation：18 行只解析出 12 行有效，合计 202,364.50 vs 229,556.74）。
    #   列数必须与原文对齐，多一列都算错。
    ("avg_rec", ("平均每笔预计可回收金额", "平均每笔预计回收")),
    ("ltv", ("加权平均初始抵押率", "加权平均抵押率", "初始抵押率")),
]


def detect_cols(header_text):
    """从表头文本推断列序，返回字段名列表（按出现顺序）

    表头里同一字段可能出现多次（换行重复），按首次出现位置排序即可。
    """
    t = ns(header_text)
    hits = []
    used = set()
    # 先按「更长的关键词优先」避免「余额」吃掉「余额占比」
    for key, pats in HDR_MAP:
        for p in pats:
            i = t.find(p)
            if i >= 0:
                # ★ 同一写法在表头出现多次时取**最后一次**：
                #   表头首列常是"与数据列同名"的区间列（兴业：
                #   `贷款余额（万元）| 贷款笔数 | 笔数占比 | 贷款余额（万元）| 余额占比 | …`，
                #   第一个「贷款余额（万元）」是区间列的抬头）。
                #   取首次会把 bal 定位到区间列 → 整表列序左移一位。
                #   对建行/中信/招行无影响：它们的首列抬头带「区间」二字，
                #   取最后一次仍是同一个数据列（已复核列序不变）。
                _j = t.find(p, i + 1)
                while _j >= 0:
                    i = _j
                    _j = t.find(p, i + 1)
                hits.append((i, key, p))
                break
    hits.sort()
    # 去重：同一字段只取一次
    cols = []
    for _, key, _ in hits:
        if key not in used:
            used.add(key)
            cols.append(key)
    return cols


# 标签行识别：区间、年龄、地区、职业、五级分类等
# 表头词：出现这些词的行不是标签（是表头或说明）
HDR_WORDS = ("未偿本息费余额", "未偿本金余额", "资产笔数", "预计回收", "平均每笔",
             "贷款笔数", "预计可回收", "本息余额",
             "占比", "（万元）", "(万元)", "分布", "万元", "下列", "下述", "注：", "如下",
             "回收率（%）", "回收率(%)", "（占比）", "(占比)", "借款人年龄", "借款人职业",
             "借款人年收入", "借款人所在地区", "借款人授信额度", "未偿本息费余额",
             "五级分类", "贷款逾期时间",
             # ★ 房贷表头特有：末尾多了「加权平均初始抵押率（%）」一列，
             #   不排除的话它会被当成行标签、再跨行把下一行的「次级」拼上去，
             #   得到「加权平均初始抵押率（%）次级」这种脏标签（4 单房贷实测）。
             "加权平均初始抵押率", "初始抵押率", "平均每笔预计可回收")


# 绝不能当行标签的表头残片（只列会真的踩到的，不用 HDR_WORDS 全量，
# 以免改变其他品种已交付单的解析行为）
SKIP_LABEL_WORDS = ("加权平均初始抵押率", "初始抵押率", "平均每笔预计可回收",
                    "平均每笔本息余额", "预计可回收金额（万元）")


def is_number(v):
    return bool(re.fullmatch(NUM + r"%*", v.strip()))


def is_label(line):
    """判断是否为分布表的「区间/分类标签」——用结构启发式，不用白名单

    ★ 为什么不用白名单：招行的职业标签是行业名（教育机构、医疗机构、金融业、
    「贸易、商业、事务所」「建筑、制造业」「酒店、餐厅、娱乐」、个体经营），
    年龄标签是「30岁（含）以下」「30（不含）-40岁（含）」，白名单永远列不全。
    改为：非空、非数值、非表头词、不含句号（排除正文句子）、长度受限。
    """
    s = line.strip()
    if not s or len(s) > 40:
        return False
    if is_number(s):
        return False
    # ★ 先认「区间式标签」再判表头词：
    #   兴业余额/收入分布的最后一行写作「30 万元以上」「100 万元以上」，
    #   里面含「万元」，而 HDR_WORDS 为过滤表头列名收了裸词「万元」，
    #   于是这一行被当表头碎片丢掉 → 该维度末档缺失、合计对不上
    #   （实测兴瑞2023七期 balance 少 12,063.79 万、income 少 2,151.27 万）。
    #   判据：以数字开头且含「以上/以下/（含）/万」的短行，必是区间标签。
    if re.match(r"^[（(]?\d", s) and re.search(r"以上|以下|万元|万$|含", s):
        return True
    if any(w in s for w in HDR_WORDS):
        return False
    if s.endswith(("。", "：", ":")) or "。" in s:
        return False
    if re.match(r"^[\d,]+\.?\d*$", s):          # 纯数字（含千分位）
        return False
    if s.startswith(("第", "注", "（", "(")) and "分布" not in s:
        pass
    return True


def table_header_ok(line):
    """表头行：同时含「未偿」与「占比」等"""
    s = line.strip()
    return ("未偿" in s or "资产笔数" in s or "预计回收" in s) and \
           ("占比" in s or "万元" in s or "笔数" in s)


def _skip_header_lines(lines):
    """返回表头结束后的起始行号：跳过 block 开头的表头碎片

    ★ 为什么需要：PDF 把表头拆成多行碎片（房贷：「加权平均」/「初始抵押」/
      「率（%）」/「平均每笔」/「预计可回」…）。这些碎片满足 is_label 的
      「短且非数字」，会被当成行标签，还把下一个真标签拼上去，得到
      「加权平均初始抵押率（%）次级」「初始抵押率（%）1 年（含）以下」这种脏标签。
      维护"排除词表"堵不住（碎片无穷多），故改为**结构性判定**：
      真标签的定义是「它后面 1~3 行内出现数值」。表头碎片后面紧跟的是别的文字，
      不满足这一条。
    """
    n = len(lines)
    for i in range(n):
        if not is_label(lines[i]):
            continue
        # ★ 必须「紧邻下一行就是数值」，不能放宽到 1~3 行内：
        #   表头碎片「率（%）」后面紧跟的是真标签「1 年（含）以下」，
        #   再下一行才是数值 —— 窗口放宽就会把碎片认成真标签，
        #   得到「率（%）1 年（含）以下」「初始抵押率（%）1 年-2 年（含）」这种脏标签。
        if i + 1 < n and is_number(lines[i + 1].strip()):
            return i
    return 0


def parse_table_block(lines, cols, stop_at_total=True, label_whitelist=None,
                      skip_header=False):
    """按列序把「标签 + N 个数」切成行

    ★ 关键：标签判定用 is_label 的结构启发式；数值按「连续 N 个」聚合。
    stop_at_total=True 时遇到「总计/合计」即停止——地区分布后面还有一张
    「占比最大的 10 个城市」附加表（p148），不截断会把前 10 城市重复计入，
    实测导致 region 从应有的 ~300 行涨到 311 行且含重复。
    """
    ncol = len(cols)
    rows, total = [], None
    i = _skip_header_lines(lines) if skip_header else 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith(("合计", "总计")):
            vals, j = [], i + 1
            while j < n and len(vals) < ncol and is_number(lines[j]):
                vals.append(lines[j].strip())
                j += 1
            if vals:
                total = {"label": s}
                for k, v in zip(cols, vals):
                    total[k] = v
            if stop_at_total:
                break
            i = j
            continue
        # ★ 白名单模式（grade 用）：只认词表里的行标签，其余一律视为表头碎片。
        #   房贷的五级分类表头是**多行碎片**（「加权平均」/「初始抵押」/「率（%）」），
        #   任何"排除词"都堵不住，结果是首行标签被拼成
        #   「加权平均初始抵押率（%）次级」。改用白名单直接定位真标签，最干净。
        if label_whitelist is not None:
            # 支持两种形态：词表（元组）或判定函数（谓词）。
            # 谓词用于「标签无固定词表、但有结构特征」的维度（如逾期档次
            # 必然含 年/天/月/以上/以下，或写成「(90,120」这种数字区间）。
            if callable(label_whitelist):
                ok_lbl = bool(label_whitelist(s))
            else:
                ok_lbl = any(s == w or s.startswith(w) or w in s
                             for w in label_whitelist)
            if not ok_lbl:
                i += 1
                continue
        if not is_label(s):
            i += 1
            continue
        if any(w in s for w in SKIP_LABEL_WORDS):
            i += 1
            continue
        # ★ 标签可能跨行：PDF 会把「30（不含）-40岁（含）」拆成「30（不含）-40」+「岁（含）」，
        #   把「黔东南苗族侗族」+「自治州」拆开。不合并会得到「岁（含）」「治州」这种残标签，
        #   实测导致 age 只有 4 行里 3 行是残的、region 出现 11 个重复标签。
        label, i2, merged = s, i + 1, 0
        while i2 < n and merged < 3:
            v = lines[i2].strip()
            if is_number(v) or v.startswith(("合计", "总计")):
                break
            if is_label(v) and not any(w in v for w in HDR_WORDS) and len(v) <= 14:
                label += v          # 直接拼接（PDF 换行处无空格）
                i2 += 1
                merged += 1
            else:
                break
        s = label
        # 收集紧随其后的数值（允许中间夹非数值的换行碎片）
        vals, j, miss = [], i2, 0
        while j < n and len(vals) < ncol:
            v = lines[j].strip()
            # ★ PDF 会把**同一行的两个数值挤在一个 line 里**（中间 2+ 空格）：
            #   建鑫2021四期职业分布实测 `'26.34   864,708.68'`
            #   —— 它是「平均每笔本息余额」和「平均每笔预计可回收金额」两列。
            #   只判 is_number(整行) 会 miss+1，最终凑不满 ncol → **整行数据被丢弃**，
            #   该维度合计少 27,192 万元（18 行只认 12 行），且占比看着仍自洽。
            #   故先尝试按空白拆分，能拆出多个完整数值就逐个收。
            _parts = [x for x in re.split(r"\s{2,}|\t", v) if x]
            if len(_parts) > 1 and all(is_number(x) for x in _parts):
                vals.extend(_parts)
                miss = 0
                j += 1
                continue
            if is_number(v):
                vals.append(v)
                miss = 0
            else:
                miss += 1
                if miss > 2 or is_label(v):   # 连续 2 个非数值 → 换行/下一个标签
                    break
            j += 1
        if len(vals) >= ncol:
            rec = {"label": s}
            ok = True
            for k, v in zip(cols, vals):
                if k.endswith("_pct"):
                    rec[k] = v if v.endswith("%") else v + "%"
                elif k == "n":
                    # ★ 笔数可能带小数：2022 一期逾期分布首行写作 `28,110.00`，
                    #   原逻辑要求纯整数 [\d,]+，匹配失败 → 整行丢弃 →
                    #   该维度笔数少 2.8 万、余额少 13.5 亿，但占比看着仍自洽，极难发现。
                    if not re.fullmatch(r"[\d,]+\.?\d*", v):
                        ok = False
                        break
                    rec[k] = int(float(v.replace(",", "")))
                else:
                    rec[k] = fnum(v)
            if ok:
                rows.append(rec)
                i = j
                continue
        i += 1
    return rows, total


# ── 各分布节的定位（★ 用「标题切片」而不是「关键词命中页」）────
# 实测教训：PDF 里小标题常出现在**页尾**（下一页内容的开始），数据在下一页。
# 用「关键词命中页」定位会让每个维度整体错位一页——
# 例如「（二）五级分类」标题在 p129 尾，数据在 p130 头，结果把 p129 的余额分布
# 当成五级分类，还把「次级类 70.09%」当成了笔数。
# 正确做法：定位标题的字符位置，截到下一个标题之前，再在切片内解析。
SECTIONS = [
    # ★ 房贷类写「未偿本息**金额**分布」（本息 + 金额，两个词都多出来），
    #   且章节是「第八章 基础资产分布信息」下的「（一）贷款分布」子表，
    #   与信用卡的「入池资产的未偿本息费余额分布」完全不同名。
    ("balance", ["入池资产的未偿本息费余额分布", "未偿本息费余额分布", "未偿本息余额分布",
                 "未偿本息余额金额分布", "未偿本息费余额金额分布", "贷款余额分布"]),
    # ★ 「贷款种类分布」是**房贷**品种对五级分类的叫法：标题换成"种类"，
    #   表体仍是「次级 / 可疑 / 损失」三档（建鑫2021四/七期 p161、2023四/七期 p153）。
    #   只认「五级分类」四个字会让 4 单房贷的五级分类整块判成"说明书未披露" ——
    #   而原文白纸黑字就在那里，属于最危险的一类错：拿解析失败去证明"原文没有"。
    #   安全性由 parse_dist 的表体校验保证（行标签必须命中五级分类词表才采纳）。
    ("grade", ["贷款质量（五级分类）分布", "贷款五级分类分布", "五级分类分布", "贷款质量分布",
               "贷款种类分布"]),
    ("guarantee", ["贷款担保情况分布", "贷款担保方式分布", "担保情况分布", "担保方式分布"]),
    ("overdue", ["贷款逾期时间分布", "逾期时间分布", "逾期期限分布",
                 "历史累计贷款逾期时间分布", "贷款逾期时间分"]),
    # ★ 主体称谓逐行不同，别名必须全收：
    #     中信/招行：「借款人年龄分布」
    #     建行      ：「入池资产的**债务人**年龄分布」（章节名「二、入池资产债务人特征」）
    #   只认「借款人…」会把建行这几张表整块判成"源未披露"，
    #   报告里就变成置灰格（实测建鑫2021-2 的 age/income/region/occupation 全被误判）。
    ("age", ["借款人年龄分布", "入池资产的借款人年龄分布",
             "入池资产的债务人年龄分布", "债务人年龄分布",
             "入池资产的借款人年龄分布表"]),
    ("region", ["借款人所在地区分布", "借款人地区分布",
                "入池资产的债务人所在地区分布", "债务人所在地区分布",
                "入池资产的债务人地区分布", "债务人地区分布"]),
    ("occupation", ["借款人职业分布", "入池资产的债务人职业分布",
                    "债务人职业分布", "入池资产的债务人职业状况分布"]),
    ("income", ["借款人年收入分布", "借款人收入分布",
                "入池资产的债务人年收入分布", "债务人年收入分布",
                "入池资产的债务人收入分布", "债务人收入分布"]),
    ("creditlimit", ["借款人授信额度分布", "借款人账户授信额度分布", "账户授信额度分布",
                     "入池资产的债务人授信额度分布", "债务人授信额度分布",
                     "入池资产的债务人加权平均授信额度分布"]),
    # ★ 贷款账龄：房贷/对公类披露，信用卡/消费贷不披露（已在 ABSENT_BY_VARIETY 声明）
    ("age_loan", ["贷款账龄分布", "入池资产贷款账龄分布", "加权平均贷款账龄分布"]),
]

# 品种层面**结构性缺失**的维度（不是解析失败）
# ★ 这里是「品种不适用」的判定台：命中即置灰，并在报告里写明「本品种未做该项统计」，
#   不允许静默消失 —— 否则跑出来的报告比中信/招行少好几块图，读者会以为漏了。
ABSENT_BY_VARIETY = {
    "信用卡不良": {
        "guarantee": "信用卡不良为纯信用、无抵押担保，说明书不披露担保方式分布",
        "age_loan": "单笔资产为多笔消费/分期交易的合集，无法统计贷款账龄，改用加权平均逾期期限",
    },
    "个人消费不良": {
        "age_loan": "单笔资产为多笔消费/分期交易的合集，说明书不披露贷款账龄分布，以加权平均逾期期限替代",
    },
    "个人住房抵押不良": {
        # 房贷有抵押物、有账龄，缺的是消费贷那类「授信额度/年收入」画像
        "creditlimit": "个人住房抵押贷款为一次性放款，无循环授信额度概念，说明书不披露该分布",
    },
    "个人经营不良": {},
    # ★ 品种名要和 payload.meta.variety 逐字一致，否则命中不了字典键，
    #   缺的维度会被写成「说明书未披露」（听起来像我们没找到），
    #   而实际是**本品种不统计这些画像**。建行小微经营单实测三个品种名并存：
    #   「小微经营不良」/「个人经营不良」，都要登记。
    "小微经营不良": {
        "age": "借款人为小微经营主体（企业/个体工商户），说明书不披露借款人年龄分布",
        "occupation": "借款人为小微经营主体，说明书不披露职业分布",
        "income": "借款人为小微经营主体，说明书不披露借款人年收入分布",
        "creditlimit": "小微经营贷为一次性放款，无循环授信额度概念，说明书不披露该分布",
    },
}
ABSENT = ABSENT_BY_VARIETY["信用卡不良"]      # 兼容旧调用（无品种信息时的默认）


def _dist_chapter_start(pages):
    """定位「基础资产分布信息」正文章节起始页（0 基），取不到退回 120

    ★ 原实现把 lo 写死 120（建行说明书的分布章节在 p121 之后）。
      兴业（兴瑞）的分布章节在 **p110** 左右，写死 120 会把整章跳过 →
      split_by_headings 返回空、9 个分布维度全判"未披露"、
      预测回收率分布 0 行。实测兴瑞2023七期即如此。
      改为按「第八章 基础资产分布」正文页自适应，各家用同一套代码。
      判据：该页含「基础资产分布」且**不含**连续 4 个以上点号（排除目录页）。
    """
    for i, t in enumerate(pages):
        n = ns(t)
        if "基础资产分布" in n:
            if re.search(r"[.．]{6,}", n):
                continue            # 目录页
            if i >= 3:              # 封面/声明不算
                return max(0, i - 2)
    return 120


def split_by_headings(pages, lo=None):
    """把说明书按「（X）…分布」/「X、…」标题切片，返回 {标题文本: 切片文本}

    只扫描 lo 之后的页（分布章节在说明书后部，前文有目录会误命中）。
    title 也会出现在目录页，故用 lo 跳过。
    """
    if lo is None:
        lo = _dist_chapter_start(pages)
    full, offs = [], []
    for i, t in enumerate(pages):
        offs.append(sum(len(x) for x in full))
        full.append(t)
    text = "".join(full)
    # 标题里可能自带括号（「贷款质量（五级分类）分布」），所以不能用 [^\n（(] 排除括号，
    # 否则该节直接被漏掉；也不能跨行（[^\n]）。
    HEAD = re.compile(
        r"[（(][一二三四五六七八九十]+[）)]\s*[^\n]{2,30}?分布"
        r"|[一二三四五六七八九十]+、\s*[^\n]{2,26}?分布"
        # ★ 阿拉伯数字序号也能引出分类小节：「1、历史累计贷款逾期时间分布」
        #   （2021四期 p162）。缺这条会把整节漏掉，overdue 直接判成"未披露"。
        r"|\d{1,2}[、.．]\s*[^\n]{2,30}?分布"
        # ★ 标题被排版截断：「（四）贷款逾期时间分」（少了"布"字，换行收尾）。
        #   2021四期原文如此，整节因此切不出来 → overdue 置灰（原文其实有）。
        r"|[（(][一二三四五六七八九十]+[）)]\s*[^\n]{2,30}?分(?=\s*\n)", re.M)
    start = offs[min(lo, len(offs) - 1)] if offs else 0
    ms = [(m.start(), m.end(), m.group(0)) for m in HEAD.finditer(text, start)]
    out = {}
    for k, (a, b, title) in enumerate(ms):
        end = ms[k + 1][0] if k + 1 < len(ms) else min(len(text), b + 12000)
        key = ns(title)
        # 归一化：先去掉编号（括号式与顿号式分别处理——用 | 会让「一、」只吃掉「一」），
        # 再去掉「分布」后缀。曾因写成单个 | 正则导致键名残留「、」。
        key = re.sub(r"^[（(][一二三四五六七八九十]+[）)]\s*", "", key)
        key = re.sub(r"^[一二三四五六七八九十]+、\s*", "", key)
        key = key.replace("分布", "").strip()
        out[key] = text[b:end]
    return out


def pick_block(blocks, names):
    """按名称匹配切片。names 可为字符串或别名列表（多写法兼容）

    ★ 两个已踩的坑，都必须在这里挡掉：
      ① `k in name` 对空串恒真 —— 切片里会出现 '贷款'(len=2)、'借款人'(len=2) 这类
         由章节标题「二、借款人分布」误切出的空壳块，它会把「借款人年龄」整块顶掉，
         结果 age/region/occupation/income/creditlimit 五个维度全部 len=2、解析为空。
      ② 泛型短键抢先命中 —— '贷款' 会命中「贷款五级分类」，取到的却是空壳。
    故：先精确匹配；再做包含匹配时要求键长 ≥3、且按键长降序取最长者（最具体优先）。
    """
    if isinstance(names, str):
        names = [names]

    def _ok(v):
        # ★ 空壳块不算命中：新增「1、/2、」子标题的切分后，父标题
        #   「（四）贷款逾期时间分」会切出一个几乎没有内容的空壳，
        #   精确匹配到它就会让整节数据丢失（实测房贷 4 单 overdue 因此变空）。
        #   判定标准同调用方：去空白后 < 40 字符。
        return bool(v) and len(ns(v)) >= 40

    for n in names:
        if n in blocks and _ok(blocks[n]):
            return blocks[n]
    for n in names:
        n2 = n.replace("分布", "")
        if n2 in blocks and _ok(blocks[n2]):
            return blocks[n2]
    cands = []
    for n in names:
        n2 = n.replace("分布", "")
        for k, v in blocks.items():
            if len(k) < 3 or k == "预计回收率":
                continue
            if n2 in k or k in n2:
                cands.append((len(k), k, v))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][2]


CANON_DIMS = ["balance", "grade", "guarantee", "overdue", "age",
              "region", "occupation", "income", "creditlimit"]


def parse_dist(pages, variety=None):
    """解析全部分布维度；返回 (D, meta)

    ★ meta['_gray'] 是「置灰清单」：本单**统一范本里有、但这单没有**的维度。
      分两种性质，报告里必须区别标注：
        · 品种不适用（ABSENT_BY_VARIETY 命中）→ 「本品种未做该项统计」
        · 有披露但解析失败/未披露 → 「说明书未披露」
      两种都置灰而不是删掉，否则与中信/招行并排时块数不一致，读者无法判断
      是"这单没有"还是"这单漏做了"。
    """
    blocks = split_by_headings(pages)
    D, meta = {}, {}
    for key, names in SECTIONS:
        blk = pick_block(blocks, names)
        if not blk or len(ns(blk)) < 40:
            continue
        # ★ 表头锚点逐品种不同，房贷写「未偿本息余额」（无"费"字），
        #   只认「未偿本息费余额」会让房贷 9 个分布表全部解析为空
        #   （表现为 dist 只剩 recrate，dist_gray 里 9 个维度全标"未披露"）。
        _b = ns(blk)
        hi = -1
        for _anchor in ("未偿本息费余额", "未偿本息余额", "本息余额（万元）",
                        "本息余额占比", "贷款笔数"):
            hi = _b.find(_anchor)
            if hi >= 0:
                break
        hdr = _b[hi:hi + 170] if hi >= 0 else _b[:170]
        cols = detect_cols(hdr)
        if not cols or len(cols) < 4:
            continue
        lines = [x.strip() for x in blk.splitlines() if x.strip()]
        _wl = None
        if key == "grade":
            # 五级分类行标签是固定词
            _wl = ("正常", "关注", "次级", "可疑", "损失")
        elif key == "overdue":
            # ★ 逾期档次没有固定词表，但结构特征很强：
            #   含 年/天/月/以上/以下，或写成「(90,120」「360 天以上」这类。
            #   房贷表头碎片（「加权平均」「初始抵押」「率（%）」）一个都不满足，
            #   所以用谓词就能把它们全部挡在标签之外 —— 不必猜表头在第几行。
            # ★ 区间左括号有两种：`(90,120` 和 **`[0,4]`**（闭区间，兴业用）。
            #   原谓词只认 `(`，兴业的 `[0,4]` 首个档次被排除 →
            #   逾期分布少一整档（余额 115,332.84 万，占 56%），
            #   而其余档次之和看着仍"像个分布"，极难发现。
            _wl = lambda s: bool(re.search(r"年|天|月|以上|以下|含", s)) \
                or bool(re.match(r"^[（(\[\s]*\d", s))
        rows, total = parse_table_block(lines, cols, label_whitelist=_wl)
        # ★ grade 的表体校验：「贷款种类分布」这个标题在不同产品里含义不同
        #   （房贷＝五级分类；也有产品按 信用/抵押/保证 分"种类"）。
        #   只有当行标签命中五级分类词表时才采纳，否则视为未披露，
        #   绝不用标题硬猜——否则会把担保方式当五级分类塞进报告。
        if key == "grade" and rows:
            _GRADE_WORDS = ("正常", "关注", "次级", "可疑", "损失", "次级类", "可疑类", "损失类")
            if not any(any(w in str(r.get("label", "")) for w in _GRADE_WORDS)
                       for r in rows):
                continue
        if rows:
            D[key] = rows
            meta[key + "_cols"] = cols
            if total:
                meta[key + "_total"] = total

    absent = dict(ABSENT_BY_VARIETY.get(variety or "", {}))
    # 「预计回收率分布」单独一张表（列数与其它不同），由 parse_recrate 处理
    gray = {}
    for k in CANON_DIMS + ["recrate"]:
        if k in D:
            continue
        if k in absent:
            gray[k] = {"kind": "variety", "why": absent[k]}
        else:
            gray[k] = {"kind": "undisclosed",
                       "why": "发行说明书未披露该分布表（已核 p120–p127 全部分布章节）"}
    # age_loan（贷款账龄）不在 CANON 里：中信/招行/建鑫三行说明书均无该表
    gray["age_loan"] = {"kind": "variety",
                        "why": absent.get("age_loan",
                                          "说明书未披露逐笔贷款账龄分布，改以加权平均逾期期限刻画")}
    meta["_absent"] = absent
    meta["_gray"] = gray
    return D, meta


def parse_recrate(pages):
    """三、预测回收率分布表（6 列：余额/占比/笔数/笔数占比/预计回收/回收占比，**无 avg**）

    ★ 与其它分布表列数不同：本表没有「平均每笔余额」，若沿用 7 列会整表错位。
    """
    blocks = split_by_headings(pages)
    blk = pick_block(blocks, "预测回收率") or ""
    if not blk:
        # 兜底：章节标题「三、预测回收率分布表」也被切成切片，键名可能是「预测回收率」
        for k, v in blocks.items():
            if "回收率" in k:
                blk = v
                break
    if not blk:
        return []
    lines = [x.strip() for x in blk.splitlines() if x.strip()]
    cols = ["bal", "bal_pct", "n", "n_pct", "rec", "rec_pct"]
    rows, _ = parse_table_block(lines, cols)
    return rows


def _month_end(base_iso, n):
    """自 base 起第 n 个月的月末（n 从 1 计）

    ★ 为什么需要：建行说明书预测表用「第N 月」而不是具体日期，
      无法直接与支付日比较。按「初始起算日 + N 个月」的月末推算，
      与说明书「本期期初日 = 初始起算日」（建鑫2021-2：2021-01-01）一致。
      推算口径会写进 payload.fc_date_basis，报告图注据此标注，不当成源披露日期。
    """
    import calendar
    y, m = int(base_iso[:4]), int(base_iso[5:7])
    # ★ 「第1 月」对应 base 所在月，故偏移是 n-1，不是 n。
    #   写成 n 会把整表推后一个月（第1 月→下月末），与支付日比较时整体错位。
    tot = (m - 1) + (n - 1)
    y += tot // 12
    m = tot % 12 + 1
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def parse_forecast(pages, cutoff=None):
    """四、现金流回收预测表：日期 | 期初 | 本期回收 | 期末

    支持两种体例：
      ① 日 期 体例（中信/招行）：「2023/7/31 | 期初 | 回收 | 期末」
      ② 月 序 体例（建行）    ：「第1 月 | 82,416.68 | 10,372.66 | 72,044.02」
        —— 建行不给归集日期，只给月份序号；月份数字与「月」之间常有空格。
    """
    # ★ 日期行前可能带杂字符：2022 三期原文是 `y2023/2/28`（PDF 排版残留一个 y），
    #   用 ^ 锚定会漏掉该行 → 现金流少一期、衔接断裂、合计对不上。
    #   故允许行首有 1-2 个非数字字符。
    DATE = re.compile(r"^[^\d]{0,2}(\d{4})[/-](\d{1,2})[/-](\d{1,2})\D{0,2}$")
    # ★ 兴业（兴瑞）预测表给的是**区间**，不是单日：
    #     `2024/1/1-2024/3/31`  期初本息总余额 | 本期预计回收金额 | 期末本息总余额
    #   上面 DATE 要求行尾无非数字，区间式会整行落空 → 预测表现金流为空，
    #   「预测回收 × 达成率」链全断。这里单独认区间式，取**区间右端（期末）**
    #   作为该期的计算日：与「计算日（收款期间期末日期）」这个表头口径一致。
    RANGE = re.compile(r"^[^\d]{0,2}(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*[-—~至]\s*"
                       r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})\D{0,2}$")
    # 月序体例：`第1 月` / `第 12 月` / `第1个月`（OCR 偶把「月」打成「个月」）
    MON = re.compile(r"^第\s*(\d{1,3})\s*个?\s*月\D{0,3}$")
    # ★ 兴业（兴瑞）体例：`2023 年10 月` —— 中文年月、带空格、无「日」。
    #   只认上面 DATE/MON 会让整张预测表落空（实测兴瑞2023七期 0 期）→
    #   「预测回收 vs 实际达成率」整条链断掉。按「年 + 月」取**当月月末**。
    YM = re.compile(r"^[^\d]{0,2}(\d{4})\s*年\s*(\d{1,2})\s*月\D{0,3}$")
    # ★ 页码下限不能写死 120：建行预测表在 p183 之后，兴业在 **p111** ——
    #   写死 120 会让兴业整张预测表落空（实测 0 期），达成率链断。
    #   改为「落在分布章节之后」。
    _lo = _dist_chapter_start(pages)
    for i, t in enumerate(pages):
        if "现金流回收预测表" in ns(t) and i >= _lo:
            block = t + "".join(pages[i + 1:i + 3])
            lines = [x.strip() for x in block.splitlines() if x.strip()]
            out, j = [], 0
            # ★ 末期「期末预期本息回收余额」常写作 `-` 表示 0（2021 四期 2023/7/31 行即如此）。
            #   只认 NUM 会把整行丢掉，导致「末期期末不为 0」误报、合计也少一期。
            DASH = ("-", "—", "－", "‐", "--")
            ok = lambda x: bool(re.fullmatch(NUM, x)) or x.strip() in DASH
            while j < len(lines):
                m = DATE.match(lines[j])
                mo = MON.match(lines[j])
                rg = None if (m or mo) else RANGE.match(lines[j])
                ym = None if (m or mo or rg) else YM.match(lines[j])
                if (m or mo or rg or ym) and j + 3 < len(lines):
                    a, b, c = lines[j + 1], lines[j + 2], lines[j + 3]
                    if all(ok(x) for x in (a, b, c)):
                        conv = lambda x: 0.0 if x.strip() in DASH else fnum(x)
                        if m:
                            lab = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                        elif rg:
                            # 区间式取右端（期末日）
                            lab = (f"{rg.group(4)}-{int(rg.group(5)):02d}-"
                                   f"{int(rg.group(6)):02d}")
                        elif ym:
                            # 「2023 年10 月」→ 该月月末
                            import calendar as _cal
                            _y, _mo2 = int(ym.group(1)), int(ym.group(2))
                            lab = (f"{_y:04d}-{_mo2:02d}-"
                                   f"{_cal.monthrange(_y, _mo2)[1]:02d}")
                        else:
                            # 月序体例：需要 cutoff 才能推日期；没有就退回「第N 月」标签，
                            # 由调用方决定是否弃用（绝不瞎编具体日期）
                            lab = (_month_end(cutoff, int(mo.group(1)))
                                   if cutoff else f"第{int(mo.group(1))}月")
                        _a, _b2, _c = conv(a), conv(b), conv(c)
                        # ★ 首期/无回收期常见缩写：「期初 167,282.64 | 回收 - | 期末 -」
                        #   （建鑫2021四期房贷 p183 实测原样 `2021/4/28167,282.64--`）
                        #   两格破折号的含义是「本期无回收、余额不变」，期末应等于期初。
                        #   留 0 会让「期初＝上期期末」的系统性校验在首期就断裂，
                        #   还会把预测余额曲线头一段压成 0。
                        if _c == 0.0 and _b2 == 0.0 and _a:
                            _c = _a
                        out.append([lab, _a, _b2, _c])
                        j += 4
                        continue
                j += 1
            # ★ 去重 ＋ 日期单调：block 取的是「本页 + 后两页」，收入分布章那几页
            #   常把同一张预测表再排一遍，于是末尾会多出一行早期日期
            #   （建鑫2022二期：表本来到 2024-12-31 期末 0.00，后面又冒出
            #    2024-07-31 期初 1,188,000.00）→「期初＝上期期末」校验在倒数第二行断裂。
            #   只保留日期/月序**严格递增**的首现行。
            def _key(lab):
                mm = re.match(r"^第(\d+)月$", str(lab))
                return (0, int(mm.group(1))) if mm else (1, str(lab))
            _seen, _mono = set(), []
            for r in out:
                if r[0] in _seen:
                    continue
                if _mono and _key(r[0]) <= _key(_mono[-1][0]):
                    continue
                _seen.add(r[0])
                _mono.append(r)
            return _mono
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    a = ap.parse_args()
    pages = pages_of(a.proj)
    # 品种决定「哪些维度是品种性缺失」（置灰而非报错）
    _variety = None
    _smp0 = os.path.join(a.proj, "02_提取数据", "_sm_parsed.json")
    if os.path.exists(_smp0):
        _variety = ((json.load(open(_smp0, encoding="utf-8")).get("meta") or {})
                    .get("variety"))
    D, META = parse_dist(pages, variety=_variety)
    rr = parse_recrate(pages)
    # 预计回收率分布表是独立一张表（无 avg 列），解析成功即从置灰清单里摘掉
    if rr and "recrate" in (META.get("_gray") or {}):
        del META["_gray"]["recrate"]
    # 预测表体例判定：月序体例需要「初始起算日」才能推日期
    _cutoff = None
    if os.path.exists(_smp0):
        _cutoff = ((json.load(open(_smp0, encoding="utf-8")).get("meta") or {})
                   .get("cutoff_date"))
    fc = parse_forecast(pages, cutoff=_cutoff)
    _fc_basis = None
    if fc and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(fc[0][0])):
        _fc_basis = "说明书为月序体例（第N 月），未给归集日期"
    # ★ 现金流预测表单位逐行不同：招行（和萃）用**元**，建行（建鑫）用**万元**。
    #   建行原文首行：`2021-03-31  36,061.54  7,272.16  28,789.37`（万元）
    #   若不换算，预测回收只有 3.6 万元，与中债 3.6 亿差 1 万倍，
    #   「累计回收曲线」和「达成率分母」全错。
    #   判定：拿首行期初余额与说明书入池本息费比，量级差 1e4 即万元制。
    if fc:
        _b0 = fc[0][1]
        # 判据用「预测回收合计 vs 中债预计回收」：两者应同量级。
        #   建行该表以「预计回收」为口径列示（首行期初 36,061.54 = 中债预计回收
        #   360,615,400 元 / 1e4），与入池本息费不是同一分母，故不能用入池本息费比。
        _ref = None
        _smp = os.path.join(a.proj, "02_提取数据", "_sm_parsed.json")
        _rtp = os.path.join(a.proj, "02_提取数据", "_rating_parsed.json")
        if os.path.exists(_rtp):
            _ref = (json.load(open(_rtp, encoding="utf-8")) or {}).get("exp_recovery")
        if not _ref and os.path.exists(_smp):
            _ref = (json.load(open(_smp, encoding="utf-8")).get("pool") or {}).get("balance_total")
        _sum = sum(x[2] for x in fc)
        _ratio = (_ref / _sum) if (_ref and _sum) else None
        # ★ 双判据，防止对照值取错来源导致漏换算：
        #   ① 相对中债预计回收的比值落在 5e3–2e4（该表本就是"预计回收"口径，首选）
        #   ② 比值落在 8e3–1.2e4 的极窄带（≈1 万倍），不论 _ref 来自哪张表都认
        #   曾因 07 排在 03 之后、_ref 退回"入池本息费"，比值 21 万落在窗口外，
        #   于是 26,388.52 万元被当成 26,388 元，全表差 1 万倍。
        if (_ratio and 5e3 < _ratio < 2e4) or (_ratio and 8e3 <= _ratio <= 1.2e4):
            fc = [[d, round(a1 * 1e4, 2), round(b1 * 1e4, 2), round(c1 * 1e4, 2)]
                  for d, a1, b1, c1 in fc]
            print(f"  现金流预测表按**万元**换算（预测合计 {_sum:,.2f} × 1e4，"
                  f"对照值 {_ref:,.2f}，比值 {_ratio:,.0f}）")
    # ── 扫描件专用：坐标还原结果并入 ────────────────────────────────
    # ★ 说明书是扫描件时（兴瑞2021一期 字体编码错乱 / 2023四期 纯图片），
    #   文本解析拿不到任何分布表，若任由它空着，报告会把 9 个维度全置灰成
    #   「说明书未披露」—— 等于拿解析失败去证明原文没有。
    #   这两单由 _ocr_xy2.py + _xy_dist.py 按版面坐标还原（表头在页底/并排/
    #   跨页都能对上），且每个维度都已用「余额合计＝入池本息费」硬校验过，
    #   这里只做合并；未通过校验的维度不会出现在 _dist_xy.json 里。
    _xyp = os.path.join(a.proj, "02_提取数据", "_dist_xy.json")
    if os.path.exists(_xyp):
        _xy = json.load(open(_xyp, encoding="utf-8"))
        # ★ 坐标版**优先覆盖**文本解析结果，而不是"有值就不动"：
        #   扫描件的文本解析虽然能凑出一张表，但列与列之间是错位的 ——
        #   实测兴瑞2023四期 grade 被解析成 bal=12,096（那是**笔数**）、
        #   n=55,764（那是**余额**）、bal_pct='5,464.21%'（那是**预计回收金额**），
        #   而每一行的数字都在、格式也像模像样，只看单行查不出来。
        #   坐标版每个维度都过了「余额合计＝入池本息费」硬校验（误差 < 200 元），
        #   所以它才是可信的那一份。
        _added, _over = [], []
        for _k, _v in (_xy.get("dist") or {}).items():
            if not _v:
                continue
            if D.get(_k):
                _over.append(_k)
            D[_k] = _v
            META[_k + "_cols"] = ["bal", "bal_pct", "n", "n_pct", "rec", "rec_pct"]
            META.setdefault("_xy_src", {})[_k] = ((_xy.get("meta") or {}).get(_k)
                                                  or {}).get("src")
            # ★ 必须同时从 dist_gray 里摘掉：扫描件下文本解析失败，
            #   这 9 个维度会被一律写成「说明书未披露」；坐标还原成功后再留着，
            #   报告就自相矛盾了（同一维度既"未披露"又有 7 行数据），
            #   而且分布网格按 gray 画灰格 → SVG 只有 5 张，断言当场 FAIL。
            (META.get("_gray") or {}).pop(_k, None)
            _added.append(_k)
        # ★ 仍未取到的维度：灰格理由必须写**真实原因**。
        #   扫描件单的文本解析一条都没成，原来的理由会写成「说明书未披露」——
        #   而说明书里明明有这张表（只是扫描件版面还原不了），
        #   等于拿"解析失败"去证明"原文没有"，这是最不该出现的一类自证。
        _rej = (_xy.get("meta") or {}).get("_rejected") or {}
        for _k in list((META.get("_gray") or {}).keys()):
            if _k in D or _k in ("recrate", "age_loan"):
                continue
            _g = META["_gray"][_k]
            if not isinstance(_g, dict):
                _g = {"kind": "undisclosed", "why": str(_g)}
                META["_gray"][_k] = _g
            if _g.get("kind") == "undisclosed":
                _g["kind"] = "scan-unparsable"
                _g["why"] = (_rej.get(_k) or
                             "说明书为扫描件／字体编码错乱，该分布表按版面坐标还原后"
                             "仍无法与入池本息费勾稽，未采信；详见原件对应页表")
        if _added:
            print(f"  坐标还原并入 {len(_added)} 个维度：{_added}"
                  + (f"（覆盖文本解析错位结果：{_over}）" if _over else ""))

    out = {"dist": D, "dist_meta": META, "recrate": rr, "forecast_flow": fc,
           "fc_date_basis": _fc_basis}
    p = os.path.join(a.proj, "02_提取数据", "_dist_parsed.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)

    print(f"分布维度 {len(out['dist'])} 个：")
    for k, v in out["dist"].items():
        cols = META.get(k + "_cols", [])
        print(f"  {k:14s} {len(v):>3} 行  列序 {'|'.join(cols)}")
    for k, why in META.get("_absent", {}).items():
        print(f"  {k:14s} 本品种无此维度：{why[:40]}")
    print(f"\n预测回收率分布 {len(rr)} 行")
    print(f"预测现金流 {len(fc)} 期  首 {fc[0] if fc else '—'}")
    if fc:
        print(f"  期末余额末值 {fc[-1][3]:,.2f}（应为 0）")
    print(f"\n→ {p}")


if __name__ == "__main__":
    main()
