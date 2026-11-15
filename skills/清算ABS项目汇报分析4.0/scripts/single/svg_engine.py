# -*- coding: utf-8 -*-
"""SVG 引擎 —— 严格对齐 v11 报告的绘图规格（自 v11 view-p1 渲染后 SVG 反推）

规格备忘（与 v11 一致，不得自创）：
· 折线图   viewBox 0 0 680 240；绘图区 x∈[68,658]、y∈[40,200]；网格 6 档
           轴文字 11px #697487（.v2c-ax）；单位注 10.5px #98A2B3；x 轴 11px #697487（.v6-xlabel）
           实线 #A52524 1.6px；虚线 #98A2B3 1.6px dasharray 7 5；点 r=3 fill #fff stroke 1.7
           面积渐变 #A52524 .26 → 0
· 瀑布     viewBox 0 0 680 300；绘图区 x∈[68,658]、y∈[50,246]
· 分布图   viewBox 0 0 352 182；双轴（左金额 9.5px #98A2B3 / 右百分比 9.5px #8A94A6）
           柱 #2D3955 rx 1.5；柱顶标签 9.5px #38425A；x 轴旋转 10px #5B6472
· 交互     <rect class="v2c-band"> 透明热区 + <title> 做 tooltip（v11 原生机制）
"""
import math

# v11 设计令牌（与 base CSS 的 :root 一致）
INK, INK2, INK3, INK4 = "#1A2230", "#4B5566", "#79849A", "#A6AFBE"
SUB, MUTE = "#697487", "#98A2B3"
AXIS_LOW, AXIS_GRID = "#C9D2E0", "#E6EBF3"
RED, NAVY, GREEN, AMBER = "#A52524", "#2D3955", "#1F7A5C", "#B0763F"
RAMP = ["#2D3955", "#45516E", "#5F6B87", "#7D889F", "#9BA5B8", "#BCC4D2"]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_num(v, nd=2):
    return f"{v:,.{nd}f}"


def nice_ticks(vmax, n=5):
    """取整齐刻度（1/2/2.5/5 × 10^k）"""
    if vmax <= 0:
        return [0, 1], 1
    raw = vmax / n
    p = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * p:
            step = m * p
            break
    else:
        step = 10 * p
    top = math.ceil(vmax / step) * step
    ticks = []
    v = 0.0
    while v <= top + step * 0.001:
        ticks.append(round(v, 10))
        v += step
    return ticks, top


# ---------------- 单调三次插值（Fritsch–Carlson）→ 不过冲的贝塞尔 ----------------
def mono_path(pts):
    n = len(pts)
    if n < 2:
        return ""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    dx = [xs[i + 1] - xs[i] for i in range(n - 1)]
    dy = [ys[i + 1] - ys[i] for i in range(n - 1)]
    m = [dy[i] / dx[i] if dx[i] else 0.0 for i in range(n - 1)]
    tang = [m[0]] + [0.0] * (n - 2) + [m[-1]]
    for i in range(1, n - 1):
        if m[i - 1] * m[i] <= 0:
            tang[i] = 0.0
        else:
            w1, w2 = 2 * dx[i] + dx[i - 1], dx[i] + 2 * dx[i - 1]
            tang[i] = (w1 + w2) / (w1 / m[i - 1] + w2 / m[i])
    d = f"M{xs[0]:.1f},{ys[0]:.1f}"
    for i in range(n - 1):
        h = dx[i] / 3.0
        d += (f" C{xs[i]+h:.1f},{ys[i]+tang[i]*h:.1f} "
              f"{xs[i+1]-h:.1f},{ys[i+1]-tang[i+1]*h:.1f} {xs[i+1]:.1f},{ys[i+1]:.1f}")
    return d


