# -*- coding: utf-8 -*-
"""扫描版说明书：按坐标还原分布表（兴瑞 2021一期 / 2023四期 专用）

★ 这两单的说明书都是扫描件，但版面结构**不一样**，必须分别处理：

  ① 横排表（兴瑞2023四期）
     行=类别（广州/南宁/(18,30]…），列=指标，列 x 固定：
        424 类别 | 769 贷款笔数 | 1115 笔数占比 | 1460 贷款余额
        | 1806 余额占比 | 2152 预计回收金额 | 2497 金额占比
     麻烦只在**表头被拆成三行**（「笔数占比@1113」+「(%)@1116」），
     纯文本解析会把它当成三条数据行的开头。

  ② 转置表（兴瑞2021一期）
     指标名在**左侧第一列**（贷款余额/余额占比/笔数占比/贷款笔数/预计回收金额/金额占比），
     类别标签在**表格最后一行**（(0,5] … 60万元以上 总计），而且常与其他表**并排**、
     「合计」列还会跨页。纯文本按文本框顺序输出，两批混在一起 → 顺序配对必错位，
     **而错位后「合计」照样对得上**（合计永远是最后一个值），属最难发现的一类错。

★ 判据全部来自结构，不猜：
  · 维度 = 表头**首列名**（「逾期时间 (天)」→overdue、「年龄 (岁)」→age …）。
    不用类别内容去猜 —— 年龄区间 (18,30] 与逾期区间 (90,120] 长得一模一样。
  · 每个维度落盘前用「余额合计 = 入池本息费」硬校验，对不上就丢弃并留痕。
"""
import json
import os
import re
import sys

B = r'E:/兴业银行兴瑞冒烟测试'
Y_TOL = 14
X_GAP = 130

HEAD2DIM = [
    ("逾期", "overdue"), ("年龄", "age"),
    ("五级分类", "grade"), ("贷款种类", "grade"),
    ("担保", "guarantee"), ("地区", "region"),
    ("职业", "occupation"), ("年收入", "income"),
    ("收入", "income"), ("授信额度", "creditlimit"),
    ("贷款余额", "balance"), ("余额", "balance"),
]
# 指标名片段 → 列键（顺序：长词在前，避免「余额占比」被「余额」抢走）
IND2KEY = [
    ("笔数占比", "n_pct"), ("余额占比", "bal_pct"), ("金额占比", "rec_pct"),
    ("预计回收金额", "rec"), ("贷款笔数", "n"), ("贷款余额", "bal"),
    ("预计回收", "rec"), ("笔数", "n"), ("余额", "bal"),
]
TOTAL_WORDS = ("合计", "总计")


def num(t):
    s = t.replace(",", "").replace("，", "").replace(" ", "").replace("．", ".")
    try:
        return float(s)
    except Exception:
        return None


def rows_of(boxes, tol=Y_TOL):
    bs = sorted(boxes, key=lambda a: a[1])
    out, cur, cy = [], [], None
    for x, y, t in bs:
        if cy is None or abs(y - cy) <= tol:
            cur.append((x, y, t))
            cy = y if cy is None else (cy * (len(cur) - 1) + y) / len(cur)
        else:
            out.append(cur)
            cur, cy = [(x, y, t)], y
    if cur:
        out.append(cur)
    return [sorted(r, key=lambda a: a[0]) for r in out]


