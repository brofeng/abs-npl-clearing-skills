# -*- coding: utf-8 -*-
"""招行项目共用：数字清洗（OCR 千分位误读）

各脚本都 import 这里的 fix/fnum，避免每个脚本各写一套导致行为不一致。
踩过的坑（都在本文件里处理）：
  1. 千分位逗号被读成点：185.000.000.00 → 185,000,000.00
  2. 千分位与小数点混用：350.997,548.71 / 49.000,000.00
  3. 两个金额粘连：350.997,548.71350,997,548.71（需靠上游正则约束）
  4. 形近字符：数字中的 Q/O → 0
  5. 全角逗号：1，234.56
"""
import re

DASH = ("-", "—", "－", "‐", "--", "/")
FIX_NUM = re.compile(r"(?<=\d)[，､](?=\d)")
NUM = r"-?[\d,]+(?:\.\d+)?"


def fix(t):
    t = FIX_NUM.sub(",", t or "")
    t = re.sub(r"(?<=\d)[QOo](?=[\d.])", "0", t)

    def _fixnum(m):
        tok = m.group(0)
        parts = tok.split(".")
        if len(parts) < 3:
            return tok
        if not all(len(x) == 3 for x in parts[1:-1]):
            return tok
        if len(parts[-1]) not in (2, 1, 0):
            return tok
        return ",".join(parts[:-1]) + "." + parts[-1]

    # ★ 不能用 \b：中文字符在 Python re 里算 \w，所以「证券450.000,000.00」中
    #   450 前面**不是**词边界，\b 会导致整段跳过清洗。
    #   实测 2023 五期「优先档资产支持证券450.000,000.00元」因此没被修正，
    #   正则匹配不到本金 → 分档兑付全为 None。
    #   改用「前后不是数字或分隔符」的 lookaround。
    t = re.sub(r"(?<![\d.,])\d[\d.]*\d(?![\d.,])", _fixnum, t)

    def _fixmix(m):
        tok = m.group(0)
        if not ("." in tok and "," in tok):
            return tok
        last = max(tok.rfind("."), tok.rfind(","))
        head, tail = tok[:last], tok[last + 1:]
        if len(tail) not in (2, 1) or not tail.isdigit():
            return tok
        if not re.fullmatch(r"\d[\d.,]*", head):
            return tok
        # ★ 关键收窄：只有当「小数点之前的部分里还含点」时，才是真正的混用
        #   （450.000,000.00 → head="450.000,000" 含点 → 需归一）。
        #   若 head 里只有逗号（13,781.70 → head="13,781"），那已是标准千分位，
        #   必须原样保留——归并成 13781.70 虽数值等价，但会破坏下游
        #   「千分位严格形态」正则，导致金额取不到。
        if "." not in head:
            return tok
        norm = re.sub(r"[.,]", "", head)
        # ★ 长度护栏：单个金额的整数部分不可能超过 12 位（千亿级已是上限）。
        #   实测 2023 六期 `520,700.00`+`3,019,800.00` 粘连成
        #   `520,700.003,019,800.00`，归一后正好 15 位，逃过了 15 位护栏，
        #   变成 520 万亿，直接把分档合计毁掉。
        #   超长说明这是**两个金额粘连**，例如
        #   `211,934,660.10` + `211,934,660.10` = `211,934,660.10211,934,660.10`，
        #   直接归一会合并成 21193466010211934660.10 这种天文数字，
        #   而且下游再也切不开（实测 2023 五期逐期回收全部丢失）。
        #   这种情况保持原样，交给下游「千分位严格形态」正则去切分。
        # ★ 阈值 12 → 11（含 12 位一律不归一）：建行/招行/中信三类不良的资产池
        #   最大约 31.5 亿（11 位），**12 位＝千亿级不可能出现**；而粘连的两列
        #   小额很容易正好拼成 12 位 —— 实测建鑫2021八期清算报告
        #   `合格投资 24,159.91 24,159.91`（本期/累计同值）粘连后归一成
        #   241,599,124,159.91（2415 亿），账户结息取成天文数字且无人报错。
        if len(norm) > 11:
            return tok
        return norm + "." + tail

    return re.sub(r"(?<![\d.,])\d[\d.,]*\d(?![\d.,])", _fixmix, t)


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


# ── 金额粘连切分 ────────────────────────────────────────────
# 千分位数字的严格形态（保留给下游正则引用）
NUMGRP = r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"

_SEP = ".,"
# 单笔金额的严格形态：首组 1-3 位 + 若干 3 位千分位组 + 2 位小数
#   注意千分位可能是 `.` 也可能是 `,`（OCR 常把两者读混）
_PIECE = re.compile(r"^\d{1,3}(?:[.,]\d{3})*[.,]\d{2}$")
# 整数部分位数上限：千亿级已是上限，超过说明是「两笔粘连」而非一笔
_MAXIP = 12