# ==================== 累计回收曲线（实际实线 / 预计虚线） ====================
def recon_line(actual, forecast, xlabels, xtitles, unit="亿元", W=680, H=240,
               name_a="累计实际回收", name_f="累计预计回收", nd=2,
               bars=None, name_b="当期回收（柱）"):
    """actual/forecast: 等长数值列表（单位由调用方换算好）；None 表示该期无数据
    bars: 可选，逐期回收额（柱），与累计线共用 y 轴。
    """
    L, R, T, B = 68, 22, 40, 40
    x0, x1 = L, W - R
    y0, y1 = T, H - B
    _bars = list(bars) if bars else []
    allv = [v for v in list(actual) + list(forecast) + _bars if v is not None]
    ticks, top = nice_ticks(max(allv) * 1.02, 5)
    n = len(xlabels)
    step = (x1 - x0) / max(1, n - 1)

    def Y(v):
        return y0 + (y1 - y0) - (y1 - y0) * (v / top)

    def X(i):
        return x0 + step * i

    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="累计回收曲线（实际实线 / 预计虚线{"/ 当期回收柱" if _bars else ""}）" '
         f'style="width:100%;height:auto;display:block" class="v2c-svg">']
    g.append('<defs><linearGradient id="v_ar" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{RED}" stop-opacity=".26"></stop>'
             f'<stop offset="1" stop-color="{RED}" stop-opacity="0"></stop>'
             '</linearGradient></defs>')
    # 网格 + 左轴
    for t in ticks:
        yy = Y(t)
        g.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{AXIS_LOW if t == 0 else AXIS_GRID}" stroke-width="1"></line>')
        g.append(f'<text class="v2c-ax" x="{x0-10}" y="{yy+4:.1f}" text-anchor="end" '
                 f'font-size="11" fill="{SUB}">{fmt_num(t, nd)}</text>')
    g.append(f'<text class="v2c-note" x="{x0}" y="{T-20}" font-size="10.5" fill="{MUTE}">'
             f'单位：{unit}</text>')
    # 图例（无预测数据时不显示“预计”图例；有柱时增加柱图例）
    has_f = any(v is not None for v in forecast)
    if not _bars:
        lx = W - R - (196 if has_f else 96)
        _legs = [(name_a, RED, "")]
        if has_f:
            _legs.append((name_f, MUTE, ' stroke-dasharray="7 5"'))
        for nm, col, dash in _legs:
            g.append(f'<rect x="{lx}" y="{T-26}" width="16" height="3" rx="1.5" fill="{col}"></rect>')
            g.append(f'<text class="v2c-leg" x="{lx+22}" y="{T-21}" font-size="11" fill="{INK2}">'
                     f'{esc(nm)}</text>')
            lx += 104
    else:
        _legs = [(name_a, RED, "line")]
        if has_f:
            _legs.append((name_f, MUTE, "dash"))
        _legs.append((name_b, GREEN, "bar"))
        lx = W - R - 104 * len(_legs)
        for nm, col, kind in _legs:
            if kind == "bar":
                g.append(f'<rect x="{lx}" y="{T-29}" width="9" height="9" rx="2" fill="{col}" opacity=".55"></rect>')
            else:
                g.append(f'<rect x="{lx}" y="{T-26}" width="16" height="3" rx="1.5" fill="{col}"></rect>')
            g.append(f'<text class="v2c-leg" x="{lx+22}" y="{T-21}" font-size="11" fill="{INK2}">'
                     f'{esc(nm)}</text>')
            lx += 104
    # x 轴标签（稀疏化：最多 6 个）
    every = max(1, math.ceil(n / 6))
    for i in range(n):
        if i % every and i != n - 1:
            continue
        g.append(f'<text class="v6-xlabel" x="{X(i):.1f}" y="{H-22}" text-anchor="middle" '
                 f'font-size="11" fill="{SUB}"><title>{esc(xtitles[i])}</title>'
                 f'{esc(xlabels[i])}</text>')
    # 当期回收柱（先画，压在累计线下方）
    if _bars:
        _bw = min(20, max(8, step * 0.42))
        for i, v in enumerate(_bars):
            if v is None or v <= 0:
                continue
            _yy = Y(v)
            g.append(f'<rect x="{X(i)-_bw/2:.1f}" y="{_yy:.1f}" width="{_bw:.1f}" '
                     f'height="{max(1.5, y1-_yy):.1f}" rx="2" fill="{GREEN}" opacity=".30">'
                     f'<title>第{i+1}期｜当期回收 {fmt_num(v, nd)} {unit}</title></rect>')
    # 预计（虚线，先画，在下层）
    fp = [(X(i), Y(v)) for i, v in enumerate(forecast) if v is not None]
    if len(fp) >= 2:
        g.append(f'<path d="{mono_path(fp)}" fill="none" stroke="{MUTE}" stroke-width="1.6" '
                 f'stroke-dasharray="7 5" stroke-linecap="round"></path>')
    for x, y in fp:
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#fff" stroke="{MUTE}" '
                 f'stroke-width="1.7"></circle>')
    # 实际（实线 + 面积）
    ap = [(X(i), Y(v)) for i, v in enumerate(actual) if v is not None]
    if len(ap) >= 2:
        area = (f'M{ap[0][0]:.1f},{ap[0][1]:.1f} '
                + mono_path(ap)[mono_path(ap).find(" C"):] +
                f' L{ap[-1][0]:.1f},{y1:.1f} L{ap[0][0]:.1f},{y1:.1f} Z')
        g.append(f'<path d="{area}" fill="url(#v_ar)"></path>')
        g.append(f'<path class="v2c-anim" d="{mono_path(ap)}" fill="none" stroke="{RED}" '
                 f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"></path>')
    # 热区 + 点（带 title tooltip）
    for i in range(n):
        if actual[i] is None and forecast[i] is None and not (_bars and i < len(_bars) and _bars[i]):
            continue
        tip = xtitles[i]
        if actual[i] is not None:
            tip += f'｜累计实际 {fmt_num(actual[i], nd)} {unit}'
        if forecast[i] is not None:
            tip += f'｜累计预计 {fmt_num(forecast[i], nd)} {unit}'
        if _bars and i < len(_bars) and _bars[i] is not None:
            tip += f'｜当期回收 {fmt_num(_bars[i], nd)} {unit}'
        g.append(f'<rect class="v2c-band" data-i="{i}" x="{X(i)-step/2:.1f}" y="{y0}" '
                 f'width="{step:.1f}" height="{y1-y0}"><title>{esc(tip)}</title></rect>')
        if actual[i] is not None:
            g.append(f'<circle class="v2c-dot" data-r0="4.4" cx="{X(i):.1f}" cy="{Y(actual[i]):.1f}" '
                     f'r="4.4" fill="{RED}" stroke="#fff" stroke-width="1.8" '
                     f'pointer-events="none"></circle>')
    g.append("</svg>")
    return "".join(g)


# ==================== 瀑布（期初 → 流入 → 逐级扣减 → 期末） ====================
def waterfall(steps, unit="亿元", W=680, H=300, nd=2, large=False):
    """steps: [(label, value, kind)]  kind∈{open,in,out,sec,close}
    约定：open/close 为绝对高度柱；in 向上累加；out/sec 向下累减

    large=True 时字号整体 +1（普通单项目报告用）；LEGACY_TEXT 旧交付件保持原字号。
    """
    fs_unit = 12 if large else 10.5
    fs_ax = 12 if large else 11
    fs_leg = 12 if large else 10.5
    fs_val = 11.5 if large else 9.5
    fs_x = 11.5 if large else 9.5
    fs_foot = 11 if large else 9.5
    L, R, T, B = 68, 22, 50, 54
    x0, x1 = L, W - R
    y0, y1 = T, H - B
    n = len(steps)
    bw = (x1 - x0) / n
    bar = min(46, bw * 0.56)
    run = 0.0
    bars = []
    for lb, v, kind in steps:
        if kind in ("open", "close"):
            bars.append((lb, 0.0, v, v, kind))
            run = v
        elif kind == "in":
            bars.append((lb, run, run + v, v, kind))
            run += v
        else:
            bars.append((lb, run - v, run, v, kind))
            run -= v
    top = max(max(b[2] for b in bars), max(b[1] for b in bars)) or 1
    ticks, top = nice_ticks(top * 1.06, 5)

    def Y(v):
        return y1 - (y1 - y0) * (v / top)

    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="全周期资金分配瀑布（期初 → 回收流入 → 逐级扣减 → 期末）" '
         f'style="width:100%;height:auto;display:block" class="v2c-svg">']
    g.append(f'<text class="v2c-note v2c-valuenote" text-anchor="end" font-size="{fs_unit}" '
             f'fill="{MUTE}" x="{W-4}" y="12">单位：{unit}</text>')
    for t in ticks:
        yy = Y(t)
        g.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{AXIS_LOW if t == 0 else AXIS_GRID}" stroke-width="1"></line>')
        g.append(f'<text class="v2c-ax" x="{x0-10}" y="{yy+4:.1f}" text-anchor="end" '
                 f'font-size="{fs_ax}" fill="{SUB}">{fmt_num(t, nd)}</text>')
    # 图例
    leg = [("回收流入", GREEN), ("处置费用", RED), ("服务报酬", AMBER),
           ("证券本息", NAVY), ("期末余额", INK3)]
    lx = x0 + 96
    for nm, col in leg:
        g.append(f'<rect x="{lx}" y="17.5" width="9" height="9" rx="2" fill="{col}"></rect>')
        g.append(f'<text class="v2c-leg v2c-wfleg" x="{lx+13}" y="26" font-size="{fs_leg}" '
                 f'fill="{INK3}">{esc(nm)}</text>')
        lx += 22 + len(nm) * 12
    # 柱
    for i, (lb, ylo, yhi, v, kind) in enumerate(bars):
        cx = x0 + bw * (i + 0.5)
        ya, yb = Y(yhi), Y(ylo)
        h = max(1.5, yb - ya)
        col = {"open": INK3, "in": GREEN, "out": RED, "sec": NAVY, "close": INK}[kind]
        if "服务" in lb:
            col = AMBER
        tip = f'{lb}｜{fmt_num(v, nd)} {unit}'
        g.append(f'<rect class="v2c-wbar" x="{cx-bar/2:.1f}" y="{ya:.1f}" width="{bar:.1f}" '
                 f'height="{h:.1f}" rx="2" fill="{col}" opacity="0.9"><title>{esc(tip)}</title></rect>')
        g.append(f'<text x="{cx:.1f}" y="{ya-5:.1f}" text-anchor="middle" font-size="{fs_val}" '
                 f'fill="{INK2}">{fmt_num(v, nd)}</text>')
        if i:
            g.append(f'<line x1="{cx-bar/2-bw*0.16:.1f}" y1="{yb:.1f}" x2="{cx-bar/2:.1f}" '
                     f'y2="{yb:.1f}" stroke="{INK4}" stroke-width="0.8" stroke-dasharray="2 2"></line>')
        lab = lb if len(lb) <= 6 else lb[:5] + "…"
        g.append(f'<text x="{cx:.1f}" y="{y1+18}" text-anchor="middle" font-size="{fs_x}" '
                 f'fill="{SUB}">{esc(lab)}</text>')
    g.append(f'<text x="{x0}" y="{H-8}" font-size="{fs_foot}" fill="{MUTE}">'
             f'中间项按金额降序排列，非合同支付顺序</text>')
    g.append("</svg>")
    return "".join(g)


