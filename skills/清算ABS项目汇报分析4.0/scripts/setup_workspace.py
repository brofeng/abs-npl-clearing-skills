#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""setup_workspace.py —— 从技能自带资产还原工作区

技能已自包含（v2 模块 + 原始 payload + BASE 报告 + 适配层 + 设计资产），
本脚本把它们铺回 E 盘项目目录，使 build_v2.py / verify_v2.py 无需改路径即可运行。

用法：
    <python> setup_workspace.py --check              # 只检查，不写
    <python> setup_workspace.py                      # 还原到默认 E:\不良ABS穿透研究
    <python> setup_workspace.py --home D:\NPL_ABS    # 还原到指定根目录（换盘/换机）
    <python> setup_workspace.py --force              # 强制覆盖（危险！）

目录约定（脚本里硬编码的就是这两个根）：
    E:\不良ABS穿透研究\清算28单_单项目穿透\      ← BASE 报告 + _校验件/payload.json
    E:\不良ABS穿透研究\清算28单_不良ABS分析\      ← 脚本\v2 + 设计资产 + 输出
"""
import argparse
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
V2SRC = SKILL / "scripts" / "v2"

DEFAULT_HOME = Path(r"E:\不良ABS穿透研究")


def build_plan(home: Path):
    """按给定的根目录生成还原计划：[(技能内源, 目标, 说明), ...]"""
    base = home / "清算28单_单项目穿透"
    proj = home / "清算28单_不良ABS分析"
    return [
        (ASSETS / "payload.json",        base / "_校验件" / "payload.json",        "原始 payload（WF/DIST 的数据源）"),
        (ASSETS / "base_report.html",    base / "清算28单_单项目穿透_报告.html",   "BASE 报告（增强层的宿主）"),
        (ASSETS / "payload_28.json",     proj / "设计资产" / "payload_28.json",    "适配层（PROF/ORDER/FL）"),
        (ASSETS / "audit_payload.json",  proj / "设计资产" / "audit_payload.json", "稽核数据"),
        (ASSETS / "三单_design.css",     proj / "设计资产" / "三单_design.css",    "设计母版 CSS"),
    ]


def human(n):
    return f"{n/1e6:.2f} MB" if n >= 1e6 else f"{n/1e3:.1f} KB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不写")
    ap.add_argument("--force", action="store_true", help="强制覆盖（危险）")
    ap.add_argument("--home", default=None,
                    help=r"项目根目录（默认 E:\不良ABS穿透研究）")
    args = ap.parse_args()
    R = Path(args.home) if args.home else DEFAULT_HOME
    BASE = R / "清算28单_单项目穿透"
    PROJ = R / "清算28单_不良ABS分析"
    PLAN = build_plan(R)

    print("=" * 74)
    print(f"清算ABS 工作区{'检查' if args.check else '还原'}   技能目录 {SKILL}")
    print("=" * 74)

    # ── 1. 技能内资产完整性 ──
    print("\n[1] 技能自带资产")
    ok = True
    for src, dst, desc in PLAN:
        if src.exists():
            print(f"   ✅ {src.name:<26} {human(src.stat().st_size):>9}  {desc}")
        else:
            print(f"   ❌ 缺失 {src.name}  ← 技能不完整")
            ok = False
    if not V2SRC.exists():
        print("   ❌ 缺失 scripts/v2/  ← 技能不完整")
        ok = False
    else:
        n_py = len(list(V2SRC.glob("*.py")))
        need = ["00_ctx.py", "10_overview.py", "20_profile.py", "30_compare.py",
                "40_audit.py", "50_charts.py", "60_assets.py", "70_wording.py",
                "build_v2.py", "verify_v2.py"]
        miss = [f for f in need if not (V2SRC / f).exists()]
        if miss:
            print(f"   ❌ scripts/v2 缺模块：{miss}")
            ok = False
        else:
            print(f"   ✅ scripts/v2/                {n_py:>3} 个 .py（10 必要模块齐全）")

    if not ok:
        print("\n技能资产不完整，终止。")
        sys.exit(2)

    # ── 2. 目标工作区状态 ──
    print("\n[2] 目标工作区")
    need_write = []
    for src, dst, desc in PLAN:
        state = "已存在" if dst.exists() else "缺失"
        mark = "✅" if dst.exists() else "⬜"
        print(f"   {mark} {dst}")
        print(f"        {state}  ← {desc}")
        if not dst.exists():
            need_write.append((src, dst))
    # v2 模块
    v2dst = PROJ / "脚本" / "v2"
    v2_missing = [f for f in (V2SRC.glob("*.py")) if not (v2dst / f.name).exists()]
    print(f"   {'✅' if not v2_missing else '⬜'} {v2dst}")
    print(f"        {'齐全' if not v2_missing else f'缺 {len(v2_missing)} 个'}  ← 增强层脚本")

    if args.check:
        print("\n" + "=" * 74)
        print("检查完成（未写入）。" + ("工作区已就绪 ✅" if not need_write and not v2_missing
                                  else f"需还原 {len(need_write)} 个资产 + {len(v2_missing)} 个脚本"))
        print("=" * 74)
        return

    # ── 3. 还原 ──
    print("\n[3] 还原")
    if not need_write and not v2_missing and not args.force:
        print("   工作区已就绪，无需还原（加 --force 可强制覆盖）")
    else:
        for src, dst, desc in PLAN:
            if dst.exists() and not args.force:
                print(f"   skip {dst.name}（已存在）")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"   ✅ {dst}  ({human(dst.stat().st_size)})")
        v2dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(V2SRC.glob("*.py")):
            t = v2dst / f.name
            if t.exists() and not args.force:
                continue
            shutil.copy2(f, t)
            print(f"   ✅ {t.name}")
        # 写 _root.txt：让模块自动识别新根目录（搬家/换盘时关键）
        rt = v2dst / "_root.txt"
        rt.write_text(str(R), encoding="utf-8")
        print(f"   ✅ _root.txt → {R}")

    # ── 4. 自检 ──
    print("\n[4] 自检")
    py = sys.executable
    print(f"   python: {py}")
    # 数据门控
    sc = SKILL / "scripts" / "selfcheck_data.py"
    if sc.exists():
        import subprocess
        r = subprocess.run([py, str(sc), "--payload", str(BASE / "_校验件" / "payload.json")],
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        tail = [l for l in (r.stdout or "").splitlines() if ("单数" in l or "瀑布重建" in l or "门控" in l)]
        for l in tail[:4]:
            print("   " + l.strip())
        print(f"   selfcheck_data.py EXIT={r.returncode}")
    print("\n" + "=" * 74)
    print("✅ 还原完成。下一步：")
    print(f"   {py} \"{V2SRC.parent.parent.parent / 'scripts' / 'v2' / 'build_v2.py'}\"".replace(
        str(V2SRC.parent.parent.parent), str(PROJ)))
    print(f"   {py} {PROJ}\\脚本\\v2\\build_v2.py    # 组装")
    print(f"   {py} {PROJ}\\脚本\\v2\\verify_v2.py   # 144 断言验收")
    print("=" * 74)


if __name__ == "__main__":
    main()
