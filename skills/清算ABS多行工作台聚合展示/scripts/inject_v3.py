# -*- coding: utf-8 -*-
"""The only V3 injection implementation for the multi-deal workbench.

V9 base + v3 source + 74-row data -> V9 output (byte-identical when inputs match).
All paths are package-relative; safe to run from any directory / agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "assets" / "workbench" / "不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"
ROWS = ROOT / "assets" / "data" / "_rows_all.json"
SRC = ROOT / "assets" / "source"
OUT = ROOT / "dist" / "不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def inject(base: Path, rows: Path, out: Path, quiet: bool = False) -> dict:
    html = base.read_text(encoding="utf-8")
    css = (
        (SRC / "v3.css").read_text(encoding="utf-8")
        + "\n\n"
        + (SRC / "v3-extra.css").read_text(encoding="utf-8")
        + "\n\n"
        + (SRC / "v3-gold.css").read_text(encoding="utf-8")
    )
    js = (SRC / "v3.js").read_text(encoding="utf-8")
    echarts = (SRC / "echarts.min.js").read_text(encoding="utf-8", errors="ignore")
    echarts = echarts.replace("</script", "<\\/script")
    full = json.loads(rows.read_text(encoding="utf-8"))
    full_json = json.dumps(full, ensure_ascii=False, separators=(",", ":")).replace("</script", "<\\/script")

    # idempotent: strip the previous injected blocks
    html = re.sub(r"\n?<!--V3_STYLE_START-->.*?<!--V3_STYLE_END-->\n?", "\n", html, flags=re.S)
    html = re.sub(r"\n?<!--V3_LIB_START-->.*?<!--V3_LIB_END-->\n?", "\n", html, flags=re.S)
    html = re.sub(r"\n?<!--V3_DATA_START-->.*?<!--V3_DATA_END-->\n?", "\n", html, flags=re.S)
    html = re.sub(r"\n?<!--V3_APP_START-->.*?<!--V3_APP_END-->\n?", "\n", html, flags=re.S)

    if '<body class="v3">' not in html:
        html = html.replace("<body>", '<body class="v3">', 1)

    style = (
        '<!--V3_STYLE_START-->\n<style id="v3-theme">\n'
        + css
        + "\n</style>\n<!--V3_STYLE_END-->"
    )
    i = html.find("</head>")
    if i < 0:
        raise SystemExit("BASE_INVALID: no </head>")
    html = html[:i] + style + "\n" + html[i:]

    lib = (
        '<!--V3_LIB_START-->\n<script id="v3-echarts">/* Apache ECharts 6.1.0 (Apache-2.0) */\n'
        + echarts
        + "\n</script>\n<!--V3_LIB_END-->"
    )
    data = (
        '<!--V3_DATA_START-->\n<script id="v3-full-data">const V3_FULL = '
        + full_json
        + ";</script>\n<!--V3_DATA_END-->"
    )
    app = '<!--V3_APP_START-->\n<script id="v3-app">\n' + js + "\n</script>\n<!--V3_APP_END-->"
    i = html.rfind("</body>")
    if i < 0:
        raise SystemExit("BASE_INVALID: no </body>")
    html = html[:i] + lib + "\n" + data + "\n" + app + "\n" + html[i:]

    out.parent.mkdir(parents=True, exist_ok=True)
    # Keep the original writer semantics: this is what produced V9 in the reference environment.
    out.write_text(html, encoding="utf-8")
    b = out.read_bytes()
    info = {"out": str(out), "bytes": len(b), "sha256": sha256_bytes(b), "rows": len(full)}
    if not quiet:
        print("INJECTED", info["bytes"], "bytes", "sha256", info["sha256"], "rows", info["rows"])
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(BASE))
    ap.add_argument("--rows", default=str(ROWS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    inject(Path(args.base), Path(args.rows), Path(args.out), args.quiet)


if __name__ == "__main__":
    main()