# ==================== 分档累计本金走势（堆叠面积） ====================
def stack_area(series, xlabels, unit="亿元", W=680, H=300, nd=2):
    """series: [{'name','color','data'}]  自下而上堆叠"""
    L, R, T, B = 68, 22, 46, 48
    x0, x1 = L, W - R
    y0, y1 = T, H - B
    n = len(xlabels)
    step = (x1 - x0) / max(1, n - 1)
    tot = [sum(s["data"][i] for s in series) for i in range(n)]
    ticks, top = nice_ticks(max(tot) * 1.05, 5)

    def Y(v):
        return y1 - (y1 - y0) * (v / top)

    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="分档累计本金走势" '
         f'style="width:100%;height:auto;display:block" class="v2c-svg">']
    g.append(f'<text class="v2c-note" x="{x0}" y="16" font-size="10.5" fill="{MUTE}">单位：{unit}</text>')
    for t in ticks:
        yy = Y(t)
        g.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{AXIS_LOW if t == 0 else AXIS_GRID}" stroke-width="1"></line>')
        g.append(f'<text class="v2c-ax" x="{x0-10}" y="{yy+4:.1f}" text-anchor="end" '
                 f'font-size="11" fill="{SUB}">{fmt_num(t, nd)}</text>')
    lx = W - R - 168
    for s in series:
        g.append(f'<rect x="{lx}" y="10" width="9" height="9" rx="2" fill="{s["color"]}"></rect>')
        g.append(f'<text x="{lx+13}" y="18.5" font-size="10.5" fill="{INK3}">{esc(s["name"])}</text>')
        lx += 22 + len(s["name"]) * 12
    base = [0.0] * n
    for s in series:
        pts_top = [(x0 + step * i, Y(base[i] + s["data"][i])) for i in range(n)]
        pts_bot = [(x0 + step * i, Y(base[i])) for i in range(n)]
        d = f'M{pts_top[0][0]:.1f},{pts_top[0][1]:.1f} '
        d += " ".join(f'L{x:.1f},{y:.1f}' for x, y in pts_top[1:])
        d += " " + " ".join(f'L{x:.1f},{y:.1f}' for x, y in reversed(pts_bot))
        d += " Z"
        g.append(f'<path d="{d}" fill="{s["color"]}" opacity="0.82"></path>')
        base = [base[i] + s["data"][i] for i in range(n)]
    every = max(1, math.ceil(n / 6))
    for i in range(n):
        if i % every and i != n - 1:
            continue
        g.append(f'<text class="v6-xlabel" x="{x0+step*i:.1f}" y="{H-20}" text-anchor="middle" '
                 f'font-size="11" fill="{SUB}">{esc(xlabels[i])}</text>')
        g.append(f'<rect class="v2c-band" data-i="{i}" x="{x0+step*i-step/2:.1f}" y="{y0}" '
                 f'width="{step:.1f}" height="{y1-y0}"><title>{esc(xlabels[i])}｜'
                 + "｜".join(f'{s["name"]} {fmt_num(s["data"][i], nd)} {unit}' for s in series)
                 + f'｜合计 {fmt_num(tot[i], nd)} {unit}</title></rect>')
    g.append("</svg>")
    return "".join(g)


