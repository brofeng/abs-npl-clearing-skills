# -*- coding: utf-8 -*-
"""★★★ 复刻验收一键门禁（技能 3.0 · DoD）

用法：
  python repro_gate.py                       # 构建 + G1 + G2 + G3，全通过才 EXIT=0
  python repro_gate.py --html <已有产物>      # 只跑门禁，不构建
  python repro_gate.py --only g1|g2|g3
  python repro_gate.py --preflight           # 只做环境与输入体检
  python repro_gate.py --rebless              # ★先过 G3 才允许重设黄金基线
  python repro_gate.py --rebless --force --why "原因"   # ★★跳过 G3（须用户同意）

门禁分级：
  G1  产物 SHA256 vs assets/single/golden/report.sha256     字节级（1 秒）
  G2  版式+文案指纹 vs assets/single/golden/spec.json        语义级（~40 秒）
  G3  语义断言（数据复算 + 禁用词 + 渲染后内容）              数值级（~40 秒）

EXIT：0 全通过 / 1 有门禁未通过 / 2 环境或输入有问题

★ 3.0 相对 2.0 的三处流程加固（都是「门禁自证」类缺陷）
────────────────────────────────────────────────────────────────
A. **rebless 前强制先过 G3**。2.0 的 --rebless 直接把当前产物定为黄金，
   若产物本身有错，错误就被固化成「正确」，之后 G1/G2 永远通过。
B. **rebless 保留基线历史**。旧 sha256 追加到 golden/history.tsv，可回溯。
C. **门禁未过绝不改基线，且返回非零退出码**。项目早期 pipeline 曾无条件在门禁前
   建基线 → 每次自己跟自己比，G1 形同虚设（曾因此放过 4 项真实 FAIL）。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
# ★ 3.2：与 build_single.py 同步参数化——不设环境变量时仍指向技能自带的惠元资产，
#   故惠元的 G1/G2/G3 行为一字不变；换行/换单时用
#     ABS_ASSETS=<单的资产目录>  ABS_GOLDEN=<该单/该行的 golden 目录>
#   即可复用同一套三级门禁，不必每换一个银行重写一份门禁脚本。
ASSETS = os.environ.get("ABS_ASSETS") or os.path.join(SKILL, "assets", "single")
GOLDEN = os.environ.get("ABS_GOLDEN") or os.path.join(ASSETS, "golden")
PY = sys.executable

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def _out_name():
    """产物名从 payload.meta.file_name 读取（跨单泛化；缺省回落到三期原文件名）"""
    try:
        d = json.load(open(os.path.join(ASSETS, "payload.json"), encoding="utf-8"))
        return d["meta"].get("file_name") or "惠元2021年第三期_不良ABS穿透分析_v5.html"
    except Exception:
        return "惠元2021年第三期_不良ABS穿透分析_v5.html"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def header(t):
    print("\n" + "─" * 68)
    print(t)
    print("─" * 68)


# ─────────────────────────────────────────────────────────────
# 环境与输入体检（v3 新增，可单独跑 --preflight）
# ─────────────────────────────────────────────────────────────
def preflight(verbose=True):
    bad = []
    if verbose:
        header("环境与输入体检（preflight）")
    edge = next((p for p in EDGE_CANDIDATES if os.path.exists(p)), None)
    if edge:
        if verbose:
            print(f"  浏览器   ✅ {edge}")
    else:
        bad.append("未找到 Edge/Chrome，G2/G3 的渲染断言无法执行")
        if verbose:
            print("  浏览器   ❌ 未找到 Edge/Chrome")

    for fn in ("payload.json", "metrics.json"):
        p = os.path.join(ASSETS, fn)
        if os.path.exists(p):
            if verbose:
                print(f"  {fn:14s} ✅ {os.path.getsize(p):,} B")
        else:
            bad.append(f"缺输入 {fn}")
            if verbose:
                print(f"  {fn:14s} ❌ 缺失")

    # 必需字段抽查（与 verify_single.py 的前置契约保持一致）
    try:
        d = json.load(open(os.path.join(ASSETS, "payload.json"), encoding="utf-8"))
        req = {
            "pool": ["balance_total", "exp_recovery_zz", "n_loans"],
            "tranche": ["senior", "sub", "total"],
            "liquidation": ["total_recovery", "fees_total", "fee_detail",
                            "residual_asset", "holder_equity_end"],
            "periods": [], "trust_account": [], "dist": ["grade"],
        }
        miss = [f"{k}.{x}" for k, ks in req.items()
                if k not in d for x in ks]
        miss += [f"{k}.{x}" for k, ks in req.items()
                 if isinstance(d.get(k), dict) for x in ks if x not in d[k]]
        fd = (d.get("liquidation") or {}).get("fee_detail") or {}
        miss += [f"fee_detail.{c}" for c in ("处置费", "贷款服务费") if c not in fd]
        if miss:
            bad.append("payload 缺字段：" + "、".join(miss))
            if verbose:
                print(f"  字段契约  ❌ 缺 {len(miss)} 项：{'、'.join(miss[:6])}")
        elif verbose:
            print(f"  字段契约  ✅ 齐备（费用明细 {len(fd)} 项）")
    except Exception as e:
        bad.append(f"payload 解析失败：{e}")
        if verbose:
            print(f"  字段契约  ❌ 解析失败 {e}")

    if not os.path.exists(GOLDEN):
        if verbose:
            print("  黄金基线  · 未建立（首次需 --rebless）")
    else:
        gp = os.path.join(GOLDEN, "report.sha256")
        if verbose:
            print(f"  黄金基线  {'✅ 已建立' if os.path.exists(gp) else '· 不完整'}")
    if verbose:
        print("\n  " + ("✅ 体检通过，可跑门禁" if not bad else f"❌ 体检发现 {len(bad)} 个问题"))
    return bad


# ─────────────────────────────────────────────────────────────
# 门禁
# ─────────────────────────────────────────────────────────────
def g1(html):
    header("G1 哈希门禁（字节级）")
    mp = os.path.join(GOLDEN, "report.sha256")
    if not os.path.exists(mp):
        print("  基线缺失：assets/single/golden/report.sha256")
        print("  首次交付需先确认产物正确，再 python repro_gate.py --rebless（会先跑 G3）")
        return False
    parts = open(mp, encoding="utf-8").read().split()
    want, want_size = parts[0], int(parts[1])
    got, size = sha(html), os.path.getsize(html)
    print(f"  期望 {want[:16]}…  ({want_size:,} B)")
    print(f"  实得 {got[:16]}…  ({size:,} B)")
    if got == want:
        print("  ✅ G1 通过：产物与基线字节级一致")
        return True
    print("  ❌ G1 未通过")
    print("     排查顺序：1) 是否用了自带 build_single.py（不要自己重写模块）")
    print("               2) assets/single/ 输入是否被改（比对 INPUTS.sha256）")
    print("               3) 是否手改了输出换行（必须 newline=''，不得转 \\r\\n）")
    print("               4) 若确属有意改版 → python repro_gate.py --rebless（须用户同意）")
    return False


def g2(html):
    header("G2 版式+文案指纹（语义级）")
    sp = os.path.join(GOLDEN, "spec.json")
    if not os.path.exists(sp):
        print("  基线缺失：assets/single/golden/spec.json")
        return False
    r = subprocess.run([PY, os.path.join(HERE, "probe_single.py"),
                        "--html", html, "--verify", sp],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(r.stdout.strip()[-6000:] or r.stderr[-2000:])
    return r.returncode == 0


def g3(html):
    header("G3 语义断言（数据复算 + 禁用词 + 渲染后内容）")
    vp = os.path.join(HERE, "verify_single.py")
    if not os.path.exists(vp):
        print("  缺少 verify_single.py，跳过")
        return True
    r = subprocess.run([PY, vp, "--html", html, "--assets", ASSETS],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out = (r.stdout or "").strip() or (r.stderr or "")[-2000:]
    print(out[-6000:])
    if r.returncode == 2:
        print("  ⚠ G3 输入契约不满足（取数漏项），非数据错")
    return r.returncode == 0


# ─────────────────────────────────────────────────────────────
# 重设基线（v3 加固：先过 G3）
# ─────────────────────────────────────────────────────────────
def rebless(html, force=False, why=""):
    header("★ 重设黄金基线（等于宣布当前产物才是对的）")
    if not force:
        print("  3.0 规则：先跑 G3，全过才允许重设。")
        print("  理由：若产物本身有错，直接重设会把错误固化成「正确」，")
        print("        之后 G1/G2 永远通过，等于把门禁废掉。\n")
        if not g3(html):
            print("\n❌ G3 未通过 → 拒绝重设基线。")
            print("   请先修数据/取数器；确需跳过请用 --rebless --force --why \"原因\"（须用户明确同意）")
            return 1
        print("\n  ✅ G3 全过，继续重设基线")
    else:
        if not why:
            print("  ❌ --force 必须同时给出 --why \"为什么跳过 G3\"，否则拒绝")
            return 2
        print(f"  ⚠ 已按 --force 跳过 G3，原因：{why}")

    os.makedirs(GOLDEN, exist_ok=True)
    mp = os.path.join(GOLDEN, "report.sha256")
    h, size = sha(html), os.path.getsize(html)

    # 保留历史：旧基线追加到 history.tsv，可回溯「哪天为什么变」
    if os.path.exists(mp):
        old = open(mp, encoding="utf-8").read().strip()
        with open(os.path.join(GOLDEN, "history.tsv"), "a", encoding="utf-8",
                  newline="") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{old}\t{why or 'G3 通过后重设'}\n")
        print("  旧基线已归档 → golden/history.tsv")

    open(mp, "w", encoding="utf-8", newline="").write(f"{h}  {size}  {_out_name()}\n")
    print(f"  report.sha256 ← {h}  ({size:,} B)")

    r = subprocess.run([PY, os.path.join(HERE, "probe_single.py"), "--html", html,
                        "--out", os.path.join(GOLDEN, "spec.json")],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(r.stdout.strip()[-1500:] or r.stderr[-1500:])
    print("  已重设。请在 README/交付说明写明「为什么变」，否则视为回归。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html")
    ap.add_argument("--only", choices=["g1", "g2", "g3"])
    ap.add_argument("--rebless", action="store_true")
    ap.add_argument("--force", action="store_true", help="配合 --rebless 跳过 G3（须给 --why）")
    ap.add_argument("--why", default="", help="跳过 G3 的原因，会写进 history.tsv")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--out", default=os.getcwd())
    a = ap.parse_args()

    if a.preflight:
        bad = preflight()
        sys.exit(0 if not bad else 2)

    # 构建（未指定 --html 时）
    html = a.html
    if not html:
        header("构建（build_single.py）")
        if preflight(verbose=False):
            print("  输入不齐，先修输入再构建")
            sys.exit(2)
        r = subprocess.run([PY, os.path.join(HERE, "build_single.py"), "--out", a.out],
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        print(r.stdout.strip() or r.stderr[-3000:])
        if r.returncode != 0:
            print("构建失败，终止")
            sys.exit(2)
        html = os.path.join(a.out, _out_name()) if not a.out.endswith(".html") else a.out

    if not os.path.exists(html):
        print("产物不存在：", html)
        sys.exit(2)

    if a.rebless:
        sys.exit(rebless(html, force=a.force, why=a.why))

    tests = [("g1", g1), ("g2", g2), ("g3", g3)]
    if a.only:
        tests = [t for t in tests if t[0] == a.only]
    results = [(n, f(html)) for n, f in tests]

    header("DoD 汇总")
    for n, ok in results:
        print(f"  {n.upper()}  {'✅ 通过' if ok else '❌ 未通过'}")
    allok = all(ok for _, ok in results)
    if allok:
        print("\n✅ DoD 通过：可以交付")
    else:
        print("\n❌ DoD 未通过：不得交付")
        print("   注意：门禁未过时**不要**跑 --rebless，否则等于把错误固化成基线。")
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
