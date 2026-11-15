# -*- coding: utf-8 -*-
"""建鑫 中债资信评级报告解析（权威口径）

★ 为什么必须解析这份：定源铁律规定「发行规模分层与预计回收只认中债资信」。
   招行说明书第七章披露的是**主承销商**估值，与中债不一致：
   建鑫2021-2 说明书 29,000.30 万 vs 中债 31,639.62 万（差 8.3%）。
   若直接用说明书数字，达成率分母就错了。

★ 本报告是**扫描件**，必须先跑 04_extract.py --ocr 生成 ZZ.ocr.txt。

提取内容：
  · 预计回收总金额（核心）
  · 模型测算毛回收率
  · 发行规模分层（优先/次级/合计）
  · 票面利率、加权平均逾期、加权平均年龄/收入/授信
  · 静态池分组数、历史项目累计真实/预测回收比

用法：
  python 07_parse_rating.py --proj "E:\\中国建设银行建鑫冒烟测试\\建鑫2021年第2期"
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NUM = r"-?[\d,]+(?:\.\d+)?"


def ns(t):
    return re.sub(r"[\s\u3000]+", "", t or "")


def fix(t):
    from _numfix import fix as _f
    return _f(t)


def fnum(s):
    if s is None:
        return None
    # ★ 全角逗号也要认：OCR 会把千分位打成「73，080.97」（建鑫2022八期实测），
    #   只 replace 半角逗号会得到 "73，080.97" → float() 抛错 → 返回 None，
    #   表现为「该期无中债预计回收」，其实是千分位字符集没覆盖。
    s = str(s).replace(",", "").replace("，", "").replace("．", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def load_ocr(proj):
    p = os.path.join(proj, "02_提取数据", "OCR", "ZZ.ocr.txt")
    if not os.path.exists(p):
        return None, None
    return open(p, encoding="utf-8").read(), p


def parse(proj):
    txt, src = load_ocr(proj)
    R = {"_src": os.path.basename(src) if src else None}
    if not txt:
        return R
    t = ns(txt)

    # ① 预计回收总金额（权威）：优先取「核心指标对比」表里的「预计回收总金额（万元）」
    # ── 预计回收总额：★ 三级来源，按可靠性排序 ──────────────────
    # ①【最可靠】正文表述「预计总体回收率为X%，回收金额为Y万元」
    #    理由：这是针对**本期**的独立结论句，不与历史项目混排。
    #    实测 2021-4 正文 = 17.76% / 61,138.64 万元（与优先档 40,300 万、现金流合计一致）
    # ②【次选】「资产池可供分配的回收金额预计为Y万元」
    # ③【最不可靠】「核心指标对比」表首列
    #    该表是**3 个项目并排**（本期/上期/上上期），OCR 后列错位严重：
    #    2021-4 读出 `31,639.62 46.5151.11`，而 31,639.62 其实是**2021-2 的值**，
    #    照用会让达成率虚高到 191%。仅在前两级都取不到时才用，且必须与
    #    「主承销商预计回收」做 2 倍以内的合理性校验。
    # ★ 千分位可能是全角「，」（OCR 常见），三种都要认
    NUMGRP = r"\d{1,3}(?:[.,，]\d{3})*[.,，]\d{2}"
    m = None
    m1 = re.search(r"预计总体回收率为\s*([\d.]+)\s*%\s*[，,]\s*回收金额(?:为)?\s*("
                   + NUMGRP + r")\s*万元", t)
    if m1 and fnum(m1.group(1)) is not None:
        R["exp_rec_rate"] = fnum(m1.group(1)) / 100
        R["exp_recovery"] = fnum(fix(m1.group(2))) * 1e4
        R["_exp_src"] = "正文·预计总体回收率与回收金额"
    if R.get("exp_recovery") is None:
        # ★ 数值与「万元」之间可能插逗号（「预计为73，080.97万元」），\s* 不够用
        m2 = re.search(r"可供分配的回收金额预计为\s*[，,]?\s*(" + NUMGRP + r")\s*万元", t)
        if m2:
            R["exp_recovery"] = fnum(fix(m2.group(1))) * 1e4
            R["_exp_src"] = "正文·可供分配回收金额"
    if R.get("exp_recovery") is None:
        m = re.search(r"预计回收总金额\s*[（(]\s*万元\s*[）)]\s*(" + NUMGRP + ")", t)
    if not m:
        # 兜底：正文「预计总体回收率为X%，回收金额为Y万元」
        m2 = re.search(r"预计总体回收率为([\d.]+)%[，,]?回收金额为([\d,]+\.?\d*)万元", t)
        if m2 and fnum(m2.group(1)) is not None:
            R["exp_rec_rate"] = fnum(m2.group(1)) / 100
            R["exp_recovery"] = fnum(m2.group(2)) * 1e4
    if m and fnum(fix(m.group(1))) is not None and R.get("exp_recovery") is None:
        R["_exp_raw"] = m.group(1)
        R["exp_recovery"] = fnum(fix(m.group(1))) * 1e4
        R["_exp_src"] = "对比表首列（最不可靠，需交叉校验）"

    # ② 预计回收率：正文「预计总体回收率为12.35%，回收金额为31,639.62万元」
    m = re.search(r"预计总体回收率为([\d.]+)%", t)
    if m and fnum(m.group(1)) is not None:
        R["exp_rec_rate"] = fnum(m.group(1)) / 100

    # ③ 模型测算毛回收率（核心指标表）
    # 括号全半角都要认：OCR 出来的是「模型测算毛回收率(%)」（半角）
    m = re.search(r"模型测算毛回收率\s*[（(]\s*%\s*[）)]\s*([\d.]+)", t)
    if m and fnum(m.group(1)) is not None:
        R["model_recovery_rate"] = fnum(m.group(1)) / 100

    # ④ 发行规模分层：摘要表里「18,500.00」「4,900.00」「23,400.00」
    m = re.search(r"优先档.{0,60}?([\d,]+\.\d{2}).{0,30}?次级档.{0,40}?([\d,]+\.\d{2})", t)
    if m:
        R["senior_issue"] = fnum(m.group(1)) * 1e4
        R["sub_issue"] = fnum(m.group(2)) * 1e4
    m = re.search(r"发行额([\d,]+\.\d{2})", t)
    if m:
        R["total_issue"] = fnum(m.group(1)) * 1e4

    # ⑤ 票面：招行票面在发行结果公告，评级报告只写"固定利率"，此处不取

    # ⑥ 资产池指标（**只作交叉校验**，权威值仍取说明书第七章）
    #   注：交叉校验字段常有取不到的情况——评级报告「核心指标对比」表是 3 列并排，
    #   OCR 后数字粘连且列间无分隔符（`68,99574,57298.703`），只能取到第一段；
    #   若第一段本身也粘连（如「19.73」被读成「236.66」），则留空。
    #   这些字段**不参与计算**，缺失不影响任何指标。
    # ★ 评级报告的「核心指标对比」表是 3 个项目并排（本期/上期/上上期），
    #   OCR 后数字会粘连：`借款人户数68,99574,57298.703`（本期 68,995 + 74,572 + 98,703）。
    #   因此这里**只取第一个完整数字**（＝本期），且仅在说明书缺失时兜底使用。
    def first_num(kw, scale=1, as_int=False):
        k = t.find(ns(kw))
        if k < 0:
            return None
        seg = t[k + len(ns(kw)):k + len(ns(kw)) + 60]
        m = re.match(r"[（(][^）)]{0,12}[）)]?\s*([\d,]+\.?\d*)", seg) or \
            re.match(r"([\d,]+\.\d{2}|[\d,]{2,})", seg)
        if not m:
            return None
        v = fnum(m.group(1))
        if v is None:
            return None
        return int(v) if as_int else round(v * scale, 2)

    cross = {
        "n_borrowers": first_num("借款人户数", as_int=True),
        "balance_total": first_num("资产池未偿本息费余额", 1e4),
        "balance_principal": first_num("资产池未偿本金余额", 1e4),
        "wavg_overdue_months": first_num("加权平均贷款逾期期限"),
        "wavg_age": first_num("加权平均年龄"),
        "wavg_income": first_num("加权平均年收入", 1e4),
        "wavg_credit_limit": first_num("加权平均授信额度", 1e4),
    }
    R["cross_check"] = {k: v for k, v in cross.items() if v is not None}

    # 静态池分组数：9810443 = 98 / 104 / 43 三列粘连，取前 2 位
    m = re.search(r"静态池分组个数\s*[（(]\s*个\s*[）)]\s*(\d{2})", t)
    if m:
        R["static_pool_groups"] = int(m.group(1))

    # ⑦ 历史项目表现（均值）
    m = re.search(r"均值([\d.]+)", t)
    if m:
        R["hist_cum_real_vs_forecast"] = fnum(m.group(1))

    # ⑧ 首期超额覆盖
    m = re.search(r"可供分配的回收金额预计为([\d,]+\.\d+)万元", t)
    if m and fnum(m.group(1)) is not None:
        R["excess_cover_recovery"] = fnum(m.group(1)) * 1e4

    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    a = ap.parse_args()
    R = parse(a.proj)
    p = os.path.join(a.proj, "02_提取数据", "_rating_parsed.json")
    json.dump({k: v for k, v in R.items() if not k.startswith("_")},
              open(p, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)

    # 与说明书交叉校验
    smp = os.path.join(a.proj, "02_提取数据", "_sm_parsed.json")
    P = {}
    if os.path.exists(smp):
        P = json.load(open(smp, encoding="utf-8")).get("pool") or {}
    # ★ 全部改用「先取值再格式化」并做 None 保护：
    #   直接对 R.get(...) 用 :,.2f 会在字段缺失时崩（实测 2022 三期起 4 期报
    #   TypeError: unsupported format string passed to NoneType.__format__）。
    def _n(v, fmt="{:,.2f}", dash="—"):
        return dash if v is None else fmt.format(v)

    print(f"来源 {R.get('_src')}")
    print(f"  中债预计回收      {_n(R.get('exp_recovery'))} 元"
          f"（回收率 {R.get('exp_rec_rate')}）")
    print(f"  模型测算毛回收率  {R.get('model_recovery_rate')}")
    print(f"  发行分层          优先 {R.get('senior_issue')} / 次级 {R.get('sub_issue')}"
          f" / 合计 {R.get('total_issue')}")
    print(f"  资产池            笔 {R.get('n_loans')} / 户 {R.get('n_borrowers')}"
          f" / 本息费 {R.get('balance_total')}")
    print(f"  加权逾期 {R.get('wavg_overdue_months')} 月 / 年龄 {R.get('wavg_age')} 岁")
    print(f"  静态池分组 {R.get('static_pool_groups')} 组"
          f"  历史回收比均值 {R.get('hist_cum_real_vs_forecast')}")
    if P.get("exp_recovery") and R.get("exp_recovery"):
        d = R["exp_recovery"] - P["exp_recovery"]
        print(f"\n  ★ 与说明书对比：说明书（主承销商口径）{P['exp_recovery']:,.2f}")
        print(f"     差额 {d:+,.2f} 元（{(d/P['exp_recovery']*100):+.2f}%）")
        print(f"     → 按定源铁律，预计回收采用**中债** {R['exp_recovery']:,.2f}")
    elif not R.get("exp_recovery"):
        print("\n  ⚠ 未取到中债预计回收——检查 ZZ.ocr.txt 是否已 OCR")
    print(f"\n→ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
