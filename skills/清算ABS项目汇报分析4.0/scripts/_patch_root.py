#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_patch_root.py —— 把 7 个模块的硬编码根路径改为可配置

用法（由开发者运行一次，产物已固化进技能）：
    <python> _patch_root.py --dir <技能内 scripts/v2 目录>

改造后每个模块顶部都有：
    _HOME = _resolve_home()      # 环境变量 NPL_ABS_HOME → 同目录 _root.txt → 默认 E:\不良ABS穿透研究
优先级：NPL_ABS_HOME 环境变量 > 同目录 _root.txt > 默认路径
"""
import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RESOLVER = '''
# ── 根路径解析（v12：支持搬迁）─────────────────────────────────────
# 优先级：环境变量 NPL_ABS_HOME > 本目录 _root.txt > 默认 E:\\不良ABS穿透研究
# 目标结构：<HOME>\\清算28单_单项目穿透\\ 与 <HOME>\\清算28单_不良ABS分析\\
def _resolve_home():
    import os as _os
    from pathlib import Path as _P
    _v = _os.environ.get("NPL_ABS_HOME")
    if _v:
        _p = _P(_v)
        if _p.exists():
            return _p
    _c = _P(__file__).resolve().parent / "_root.txt"
    if _c.exists():
        try:
            _s = _c.read_text(encoding="utf-8").strip()
            if _s and _P(_s).exists():
                return _P(_s)
        except Exception:
            pass
    return _P(r"E:\\不良ABS穿透研究")
_HOME = _resolve_home()
# ──────────────────────────────────────────────────────────────────
'''

# 逐文件替换规则：(文件名, [(旧串, 新串), ...])
RULES = {
    "00_ctx.py": [
        ('E = Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析")',
         'E = _HOME / "清算28单_不良ABS分析"'),
        ('RAW_PAYLOAD = Path(r"E:\\不良ABS穿透研究\\清算28单_单项目穿透\\_校验件\\payload.json")',
         'RAW_PAYLOAD = _HOME / "清算28单_单项目穿透" / "_校验件" / "payload.json"'),
    ],
    "10_overview.py": [
        ('_E = Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析")',
         '_E = _HOME / "清算28单_不良ABS分析"'),
    ],
    "30_compare.py": [
        ('ROOT = Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析")',
         'ROOT = _HOME / "清算28单_不良ABS分析"'),
        ('RAW = Path(r"E:\\不良ABS穿透研究\\清算28单_单项目穿透\\_校验件\\payload.json")',
         'RAW = _HOME / "清算28单_单项目穿透" / "_校验件" / "payload.json"'),
    ],
    "40_audit.py": [
        ('_E = Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析")',
         '_E = _HOME / "清算28单_不良ABS分析"'),
    ],
    "60_assets.py": [
        ('for p in (Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析\\清算28单_不良ABS穿透分析报告_v2.html"),\n'
         '              Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析\\清算28单_横向对照与逐单稽核_合并版.html")):',
         'for p in (_HOME / "清算28单_不良ABS分析" / "清算28单_不良ABS穿透分析报告_v2.html",\n'
         '              _HOME / "清算28单_不良ABS分析" / "清算28单_横向对照与逐单稽核_合并版.html"):'),
    ],
    "70_wording.py": [],   # 无硬编码根路径（只有正则里的 E:\ 字面量，不动）
    "build_v2.py": [
        ('E = Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析")',
         'E = _HOME / "清算28单_不良ABS分析"'),
        ('ORIG = Path(r"E:\\不良ABS穿透研究\\清算28单_单项目穿透\\清算28单_单项目穿透_报告.html")',
         'ORIG = _HOME / "清算28单_单项目穿透" / "清算28单_单项目穿透_报告.html"'),
    ],
    "verify_v2.py": [
        ('E = Path(r"E:\\不良ABS穿透研究\\清算28单_不良ABS分析")',
         'E = _HOME / "清算28单_不良ABS分析"'),
    ],
}


def patch_one(p: Path) -> bool:
    s = p.read_text(encoding="utf-8")
    if "_resolve_home" in s:
        print(f"   skip {p.name}（已打补丁）")
        return False
    rules = RULES.get(p.name, [])
    changed = 0
    for old, new in rules:
        if old in s:
            s = s.replace(old, new)
            changed += 1
        else:
            print(f"   ⚠ {p.name} 未匹配：{old[:60]}")
    if not changed:
        print(f"   skip {p.name}（无硬编码根路径）")
        return False

    # 在最后一个 import 之后插入 resolver
    m = None
    for m in re.finditer(r"^(?:import|from)\s+[^\n]+\n", s, re.M):
        pass
    if not m:
        print(f"   ❌ {p.name} 找不到 import 锚点")
        return False
    pos = m.end()
    s = s[:pos] + RESOLVER + s[pos:]
    p.write_text(s, encoding="utf-8")
    print(f"   ✅ {p.name}  替换 {changed} 处 + 插入 resolver")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="scripts/v2 目录")
    args = ap.parse_args()
    d = Path(args.dir)
    if not d.exists():
        print(f"目录不存在：{d}")
        sys.exit(2)
    print("=" * 70)
    print(f"打补丁：{d}")
    print("=" * 70)
    n = 0
    for f in RULES:
        p = d / f
        if not p.exists():
            print(f"   ❌ 缺文件 {f}")
            continue
        if patch_one(p):
            n += 1
    print(f"\n完成：{n} 个文件已打补丁")
    print("提示：可在同目录放 _root.txt（内容为新的根路径）或设环境变量 NPL_ABS_HOME")


if __name__ == "__main__":
    main()
