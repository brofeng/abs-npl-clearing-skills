# -*- coding: utf-8 -*-
"""逐科目对账：受托报告原文 vs 成稿 payload/metrics

★ 为什么单列一个脚本：报告里的汇总数（优先档付息合计、次级档收益合计）
  很容易"总额对、明细错"——本轮的三个真缺陷（年度报告期次重复、按清算口径
  等比例缩放、次级固资漏提）全都属于这一类，只看汇总看不出来。
  对账必须**逐期**做，并把「受托报告原文解析值」与「成稿值」并排打印。

输出（均为 UTF-8 BOM、CRLF，Excel 直接可开）：
  00_最新版_20261030_v3/_科目对账_10单.csv
  00_最新版_20261030_v3/_逐期兑付明细_10单.csv
"""
import csv
import glob
import json
import os

B = r'E:/兴业银行兴瑞冒烟测试'
OUT = os.path.join(B, '00_最新版_20261030_v3')
os.makedirs(OUT, exist_ok=True)


def jload(p):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def f2(v):
    return '' if v is None else f'{v:.2f}'


def num(v):
    return '' if v is None else f'{v:,.2f}'


rows_sum, rows_per = [], []
for d in sorted(glob.glob(os.path.join(B, '兴瑞*'))):
    if not os.path.isdir(d):
        continue
    name = os.path.basename(d)
    P = jload(os.path.join(d, '02_提取数据', 'payload.json'))
    M = jload(os.path.join(d, '02_提取数据', 'metrics.json'))
    TR = jload(os.path.join(d, '02_提取数据', '_trustee_parsed.json'))
    L = jload(os.path.join(d, '02_提取数据', '_liq_parsed.json'))
    if not P:
        continue
    T = P.get('tranche') or {}
    LQ = P.get('liquidation') or {}
    PS = P.get('periods') or []
    TRP = TR.get('periods') or []

    # ── 原文解析值（未经 08 校准）──
    tr_si = sum(p.get('sen_interest') or 0 for p in TRP)
    tr_sp = sum(p.get('sen_principal') or 0 for p in TRP)

    def add(subject, src, got, note=''):
        rows_sum.append([name, subject, src, got,
                         '' if (src in ('', None) or got in ('', None)) else '',
                         note])

    add('优先档 发行额', num((T.get('senior') or {}).get('issue')),
        num(M.get('sen_issue')), '说明书/清算报告')
    add('优先档 本金兑付合计', num(tr_sp), num(M.get('sen_principal_paid')),
        '逐期「本期兑付本金」加总 vs 清算报告归属优先收益')
    add('优先档 付息合计', num(tr_si), num(M.get('sen_interest_paid')),
        '逐期「付息金额」加总；与清算报告「归属于优先级持有人收益」须相等')
    add('优先档 票面利率', '', f"{(T.get('senior') or {}).get('coupon') or 0:.2%}", '')
    add('优先档 XIRR', '', f"{(M.get('sen_xirr') or 0):.2%}",
        '按逐期真实支付日折现；与票面偏差应 < 10bp')
    add('次级档 发行额', num((T.get('sub') or {}).get('issue')),
        num(M.get('sub_issue')), '')
    add('次级档 本金兑付', num(sum(p.get('sub_principal') or 0 for p in TRP)),
        num(M.get('sub_principal_paid')), '')
    add('次级档 固定资金成本',
        num(sum(max(0.0, ((p.get('outflow') or {}).get('证券利息总支出') or 0.0)
                    - (p.get('sen_interest') or 0.0)) for p in TRP)),
        num(M.get('sub_fixed_total')),
        '受托报告「证券利息总支出 − 优先档付息」原值；折年化约 10%')
    add('次级档 超额收益', num(sum((p.get('sub_income') or 0) for p in TRP)),
        num(M.get('sub_excess_total')), '受托报告「次级档超额收益」科目')
    add('次级档 收益合计', num(L.get('sub_income_paid')),
        num((M.get('sub_fixed_total') or 0) + (M.get('sub_excess_total') or 0)),
        '清算报告「归属于次级持有人收益」')
    add('次级档 回报倍数', '', f"{(M.get('sub_multiple') or 0):.4f}", '')
    add('次级档 XIRR', '', f"{(M.get('sub_xirr') or 0):.2%}",
        '存续期短者不可年化外推')
    add('累计回收', num(LQ.get('total_recovery')), num(M.get('recovered')),
        '清算报告「收回基础资产回收款」（含清仓回购价款）')
    bb = (LQ.get('buyback') or {}).get('price')
    add('清仓回购价款', num(bb) if bb is not None else '未披露',
        num(LQ.get('buyback_inflow')),
        '未披露者不倒推')
    add('存续期（月）', '', f"{(M.get('life_months') or 0):.1f}", '')

    # 剔除的年度累计期次
    for x in (P.get('dropped_annual') or []):
        rows_sum.append([name, '剔除：年度受托机构报告累计期次',
                         x.get('pay_date'), '', '',
                         x.get('reason')])

    # ── 逐期明细 ──
    for p in PS:
        rows_per.append([
            name, p.get('period'), p.get('pay_date'),
            num(p.get('sen_principal')), num(p.get('sen_interest')),
            num(p.get('sub_principal')), num(p.get('sub_fixed_cost')),
            num(p.get('sub_income')), num(p.get('in_total')),
            num(p.get('out_total')),
            p.get('pay_date_basis') or '',
        ])

with open(os.path.join(OUT, '_科目对账_10单.csv'), 'w', encoding='utf-8-sig',
          newline='') as f:
    w = csv.writer(f)
    w.writerow(['项目', '科目', '受托报告/清算报告口径', '成稿口径', '', '说明'])
    w.writerows(rows_sum)

with open(os.path.join(OUT, '_逐期兑付明细_10单.csv'), 'w', encoding='utf-8-sig',
          newline='') as f:
    w = csv.writer(f)
    w.writerow(['项目', '期次', '支付日', '优先档本金', '优先档付息',
                '次级档本金', '次级档固定资金成本', '次级档超额收益',
                '本期回收', '本期流出', '支付日来源说明'])
    w.writerows(rows_per)

print(f'汇总 {len(rows_sum)} 行 / 逐期 {len(rows_per)} 行 → {OUT}')
