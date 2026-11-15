# -*- coding: utf-8 -*-
"""兴业银行（兴瑞系列）不良ABS 全池范围核定

★ 目的：把「哪些做了、哪些没做、为什么不做」变成一张可核对的表，
  而不是靠印象说"应该还有"。

三源交叉（与 10 单已交付件一致）：
  ① NPL项目_资产类型与清算_全表.csv      —— 项目池 + 是否已清算
  ② 中债清算公告_全量.json                —— 清算审计报告 / 受托报告期数 / 成立公告日
  ③ 本地已做 10 单的 payload.meta         —— 已做单的发行日、法定到期日真值

判定规则（用户口径）：
  纳入 = 发行日 ≥ 2021-01-01 且 （已取得清算文书 或 法定到期日 ≤ 基准日）
  其中「法定到期日」优先取真值；无真值时按「成立公告日 + 5 年」推算并明确标注，
  不得当作真值使用。

输出：E:/兴业银行兴瑞冒烟测试/00_最新版_20261030_v3/_兴业银行项目池核定.csv
"""
import csv
import glob
import json
import os
import re
from datetime import date, timedelta

B = r'E:/兴业银行兴瑞冒烟测试'
DIAG = r'E:/不良ABS穿透研究/193单穿透复现_工作区/40_回补/diag'
OUT = os.path.join(B, '00_最新版_20261030_v3')
TODAY = date(2026, 10, 30)

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7,
      '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}


def cn2int(s):
    if s.isdigit():
        return int(s)
    if s == '十一':
        return 11
    if s == '十二':
        return 12
    return CN.get(s, 0)


# ── ① 项目池 ──────────────────────────────────────────────
pool = {}
with open(os.path.join(DIAG, 'NPL项目_资产类型与清算_全表.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        if not r['项目'].startswith('兴瑞'):
            continue
        m = re.match(r'兴瑞(\d{4})年第(.+?)期$', r['项目'])
        if not m:
            continue
        pool[r['项目']] = {
            'year': int(m.group(1)), 'seq': cn2int(m.group(2)),
            'kind': r.get('类型') or '', 'liq': (r.get('已清算') == '是'),
            'liqfile': r.get('清算文件') or '',
        }

# ── ② 公告：成立公告日 + 清算审计报告 + 最新受托报告期数 ──────
ann = {}
with open(os.path.join(DIAG, '中债清算公告_全量.json'), encoding='utf-8') as f:
    docs = json.load(f)['list']
pat = re.compile(r'兴瑞(\d{4})年第([一二三四五六七八九十]+)期')
for x in docs:
    t = x.get('docTitle') or ''
    m = pat.search(t)
    if not m:
        continue
    k = f'兴瑞{m.group(1)}年第{m.group(2)}期'
    if k not in pool:
        continue
    d = (x.get('shengXiaoShiJian') or '')[:10]
    a = ann.setdefault(k, {'est': None, 'liq_doc': None, 'last': '', 'last_title': '',
                           'n_tr': 0})
    if '成立公告' in t and d:
        a['est'] = min(filter(None, [a['est'], d])) if a['est'] else d
    if '清算' in t and ('审计' in t or '复核' in t):
        a['liq_doc'] = d
    if '受托机构报告' in t:
        mm = re.search(r'第([一二三四五六七八九十百]+)期', t)
        if mm:
            v = a['n_tr']
            try:
                import unicodedata  # noqa
                zh = mm.group(1).replace('百', '')
                val = 0
                if len(zh) >= 2 and zh[0] == '十':
                    val = 10 + cn2int(zh[1:])
                elif '十' in zh:
                    p, q = zh.split('十')
                    val = cn2int(p) * 10 + (cn2int(q) if q else 0)
                else:
                    val = cn2int(zh)
                v = max(v, val)
            except Exception:
                pass
            a['n_tr'] = v
    if d > a['last']:
        a['last'] = d
        a['last_title'] = t

# ── ③ 已做单的真值 ────────────────────────────────────────
done = {}
for d in sorted(glob.glob(os.path.join(B, '兴瑞*'))):
    fp = os.path.join(d, '02_提取数据', 'payload.json')
    if not os.path.exists(fp):
        continue
    P = json.load(open(fp, encoding='utf-8'))
    meta, L = P.get('meta') or {}, P.get('liquidation') or {}
    done[os.path.basename(d)] = {
        'issue': meta.get('issue_date'),
        'legal': meta.get('legal_maturity'),
        'liqdate': L.get('liquidation_date'),
        'rep': [f for f in os.listdir(os.path.join(d, '03_报告产出'))
                if f.endswith('_v3.html') and not f.startswith('_')],
    }
# 已做目录名是「兴瑞2021年第一期」，池子里同名（阿拉伯数字期次不同写法无碍）

rows = []
for k, p in sorted(pool.items(), key=lambda kv: (kv[1]['year'], kv[1]['seq'])):
    a = ann.get(k, {})
    dn = done.get(k)
    issue = (dn or {}).get('issue') or a.get('est')
    legal = (dn or {}).get('legal')
    legal_src = '真值（说明书）'
    if not legal and issue:
        # 推算：成立日 + 5 年（已做 10 单实测区间 +4年5月 ~ +5年1月）
        y, m, dd = map(int, issue.split('-'))
        legal = f'{y + 5:04d}-{m:02d}-{dd:02d}'
        legal_src = '推算（成立日+5年）'
    elif not legal:
        legal_src = '不可得'
    is_liq = bool(p['liq'] or a.get('liq_doc') or (dn or {}).get('liqdate'))
    overdue = False
    if legal and legal_src.startswith('真值') or (legal and issue):
        try:
            overdue = date(*map(int, legal.split('-'))) <= TODAY
        except Exception:
            overdue = False
    in_scope = (p['year'] >= 2021) and (is_liq or overdue)
    if dn:
        state = '已完成 v3'
    elif is_liq:
        state = '已清算·待做'
    elif overdue:
        state = '过法定日期·待做'
    else:
        state = f'存续中（最新第 {a.get("n_tr") or "?"} 期受托报告）'
    rows.append([
        k, f"{p['year']}年第{p['seq']}期", p['kind'] or '—',
        issue or '—', legal or '—', legal_src,
        '是' if is_liq else '否', '是' if overdue else '否',
        '纳入' if in_scope else '不纳入',
        state, a.get('last') or '—',
        (dn.get('rep') or [''])[0] if dn else '',
    ])

os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, '_兴业银行项目池核定.csv')
with open(p, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['项目', '期次', '资产类型', '发行/成立日', '法定到期日', '法定到期日来源',
                '已清算', '过法定日期', '是否纳入', '当前状态',
                '最新公告日', '已交付文件'])
    w.writerows(rows)

n_all = len(rows)
n_done = sum(1 for r in rows if r[9] == '已完成 v3')
n_scope = sum(1 for r in rows if r[8] == '纳入')
n_wait = sum(1 for r in rows if r[9] in ('已清算·待做', '过法定日期·待做'))
n_alive = sum(1 for r in rows if r[9].startswith('存续中'))
print(f'全池 {n_all} 单｜纳入口径 {n_scope} 单｜已完成 {n_done} 单'
      f'｜待做 {n_wait} 单｜存续中 {n_alive} 单')
print(f'→ {p}')
print()
print(f"{'项目':20s}{'发行日':>12s}{'法定到期日':>13s}{'来源':>18s}  {'状态'}")
for r in rows:
    print(f'{r[0]:20s}{r[3]:>12s}{r[4]:>13s}{r[5]:>18s}  {r[9]}')
