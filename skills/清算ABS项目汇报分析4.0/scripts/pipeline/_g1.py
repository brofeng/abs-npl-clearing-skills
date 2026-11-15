# -*- coding: utf-8 -*-
"""兴瑞 10 单 G1 字节级门禁：同 stage 重建 → SHA256 比对 → 写本单 golden

★ G1 证明的是「同一输入 + 同一代码，两次构建字节一致」，即**可复现**；
  它不证明「与上一版一致」—— 兴瑞是本轮首次建基线，历史不存在可比对象。
  真正把关质量的是 G3（语义断言），G1 只负责抓"构建不可复现"这类问题
  （模板里混入时间戳、字典序不稳定、随机数、依赖外部状态）。
"""
import hashlib
import json
import os
import subprocess
import sys

PY = sys.executable
# ★ 4.0：路径一律来自环境变量，不写死盘符/用户名/品牌名。
#   ABS_BATCH  = 批次根（各期子目录的父目录）
#   ABS_PREFIX = 期次目录名前缀（如 兴瑞 / 建鑫 / 惠元 / 和萃）
#   ABS_SKILL  = 技能根（缺省由本文件位置反推）
_HERE = os.path.dirname(os.path.abspath(__file__))
B = os.environ.get('ABS_BATCH') or os.path.dirname(os.path.dirname(_HERE))
PREFIX = os.environ.get('ABS_PREFIX') or ''
SCR = _HERE
SK = os.environ.get('ABS_SKILL') or os.path.dirname(os.path.dirname(_HERE))
SK = os.path.join(SK, 'scripts', 'single')
if not PREFIX:
    sys.exit('必须设置 ABS_PREFIX（期次目录名前缀，如 兴瑞）')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


rows = []
names = sorted(d for d in os.listdir(B)
               if d.startswith(PREFIX) and os.path.isdir(os.path.join(B, d)))
for n in names:
    pj = os.path.join(B, n)
    od = os.path.join(pj, '03_报告产出')
    reps = [f for f in os.listdir(od) if f.endswith('_v2.html') and not f.startswith('_')]
    if not reps:
        print(f'{n:18s} 无产物')
        rows.append([n, '', '', '', False])
        continue
    rep = reps[0]
    rp = os.path.join(od, rep)
    h1 = sha(rp)

    stage = os.path.join(B, '_g1', n)
    rc = subprocess.run([PY, '14_to_layout.py', '--proj', pj, '--stage', stage],
                        capture_output=True, text=True, encoding='utf-8', cwd=SCR).returncode
    if rc:
        print(f'{n:18s} 适配失败')
        rows.append([n, rep, h1, '', False])
        continue
    env = dict(os.environ, ABS_ASSETS=stage)
    subprocess.run([PY, 'build_single.py', '--no-guard', '--out', od],
                   capture_output=True, text=True, encoding='utf-8', env=env, cwd=SK)
    h2 = sha(rp)
    same = (h1 == h2)

    gd = os.path.join(od, 'golden')
    os.makedirs(gd, exist_ok=True)
    hp = os.path.join(gd, 'report.sha256')
    if os.path.exists(hp):
        old = open(hp, encoding='utf-8').read().strip().split()[0]
        if old != h2:
            with open(os.path.join(gd, 'history.tsv'), 'a', encoding='utf-8',
                      newline='') as f:
                f.write(f'{old}\t{h2}\t兴瑞首次建基线\t2026-10-30\n')
    with open(hp, 'w', encoding='utf-8', newline='') as f:
        f.write(f'{h2}  {rep}\n')
    rows.append([n, rep, h2, os.path.getsize(rp), same])
    print(f"{n:18s} {'G1 PASS' if same else 'G1 FAIL'}  {h2[:16]}  {os.path.getsize(rp):,}B")

json.dump(rows, open(os.path.join(B, '_g1.json'), 'w', encoding='utf-8', newline=''),
          ensure_ascii=False, indent=1)
print('G1', sum(1 for r in rows if r[4]), '/', len(rows))