def _piece_value(piece, strict=False):
    """把一个严格形态的金额串转成 (值, 前导零罚分, 小数点符号异常数)；非法返回 None

    strict=True：额外要求**千分位分隔符同种**（`5.310,800.00` 这类会被否掉）。
    只有在 caller 明确知道「这一段本该是两个同列的金额」时才用（见 06 的 _money_after），
    不能当默认——真实的千分位混用金额会被误杀。

    ★ 罚分的用途：`5.310.800.002,411,200.00` 既能切成
      `5.310.80` + `02,411,200.00`，也能切成 `5.310.800.00` + `2,411,200.00`，
      段数相同、数值都合法，只能靠「真实金额的整数部分不会以 0 开头」来分优劣。
      （实测 2023 四期第 8 期兑付表靠这条才选对，否则优先档本金少 8 个数量级。）
    """
    if not _PIECE.match(piece):
        return None
    # ★★ 硬合法性：小数点只能有 1 个。
    #   若同一段里 `.` 出现 ≥2 次**且**还存在 `,`，说明有两个 `.`，
    #   其中一个被当成了千分位——这在实际金额里不可能（千分位只会用同一种符号）。
    #   典型：`2,086,027.400.00`（其实 = 2,086,027.40 + 0.00）
    #   这条必须在"段数最少"之前挡掉，否则 DP 会选 1 段解，
    #   得 2,086,027,400（比真值大 1000 倍），
    #   导致建鑫2023四期 TR01 优先档利息 20.86 亿 > 发行额 9.4 亿、XIRR 无解。
    #   注意不能一刀切禁"`.` 出现 ≥2 次"：OCR 常把全部逗号认成点
    #   （`5.310.800.00`），那种情况没有 `,`，必须放过。
    if piece.count(".") >= 2 and piece.count(",") >= 1:
        return None
    last = max(piece.rfind("."), piece.rfind(","))
    if strict:
        # ★ 千分位分隔符混用即否：`24,159.9124,159.91` 是同一金额的本期/累计两列粘连，
        #   宽松切法会拼成 241,599,124,159.91（2415 亿）一个数，
        #   而真实的单笔金额不会让千分位一半逗号一半点（那只会出现在粘连处）。
        if len(set(c for c in piece[:last] if c in ".,")) > 1:
            return None
    # ★★ 小数点符号异常：中文财报里小数位**永远用点**（`,` 只作千分位）。
    #   若某一段把逗号当成了小数点（`10,492,000.003,11` 的小数位是 `11`），
    #   基本可以断定这是伪切分——它把下一格的「3,」吞进了小数位。
    #   这个信号用来做**软判别**（不计入硬合法性）：真实的千分位混用
    #   （`5.310,800.00`，OCR 把某个逗号认成点）绝不能被否掉，
    #   故只排序、不拒解。
    _dot_bad = 0 if piece[last] == "." else 1
    ip = piece[:last].replace(".", "").replace(",", "")
    dp_ = piece[last + 1:]
    if not ip or len(ip) > _MAXIP:
        return None
    pen = 1 if (len(ip) > 1 and ip[0] == "0") else 0
    return float(ip + "." + dp_), pen, _dot_bad


