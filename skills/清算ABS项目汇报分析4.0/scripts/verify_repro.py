#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""verify_repro.py —— 复刻验收一键门禁（DoD）

这是本技能的**唯一验收入口**。任何 agent 交付前必须跑它并拿到 EXIT=0。

三级门禁（由严到宽，前一级过则后续可跳过）：
  G1 哈希门禁   产物 SHA256 == assets/golden/report.sha256 → 字节级一致，直接 PASS
  G2 指纹门禁   逐视图比对「版式 + 文案 + 字号」指纹（probe_report.py）
  G3 视觉门禁   逐视图像素比对黄金截图（visual_regression.py，可选/较慢）

用法：
    # 标准验收（G1 → G2）
    <python> verify_repro.py --html <你的产出.html>

    # 加上视觉回归（慢，约 3 分钟）
    <python> verify_repro.py --html <产出.html> --visual

    # 只跑某一级
    <python> verify_repro.py --html <产出.html> --level 1|2|3

退出码：0 = 全过；1 = 未过
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SKILL = Path(__file__).resolve().parent.parent
GOLDEN = SKILL / "assets" / "golden"
SCRIPTS = SKILL / "scripts"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, title):
    print(f"\n{'='*74}\n{title}\n{'='*74}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip())
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--level", choices=["1", "2", "3"], help="只跑到某一级")
    ap.add_argument("--visual", action="store_true", help="启用 G3 视觉回归（慢）")
    ap.add_argument("--py", default=sys.executable)
    args = ap.parse_args()

    html = Path(args.html).resolve()
    if not html.exists():
        raise SystemExit(f"❌ 产物不存在：{html}")
    py = args.py
    results = []

    # ── G1 哈希 ──
    hs = GOLDEN / "report.sha256"
    g1 = None
    if hs.exists():
        exp = json.loads(hs.read_text(encoding="utf-8-sig"))
        got = sha256(html)
        ok = got == exp["sha256"]
        g1 = ok
        print(f"\n{'='*74}\nG1 哈希门禁\n{'='*74}")
        print(f"  期望 {exp['sha256']}  ({exp['bytes']:,} B, {exp['version']})")
        print(f"  实得 {got}  ({html.stat().st_size:,} B)")
        if ok:
            print("\n✅ G1 通过：产物与基线**字节级一致**（最强保证，跳过 G2/G3）")
            results.append(("G1 哈希", True))
            return finish(results)
        print("\n⚠ G1 未通过 —— 若你是**有意的改版**，请按本文末「更新基线」流程；")
        print("  若你是**复刻**，说明产品已漂移，继续跑 G2 定位差异。")
        results.append(("G1 哈希", False))
    else:
        print("⚠ 未找到 assets/golden/report.sha256，跳过 G1")

    if args.level == "1":
        return finish(results)

    # ── G2 指纹 ──
    spec = GOLDEN / "report_spec.json"
    if spec.exists():
        rc = run([py, str(SCRIPTS / "probe_report.py"),
                  "--html", str(html), "--mode", "verify", "--spec", str(spec)],
                 "G2 指纹门禁（版式 + 文案 + 字号）")
        results.append(("G2 指纹", rc == 0))
        if rc != 0:
            print("\n❗ G2 未通过：上面的差异就是「和标准长得不一样」的地方。")
            print("   修复方式：不要手改产物，而是检查")
            print("     ① 是否用的 skill 自带 scripts/v2 模块（而不是自己重写）")
            print("     ② 是否漏跑某个模块 / 模块版本不对")
            print("     ③ 是否改了 window-size（响应式会让栅格列数变）")
    else:
        print("⚠ 未找到 report_spec.json，跳过 G2")

    if args.level == "2":
        return finish(results)

    # ── G3 视觉 ──
    screens = GOLDEN / "screens"
    if args.visual or args.level == "3":
        if screens.exists() and any(screens.glob("*.png")):
            rc = run([py, str(SCRIPTS / "visual_regression.py"),
                      "--html", str(html), "--mode", "verify", "--golden", str(screens)],
                     "G3 视觉门禁（像素比对）")
            results.append(("G3 视觉", rc == 0))
        else:
            print("⚠ 未找到黄金截图，跳过 G3")

    return finish(results)


def finish(results):
    print(f"\n{'='*74}\n复刻验收结论\n{'='*74}")
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    hard = [r for r in results if r[0] != "G1 哈希"]
    passed = all(ok for _, ok in hard) if hard else any(ok for _, ok in results)
    if passed:
        print("\n✅ DoD 通过：可以交付")
        return 0
    print("\n❌ DoD 未通过：不得交付。请按上面提示定位修复后再跑。")
    print("""
更新基线（**仅在你确认新版本更好、且改动有意为之**时）：
   <python> scripts/probe_report.py --html <新产物> --mode extract \\
            --out assets/golden/report_spec.json
   <python> scripts/gen_layout_doc.py --spec assets/golden/report_spec.json \\
            --out references/12-版式像素规格.md
   <python> scripts/visual_regression.py --html <新产物> --mode snapshot \\
            --out assets/golden/screens
   并把新 SHA256 写入 assets/golden/report.sha256
   ⚠ 更新基线必须在 README 写明「为什么变」，否则视为回归。
""")
    return 1


if __name__ == "__main__":
    sys.exit(main())
