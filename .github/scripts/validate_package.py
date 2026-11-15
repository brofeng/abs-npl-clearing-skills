# -*- coding: utf-8 -*-
"""仓库自检：CI 与本地共用。

检查项
1. 每个技能目录有 SKILL.md，frontmatter 含平台要求的字段，version 为三段式 SemVer；
2. name 与目录名一致（安装后目录名即技能名）；
3. 全部 .py 可解析（ast）；
4. market/*.zip 压缩包 ≤ 3MB，且 SKILL.md 位于包内第一层目录；
5. 源码中不含本机用户名路径痕迹。

用法：python -X utf8 .github/scripts/validate_package.py
"""
from __future__ import annotations

import ast
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
MARKET = ROOT / "market"

REQUIRED = ["name", "version", "display_name", "display_name_en", "description_zh", "description_en"]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
USERPATH = re.compile(r"C:\\Users\\\d{3,}|C:/Users/\d{3,}")
MAX_ZIP = 3 * 1024 * 1024

errors: list[str] = []
warnings: list[str] = []


def read_frontmatter(p: Path) -> dict[str, str]:
    text = p.read_text(encoding="utf-8")
    if not text.startswith("---"):
        errors.append(f"{p.relative_to(ROOT)}: 首行不是 --- frontmatter")
        return {}
    body = text.split("---", 2)[1]
    data: dict[str, str] = {}
    for line in body.splitlines():
        if not line or line.startswith((" ", "\t")) or ":" not in line:
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip()
    return data


def check_skills() -> None:
    if not SKILLS.is_dir():
        errors.append("缺少 skills/ 目录")
        return
    for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if not md.is_file():
            errors.append(f"{d.name}: 缺少 SKILL.md")
            continue
        fm = read_frontmatter(md)
        missing = [k for k in REQUIRED if not fm.get(k)]
        if missing:
            errors.append(f"{d.name}: frontmatter 缺少 {', '.join(missing)}")
        ver = fm.get("version", "")
        if ver and not SEMVER.match(ver):
            errors.append(f"{d.name}: version '{ver}' 不是三段式 SemVer（如 1.0.0）")
        if fm.get("name") and fm["name"] != d.name:
            warnings.append(f"{d.name}: name 字段 '{fm['name']}' 与目录名不一致（安装后以目录名为准）")
        print(f"  skill OK: {d.name} v{ver}")


def check_python() -> None:
    bad = 0
    for p in SKILLS.rglob("*.py"):
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as e:
            errors.append(f"{p.relative_to(ROOT)}: 语法错误 line {e.lineno}: {e.msg}")
            bad += 1
    print(f"  python parsed: {len(list(SKILLS.rglob('*.py'))) - bad} files")


def check_market() -> None:
    zips = sorted(MARKET.glob("*.zip"))
    if not zips:
        warnings.append("market/ 下没有 zip")
    for z in zips:
        size = z.stat().st_size
        if size > MAX_ZIP:
            errors.append(f"{z.name}: {size/1048576:.2f} MB 超过平台 3MB 上限")
        with zipfile.ZipFile(z) as f:
            names = f.namelist()
            if not any(n.count("/") == 1 and n.endswith("SKILL.md") for n in names):
                errors.append(f"{z.name}: 包内第一层没有 SKILL.md（平台固定在该位置解析）")
        print(f"  zip OK: {z.name} {size/1048576:.2f} MB / {len(names)} files")


def check_userpaths() -> None:
    for p in list(SKILLS.rglob("*.py")) + list(SKILLS.rglob("*.md")) + list(SKILLS.rglob("*.json")):
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = USERPATH.search(t)
        if m:
            errors.append(f"{p.relative_to(ROOT)}: 含本机用户名路径 '{m.group(0)}'，请改为环境变量或占位符")


def main() -> int:
    print("[1/4] 校验技能包结构")
    check_skills()
    print("[2/4] 校验 Python 语法")
    check_python()
    print("[3/4] 校验市场包")
    check_market()
    print("[4/4] 校验路径脱敏")
    check_userpaths()

    for w in warnings:
        print(f"WARN  {w}")
    if errors:
        print()
        for e in errors:
            print(f"FAIL  {e}")
        return 1
    print("\n全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
