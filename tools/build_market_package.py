# -*- coding: utf-8 -*-
"""从仓库内完整版技能生成 WorkBuddy 技能市场上架包（≤3MB）。

平台约束（实测）
- 仅接受 .zip，压缩后 ≤ 3MB；
- SKILL.md 必须位于 zip 内第一层目录；
- frontmatter 必须含 name / version / display_name / display_name_en
  / description_zh / description_en，version 为三段式 SemVer。

做法：完整版留在 skills/，市场包剔除「体积大且可再生」的基线资产，
并在包内写 references/99-完整资产包获取.md 指路回本仓库。

用法：
    python -X utf8 tools/build_market_package.py            # 生成 market/*.zip
    python -X utf8 tools/build_market_package.py --check    # 只校验不写盘
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MARKET = ROOT / "market"
STAGE = ROOT / ".stage"

MAX_ZIP = 3 * 1024 * 1024

# 市场包中剔除的路径（相对技能目录）
EXCLUDE = {
    "清算ABS项目汇报分析4.0": [
        "assets/golden/screens",
        "assets/single/golden",
    ],
    "清算ABS多行工作台聚合展示": [
        "assets/workbench",
    ],
}

# 技能名 → 市场包文件名
ZIPNAME = {
    "清算ABS项目汇报分析4.0": "abs-clearing-report-4.2.0.zip",
    "清算ABS多行工作台聚合展示": "abs-workbench-1.0.0.zip",
}

NOTE = """# 完整资产包获取（市场版说明）

本市场包为 **≤3MB 上架版**。为保证上传通过，剔除了体积大且**可再生**的基线资产；
方法、脚本、文档、契约、口径台账 **全部保留**，技能逻辑零删减。

## 一、剔除了什么

{rows}

## 二、怎么拿回完整资产

### 方式 A：克隆仓库（推荐，含全部资产）

```bash
git clone https://github.com/brofeng/abs-npl-clearing-skills.git
```

仓库 `skills/` 下即完整版，直接复制到 `%USERPROFILE%\\.workbuddy\\skills\\`。

### 方式 B：只下载资产包

到 `https://github.com/brofeng/abs-npl-clearing-skills/releases` 下载对应附件，
解压覆盖到本技能目录，结构与完整版一致。

## 三、没有完整资产包时能不能用

能。三条主线都不依赖大资产：

1. **从零做单项目报告**：`scripts/pipeline/` + `scripts/single/build_single.py`，用你自己的
   PDF 取数；
2. **从零做 N 单工作台**：`scripts/aggregate_rows.py` + `scripts/build_workbench.py`，用你自己的
   行数据重建；
3. **口径与踩坑**：`references/` 全部保留，这是本技能最贵的部分。

只有「与既有交付件做字节级比对」「与参考实现做像素比对」需要完整资产包。
"""

ROWS = {
    "清算ABS项目汇报分析4.0": [
        ("`assets/golden/screens/`", "≈8 MB", "25 张像素回归截图", "仅影响视觉回归比对；语义门禁不受影响"),
        ("`assets/single/golden/`", "≈1.7 MB", "单项目 golden 规格基线", "首次复刻无法与基线字节比对"),
    ],
    "清算ABS多行工作台聚合展示": [
        ("`assets/workbench/`", "≈11.4 MB", "V9 参考实现（含 74 份报告正文）", "无法直接打开成品，需按脚本重建"),
    ],
}


def human(n: int) -> str:
    return f"{n / 1024 / 1024:.2f} MB"


def build_one(skill: str) -> Path:
    src = SKILLS / skill
    if not src.is_dir():
        raise SystemExit(f"缺少技能目录：{src}")
    dst = STAGE / skill
    if dst.exists():
        shutil.rmtree(dst)
    skip = EXCLUDE.get(skill, [])

    for dirpath, dirnames, filenames in os.walk(src):
        rel_dir = Path(dirpath).relative_to(src).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        keep = []
        for d in dirnames:
            rel = f"{rel_dir}/{d}".lstrip("/")
            if any(rel == s or rel.startswith(s + "/") for s in skip):
                continue
            keep.append(d)
        dirnames[:] = keep
        (dst / rel_dir).mkdir(parents=True, exist_ok=True)
        for f in filenames:
            rel = f"{rel_dir}/{f}".lstrip("/")
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(dirpath) / f, dst / rel)

    # 包内说明
    rows = "\n".join(
        f"| {p} | {s} | {w} | {i} |" for p, s, w, i in ROWS.get(skill, [])
    )
    note = dst / "references" / "99-完整资产包获取.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        NOTE.replace("{rows}", "| 路径 | 体积 | 作用 | 缺失影响 |\n|---|---|---|---|\n" + rows),
        encoding="utf-8",
    )

    # SKILL.md 追加市场版说明
    md = dst / "SKILL.md"
    text = md.read_text(encoding="utf-8")
    marker = "## 市场版（≤3MB 上架包）说明"
    if marker not in text:
        block = f"""
---

{marker}

> 本包是从完整仓库裁剪出的**上架版**：方法、脚本、references、契约、口径台账全量保留，
> 仅剔除体积大且可再生的基线资产（截图 / golden / 参考实现），以保证 zip ≤ 3MB。

- 已剔除：{", ".join("`" + p + "`" for p in skip) or "（无）"}
- 完整资产包：https://github.com/brofeng/abs-npl-clearing-skills
- 剔除清单与取回方式 → **`references/99-完整资产包获取.md`**

**没有基线资产时：** 从零取数与成稿、从零聚合重建、口径与踩坑三件事都不受影响；
仅「与既有交付件做字节级/像素级比对」需要完整资产包。
"""
        md.write_text(text.rstrip() + "\n" + block, encoding="utf-8")

    return dst


def pack(skill: str, check_only: bool) -> int:
    dst = build_one(skill)
    name = ZIPNAME.get(skill, f"{skill}.zip")
    target = MARKET / name
    if not check_only:
        MARKET.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(dst.rglob("*")):
                if p.is_file():
                    z.write(p, f"{skill}/{p.relative_to(dst).as_posix()}")
        size = target.stat().st_size
    else:
        import io

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(dst.rglob("*")):
                if p.is_file():
                    z.write(p, f"{skill}/{p.relative_to(dst).as_posix()}")
        size = len(buf.getvalue())

    n = sum(1 for p in dst.rglob("*") if p.is_file())
    ok = size <= MAX_ZIP
    print(f"  {skill}: {n} files, zip {human(size)} -> {'OK' if ok else '!! 超过 3MB'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验体积，不写盘")
    args = ap.parse_args()

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    rc = 0
    for skill in EXCLUDE:
        print(f"[build] {skill}")
        rc |= pack(skill, args.check)
    shutil.rmtree(STAGE, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