def split_groups(row, gap=None):
    """把一行按 x 间隙切成若干「并排的表」

    ★ 阈值必须**自适应**，不能写死：
      2023四期的列间距约 345px（版心很宽、只有 7 列），
      写死 130 会把每一列都当"不同的表"切开，行只剩单个 cell，
      整页数据因此全部作废（实测该单直接"无可靠还原"）；
      2021一期表内间距 66–100、并排表之间 216，写死 345 又切不开。
      取「该行间距中位数 × 2.2、且不低于 120」两种情况都覆盖：
        345×2.2=759 → 345 < 759 不切（对）
        70×2.2=154  → 216 > 154 切开（对）
    """
    if not row or len(row) < 2:
        return [row] if row else []
    gaps = sorted(b[0] - a[0] for a, b in zip(row, row[1:]) if b[0] > a[0])
    if not gaps:
        return [row]
    med = gaps[len(gaps) // 2]
    lim = max(120.0, med * 2.2) if gap is None else gap
    groups, cur = [], [row[0]]
    for prev, now in zip(row, row[1:]):
        if now[0] - prev[0] > lim:
            groups.append(cur)
            cur = [now]
        else:
            cur.append(now)
    groups.append(cur)
    return groups


def dim_of(head):
    for kw, d in HEAD2DIM:
        if kw in head:
            return d
    return None


def key_of(ind):
    for kw, k in IND2KEY:
        if kw in ind:
            return k
    return None


def nearest_col(xs, x, tol=None):
    if not xs:
        return None
    gaps = [b - a for a, b in zip(xs, xs[1:])] or [200]
    lim = tol if tol is not None else max(45.0, min(gaps) / 2.0)
    j = min(range(len(xs)), key=lambda i: abs(xs[i] - x))
    return j if abs(xs[j] - x) <= lim else None


def parse_transposed(block_rows):
    """转置表：块内有一行是类别行（含合计/总计），其余行首列是指标名"""
    head = None
    for r in block_rows:
        if any(any(w == t or t.startswith(w) for w in TOTAL_WORDS)
               for _x, _y, t in r[1:]):
            head = r
            break
    if head is None:
        return None
    head_txt = [head[0][2]]
    for x, y, t in head[1:]:
        if not re.match(r"^[（(]", t):
            break
        head_txt.append(t)
    hname = "".join(head_txt)
    dim = dim_of(hname)
    if not dim:
        return None
    keep = [(x, t) for x, _y, t in head
            if not any(w == t or t.startswith(w) for w in TOTAL_WORDS)]
    if len(keep) < 2:
        return None
    xs = [x for x, _t in keep]
    labels = [t for _x, t in keep]
    vals = {}
    for r in block_rows:
        if r is head:
            continue
        k = key_of(r[0][2])
        if k is None:
            continue
        for x, _y, t in r[1:]:
            v = num(t)
            if v is None:
                continue
            j = nearest_col(xs, x)
            if j is None or j in vals.get(k, {}):
                continue
            vals.setdefault(k, {})[j] = v
    rows_out = []
    for j, lab in enumerate(labels):
        d = {"label": lab}
        for k, m in vals.items():
            if j in m:
                d[k] = m[j]
        if d.get("bal") is not None:
            rows_out.append(d)
    return dim, rows_out, hname


def parse_flat(block_rows):
    """横排表：首列是类别名，其余列是指标数值；表头在其上方的若干行"""
    data, heads = [], []
    for r in block_rows:
        txt_first = r[0][2]
        nums = [c for c in r[1:] if num(c[2]) is not None]
        # ★ 与 _is_data_row 同一判据：只看「首列能否解析成金额」，**不要求含中文**。
        #   逾期/年龄档次是 `[0,5]`、`(18,30]`，整串无汉字；加中文要求会让它们
        #   全部落到 heads 里，data 只剩「30 以上」一行（实测 balance 只出 1 行）。
        if num(txt_first) is None and len(nums) >= 3:
            data.append(r)
        else:
            heads.append(r)
    if not data:
        return None
    allx = sorted({round(c[0] / 40) * 40 for r in data for c in r[1:]})
    xs = []
    for x in allx:
        if xs and x - xs[-1] < 45:
            continue
        xs.append(x)
    if len(xs) < 3:
        return None
    col_txt = {i: [] for i in range(len(xs))}
    first_col = []
    for r in heads:
        for x, _y, t in r:
            if abs(x - data[0][0][0]) < 60:
                first_col.append(t)
                continue
            j = nearest_col(xs, x, tol=60)
            if j is not None:
                col_txt[j].append(t)
    head_str = "".join(first_col)
    dim = dim_of(head_str)
    if not dim:
        return None
    keys = {i: key_of("".join(v)) for i, v in col_txt.items()}
    rows_out = []
    for r in data:
        d = {"label": r[0][2]}
        for x, _y, t in r[1:]:
            v = num(t)
            if v is None:
                continue
            j = nearest_col(xs, x)
            if j is None or keys.get(j) is None:
                continue
            d.setdefault(keys[j], v)
        if d.get("bal") is None:
            continue
        if any(w == d["label"] or d["label"].startswith(w) for w in TOTAL_WORDS):
            continue
        rows_out.append(d)
    if not rows_out:
        return None
    return dim, rows_out, head_str


def _has_total(row):
    """该行是否含「合计/总计」（表尾行）"""
    return any(any(w == t or t.startswith(w) for w in TOTAL_WORDS)
               for _x, _y, t in row[1:])


def _is_data_row(r):
    """首列不是「单个金额」、且右侧有 ≥3 个纯数值 cell

    ★ 首列判据只能用 «num() 解析失败»，**不能**再要求含中文：
      逾期/年龄档次的类别名是 `(18,30]`、`[0,4]`、`(90,120]`，
      整串没有一个汉字，加中文要求会把它们全部判成非数据行 →
      数据行只剩"合计"那一行，整表作废（实测 2023四期 13 段全是 2 行）。
    """
    return (num(r[0][2]) is None
            and sum(1 for c in r[1:] if num(c[2]) is not None) >= 3)


def _rows_and_segments(rows):
    """把一页的行切成 (表头行列表, 数据行列表) 若干段

    ★ 判据按「数据行连续性」分段，再按首列是不是指标名区分版式：
      · 转置表（2021一期）：数据行首列是**指标名**（贷款余额/余额占比…），
        类别行在其**下方**且含「合计/总计」；
      · 横排表（2023四期）：数据行首列是**类别名**（广州/(18,30]…），
        表头在其**上方**，且被 OCR 拆成 2–3 行（「笔数占比」+「(%)」）。
      不能用「首列 x」聚：2023四期的表首列 x 全部等于 424（版心左边界），
      会把年龄表与地区表混成一块，数值跨表串列（实测 age 合计差 +87 亿）。
    """
    segs, i, n = [], 0, len(rows)
    while i < n:
        if not _is_data_row(rows[i]):
            i += 1
            continue
        # ★ 段在「合计/总计」行处结束：一个表只有一行合计，合计之后必是下一张表。
        #   不切的话，两表会连成一段（兴瑞2023四期 p105「担保方式」的合计行后面
        #   紧跟「逾期时间」的分类行、中间没有表头）→ 11 行被当成担保方式，
        #   合计 14 亿对不上 40.5 亿，整表作废。
        j = i
        while j + 1 < n and _is_data_row(rows[j + 1]) and not _has_total(rows[j]):
            j += 1
        data = rows[i:j + 1]
        trans = all(key_of(r[0][2]) is not None for r in data)
        if trans:
            # 类别行在下方
            k = j + 1
            while k < n and not _is_data_row(rows[k]) and k - (j + 1) < 3:
                if any(any(w == t or t.startswith(w) for w in TOTAL_WORDS)
                       for _x, _y, t in rows[k][1:]):
                    segs.append(("trans", rows[k], data))
                    break
                k += 1
        else:
            # 表头在上方（最多回溯 4 行）
            head, k = [], i - 1
            while k >= 0 and not _is_data_row(rows[k]) and len(head) < 4:
                head.insert(0, rows[k])
                k -= 1
            segs.append(("flat", head, data))
        i = j + 1
    return segs


def collect(proj):
    """按页切「并排表」，再把整页的 cell 按 x 范围裁剪成单表，最后按数据行分段

    ★ 三层都必需，任何一层省掉都会算错：
      ① **并排**（2021一期一页 2–3 张表、行 y 相同）：不按 x 切开，
         「金额占比@384」会和「金额占比@900」「金额占比@1296」挤在同一行；
      ② **表头横向分散**（2023四期）：表头是「贷款笔数@769 | 笔数占比@1115 |
         贷款余额@1460 | 余额占比@1806 | 预计回收金额@2152 | 金额占比@2497」，
         本身就被 x 距离拉开 —— 若按「首列 x 分桶」归块，表头会被拆到 4–5 个桶里，
         数据行那一桶只剩「贷款余额/预计回收」两个列名，其余列全取不到
         （实测该单 balance 只剩 1 行 2 亿）；
         故改为：先按并排切出 x 范围，再把**整页每个 cell**按该范围筛选，
         表头与数据行自然对齐；
      ③ **分段**：块内按数据行连续性分段，遇「合计」即收尾。
    """
    op = os.path.join(B, proj, '02_提取数据', 'OCR', '_xy.json')
    xy = json.load(open(op, encoding='utf-8'))
    found = []
    for pn in sorted(xy, key=int):
        rows = rows_of(xy[pn])
        widest = None
        for r in rows:
            if _is_data_row(r) and (widest is None or len(r) > len(widest)):
                widest = r
        if widest is None:
            continue
        for g in split_groups(widest):
            lo, hi = g[0][0] - 50, g[-1][0] + 80
            sub = [[c for c in r if lo <= c[0] <= hi] for r in rows]
            sub = [s for s in sub if len(s) >= 2]
            for kind, head, data in _rows_and_segments(sub):
                if kind == "trans":
                    res = parse_transposed([head] + data)
                else:
                    res = parse_flat(data + (head or []))
                if res:
                    dim, rows_out, hname = res
                    found.append((dim, rows_out, int(pn), hname))
    return found


def main():
    projs = [a for a in sys.argv[1:] if not a.startswith('-')] or \
        ['兴瑞2021年第一期', '兴瑞2023年第四期']
    for proj in projs:
        pj = os.path.join(B, proj, '02_提取数据', 'payload.json')
        pool = 0.0
        if os.path.exists(pj):
            pool = (json.load(open(pj, encoding='utf-8')).get('pool') or {}).get(
                'balance_total') or 0.0
        print(f'== {proj}  pool={pool:,.2f}')
        tol = max(1.0, (pool or 0) * 0.002)
        REJ = {}
        segs = {}
        for dim, rows_out, page, head in collect(proj):
            segs.setdefault(dim, []).append((rows_out, page, head))

        def _ok(rs):
            return bool(pool) and abs(sum(r.get("bal") or 0.0 for r in rs) * 1e4
                                      - pool) <= tol

        best = {}
        for dim, lst in segs.items():
            # 单段就对上，直接用
            hit = [x for x in lst if _ok(x[0])]
            if hit:
                pick = max(hit, key=lambda x: len(x[0]))
                best[dim] = pick
                tot = sum(r.get("bal") or 0.0 for r in pick[0]) * 1e4
                print(f'   {dim:12s} {len(pick[0]):2d} 行 合计 {tot:>16,.2f} '
                      f'{"OK":>18s} p{pick[1]} 头={pick[2][:16]}')
                continue
            # 跨页表：同维度多段按 label 合并后再校验
            merged, seen = [], set()
            for rs, _pg, _h in lst:
                for r in rs:
                    lab = r["label"]
                    if lab in seen:
                        continue
                    seen.add(lab)
                    merged.append(r)
            tot = sum(r.get("bal") or 0.0 for r in merged) * 1e4
            ok = bool(pool) and abs(tot - pool) <= tol
            print(f'   {dim:12s} {len(merged):2d} 行 合计 {tot:>16,.2f} '
                  f'{"OK(合并跨页)" if ok else "差 " + format(tot - pool, "+,.0f"):>18s} '
                  f'<{len(lst)} 段>')
            if ok:
                best[dim] = (merged, lst[0][1], lst[0][2])
            else:
                REJ[dim] = (f"扫描件表格版面无法可靠还原：按坐标还原后余额合计 "
                            f"{tot:,.2f} 元与入池本息费 {pool:,.2f} 元不符"
                            f"（差 {tot - pool:+,.2f}），为避免给出错位数已置灰；"
                            f"请查原件对应页表")
        D, meta = {}, {}
        for dim, (rows_out, page, head) in best.items():
            D[dim] = [{"label": r["label"], "bal": round(r["bal"], 2),
                       "bal_pct": r.get("bal_pct"), "n": r.get("n"),
                       "n_pct": r.get("n_pct"),
                       # rec 与 bal 同为**万元**（表头写的就是「预计回收金额（万元）」），
                       # 不能再除 1e4 —— 除了会变成 0.55，图里画不出来、断言也读不懂。
                       "rec": (round(r["rec"], 2) if r.get("rec") else None),
                       "rec_pct": r.get("rec_pct")} for r in rows_out]
            meta[dim] = {"src": f"扫描件坐标还原·说明书 p{page}·表头「{head}」"}
        if D:
            op = os.path.join(B, proj, '02_提取数据', '_dist_xy.json')
            json.dump({"dist": D, "meta": {**meta, "_rejected": REJ}},
                      open(op, 'w', encoding='utf-8', newline=''),
                      ensure_ascii=False, indent=1)
            print(f'   → {op}  维度 {len(D)}：{list(D)}')
        else:
            print('   无可靠还原')
        if REJ:
            print(f'   未能可靠还原 {len(REJ)} 个：{list(REJ)}')
    print('XY DIST DONE')


if __name__ == '__main__':
    main()