# ==================== 分布图：柱 + 累计线（双轴） ====================
def dist_col_pareto(items, unit="亿元", W=352, H=182, cum=True, nd=2, color=None):
    """items: [{'label','val','pct','tip'}]  val 已换算到展示单位"""
    color = color or NAVY
    L, R, T, B = 34, 30, 26, 44
    x0, x1 = L, W - R
    y0, y1 = T, H - B
    n = len(items)
    # ★ 空序列必须挡在前面：`dist_col_pareto([])` 会让 n=0，
    #   `(x1-x0)/0` 直接 ZeroDivisionError，把整份报告崩在绘图上。
    #   调用方本应在维度缺失时走置灰格，但宁可这里兜住，也不要让一张图毁掉全篇。
    if n == 0:
        return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="无数据">'
                f'<rect x="0" y="0" width="{W}" height="{H}" fill="none"/>'
                f'<text x="{W/2}" y="{H/2}" text-anchor="middle" font-size="11" '
                f'fill="{MUTE}">本维度不适用（源未披露）</text></svg>')
    bw = (x1 - x0) / n
    bar = min(26, bw * 0.62)
    vmax = max(i["val"] for i in items) * 1.06 or 1
    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="分布图" '
         f'data-xdraw="1" class="v6-donut v2c-svg" style="width:100%;height:auto;display:block" '
         f'data-v2c-dist="1" data-v2c-charttype="col-pareto">']
    g.append(f'<text class="v2c-note v2c-valuenote" text-anchor="end" font-size="10.5" '
             f'fill="{MUTE}" x="{W-4}" y="12">单位：{unit}</text>')
    # 左轴 3 档 / 右轴 3 档
    for k, frac in ((0, 0.0), (1, 0.5), (2, 1.0)):
        yy = y1 - (y1 - y0) * frac
        g.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{AXIS_LOW if k == 0 else AXIS_GRID}" stroke-width="1"></line>')
        g.append(f'<text x="{x0-4}" y="{yy+3.5:.1f}" text-anchor="end" font-size="9.5" '
                 f'fill="{MUTE}">{fmt_num(vmax*frac, nd)}</text>')
        if cum:
            g.append(f'<text x="{x1+4}" y="{yy+3.5:.1f}" font-size="9.5" fill="#8A94A6">'
                     f'{frac*100:.2f}%</text>')
    # 柱
    acc = 0.0
    cpts = []
    tot = sum(i["val"] for i in items) or 1
    for i, it in enumerate(items):
        cx = x0 + bw * (i + 0.5)
        h = (y1 - y0) * (it["val"] / vmax)
        g.append(f'<rect class="v2c-dbar" x="{cx-bar/2:.1f}" y="{y1-h:.1f}" width="{bar:.1f}" '
                 f'height="{max(1,h):.1f}" rx="1.5" fill="{color}">'
                 f'<title>{esc(it["tip"])}</title></rect>')
        if h > 14:
            g.append(f'<text x="{cx:.1f}" y="{y1-h-5:.1f}" text-anchor="middle" font-size="9.5" '
                     f'fill="{INK2}">{fmt_num(it["val"], nd)}{unit}</text>')
        acc += it["val"]
        cpts.append((cx, y1 - (y1 - y0) * (acc / tot)))
        # x 轴旋转标签
        lab = it["label"] if len(it["label"]) <= 8 else it["label"][:7] + "…"
        g.append(f'<text x="{cx:.1f}" y="{y1+14}" dy="0" text-anchor="end" font-size="10" '
                 f'fill="#5B6472" transform="rotate(-28 {cx:.1f} {y1+14})">{esc(lab)}</text>')
    if cum and len(cpts) >= 2:
        g.append(f'<path d="{mono_path(cpts)}" fill="none" stroke="{RED}" stroke-width="1.6" '
                 f'stroke-linejoin="round"></path>')
        for x, y in cpts:
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#fff" stroke="{RED}" '
                     f'stroke-width="1.4"></circle>')
    g.append("</svg>")
    return "".join(g)