def _split_run(run, cap=None, strict=False):
    r"""把一串连续数字/分隔符切成最少的合法金额，返回 [float, ...]

    ★ 为什么不能靠单一正则：`5.310.800.002,411,200.00` 其实等于
      5,310,800.00 + 2,411,200.00（OCR 把相邻两格连成一串）。
      正则会两种错法：`[\d,]+\.\d{2}` 只吃到 `5.31` 然后一路碎成
      [5.31, 0.8, 0.0, 241.0, 120.0, 0.0]；`\d{1,3}(?:[.,]\d{3})+[.,]\d{2}`
      又会把整串吞成一个 16 位数。

    ★ 做法：动态规划。把「分隔符 + 恰 2 位数字 + 后面紧跟数字/串尾」的每个
      位置都当作**候选小数点**，对所有可行切分求「段数最少、小数点符号正常、
      前导零最少、首段吃满」的解。
      再用「整数部分 ≤ 12 位」把「一笔天文数字」这种伪解排掉——真实的单笔
      金额不会超过千亿，超过就是两笔粘连。
    """
    n = len(run)
    if n == 0:
        return []

    # 候选断点 end：run[end-2:end] 是两位小数，run[end-3] 是分隔符，
    # 且 run[end] 是数字（下一笔的开头）或已到串尾
    ends = set()
    for j in range(1, n - 2):
        if run[j] in _SEP and run[j + 1:j + 3].isdigit():
            e = j + 3
            if e <= n and (e == n or run[e].isdigit()):
                ends.add(e)
    ends = sorted(ends)

    memo = {}

    def best(i):
        """返回 (段数, 小数点符号异常数, 前导零罚分, 数值列表, 首段长度取负)"""
        if i == n:
            return (0, 0, 0, [], 0)
        if i in memo:
            return memo[i]
        res = None
        if run[i].isdigit():
            for e in ends:
                if e - i < 4:
                    continue
                pv = _piece_value(run[i:e], strict)
                if pv is None:
                    continue
                v, pen, dot_bad = pv
                sub = best(e)
                if sub is None:
                    continue
                # ★ 判别键，按优先级：
                #   ① 段数最少（粘连串的正确切法一定不多切）
                #   ② 小数点符号异常最少（逗号当小数点的解一律后置）
                #      —— 建鑫2021一期 TR05：`10,492,000.003,115,800.00`
                #      的伪解 `[10,492,000.003,11 | 5,800.00]` 段数、罚分都不差，
                #      但它的小数位用了逗号，正是"把下一格的 3, 吞进小数位"的证据；
                #      真解 `[10,492,000.00 | 3,115,800.00]` 两段都是点，胜出。
                #      改前 24 期里 7 期次级本金合计小于兑付额（少 311 万而不报错）。
                #   ③ 前导零罚分
                #   ④ 首段吃满（OCR 粘连是相邻两格连写，前格一定写完）
                cand = (sub[0] + 1, sub[2] + pen, sub[1] + dot_bad,
                        [v] + sub[3], -(e - i))
                # ★ 比较键必须是前面几个**标量**，不能把数值列表放进去比
                #   （Python 比较列表是逐元素比大小，等于随机决胜）。
                #   优先级：段数 → 前导零 → 小数点符号异常 → 首段吃满。
                #   小数点符号放在第 3 位（不是第 2 位）是实测结论：
                #   放到第 2 位会把 `5.310,800.00` 这种"千分位混用但小数点是点"
                #   的真解挤掉（建鑫2021二期优先档本金会碎成 5.31 + 800.00）；
                #   而第 1 位的"吞掉下一格首位数"另有**恒等式**兜底（见 parse_tranche
                #   的「兑付前本金 − 兑付本金 = 剩余本金」逐档定解），不必靠这里猜。
                if res is None or cand[:3] + (cand[4],) < res[:3] + (res[4],):
                    res = cand
        memo[i] = res
        return res

    got = best(0)
    if got is None:
        # 兜底：老路径（无小数的整数金额等），保证行为不退化
        v = fnum(fix(run))
        return [v] if v is not None else []
    vals = got[3]
    if cap is not None and len(vals) > cap:
        vals = vals[:cap]
    return vals


def split_money(text, maxn=None, strict=False):
    """从 OCR 文本里按出现顺序切出所有金额，能处理「两笔金额首尾粘连」

    maxn：只要前 maxn 个（下游按列取值时用，避免把下一格的数也吃进来）
    strict：要求每段千分位同种（仅用于「已知是两列同值」的场景，见 _money_after）。
    """
    out = []
    for m in re.finditer(r"-|—|－|\d[\d.,]*\d", text or ""):
        tok = m.group(0)
        if tok in ("-", "—", "－"):
            out.append(0.0)            # 表格里的「-」＝ 0
        else:
            remain = None if maxn is None else maxn - len(out)
            out.extend(_split_run(tok, remain, strict))
        if maxn and len(out) >= maxn:
            break
    return out[:maxn] if maxn else out


def money_at(text):
    """按出现顺序返回 [(起始位置, 金额)]

    用途：OCR 把表格压平后，数值可能跑到**标签前面**，靠「标签右切」取不全，
      要拿到带位置的序列才能用恒等式定解。例（建鑫2023五期 TR06）：
        `票面利率2.56% 67.455.000.00 本期兑付前本金值 130,000,000.00`
      ——67,455,000.00（优先档兑付前本金）落在标签左侧，右切只剩次级发行额。

    ★ 粘连 + 百分号的处理：`196,000,000.0076.56%` 是「发行额 + 占比76.56%」，
      金额**不该**因为整串后面跟着 % 就被丢掉（那样会往后取到日期 262028）。
      规则：串被 % 收尾时只丢掉**最后一段**（占比永远是末尾那一段）。
      纯利率 `2.56%` 只有一段，丢完为空，正好不当作金额。
    """
    out = []
    txt = text or ""
    for m in re.finditer(r"-|—|－|\d[\d.,]*\d", txt):
        tok = m.group(0)
        if tok in ("-", "—", "－"):
            continue
        pieces = _split_run(tok)
        if txt[m.end():m.end() + 1] in ("%", "％"):
            pieces = pieces[:-1]
        for v in pieces:
            out.append((m.start(), v))
    return out

