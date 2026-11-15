# -*- coding: utf-8 -*-
"""兴瑞 10 单全量产线：02→07→03→05→06→08 →14 → build → verify

每单独立跑，单点失败不影响其他单；结果落 _xr_all.json 便于汇总。
"""
import subprocess, sys, os, json, glob

PY = sys.executable
# ★ 4.0：路径来自环境变量（ABS_BATCH / ABS_PREFIX / ABS_SKILL），不写死。
_HERE = os.path.dirname(os.path.abspath(__file__))
B = os.environ.get('ABS_BATCH') or os.path.dirname(os.path.dirname(_HERE))
PREFIX = os.environ.get('ABS_PREFIX') or ''
SCR = _HERE
SK = os.environ.get('ABS_SKILL') or os.path.dirname(os.path.dirname(_HERE))
SK = os.path.join(SK, 'scripts', 'single')
if not PREFIX:
    sys.exit('必须设置 ABS_PREFIX（期次目录名前缀，如 兴瑞）')
STEPS = ['02_parse_prospectus.py', '07_parse_rating.py', '03_parse_dist.py',
         '05_parse_trustee.py', '06_parse_liquidation.py', '08_assemble.py']


def run(step, pj, cwd):
    r = subprocess.run([PY, step, '--proj', pj], capture_output=True, text=True,
                       encoding='utf-8', cwd=cwd)
    return r.returncode, ((r.stderr or r.stdout or '').strip().splitlines() or [''])[-1][:90]


rows = []
names = sorted(d for d in os.listdir(B)
               if d.startswith(PREFIX) and os.path.isdir(os.path.join(B, d)))
for n in names:
    pj = os.path.join(B, n)
    err = None
    for sc in STEPS:
        rc, tail = run(sc, pj, SCR)
        if rc:
            err = f'{sc}: {tail}'
            break
    if err:
        print(f'{n:18s} X 数据 {err}', flush=True)
        rows.append([n, 'datfail', err, 0, '', []])
        continue

    # 每单独立 stage：共用目录在并行/中断时会把上一单的数据混进下一单
    stage = os.path.join(B, '_stage', n)
    rc = subprocess.run([PY, '14_to_layout.py', '--proj', pj, '--stage', stage],
                        capture_output=True, text=True, encoding='utf-8', cwd=SCR).returncode
    if rc:
        print(f'{n:18s} X 适配', flush=True)
        rows.append([n, 'adapt', '', 0, '', []])
        continue

    od = os.path.join(pj, '03_报告产出')
    os.makedirs(od, exist_ok=True)
    for f in glob.glob(os.path.join(od, '*.html')):
        if not os.path.basename(f).startswith('_'):
            os.remove(f)
    env = dict(os.environ, ABS_ASSETS=stage)
    r = subprocess.run([PY, 'build_single.py', '--no-guard', '--out', od],
                       capture_output=True, text=True, encoding='utf-8', env=env, cwd=SK)
    reps = [f for f in os.listdir(od) if f.endswith('_v2.html') and not f.startswith('_')]
    if r.returncode or not reps:
        tail = ((r.stderr or r.stdout or '').strip().splitlines() or [''])[-1][:90]
        print(f'{n:18s} X 构建 {tail}', flush=True)
        rows.append([n, 'build', tail, 0, '', []])
        continue

    rp = os.path.join(od, reps[0])
    r = subprocess.run([PY, 'verify_single.py', '--html', rp, '--assets', stage],
                       capture_output=True, text=True, encoding='utf-8', cwd=SK)
    out = r.stdout or ''
    line = [l for l in out.splitlines() if l.startswith('断言 ')]
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith('[') and '✗' in l]
    skips = []
    grab = False
    for l in out.splitlines():
        if '跳过' in l and '项' in l:
            grab = True
            continue
        if grab:
            if l.strip().startswith('['):
                skips.append(l.strip())
            elif l.strip().startswith('分组'):
                grab = False
    tag = 'OK' if not fails else f'FAIL{len(fails)}'
    print(f'{n:18s} {os.path.getsize(rp):>8,}B  {line[0] if line else "?"}  {tag}', flush=True)
    for f_ in fails:
        print('     ', f_, flush=True)
    rows.append([n, tag, line[0] if line else '', os.path.getsize(rp), reps[0],
                 {'fails': fails, 'skips': skips}])

json.dump(rows, open(os.path.join(B, '_xr_all.json'), 'w', encoding='utf-8', newline=''),
          ensure_ascii=False, indent=1)
print('ALL DONE', flush=True)