# ==================== 分布图：100% 堆叠条 / 单类占比条 ====================
def dist_stack_bar(items, W=352, H=118, nd=2):
    """items: [{'label','pct','tip','color'}]  横向 100% 堆叠 + 图例（两行）"""
    if not items:
        return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="无数据">'
                f'<text x="{W/2}" y="{H/2}" text-anchor="middle" font-size="11" '
                f'fill="{MUTE}">本维度不适用（源未披露）</text></svg>')
    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="占比分布" '
         f'data-xdraw="1" class="v6-donut v2c-svg" style="width:100%;height:auto;display:block" '
         f'data-v2c-dist="1" data-v2c-charttype="stack-bar">']
    bx, by, bw, bh = 12, 18, W - 24, 26
    x = bx
    for it in items:
        w = bw * it["pct"] / 100.0
        g.append(f'<rect x="{x:.1f}" y="{by}" width="{max(0.6,w):.1f}" height="{bh}" '
                 f'rx="1.5" fill="{it["color"]}"><title>{esc(it["tip"])}</title></rect>')
        if w > 46:
            g.append(f'<text x="{x+w/2:.1f}" y="{by+17}" text-anchor="middle" font-size="10" '
                     f'fill="#fff" font-weight="600">{it["pct"]:.2f}%</text>')
        x += w
    ly = by + bh + 18
    lx = 12
    for it in items:
        lab = f'{it["label"]} {it["pct"]:.2f}%'
        if lx + len(lab) * 6.4 > W - 12:
            lx = 12
            ly += 15
        g.append(f'<rect x="{lx}" y="{ly-8}" width="8" height="8" rx="2" fill="{it["color"]}"></rect>')
        g.append(f'<text x="{lx+12}" y="{ly-1}" font-size="10" fill="{SUB}">{esc(lab)}</text>')
        lx += 14 + len(lab) * 6.6
    g.append("</svg>")
    return "".join(g)


# ==================== 分布图：垂直柱（有序分箱，无累计线） ====================
def dist_col(items, unit="亿元", W=352, H=182, nd=2, color=None, hi=None):
    if not items:
        return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="无数据">'
                f'<text x="{W/2}" y="{H/2}" text-anchor="middle" font-size="11" '
                f'fill="{MUTE}">本维度不适用（源未披露）</text></svg>')
    color = color or NAVY
    L, R, T, B = 34, 12, 26, 44
    x0, x1 = L, W - R
    y0, y1 = T, H - B
    n = len(items)
    bw = (x1 - x0) / n
    bar = min(30, bw * 0.6)
    vmax = max(i["val"] for i in items) * 1.14 or 1
    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="分布图" '
         f'data-xdraw="1" class="v6-donut v2c-svg" style="width:100%;height:auto;display:block" '
         f'data-v2c-dist="1" data-v2c-charttype="col">']
    g.append(f'<text class="v2c-note v2c-valuenote" text-anchor="end" font-size="10.5" '
             f'fill="{MUTE}" x="{W-4}" y="12">单位：{unit}</text>')
    for k in (0, 1, 2):
        frac = k / 2
        yy = y1 - (y1 - y0) * frac
        g.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{AXIS_LOW if k == 0 else AXIS_GRID}" stroke-width="1"></line>')
        g.append(f'<text x="{x0-4}" y="{yy+3.5:.1f}" text-anchor="end" font-size="9.5" '
                 f'fill="{MUTE}">{fmt_num(vmax*frac, nd)}</text>')
    for i, it in enumerate(items):
        cx = x0 + bw * (i + 0.5)
        h = (y1 - y0) * (it["val"] / vmax)
        col = RED if (hi and it["label"] in hi) else color
        g.append(f'<rect class="v2c-dbar" x="{cx-bar/2:.1f}" y="{y1-h:.1f}" width="{bar:.1f}" '
                 f'height="{max(1,h):.1f}" rx="1.5" fill="{col}"><title>{esc(it["tip"])}</title></rect>')
        g.append(f'<text x="{cx:.1f}" y="{y1-h-5:.1f}" text-anchor="middle" font-size="9.5" '
                 f'fill="{INK2}">{fmt_num(it["val"], nd)}</text>')
        g.append(f'<text x="{cx:.1f}" y="{y1+14}" text-anchor="end" font-size="10" fill="#5B6472" '
                 f'transform="rotate(-28 {cx:.1f} {y1+14})">{esc(it["label"][:9])}</text>')
    g.append("</svg>")
    return "".join(g)


# ==================== 分布图：排序横条 TopN + 其他 ====================
def dist_hbar(items, unit="亿元", W=352, nd=2, color=None, topn=8):
    if not items:
        return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="无数据">'
                f'<text x="{W/2}" y="{H/2}" text-anchor="middle" font-size="11" '
                f'fill="{MUTE}">本维度不适用（源未披露）</text></svg>')
    color = color or NAVY
    items = sorted(items, key=lambda x: -x["val"])
    head, rest = items[:topn], items[topn:]
    rows = list(head)
    if rest:
        rows.append({"label": f"其他（{len(rest)} 类）", "val": sum(r["val"] for r in rest),
                     "tip": f'其他 {len(rest)} 类合计', "other": True})
    rh = 20
    H = 18 + len(rows) * rh + 12
    L, R = 88, 58
    pw = W - L - R
    vmax = max(r["val"] for r in rows) or 1
    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="TopN 分布" '
         f'data-xdraw="1" class="v6-donut v2c-svg" style="width:100%;height:auto;display:block" '
         f'data-v2c-dist="1" data-v2c-charttype="hbar">']
    g.append(f'<text x="{W-4}" y="10" text-anchor="end" font-size="10.5" fill="{MUTE}">'
             f'单位：{unit}</text>')
    for i, r in enumerate(rows):
        yy = 16 + i * rh
        w = pw * r["val"] / vmax
        col = INK4 if r.get("other") else color
        g.append(f'<rect x="{L}" y="{yy+3:.1f}" width="{max(1,w):.1f}" height="{rh-9}" rx="1.5" '
                 f'fill="{col}" opacity="0.92"><title>{esc(r["tip"])}</title></rect>')
        g.append(f'<text x="{L-6}" y="{yy+rh/2+2:.1f}" text-anchor="end" font-size="9.5" '
                 f'fill="{INK3}">{esc(r["label"][:10])}</text>')
        g.append(f'<text x="{L+w+6:.1f}" y="{yy+rh/2+2:.1f}" font-size="9.5" fill="{INK2}">'
                 f'{fmt_num(r["val"], nd)}</text>')
    g.append("</svg>")
    return "".join(g)
